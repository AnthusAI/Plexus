#!/usr/bin/env python3
"""Pre-production dispatch canaries for execute_tactus and Task dispatch paths."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "WILL_BE_SET_AFTER_DEPLOYMENT"
TERMINAL_OK = {"COMPLETED", "COMPLETE", "SUCCESS", "SUCCEEDED"}
TERMINAL_BAD = {"FAILED", "ERROR"}


def _prepare_import_path() -> None:
    repo = str(REPO_ROOT)
    cleaned = []
    for entry in sys.path:
        try:
            resolved = str(Path(entry or ".").resolve())
        except OSError:
            cleaned.append(entry)
            continue
        if (
            resolved.startswith(str(REPO_ROOT.parent / "Plexus"))
            and resolved != repo
            and not resolved.startswith(repo + os.sep)
        ):
            continue
        cleaned.append(entry)
    sys.path = [repo, *[entry for entry in cleaned if entry != repo]]


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(REPO_ROOT / ".env", override=False)
    load_dotenv(REPO_ROOT / "dashboard" / ".env.local", override=False)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=str)


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value or value == PLACEHOLDER:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _auth_mode() -> str:
    return str(os.getenv("PLEXUS_GRAPHQL_AUTH_MODE") or "api_key").strip().lower()


def _client_and_account() -> tuple[Any, str]:
    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client

    client = create_client()
    if not client:
        raise RuntimeError("Could not create Plexus dashboard client")
    account_id = resolve_account_id_for_command(client, None)
    if not account_id:
        raise RuntimeError("Could not resolve account id from PLEXUS_ACCOUNT_KEY")
    return client, account_id


async def _execute_tactus(tactus: str) -> dict[str, Any]:
    from fastmcp import FastMCP

    from MCP.tools.tactus_runtime.execute import BudgetGate, BudgetSpec, _execute_tactus_tool

    return await _execute_tactus_tool(
        tactus,
        FastMCP("preprod-dispatch-canary"),
        budget=BudgetGate(
            BudgetSpec(
                usd=2.0,
                wallclock_seconds=900,
                depth=3,
                tool_calls=100,
            )
        ),
    )


def _handle_status(handle_id: str) -> dict[str, Any]:
    result = asyncio.run(_execute_tactus(f'return handle_status{{ id = "{handle_id}" }}'))
    if not result.get("ok"):
        raise RuntimeError(f"handle_status failed: {_json(result)}")
    value = result.get("value")
    if not isinstance(value, dict):
        raise RuntimeError(f"handle_status returned non-object value: {_json(result)}")
    return value


def _cache_key(label: str) -> str:
    return f"preprod-dispatch-canary:{label}:{_stamp()}:{uuid.uuid4().hex[:8]}"


def _block_tactus(cache_key: str, child_seconds: int = 90) -> str:
    return f"""
local h = plexus.report.run({{
  block_class = "ScoreChampionVersionTimeline",
  block_config = {{
    scorecard = "selectquote_hcs_medium_risk",
    days = 365,
  }},
  cache_key = "{cache_key}",
  ttl_hours = 24,
  async = true,
  budget = {{ usd = 0.20, wallclock_seconds = {child_seconds}, depth = 1, tool_calls = 3 }},
}})
return h
"""


def _find_report_for_cache_key(client: Any, account_id: str, cache_key: str) -> tuple[str | None, int]:
    from plexus.dashboard.api.models.report import Report
    from plexus.dashboard.api.models.report_block import ReportBlock

    reports = Report.list_by_account_id(account_id, client, limit=50, max_items=300)
    for report in reports:
        params = report.parameters if isinstance(report.parameters, dict) else {}
        if params.get("_cache_key") == cache_key:
            blocks = ReportBlock.list_by_report_id(report.id, client, limit=20, max_items=50)
            return report.id, len(blocks)
    return None, 0


def _task_mentions_cache_key(task: dict[str, Any], cache_key: str) -> bool:
    payload = json.dumps(task, default=str)
    return cache_key in payload


def _is_remote_dispatch_task(task: dict[str, Any]) -> bool:
    dispatch_status = str(task.get("dispatchStatus") or "").upper()
    status = str(task.get("status") or "").upper()
    return dispatch_status in {"PENDING", "DISPATCHED", "RUNNING"} or status in {
        "PENDING",
        "RUNNING",
    }


def _recent_tasks_for_account(client: Any, account_id: str, limit: int = 50) -> list[dict[str, Any]]:
    query = """
    query ListTaskByAccountIdAndUpdatedAt(
      $accountId: String!
      $updatedAt: ModelStringKeyConditionInput
      $sortDirection: ModelSortDirection
      $limit: Int
    ) {
      listTaskByAccountIdAndUpdatedAt(
        accountId: $accountId
        updatedAt: $updatedAt
        sortDirection: $sortDirection
        limit: $limit
      ) {
        items {
          id type status dispatchStatus command target metadata createdAt updatedAt
          errorMessage errorDetails stdout stderr workerNodeId
        }
      }
    }
    """
    response = client.execute(
        query,
        {
            "accountId": account_id,
            "updatedAt": {"ge": "2000-01-01T00:00:00.000Z"},
            "sortDirection": "DESC",
            "limit": limit,
        },
    )
    return response.get("listTaskByAccountIdAndUpdatedAt", {}).get("items", [])


def _wait_until(
    label: str,
    timeout_seconds: int,
    poll_seconds: float,
    callback: Callable[[], Any],
) -> Any:
    deadline = time.time() + timeout_seconds
    last: Any = None
    while time.time() < deadline:
        last = callback()
        if last:
            return last
        time.sleep(poll_seconds)
    raise RuntimeError(f"Timed out waiting for {label}. Last state: {_json(last)}")


def _process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _wait_task(client: Any, task_id: str, timeout_seconds: int, poll_seconds: float) -> Any:
    from plexus.dashboard.api.models.task import Task

    def poll() -> Any:
        task = Task.get_by_id(task_id, client)
        status = str(getattr(task, "status", "") or "").upper()
        if status in TERMINAL_BAD:
            raise RuntimeError(
                f"Task {task_id} failed: {getattr(task, 'errorMessage', None)}"
            )
        return task if status in TERMINAL_OK else None

    return _wait_until(f"task {task_id}", timeout_seconds, poll_seconds, poll)


def _create_report_block_task(cache_key: str) -> dict[str, Any]:
    from plexus.reports.service import run_block_cached

    client, account_id = _client_and_account()
    output, log_output, _cached = run_block_cached(
        block_class="ScoreChampionVersionTimeline",
        block_config={"scorecard": "selectquote_hcs_medium_risk", "days": 365},
        account_id=account_id,
        client=client,
        cache_key=cache_key,
        ttl_hours=24,
        fresh=True,
        background=True,
        child_budget={
            "usd": 0.20,
            "wallclock_seconds": 90,
            "depth": 1,
            "tool_calls": 3,
        },
    )
    if not isinstance(output, dict) or not output.get("task_id"):
        raise RuntimeError(f"Could not create report block task: {output} {log_output}")
    return output


def _create_task(
    client: Any,
    account_id: str,
    task_type: str,
    target: str,
    command: str,
    metadata: dict[str, Any],
) -> Any:
    from plexus.dashboard.api.models.task import Task

    return Task.create(
        client=client,
        accountId=account_id,
        type=task_type,
        target=target,
        command=command,
        description=f"Preprod dispatch canary: {target}",
        metadata=json.dumps(metadata, sort_keys=True),
        dispatchStatus="PENDING",
        status="PENDING",
    )


def _create_log_demo_procedure() -> str:
    from plexus.cli.procedure.service import ProcedureService

    client, _account_id = _client_and_account()
    account = _require_env("PLEXUS_ACCOUNT_KEY")
    yaml_config = (REPO_ROOT / "plexus" / "procedures" / "examples" / "log_demo.yaml").read_text()
    result = ProcedureService(client).create_procedure(
        account_identifier=account,
        yaml_config=yaml_config,
        featured=False,
    )
    if not result.success or not result.procedure:
        raise RuntimeError(f"Could not create log demo procedure: {result.message}")
    return result.procedure.id


def _print_result(result: dict[str, Any]) -> None:
    print(_json(result))


def canary_direct_local_report(args: argparse.Namespace) -> dict[str, Any]:
    os.environ["PLEXUS_DISPATCH_MODE"] = "local"
    client, account_id = _client_and_account()
    cache_key = _cache_key("direct-local-report")
    before = _recent_tasks_for_account(client, account_id, limit=50)

    result = asyncio.run(_execute_tactus(_block_tactus(cache_key)))
    if not result.get("ok"):
        raise RuntimeError(f"execute_tactus failed: {_json(result)}")
    handle_id = result.get("value", {}).get("id")
    if not handle_id:
        raise RuntimeError(f"execute_tactus did not return a handle: {_json(result)}")
    handle = _handle_status(str(handle_id))
    dispatch = handle.get("dispatch_result", {})
    if dispatch.get("status") != "running" or not dispatch.get("pid"):
        raise RuntimeError(f"Expected local subprocess dispatch, got: {_json(dispatch)}")
    local_pid = int(dispatch["pid"])

    def poll_report() -> tuple[str, int] | None:
        report_id, block_count = _find_report_for_cache_key(client, account_id, cache_key)
        if report_id and block_count > 0:
            return (report_id, block_count)
        if not _process_is_running(local_pid):
            latest_handle = _handle_status(str(handle_id))
            raise RuntimeError(
                "Direct local report subprocess exited before report persistence. "
                f"pid={local_pid} cache_key={cache_key} handle={_json(latest_handle)}"
            )
        return None

    report_id, block_count = _wait_until(
        "direct local report persistence",
        args.timeout_seconds,
        args.poll_interval_seconds,
        poll_report,
    )
    after = _recent_tasks_for_account(client, account_id, limit=75)
    new_task_ids = {
        task.get("id")
        for task in after
        if _task_mentions_cache_key(task, cache_key) and _is_remote_dispatch_task(task)
    }
    old_task_ids = {task.get("id") for task in before if _task_mentions_cache_key(task, cache_key)}
    unexpected = sorted(new_task_ids - old_task_ids)
    if unexpected:
        raise RuntimeError(f"Direct local report created remote Task rows: {unexpected}")

    return {
        "status": "ok",
        "scenario": "direct-local-report",
        "trace_id": result.get("trace_id"),
        "handle_id": handle_id,
        "pid": local_pid,
        "report_id": report_id,
        "report_block_count": block_count,
        "cache_key": cache_key,
    }


def canary_local_task_dispatcher(args: argparse.Namespace) -> dict[str, Any]:
    client, account_id = _client_and_account()
    cache_key = _cache_key("local-task-dispatcher")
    task_result = _create_report_block_task(cache_key)
    task_id = task_result["task_id"]
    _wait_until(
        f"pending task visibility for {task_id}",
        args.timeout_seconds,
        args.poll_interval_seconds,
        lambda: any(
            task.get("id") == task_id
            for task in _recent_tasks_for_account(client, account_id, limit=50)
            if task.get("dispatchStatus") == "PENDING"
            and task.get("status") == "PENDING"
        ),
    )

    env = os.environ.copy()
    env["PLEXUS_DISPATCH_MODE"] = "local"
    env["PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT"] = "false"
    command = [
        sys.executable,
        "-m",
        "plexus.cli",
        "command",
        "dispatcher",
        "--once",
        "--limit",
        "10",
        "--loglevel",
        "INFO",
    ]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=args.timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Local task dispatcher failed:\n"
            f"stdout={completed.stdout[-4000:]}\nstderr={completed.stderr[-4000:]}"
        )

    task = _wait_task(client, task_id, args.timeout_seconds, args.poll_interval_seconds)
    report_id, block_count = _find_report_for_cache_key(client, account_id, cache_key)
    if not report_id or block_count < 1:
        raise RuntimeError(f"Local dispatcher task completed without report for {cache_key}")

    return {
        "status": "ok",
        "scenario": "local-task-dispatcher",
        "task_id": task_id,
        "task_status": task.status,
        "dispatch_status": task.dispatchStatus,
        "report_id": report_id,
        "report_block_count": block_count,
        "cache_key": cache_key,
    }


def canary_direct_local_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    os.environ["PLEXUS_DISPATCH_MODE"] = "local"
    tactus = """
local h = plexus.evaluation.run({
  evaluation_type = "accuracy",
  scorecard_name = "SelectQuote HCS Medium-Risk",
  score_name = "Patient Allergies",
  n_samples = 1,
  async = true,
  budget = { usd = 0.50, wallclock_seconds = 180, depth = 1, tool_calls = 3 },
})
return h
"""
    result = asyncio.run(_execute_tactus(tactus))
    if not result.get("ok"):
        raise RuntimeError(f"execute_tactus failed: {_json(result)}")
    handle_id = result.get("value", {}).get("id")
    if not handle_id:
        raise RuntimeError(f"execute_tactus did not return a handle: {_json(result)}")

    def poll_handle() -> str | None:
        handle = _handle_status(str(handle_id))
        dispatch = handle.get("dispatch_result", {})
        evaluation_id = handle.get("evaluation_id") or dispatch.get("evaluation_id")
        if evaluation_id:
            return evaluation_id
        if str(handle.get("status") or "").lower() in {
            "failed",
            "completed_unknown",
            "cancelled",
        }:
            raise RuntimeError(f"Evaluation handle ended without an evaluation id: {_json(handle)}")
        return None

    evaluation_id = _wait_until(
        f"evaluation id for handle {handle_id}",
        args.timeout_seconds,
        args.poll_interval_seconds,
        poll_handle,
    )

    def poll_eval() -> dict[str, Any] | None:
        status_result = asyncio.run(_execute_tactus(f'return evaluation_info{{ evaluation_id = "{evaluation_id}" }}'))
        if not status_result.get("ok"):
            raise RuntimeError(f"evaluation_info failed: {_json(status_result)}")
        value = status_result.get("value") or {}
        status = str(value.get("status") or value.get("evaluation", {}).get("status") or "").upper()
        if status in TERMINAL_BAD:
            raise RuntimeError(f"Evaluation {evaluation_id} failed: {_json(value)}")
        return value if status in TERMINAL_OK else None

    final = _wait_until(
        f"evaluation {evaluation_id}",
        args.timeout_seconds,
        args.poll_interval_seconds,
        poll_eval,
    )
    return {
        "status": "ok",
        "scenario": "direct-local-evaluation",
        "trace_id": result.get("trace_id"),
        "handle_id": handle_id,
        "evaluation_id": evaluation_id,
        "evaluation_status": final.get("status") or final.get("evaluation", {}).get("status"),
    }


def canary_direct_local_procedure(args: argparse.Namespace) -> dict[str, Any]:
    os.environ["PLEXUS_DISPATCH_MODE"] = "local"
    procedure_id = args.procedure_id or _create_log_demo_procedure()
    result = asyncio.run(
        _execute_tactus(
            f"""
return plexus.procedure.run({{
  procedure_id = "{procedure_id}",
  dry_run = true,
  async = true,
  budget = {{ usd = 0.10, wallclock_seconds = 120, depth = 1, tool_calls = 3 }},
}})
"""
        )
    )
    if not result.get("ok"):
        raise RuntimeError(f"execute_tactus failed: {_json(result)}")

    from plexus.dashboard.api.models.procedure import Procedure

    client, _account_id = _client_and_account()

    def poll_proc() -> Any:
        proc = Procedure.get_by_id(procedure_id, client)
        status = str(getattr(proc, "status", "") or "").upper()
        if status in TERMINAL_BAD:
            raise RuntimeError(f"Procedure {procedure_id} failed")
        return proc if status in TERMINAL_OK else None

    proc = _wait_until(
        f"procedure {procedure_id}",
        args.timeout_seconds,
        args.poll_interval_seconds,
        poll_proc,
    )
    return {
        "status": "ok",
        "scenario": "direct-local-procedure",
        "trace_id": result.get("trace_id"),
        "handle_id": result.get("value", {}).get("id"),
        "procedure_id": procedure_id,
        "procedure_status": proc.status,
    }


def canary_remote_evaluation_task(args: argparse.Namespace) -> dict[str, Any]:
    client, account_id = _client_and_account()
    marker = _cache_key("remote-evaluation-task")
    task = _create_task(
        client,
        account_id,
        task_type="Evaluation",
        target="evaluation/accuracy",
        command=(
            "evaluate accuracy --scorecard 'SelectQuote HCS Medium-Risk' "
            "--score 'Patient Allergies' --number-of-samples 1 --json-only"
        ),
        metadata={"canary": marker, "scenario": "remote-evaluation-task"},
    )
    final = _wait_task(client, task.id, args.timeout_seconds, args.poll_interval_seconds)
    return {
        "status": "ok",
        "scenario": "remote-evaluation-task",
        "task_id": task.id,
        "task_status": final.status,
        "dispatch_status": final.dispatchStatus,
        "marker": marker,
    }


def canary_remote_procedure_task(args: argparse.Namespace) -> dict[str, Any]:
    client, account_id = _client_and_account()
    procedure_id = args.procedure_id or _create_log_demo_procedure()
    marker = _cache_key("remote-procedure-task")
    task = _create_task(
        client,
        account_id,
        task_type="Procedure",
        target="procedure/run",
        command=f"procedure run {procedure_id} --dry-run -o json",
        metadata={
            "canary": marker,
            "scenario": "remote-procedure-task",
            "procedure_id": procedure_id,
        },
    )
    final = _wait_task(client, task.id, args.timeout_seconds, args.poll_interval_seconds)
    return {
        "status": "ok",
        "scenario": "remote-procedure-task",
        "task_id": task.id,
        "task_status": final.status,
        "dispatch_status": final.dispatchStatus,
        "procedure_id": procedure_id,
        "marker": marker,
    }


SCENARIOS: dict[str, Callable[[argparse.Namespace], dict[str, Any]]] = {
    "direct-local-report": canary_direct_local_report,
    "local-task-dispatcher": canary_local_task_dispatcher,
    "direct-local-evaluation": canary_direct_local_evaluation,
    "direct-local-procedure": canary_direct_local_procedure,
    "remote-evaluation-task": canary_remote_evaluation_task,
    "remote-procedure-task": canary_remote_procedure_task,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        choices=[*SCENARIOS.keys(), "all-local", "all-remote-tasks"],
    )
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--procedure-id", default=None)
    return parser.parse_args()


def main() -> int:
    _prepare_import_path()
    _load_env()
    _require_env("PLEXUS_API_URL")
    if _auth_mode() != "iam":
        _require_env("PLEXUS_API_KEY")
    _require_env("PLEXUS_ACCOUNT_KEY")

    args = parse_args()
    scenario_names = [args.scenario]
    if args.scenario == "all-local":
        scenario_names = [
            "direct-local-report",
            "local-task-dispatcher",
            "direct-local-evaluation",
            "direct-local-procedure",
        ]
    elif args.scenario == "all-remote-tasks":
        scenario_names = ["remote-evaluation-task", "remote-procedure-task"]

    results = []
    try:
        for scenario in scenario_names:
            result = SCENARIOS[scenario](args)
            results.append(result)
            _print_result(result)
        return 0
    except Exception as exc:
        payload = {
            "status": "error",
            "scenario": scenario_names[len(results)] if len(results) < len(scenario_names) else args.scenario,
            "completed": results,
            "error": str(exc),
        }
        print(_json(payload))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
