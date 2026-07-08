from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from console_chat_score_edit_replay import (
    _are_tasks_created,
    _are_tasks_dispatched,
    _build_evaluation_task_entry,
    _build_evaluation_message,
    _extract_candidate_ref_from_turn,
    _extract_task_ids_from_turn,
    _is_task_claimed_or_running,
    _match_evaluations,
    _resolve_candidate_version_from_turn,
    _select_single_new_version,
    _task_dispatcher_readiness,
)


VERSION_A = "11111111-1111-4111-8111-111111111111"
VERSION_B = "22222222-2222-4222-8222-222222222222"
PARENT_VERSION = "33333333-3333-4333-8333-333333333333"
SCORE_ID = "44444444-4444-4444-8444-444444444444"
TASK_A = "55555555-5555-4555-8555-555555555555"
TASK_B = "66666666-6666-4666-8666-666666666666"


def test_select_single_new_version_returns_only_new_entry() -> None:
    before = {
        "v1": {"id": "v1", "parentVersionId": "p0"},
        "v2": {"id": "v2", "parentVersionId": "v1"},
    }
    after = {
        **before,
        "v3": {"id": "v3", "parentVersionId": "v2"},
    }
    selected = _select_single_new_version(before, after)
    assert selected["id"] == "v3"
    assert selected["parentVersionId"] == "v2"


def test_select_single_new_version_raises_when_missing_or_multiple() -> None:
    before = {"v1": {"id": "v1"}}
    with pytest.raises(RuntimeError, match="No new score version"):
        _select_single_new_version(before, dict(before))

    with pytest.raises(RuntimeError, match="Expected exactly one new score version"):
        _select_single_new_version(before, {"v1": {"id": "v1"}, "v2": {"id": "v2"}, "v3": {"id": "v3"}})


def test_build_evaluation_message_uses_count_mode_without_days() -> None:
    message = _build_evaluation_message(
        scorecard="Scorecard A",
        score="Score X",
        champion_version_id="champion-123",
        max_feedback_items=20,
    )
    assert "champion-123" in message
    assert "max_feedback_items = 20" in message
    assert "sampling_mode = \"newest\"" in message
    assert "no days" in message.lower()
    assert "do not reset to champion" in message.lower()


def test_extract_candidate_ref_prefers_score_change_audit_metadata() -> None:
    ref = _extract_candidate_ref_from_turn(
        {
            "assistant_metadata": {
                "score_change_audit": {
                    "version_id": VERSION_A,
                    "parent_version_id": PARENT_VERSION,
                }
            },
            "assistant_content": f"[Updated score version](/versions/{VERSION_B})",
        }
    )

    assert ref == {
        "version_id": VERSION_A,
        "parent_version_id": PARENT_VERSION,
        "source": "score_change_audit",
    }


def test_extract_candidate_ref_falls_back_to_assistant_links() -> None:
    ref = _extract_candidate_ref_from_turn(
        {
            "assistant_content": (
                f"[Previous score version](https://example.test/lab/scorecards/sc/scores/s/versions/{PARENT_VERSION})\n"
                f"[Updated score version](https://example.test/lab/scorecards/sc/scores/s/versions/{VERSION_A})"
            )
        }
    )

    assert ref == {
        "version_id": VERSION_A,
        "parent_version_id": PARENT_VERSION,
        "source": "assistant_content",
    }


def test_resolve_candidate_version_verifies_direct_score_version_parent() -> None:
    class FakeClient:
        def execute(self, _query, variables):
            assert variables == {"id": VERSION_A}
            return {
                "getScoreVersion": {
                    "id": VERSION_A,
                    "scoreId": SCORE_ID,
                    "parentVersionId": PARENT_VERSION,
                }
            }

    version, latest_map, source = _resolve_candidate_version_from_turn(
        client=FakeClient(),
        turn={
            "assistant_metadata": {
                "score_change_audit": {
                    "version_id": VERSION_A,
                    "parent_version_id": PARENT_VERSION,
                }
            }
        },
        expected_score_id=SCORE_ID,
        before={},
        fetch_score_info=lambda: {"versions": []},
        label="First edit",
        attempts=1,
    )

    assert version["id"] == VERSION_A
    assert version["parentVersionId"] == PARENT_VERSION
    assert latest_map[VERSION_A]["id"] == VERSION_A
    assert source == "score_change_audit"


def test_match_evaluations_finds_champion_and_candidate() -> None:
    now = datetime.now(timezone.utc)
    evaluations = [
        {
            "id": "older-eval",
            "createdAt": "2001-01-01T00:00:00Z",
            "scoreVersionId": "champ",
            "taskId": "older-task",
        },
        {
            "id": "champion-eval",
            "createdAt": now.isoformat(),
            "scoreVersionId": "champ",
            "taskId": "champion-task",
        },
        {
            "id": "candidate-eval",
            "createdAt": now.isoformat(),
            "scoreVersionId": "cand",
            "taskId": "candidate-task",
        },
    ]
    champion_eval, candidate_eval = _match_evaluations(
        evaluations,
        champion_version_id="champ",
        candidate_version_id="cand",
        not_before=now.replace(microsecond=0),
    )
    assert champion_eval is not None
    assert champion_eval["id"] == "champion-eval"
    assert candidate_eval is not None
    assert candidate_eval["id"] == "candidate-eval"


def test_is_task_claimed_or_running_distinguishes_pending_from_dispatched() -> None:
    assert _is_task_claimed_or_running({"dispatchStatus": "PENDING"}) is False
    assert _is_task_claimed_or_running({"dispatchStatus": "DISPATCHING"}) is True
    assert _is_task_claimed_or_running({"dispatchStatus": "DISPATCHED"}) is True
    assert _is_task_claimed_or_running({"status": "RUNNING"}) is True
    assert _is_task_claimed_or_running({"workerNodeId": "node-1"}) is True
    assert _is_task_claimed_or_running({"dispatchStatus": "FAILED", "status": "FAILED"}) is False


def test_task_creation_and_dispatch_flags_are_separate() -> None:
    pending_tasks = [
        {"id": TASK_A, "dispatchStatus": "PENDING"},
        {"id": TASK_B, "dispatchStatus": "PENDING"},
    ]
    dispatched_tasks = [
        {"id": TASK_A, "dispatchStatus": "DISPATCHED"},
        {"id": TASK_B, "workerNodeId": "worker-1"},
    ]

    assert _are_tasks_created(pending_tasks) is True
    assert _are_tasks_dispatched(pending_tasks) is False
    assert _are_tasks_created(dispatched_tasks) is True
    assert _are_tasks_dispatched(dispatched_tasks) is True


def test_extract_task_ids_from_assistant_response() -> None:
    task_ids = _extract_task_ids_from_turn(
        {
            "assistant_content": (
                f"Champion task_id: `{TASK_A}`\n"
                f"Candidate task_id: {TASK_B}\n"
                f"Repeated task_id: `{TASK_A}`"
            )
        }
    )

    assert task_ids == [TASK_A, TASK_B]


def test_task_dispatcher_readiness_reports_placeholder_or_disabled(monkeypatch) -> None:
    class FakeLambda:
        def list_functions(self):
            return {
                "Functions": [
                    {"FunctionName": "amplify-plexus-main-TaskDispatcherFunction-abc"}
                ]
            }

        def get_function_configuration(self, FunctionName):
            assert FunctionName == "amplify-plexus-main-TaskDispatcherFunction-abc"
            return {
                "Environment": {
                    "Variables": {
                        "CELERY_AWS_ACCESS_KEY_ID": "bootstrap-nonsecret",
                        "CELERY_AWS_SECRET_ACCESS_KEY": "secret",
                        "CELERY_AWS_REGION_NAME": "us-east-1",
                        "CELERY_QUEUE_NAME": "queue",
                        "CELERY_RESULT_BACKEND_TEMPLATE": "WILL_BE_SET_AFTER_DEPLOYMENT",
                    }
                }
            }

        def list_event_source_mappings(self, FunctionName):
            assert FunctionName == "amplify-plexus-main-TaskDispatcherFunction-abc"
            return {
                "EventSourceMappings": [
                    {"UUID": "mapping-1", "State": "Disabled"},
                ]
            }

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *_args, **_kwargs: FakeLambda()))

    readiness = _task_dispatcher_readiness()

    assert readiness["checked"] is True
    assert readiness["ready"] is False
    assert "placeholder/missing env" in readiness["reason"]
    assert "not enabled" in readiness["reason"]


def test_build_evaluation_task_entry_merges_evaluation_and_task_fields() -> None:
    entry = _build_evaluation_task_entry(
        {"id": "eval-1", "taskId": "task-1", "scoreVersionId": "version-1", "status": "RUNNING"},
        {"status": "RUNNING", "dispatchStatus": "PENDING", "workerNodeId": "worker-1"},
    )
    assert entry["evaluation_id"] == "eval-1"
    assert entry["task_id"] == "task-1"
    assert entry["score_version_id"] == "version-1"
    assert entry["dispatch_status"] == "PENDING"
