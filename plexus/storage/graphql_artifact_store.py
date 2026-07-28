"""Application-authorized artifact transfer over GraphQL-issued HTTPS tickets.

This module deliberately knows nothing about dashboard authentication or object
storage credentials.  Callers provide a dashboard-client-compatible executor;
the application authorizes an artifact transfer and the store transfers the
bytes only through the resulting HTTPS URL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Optional, Protocol, Sequence
from urllib.parse import urlparse

import requests


_TICKET_MUTATION = """
mutation CreateArtifactTransferTickets($requests: [ArtifactTransferRequest!]!) {
  createArtifactTransferTickets(requests: $requests) {
    objectKey
    method
    url
    requiredHeaders
    expiresAt
  }
}
"""

_EXPIRY_RESPONSE_MARKERS = (
    "requestexpired",
    "expiredtoken",
    "request has expired",
    "signature has expired",
)


class GraphQLArtifactStoreError(RuntimeError):
    """Base class for artifact-store failures that must not fall back."""


class ArtifactTicketError(GraphQLArtifactStoreError):
    """The application did not return a valid transfer ticket."""


class ArtifactAuthorizationError(GraphQLArtifactStoreError):
    """The signed URL rejected the authorized transfer."""


class ArtifactTransferError(GraphQLArtifactStoreError):
    """The HTTP transfer did not complete successfully."""


class ArtifactIntegrityError(GraphQLArtifactStoreError):
    """Bytes do not match the declared size or SHA-256 digest."""


class _ExpiredSignedURL(ArtifactTransferError):
    """Internal marker permitting the single signed-URL refresh."""


class GraphQLExecutor(Protocol):
    """The stable subset supplied by ``PlexusDashboardClient``."""

    def execute(self, query: str, variables: Optional[dict[str, Any]] = None, **kwargs: Any) -> dict[str, Any]:
        ...


class HTTPSession(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        data: Optional[bytes] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class ArtifactTransferRequest:
    """One artifact request in the frozen GraphQL ticket contract."""

    operation: str
    resource_type: str
    resource_id: str
    artifact_type: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if self.operation not in {"READ", "WRITE"}:
            raise ValueError("operation must be READ or WRITE")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                self.resource_type,
                self.resource_id,
                self.artifact_type,
                self.filename,
                self.content_type,
                self.sha256,
            )
        ):
            raise ValueError("artifact request string fields must be non-empty")
        if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")
        if len(self.sha256) != 64 or any(character not in "0123456789abcdefABCDEF" for character in self.sha256):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")

    def as_graphql_input(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "artifactType": self.artifact_type,
            "filename": self.filename,
            "contentType": self.content_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class ArtifactTransferTicket:
    """A short-lived HTTPS transfer authorization returned by GraphQL."""

    object_key: str
    method: str
    url: str
    required_headers: Mapping[str, str]
    expires_at: datetime

    @classmethod
    def from_graphql(cls, ticket: Mapping[str, Any]) -> "ArtifactTransferTicket":
        try:
            object_key = ticket["objectKey"]
            method = ticket["method"]
            url = ticket["url"]
            required_headers = ticket["requiredHeaders"]
            expires_at = ticket["expiresAt"]
        except (KeyError, TypeError) as exc:
            raise ArtifactTicketError("ticket response omitted a required field") from exc

        if not isinstance(object_key, str) or not object_key:
            raise ArtifactTicketError("ticket objectKey must be non-empty")
        if method not in {"GET", "PUT"}:
            raise ArtifactTicketError("ticket method must be GET or PUT")
        parsed_url = urlparse(url) if isinstance(url, str) else None
        if not parsed_url or parsed_url.scheme.lower() != "https" or not parsed_url.netloc:
            raise ArtifactTicketError("ticket URL must use HTTPS")
        if isinstance(required_headers, str):
            try:
                required_headers = json.loads(required_headers)
            except json.JSONDecodeError as exc:
                raise ArtifactTicketError("ticket requiredHeaders must be valid JSON") from exc
        if not isinstance(required_headers, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in required_headers.items()
        ):
            raise ArtifactTicketError("ticket requiredHeaders must be a string map")
        if not isinstance(expires_at, str):
            raise ArtifactTicketError("ticket expiresAt must be an ISO-8601 timestamp")
        try:
            parsed_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ArtifactTicketError("ticket expiresAt must be an ISO-8601 timestamp") from exc
        if parsed_expiry.tzinfo is None:
            raise ArtifactTicketError("ticket expiresAt must include a timezone")

        return cls(
            object_key=object_key,
            method=method,
            url=url,
            required_headers=dict(required_headers),
            expires_at=parsed_expiry.astimezone(timezone.utc),
        )

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at <= now.astimezone(timezone.utc)


class GraphQLArtifactStore:
    """Transfer artifacts through application-authorized GraphQL tickets only."""

    def __init__(
        self,
        executor: GraphQLExecutor,
        *,
        http_session: Optional[HTTPSession] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not hasattr(executor, "execute") or not callable(executor.execute):
            raise TypeError("executor must provide an execute(query, variables) method")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._executor = executor
        self._http_session = http_session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def request_tickets(
        self, requests_to_authorize: Sequence[ArtifactTransferRequest]
    ) -> list[ArtifactTransferTicket]:
        """Request one to twenty tickets through the frozen GraphQL operation."""
        if not 1 <= len(requests_to_authorize) <= 20:
            raise ValueError("artifact ticket batches must contain one to twenty requests")
        if not all(isinstance(item, ArtifactTransferRequest) for item in requests_to_authorize):
            raise TypeError("ticket requests must be ArtifactTransferRequest instances")

        variables = {
            "requests": [request.as_graphql_input() for request in requests_to_authorize]
        }
        try:
            response = self._executor.execute(_TICKET_MUTATION, variables=variables)
        except Exception as exc:
            raise ArtifactTicketError("artifact ticket authorization failed") from exc

        try:
            ticket_data = response["createArtifactTransferTickets"]
        except (KeyError, TypeError) as exc:
            raise ArtifactTicketError("artifact ticket response was malformed") from exc
        if not isinstance(ticket_data, list) or len(ticket_data) != len(requests_to_authorize):
            raise ArtifactTicketError("artifact ticket response did not match the request batch")

        tickets = [ArtifactTransferTicket.from_graphql(item) for item in ticket_data]
        for request, ticket in zip(requests_to_authorize, tickets):
            expected_method = "PUT" if request.operation == "WRITE" else "GET"
            if ticket.method != expected_method:
                raise ArtifactTicketError("ticket method does not match requested operation")
        return tickets

    def upload_bytes(
        self,
        request: ArtifactTransferRequest,
        content: bytes,
        *,
        existing_metadata: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Upload verified bytes, then return metadata for a caller to persist."""
        if request.operation != "WRITE":
            raise ValueError("upload_bytes requires a WRITE request")
        payload = self._require_bytes(content)
        self._verify_content(request, payload)
        ticket, _ = self._transfer_with_one_expiry_retry(request, payload)
        return self.build_metadata(
            existing_metadata=existing_metadata,
            object_key=ticket.object_key,
            sha256=request.sha256,
            size_bytes=request.size_bytes,
            content_type=request.content_type,
        )

    def download_bytes(self, request: ArtifactTransferRequest) -> bytes:
        """Download and verify bytes; no unchecked or alternate source is returned."""
        if request.operation != "READ":
            raise ValueError("download_bytes requires a READ request")
        _ticket, content = self._transfer_with_one_expiry_retry(request, None)
        if content is None:
            raise ArtifactTransferError("HTTPS download did not return content")
        self._verify_content(request, content)
        return content

    @staticmethod
    def build_metadata(
        *,
        existing_metadata: Optional[Mapping[str, Any]],
        object_key: str,
        sha256: str,
        size_bytes: int,
        content_type: str,
    ) -> dict[str, Any]:
        """Add integrity metadata while retaining the compatible ``_s3_key`` field."""
        metadata = dict(existing_metadata or {})
        metadata["_s3_key"] = object_key
        metadata.update(
            {
                "sha256": sha256,
                "size_bytes": size_bytes,
                "content_type": content_type,
            }
        )
        return metadata

    def _transfer_with_one_expiry_retry(
        self, request: ArtifactTransferRequest, payload: Optional[bytes]
    ) -> tuple[ArtifactTransferTicket, Optional[bytes]]:
        ticket = self.request_tickets([request])[0]
        try:
            return self._transfer(ticket, payload)
        except _ExpiredSignedURL:
            replacement = self.request_tickets([request])[0]
            try:
                return self._transfer(replacement, payload)
            except _ExpiredSignedURL as exc:
                raise ArtifactTransferError("replacement signed URL expired") from exc

    def _transfer(
        self, ticket: ArtifactTransferTicket, payload: Optional[bytes]
    ) -> tuple[ArtifactTransferTicket, Optional[bytes]]:
        if ticket.is_expired(datetime.now(timezone.utc)):
            raise _ExpiredSignedURL("signed URL expired before transfer")
        try:
            response = self._http_session.request(
                ticket.method,
                ticket.url,
                headers=ticket.required_headers,
                data=payload,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ArtifactTransferError("HTTPS artifact transfer failed") from exc
        except Exception as exc:
            raise ArtifactTransferError("HTTPS artifact transfer failed") from exc

        status_code = getattr(response, "status_code", None)
        if self._is_expired_response(response):
            raise _ExpiredSignedURL("signed URL expired during transfer")
        if status_code in {401, 403}:
            raise ArtifactAuthorizationError("signed URL authorization was rejected")
        if not isinstance(status_code, int) or not 200 <= status_code < 300:
            raise ArtifactTransferError(f"HTTPS artifact transfer returned status {status_code}")

        if ticket.method == "GET":
            content = getattr(response, "content", None)
            if not isinstance(content, bytes):
                raise ArtifactTransferError("HTTPS download returned non-bytes content")
            return ticket, content
        return ticket, None

    @staticmethod
    def _is_expired_response(response: Any) -> bool:
        status_code = getattr(response, "status_code", None)
        if status_code not in {400, 401, 403}:
            return False
        response_text = str(getattr(response, "text", "")).lower()
        return any(marker in response_text for marker in _EXPIRY_RESPONSE_MARKERS)

    @staticmethod
    def _require_bytes(content: bytes) -> bytes:
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be bytes")
        return content

    @staticmethod
    def _verify_content(request: ArtifactTransferRequest, content: bytes) -> None:
        if len(content) != request.size_bytes:
            raise ArtifactIntegrityError("artifact size does not match the authorized request")
        digest = hashlib.sha256(content).hexdigest()
        if digest.lower() != request.sha256.lower():
            raise ArtifactIntegrityError("artifact SHA-256 does not match the authorized request")
