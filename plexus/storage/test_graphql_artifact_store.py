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
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import boto3
import pytest
import requests

from plexus.storage.graphql_artifact_store import (
    ArtifactUpload,
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
    def __init__(self, responses: list[FakeResponse | Exception]):
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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeCAHTTPSession(FakeHTTPSession):
    def request(self, method, url, *, headers, data=None, timeout=None, verify=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
                "verify": verify,
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


def test_upload_omits_only_a_redundant_unsigned_checksum_header_already_bound_in_the_url():
    checksum = b64encode(bytes.fromhex(PAYLOAD_SHA256)).decode("ascii")
    query = urlencode({
        "X-Amz-Checksum-Sha256": checksum,
        "X-Amz-SignedHeaders": "content-length;host",
    })
    legacy_ticket = ticket(url=f"https://storage.example/upload?{query}")
    legacy_ticket["requiredHeaders"] = {
        "content-length": str(len(PAYLOAD)),
        "content-type": "application/json",
        "x-amz-checksum-sha256": checksum,
    }
    http = FakeHTTPSession([FakeResponse(200)])
    store = GraphQLArtifactStore(FakeExecutor([[legacy_ticket]]), http_session=http)

    store.upload_bytes(write_request(), PAYLOAD)

    assert http.calls[0]["headers"] == {
        "content-length": str(len(PAYLOAD)),
        "content-type": "application/json",
    }


@pytest.mark.parametrize(
    ("url_query", "header_value"),
    [
        ({"X-Amz-SignedHeaders": "content-length;host"}, "declared-checksum"),
        (
            {
                "X-Amz-Checksum-Sha256": "query-checksum",
                "X-Amz-SignedHeaders": "content-length;host",
            },
            "different-checksum",
        ),
        (
            {
                "X-Amz-Checksum-Sha256": "declared-checksum",
                "X-Amz-SignedHeaders": "content-length;host;x-amz-checksum-sha256",
            },
            "declared-checksum",
        ),
    ],
)
def test_upload_preserves_checksum_header_when_query_binding_is_absent_inconsistent_or_signed(
    url_query, header_value
):
    legacy_ticket = ticket(
        url=f"https://storage.example/upload?{urlencode(url_query)}"
    )
    legacy_ticket["requiredHeaders"] = {
        "content-length": str(len(PAYLOAD)),
        "x-amz-checksum-sha256": header_value,
    }
    http = FakeHTTPSession([FakeResponse(403, text="<Code>AccessDenied</Code>")])
    store = GraphQLArtifactStore(FakeExecutor([[legacy_ticket]]), http_session=http)

    with pytest.raises(ArtifactAuthorizationError):
        store.upload_bytes(write_request(), PAYLOAD)

    assert http.calls[0]["headers"]["x-amz-checksum-sha256"] == header_value


def test_upload_batch_requests_all_tickets_once_before_uploading_each_verified_artifact():
    second_payload = b"second application-authorized artifact"
    second_request = ArtifactTransferRequest(
        operation="WRITE",
        resource_type="PROCEDURE",
        resource_id="procedure-1",
        artifact_type="PROCEDURE_ATTACHMENT",
        filename="lua_state.json",
        content_type="application/json",
        size_bytes=len(second_payload),
        sha256=hashlib.sha256(second_payload).hexdigest(),
    )
    executor = FakeExecutor([[ticket(), ticket(url="https://storage.example/second")]])
    http = FakeHTTPSession([FakeResponse(200), FakeResponse(200)])
    store = GraphQLArtifactStore(executor, http_session=http)

    metadata = store.upload_batch(
        [
            ArtifactUpload(write_request(), PAYLOAD),
            ArtifactUpload(second_request, second_payload),
        ]
    )

    assert len(executor.calls) == 1
    assert len(executor.calls[0][1]["requests"]) == 2
    assert [call["url"] for call in http.calls] == [
        "https://storage.example/upload",
        "https://storage.example/second",
    ]
    assert metadata[0]["_s3_key"] == "artifacts/report-1/output.json"
    assert metadata[1]["_s3_key"] == "artifacts/report-1/output.json"


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


def test_download_batch_requests_all_tickets_once_and_verifies_each_payload():
    executor = FakeExecutor([[ticket(method="GET"), ticket(method="GET", url="https://storage.example/second")]])
    http = FakeHTTPSession([FakeResponse(200, content=PAYLOAD), FakeResponse(200, content=PAYLOAD)])
    store = GraphQLArtifactStore(executor, http_session=http)

    payloads = store.download_batch([read_request(), read_request()])

    assert payloads == [PAYLOAD, PAYLOAD]
    assert len(executor.calls) == 1
    assert len(executor.calls[0][1]["requests"]) == 2


def test_upload_rejects_mismatched_declared_bytes_before_requesting_ticket():
    executor = FakeExecutor([])
    store = GraphQLArtifactStore(executor, http_session=FakeHTTPSession([]))

    with pytest.raises(ArtifactIntegrityError):
        store.upload_bytes(write_request(), b"tampered")

    assert executor.calls == []


@pytest.mark.parametrize("status_code", [408, 429, 503])
def test_retryable_upload_status_gets_one_fresh_ticket_for_identical_bytes(status_code):
    executor = FakeExecutor([
        [ticket()],
        [ticket(url="https://storage.example/replacement")],
    ])
    http = FakeHTTPSession([FakeResponse(status_code, text="retry later"), FakeResponse(200)])
    store = GraphQLArtifactStore(executor, http_session=http)

    metadata = store.upload_bytes(write_request(), PAYLOAD)

    assert metadata["_s3_key"] == "artifacts/report-1/output.json"
    assert len(executor.calls) == 2
    assert [call["url"] for call in http.calls] == [
        "https://storage.example/upload",
        "https://storage.example/replacement",
    ]
    assert [call["data"] for call in http.calls] == [PAYLOAD, PAYLOAD]


def test_retryable_upload_request_exception_gets_one_fresh_ticket_for_identical_bytes():
    executor = FakeExecutor([
        [ticket()],
        [ticket(url="https://storage.example/replacement")],
    ])
    http = FakeHTTPSession([requests.ConnectionError("connection reset"), FakeResponse(200)])
    store = GraphQLArtifactStore(executor, http_session=http)

    store.upload_bytes(write_request(), PAYLOAD)

    assert len(executor.calls) == 2
    assert [call["data"] for call in http.calls] == [PAYLOAD, PAYLOAD]


def test_retryable_download_failure_does_not_request_a_fresh_ticket():
    executor = FakeExecutor([[ticket(method="GET")]])
    http = FakeHTTPSession([FakeResponse(503, text="retry later")])
    store = GraphQLArtifactStore(executor, http_session=http)

    with pytest.raises(ArtifactTransferError):
        store.download_bytes(read_request())

    assert len(executor.calls) == 1
    assert len(http.calls) == 1


@pytest.mark.parametrize("status_code", [400, 404])
def test_non_retryable_upload_client_status_fails_closed_without_fresh_ticket(status_code):
    executor = FakeExecutor([[ticket()]])
    store = GraphQLArtifactStore(executor, http_session=FakeHTTPSession([FakeResponse(status_code, text="client error")]))

    with pytest.raises(ArtifactTransferError):
        store.upload_bytes(write_request(), PAYLOAD)

    assert len(executor.calls) == 1


def test_second_retryable_upload_failure_fails_closed_without_a_third_ticket():
    executor = FakeExecutor([
        [ticket()],
        [ticket(url="https://storage.example/replacement")],
    ])
    http = FakeHTTPSession([FakeResponse(503, text="retry later"), FakeResponse(503, text="still unavailable")])
    store = GraphQLArtifactStore(executor, http_session=http)

    with pytest.raises(ArtifactTransferError):
        store.upload_bytes(write_request(), PAYLOAD)

    assert len(executor.calls) == 2
    assert len(http.calls) == 2


def test_configured_local_ca_bundle_is_used_for_https_verification(tmp_path, monkeypatch):
    ca_bundle = tmp_path / "minio-ca.crt"
    ca_bundle.write_text("test local CA")
    monkeypatch.setenv("PLEXUS_ARTIFACT_CA_BUNDLE", str(ca_bundle))
    executor = FakeExecutor([[ticket()]])
    http = FakeCAHTTPSession([FakeResponse(200)])

    GraphQLArtifactStore(executor, http_session=http).upload_bytes(write_request(), PAYLOAD)

    assert http.calls[0]["verify"] == str(ca_bundle)


def test_missing_configured_local_ca_bundle_fails_closed(monkeypatch):
    monkeypatch.setenv("PLEXUS_ARTIFACT_CA_BUNDLE", "/missing/minio-ca.crt")

    with pytest.raises(ValueError, match="CA bundle"):
        GraphQLArtifactStore(FakeExecutor([]), http_session=FakeHTTPSession([]))
