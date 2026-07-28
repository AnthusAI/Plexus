from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import os
import re
from typing import Any, Mapping, Optional
from urllib.parse import urlparse
import uuid

import boto3
from botocore.config import Config


MAX_BATCH_SIZE = 20
MAX_WRITE_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class ArtifactRoute:
    resource_type: str
    model: str
    bucket_key: str
    key_prefix: str
    account_scoped: bool = False


ROUTES = {
    "DATASET_FILE": ArtifactRoute("DATA_SET", "DataSet", "datasets", "datasets", True),
    "PROCEDURE_ATTACHMENT": ArtifactRoute(
        "PROCEDURE", "Procedure", "reportBlockDetails", "procedures"
    ),
    "PROCEDURE_DASHBOARD_STATE": ArtifactRoute(
        "PROCEDURE", "Procedure", "reportBlockDetails", "reportblocks/procedures"
    ),
    "SCORE_RESULT_ATTACHMENT": ArtifactRoute(
        "SCORE_RESULT", "ScoreResult", "scoreResultAttachments", "scoreresults"
    ),
    "EVALUATION_RCA": ArtifactRoute(
        "EVALUATION", "Evaluation", "scoreResultAttachments", "evaluations"
    ),
    "TASK_ATTACHMENT": ArtifactRoute("TASK", "Task", "taskAttachments", "tasks"),
}


class ArtifactTicketRequestError(RuntimeError):
    def __init__(self, detail: str, *, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class ArtifactTicketConfiguration:
    enabled: bool
    endpoint: Optional[str]
    region: str
    access_key_id: Optional[str]
    secret_access_key: Optional[str]
    account_id: Optional[str]
    buckets: Mapping[str, str]
    url_ttl_seconds: int = 300

    @classmethod
    def from_env(cls) -> "ArtifactTicketConfiguration":
        return cls(
            enabled=os.getenv("PLEXUS_ARTIFACT_TICKETS_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            endpoint=os.getenv("PLEXUS_ARTIFACT_STORE_ENDPOINT"),
            region=os.getenv("PLEXUS_ARTIFACT_STORE_REGION", "us-east-1"),
            access_key_id=os.getenv("PLEXUS_ARTIFACT_STORE_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("PLEXUS_ARTIFACT_STORE_SECRET_ACCESS_KEY"),
            account_id=os.getenv("PLEXUS_ARTIFACT_ACCOUNT_ID"),
            buckets={
                "datasets": os.getenv("PLEXUS_ARTIFACT_BUCKET_DATASETS", ""),
                "reportBlockDetails": os.getenv("PLEXUS_ARTIFACT_BUCKET_REPORT_BLOCK_DETAILS", ""),
                "taskAttachments": os.getenv("PLEXUS_ARTIFACT_BUCKET_TASK_ATTACHMENTS", ""),
                "scoreResultAttachments": os.getenv(
                    "PLEXUS_ARTIFACT_BUCKET_SCORE_RESULT_ATTACHMENTS", ""
                ),
            },
            url_ttl_seconds=int(os.getenv("PLEXUS_ARTIFACT_TICKET_TTL_SECONDS", "300")),
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        endpoint = urlparse(self.endpoint or "")
        if endpoint.scheme.lower() != "https" or not endpoint.netloc:
            raise ValueError("local artifact ticket endpoint must use HTTPS")
        required = {
            "PLEXUS_ARTIFACT_STORE_ACCESS_KEY_ID": self.access_key_id,
            "PLEXUS_ARTIFACT_STORE_SECRET_ACCESS_KEY": self.secret_access_key,
            "PLEXUS_ARTIFACT_ACCOUNT_ID": self.account_id,
            **{f"artifact bucket {name}": value for name, value in self.buckets.items()},
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"local artifact ticket configuration is missing: {', '.join(missing)}")
        if self.url_ttl_seconds <= 0 or self.url_ttl_seconds > 3600:
            raise ValueError("artifact ticket TTL must be between 1 and 3600 seconds")


@dataclass(frozen=True)
class TransferRequest:
    operation: str
    resource_type: str
    resource_id: str
    artifact_type: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str


class ArtifactTicketService:
    def __init__(self, configuration: ArtifactTicketConfiguration, store: Any, *, s3_client=None):
        self.configuration = configuration
        self.configuration.validate()
        self.store = store
        self.s3 = s3_client
        if configuration.enabled and self.s3 is None:
            self.s3 = boto3.client(
                "s3",
                endpoint_url=configuration.endpoint,
                region_name=configuration.region,
                aws_access_key_id=configuration.access_key_id,
                aws_secret_access_key=configuration.secret_access_key,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )

    def issue(
        self, raw_requests: Any, *, account_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        if not self.configuration.enabled or self.s3 is None:
            raise ArtifactTicketRequestError(
                "local artifact transfer tickets are not configured", status_code=503
            )
        if not isinstance(raw_requests, list) or not 1 <= len(raw_requests) <= MAX_BATCH_SIZE:
            raise ArtifactTicketRequestError(
                "requests must contain between 1 and 20 transfer requests"
            )
        trusted_account_id = account_id or self.configuration.account_id
        correlation_id = uuid.uuid4().hex
        tickets = [
            self._issue_one(self._validate_request(raw), trusted_account_id)
            for raw in raw_requests
        ]
        logging.info(
            "artifact_transfer_tickets correlation_id=%s request_count=%d resource_types=%s",
            correlation_id,
            len(tickets),
            ",".join(sorted({request.get("resourceType", "") for request in raw_requests})),
        )
        return tickets

    def _issue_one(
        self, request: TransferRequest, trusted_account_id: Optional[str]
    ) -> dict[str, Any]:
        route = ROUTES[request.artifact_type]
        resource = self.store.get_private(route.model, {"id": request.resource_id})
        resource_account_id = resource.get("accountId") if isinstance(resource, Mapping) else None
        if not resource or not resource_account_id:
            raise ArtifactTicketRequestError(
                "Requested resource was not found or is not transfer-authorized",
                status_code=403,
            )
        if not trusted_account_id or resource_account_id != trusted_account_id:
            raise ArtifactTicketRequestError(
                "Requested resource belongs to a different account", status_code=403
            )

        object_key = (
            f"{route.key_prefix}/{resource_account_id}/{request.resource_id}/{request.filename}"
            if route.account_scoped
            else f"{route.key_prefix}/{request.resource_id}/{request.filename}"
        )
        bucket = self.configuration.buckets[route.bucket_key]
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self.configuration.url_ttl_seconds
        )

        if request.operation == "READ":
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": object_key},
                ExpiresIn=self.configuration.url_ttl_seconds,
            )
            required_headers: dict[str, str] = {}
            method = "GET"
        else:
            checksum = base64.b64encode(bytes.fromhex(request.sha256)).decode()
            required_headers = {
                "content-type": request.content_type,
                "content-length": str(request.size_bytes),
                "x-amz-checksum-sha256": checksum,
            }
            url = self.s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": bucket,
                    "Key": object_key,
                    "ContentType": request.content_type,
                    "ContentLength": request.size_bytes,
                    "ChecksumSHA256": checksum,
                },
                ExpiresIn=self.configuration.url_ttl_seconds,
            )
            method = "PUT"
        parsed_url = urlparse(url)
        if parsed_url.scheme.lower() != "https" or not parsed_url.netloc:
            raise ArtifactTicketRequestError(
                "artifact signer returned a non-HTTPS transfer URL", status_code=503
            )
        return {
            "objectKey": object_key,
            "method": method,
            "url": url,
            "requiredHeaders": required_headers,
            "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _validate_request(value: Any) -> TransferRequest:
        if not isinstance(value, Mapping):
            raise ArtifactTicketRequestError("Each transfer request must be an object")

        def required_string(field: str) -> str:
            candidate = value.get(field)
            if not isinstance(candidate, str) or not candidate.strip():
                raise ArtifactTicketRequestError(f"{field} is required")
            return candidate.strip()

        operation = required_string("operation")
        resource_type = required_string("resourceType")
        resource_id = required_string("resourceId")
        artifact_type = required_string("artifactType")
        filename = required_string("filename")
        content_type = required_string("contentType").lower()
        size_bytes = value.get("sizeBytes")
        sha256 = required_string("sha256").lower()

        if operation not in {"READ", "WRITE"}:
            raise ArtifactTicketRequestError("operation must be READ or WRITE")
        route = ROUTES.get(artifact_type)
        if not route:
            raise ArtifactTicketRequestError(f"Unsupported artifactType: {artifact_type}")
        if route.resource_type != resource_type:
            raise ArtifactTicketRequestError(
                f"artifactType {artifact_type} is not allowed for {resource_type}"
            )
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,254}", resource_id):
            raise ArtifactTicketRequestError("resourceId contains unsupported characters")
        segments = filename.split("/")
        if (
            filename.startswith("/")
            or filename.endswith("/")
            or any(
                segment in {".", ".."}
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", segment)
                for segment in segments
            )
        ):
            raise ArtifactTicketRequestError("filename contains unsupported characters")
        if artifact_type == "PROCEDURE_DASHBOARD_STATE" and filename != "dashboard_state.json":
            raise ArtifactTicketRequestError(
                "PROCEDURE_DASHBOARD_STATE must use dashboard_state.json"
            )
        if artifact_type == "EVALUATION_RCA" and filename != "root_cause.full.json":
            raise ArtifactTicketRequestError("EVALUATION_RCA must use root_cause.full.json")
        if not re.fullmatch(
            r"[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*",
            content_type,
        ):
            raise ArtifactTicketRequestError("contentType must be a valid media type")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise ArtifactTicketRequestError("sizeBytes must be a nonnegative integer")
        if operation == "WRITE" and size_bytes > MAX_WRITE_BYTES:
            raise ArtifactTicketRequestError("WRITE sizeBytes cannot exceed 100 MiB")
        if not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise ArtifactTicketRequestError("sha256 must be a hexadecimal SHA-256 digest")

        return TransferRequest(
            operation,
            resource_type,
            resource_id,
            artifact_type,
            filename,
            content_type,
            size_bytes,
            sha256,
        )
