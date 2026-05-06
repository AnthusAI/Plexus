#!/usr/bin/env python3
"""
Staging canary for execute_tactus async report dispatch.

Validates:
1) execute_tactus returns a handle for plexus.report.run(async=true)
2) handle status includes dispatched task id
3) task lifecycle advances from PENDING to DISPATCHED/COMPLETED (or fails)
4) persisted Report and ReportBlock records exist for the cache key
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "WILL_BE_SET_AFTER_DEPLOYMENT"


class CanaryError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorecard", default="selectquote_hcs_medium_risk")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--dispatch-mode", default="celery")
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--child-budget-usd", type=float, default=0.20)
    parser.add_argument("--child-budget-seconds", type=int, default=60)
    parser.add_argument("--child-budget-depth", type=int, default=1)
    parser.add_argument("--child-budget-tool-calls", type=int, default=3)
    parser.add_argument("--parent-budget-usd", type=float, default=0.25)
    parser.add_argument("--parent-budget-seconds", type=int, default=90)
    parser.add_argument("--parent-budget-depth", type=int, default=3)
    parser.add_argument("--parent-budget-tool-calls", type=int, default=50)
    return parser.parse_args()


def _require_env(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value or value == PLACEHOLDER:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _auth_mode() -> str:
    return str(os.getenv("PLEXUS_GRAPHQL_AUTH_MODE") or "api_key").strip().lower()


def _prepare_import_path() -> None:
    repo = str(REPO_ROOT)
    cleaned: list[str] = []
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


def _build_tactus(scorecard: str, days: int, cache_key: str, child_budget: dict[str, Any]) -> str:
    return f"""
local h = plexus.report.run({{
  block_class = "ScoreChampionVersionTimeline",
  block_config = {{
    scorecard = "{scorecard}",
    days = {days},
  }},
  cache_key = "{cache_key}",
  ttl_hours = 24,
  async = true,
  budget = {{
    usd = {child_budget["usd"]},
    wallclock_seconds = {child_budget["wallclock_seconds"]},
    depth = {child_budget["depth"]},
    tool_calls = {child_budget["tool_calls"]},
  }},
}})
return h
"""


def _safe_get(dct: Any, *keys: str) -> Any:
    cur = dct
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


async def _run_canary(args: argparse.Namespace) -> dict[str, Any]:
    # Keep process-level explicit env authoritative for dispatch behavior.
    try:
        import dotenv  # type: ignore

        dotenv.load_dotenv = lambda *a, **k: False
    except Exception:
        pass

    api_url = _require_env("PLEXUS_API_URL")
    auth_mode = _auth_mode()
    api_key = None if auth_mode == "iam" else _require_env("PLEXUS_API_KEY")
    account_key = _require_env("PLEXUS_ACCOUNT_KEY")
    os.environ["PLEXUS_DISPATCH_MODE"] = args.dispatch_mode

    from fastmcp import FastMCP

    from MCP.tools.tactus_runtime.execute import (
        BudgetGate,
        BudgetSpec,
        _execute_tactus_tool,
    )
    from plexus.dashboard.api.client import ClientContext, PlexusDashboardClient
    from plexus.dashboard.api.models.report import Report
    from plexus.dashboard.api.models.report_block import ReportBlock
    from plexus.dashboard.api.models.task import Task

    child_budget = {
        "usd": float(args.child_budget_usd),
        "wallclock_seconds": int(args.child_budget_seconds),
        "depth": int(args.child_budget_depth),
        "tool_calls": int(args.child_budget_tool_calls),
    }
    parent_budget = BudgetGate(
        BudgetSpec(
            usd=float(args.parent_budget_usd),
            wallclock_seconds=float(args.parent_budget_seconds),
            depth=int(args.parent_budget_depth),
            tool_calls=int(args.parent_budget_tool_calls),
        )
    )

    run_id = str(uuid.uuid4())[:8]
    cache_key = (
        "ScoreChampionVersionTimeline: "
        f"{args.scorecard} / {args.days}d / staging_canary / {_utc_stamp()} / {run_id}"
    )
    diagnostics: dict[str, Any] = {
        "dispatch_mode": args.dispatch_mode,
        "auth_mode": auth_mode,
        "cache_key": cache_key,
    }

    mcp = FastMCP("report-dispatch-canary")
    run_result = await _execute_tactus_tool(
        _build_tactus(args.scorecard, args.days, cache_key, child_budget),
        mcp,
        budget=parent_budget,
    )
    if not run_result.get("ok"):
        diagnostics["trace_id"] = run_result.get("trace_id")
        raise CanaryError(
            f"execute_tactus failed: {json.dumps(run_result, default=str)}",
            diagnostics,
        )

    handle_id = _safe_get(run_result, "value", "id")
    trace_id = run_result.get("trace_id")
    diagnostics.update({"trace_id": trace_id, "handle_id": handle_id})
    if not handle_id:
        raise CanaryError(
            f"execute_tactus did not return a handle id: {json.dumps(run_result, default=str)}",
            diagnostics,
        )

    status_result = await _execute_tactus_tool(f'return handle_status{{ id = "{handle_id}" }}', mcp)
    if not status_result.get("ok"):
        raise CanaryError(
            f"handle_status failed: {json.dumps(status_result, default=str)}",
            diagnostics,
        )

    task_id = _safe_get(status_result, "value", "dispatch_result", "task_id")
    diagnostics["task_id"] = task_id
    if not task_id:
        raise CanaryError(
            (
                "handle_status did not include dispatched task id. "
                f"status={json.dumps(status_result, default=str)}"
            ),
            diagnostics,
        )

    client = PlexusDashboardClient(
        api_url=api_url,
        api_key=api_key,
        context=ClientContext(account_key=account_key),
    )
    account_id = client._resolve_account_id()

    deadline = time.time() + args.timeout_seconds
    seen_pending = False
    seen_dispatched = False
    final_task_status: Optional[str] = None
    final_dispatch_status: Optional[str] = None
    report_id: Optional[str] = None
    report_block_count = 0

    while time.time() < deadline:
        task = Task.get_by_id(task_id, client)
        final_task_status = task.status
        final_dispatch_status = task.dispatchStatus
        diagnostics.update({
            "task_status": final_task_status,
            "dispatch_status": final_dispatch_status,
        })

        if task.dispatchStatus == "PENDING":
            seen_pending = True
        if task.dispatchStatus in {"DISPATCHING", "DISPATCHED"}:
            seen_dispatched = True

        reports = Report.list_by_account_id(account_id, client, limit=50, max_items=250)
        matched_report = None
        for rep in reports:
            params = rep.parameters if isinstance(rep.parameters, dict) else {}
            if params.get("_cache_key") == cache_key:
                matched_report = rep
                break

        if matched_report:
            report_id = matched_report.id
            blocks = ReportBlock.list_by_report_id(matched_report.id, client, limit=20, max_items=50)
            report_block_count = len(blocks)
            diagnostics.update({
                "report_id": report_id,
                "report_block_count": report_block_count,
            })

        if task.status == "COMPLETED" and report_id and report_block_count > 0:
            if not seen_pending:
                raise CanaryError(
                    (
                        "Task never observed in PENDING state before completion. "
                        f"task_id={task_id} final_dispatch_status={final_dispatch_status}"
                    ),
                    diagnostics,
                )
            if not seen_dispatched:
                raise CanaryError(
                    (
                        "Task never observed in DISPATCHED/DISPATCHING state before completion. "
                        f"task_id={task_id} final_dispatch_status={final_dispatch_status}"
                    ),
                    diagnostics,
                )
            return {
                "status": "ok",
                "dispatch_mode": args.dispatch_mode,
                "trace_id": trace_id,
                "handle_id": handle_id,
                "task_id": task_id,
                "report_id": report_id,
                "report_block_count": report_block_count,
                "task_status": final_task_status,
                "dispatch_status": final_dispatch_status,
                "cache_key": cache_key,
            }

        if task.status in {"FAILED", "ERROR"}:
            diagnostics["task_error"] = task.errorMessage
            raise CanaryError(
                (
                    "Task failed during canary run "
                    f"(task_id={task_id}, status={task.status}, dispatch={task.dispatchStatus}, "
                    f"error={task.errorMessage})"
                ),
                diagnostics,
            )

        await asyncio.sleep(args.poll_interval_seconds)

    raise CanaryError(
        (
            "Timed out waiting for report dispatch canary completion. "
            f"trace_id={trace_id} handle_id={handle_id} task_id={task_id} report_id={report_id} "
            f"task_status={final_task_status} dispatch_status={final_dispatch_status}"
        ),
        diagnostics,
    )


def main() -> int:
    _prepare_import_path()
    _load_env()
    args = _parse_args()
    try:
        result = asyncio.run(_run_canary(args))
        print(json.dumps(result, indent=2, default=str))
        return 0
    except Exception as exc:
        payload = {
            "status": "error",
            "error": str(exc),
            "dispatch_mode": args.dispatch_mode,
        }
        if isinstance(exc, CanaryError):
            payload.update(exc.diagnostics)
        print(json.dumps(payload, indent=2, default=str))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
