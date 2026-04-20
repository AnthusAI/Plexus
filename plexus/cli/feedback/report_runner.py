"""
Shared helpers for running core feedback report blocks directly.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.cli.shared.client_utils import create_client
from plexus.reports.service import run_block_cached


def build_window_config(
    *,
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build normalized report window config with strict mutual-exclusion rules.
    """
    window_config: Dict[str, Any] = {}
    normalized_start = start_date.strip() if isinstance(start_date, str) else start_date
    normalized_end = end_date.strip() if isinstance(end_date, str) else end_date

    if (normalized_start and not normalized_end) or (normalized_end and not normalized_start):
        raise ValueError("Both 'start_date' and 'end_date' are required when specifying explicit date windows.")
    if days is not None and normalized_start and normalized_end:
        raise ValueError("Use either 'days' or 'start_date'+'end_date', not both.")
    if days is not None and days <= 0:
        raise ValueError("'days' must be a positive integer.")

    if normalized_start and normalized_end:
        window_config["start_date"] = normalized_start
        window_config["end_date"] = normalized_end
    elif days is not None:
        window_config["days"] = int(days)

    return window_config


def run_feedback_report_block(
    *,
    block_class: str,
    scorecard: str,
    score: Optional[str] = None,
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    extra_config: Optional[Dict[str, Any]] = None,
    account_identifier: Optional[str] = None,
    cache_key: Optional[str] = None,
    ttl_hours: float = 24.0,
    fresh: bool = False,
    background: bool = False,
) -> Dict[str, Any]:
    """
    Execute a report block with a feedback-specific config contract.
    """
    if not scorecard or not str(scorecard).strip():
        raise ValueError("'scorecard' is required.")
    if ttl_hours <= 0:
        raise ValueError("'ttl_hours' must be > 0.")

    client = create_client()
    account_id = resolve_account_id_for_command(client, account_identifier)

    block_config: Dict[str, Any] = {"scorecard": str(scorecard).strip()}
    if score and str(score).strip():
        block_config["score"] = str(score).strip()

    block_config.update(
        build_window_config(days=days, start_date=start_date, end_date=end_date)
    )

    if extra_config:
        for key, value in extra_config.items():
            if value is not None:
                block_config[key] = value

    output_data, log_output, was_cached = run_block_cached(
        block_class=block_class,
        block_config=block_config,
        account_id=account_id,
        client=client,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        background=background,
    )

    if isinstance(output_data, dict) and output_data.get("status") in {"dispatched", "already_dispatched"}:
        return {
            "status": output_data["status"],
            "cache_key": output_data.get("cache_key"),
            "task_id": output_data.get("task_id"),
            "block_class": block_class,
            "block_config": block_config,
            "cached": False,
        }

    if output_data is None:
        return {
            "status": "failed",
            "error": log_output or f"{block_class} execution failed.",
            "block_class": block_class,
            "block_config": block_config,
            "cached": False,
        }

    result: Dict[str, Any] = {
        "status": "success",
        "output": output_data,
        "block_class": block_class,
        "block_config": block_config,
        "cached": bool(was_cached),
    }
    if log_output:
        result["log"] = log_output
    return result


def summarize_timeline_feedback_volume(timeline_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive feedback-volume views from FeedbackAlignmentTimeline output.
    """
    overall = timeline_output.get("overall") or {}
    points = overall.get("points") or []

    series = [
        {
            "bucket_index": point.get("bucket_index"),
            "label": point.get("label"),
            "start": point.get("start"),
            "end": point.get("end"),
            "feedback_item_count": point.get("item_count", 0),
            "agreements": point.get("agreements", 0),
            "mismatches": point.get("mismatches", 0),
        }
        for point in points
    ]
    total_feedback = sum(int(point.get("feedback_item_count", 0)) for point in series)
    buckets_with_feedback = sum(
        1 for point in series if int(point.get("feedback_item_count", 0)) > 0
    )

    return {
        "report_type": "feedback_volume",
        "scorecard_id": timeline_output.get("scorecard_id"),
        "scorecard_name": timeline_output.get("scorecard_name"),
        "mode": timeline_output.get("mode"),
        "date_range": timeline_output.get("date_range"),
        "bucket_policy": timeline_output.get("bucket_policy"),
        "summary": {
            "total_feedback_items": total_feedback,
            "bucket_count": len(series),
            "buckets_with_feedback": buckets_with_feedback,
        },
        "series": series,
    }
