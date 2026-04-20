import json
import pytest

from plexus.reports import service
from unittest.mock import Mock


def test_safe_output_preview_extracts_core_fields():
    output_json = json.dumps(
        {
            "type": "VectorTopicMemory",
            "status": "ok",
            "summary": "Processed 42 items.",
            "items_processed": 42,
            "index_name": "topic-memory-idx",
            "cluster_version": "v1",
            "extra": "ignored",
        }
    )
    preview = service._safe_output_preview(output_json)
    assert preview == {
        "type": "VectorTopicMemory",
        "status": "ok",
        "summary": "Processed 42 items.",
        "items_processed": 42,
        "index_name": "topic-memory-idx",
        "cluster_version": "v1",
    }


def test_safe_output_preview_accepts_dict_payload():
    preview = service._safe_output_preview(
        {
            "type": "VectorTopicMemory",
            "status": "ok",
            "summary": "From dict payload",
            "items_processed": 9,
        }
    )
    assert preview["type"] == "VectorTopicMemory"
    assert preview["summary"] == "From dict payload"


def test_compact_output_json_for_storage_includes_attachment_and_preview():
    output_json = json.dumps({"status": "ok", "summary": "Done", "items_processed": 10})
    compact_json = service._compact_output_json_for_storage(
        output_payload=output_json,
        output_attachment_path="reportblocks/rb-1/output-rb-1.json",
    )
    compact = json.loads(compact_json)

    assert compact["output_compacted"] is True
    assert compact["output_attachment"] == "reportblocks/rb-1/output-rb-1.json"
    assert compact["preview"]["summary"] == "Done"


def test_persist_output_artifact_compacts_with_attachment(monkeypatch):
    monkeypatch.setattr(service, "S3_UTILS_AVAILABLE", True)
    upload_mock = Mock(return_value="reportblocks/rb-1/output-rb-1.json")
    monkeypatch.setattr(service, "upload_report_block_file", upload_mock)

    output_json, attached, output_path = service._persist_output_artifact_and_compact(
        report_block_id="rb-1",
        output_payload=json.dumps({"status": "ok"}),
        existing_details_files_list=[],
        log_prefix="[test]",
    )

    parsed = json.loads(output_json)
    assert parsed["output_compacted"] is True
    assert parsed["output_attachment"] == "reportblocks/rb-1/output-rb-1.json"
    assert attached == ["reportblocks/rb-1/output-rb-1.json"]
    assert output_path == "reportblocks/rb-1/output-rb-1.json"
    upload_mock.assert_called_once()


def test_persist_output_artifact_handles_dict_payload(monkeypatch):
    monkeypatch.setattr(service, "S3_UTILS_AVAILABLE", True)
    upload_mock = Mock(return_value="reportblocks/rb-dict/output-rb-dict.json")
    monkeypatch.setattr(service, "upload_report_block_file", upload_mock)

    output_json, attached, output_path = service._persist_output_artifact_and_compact(
        report_block_id="rb-dict",
        output_payload={"status": "ok", "summary": "dict payload"},
        existing_details_files_list=[],
        log_prefix="[test]",
    )

    parsed = json.loads(output_json)
    assert parsed["output_compacted"] is True
    assert parsed["output_attachment"] == "reportblocks/rb-dict/output-rb-dict.json"
    assert attached == ["reportblocks/rb-dict/output-rb-dict.json"]
    assert output_path == "reportblocks/rb-dict/output-rb-dict.json"
    upload_mock.assert_called_once()
    content_arg = upload_mock.call_args.kwargs["content"]
    assert isinstance(content_arg, bytes)


def test_persist_output_artifact_raises_when_s3_unavailable(monkeypatch):
    monkeypatch.setattr(service, "S3_UTILS_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="S3 utilities are unavailable"):
        service._persist_output_artifact_and_compact(
            report_block_id="rb-2",
            output_payload=json.dumps({"status": "ok"}),
            existing_details_files_list=[],
            log_prefix="[test]",
        )


def test_persist_log_artifact_if_present_attaches_log(monkeypatch):
    monkeypatch.setattr(service, "S3_UTILS_AVAILABLE", True)
    upload_mock = Mock(return_value="reportblocks/rb-3/log.txt")
    monkeypatch.setattr(service, "upload_report_block_file", upload_mock)

    log_message, attached, log_path = service._persist_log_artifact_if_present(
        report_block_id="rb-3",
        log_output="long log output",
        existing_details_files_list=[],
        log_prefix="[test]",
    )

    assert log_message == "See log.txt in attachedFiles."
    assert attached == ["reportblocks/rb-3/log.txt"]
    assert log_path == "reportblocks/rb-3/log.txt"
    upload_mock.assert_called_once()


def test_persist_log_artifact_if_present_raises_when_s3_unavailable(monkeypatch):
    monkeypatch.setattr(service, "S3_UTILS_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="S3 utilities are unavailable"):
        service._persist_log_artifact_if_present(
            report_block_id="rb-4",
            log_output="x",
            existing_details_files_list=[],
            log_prefix="[test]",
        )
