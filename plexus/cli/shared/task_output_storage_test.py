import json

import pytest

from plexus.cli.shared.task_output_storage import persist_task_output_artifact


def test_persist_task_output_artifact_json_uses_attachment_and_compact_envelope():
    uploads = []

    def _fake_uploader(**kwargs):
        uploads.append(kwargs)
        return kwargs["key"]

    compact_output, attached_files, attachment_key = persist_task_output_artifact(
        task_id="task-123",
        output_payload={"status": "ok", "message": "done", "score": "Dosage"},
        format_type="json",
        existing_attached_files=["tasks/task-123/stdout.txt"],
        uploader=_fake_uploader,
        bucket_name="task-attachments-test",
    )

    assert attachment_key == "tasks/task-123/output.json"
    assert attached_files == [
        "tasks/task-123/stdout.txt",
        "tasks/task-123/output.json",
    ]
    assert uploads == [
        {
            "bucket_name": "task-attachments-test",
            "key": "tasks/task-123/output.json",
            "body": json.dumps(
                {"status": "ok", "message": "done", "score": "Dosage"},
                indent=2,
                ensure_ascii=False,
                default=str,
            ).encode("utf-8"),
            "content_type": "application/json",
        }
    ]

    parsed = json.loads(compact_output)
    assert parsed["output_compacted"] is True
    assert parsed["output_attachment"] == "tasks/task-123/output.json"
    assert parsed["preview"]["status"] == "ok"
    assert parsed["preview"]["message"] == "done"


def test_persist_task_output_artifact_yaml_uses_output_yaml_and_merges_attachments():
    uploads = []

    def _fake_uploader(**kwargs):
        uploads.append(kwargs)
        return kwargs["key"]

    compact_output, attached_files, attachment_key = persist_task_output_artifact(
        task_id="task-456",
        output_payload="name: Example\nstatus: completed\n",
        format_type="yaml",
        existing_attached_files=["tasks/task-456/stdout.txt", "tasks/task-456/stdout.txt"],
        uploader=_fake_uploader,
        bucket_name="task-attachments-test",
    )

    assert attachment_key == "tasks/task-456/output.yaml"
    assert attached_files == [
        "tasks/task-456/stdout.txt",
        "tasks/task-456/output.yaml",
    ]
    assert uploads[0]["content_type"] == "text/yaml"
    assert uploads[0]["body"] == b"name: Example\nstatus: completed\n"

    parsed = json.loads(compact_output)
    assert parsed["output_compacted"] is True
    assert parsed["output_attachment"] == "tasks/task-456/output.yaml"
    assert "name: Example" in parsed["preview"]["raw_preview"]


def test_persist_task_output_artifact_requires_bucket_name():
    with pytest.raises(RuntimeError, match="AMPLIFY_STORAGE_TASKATTACHMENTS_BUCKET_NAME"):
        persist_task_output_artifact(
            task_id="task-789",
            output_payload={"status": "ok"},
            format_type="json",
            bucket_name=None,
        )
