from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from plexus.console.llm_context_audit import (
    LLMContextAuditRecord,
    _s3_key,
    fetch_llm_context_audit,
    upload_llm_context_audit,
)


def _make_record(**overrides) -> LLMContextAuditRecord:
    defaults = dict(
        procedure_id="builtin:console/chat",
        session_id="sess-1",
        trigger_message_id="msg-1",
        run_id="run-1",
        agent_name="console",
        turn_index=0,
        call_index=0,
        call_type="initial",
        messages=[{"role": "user", "content": "Hello"}],
        model_config={"id": "gpt-5.4", "temperature": 0.0},
        token_stats={"input": 10, "output": 5},
        timestamp_sent="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return LLMContextAuditRecord(**defaults)


# ---------------------------------------------------------------------------
# LLMContextAuditRecord
# ---------------------------------------------------------------------------

def test_audit_record_serializes_to_json():
    record = _make_record()
    raw = json.loads(record.to_json())

    assert raw["session_id"] == "sess-1"
    assert raw["call_type"] == "initial"
    assert raw["messages"] == [{"role": "user", "content": "Hello"}]
    assert raw["compaction_applied"] is False
    assert raw["compaction_metadata"] is None


def test_audit_record_serializes_optional_fields():
    record = _make_record(
        tool_config={"tools": ["eval"]},
        timestamp_received="2026-01-01T00:00:01Z",
        latency_ms=500,
        compaction_applied=True,
        compaction_metadata={"summary": "Prior work", "tokens_saved": 1000},
    )
    raw = json.loads(record.to_json())

    assert raw["tool_config"] == {"tools": ["eval"]}
    assert raw["timestamp_received"] == "2026-01-01T00:00:01Z"
    assert raw["latency_ms"] == 500
    assert raw["compaction_applied"] is True
    assert raw["compaction_metadata"]["tokens_saved"] == 1000


def test_audit_record_round_trips_via_json():
    record = _make_record(call_index=2, call_type="tool_followup")
    restored = LLMContextAuditRecord(**json.loads(record.to_json()))

    assert restored.call_index == 2
    assert restored.call_type == "tool_followup"
    assert restored.messages == record.messages


# ---------------------------------------------------------------------------
# S3 key generation
# ---------------------------------------------------------------------------

def test_s3_key_format():
    key = _s3_key("sess-abc", turn_index=3, call_index=1)
    assert key == "console-contexts/sess-abc/turn_3_call_1.json"


def test_s3_key_sanitizes_colons_and_slashes_in_session_id():
    key = _s3_key("builtin:console/chat", turn_index=0, call_index=0)
    # No colons anywhere
    assert ":" not in key
    # The session segment (between the two expected slashes) must not contain slashes
    parts = key.split("/")
    # Expected structure: ["console-contexts", "<safe_session>", "turn_0_call_0.json"]
    assert len(parts) == 3
    assert parts[0] == "console-contexts"
    assert "/" not in parts[1]
    assert ":" not in parts[1]


# ---------------------------------------------------------------------------
# upload_llm_context_audit
# ---------------------------------------------------------------------------

def test_upload_returns_expected_s3_key():
    record = _make_record(session_id="sess-upload", turn_index=2, call_index=1)
    mock_s3 = MagicMock()

    with patch("plexus.console.llm_context_audit.boto3.client", return_value=mock_s3):
        with patch("plexus.console.llm_context_audit.get_bucket_name", return_value="test-bucket"):
            returned_key = upload_llm_context_audit(record)

    assert returned_key == "console-contexts/sess-upload/turn_2_call_1.json"
    mock_s3.upload_file.assert_called_once()
    _, kwargs = mock_s3.upload_file.call_args
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Key"] == returned_key
    assert kwargs["ExtraArgs"] == {"ContentType": "application/json"}


def test_upload_propagates_s3_error():
    from botocore.exceptions import ClientError

    record = _make_record()
    mock_s3 = MagicMock()
    mock_s3.upload_file.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "upload_file"
    )

    with patch("plexus.console.llm_context_audit.boto3.client", return_value=mock_s3):
        with patch("plexus.console.llm_context_audit.get_bucket_name", return_value="test-bucket"):
            with pytest.raises(ClientError):
                upload_llm_context_audit(record)


# ---------------------------------------------------------------------------
# fetch_llm_context_audit
# ---------------------------------------------------------------------------

def test_fetch_downloads_and_parses_record(tmp_path):
    record = _make_record(turn_index=5, call_index=0, call_type="synthesis")
    artifact_file = tmp_path / "artifact.json"
    artifact_file.write_text(record.to_json(), encoding="utf-8")

    mock_s3 = MagicMock()

    def fake_download(Bucket, Key, Filename):
        import shutil
        shutil.copy(str(artifact_file), Filename)

    mock_s3.download_file.side_effect = fake_download

    with patch("plexus.console.llm_context_audit.boto3.client", return_value=mock_s3):
        with patch("plexus.console.llm_context_audit.get_bucket_name", return_value="test-bucket"):
            restored = fetch_llm_context_audit("console-contexts/sess-1/turn_5_call_0.json")

    assert restored.turn_index == 5
    assert restored.call_type == "synthesis"
    assert restored.session_id == "sess-1"


# ---------------------------------------------------------------------------
# record_audit_keys_on_message (chat_runtime integration)
# ---------------------------------------------------------------------------

def test_record_audit_keys_writes_context_artifacts_to_metadata():
    from plexus.console import chat_runtime

    executed = []

    class AuditClient:
        def execute(self, query, variables=None, **_kwargs):
            executed.append((query, variables or {}))
            return {"data": {"updateChatMessage": {"id": "msg-1", "metadata": "{}"}}}

    chat_runtime.record_audit_keys_on_message(
        AuditClient(),
        "msg-1",
        created_at="2026-01-01T00:00:00.000Z",
        s3_keys=["console-contexts/sess-1/turn_0_call_0.json"],
    )

    assert len(executed) == 1
    query, variables = executed[0]
    assert "RecordAuditKeysOnChatMessage" in query
    metadata = json.loads(variables["input"]["metadata"])
    assert metadata["contextArtifacts"] == ["console-contexts/sess-1/turn_0_call_0.json"]


def test_record_audit_keys_preserves_existing_metadata():
    from plexus.console import chat_runtime

    executed = []

    class AuditClient:
        def execute(self, query, variables=None, **_kwargs):
            executed.append((query, variables or {}))
            return {"data": {"updateChatMessage": {"id": "msg-1", "metadata": "{}"}}}

    chat_runtime.record_audit_keys_on_message(
        AuditClient(),
        "msg-1",
        created_at="2026-01-01T00:00:00.000Z",
        s3_keys=["console-contexts/sess-1/turn_0_call_0.json"],
        existing_metadata={"model": {"id": "gpt-5.4"}, "streaming": {"enabled": True}},
    )

    _, variables = executed[0]
    metadata = json.loads(variables["input"]["metadata"])
    assert metadata["model"] == {"id": "gpt-5.4"}
    assert metadata["streaming"] == {"enabled": True}
    assert "contextArtifacts" in metadata


def test_record_audit_keys_stores_multiple_artifact_keys():
    from plexus.console import chat_runtime

    executed = []

    class AuditClient:
        def execute(self, query, variables=None, **_kwargs):
            executed.append((query, variables or {}))
            return {"data": {"updateChatMessage": {"id": "msg-1", "metadata": "{}"}}}

    keys = [
        "console-contexts/sess-1/turn_0_call_0.json",
        "console-contexts/sess-1/turn_0_call_1.json",
        "console-contexts/sess-1/turn_0_call_2.json",
    ]

    chat_runtime.record_audit_keys_on_message(
        AuditClient(),
        "msg-1",
        created_at="2026-01-01T00:00:00.000Z",
        s3_keys=keys,
    )

    _, variables = executed[0]
    metadata = json.loads(variables["input"]["metadata"])
    assert metadata["contextArtifacts"] == keys
