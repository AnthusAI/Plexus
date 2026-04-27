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


def test_compact_output_json_for_storage_marks_error_status():
    compact_json = service._compact_output_json_for_storage(
        output_payload={"status": "error", "error": "Score not found"},
        output_attachment_path="reportblocks/rb-err/output-rb-err.json",
        status="error",
        error_message="Score not found",
    )
    compact = json.loads(compact_json)

    assert compact["status"] == "error"
    assert compact["error"] == "Score not found"
    assert compact["preview"]["error"] == "Score not found"


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


def test_fetch_first_block_result_surfaces_failed_compacted_payload(monkeypatch):
    monkeypatch.setattr(service, "S3_UTILS_AVAILABLE", True)
    client = Mock()
    client.execute.return_value = {
        "getReport": {
            "reportBlocks": {
                "items": [
                    {
                        "output": json.dumps(
                            {
                                "status": "error",
                                "output_compacted": True,
                                "error": "Score not found",
                                "output_attachment": "reportblocks/rb-err/output.json",
                            }
                        )
                    }
                ]
            }
        }
    }
    monkeypatch.setattr(
        "plexus.reports.s3_utils.download_report_block_file",
        Mock(return_value=(json.dumps({"error": "Score not found"}), "application/json")),
    )

    output, error = service._fetch_first_block_result("report-err", client)

    assert output is None
    assert error == "Score not found"


def test_check_db_cache_ignores_failed_compacted_report(monkeypatch):
    report = Mock()
    report.id = "report-err"
    report.createdAt = service.datetime.now(service.timezone.utc)
    report.output = "```block\nclass: FeedbackContradictions\n```"
    report.parameters = {"_cache_key": "cache-key"}

    monkeypatch.setattr(service.Report, "list_by_account_id", Mock(return_value=[report]))
    monkeypatch.setattr(service, "_fetch_first_block_result", Mock(return_value=(None, "Score not found")))

    cached = service._check_db_cache("cache-key", "acct-1", Mock(), ttl_hours=24)

    assert cached is None


def test_check_db_cache_uses_report_parameters_cache_key(monkeypatch):
    matching_report = Mock()
    matching_report.id = "report-match"
    matching_report.createdAt = service.datetime.now(service.timezone.utc)
    matching_report.output = "```block\nclass: FeedbackContradictions\n```"
    matching_report.parameters = {"_cache_key": "cache-key"}

    non_matching_report = Mock()
    non_matching_report.id = "report-other"
    non_matching_report.createdAt = service.datetime.now(service.timezone.utc)
    non_matching_report.output = "```block\nclass: FeedbackContradictions\n```"
    non_matching_report.parameters = {"_cache_key": "other-cache-key"}

    monkeypatch.setattr(
        service.Report,
        "list_by_account_id",
        Mock(return_value=[non_matching_report, matching_report]),
    )
    monkeypatch.setattr(
        service,
        "_fetch_first_block_result",
        Mock(return_value=({"status": "ok", "topics": [1, 2]}, None)),
    )

    cached = service._check_db_cache("cache-key", "acct-1", Mock(), ttl_hours=24)

    assert cached == {"status": "ok", "topics": [1, 2]}


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
