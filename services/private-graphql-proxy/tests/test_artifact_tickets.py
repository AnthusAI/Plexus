from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from proxy import artifact_tickets
from proxy.artifact_tickets import (
    ArtifactTicketConfiguration,
    ArtifactTicketRequestError,
    ArtifactTicketService,
)


SHA256 = "a" * 64


class FakeStore:
    def __init__(self):
        self.resources = {
            ("Task", "task-1"): {"id": "task-1", "accountId": "account-1"},
            ("DataSet", "dataset-1"): {"id": "dataset-1", "accountId": "account-1"},
        }

    def get_private(self, model, key):
        return self.resources.get((model, key.get("id")))


class FakeS3:
    def __init__(self):
        self.calls = []

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        self.calls.append((operation, Params, ExpiresIn))
        return f"https://plexus-local-object-store:9000/signed/{Params['Key']}"


def configuration(**overrides):
    values = {
        "enabled": True,
        "endpoint": "https://plexus-local-object-store:9000",
        "region": "us-east-1",
        "access_key_id": "local-access",
        "secret_access_key": "local-secret",
        "account_id": "account-1",
        "buckets": {
            "datasets": "datasets-bucket",
            "reportBlockDetails": "reports-bucket",
            "taskAttachments": "tasks-bucket",
            "scoreResultAttachments": "results-bucket",
        },
        "url_ttl_seconds": 300,
    }
    values.update(overrides)
    return ArtifactTicketConfiguration(**values)


def request(**overrides):
    values = {
        "operation": "WRITE",
        "resourceType": "TASK",
        "resourceId": "task-1",
        "artifactType": "TASK_ATTACHMENT",
        "filename": "optimizer/manifest.json",
        "contentType": "application/json",
        "sizeBytes": 42,
        "sha256": SHA256,
    }
    values.update(overrides)
    return values


def test_issues_checksum_bound_https_ticket_with_canonical_task_key():
    s3 = FakeS3()
    service = ArtifactTicketService(configuration(), FakeStore(), s3_client=s3)

    tickets = service.issue([request()])

    assert tickets[0]["objectKey"] == "tasks/task-1/optimizer/manifest.json"
    assert tickets[0]["method"] == "PUT"
    assert tickets[0]["url"].startswith("https://")
    assert tickets[0]["requiredHeaders"] == {
        "content-type": "application/json",
        "content-length": "42",
        "x-amz-checksum-sha256": base64.b64encode(bytes.fromhex(SHA256)).decode(),
    }
    assert datetime.fromisoformat(tickets[0]["expiresAt"].replace("Z", "+00:00")) > datetime.now(timezone.utc)
    operation, params, ttl = s3.calls[0]
    assert operation == "put_object"
    assert params["Bucket"] == "tasks-bucket"
    assert params["Key"] == "tasks/task-1/optimizer/manifest.json"
    assert params["ChecksumSHA256"] == tickets[0]["requiredHeaders"]["x-amz-checksum-sha256"]
    assert ttl == 300


def test_ticket_issue_is_correlated_in_application_logs_without_artifact_details(monkeypatch):
    messages = []

    class FakeLogger:
        def info(self, message, *args):
            messages.append(message % args)

    monkeypatch.setattr(artifact_tickets, "APPLICATION_LOGGER", FakeLogger())
    service = ArtifactTicketService(configuration(), FakeStore(), s3_client=FakeS3())

    service.issue([request()])

    assert len(messages) == 1
    assert "artifact_transfer_tickets correlation_id=" in messages[0]
    assert "request_count=1 resource_types=TASK" in messages[0]
    for prohibited in ("task-1", "manifest.json", SHA256, "https://"):
        assert prohibited not in messages[0]


def test_dataset_key_is_account_scoped_and_read_ticket_has_no_write_headers():
    s3 = FakeS3()
    service = ArtifactTicketService(configuration(), FakeStore(), s3_client=s3)

    ticket = service.issue([request(
        operation="READ",
        resourceType="DATA_SET",
        resourceId="dataset-1",
        artifactType="DATASET_FILE",
        filename="training.parquet",
        contentType="application/octet-stream",
    )])[0]

    assert ticket["objectKey"] == "datasets/account-1/dataset-1/training.parquet"
    assert ticket["method"] == "GET"
    assert ticket["requiredHeaders"] == {}


@pytest.mark.parametrize(
    "override, message",
    [
        ({"filename": "../escape.json"}, "filename"),
        ({"sha256": "not-a-checksum"}, "sha256"),
        ({"sizeBytes": 100 * 1024 * 1024 + 1}, "100 MiB"),
        ({"artifactType": "DATASET_FILE"}, "not allowed"),
    ],
)
def test_malformed_requests_fail_before_signing(override, message):
    s3 = FakeS3()
    service = ArtifactTicketService(configuration(), FakeStore(), s3_client=s3)

    with pytest.raises(ArtifactTicketRequestError, match=message):
        service.issue([request(**override)])

    assert s3.calls == []


def test_missing_and_cross_account_resources_fail_closed():
    s3 = FakeS3()
    service = ArtifactTicketService(configuration(), FakeStore(), s3_client=s3)

    with pytest.raises(ArtifactTicketRequestError, match="not found or is not transfer-authorized"):
        service.issue([request(resourceId="missing")])
    with pytest.raises(ArtifactTicketRequestError, match="different account"):
        service.issue([request()], account_id="account-2")

    assert s3.calls == []


def test_configuration_rejects_http_endpoint():
    with pytest.raises(ValueError, match="HTTPS"):
        configuration(endpoint="http://plexus-local-object-store:9000").validate()
