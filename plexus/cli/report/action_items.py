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
from plexus.reports.action_items_utils import collect_action_items, fetch_block_output

from .utils import resolve_account_id_for_command, resolve_report

logger = logging.getLogger(__name__)


def _render_markdown(items: list, ac1_threshold: float, recency_days: int, date_range: dict) -> str:
    lines = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    period = ""
    if date_range:
        period = f" ({date_range.get('start', '')[:10]} - {date_range.get('end', '')[:10]})"
    lines.append(f"# Action Items — All Feedback{period}")
    lines.append(f"Generated: {today}  |  Thresholds: AC1 < {ac1_threshold:.2f}, inactive <= {recency_days}d\n")

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
        if item.get("lifecycle_tier") == "new" or item["is_new"]:
            urgency = " [NEW]"
        elif item["is_trending"]:
            urgency = " [TRENDING]"

        lines.append(
            f"\n### {item['score_name']} > {item['topic_label']}{urgency}"
        )
        lines.append(
            f"AC1: {ac1_str}  |  {item['member_count']} items  |  {item['days_inactive']}d ago"
        )
        if item["cause"]:
            lines.append(f"\n**Root cause:** {item['cause']}")
        if item["keywords"]:
            lines.append(f"**Keywords:** {', '.join(item['keywords'])}")

        for ex in item["exemplars"][:2]:
            if not isinstance(ex, dict):
                lines.append(f"\n> {str(ex)[:200]}")
                continue
            text = ex.get("text", "")
            identifiers = ex.get("identifiers", [])
            link = next((i.get("url") for i in identifiers if i.get("url")), None)
            ref = f" ({link})" if link else ""

            lines.append(f"\n> {text[:200]}{ref}")

            initial = ex.get("initial_answer_value")
            final = ex.get("final_answer_value")
            if initial is not None or final is not None:
                lines.append(f"> Original: {initial}  ->  Corrected: {final}")

            explanation = ex.get("score_explanation")
            if explanation:
                lines.append(f"> AI reasoning: {explanation[:300]}")

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
        console.print("[dim]Fetching most recent report...[/dim]")
        reports = Report.list_by_account_id(account_id=account_id, client=client, limit=10)
        if not reports:
            console.print("[red]No reports found for this account.[/red]")
            raise click.Abort()
        report_instance = reports[0]

    console.print(f"[dim]Report: {report_instance.id}[/dim]")

    # Find the FeedbackAlignment block
    blocks = ReportBlock.list_by_report_id(report_instance.id, client)
    fa_block = next(
        (b for b in blocks if (b.type or "").lower() in ("feedbackalignment", "feedback_alignment")),
        None,
    )
    if not fa_block:
        console.print("[red]No FeedbackAlignment block found in this report.[/red]")
        raise click.Abort()

    console.print("[dim]Fetching report output...[/dim]")
    output = fetch_block_output(fa_block)
    if not output:
        console.print("[red]Could not read block output.[/red]")
        raise click.Abort()

    # Try to get a human-readable scorecard name from report parameters
    report_params = report_instance.parameters or {}
    if isinstance(report_params, str):
        try:
            report_params = json.loads(report_params)
        except Exception:
            report_params = {}
    scorecard_name_hint = (
        report_params.get("param_scorecard_name")
        or report_params.get("scorecard_name")
        or fa_block.name
    )

    console.print("[dim]Collecting action items...[/dim]")
    items = collect_action_items(output, ac1_threshold, recency_days,
                                 scorecard_name_hint=scorecard_name_hint)

    console.print(f"[dim]Found {len(items)} action item(s).[/dim]\n")

    date_range = output.get("date_range", {})

    if output_format == "json":
        click.echo(json.dumps(items, indent=2, default=str))
    elif output_format == "yaml":
        click.echo(yaml.dump(items, allow_unicode=True, sort_keys=False))
    else:
        click.echo(_render_markdown(items, ac1_threshold, recency_days, date_range))
