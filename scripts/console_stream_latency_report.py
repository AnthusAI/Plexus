#!/usr/bin/env python3
"""
Report console streaming latency markers from persisted chat metadata.

This script reads frontend + backend timing instrumentation for recent Console
sessions and prints latency breakdowns without requiring browser log copy/paste.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plexus.dashboard.api.client import ClientContext, PlexusDashboardClient
from plexus.cli.procedure.builtin_procedures import CONSOLE_CHAT_BUILTIN_ID


LIST_SESSIONS_QUERY = """
query ListSessions($procedureId: String!, $limit: Int) {
  listChatSessionByProcedureIdAndCreatedAt(
    procedureId: $procedureId
    sortDirection: DESC
    limit: $limit
  ) {
    items {
      id
      category
      status
      createdAt
      updatedAt
    }
  }
}
"""


LIST_MESSAGES_QUERY = """
query ListMessages($sessionId: String!, $limit: Int) {
  listChatMessageBySessionIdAndCreatedAt(
    sessionId: $sessionId
    sortDirection: ASC
    limit: $limit
  ) {
    items {
      id
      role
      messageType
      humanInteraction
      content
      metadata
      createdAt
      sessionId
      procedureId
    }
  }
}
"""


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      "--account-key",
      default=os.getenv("PLEXUS_ACCOUNT_KEY"),
      help="Account key (defaults to PLEXUS_ACCOUNT_KEY).",
  )
  parser.add_argument(
      "--procedure-id",
      default=CONSOLE_CHAT_BUILTIN_ID,
      help=f"Procedure ID (defaults to {CONSOLE_CHAT_BUILTIN_ID}).",
  )
  parser.add_argument(
      "--limit-sessions",
      type=int,
      default=5,
      help="Number of recent sessions to inspect.",
  )
  parser.add_argument(
      "--limit-messages",
      type=int,
      default=400,
      help="Per-session message fetch limit.",
  )
  parser.add_argument(
      "--session-id",
      default=None,
      help="Optional single session id to inspect.",
  )
  return parser.parse_args()


def parse_json(value: Any) -> Optional[Dict[str, Any]]:
  if isinstance(value, dict):
    return value
  if not isinstance(value, str) or not value.strip():
    return None
  try:
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None
  except Exception:
    return None


def graphql_field(payload: Any, field_name: str) -> Any:
  if not isinstance(payload, dict):
    return None
  data = payload.get("data")
  if isinstance(data, dict) and field_name in data:
    return data.get(field_name)
  return payload.get(field_name)


def parse_iso(value: Optional[str]) -> Optional[datetime]:
  if not isinstance(value, str) or not value.strip():
    return None
  try:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
  except Exception:
    return None


def delta_ms(start: Optional[str], end: Optional[str]) -> Optional[float]:
  start_dt = parse_iso(start)
  end_dt = parse_iso(end)
  if not start_dt or not end_dt:
    return None
  return round((end_dt - start_dt).total_seconds() * 1000.0, 2)


def format_ms(value: Optional[float]) -> str:
  if value is None:
    return "-"
  return f"{value:.2f} ms"


def percentile(values: List[float], pct: float) -> Optional[float]:
  if not values:
    return None
  ordered = sorted(values)
  if len(ordered) == 1:
    return ordered[0]
  rank = (len(ordered) - 1) * pct
  lower = int(rank)
  upper = min(lower + 1, len(ordered) - 1)
  fraction = rank - lower
  return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


STAGE_FIELDS = {
    "client_send_to_dispatch_queued_ms": ("client_send_started_at", "dispatch_queued_at"),
    "dispatch_queued_to_backend_exec_start_ms": ("dispatch_queued_at", "backend_execution_started_at"),
    "backend_exec_start_to_runtime_start_ms": ("backend_execution_started_at", "backend_runtime_execute_started_at"),
    "runtime_start_to_first_chunk_received_ms": ("backend_runtime_execute_started_at", "first_chunk_received_at"),
    "first_chunk_received_to_first_chunk_persisted_ms": ("first_chunk_received_at", "first_chunk_persisted_at"),
    "first_chunk_persisted_to_last_chunk_received_ms": ("first_chunk_persisted_at", "last_chunk_received_at"),
}


def latest_user_message(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
  user_messages = [
      message for message in messages
      if str(message.get("role") or "").upper() == "USER"
      and str(message.get("messageType") or "MESSAGE").upper() == "MESSAGE"
  ]
  return user_messages[-1] if user_messages else None


def first_assistant_stream_message_after(
    messages: List[Dict[str, Any]],
    created_at: Optional[str],
) -> Optional[Dict[str, Any]]:
  start = parse_iso(created_at) if created_at else None
  candidates: List[Dict[str, Any]] = []
  for message in messages:
    role = str(message.get("role") or "").upper()
    if role != "ASSISTANT":
      continue
    metadata = parse_json(message.get("metadata")) or {}
    streaming = metadata.get("streaming")
    if not isinstance(streaming, dict):
      continue
    created = parse_iso(message.get("createdAt"))
    if start and created and created < start:
      continue
    candidates.append(message)
  return candidates[0] if candidates else None


def print_session_report(session: Dict[str, Any], messages: List[Dict[str, Any]]) -> Dict[str, float]:
  session_id = str(session.get("id") or "")
  print(f"\nSession {session_id}")
  print(f"  status={session.get('status')} category={session.get('category')} updatedAt={session.get('updatedAt')}")
  metrics: Dict[str, float] = {}

  user_message = latest_user_message(messages)
  if not user_message:
    print("  No USER message found.")
    return metrics

  assistant_message = first_assistant_stream_message_after(messages, user_message.get("createdAt"))
  if not assistant_message:
    print("  No streamed ASSISTANT message found after latest USER message.")
    return metrics

  user_meta = parse_json(user_message.get("metadata")) or {}
  user_instr = user_meta.get("instrumentation") if isinstance(user_meta.get("instrumentation"), dict) else {}

  assistant_meta = parse_json(assistant_message.get("metadata")) or {}
  streaming = assistant_meta.get("streaming") if isinstance(assistant_meta.get("streaming"), dict) else {}
  timings = streaming.get("timings") if isinstance(streaming.get("timings"), dict) else {}

  client_send_started_at = user_instr.get("client_send_started_at") or user_meta.get("sent_at")
  dispatch_queued_at = timings.get("dispatch_queued_at")
  backend_execution_started_at = timings.get("backend_execution_started_at")
  backend_runtime_execute_started_at = timings.get("backend_runtime_execute_started_at")
  first_chunk_received_at = timings.get("first_chunk_received_at")
  first_chunk_persisted_at = timings.get("first_chunk_persisted_at")
  last_chunk_received_at = timings.get("last_chunk_received_at")

  raw_stage_values = {
      "client_send_started_at": client_send_started_at,
      "dispatch_queued_at": dispatch_queued_at,
      "backend_execution_started_at": backend_execution_started_at,
      "backend_runtime_execute_started_at": backend_runtime_execute_started_at,
      "first_chunk_received_at": first_chunk_received_at,
      "first_chunk_persisted_at": first_chunk_persisted_at,
      "last_chunk_received_at": last_chunk_received_at,
  }

  print("  Latency breakdown:")
  for label, (start_field, end_field) in STAGE_FIELDS.items():
    value = delta_ms(raw_stage_values.get(start_field), raw_stage_values.get(end_field))
    if value is not None:
      metrics[label] = value
    human_label = label.replace("_ms", "").replace("_", " ")
    print(f"    {human_label}: {format_ms(value)}")

  print("  Stream cadence:")
  print(f"    chunk_count: {timings.get('chunk_count')}")
  print(f"    inter_chunk_average_ms: {timings.get('inter_chunk_average_ms')}")
  print(f"    inter_chunk_max_ms: {timings.get('inter_chunk_max_ms')}")
  if isinstance(timings.get("persisted_inter_update_average_ms"), (int, float)):
    metrics["persisted_inter_update_average_ms"] = float(timings["persisted_inter_update_average_ms"])
  if isinstance(timings.get("persisted_inter_update_max_ms"), (int, float)):
    metrics["persisted_inter_update_max_ms"] = float(timings["persisted_inter_update_max_ms"])
  print(f"    persisted_update_count: {timings.get('persisted_update_count')}")
  print(f"    persisted_inter_update_average_ms: {timings.get('persisted_inter_update_average_ms')}")
  print(f"    persisted_inter_update_max_ms: {timings.get('persisted_inter_update_max_ms')}")

  dispatch_client_timing = timings.get("dispatch_client_timing")
  if isinstance(dispatch_client_timing, dict):
    dispatch_start = dispatch_client_timing.get("client_dispatch_request_started_at")
    dispatch_end = dispatch_client_timing.get("client_dispatch_request_completed_at")
    task_create_start = dispatch_client_timing.get("client_task_create_started_at")
    task_create_end = dispatch_client_timing.get("client_task_create_completed_at")
    print("  Frontend dispatch timings:")
    print(f"    task_create_duration: {format_ms(delta_ms(task_create_start, task_create_end))}")
    print(f"    dispatch_request_duration: {format_ms(delta_ms(dispatch_start, dispatch_end))}")
    print(f"    dispatch_request_accepted: {dispatch_client_timing.get('client_dispatch_request_accepted')}")
    worker_markers = {
        "queue_enqueued_at": dispatch_client_timing.get("queue_enqueued_at"),
        "worker_dequeued_at": dispatch_client_timing.get("worker_dequeued_at"),
        "worker_init_done_at": dispatch_client_timing.get("worker_init_done_at"),
        "runtime_init_done_at": dispatch_client_timing.get("runtime_init_done_at"),
    }
    print("  Worker timing markers:")
    for key, value in worker_markers.items():
      print(f"    {key}: {value if value else '-'}")

  return metrics


def print_percentile_summary(session_metrics: List[Dict[str, float]]) -> None:
  if not session_metrics:
    print("\nNo session metrics captured for percentile summary.")
    return

  buckets: Dict[str, List[float]] = defaultdict(list)
  for metric_map in session_metrics:
    for key, value in metric_map.items():
      if isinstance(value, (int, float)):
        buckets[key].append(float(value))

  if not buckets:
    print("\nNo numeric latency metrics available for percentile summary.")
    return

  print("\nPercentile summary:")
  dominant_stage = None
  dominant_p50 = -1.0

  ordered_metric_names = [
      "client_send_to_dispatch_queued_ms",
      "dispatch_queued_to_backend_exec_start_ms",
      "backend_exec_start_to_runtime_start_ms",
      "runtime_start_to_first_chunk_received_ms",
      "first_chunk_received_to_first_chunk_persisted_ms",
      "first_chunk_persisted_to_last_chunk_received_ms",
      "persisted_inter_update_average_ms",
      "persisted_inter_update_max_ms",
  ]

  for metric_name in ordered_metric_names:
    values = buckets.get(metric_name, [])
    if not values:
      continue
    p50 = percentile(values, 0.5)
    p90 = percentile(values, 0.9)
    p95 = percentile(values, 0.95)
    label = metric_name.replace("_ms", "").replace("_", " ")
    print(
        f"  {label}: count={len(values)} p50={format_ms(p50)} p90={format_ms(p90)} p95={format_ms(p95)}"
    )
    if p50 is not None and p50 > dominant_p50 and metric_name.endswith("_ms"):
      dominant_p50 = p50
      dominant_stage = metric_name

  if dominant_stage:
    label = dominant_stage.replace("_ms", "").replace("_", " ")
    print(f"\nDominant latency phase (highest p50): {label} ({format_ms(dominant_p50)})")


def main() -> int:
  args = parse_args()
  if not args.account_key:
    print("Missing account key. Set PLEXUS_ACCOUNT_KEY or pass --account-key.", file=sys.stderr)
    return 1

  client = PlexusDashboardClient(context=ClientContext(account_key=args.account_key))

  if args.session_id:
    sessions = [{"id": args.session_id, "category": "Console", "status": "UNKNOWN", "updatedAt": None}]
  else:
    result = client.execute(
        LIST_SESSIONS_QUERY,
        {
            "procedureId": args.procedure_id,
            "limit": max(1, args.limit_sessions),
        },
    )
    session_payload = graphql_field(result, "listChatSessionByProcedureIdAndCreatedAt")
    sessions = (session_payload.get("items", []) if isinstance(session_payload, dict) else []) or []

  if not sessions:
    print("No sessions found.")
    return 0

  print(f"Console streaming latency report ({datetime.now(timezone.utc).isoformat()})")
  print(f"procedure_id={args.procedure_id}")
  collected_metrics: List[Dict[str, float]] = []
  for session in sessions:
    session_id = session.get("id")
    if not session_id:
      continue
    message_result = client.execute(
        LIST_MESSAGES_QUERY,
        {"sessionId": session_id, "limit": max(1, args.limit_messages)},
    )
    message_payload = graphql_field(message_result, "listChatMessageBySessionIdAndCreatedAt")
    messages = (message_payload.get("items", []) if isinstance(message_payload, dict) else []) or []
    metrics = print_session_report(session, messages)
    if metrics:
      collected_metrics.append(metrics)

  print_percentile_summary(collected_metrics)

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
