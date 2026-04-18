"""
Direct feedback report commands (no report template required).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import click
import yaml

from plexus.cli.feedback.report_runner import (
    run_feedback_report_block,
    summarize_timeline_feedback_volume,
)
from plexus.cli.shared.console import console


def _print_result(
    *,
    title: str,
    result: Dict[str, Any],
    output_format: str,
    include_log: bool,
) -> None:
    if result.get("status") in {"dispatched", "already_dispatched"}:
        console.print(
            json.dumps(
                {
                    "status": result["status"],
                    "cache_key": result.get("cache_key"),
                    "message": f"{title} dispatched to background execution.",
                },
                indent=2,
            )
        )
        return

    if output_format == "yaml":
        payload = result.copy()
        if not include_log:
            payload.pop("log", None)
        console.print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    else:
        payload = result.copy()
        if not include_log:
            payload.pop("log", None)
        console.print(json.dumps(payload, indent=2, default=str))


def _coerce_optional_int(value: Optional[int], name: str) -> Optional[int]:
    if value is None:
        return None
    try:
        int_value = int(value)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(f"'{name}' must be an integer.") from exc
    return int_value


@click.group(name="report")
def report() -> None:
    """Run core feedback reports directly from code-defined block classes."""


@report.command(name="correction-rate")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Dispatch in background and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def correction_rate(
    scorecard: str,
    score: Optional[str],
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fresh: bool,
    background: bool,
    account_identifier: Optional[str],
    output_format: str,
    include_log: bool,
) -> None:
    """Run the CorrectionRate report block."""
    result = run_feedback_report_block(
        block_class="CorrectionRate",
        scorecard=scorecard,
        score=score,
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
        account_identifier=account_identifier,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        background=background,
    )
    _print_result(title="CorrectionRate", result=result, output_format=output_format, include_log=include_log)


@report.command(name="acceptance-rate")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option(
    "--include-item-acceptance-rate",
    is_flag=True,
    help="Include item-level acceptance metrics (default: score-result-only).",
)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Dispatch in background and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def acceptance_rate(
    scorecard: str,
    score: Optional[str],
    include_item_acceptance_rate: bool,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fresh: bool,
    background: bool,
    account_identifier: Optional[str],
    output_format: str,
    include_log: bool,
) -> None:
    """Run the AcceptanceRate report block."""
    result = run_feedback_report_block(
        block_class="AcceptanceRate",
        scorecard=scorecard,
        score=score,
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
        extra_config={"include_item_acceptance_rate": include_item_acceptance_rate},
        account_identifier=account_identifier,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        background=background,
    )
    _print_result(title="AcceptanceRate", result=result, output_format=output_format, include_log=include_log)


@report.command(name="recent")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option("--max-feedback-items", type=int, default=500, show_default=True)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Dispatch in background and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def recent(
    scorecard: str,
    score: Optional[str],
    max_feedback_items: int,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fresh: bool,
    background: bool,
    account_identifier: Optional[str],
    output_format: str,
    include_log: bool,
) -> None:
    """Run the RecentFeedback report block."""
    result = run_feedback_report_block(
        block_class="RecentFeedback",
        scorecard=scorecard,
        score=score,
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
        account_identifier=account_identifier,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        background=background,
        extra_config={"max_feedback_items": max_feedback_items},
    )
    _print_result(title="RecentFeedback", result=result, output_format=output_format, include_log=include_log)


@report.command(name="analysis")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Dispatch in background and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def analysis(
    scorecard: str,
    score: Optional[str],
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fresh: bool,
    background: bool,
    account_identifier: Optional[str],
    output_format: str,
    include_log: bool,
) -> None:
    """Run the FeedbackAnalysis report block directly."""
    result = run_feedback_report_block(
        block_class="FeedbackAnalysis",
        scorecard=scorecard,
        score=score,
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
        account_identifier=account_identifier,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        background=background,
    )
    _print_result(title="FeedbackAnalysis", result=result, output_format=output_format, include_log=include_log)


@report.command(name="contradictions")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=True, help="Score identifier (id or external id).")
@click.option(
    "--mode",
    type=click.Choice(["contradictions", "aligned"]),
    default="contradictions",
    show_default=True,
    help="Contradiction-focused or aligned-item-focused run mode.",
)
@click.option("--max-feedback-items", type=int, default=400, show_default=True)
@click.option("--num-topics", type=int, default=8, show_default=True)
@click.option("--max-concurrent", type=int, default=20, show_default=True)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Dispatch in background and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def contradictions(
    scorecard: str,
    score: str,
    mode: str,
    max_feedback_items: int,
    num_topics: int,
    max_concurrent: int,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fresh: bool,
    background: bool,
    account_identifier: Optional[str],
    output_format: str,
    include_log: bool,
) -> None:
    """Run the FeedbackContradictions report block."""
    result = run_feedback_report_block(
        block_class="FeedbackContradictions",
        scorecard=scorecard,
        score=score,
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
        account_identifier=account_identifier,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        background=background,
        extra_config={
            "mode": mode,
            "max_feedback_items": max_feedback_items,
            "num_topics": num_topics,
            "max_concurrent": max_concurrent,
        },
    )
    _print_result(title="FeedbackContradictions", result=result, output_format=output_format, include_log=include_log)


@report.command(name="timeline")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option("--bucket-type", default="trailing_7d", show_default=True)
@click.option("--bucket-count", type=int, default=12, show_default=True)
@click.option("--timezone", "timezone_name", default="UTC", show_default=True)
@click.option("--week-start", type=click.Choice(["monday", "sunday"]), default="monday", show_default=True)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Dispatch in background and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def timeline(
    scorecard: str,
    score: Optional[str],
    bucket_type: str,
    bucket_count: int,
    timezone_name: str,
    week_start: str,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fresh: bool,
    background: bool,
    account_identifier: Optional[str],
    output_format: str,
    include_log: bool,
) -> None:
    """Run the FeedbackAlignmentTimeline report block directly."""
    result = run_feedback_report_block(
        block_class="FeedbackAlignmentTimeline",
        scorecard=scorecard,
        score=score,
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
        account_identifier=account_identifier,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        background=background,
        extra_config={
            "bucket_type": bucket_type,
            "bucket_count": bucket_count,
            "timezone": timezone_name,
            "week_start": week_start,
        },
    )
    _print_result(title="FeedbackAlignmentTimeline", result=result, output_format=output_format, include_log=include_log)


@report.command(name="volume")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option("--bucket-type", default="trailing_7d", show_default=True)
@click.option("--bucket-count", type=int, default=12, show_default=True)
@click.option("--timezone", "timezone_name", default="UTC", show_default=True)
@click.option("--week-start", type=click.Choice(["monday", "sunday"]), default="monday", show_default=True)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Dispatch in background and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def volume(
    scorecard: str,
    score: Optional[str],
    bucket_type: str,
    bucket_count: int,
    timezone_name: str,
    week_start: str,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fresh: bool,
    background: bool,
    account_identifier: Optional[str],
    output_format: str,
    include_log: bool,
) -> None:
    """Run timeline and return a feedback-volume-focused payload."""
    result = run_feedback_report_block(
        block_class="FeedbackAlignmentTimeline",
        scorecard=scorecard,
        score=score,
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
        account_identifier=account_identifier,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        background=background,
        extra_config={
            "bucket_type": bucket_type,
            "bucket_count": bucket_count,
            "timezone": timezone_name,
            "week_start": week_start,
        },
    )

    if result.get("status") == "success":
        result = {
            **result,
            "output": summarize_timeline_feedback_volume(result["output"]),
        }

    _print_result(title="FeedbackVolume", result=result, output_format=output_format, include_log=include_log)
