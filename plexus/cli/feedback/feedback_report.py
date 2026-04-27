"""
Direct feedback report commands (no report template required).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import click
import yaml

from plexus.cli.feedback.report_runner import (
    build_window_config,
    run_feedback_report_block,
)
from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.memoized_resolvers import (
    memoized_resolve_score_identifier,
    memoized_resolve_scorecard_identifier,
)
from plexus.cli.shared.console import console
from plexus.reports.parameter_utils import enrich_parameters_with_names
from plexus.reports.service import (
    decode_programmatic_run_payload,
    run_programmatic_block_and_persist,
    run_programmatic_report_and_persist,
)


def _print_result(
    *,
    title: str,
    result: Dict[str, Any],
    output_format: str,
    include_log: bool,
) -> None:
    if result.get("status") in {"dispatched", "already_dispatched"}:
        click.echo(
            json.dumps(
                {
                    "status": result["status"],
                    "cache_key": result.get("cache_key"),
                    "task_id": result.get("task_id"),
                    "message": (
                        f"{title} queued as a durable task for dispatcher execution. "
                        "Run `plexus command dispatcher` to process it."
                    ),
                },
                indent=2,
            )
        )
        return

    if output_format == "yaml":
        payload = result.copy()
        if not include_log:
            payload.pop("log", None)
        click.echo(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    else:
        payload = result.copy()
        if not include_log:
            payload.pop("log", None)
        # Use plain stdout writes for machine-readable output; Rich may wrap long strings.
        click.echo(json.dumps(payload, indent=2, default=str))


def _coerce_optional_int(value: Optional[int], name: str) -> Optional[int]:
    if value is None:
        return None
    try:
        int_value = int(value)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(f"'{name}' must be an integer.") from exc
    return int_value


def _window_label(days: Optional[int], start_date: Optional[str], end_date: Optional[str]) -> str:
    if start_date and end_date:
        return f"{start_date} to {end_date}"
    if days is not None:
        return f"Last {days} days"
    return "Default window"


def _score_has_nonempty_champion_guidelines(
    *,
    client: Any,
    scorecard_identifier: str,
    score_identifier: str,
) -> Tuple[bool, Optional[str]]:
    scorecard_id = memoized_resolve_scorecard_identifier(client, str(scorecard_identifier).strip())
    if not scorecard_id:
        return False, f"Skipped Feedback Contradictions: could not resolve scorecard '{scorecard_identifier}'."

    score_id = memoized_resolve_score_identifier(client, scorecard_id, str(score_identifier).strip())
    if not score_id:
        return False, f"Skipped Feedback Contradictions: could not resolve score '{score_identifier}'."

    try:
        score_result = client.execute(
            """
            query GetScoreChampionVersion($id: ID!) {
                getScore(id: $id) {
                    championVersionId
                }
            }
            """,
            {"id": score_id},
        )
        champion_version_id = (
            (score_result or {})
            .get("getScore", {})
            .get("championVersionId")
        )
        if not champion_version_id:
            return False, "Skipped Feedback Contradictions: score has no champion version."

        version_result = client.execute(
            """
            query GetScoreVersionGuidelines($id: ID!) {
                getScoreVersion(id: $id) {
                    guidelines
                }
            }
            """,
            {"id": champion_version_id},
        )
        guidelines = str(
            ((version_result or {}).get("getScoreVersion", {}) or {}).get("guidelines") or ""
        ).strip()
        if not guidelines:
            return False, "Skipped Feedback Contradictions: champion version guidelines are empty."

        return True, None
    except Exception as exc:
        return False, f"Skipped Feedback Contradictions: failed to resolve champion guidelines ({exc})."


@click.group(name="report")
def report() -> None:
    """Run core feedback reports directly from code-defined block classes."""


@report.command(name="run-programmatic-block", hidden=True)
@click.option("--payload-base64", required=True, help="Encoded durable programmatic report payload.")
def run_programmatic_block(payload_base64: str) -> None:
    """Internal dispatcher entrypoint for durable programmatic report blocks."""
    payload = decode_programmatic_run_payload(payload_base64)
    client = create_client()
    if not client:
        raise click.ClickException("Could not create dashboard client.")

    output_data, log_output = run_programmatic_block_and_persist(
        cache_key=str(payload.get("cache_key") or "").strip(),
        block_class=str(payload.get("block_class") or "").strip(),
        block_config=payload.get("block_config") or {},
        account_id=str(payload.get("account_id") or "").strip(),
        client=client,
        persist_required=True,
    )
    if output_data is None:
        raise click.ClickException(log_output or "Programmatic report block execution failed.")

    console.print(
        json.dumps(
            {
                "status": "success",
                "cache_key": payload.get("cache_key"),
                "block_class": payload.get("block_class"),
            },
            indent=2,
        )
    )


@report.command(name="correction-rate")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option(
    "--max-items",
    type=int,
    default=0,
    show_default=True,
    help="Maximum item rows in output. Use 0 for no cap.",
)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fetch-shard-days", type=int, default=30, show_default=True, help="Shard size in days for score-result window fetch.")
@click.option("--fetch-shard-concurrency", type=int, default=4, show_default=True, help="Max concurrent score-result shards.")
@click.option("--fetch-max-inflight-process", type=int, default=8, show_default=True, help="Max in-flight page processing tasks per shard.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Queue as a durable task for dispatcher execution and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def correction_rate(
    scorecard: str,
    score: Optional[str],
    max_items: int,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fetch_shard_days: int,
    fetch_shard_concurrency: int,
    fetch_max_inflight_process: int,
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
        extra_config={"max_items": max_items},
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
@click.option(
    "--max-items",
    type=int,
    default=0,
    show_default=True,
    help="Maximum item rows in output. Use 0 for no cap.",
)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fetch-shard-days", type=int, default=30, show_default=True, help="Shard size in days for score-result window fetch.")
@click.option("--fetch-shard-concurrency", type=int, default=4, show_default=True, help="Max concurrent score-result shards.")
@click.option("--fetch-max-inflight-process", type=int, default=8, show_default=True, help="Max in-flight page processing tasks per shard.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Queue as a durable task for dispatcher execution and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def acceptance_rate(
    scorecard: str,
    score: Optional[str],
    include_item_acceptance_rate: bool,
    max_items: int,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fetch_shard_days: int,
    fetch_shard_concurrency: int,
    fetch_max_inflight_process: int,
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
        extra_config={
            "include_item_acceptance_rate": include_item_acceptance_rate,
            "max_items": max_items,
            "fetch_shard_days": fetch_shard_days,
            "fetch_shard_concurrency": fetch_shard_concurrency,
            "fetch_max_inflight_process": fetch_max_inflight_process,
        },
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
@click.option("--background", is_flag=True, help="Queue as a durable task for dispatcher execution and return immediately.")
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


@report.command(name="alignment")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option(
    "--order-scores",
    type=click.Choice(["best_to_worst", "worst_to_best", "none"]),
    default="best_to_worst",
    show_default=True,
    help="Scorecard-level only: order per-score results by AC1/accuracy.",
)
@click.option(
    "--memory-analysis",
    is_flag=True,
    help="Enable optional LLM-backed topic clustering for mismatch comments (slow/expensive).",
)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Queue as a durable task for dispatcher execution and return immediately.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def alignment(
    scorecard: str,
    score: Optional[str],
    order_scores: str,
    memory_analysis: bool,
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
    """Run the FeedbackAlignment report block directly."""
    result = run_feedback_report_block(
        block_class="FeedbackAlignment",
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
        extra_config={"order_scores": order_scores, "memory_analysis": bool(memory_analysis)},
    )
    _print_result(title="FeedbackAlignment", result=result, output_format=output_format, include_log=include_log)


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
@click.option("--background", is_flag=True, help="Queue as a durable task for dispatcher execution and return immediately.")
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
@click.option(
    "--show-bucket-details/--chart-only",
    default=False,
    show_default=True,
    help="Show or hide per-bucket details below the timeline chart.",
)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Queue as a durable task for dispatcher execution and return immediately.")
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
    show_bucket_details: bool,
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
            "show_bucket_details": show_bucket_details,
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
@click.option(
    "--show-bucket-details/--chart-only",
    default=False,
    show_default=True,
    help="Show or hide per-bucket metrics details below the chart.",
)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--background", is_flag=True, help="Queue as a durable task for dispatcher execution and return immediately.")
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
    show_bucket_details: bool,
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
    """Run the FeedbackVolumeTimeline report block."""
    result = run_feedback_report_block(
        block_class="FeedbackVolumeTimeline",
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
            "show_bucket_details": show_bucket_details,
        },
    )

    _print_result(title="FeedbackVolumeTimeline", result=result, output_format=output_format, include_log=include_log)


@report.command(name="acceptance-rate-timeline")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=False, help="Optional score identifier (id or external id).")
@click.option("--bucket-type", default="trailing_7d", show_default=True)
@click.option("--bucket-count", type=int, default=12, show_default=True)
@click.option(
    "--show-bucket-details/--chart-only",
    default=False,
    show_default=True,
    help="Show or hide per-bucket metrics details below the chart.",
)
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--cache-key", required=False, help="Deterministic cache key for repeated runs.")
@click.option("--ttl-hours", type=float, default=24.0, show_default=True, help="Cache TTL in hours.")
@click.option("--fetch-shard-days", type=int, default=30, show_default=True, help="Shard size in days for score-result window fetch.")
@click.option("--fetch-shard-concurrency", type=int, default=4, show_default=True, help="Max concurrent score-result shards.")
@click.option("--fetch-max-inflight-process", type=int, default=8, show_default=True, help="Max in-flight page processing tasks per shard.")
@click.option("--fresh", is_flag=True, help="Ignore cached results and rerun.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
@click.option("--include-log", is_flag=True, help="Include report block log output.")
def acceptance_rate_timeline(
    scorecard: str,
    score: Optional[str],
    bucket_type: str,
    bucket_count: int,
    show_bucket_details: bool,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    cache_key: Optional[str],
    ttl_hours: float,
    fetch_shard_days: int,
    fetch_shard_concurrency: int,
    fetch_max_inflight_process: int,
    fresh: bool,
    account_identifier: Optional[str],
    output_format: str,
    include_log: bool,
) -> None:
    """Run the AcceptanceRateTimeline report block (score-result acceptance over time)."""
    result = run_feedback_report_block(
        block_class="AcceptanceRateTimeline",
        scorecard=scorecard,
        score=score,
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
        account_identifier=account_identifier,
        cache_key=cache_key,
        ttl_hours=ttl_hours,
        fresh=fresh,
        extra_config={
            "bucket_type": bucket_type,
            "bucket_count": bucket_count,
            "show_bucket_details": show_bucket_details,
            "fetch_shard_days": fetch_shard_days,
            "fetch_shard_concurrency": fetch_shard_concurrency,
            "fetch_max_inflight_process": fetch_max_inflight_process,
        },
    )
    _print_result(title="AcceptanceRateTimeline", result=result, output_format=output_format, include_log=include_log)


@report.command(name="overview")
@click.option("--scorecard", required=True, help="Scorecard identifier (id, external id, or key).")
@click.option("--score", required=True, help="Score identifier (id or external id).")
@click.option("--days", type=int, required=False, help="Trailing window in days.")
@click.option("--start-date", required=False, help="Inclusive start date in YYYY-MM-DD.")
@click.option("--end-date", required=False, help="Inclusive end date in YYYY-MM-DD.")
@click.option("--bucket-type", default="trailing_7d", show_default=True)
@click.option("--timezone", "timezone_name", default="UTC", show_default=True)
@click.option("--week-start", type=click.Choice(["monday", "sunday"]), default="monday", show_default=True)
@click.option(
    "--show-bucket-details/--chart-only",
    default=False,
    show_default=True,
    help="Show or hide per-bucket details for the timeline blocks.",
)
@click.option(
    "--mode",
    type=click.Choice(["contradictions", "aligned"]),
    default="contradictions",
    show_default=True,
    help="Feedback contradictions block mode.",
)
@click.option("--max-feedback-items", type=int, default=400, show_default=True)
@click.option("--num-topics", type=int, default=8, show_default=True)
@click.option("--max-concurrent", type=int, default=20, show_default=True)
@click.option("--name", "report_name", required=False, help="Optional report name override.")
@click.option("--account", "account_identifier", default=None, help="Optional account key or id.")
@click.option("--format", "output_format", type=click.Choice(["json", "yaml"]), default="json", show_default=True)
def overview(
    scorecard: str,
    score: str,
    days: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    bucket_type: str,
    timezone_name: str,
    week_start: str,
    show_bucket_details: bool,
    mode: str,
    max_feedback_items: int,
    num_topics: int,
    max_concurrent: int,
    report_name: Optional[str],
    account_identifier: Optional[str],
    output_format: str,
) -> None:
    """
    Generate a 3-block score overview report:
    FeedbackVolumeTimeline, FeedbackAlignment, and FeedbackContradictions
    (when champion guidelines are present).
    """
    client = create_client()
    if not client:
        raise click.ClickException("Could not create dashboard client.")
    account_id = resolve_account_id_for_command(client, account_identifier)

    scorecard_input = str(scorecard).strip()
    score_input = str(score).strip()
    resolved_scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard_input)
    if not resolved_scorecard_id:
        raise click.ClickException(f"Could not resolve scorecard '{scorecard_input}'.")
    resolved_score_id = memoized_resolve_score_identifier(client, resolved_scorecard_id, score_input)
    if not resolved_score_id:
        raise click.ClickException(
            f"Could not resolve score '{score_input}' in scorecard '{scorecard_input}'."
        )

    window_config = build_window_config(
        days=_coerce_optional_int(days, "days"),
        start_date=start_date,
        end_date=end_date,
    )
    shared_scope: Dict[str, Any] = {
        "scorecard": resolved_scorecard_id,
        "score": resolved_score_id,
        **window_config,
    }
    named_scope = enrich_parameters_with_names(
        [
            {"name": "scorecard", "type": "scorecard_select"},
            {"name": "score", "type": "score_select", "depends_on": "scorecard"},
        ],
        shared_scope,
        client,
    )

    alignment_config: Dict[str, Any] = {**shared_scope}
    volume_timeline_config: Dict[str, Any] = {
        **shared_scope,
        "bucket_type": bucket_type,
        "timezone": timezone_name,
        "week_start": week_start,
        "show_bucket_details": show_bucket_details,
    }
    contradictions_config: Dict[str, Any] = {
        **shared_scope,
        "mode": mode,
        "max_feedback_items": max_feedback_items,
        "num_topics": num_topics,
        "max_concurrent": max_concurrent,
    }
    include_contradictions, contradictions_skip_reason = _score_has_nonempty_champion_guidelines(
        client=client,
        scorecard_identifier=resolved_scorecard_id,
        score_identifier=resolved_score_id,
    )

    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    scorecard_title = str(named_scope.get("scorecard_name") or shared_scope["scorecard"]).strip()
    score_title = str(named_scope.get("score_name") or shared_scope["score"]).strip()
    display_title = f"{scorecard_title} - {score_title} - Feedback Overview"
    generated_name = (
        f"{display_title} | {_window_label(days, start_date, end_date)} | {timestamp_utc}"
    )
    final_report_name = str(report_name).strip() if report_name and str(report_name).strip() else generated_name

    block_definitions: list[dict[str, Any]] = [
        {
            "class_name": "FeedbackVolumeTimeline",
            "block_name": "Feedback Volume Timeline",
            "config": volume_timeline_config,
        },
        {
            "class_name": "FeedbackAlignment",
            "block_name": "Feedback Alignment",
            "config": alignment_config,
        },
    ]
    if include_contradictions:
        block_definitions.append(
            {
                "class_name": "FeedbackContradictions",
                "block_name": "Feedback Contradictions",
                "config": contradictions_config,
            }
        )

    report_description = (
        "Combined feedback overview with volume over time and alignment metrics "
        "for the selected scope."
    )
    if include_contradictions:
        report_description += " Includes contradiction analysis."
    else:
        report_description += " Feedback contradictions were skipped because champion guidelines are missing."

    report_id, first_error = run_programmatic_report_and_persist(
        report_name=final_report_name,
        block_definitions=block_definitions,
        account_id=account_id,
        client=client,
        report_parameters={
            **named_scope,
            "bucket_type": bucket_type,
            "timezone": timezone_name,
            "week_start": week_start,
            "show_bucket_details": show_bucket_details,
            "contradictions_mode": mode,
            "max_feedback_items": max_feedback_items,
            "num_topics": num_topics,
            "max_concurrent": max_concurrent,
            "include_contradictions": include_contradictions,
            "contradictions_skipped_reason": contradictions_skip_reason if not include_contradictions else None,
        },
        display_title=display_title,
        display_subtitle=_window_label(days, start_date, end_date),
        display_description=report_description,
    )

    if not report_id:
        raise click.ClickException(first_error or "Overview report generation failed.")

    dashboard_url = client.generate_deep_link("/lab/reports/{reportId}", {"reportId": report_id})
    payload = {
        "status": "success" if not first_error else "partial_success",
        "report_id": report_id,
        "report_name": final_report_name,
        "dashboard_url": dashboard_url,
        "blocks": [block["class_name"] for block in block_definitions],
        "shared_scope": shared_scope,
        "timeline": {
            "bucket_type": bucket_type,
            "timezone": timezone_name,
            "week_start": week_start,
            "show_bucket_details": show_bucket_details,
        },
    }
    if not include_contradictions and contradictions_skip_reason:
        payload["warnings"] = [contradictions_skip_reason]
    if first_error:
        payload["error"] = first_error

    if output_format == "yaml":
        console.print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    else:
        console.print(json.dumps(payload, indent=2, default=str))
