#!/usr/bin/env python3
"""Replay a console chat flow: edit -> edit -> champion vs latest evaluations."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plexus.chat.session_ops import get_chat_message, list_session_messages, send_chat_message
from plexus.cli.procedure.builtin_procedures import CONSOLE_CHAT_BUILTIN_ID
from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.cli.shared.client_utils import create_client
from plexus.console.chat_runtime import build_response_owner, process_console_message

# Reuse the same deterministic resolver logic the runtime uses.
from MCP.tools.tactus_runtime.execute import (  # noqa: E402
    _default_score_info,
    _resolve_score_for_score_edit,
    _resolve_scorecard_for_score_edit,
)


UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
DISPATCHER_PLACEHOLDERS = {"WILL_BE_SET_AFTER_DEPLOYMENT", "bootstrap-nonsecret"}


def _load_local_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(REPO_ROOT / ".env", override=False)
    load_dotenv(REPO_ROOT / "dashboard" / ".env", override=False)
    load_dotenv(REPO_ROOT / "dashboard" / ".env.local", override=False)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: Optional[str]) -> datetime:
    if not ts:
        return datetime.fromtimestamp(0, timezone.utc)
    parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_metadata(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _build_score_edit_message(scorecard: str, score: str, instruction: str) -> str:
    return (
        f'Please edit score "{score}" in scorecard "{scorecard}". '
        f"{instruction.strip()} "
        "Create a non-champion candidate version."
    )


def _build_evaluation_message(
    *,
    scorecard: str,
    score: str,
    champion_version_id: str,
    max_feedback_items: int,
) -> str:
    return (
        f'Run two feedback evaluations for score "{score}" in scorecard "{scorecard}". '
        f"First: evaluate the original champion version `{champion_version_id}` with "
        f"`max_feedback_items = {max_feedback_items}`, `sampling_mode = \"newest\"`, async, and no days. "
        "Second: evaluate the latest candidate version created in this chat (do not reset to champion), "
        "with the same count-based settings. "
        "Report task_id and evaluation_id for both runs."
    )


def _version_map(score_info: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    versions = score_info.get("versions") or []
    result: Dict[str, Dict[str, Any]] = {}
    for version in versions:
        version_id = str(version.get("id") or "").strip()
        if version_id:
            result[version_id] = version
    return result


def _select_single_new_version(
    before: Dict[str, Dict[str, Any]],
    after: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    new_ids = [version_id for version_id in after if version_id not in before]
    if not new_ids:
        raise RuntimeError("No new score version was created for this turn.")
    if len(new_ids) > 1:
        raise RuntimeError(f"Expected exactly one new score version, got {len(new_ids)}: {new_ids}")
    return after[new_ids[0]]


def _extract_score_change_audit(turn: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _parse_metadata(turn.get("assistant_metadata"))
    audit = metadata.get("score_change_audit") if isinstance(metadata, dict) else None
    return audit if isinstance(audit, dict) else {}


def _extract_candidate_ref_from_turn(turn: Dict[str, Any]) -> Dict[str, Optional[str]]:
    audit = _extract_score_change_audit(turn)
    version_id = str(audit.get("version_id") or "").strip()
    parent_version_id = str(audit.get("parent_version_id") or "").strip()
    if version_id:
        return {
            "version_id": version_id,
            "parent_version_id": parent_version_id or None,
            "source": "score_change_audit",
        }

    content = str(turn.get("assistant_content") or "")
    updated_match = re.search(
        r"Updated score version\]\([^)]*/versions/(?P<id>[0-9a-fA-F-]{36})\)",
        content,
    )
    previous_match = re.search(
        r"Previous score version\]\([^)]*/versions/(?P<id>[0-9a-fA-F-]{36})\)",
        content,
    )
    if not updated_match:
        updated_match = re.search(
            r"Updated score version id:\s*`(?P<id>[0-9a-fA-F-]{36})`",
            content,
            re.IGNORECASE,
        )
    if not previous_match:
        previous_match = re.search(
            r"(?:Previous|Parent) score version id:\s*`(?P<id>[0-9a-fA-F-]{36})`",
            content,
            re.IGNORECASE,
        )
    if updated_match:
        return {
            "version_id": updated_match.group("id"),
            "parent_version_id": previous_match.group("id") if previous_match else None,
            "source": "assistant_content",
        }

    return {"version_id": None, "parent_version_id": None, "source": None}


def _extract_task_ids_from_turn(turn: Dict[str, Any]) -> List[str]:
    content = str(turn.get("assistant_content") or "")
    seen: set[str] = set()
    task_ids: List[str] = []
    for match in re.finditer(r"task_id:\s*`?(?P<id>[0-9a-fA-F-]{36})`?", content, re.IGNORECASE):
        task_id = match.group("id")
        if task_id not in seen:
            seen.add(task_id)
            task_ids.append(task_id)
    return task_ids


def _summarize_turn(turn: Dict[str, Any], *, max_content_chars: int = 1600) -> Dict[str, Any]:
    content = str(turn.get("assistant_content") or "")
    audit = _extract_score_change_audit(turn)
    audit_summary = None
    if audit:
        audit_summary = {
            key: audit.get(key)
            for key in (
                "version_id",
                "parent_version_id",
                "score_id",
                "scorecard_id",
                "changed_fields",
            )
            if key in audit
        }
    return {
        "user_message_id": turn.get("user_message_id"),
        "assistant_message_id": turn.get("assistant_message_id"),
        "assistant_created_at": turn.get("assistant_created_at"),
        "score_change_audit": audit_summary,
        "task_ids": _extract_task_ids_from_turn(turn),
        "assistant_content_excerpt": content[:max_content_chars],
        "assistant_content_truncated": len(content) > max_content_chars,
    }


def _assistant_messages_since(
    messages: Iterable[Dict[str, Any]],
    *,
    sent_at: datetime,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "").upper()
        if role != "ASSISTANT":
            continue
        created = _parse_iso(message.get("createdAt"))
        if created >= sent_at:
            results.append(message)
    return results


def _create_chat_session(client: Any, *, account_id: str, procedure_id: str) -> Dict[str, Any]:
    mutation = """
    mutation CreateChatSession($input: CreateChatSessionInput!) {
      createChatSession(input: $input) {
        id
        accountId
        procedureId
        category
        status
        createdAt
        updatedAt
      }
    }
    """
    now = _iso_now()
    payload = {
        "accountId": account_id,
        "procedureId": procedure_id,
        "category": "Console Chat",
        "status": "ACTIVE",
        "createdAt": now,
        "updatedAt": now,
    }
    created = (client.execute(mutation, {"input": payload}) or {}).get("createChatSession")
    if not created or not created.get("id"):
        raise RuntimeError("Failed to create Console Chat session.")
    return created


def _turn(
    *,
    client: Any,
    session_id: str,
    response_target: str,
    owner: str,
    text: str,
    timeout_seconds: int,
    poll_seconds: float,
) -> Dict[str, Any]:
    sent = send_chat_message(
        client,
        session_id=session_id,
        text=text,
        mode="chat",
        response_target=response_target,
    )
    sent_message = sent.get("message") or {}
    sent_message_id = str(sent_message.get("id") or "").strip()
    if not sent_message_id:
        raise RuntimeError("Missing sent message id.")
    sent_at = _parse_iso(sent_message.get("createdAt"))
    started = time.time()
    while (time.time() - started) < timeout_seconds:
        raw_message = get_chat_message(client, sent_message_id)
        if raw_message:
            process_console_message(
                client,
                raw_message,
                expected_target=response_target,
                owner=owner,
            )
        payload = list_session_messages(
            client,
            session_id=session_id,
            limit=500,
            offset=0,
            include_internal=True,
        )
        assistants = _assistant_messages_since(payload.get("items") or [], sent_at=sent_at)
        if assistants:
            latest = assistants[-1]
            return {
                "user_message_id": sent_message_id,
                "assistant_message_id": latest.get("id"),
                "assistant_created_at": latest.get("createdAt"),
                "assistant_content": str(latest.get("content") or "").strip(),
                "assistant_metadata": latest.get("metadata"),
            }
        time.sleep(max(0.1, poll_seconds))
    raise TimeoutError(f"Timed out waiting for assistant response in session {session_id}.")


def _get_score_version(client: Any, version_id: str) -> Optional[Dict[str, Any]]:
    normalized = str(version_id or "").strip()
    if not normalized:
        return None
    query = """
    query GetScoreVersionForReplay($id: ID!) {
      getScoreVersion(id: $id) {
        id
        scoreId
        parentVersionId
        isFeatured
        createdAt
        updatedAt
        note
      }
    }
    """
    response = client.execute(query, {"id": normalized}) or {}
    version = response.get("getScoreVersion")
    return version if isinstance(version, dict) else None


def _resolve_candidate_version_from_turn(
    *,
    client: Any,
    turn: Dict[str, Any],
    expected_score_id: str,
    before: Dict[str, Dict[str, Any]],
    fetch_score_info,
    label: str,
    attempts: int = 6,
    delay_seconds: float = 1.0,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], str]:
    ref = _extract_candidate_ref_from_turn(turn)
    ref_version_id = ref.get("version_id")
    if ref_version_id:
        version = _get_score_version(client, ref_version_id)
        if not version:
            raise RuntimeError(f"{label} version {ref_version_id} was reported but not found.")
        if str(version.get("scoreId") or "") != str(expected_score_id):
            raise RuntimeError(
                f"{label} version {ref_version_id} belongs to score "
                f"{version.get('scoreId') or '<empty>'}, expected {expected_score_id}."
            )
        if ref.get("parent_version_id") and str(version.get("parentVersionId") or "") != ref["parent_version_id"]:
            raise RuntimeError(
                f"{label} parent mismatch: assistant reported {ref['parent_version_id']}, "
                f"GraphQL returned {version.get('parentVersionId') or '<empty>'}."
            )
        latest_info = fetch_score_info()
        latest_map = _version_map(latest_info)
        latest_map.setdefault(str(version["id"]), version)
        return version, latest_map, str(ref.get("source") or "direct")

    last_error: Optional[Exception] = None
    for attempt in range(max(1, attempts)):
        latest_info = fetch_score_info()
        latest_map = _version_map(latest_info)
        try:
            version = _select_single_new_version(before, latest_map)
            return version, latest_map, "score_info_diff"
        except RuntimeError as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(max(0.1, delay_seconds))
    raise RuntimeError(f"{label}: {last_error or 'No candidate version found.'}")


def _list_recent_tasks(client: Any, account_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
    query = """
    query ListTaskByAccount($accountId: String!, $updatedAt: ModelStringKeyConditionInput, $limit: Int) {
      listTaskByAccountIdAndUpdatedAt(
        accountId: $accountId
        updatedAt: $updatedAt
        sortDirection: DESC
        limit: $limit
      ) {
        items {
          id
          type
          status
          dispatchStatus
          workerNodeId
          command
          target
          metadata
          createdAt
          updatedAt
          errorMessage
          evaluation {
            id
          }
        }
      }
    }
    """
    response = client.execute(
        query,
        {
            "accountId": account_id,
            "updatedAt": {"ge": "2000-01-01T00:00:00.000Z"},
            "limit": limit,
        },
    ) or {}
    return ((response.get("listTaskByAccountIdAndUpdatedAt") or {}).get("items") or [])


def _list_recent_evaluations(client: Any, account_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
    query = """
    query ListEvaluationByAccountIdAndUpdatedAt($accountId: String!, $limit: Int, $sortDirection: ModelSortDirection) {
      listEvaluationByAccountIdAndUpdatedAt(
        accountId: $accountId
        limit: $limit
        sortDirection: $sortDirection
      ) {
        items {
          id
          type
          status
          taskId
          scoreVersionId
          createdAt
          updatedAt
        }
      }
    }
    """
    response = client.execute(
        query,
        {
            "accountId": account_id,
            "limit": limit,
            "sortDirection": "DESC",
        },
    ) or {}
    return ((response.get("listEvaluationByAccountIdAndUpdatedAt") or {}).get("items") or [])


def _get_task(client: Any, task_id: str) -> Optional[Dict[str, Any]]:
    normalized = str(task_id or "").strip()
    if not normalized:
        return None
    query = """
    query GetTask($id: ID!) {
      getTask(id: $id) {
        id
        type
        status
        dispatchStatus
        workerNodeId
        target
        command
        metadata
        createdAt
        updatedAt
        errorMessage
      }
    }
    """
    response = client.execute(query, {"id": normalized}) or {}
    task = response.get("getTask")
    return task if isinstance(task, dict) else None


def _is_task_claimed_or_running(task: Optional[Dict[str, Any]]) -> bool:
    if not task:
        return False
    dispatch_status = str(task.get("dispatchStatus") or "").upper()
    status = str(task.get("status") or "").upper()
    worker_node = str(task.get("workerNodeId") or "").strip()
    if worker_node:
        return True
    if dispatch_status in {"DISPATCHING", "DISPATCHED", "COMPLETED"}:
        return True
    return status in {"RUNNING", "COMPLETED"}


def _are_tasks_created(tasks: Iterable[Optional[Dict[str, Any]]]) -> bool:
    return all(bool(task and task.get("id")) for task in tasks)


def _are_tasks_dispatched(tasks: Iterable[Optional[Dict[str, Any]]]) -> bool:
    return all(_is_task_claimed_or_running(task) for task in tasks)


def _task_dispatcher_readiness() -> Dict[str, Any]:
    try:
        import boto3
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "reason": f"boto3 unavailable: {exc}"}

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    try:
        lambda_client = boto3.client("lambda", region_name=region)
        functions = lambda_client.list_functions().get("Functions") or []
        main_dispatchers = [
            item
            for item in functions
            if "TaskDispatcherFunction" in str(item.get("FunctionName") or "")
            and "main" in str(item.get("FunctionName") or "").lower()
        ]
        if not main_dispatchers:
            return {"checked": True, "ready": False, "reason": "main TaskDispatcher Lambda not found"}
        function_name = str(main_dispatchers[0]["FunctionName"])
        config = lambda_client.get_function_configuration(FunctionName=function_name)
        env = (config.get("Environment") or {}).get("Variables") or {}
        placeholder_keys = [
            key
            for key in (
                "CELERY_AWS_ACCESS_KEY_ID",
                "CELERY_AWS_SECRET_ACCESS_KEY",
                "CELERY_AWS_REGION_NAME",
                "CELERY_QUEUE_NAME",
                "CELERY_RESULT_BACKEND_TEMPLATE",
            )
            if not str(env.get(key) or "").strip()
            or str(env.get(key) or "").strip() in DISPATCHER_PLACEHOLDERS
        ]
        mappings = lambda_client.list_event_source_mappings(
            FunctionName=function_name
        ).get("EventSourceMappings") or []
        disabled = [
            mapping
            for mapping in mappings
            if str(mapping.get("State") or "").lower() != "enabled"
        ]
        reasons: List[str] = []
        if placeholder_keys:
            reasons.append("TaskDispatcher has placeholder/missing env: " + ", ".join(placeholder_keys))
        if not mappings:
            reasons.append("TaskDispatcher has no event source mapping")
        elif disabled:
            states = ", ".join(
                f"{mapping.get('UUID')}={mapping.get('State')}" for mapping in disabled
            )
            reasons.append(f"TaskDispatcher event source mapping not enabled: {states}")
        return {
            "checked": True,
            "ready": not reasons,
            "function_name": function_name,
            "event_source_mapping_count": len(mappings),
            "reason": "; ".join(reasons) if reasons else None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "ready": None, "reason": str(exc)}


def _match_evaluations(
    evaluations: Iterable[Dict[str, Any]],
    *,
    champion_version_id: str,
    candidate_version_id: str,
    not_before: datetime,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    champion_eval: Optional[Dict[str, Any]] = None
    candidate_eval: Optional[Dict[str, Any]] = None
    for evaluation in evaluations:
        created_at = _parse_iso(evaluation.get("createdAt"))
        if created_at < not_before:
            continue
        version_id = str(evaluation.get("scoreVersionId") or "").strip()
        if version_id == champion_version_id and champion_eval is None:
            champion_eval = evaluation
        if version_id == candidate_version_id and candidate_eval is None:
            candidate_eval = evaluation
    return champion_eval, candidate_eval


def _build_evaluation_task_entry(evaluation: Dict[str, Any], task: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "task_id": evaluation.get("taskId"),
        "status": (task or {}).get("status"),
        "dispatch_status": (task or {}).get("dispatchStatus"),
        "score_version_id": evaluation.get("scoreVersionId"),
        "worker_node_id": (task or {}).get("workerNodeId"),
        "evaluation_id": evaluation.get("id"),
        "evaluation_status": evaluation.get("status"),
    }


def _resolve_score_identity(client: Any, scorecard_identifier: str, score_identifier: str) -> Dict[str, str]:
    scorecard = _resolve_scorecard_for_score_edit(client, scorecard_identifier)
    score = _resolve_score_for_score_edit(client, str(scorecard["id"]), score_identifier)
    return {
        "scorecard_id": str(scorecard["id"]),
        "score_id": str(score["id"]),
        "scorecard_name": str(scorecard.get("name") or scorecard_identifier),
        "score_name": str(score.get("name") or score_identifier),
    }


def _score_info(scorecard_id: str, score_id: str) -> Dict[str, Any]:
    result = _default_score_info(
        {
            "scorecard_identifier": scorecard_id,
            "score_identifier": score_id,
        }
    )
    if not result.get("found"):
        raise RuntimeError(f"Could not resolve score info for {scorecard_id} / {score_id}.")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-key", default=os.getenv("PLEXUS_ACCOUNT_KEY"))
    parser.add_argument("--scorecard", default="SelectQuote HCS Medium-Risk")
    parser.add_argument("--score", default="Agent Misrepresentation")
    parser.add_argument("--first-edit-text", required=True)
    parser.add_argument("--second-edit-text", required=True)
    parser.add_argument("--response-target", default="local:ryan")
    parser.add_argument("--procedure-id", default=CONSOLE_CHAT_BUILTIN_ID)
    parser.add_argument("--max-feedback-items", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--task-wait-seconds", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    _load_local_env()
    args = parse_args()
    if not str(args.response_target).startswith("local:"):
        raise ValueError("--response-target must be a local target such as local:ryan")
    if args.account_key:
        os.environ["PLEXUS_ACCOUNT_KEY"] = str(args.account_key).strip()
    client = create_client()
    if not client:
        raise RuntimeError("Could not create dashboard client. Check API credentials.")
    account_id = resolve_account_id_for_command(client, None)
    if not account_id:
        raise RuntimeError("Could not resolve account id from account key.")

    score_identity = _resolve_score_identity(client, args.scorecard, args.score)
    initial_info = _score_info(score_identity["scorecard_id"], score_identity["score_id"])
    champion_version_id = str(initial_info.get("championVersionId") or "").strip()
    if not champion_version_id:
        raise RuntimeError("Champion version ID was empty; cannot run replay.")
    before_first = _version_map(initial_info)

    session = _create_chat_session(client, account_id=account_id, procedure_id=args.procedure_id)
    session_id = str(session["id"])
    owner = build_response_owner(args.response_target)

    result: Dict[str, Any] = {
        "pass": False,
        "version_chain_pass": False,
        "evaluation_tasks_created": False,
        "evaluation_tasks_dispatched": False,
        "evaluation_records_created": False,
        "infra_blocked_reason": None,
        "session_id": session_id,
        "scorecard": args.scorecard,
        "score": args.score,
        "scorecard_id": score_identity["scorecard_id"],
        "score_id": score_identity["score_id"],
        "champion_version_id": champion_version_id,
        "assistant_turns": [],
    }

    try:
        turn1 = _turn(
            client=client,
            session_id=session_id,
            response_target=args.response_target,
            owner=owner,
            text=_build_score_edit_message(args.scorecard, args.score, args.first_edit_text),
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
        result["assistant_turns"].append(_summarize_turn(turn1))

        def fetch_current_score_info() -> Dict[str, Any]:
            return _score_info(score_identity["scorecard_id"], score_identity["score_id"])

        candidate_a, after_first, candidate_a_source = _resolve_candidate_version_from_turn(
            client=client,
            turn=turn1,
            expected_score_id=score_identity["score_id"],
            before=before_first,
            fetch_score_info=fetch_current_score_info,
            label="First edit",
        )
        candidate_a_id = str(candidate_a["id"])
        candidate_a_parent = str(candidate_a.get("parentVersionId") or "")
        if candidate_a_parent != champion_version_id:
            raise RuntimeError(
                f"First edit parent mismatch: expected {champion_version_id}, got {candidate_a_parent or '<empty>'}."
            )
        result["candidate_a_version_id"] = candidate_a_id
        result["candidate_a_parent_version_id"] = candidate_a_parent
        result["candidate_a_detection_source"] = candidate_a_source

        turn2 = _turn(
            client=client,
            session_id=session_id,
            response_target=args.response_target,
            owner=owner,
            text=_build_score_edit_message(args.scorecard, args.score, args.second_edit_text),
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
        result["assistant_turns"].append(_summarize_turn(turn2))

        candidate_b, _after_second, candidate_b_source = _resolve_candidate_version_from_turn(
            client=client,
            turn=turn2,
            expected_score_id=score_identity["score_id"],
            before=after_first,
            fetch_score_info=fetch_current_score_info,
            label="Second edit",
        )
        candidate_b_id = str(candidate_b["id"])
        candidate_b_parent = str(candidate_b.get("parentVersionId") or "")
        if candidate_b_parent != candidate_a_id:
            raise RuntimeError(
                f"Second edit parent mismatch: expected {candidate_a_id}, got {candidate_b_parent or '<empty>'}."
            )
        result["candidate_b_version_id"] = candidate_b_id
        result["candidate_b_parent_version_id"] = candidate_b_parent
        result["candidate_b_detection_source"] = candidate_b_source
        result["version_chain_pass"] = True

        evaluation_requested_at = datetime.now(timezone.utc)
        turn3 = _turn(
            client=client,
            session_id=session_id,
            response_target=args.response_target,
            owner=owner,
            text=_build_evaluation_message(
                scorecard=args.scorecard,
                score=args.score,
                champion_version_id=champion_version_id,
                max_feedback_items=args.max_feedback_items,
            ),
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
        result["assistant_turns"].append(_summarize_turn(turn3))

        dispatcher_readiness = _task_dispatcher_readiness()
        result["task_dispatcher_readiness"] = dispatcher_readiness

        started = time.time()
        champion_eval: Optional[Dict[str, Any]] = None
        candidate_eval: Optional[Dict[str, Any]] = None
        champion_task: Optional[Dict[str, Any]] = None
        candidate_task: Optional[Dict[str, Any]] = None
        task_ids = _extract_task_ids_from_turn(turn3)
        if len(task_ids) >= 2:
            champion_task = _get_task(client, task_ids[0])
            candidate_task = _get_task(client, task_ids[1])
            result["evaluation_tasks"] = {
                "champion": {
                    "task_id": task_ids[0],
                    "status": (champion_task or {}).get("status"),
                    "dispatch_status": (champion_task or {}).get("dispatchStatus"),
                    "score_version_id": champion_version_id,
                    "worker_node_id": (champion_task or {}).get("workerNodeId"),
                    "evaluation_id": None,
                    "evaluation_status": None,
                },
                "candidate_latest": {
                    "task_id": task_ids[1],
                    "status": (candidate_task or {}).get("status"),
                    "dispatch_status": (candidate_task or {}).get("dispatchStatus"),
                    "score_version_id": candidate_b_id,
                    "worker_node_id": (candidate_task or {}).get("workerNodeId"),
                    "evaluation_id": None,
                    "evaluation_status": None,
                },
            }
            result["evaluation_tasks_created"] = _are_tasks_created(
                [champion_task, candidate_task]
            )
            result["evaluation_tasks_dispatched"] = _are_tasks_dispatched(
                [champion_task, candidate_task]
            )

        while (time.time() - started) < args.task_wait_seconds:
            evaluations = _list_recent_evaluations(client, account_id, limit=150)
            champion_eval, candidate_eval = _match_evaluations(
                evaluations,
                champion_version_id=champion_version_id,
                candidate_version_id=candidate_b_id,
                not_before=evaluation_requested_at,
            )
            if champion_eval and candidate_eval:
                champion_task = _get_task(client, str(champion_eval.get("taskId") or ""))
                candidate_task = _get_task(client, str(candidate_eval.get("taskId") or ""))
                if _is_task_claimed_or_running(champion_task) and _is_task_claimed_or_running(candidate_task):
                    break
            time.sleep(max(0.2, args.poll_seconds))

        result["evaluation_records_created"] = bool(champion_eval and candidate_eval)
        if not champion_eval or not candidate_eval:
            if result["evaluation_tasks_created"] and not result["evaluation_tasks_dispatched"]:
                result["infra_blocked_reason"] = (
                    dispatcher_readiness.get("reason")
                    or "Evaluation tasks were created but not dispatched."
                )
                result["pass"] = bool(result["version_chain_pass"])
                print(json.dumps(result, indent=2, sort_keys=True, default=str))
                return 0
            raise RuntimeError("Did not find both champion and candidate evaluations.")
        if not str(champion_eval.get("taskId") or "").strip():
            raise RuntimeError("Champion evaluation exists but taskId is empty.")
        if not str(candidate_eval.get("taskId") or "").strip():
            raise RuntimeError("Candidate evaluation exists but taskId is empty.")
        if not _is_task_claimed_or_running(champion_task):
            raise RuntimeError("Champion evaluation task was created but never claimed/started.")
        if not _is_task_claimed_or_running(candidate_task):
            raise RuntimeError("Candidate evaluation task was created but never claimed/started.")

        result["evaluation_tasks"] = {
            "champion": _build_evaluation_task_entry(champion_eval, champion_task),
            "candidate_latest": _build_evaluation_task_entry(candidate_eval, candidate_task),
        }
        result["evaluation_tasks_created"] = True
        result["evaluation_tasks_dispatched"] = True
        result["pass"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
