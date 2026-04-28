"""
Deterministic local Console chat latency benchmark.

Usage example:
  CONSOLE_RESPONSE_TARGET=local:ryan \
  PLEXUS_API_URL=... \
  PLEXUS_API_KEY=... \
  python dashboard/amplify/functions/consoleRunWorker/latency_benchmark.py \
    --account-id <account_id> \
    --session-id <session_id> \
    --samples 30 \
    --out /tmp/console_latency_run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from plexus.cli.procedure.builtin_procedures import CONSOLE_CHAT_BUILTIN_ID
from plexus.dashboard.api.client import PlexusDashboardClient


def _load_local_env() -> None:
    this_file = Path(__file__).resolve()
    repo_root = this_file.parents[4]
    dashboard_dir = repo_root / "dashboard"
    env_load_order = (
        (repo_root / ".env", False),
        (dashboard_dir / ".env", True),
        (dashboard_dir / ".env.local", True),
    )
    for env_file, override in env_load_order:
        if env_file.exists():
            load_dotenv(env_file, override=override)


def _resolve_client() -> PlexusDashboardClient:
    _load_local_env()
    api_url = str(os.getenv("PLEXUS_API_URL") or os.getenv("NEXT_PUBLIC_PLEXUS_API_URL") or "").strip()
    api_key = str(os.getenv("PLEXUS_API_KEY") or os.getenv("NEXT_PUBLIC_PLEXUS_API_KEY") or "").strip()
    if not api_url or not api_key:
        raise RuntimeError("PLEXUS_API_URL and PLEXUS_API_KEY are required")
    return PlexusDashboardClient(api_url=api_url, api_key=api_key)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_ms(start: Optional[str], end: Optional[str]) -> Optional[float]:
    start_dt = _parse_iso(start)
    end_dt = _parse_iso(end)
    if not start_dt or not end_dt:
        return None
    return max((end_dt - start_dt).total_seconds() * 1000.0, 0.0)


def _percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    rank = (len(sorted_vals) - 1) * p
    low = int(rank)
    high = min(low + 1, len(sorted_vals) - 1)
    frac = rank - low
    return sorted_vals[low] + (sorted_vals[high] - sorted_vals[low]) * frac


def _find_first_assistant_chunk(
    client: PlexusDashboardClient,
    *,
    session_id: str,
    after_iso: Optional[str],
    max_items: int = 300,
) -> Optional[str]:
    query = """
    query ListAssistantMessages($sessionId: String!, $limit: Int, $nextToken: String) {
      listChatMessageBySessionIdAndCreatedAt(
        sessionId: $sessionId
        sortDirection: DESC
        limit: $limit
        nextToken: $nextToken
      ) {
        items {
          role
          humanInteraction
          messageType
          content
          metadata
          createdAt
        }
        nextToken
      }
    }
    """
    next_token: Optional[str] = None
    items: List[Dict[str, Any]] = []
    after_dt = _parse_iso(after_iso)
    while len(items) < max_items:
        result = client.execute(
            query,
            {"sessionId": session_id, "limit": 100, "nextToken": next_token},
        )
        payload = result.get("listChatMessageBySessionIdAndCreatedAt", {}) if isinstance(result, dict) else {}
        page_items = payload.get("items") or []
        if isinstance(page_items, list):
            remaining = max_items - len(items)
            if remaining <= 0:
                break
            items.extend(item for item in page_items[:remaining] if isinstance(item, dict))
        next_token = payload.get("nextToken")
        if not next_token:
            break

    for item in items:
        if str(item.get("role") or "").upper() != "ASSISTANT":
            continue
        if str(item.get("messageType") or "").upper() != "MESSAGE":
            continue
        if str(item.get("humanInteraction") or "").upper() != "CHAT_ASSISTANT":
            continue
        content = str(item.get("content") or "").strip()
        if not content or content == "Assistant turn completed.":
            continue
        raw_metadata = item.get("metadata")
        metadata: Dict[str, Any] = {}
        if isinstance(raw_metadata, dict):
            metadata = raw_metadata
        elif isinstance(raw_metadata, str) and raw_metadata.strip():
            try:
                parsed = json.loads(raw_metadata)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                metadata = parsed
        streaming = metadata.get("streaming") if isinstance(metadata, dict) else None
        timings = streaming.get("timings") if isinstance(streaming, dict) else None
        first_chunk_received_at = (
            str(timings.get("first_chunk_received_at") or "").strip()
            if isinstance(timings, dict)
            else ""
        )
        if first_chunk_received_at:
            first_chunk_dt = _parse_iso(first_chunk_received_at)
            if not after_dt or (first_chunk_dt and first_chunk_dt >= after_dt):
                return first_chunk_received_at
        created_at = str(item.get("createdAt") or "").strip()
        created_dt = _parse_iso(created_at)
        if after_dt and created_dt and created_dt < after_dt:
            continue
        return created_at
    return None


def _create_user_message(
    client: PlexusDashboardClient,
    *,
    account_id: str,
    session_id: str,
    response_target: str,
    model: str,
    prompt_text: str,
    procedure_id: str,
) -> Dict[str, Any]:
    mutation = """
    mutation CreateBenchmarkUserMessage($input: CreateChatMessageInput!) {
      createChatMessage(input: $input) {
        id
        createdAt
        responseStatus
      }
    }
    """
    metadata = {
        "source": "console-latency-benchmark",
        "model": {"id": model},
        "instrumentation": {
            "client_selected_model": model,
            "benchmark_prompt": prompt_text,
        },
    }
    result = client.execute(
        mutation,
        {
            "input": {
                "accountId": account_id,
                "sessionId": session_id,
                "procedureId": procedure_id,
                "role": "USER",
                "messageType": "MESSAGE",
                "humanInteraction": "CHAT",
                "content": prompt_text,
                "metadata": json.dumps(metadata),
                "responseTarget": response_target,
                "responseStatus": "PENDING",
            }
        },
    )
    created = result.get("createChatMessage") if isinstance(result, dict) else None
    if not isinstance(created, dict) or not created.get("id"):
        raise RuntimeError("Failed to create benchmark chat message")
    return created


def _get_message(client: PlexusDashboardClient, message_id: str) -> Dict[str, Any]:
    query = """
    query GetBenchmarkMessage($id: ID!) {
      getChatMessage(id: $id) {
        id
        sessionId
        createdAt
        responseStatus
        responseStartedAt
        responseCompletedAt
        responseError
      }
    }
    """
    result = client.execute(query, {"id": message_id})
    message = result.get("getChatMessage") if isinstance(result, dict) else None
    if not isinstance(message, dict):
        raise RuntimeError(f"Message not found: {message_id}")
    return message


@dataclass
class BenchmarkRow:
    index: int
    message_id: str
    status: str
    created_at: str
    response_started_at: Optional[str]
    first_assistant_chunk_at: Optional[str]
    response_completed_at: Optional[str]
    first_chunk_ms: Optional[float]
    total_ms: Optional[float]
    response_error: Optional[str]


def run_benchmark(
    *,
    client: PlexusDashboardClient,
    account_id: str,
    session_id: str,
    response_target: str,
    model: str,
    samples: int,
    timeout_seconds: float,
    poll_interval_seconds: float,
    procedure_id: str,
) -> List[BenchmarkRow]:
    rows: List[BenchmarkRow] = []
    for index in range(1, samples + 1):
        prompt = f"Latency benchmark sample {index}: reply with 'ok {index}'."
        created = _create_user_message(
            client,
            account_id=account_id,
            session_id=session_id,
            response_target=response_target,
            model=model,
            prompt_text=prompt,
            procedure_id=procedure_id,
        )
        message_id = str(created.get("id"))
        created_at = str(created.get("createdAt") or "")
        deadline = time.time() + timeout_seconds
        status = "PENDING"
        response_started_at: Optional[str] = None
        response_completed_at: Optional[str] = None
        response_error: Optional[str] = None
        first_chunk_at: Optional[str] = None

        while time.time() < deadline:
            message = _get_message(client, message_id)
            status = str(message.get("responseStatus") or "PENDING")
            response_started_at = message.get("responseStartedAt")
            response_completed_at = message.get("responseCompletedAt")
            response_error = message.get("responseError")
            if status in {"COMPLETED", "FAILED"}:
                after_iso = response_started_at or created_at
                first_chunk_at = _find_first_assistant_chunk(
                    client,
                    session_id=session_id,
                    after_iso=after_iso,
                )
                break
            time.sleep(poll_interval_seconds)

        if status not in {"COMPLETED", "FAILED"}:
            status = "TIMEOUT"

        rows.append(
            BenchmarkRow(
                index=index,
                message_id=message_id,
                status=status,
                created_at=created_at,
                response_started_at=response_started_at,
                first_assistant_chunk_at=first_chunk_at,
                response_completed_at=response_completed_at,
                first_chunk_ms=_duration_ms(created_at, first_chunk_at),
                total_ms=_duration_ms(created_at, response_completed_at),
                response_error=response_error,
            )
        )
    return rows


def _print_report(rows: List[BenchmarkRow]) -> None:
    first_chunk_values = [row.first_chunk_ms for row in rows if isinstance(row.first_chunk_ms, (int, float))]
    total_values = [row.total_ms for row in rows if isinstance(row.total_ms, (int, float))]
    success_count = sum(1 for row in rows if row.status == "COMPLETED")

    def _fmt(value: Optional[float]) -> str:
        return "n/a" if value is None else f"{value:.1f}ms"

    print("Console latency benchmark")
    print(f"  samples: {len(rows)}")
    print(f"  completed: {success_count}")
    print(f"  first_chunk p50/p90/p95: {_fmt(_percentile(first_chunk_values, 0.50))} / {_fmt(_percentile(first_chunk_values, 0.90))} / {_fmt(_percentile(first_chunk_values, 0.95))}")
    print(f"  total      p50/p90/p95: {_fmt(_percentile(total_values, 0.50))} / {_fmt(_percentile(total_values, 0.90))} / {_fmt(_percentile(total_values, 0.95))}")
    print(f"  first_chunk median: {_fmt(median(first_chunk_values) if first_chunk_values else None)}")
    print(f"  total median: {_fmt(median(total_values) if total_values else None)}")


def _write_artifacts(rows: List[BenchmarkRow], out_prefix: Optional[str]) -> None:
    if not out_prefix:
        return
    out_base = Path(out_prefix)
    out_base.parent.mkdir(parents=True, exist_ok=True)

    json_path = out_base.with_suffix(".json")
    csv_path = out_base.with_suffix(".csv")
    payload = [row.__dict__ for row in rows]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(payload[0].keys()) if payload else [])
        if payload:
            writer.writeheader()
            writer.writerows(payload)

    print(f"Wrote artifacts: {json_path} and {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic local Console chat latency benchmark.")
    parser.add_argument("--account-id", required=True, help="Account ID for message creation")
    parser.add_argument("--session-id", required=True, help="Console chat session ID to benchmark")
    parser.add_argument("--response-target", default=os.getenv("CONSOLE_RESPONSE_TARGET", "local:ryan"), help="Response target (default: env CONSOLE_RESPONSE_TARGET or local:ryan)")
    parser.add_argument("--model", default="gpt-5.4-mini", help="Model ID to include in message metadata")
    parser.add_argument("--samples", type=int, default=30, help="Number of benchmark messages")
    parser.add_argument("--timeout-seconds", type=float, default=180.0, help="Per-message timeout")
    parser.add_argument("--poll-interval-seconds", type=float, default=0.5, help="Poll interval while waiting")
    parser.add_argument("--procedure-id", default=CONSOLE_CHAT_BUILTIN_ID, help="Procedure ID for created user messages")
    parser.add_argument("--out", default="", help="Output path prefix for JSON/CSV artifacts")
    args = parser.parse_args()

    client = _resolve_client()
    rows = run_benchmark(
        client=client,
        account_id=args.account_id,
        session_id=args.session_id,
        response_target=args.response_target,
        model=args.model,
        samples=args.samples,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        procedure_id=args.procedure_id,
    )
    _print_report(rows)
    _write_artifacts(rows, args.out or None)


if __name__ == "__main__":
    main()
