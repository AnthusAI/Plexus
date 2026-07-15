"""
Shared helpers for running core feedback report blocks directly.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.cli.shared.client_utils import create_client
from plexus.reports.service import (
    _instantiate_and_run_block,
    persist_precomputed_report_blocks,
    run_block_cached,
)


FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS = "FeedbackAlignmentTimeline"
DEFAULT_FEEDBACK_ALIGNMENT_ROLLING_MIN_ITEMS = 100


def feedback_alignment_methodology_lines(rolling_min_items: Optional[int] = None) -> list[str]:
    minimum = rolling_min_items or DEFAULT_FEEDBACK_ALIGNMENT_ROLLING_MIN_ITEMS
    return [
        "Each chart measures how often stored production score answers agreed with the final human correction recorded in feedback.",
        "The original score answer is the value captured on the feedback record; the human answer is the final corrected value after review.",
        "Buckets are based on when the feedback was edited, not when the call happened and not when the score version was released.",
        (
            f"For each bucket, the point first uses feedback edited inside that bucket. "
            f"If that bucket has fewer than {minimum} feedback records, older feedback is added "
            f"until the sample reaches {minimum} records or no earlier feedback exists."
        ),
        "Feedback items marked invalid are excluded before bucketing and rolling-window sampling.",
        "Lookback records are only used to stabilize sparse buckets; each point still ends at that bucket's end date.",
        "This is not a replay or backtest of historical champion versions. It uses the answers already stored on feedback records.",
    ]


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


def _timeline_report_display_name(output_data: Dict[str, Any], block_config: Dict[str, Any]) -> str:
    scorecard_name = (
        output_data.get("scorecard_name")
        or block_config.get("scorecard")
        or "Scorecard"
    )
    timestamp = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    return f"{scorecard_name} - Feedback Alignment Timelines - {timestamp}"


def _timeline_report_subtitle(output_data: Dict[str, Any]) -> Optional[str]:
    date_range = output_data.get("date_range")
    if not isinstance(date_range, dict):
        return None
    start = date_range.get("start")
    end = date_range.get("end")
    if not start or not end:
        return None
    bucket_type = (output_data.get("bucket_policy") or {}).get("bucket_type")
    rolling_min = (output_data.get("sample_policy") or {}).get("rolling_min_items")
    parts = [f"{start} through {end}"]
    if bucket_type:
        parts.append(f"{bucket_type} buckets")
    if rolling_min:
        parts.append(f"rolling minimum sample of {rolling_min}")
    return ", ".join(parts)


def _single_timeline_block_output(
    *,
    source_output: Dict[str, Any],
    series: Dict[str, Any],
    title: str,
    description: str,
    mode: str,
    show_methodology: bool,
) -> Dict[str, Any]:
    split_output = deepcopy(source_output)
    split_output["block_title"] = title
    split_output["block_description"] = description
    split_output["mode"] = mode
    split_output["show_methodology"] = show_methodology
    split_output["show_bucket_details"] = False
    split_output["overall"] = deepcopy(series)
    split_output["scores"] = []
    split_output.pop("message", None)
    return split_output


def build_feedback_alignment_timeline_report_blocks(
    output_data: Dict[str, Any],
    block_config: Dict[str, Any],
    log_output: Optional[str] = None,
) -> list[Dict[str, Any]]:
    """
    Split a multi-score FeedbackAlignmentTimeline output into top-level blocks.
    """
    if not isinstance(output_data, dict):
        raise ValueError("Feedback alignment timeline output must be an object.")

    blocks: list[Dict[str, Any]] = []
    overall = output_data.get("overall")
    if isinstance(overall, dict):
        blocks.append(
            {
                "class_name": FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS,
                "block_name": "Overall Alignment Timeline",
                "config": {**block_config, "show_bucket_details": False, "_timeline_series": "overall"},
                "output": _single_timeline_block_output(
                    source_output=output_data,
                    series=overall,
                    title="Overall Alignment Timeline",
                    description="Overall alignment recomputed from the included score set.",
                    mode="all_scores",
                    show_methodology=True,
                ),
                "log": log_output,
            }
        )

    for score in output_data.get("scores") or []:
        if not isinstance(score, dict):
            continue
        score_name = str(score.get("score_name") or score.get("score_id") or "Score").strip()
        block_name = f"{score_name} Alignment Timeline"
        blocks.append(
            {
                "class_name": FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS,
                "block_name": block_name,
                "config": {
                    **block_config,
                    "show_bucket_details": False,
                    "_timeline_series": score.get("score_id") or score_name,
                },
                "output": _single_timeline_block_output(
                    source_output=output_data,
                    series=score,
                    title=block_name,
                    description="Stored feedback alignment for this score.",
                    mode="single_score",
                    show_methodology=False,
                ),
                "log": log_output,
            }
        )

    if not blocks:
        blocks.append(
            {
                "class_name": FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS,
                "block_name": "Feedback Alignment Timeline",
                "config": {**block_config, "show_bucket_details": False},
                "output": {
                    **deepcopy(output_data),
                    "show_methodology": True,
                    "show_bucket_details": False,
                },
                "log": log_output,
            }
        )

    return blocks


def run_feedback_alignment_timeline_report(
    *,
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
    split_score_timelines: bool = True,
) -> Dict[str, Any]:
    """
    Execute FeedbackAlignmentTimeline and optionally persist each series as a
    separate top-level report block.
    """
    if not split_score_timelines or score or background:
        return run_feedback_report_block(
            block_class=FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS,
            scorecard=scorecard,
            score=score,
            days=days,
            start_date=start_date,
            end_date=end_date,
            extra_config=extra_config,
            account_identifier=account_identifier,
            cache_key=cache_key,
            ttl_hours=ttl_hours,
            fresh=fresh,
            background=background,
        )

    if not scorecard or not str(scorecard).strip():
        raise ValueError("'scorecard' is required.")

    client = create_client()
    account_id = resolve_account_id_for_command(client, account_identifier)

    block_config: Dict[str, Any] = {"scorecard": str(scorecard).strip()}
    block_config.update(build_window_config(days=days, start_date=start_date, end_date=end_date))
    if extra_config:
        for key, value in extra_config.items():
            if value is not None:
                block_config[key] = value

    # The split report renders one timeline per top-level block, so bucket
    # detail gauge cards should not appear even if callers pass the legacy flag.
    block_config["show_bucket_details"] = False

    output_data, log_output, _ = _instantiate_and_run_block(
        block_def={
            "class_name": FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS,
            "block_name": FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS,
            "config": block_config,
        },
        report_params={"account_id": account_id},
        api_client=client,
    )

    if output_data is None:
        return {
            "status": "failed",
            "error": log_output or "FeedbackAlignmentTimeline execution failed.",
            "block_class": FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS,
            "block_config": block_config,
            "cached": False,
        }

    report_blocks = build_feedback_alignment_timeline_report_blocks(
        output_data=output_data,
        block_config=block_config,
        log_output=log_output,
    )
    rolling_min_items = (output_data.get("sample_policy") or {}).get("rolling_min_items")
    methodology_description = (
        "Top-level alignment timelines. The first block is the overall included score set; "
        "each following block is one included score. Bucket detail gauges are intentionally hidden.\n\n"
        "What these charts measure:\n"
        + "\n".join(f"- {line}" for line in feedback_alignment_methodology_lines(rolling_min_items))
    )
    report_name = _timeline_report_display_name(output_data, block_config)
    report_id = persist_precomputed_report_blocks(
        report_name=report_name,
        block_definitions=report_blocks,
        account_id=account_id,
        client=client,
        report_parameters={
            **block_config,
            "_display_title": output_data.get("scorecard_name") or block_config.get("scorecard"),
            "_feedback_alignment_split_timelines": True,
            "_cache_key": cache_key,
        },
        display_title=output_data.get("scorecard_name") or "Feedback Alignment Timelines",
        display_subtitle=_timeline_report_subtitle(output_data),
        display_description=methodology_description,
    )

    result: Dict[str, Any] = {
        "status": "success",
        "output": output_data,
        "block_class": FEEDBACK_ALIGNMENT_TIMELINE_BLOCK_CLASS,
        "block_config": block_config,
        "cached": False,
        "report_id": report_id,
        "report_block_count": len(report_blocks),
        "split_score_timelines": True,
    }
    if log_output:
        result["log"] = log_output
    return result
