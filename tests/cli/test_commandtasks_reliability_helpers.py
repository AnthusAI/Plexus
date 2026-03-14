from unittest.mock import patch

from plexus.cli.shared.CommandTasks import (
    _format_phase_error,
    _get_runtime_fingerprint,
    _safe_task_metadata,
)


def test_format_phase_error_always_returns_non_empty_message_stderr_and_details():
    message, stderr_text, details = _format_phase_error("", "execute_cli")
    assert message
    assert stderr_text
    assert details["phase"] == "execute_cli"
    assert details["traceback"]


def test_safe_task_metadata_handles_string_json_and_invalid():
    assert _safe_task_metadata({"k": "v"}) == {"k": "v"}
    assert _safe_task_metadata('{"k":"v"}') == {"k": "v"}
    assert _safe_task_metadata("bad-json") == {}


@patch("subprocess.check_output")
def test_runtime_fingerprint_uses_git_and_tactus_version(mock_check_output):
    mock_check_output.return_value = "abc123\n"
    fingerprint = _get_runtime_fingerprint()
    assert fingerprint["git_sha"] in {"abc123", None}
    assert "tactus_version" in fingerprint
    assert "build_timestamp" in fingerprint
