from plexus.cli.shared.experiment_runner import (
    _derive_procedure_task_state,
    _safe_task_metadata,
)


def test_safe_task_metadata_handles_dict_string_and_invalid_values():
    assert _safe_task_metadata({"a": 1}) == {"a": 1}
    assert _safe_task_metadata('{"b":2}') == {"b": 2}
    assert _safe_task_metadata("not-json") == {}
    assert _safe_task_metadata(None) == {}


def test_derive_procedure_task_state_waiting_for_human():
    result = {"status": "WAITING_FOR_HUMAN", "success": False}
    assert _derive_procedure_task_state(result) == "WAITING_FOR_HUMAN"


def test_derive_procedure_task_state_completed_for_successful_result():
    assert _derive_procedure_task_state({"success": True}) == "COMPLETED"
    assert _derive_procedure_task_state({"status": "completed"}) == "COMPLETED"


def test_derive_procedure_task_state_failed_for_error_result():
    result = {"status": "error", "success": False, "error": "boom"}
    assert _derive_procedure_task_state(result) == "FAILED"
