import json

import boto3
import pytest

from plexus.cli.shared.task_output_storage import persist_task_output_artifact, upload_task_attachment_bytes


class _FakeArtifactStore:
    def __init__(self):
        self.uploads = []

    def upload_bytes(self, request, content):
        self.uploads.append((request, content))
        return {
            "_s3_key": f"tasks/{request.resource_id}/{request.filename}",
            "sha256": request.sha256,
            "size_bytes": request.size_bytes,
            "content_type": request.content_type,
        }


def test_persist_task_output_artifact_uses_authorized_attachment_store_when_s3_is_blocked(monkeypatch):
    monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("S3 must not be used")))
    store = _FakeArtifactStore()

    compact_output, attached_files, attachment_key = persist_task_output_artifact(
        task_id="task-123",
        output_payload={"status": "ok", "message": "done", "score": "Example"},
        format_type="json",
        existing_attached_files=["tasks/task-123/stdout.txt"],
        artifact_store=store,
    )

    assert attachment_key == "tasks/task-123/output.json"
    assert attached_files == ["tasks/task-123/stdout.txt", attachment_key]
    request, content = store.uploads[0]
    assert request.resource_type == "TASK"
    assert request.artifact_type == "TASK_ATTACHMENT"
    assert request.filename == "output.json"
    assert json.loads(content) == {"status": "ok", "message": "done", "score": "Example"}
    parsed = json.loads(compact_output)
    assert parsed["output_compacted"] is True
    assert parsed["output_attachment"] == attachment_key


def test_upload_task_attachment_bytes_requires_explicit_client_or_store():
    with pytest.raises(ValueError, match="client or artifact_store"):
        upload_task_attachment_bytes(
            task_id="task-123", filename="stdout.txt", body=b"hello", content_type="text/plain",
        )


def test_persist_task_output_artifact_yaml_merges_duplicate_attachments():
    store = _FakeArtifactStore()
    compact_output, attached_files, attachment_key = persist_task_output_artifact(
        task_id="task-456",
        output_payload="name: Example\nstatus: completed\n",
        format_type="yaml",
        existing_attached_files=["tasks/task-456/stdout.txt", "tasks/task-456/stdout.txt"],
        artifact_store=store,
    )

    assert attachment_key == "tasks/task-456/output.yaml"
    assert attached_files == ["tasks/task-456/stdout.txt", attachment_key]
    assert store.uploads[0][0].content_type == "text/yaml"
    assert "name: Example" in json.loads(compact_output)["preview"]["raw_preview"]
