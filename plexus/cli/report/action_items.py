"""
`plexus report action-items` — generate a prioritized to-do list from an
All Feedback report's root-cause analysis.
"""

import click
import json
import logging
import yaml
from datetime import datetime, timezone
from typing import Optional

from plexus.cli.shared.console import console
from plexus.cli.shared.client_utils import create_client
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.reports.s3_utils import download_report_block_file

from .utils import resolve_account_id_for_command, resolve_report

logger = logging.getLogger(__name__)


def _fetch_output(block: ReportBlock) -> Optional[dict]:
    """Fetch and parse the block's output JSON, following output_attachment if compacted."""
    raw = block.output
    if not raw:
        return None
    if isinstance(raw, str):
        raw = json.loads(raw)
    if raw.get("output_compacted") and raw.get("output_attachment"):
        content, _ = download_report_block_file(raw["output_attachment"])
        # The attached output file may be YAML (feedback_analysis emits YAML)
        # or JSON; try YAML first since it is a superset of JSON.
        raw = yaml.safe_load(content)
    return raw


def _fetch_memories(memories_file: str) -> dict:
    """Download a memories YAML file from S3 and return the parsed dict."""
    content, _ = download_report_block_file(memories_file)
    return yaml.safe_load(content) or {}


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
                "is_new": topic.get("is_new", False),
                "is_trending": topic.get("is_trending", False),
                "exemplars": topic.get("exemplars", []),
            })
    return items


def _collect_action_items(output: dict, ac1_threshold: float, recency_days: int,
                          scorecard_name_hint: str = None) -> list:
    """Walk the report output and return filtered, annotated action items.

    Handles both all-scorecards mode (output has a 'scorecards' list) and
    single-scorecard mode (output has 'scores' and 'memories_file' at root).
    """
    items = []

    if output.get("mode") == "all_scorecards":
        # All-scorecards mode: one memories file per scorecard
        for scorecard in output.get("scorecards", []):
            sc_ac1 = scorecard.get("overall_ac1")
            if sc_ac1 is not None and sc_ac1 >= ac1_threshold:
                continue

            memories_file = scorecard.get("memories_file")
            if not memories_file:
                continue
            try:
                memories = _fetch_memories(memories_file)
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
        # Single-scorecard mode: memories at root level
        sc_ac1 = output.get("overall_ac1")
        if sc_ac1 is not None and sc_ac1 >= ac1_threshold:
            return []

        memories_file = output.get("memories_file")
        memories = output.get("memories") or {}
        if memories_file:
            try:
                memories = _fetch_memories(memories_file)
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

    # Sort: most recent first, then highest item count
    items.sort(key=lambda x: (x["days_inactive"], -x["member_count"]))
    return items


def _render_markdown(items: list, ac1_threshold: float, recency_days: int, date_range: dict) -> str:
    lines = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    period = ""
    if date_range:
        period = f" ({date_range.get('start', '')[:10]} – {date_range.get('end', '')[:10]})"
    lines.append(f"# Action Items — All Feedback{period}")
    lines.append(f"Generated: {today}  |  Thresholds: AC1 < {ac1_threshold:.2f}, inactive ≤ {recency_days}d\n")

    if not items:
        lines.append("_No action items found matching the specified thresholds._")
        return "\n".join(lines)

    current_scorecard = None
    for item in items:
        if item["scorecard_name"] != current_scorecard:
            current_scorecard = item["scorecard_name"]
            lines.append(f"\n## {current_scorecard}")

        ac1_str = f"{item['score_ac1']:.3f}" if item["score_ac1"] is not None else "N/A"
        urgency = ""
        if item["is_trending"]:
            urgency = " 📈 TRENDING"
        elif item["is_new"]:
            urgency = " 🆕 NEW"

        lines.append(
            f"\n### {item['score_name']} › {item['topic_label']}{urgency}"
        )
        lines.append(
            f"AC1: {ac1_str}  |  {item['member_count']} items  |  {item['days_inactive']}d ago"
        )
        if item["cause"]:
            lines.append(f"\n**Root cause:** {item['cause']}")
        if item["keywords"]:
            lines.append(f"**Keywords:** {', '.join(item['keywords'])}")

        for ex in item["exemplars"][:2]:
            text = ex.get("text", "") if isinstance(ex, dict) else str(ex)
            identifiers = ex.get("identifiers", []) if isinstance(ex, dict) else []
            link = next((i.get("url") for i in identifiers if i.get("url")), None)
            ref = f" ([link]({link}))" if link else ""
            lines.append(f"\n> {text[:200]}{ref}")

    return "\n".join(lines)


@click.command(name="action-items")
@click.argument("report_id", required=False, default=None)
@click.option("--ac1-threshold", default=0.8, show_default=True, type=float,
              help="Skip scores with AC1 at or above this value.")
@click.option("--recency-days", default=30, show_default=True, type=int,
              help="Skip topics inactive for more than this many days.")
@click.option("--format", "output_format", default="markdown",
              type=click.Choice(["markdown", "json", "yaml"]), show_default=True,
              help="Output format.")
@click.option("--account", "account_identifier", default=None,
              help="Account key or ID (uses PLEXUS_ACCOUNT_KEY if omitted).")
def action_items_command(
    report_id: Optional[str],
    ac1_threshold: float,
    recency_days: int,
    output_format: str,
    account_identifier: Optional[str],
):
    """Generate a prioritized action-item list from an All Feedback report.

    REPORT_ID is optional — omit to use the most recent report.
    """
    client = create_client()
    account_id = resolve_account_id_for_command(client, account_identifier)

    # Resolve the report
    if report_id:
        report_instance = resolve_report(report_id, account_id, client)
        if not report_instance:
            console.print(f"[red]Report '{report_id}' not found.[/red]")
            raise click.Abort()
    else:
        console.print("[dim]Fetching most recent report…[/dim]")
        reports = Report.list_by_account_id(account_id=account_id, client=client, limit=10)
        if not reports:
            console.print("[red]No reports found for this account.[/red]")
            raise click.Abort()
        report_instance = reports[0]

    console.print(f"[dim]Report: {report_instance.id}[/dim]")

    # Find the FeedbackAnalysis block
    blocks = ReportBlock.list_by_report_id(report_instance.id, client)
    fa_block = next(
        (b for b in blocks if (b.type or "").lower() in ("feedbackanalysis", "feedback_analysis")),
        None,
    )
    if not fa_block:
        console.print("[red]No FeedbackAnalysis block found in this report.[/red]")
        raise click.Abort()

    console.print("[dim]Fetching report output…[/dim]")
    output = _fetch_output(fa_block)
    if not output:
        console.print("[red]Could not read block output.[/red]")
        raise click.Abort()

    console.print("[dim]Collecting action items…[/dim]")
    items = _collect_action_items(output, ac1_threshold, recency_days,
                                  scorecard_name_hint=fa_block.name)

    console.print(f"[dim]Found {len(items)} action item(s).[/dim]\n")

    date_range = output.get("date_range", {})

    if output_format == "json":
        click.echo(json.dumps(items, indent=2, default=str))
    elif output_format == "yaml":
        click.echo(yaml.dump(items, allow_unicode=True, sort_keys=False))
    else:
        click.echo(_render_markdown(items, ac1_threshold, recency_days, date_range))
