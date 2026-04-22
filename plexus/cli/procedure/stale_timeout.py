from __future__ import annotations

import json
import logging
import os
import socket
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.experiment_runner import _parse_json_dict
from plexus.cli.shared.experiment_runner import _update_procedure_status_and_metadata
from plexus.dashboard.api.models.task import Task

logger = logging.getLogger(__name__)

STALE_PROCEDURE_TIMEOUT_SECONDS = 3600
STALE_PROCEDURE_TIMEOUT_MESSAGE = "Stalled process detected after timeout period"
STALE_PROCEDURE_DEAD_PROCESS_MESSAGE = "Procedure process no longer running"
STALE_PROCEDURE_LOOKBACK_HOURS = 72
STALLED_STATUS = "STALLED"


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _runtime_process_alive(runtime: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(runtime, dict):
        return {"known": False, "alive": None, "reason": "missing_runtime_metadata"}

    host = str(runtime.get("host") or "").strip()
    pid_raw = runtime.get("pid")
    try:
        pid = int(pid_raw)
    except Exception:
        return {"known": False, "alive": None, "reason": "invalid_runtime_pid"}

    if pid <= 0:
        return {"known": False, "alive": None, "reason": "invalid_runtime_pid"}

    local_host = socket.gethostname()
    if not host:
        return {"known": False, "alive": None, "reason": "missing_runtime_host", "pid": pid}
    if host != local_host:
        return {"known": False, "alive": None, "reason": "runtime_host_mismatch", "pid": pid, "host": host}

    try:
        os.kill(pid, 0)
        return {"known": True, "alive": True, "reason": "process_alive", "pid": pid, "host": host}
    except ProcessLookupError:
        return {"known": True, "alive": False, "reason": "process_not_found", "pid": pid, "host": host}
    except PermissionError:
        # Process exists but permission denied to signal.
        return {"known": True, "alive": True, "reason": "permission_denied", "pid": pid, "host": host}
    except Exception as exc:
        return {
            "known": False,
            "alive": None,
            "reason": "pid_probe_failed",
            "pid": pid,
            "host": host,
            "error": str(exc),
        }


def _extract_procedure_id_from_task_payload(task_data: Dict[str, Any]) -> Optional[str]:
    target = str(task_data.get("target") or "").strip()
    for prefix in ("procedure/run/", "procedure/"):
        if target.startswith(prefix):
            procedure_id = target[len(prefix):].strip()
            if procedure_id:
                return procedure_id

    metadata = _parse_json_dict(task_data.get("metadata"))
    procedure_id = metadata.get("procedure_id")
    if isinstance(procedure_id, str) and procedure_id.strip():
        return procedure_id.strip()
    return None


def _list_procedure_tasks(client: Any, account_id: str) -> List[Dict[str, Any]]:
    query = """
    query ListTaskByAccountIdAndUpdatedAt($accountId: String!, $updatedAt: ModelStringKeyConditionInput, $limit: Int, $nextToken: String) {
        listTaskByAccountIdAndUpdatedAt(accountId: $accountId, updatedAt: $updatedAt, limit: $limit, nextToken: $nextToken) {
            items {
                id
                status
                target
                command
                metadata
                startedAt
                updatedAt
                completedAt
                errorMessage
            }
            nextToken
        }
    }
    """

    items: List[Dict[str, Any]] = []
    next_token: Optional[str] = None

    while True:
        variables = {
            "accountId": account_id,
            "updatedAt": {"ge": "2000-01-01T00:00:00.000Z"},
            "limit": 1000,
        }
        if next_token:
            variables["nextToken"] = next_token

        result = client.execute(query, variables)
        payload = result.get("listTaskByAccountIdAndUpdatedAt", {}) if isinstance(result, dict) else {}
        page_items = payload.get("items", []) if isinstance(payload, dict) else []
        if isinstance(page_items, list):
            items.extend(item for item in page_items if isinstance(item, dict))

        next_token = payload.get("nextToken") if isinstance(payload, dict) else None
        if not next_token:
            break

    procedure_tasks = []
    for item in items:
        if not _extract_procedure_id_from_task_payload(item):
            continue
        procedure_tasks.append(item)

    procedure_tasks.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
    return procedure_tasks


def _get_procedure_status_snapshot(client: Any, procedure_id: str) -> Dict[str, Any]:
    query = """
    query GetProcedureStatusSnapshot($id: ID!) {
        getProcedure(id: $id) {
            id
            status
            metadata
            waitingOnMessageId
            updatedAt
        }
    }
    """
    result = client.execute(query, {"id": procedure_id})
    procedure = result.get("getProcedure") if isinstance(result, dict) else None
    if not isinstance(procedure, dict):
        return {}
    procedure["metadata"] = _parse_json_dict(procedure.get("metadata"))
    return procedure


def _list_procedure_chat_sessions(client: Any, procedure_id: str) -> List[Dict[str, Any]]:
    query = """
    query ListChatSessionsByProcedure($procedureId: String!, $limit: Int) {
        listChatSessions(
            filter: { procedureId: { eq: $procedureId } }
            limit: $limit
        ) {
            items {
                id
                status
                createdAt
                updatedAt
            }
        }
    }
    """
    result = client.execute(query, {"procedureId": procedure_id, "limit": 50})
    payload = result.get("listChatSessions", {}) if isinstance(result, dict) else {}
    items = payload.get("items", []) if isinstance(payload, dict) else []
    normalized = [item for item in items if isinstance(item, dict)]
    normalized.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
    return normalized


def _get_latest_message_created_at(client: Any, session_id: str) -> Optional[datetime]:
    query = """
    query GetLatestSessionMessage($sessionId: String!, $limit: Int) {
        listChatMessageBySessionIdAndCreatedAt(
            sessionId: $sessionId
            sortDirection: DESC
            limit: $limit
        ) {
            items {
                id
                createdAt
            }
        }
    }
    """
    result = client.execute(query, {"sessionId": session_id, "limit": 1})
    payload = result.get("listChatMessageBySessionIdAndCreatedAt", {}) if isinstance(result, dict) else {}
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not items:
        return None
    return _parse_iso_datetime(items[0].get("createdAt"))


def _get_latest_chat_activity_at(client: Any, procedure_id: str) -> Optional[datetime]:
    latest: Optional[datetime] = None
    for session in _list_procedure_chat_sessions(client, procedure_id):
        session_created_at = _parse_iso_datetime(session.get("createdAt"))
        if session_created_at and (latest is None or session_created_at > latest):
            latest = session_created_at

        session_id = session.get("id")
        if not isinstance(session_id, str) or not session_id.strip():
            continue
        last_message_at = _get_latest_message_created_at(client, session_id.strip())
        if last_message_at and (latest is None or last_message_at > latest):
            latest = last_message_at
    return latest


def _mark_procedure_chat_sessions_stalled(client: Any, procedure_id: str) -> None:
    mutation = """
    mutation UpdateChatSessionStatus($input: UpdateChatSessionInput!) {
        updateChatSession(input: $input) {
            id
            status
        }
    }
    """
    for session in _list_procedure_chat_sessions(client, procedure_id):
        session_id = session.get("id")
        if not isinstance(session_id, str) or not session_id.strip():
            continue
        session_status = str(session.get("status") or "").upper()
        if session_status in {"FAILED", "COMPLETED", STALLED_STATUS}:
            continue
        try:
            client.execute(mutation, {"input": {"id": session_id.strip(), "status": STALLED_STATUS}})
        except Exception as exc:
            logger.warning("Could not mark chat session %s stalled for procedure %s: %s", session_id, procedure_id, exc)


def _mark_nonterminal_task_stages_status(
    client: Any,
    task_id: str,
    *,
    status: str,
    status_message: str,
    now: datetime,
) -> None:
    stage_query = """
    query GetTask($id: ID!) {
        getTask(id: $id) {
            stages {
                items {
                    id
                    order
                    status
                }
            }
        }
    }
    """
    update_mutation = """
    mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
        updateTaskStage(input: $input) {
            id
            status
        }
    }
    """
    result = client.execute(stage_query, {"id": task_id})
    stages = result.get("getTask", {}).get("stages", {}).get("items", [])
    if not stages:
        return
    short_message = (status_message or "")[:500]
    now_iso = now.isoformat()
    for stage in stages:
        stage_status = str(stage.get("status") or "").upper()
        if stage_status in {"PENDING", "RUNNING"}:
            client.execute(
                update_mutation,
                {
                    "input": {
                        "id": stage.get("id"),
                        "status": status,
                        "completedAt": now_iso,
                        "statusMessage": short_message,
                    }
                },
            )


def timeout_stale_procedures(
    *,
    client: Any,
    account_id: str,
    threshold_seconds: int = STALE_PROCEDURE_TIMEOUT_SECONDS,
    lookback_hours: int = STALE_PROCEDURE_LOOKBACK_HOURS,
    exclude_procedure_id: Optional[str] = None,
    dry_run: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    if threshold_seconds <= 0:
        raise ValueError("threshold_seconds must be positive")
    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")

    now = now or datetime.now(timezone.utc)
    stale_after = timedelta(seconds=threshold_seconds)
    started_after = now - timedelta(hours=lookback_hours)

    recent_by_procedure: Dict[str, Dict[str, Any]] = {}
    for task_data in _list_procedure_tasks(client, account_id):
        procedure_id = _extract_procedure_id_from_task_payload(task_data)
        if not procedure_id or procedure_id == exclude_procedure_id:
            continue
        started_at = _parse_iso_datetime(task_data.get("startedAt"))
        if not started_at or started_at < started_after:
            continue

        existing = recent_by_procedure.get(procedure_id)
        if not existing:
            recent_by_procedure[procedure_id] = task_data
            continue
        existing_started_at = _parse_iso_datetime(existing.get("startedAt"))
        if existing_started_at is None or started_at > existing_started_at:
            recent_by_procedure[procedure_id] = task_data

    recent_started: List[Dict[str, Any]] = []
    for procedure_id, task_data in recent_by_procedure.items():
        recent_started.append(
            {
                "procedure_id": procedure_id,
                "task_id": task_data.get("id"),
                "status": str(task_data.get("status") or ""),
                "started_at": task_data.get("startedAt"),
                "updated_at": task_data.get("updatedAt"),
            }
        )
    recent_started.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)

    candidates_by_procedure: Dict[str, Dict[str, Any]] = {}
    for procedure_id, task_data in recent_by_procedure.items():
        if str(task_data.get("status") or "").upper() != "RUNNING":
            continue
        candidates_by_procedure[procedure_id] = task_data

    checked = 0
    timed_out: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for procedure_id, task_data in candidates_by_procedure.items():
        checked += 1
        procedure = _get_procedure_status_snapshot(client, procedure_id)
        procedure_status = str(procedure.get("status") or "").upper()
        if procedure_status == "WAITING_FOR_HUMAN":
            skipped.append({"procedure_id": procedure_id, "reason": "waiting_for_human"})
            continue

        runtime = procedure.get("metadata", {}).get("runtime") if isinstance(procedure.get("metadata"), dict) else {}
        if not isinstance(runtime, dict):
            runtime = {}
        liveness = _runtime_process_alive(runtime)
        runtime_dead = bool(liveness.get("known")) and liveness.get("alive") is False

        started_at = _parse_iso_datetime(task_data.get("startedAt"))
        failure_payload: Optional[Dict[str, Any]] = None
        silence_seconds: Optional[int] = None
        last_activity_iso: Optional[str] = None

        if runtime_dead:
            failure_payload = {
                "kind": "process_dead",
                "signal": None,
                "exception_type": None,
                "message": STALE_PROCEDURE_DEAD_PROCESS_MESSAGE,
                "phase": None,
                "terminated_at": now.isoformat(),
                "pid": runtime.get("pid"),
                "host": runtime.get("host"),
                "traceback": None,
                "process_probe": liveness,
            }
        else:
            last_activity_at = _get_latest_chat_activity_at(client, procedure_id)
            activity_source = "chat"
            if last_activity_at is None:
                if started_at is None:
                    skipped.append({"procedure_id": procedure_id, "reason": "no_chat_activity"})
                    continue
                last_activity_at = started_at
                activity_source = "task_started_at"

            inactivity = now - last_activity_at
            if inactivity <= stale_after:
                skipped.append(
                    {
                        "procedure_id": procedure_id,
                        "reason": "fresh_chat_activity" if activity_source == "chat" else "fresh_no_chat_runtime",
                        "last_activity_at": last_activity_at.isoformat(),
                        "activity_source": activity_source,
                        "process_probe": liveness,
                    }
                )
                continue

            silence_seconds = int(inactivity.total_seconds())
            last_activity_iso = last_activity_at.isoformat()
            failure_payload = {
                "kind": "timeout",
                "signal": None,
                "exception_type": None,
                "message": STALE_PROCEDURE_TIMEOUT_MESSAGE,
                "phase": None,
                "terminated_at": now.isoformat(),
                "pid": runtime.get("pid"),
                "host": runtime.get("host"),
                "traceback": None,
                "timeout_seconds": threshold_seconds,
                "last_chat_activity_at": last_activity_iso,
                "activity_source": activity_source,
                "process_probe": liveness,
            }

        if not failure_payload:
            continue

        record = {
            "procedure_id": procedure_id,
            "task_id": task_data.get("id"),
            "last_chat_activity_at": last_activity_iso,
            "silence_seconds": silence_seconds,
            "failure": failure_payload,
            "dry_run": dry_run,
        }

        if dry_run:
            timed_out.append(record)
            continue

        task = Task.get_by_id(str(task_data["id"]), client)
        if not task or str(getattr(task, "status", "")).upper() != "RUNNING":
            skipped.append({"procedure_id": procedure_id, "reason": "task_not_running"})
            continue

        failure_message = str(failure_payload.get("message") or STALE_PROCEDURE_TIMEOUT_MESSAGE)
        try:
            _mark_nonterminal_task_stages_status(
                client,
                task.id,
                status=STALLED_STATUS,
                status_message=failure_message,
                now=now,
            )
        except Exception as exc:
            logger.warning("Could not mark task stages stalled for timed out procedure %s: %s", procedure_id, exc, exc_info=True)

        task_metadata = _parse_json_dict(task.metadata)
        try:
            task.update(
                accountId=task.accountId,
                type=task.type,
                status=STALLED_STATUS,
                target=task.target,
                command=task.command,
                metadata=json.dumps(task_metadata),
                updatedAt=now.isoformat(),
                completedAt=now.isoformat(),
                errorMessage=failure_message,
                errorDetails=json.dumps(failure_payload),
            )
        except Exception as exc:
            logger.warning("Could not update Task %s as STALLED during stale timeout: %s", task.id, exc, exc_info=True)
            skipped.append({"procedure_id": procedure_id, "reason": "task_update_failed", "error": str(exc)})
            continue

        try:
            _update_procedure_status_and_metadata(
                client,
                procedure_id,
                status=STALLED_STATUS,
                metadata_patch={
                    "last_failure": failure_payload,
                },
            )
        except Exception as exc:
            logger.warning(
                "Could not update Procedure %s as STALLED during stale timeout: %s",
                procedure_id,
                exc,
                exc_info=True,
            )
            record.setdefault("warnings", []).append(f"procedure_update_failed: {exc}")

        try:
            _mark_procedure_chat_sessions_stalled(client, procedure_id)
        except Exception as exc:
            logger.warning(
                "Could not update chat sessions for Procedure %s during stale timeout: %s",
                procedure_id,
                exc,
                exc_info=True,
            )
            record.setdefault("warnings", []).append(f"chat_session_update_failed: {exc}")

        timed_out.append(record)

    return {
        "threshold_seconds": threshold_seconds,
        "lookback_hours": lookback_hours,
        "window_started_after": started_after.isoformat(),
        "recent_started_count": len(recent_started),
        "recent_started": recent_started,
        "checked": checked,
        "timed_out": timed_out,
        "skipped": skipped,
        "dry_run": dry_run,
    }


def launch_async_stale_timeout_scan(
    *,
    account_id: str,
    exclude_procedure_id: Optional[str] = None,
    threshold_seconds: int = STALE_PROCEDURE_TIMEOUT_SECONDS,
    lookback_hours: int = STALE_PROCEDURE_LOOKBACK_HOURS,
) -> None:
    def _worker() -> None:
        try:
            client = create_client()
            if not client:
                logger.warning("Skipping stale procedure timeout scan because API client could not be created")
                return
            result = timeout_stale_procedures(
                client=client,
                account_id=account_id,
                threshold_seconds=threshold_seconds,
                lookback_hours=lookback_hours,
                exclude_procedure_id=exclude_procedure_id,
            )
            logger.info(
                "Stale procedure timeout scan completed: recent_started=%s checked=%s timed_out=%s skipped=%s",
                result.get("recent_started_count"),
                result.get("checked"),
                len(result.get("timed_out") or []),
                len(result.get("skipped") or []),
            )
        except Exception as exc:
            logger.warning("Background stale procedure timeout scan failed: %s", exc, exc_info=True)

    thread = threading.Thread(
        target=_worker,
        name=f"stale-procedure-timeout-{exclude_procedure_id or 'scan'}",
        daemon=True,
    )
    thread.start()
