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
import os
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence
from urllib.parse import parse_qs, urlparse

import requests


_TICKET_MUTATION = """
mutation CreateArtifactTransferTickets($requests: [ArtifactTransferRequestInput!]!) {
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
class ArtifactUpload:
    """A verified write request and its bytes for one batched authorization."""

    request: ArtifactTransferRequest
    content: bytes
    existing_metadata: Optional[Mapping[str, Any]] = None


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
        ca_bundle: Optional[str] = None,
    ) -> None:
        if not hasattr(executor, "execute") or not callable(executor.execute):
            raise TypeError("executor must provide an execute(query, variables) method")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._executor = executor
        self._http_session = http_session or requests.Session()
        self._timeout_seconds = timeout_seconds
        configured_ca_bundle = ca_bundle if ca_bundle is not None else os.getenv(
            "PLEXUS_ARTIFACT_CA_BUNDLE"
        )
        self._ca_bundle: Optional[str] = None
        if configured_ca_bundle and configured_ca_bundle.strip():
            bundle_path = Path(configured_ca_bundle).expanduser()
            if not bundle_path.is_file():
                raise ValueError("configured artifact CA bundle does not exist")
            self._ca_bundle = str(bundle_path.resolve())

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
        return self.upload_batch(
            [ArtifactUpload(request, content, existing_metadata)]
        )[0]

    def upload_batch(self, uploads: Sequence[ArtifactUpload]) -> list[dict[str, Any]]:
        """Authorize up to twenty verified writes with one ticket request.

        An explicit signed-URL expiry may refresh only its individual ticket once;
        no other authorization, transfer, or integrity failure is retried.
        """
        if not uploads:
            raise ValueError("artifact upload batches must not be empty")
        if not all(isinstance(upload, ArtifactUpload) for upload in uploads):
            raise TypeError("upload batches must contain ArtifactUpload instances")

        validated_uploads: list[tuple[ArtifactUpload, bytes]] = []
        for upload in uploads:
            if upload.request.operation != "WRITE":
                raise ValueError("upload_batch requires WRITE requests")
            payload = self._require_bytes(upload.content)
            self._verify_content(upload.request, payload)
            validated_uploads.append((upload, payload))

        tickets = self.request_tickets([upload.request for upload, _ in validated_uploads])
        metadata: list[dict[str, Any]] = []
        for (upload, payload), ticket in zip(validated_uploads, tickets):
            completed_ticket, _ = self._transfer_ticket_with_one_expiry_retry(
                upload.request,
                ticket,
                payload,
            )
            metadata.append(
                self.build_metadata(
                    existing_metadata=upload.existing_metadata,
                    object_key=completed_ticket.object_key,
                    sha256=upload.request.sha256,
                    size_bytes=upload.request.size_bytes,
                    content_type=upload.request.content_type,
                )
            )
        return metadata

    def download_bytes(self, request: ArtifactTransferRequest) -> bytes:
        """Download and verify bytes; no unchecked or alternate source is returned."""
        return self.download_batch([request])[0]

    def download_batch(self, requests_to_download: Sequence[ArtifactTransferRequest]) -> list[bytes]:
        """Authorize up to twenty reads with one ticket request and verify each."""
        if not requests_to_download:
            raise ValueError("artifact download batches must not be empty")
        if any(request.operation != "READ" for request in requests_to_download):
            raise ValueError("download_batch requires READ requests")

        tickets = self.request_tickets(requests_to_download)
        content_items: list[bytes] = []
        for request, ticket in zip(requests_to_download, tickets):
            _completed_ticket, content = self._transfer_ticket_with_one_expiry_retry(
                request,
                ticket,
                None,
            )
            if content is None:
                raise ArtifactTransferError("HTTPS download did not return content")
            self._verify_content(request, content)
            content_items.append(content)
        return content_items

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
        return self._transfer_ticket_with_one_expiry_retry(request, ticket, payload)

    def _transfer_ticket_with_one_expiry_retry(
        self,
        request: ArtifactTransferRequest,
        ticket: ArtifactTransferTicket,
        payload: Optional[bytes],
    ) -> tuple[ArtifactTransferTicket, Optional[bytes]]:
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
            request_kwargs: dict[str, Any] = {
                "headers": self._transfer_headers(ticket),
                "data": payload,
                "timeout": self._timeout_seconds,
            }
            if self._ca_bundle:
                request_kwargs["verify"] = self._ca_bundle
            response = self._http_session.request(ticket.method, ticket.url, **request_kwargs)
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
    def _transfer_headers(ticket: ArtifactTransferTicket) -> dict[str, str]:
        """Normalize one legacy S3 checksum representation without weakening tickets.

        Some deployed ticket issuers returned ``x-amz-checksum-sha256`` as a
        required header after the S3 presigner had already moved the identical
        checksum into the query string.  When that header is absent from
        ``X-Amz-SignedHeaders``, S3 rejects it as an unsigned ``x-amz-*``
        header.  Omit it only when the URL contains the exact same checksum and
        explicitly does not sign the header; every ambiguous or contradictory
        ticket remains unchanged and therefore continues to fail closed.
        """
        headers = dict(ticket.required_headers)
        if ticket.method != "PUT":
            return headers

        checksum_header_name = next(
            (
                name
                for name in headers
                if name.lower() == "x-amz-checksum-sha256"
            ),
            None,
        )
        if checksum_header_name is None:
            return headers

        query = {
            name.lower(): values
            for name, values in parse_qs(urlparse(ticket.url).query).items()
        }
        query_checksums = query.get("x-amz-checksum-sha256") or []
        signed_header_values = query.get("x-amz-signedheaders") or []
        if len(query_checksums) != 1 or len(signed_header_values) != 1:
            return headers
        signed_headers = {
            name.strip().lower()
            for name in signed_header_values[0].split(";")
            if name.strip()
        }
        if "x-amz-checksum-sha256" in signed_headers:
            return headers
        if query_checksums[0] != headers[checksum_header_name]:
            return headers

        del headers[checksum_header_name]
        return headers

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
