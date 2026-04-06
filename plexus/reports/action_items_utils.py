"""
Shared helpers for generating action items from FeedbackAnalysis report output.

Used by both the ActionItems ReportBlock and the `plexus report action-items` CLI.
"""

import json
import logging
import yaml
from typing import Optional

from plexus.reports.s3_utils import download_report_block_file

logger = logging.getLogger(__name__)


def fetch_block_output(block) -> Optional[dict]:
    """Fetch and parse a ReportBlock's output, following output_attachment if compacted."""
    raw = block.output
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = yaml.safe_load(raw)
    if isinstance(raw, dict) and raw.get("output_compacted") and raw.get("output_attachment"):
        try:
            content, _ = download_report_block_file(raw["output_attachment"])
            raw = yaml.safe_load(content)
        except Exception as e:
            logger.warning(f"Could not fetch output attachment: {e}")
            return None
    return raw if isinstance(raw, dict) else None


def fetch_memories(memories_file: str) -> dict:
    """Download a memories YAML file from S3 and return the parsed dict."""
    content, _ = download_report_block_file(memories_file)
    return yaml.safe_load(content) or {}


def collect_action_items(output: dict, ac1_threshold: float, recency_days: int,
                         scorecard_name_hint: str = None) -> list:
    """Walk the FeedbackAnalysis output and return filtered, annotated action items.

    Handles both all-scorecards mode (output has a 'scorecards' list) and
    single-scorecard mode (output has 'scores' and optionally 'memories_file' at root).

    Each action item dict contains:
      scorecard_name, score_name, score_ac1, topic_label, cause, keywords,
      member_count, days_inactive, is_new, is_trending, exemplars
    """
    items = []

    if output.get("mode") == "all_scorecards":
        for scorecard in output.get("scorecards", []):
            sc_ac1 = scorecard.get("overall_ac1")
            if sc_ac1 is not None and sc_ac1 >= ac1_threshold:
                continue
            memories_file = scorecard.get("memories_file")
            if not memories_file:
                continue
            try:
                memories = fetch_memories(memories_file)
            except Exception as e:
                logger.warning(f"Could not fetch memories for {scorecard.get('scorecard_name')}: {e}")
                continue
            items.extend(_extract_topics_for_scores(
                scorecard.get("scores", []),
                memories,
                scorecard.get("scorecard_name", "Unknown"),
                ac1_threshold,
                recency_days,
            ))
    else:
        # Single-scorecard mode
        sc_ac1 = output.get("overall_ac1")
        if sc_ac1 is not None and sc_ac1 >= ac1_threshold:
            return []
        memories_file = output.get("memories_file")
        memories = output.get("memories") or {}
        if memories_file:
            try:
                memories = fetch_memories(memories_file)
            except Exception as e:
                logger.warning(f"Could not fetch memories file: {e}")
        scorecard_name = output.get("scorecard_name") or scorecard_name_hint or "Unknown Scorecard"
        items.extend(_extract_topics_for_scores(
            output.get("scores", []),
            memories,
            scorecard_name,
            ac1_threshold,
            recency_days,
        ))

    # Sort: most items (biggest problem) first, then most recent
    items.sort(key=lambda x: (-x["member_count"], x["days_inactive"]))
    return items


def _extract_topics_for_scores(scores: list, memories: dict, scorecard_name: str,
                                ac1_threshold: float, recency_days: int) -> list:
    """Extract action items from a list of scores using a memories dict."""
    items = []
    topics_by_score_id = {
        s["score_id"]: s.get("topics", [])
        for s in memories.get("scores", [])
        if s.get("score_id")
    }
    for score in scores:
        score_ac1 = score.get("ac1")
        if score_ac1 is not None and score_ac1 >= ac1_threshold:
            continue
        if score.get("mismatches", 0) == 0:
            continue
        topics = topics_by_score_id.get(score.get("score_id"), [])
        for topic in topics:
            days_inactive = topic.get("days_inactive")
            if days_inactive is None or days_inactive > recency_days:
                continue
            items.append({
                "scorecard_name": scorecard_name,
                "score_name": score.get("score_name", "Unknown"),
                "score_ac1": score_ac1,
                "score_mismatches": score.get("mismatches", 0),
                "topic_label": topic.get("label") or "Unnamed topic",
                "cause": topic.get("cause"),
                "keywords": topic.get("keywords", []),
                "member_count": topic.get("member_count", 0),
                "days_inactive": days_inactive,
                "lifecycle_tier": topic.get("lifecycle_tier", "established"),
                "is_new": topic.get("is_new", False),
                "is_trending": topic.get("is_trending", False),
                "exemplars": topic.get("exemplars", []),
            })
    return items
