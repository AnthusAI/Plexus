from __future__ import annotations

import json
import click
from plexus.cli.client_utils import create_client
from plexus.cli.reports.utils import resolve_account_id_for_command
from plexus.costs.cost_analysis import ScoreResultCostAnalyzer


@click.group(help="Cost analysis tools")
def cost():
    pass


@cost.command("analyze", help="Analyze ScoreResult costs over a time range (default last 1 hour)")
@click.option("--days", type=int, default=0, show_default=True, help="Days back to include (ignored when --hours provided)")
@click.option("--hours", type=int, default=1, show_default=True, help="Hours back to include (preferred)")
@click.option("--scorecard", type=str, default=None, help="Optional scorecard ID to filter")
@click.option("--score", type=str, default=None, help="Optional score ID to filter")
@click.option("--output", type=click.Choice(["json"], case_sensitive=False), default="json")
def analyze(days: int = 0, hours: int = 1, scorecard: str | None = None, score: str | None = None, output: str = "json"):
    client = create_client()
    account_id = resolve_account_id_for_command(client, None)
    analyzer = ScoreResultCostAnalyzer(
        client=client,
        account_id=account_id,
        days=days,
        hours=hours,
        scorecard_id=scorecard,
        score_id=score,
    )

    summary = analyzer.summarize()
    if output.lower() == "json":
        click.echo(json.dumps(summary, indent=2))


