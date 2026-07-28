"""Behavior specifications for application-authorized artifact transfers.

Feature: GraphQL artifact transfers
  Scenario: Upload verified bytes without local AWS credentials
    Given an authorized GraphQL ticket executor and a signed HTTPS ticket
    When a caller uploads bytes matching the declared checksum and size
    Then the bytes are transferred before metadata is returned and no S3 client is used

  Scenario: A signed URL expires during transfer
    Given a write ticket whose HTTPS response is RequestExpired
    When a caller uploads matching bytes
    Then the store requests exactly one replacement ticket and retries once

  Scenario: Authorization or integrity validation fails
    Given an unauthorized response or mismatched downloaded content
    When a caller transfers an artifact
    Then the operation fails closed without an alternate storage path
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import boto3
import pytest

from plexus.storage.graphql_artifact_store import (
    ArtifactAuthorizationError,
    ArtifactIntegrityError,
    ArtifactTicketError,
    ArtifactTransferError,
    ArtifactTransferRequest,
    GraphQLArtifactStore,
)


PAYLOAD = b"application-authorized artifact"
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"", text: str = ""):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeHTTPSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def request(self, method, url, *, headers, data=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


class FakeExecutor:
    def __init__(self, ticket_batches):
        self.ticket_batches = list(ticket_batches)
        self.calls: list[tuple[str, dict]] = []

    def execute(self, query, variables=None):
        self.calls.append((query, variables))
        return {"createArtifactTransferTickets": self.ticket_batches.pop(0)}


def ticket(*, url="https://storage.example/upload", method="PUT"):
    return {
        "objectKey": "artifacts/report-1/output.json",
        "method": method,
        "url": url,
        "requiredHeaders": {"x-amz-meta-owner": "service", "content-type": "application/json"},
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }


def write_request():
    return ArtifactTransferRequest(
        operation="WRITE",
        resource_type="REPORT",
        resource_id="report-1",
        artifact_type="OUTPUT",
        filename="output.json",
        content_type="application/json",
        size_bytes=len(PAYLOAD),
        sha256=PAYLOAD_SHA256,
    )


def read_request():
    return ArtifactTransferRequest(
        operation="READ",
        resource_type="REPORT",
        resource_id="report-1",
        artifact_type="OUTPUT",
        filename="output.json",
        content_type="application/json",
        size_bytes=len(PAYLOAD),
        sha256=PAYLOAD_SHA256,
    )


def test_requests_batched_tickets_with_frozen_contract_fields():
    executor = FakeExecutor([[ticket(), ticket(url="https://storage.example/second")]])
    store = GraphQLArtifactStore(executor, http_session=FakeHTTPSession([]))

    tickets = store.request_tickets([write_request(), write_request()])

    assert [item.url for item in tickets] == [
        "https://storage.example/upload",
        "https://storage.example/second",
    ]
    query, variables = executor.calls[0]
    assert "$requests: [ArtifactTransferRequestInput!]!" in query
    assert "createArtifactTransferTickets" in query
    for field in ("objectKey", "method", "url", "requiredHeaders", "expiresAt"):
        assert field in query
    assert variables == {
        "requests": [
            {
                "operation": "WRITE",
                "resourceType": "REPORT",
                "resourceId": "report-1",
                "artifactType": "OUTPUT",
                "filename": "output.json",
                "contentType": "application/json",
                "sizeBytes": len(PAYLOAD),
                "sha256": PAYLOAD_SHA256,
            },
            {
                "operation": "WRITE",
                "resourceType": "REPORT",
                "resourceId": "report-1",
                "artifactType": "OUTPUT",
                "filename": "output.json",
                "contentType": "application/json",
                "sizeBytes": len(PAYLOAD),
                "sha256": PAYLOAD_SHA256,
            },
        ]
    }


def test_upload_transfers_verified_bytes_before_returning_metadata_without_s3(monkeypatch):
    executor = FakeExecutor([[ticket()]])
    http = FakeHTTPSession([FakeResponse(200)])
    store = GraphQLArtifactStore(executor, http_session=http)
    monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("S3 must not be used")))

    metadata = store.upload_bytes(
        write_request(),
        PAYLOAD,
        existing_metadata={"_s3_key": "legacy/key", "retain": "unrelated"},
    )

    assert http.calls == [
        {
            "method": "PUT",
            "url": "https://storage.example/upload",
            "headers": {"x-amz-meta-owner": "service", "content-type": "application/json"},
            "data": PAYLOAD,
            "timeout": 30.0,
        }
    ]
    assert metadata == {
        "_s3_key": "artifacts/report-1/output.json",
        "retain": "unrelated",
        "sha256": PAYLOAD_SHA256,
        "size_bytes": len(PAYLOAD),
        "content_type": "application/json",
    }


def test_decodes_required_headers_returned_as_graphql_awsjson():
    awsjson_ticket = ticket()
    awsjson_ticket["requiredHeaders"] = json.dumps(awsjson_ticket["requiredHeaders"])
    executor = FakeExecutor([[awsjson_ticket]])
    store = GraphQLArtifactStore(executor, http_session=FakeHTTPSession([]))

    authorized_ticket = store.request_tickets([write_request()])[0]

    assert authorized_ticket.required_headers == {
        "x-amz-meta-owner": "service",
        "content-type": "application/json",
    }


def test_ticket_requires_an_https_host():
    executor = FakeExecutor([[ticket(url="https:///missing-host")]])
    store = GraphQLArtifactStore(executor, http_session=FakeHTTPSession([]))

    with pytest.raises(ArtifactTicketError, match="HTTPS"):
        store.request_tickets([write_request()])


def test_expired_signed_url_reissues_one_ticket_and_retries_once():
    executor = FakeExecutor([[ticket()], [ticket(url="https://storage.example/replacement")]])
    http = FakeHTTPSession([FakeResponse(403, text="<Code>RequestExpired</Code>"), FakeResponse(200)])
    store = GraphQLArtifactStore(executor, http_session=http)

    metadata = store.upload_bytes(write_request(), PAYLOAD)

    assert metadata["_s3_key"] == "artifacts/report-1/output.json"
    assert len(executor.calls) == 2
    assert [call["url"] for call in http.calls] == [
        "https://storage.example/upload",
        "https://storage.example/replacement",
    ]


def test_standard_s3_expiry_message_reissues_one_ticket_and_retries_once():
    executor = FakeExecutor([[ticket()], [ticket(url="https://storage.example/replacement")]])
    http = FakeHTTPSession([FakeResponse(403, text="Request has expired"), FakeResponse(200)])
    store = GraphQLArtifactStore(executor, http_session=http)

    store.upload_bytes(write_request(), PAYLOAD)

    assert len(executor.calls) == 2
    assert [call["url"] for call in http.calls] == [
        "https://storage.example/upload",
        "https://storage.example/replacement",
    ]


def test_authorization_failure_does_not_request_a_replacement_ticket():
    executor = FakeExecutor([[ticket()]])
    http = FakeHTTPSession([FakeResponse(403, text="<Code>AccessDenied</Code>")])
    store = GraphQLArtifactStore(executor, http_session=http)

    with pytest.raises(ArtifactAuthorizationError):
        store.upload_bytes(write_request(), PAYLOAD)

    assert len(executor.calls) == 1


def test_download_checksum_failure_fails_closed_without_retries():
    executor = FakeExecutor([[ticket(method="GET")]])
    http = FakeHTTPSession([FakeResponse(200, content=b"tampered")])
    store = GraphQLArtifactStore(executor, http_session=http)

    with pytest.raises(ArtifactIntegrityError):
        store.download_bytes(read_request())

    assert len(executor.calls) == 1
    assert len(http.calls) == 1


def test_upload_rejects_mismatched_declared_bytes_before_requesting_ticket():
    executor = FakeExecutor([])
    store = GraphQLArtifactStore(executor, http_session=FakeHTTPSession([]))

    with pytest.raises(ArtifactIntegrityError):
        store.upload_bytes(write_request(), b"tampered")

    assert executor.calls == []


def test_http_failure_fails_closed_without_inline_or_s3_fallback():
    executor = FakeExecutor([[ticket()]])
    store = GraphQLArtifactStore(executor, http_session=FakeHTTPSession([FakeResponse(500, text="error")]))

    with pytest.raises(ArtifactTransferError):
        store.upload_bytes(write_request(), PAYLOAD)

    assert len(executor.calls) == 1
