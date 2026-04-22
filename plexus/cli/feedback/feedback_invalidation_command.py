"""CLI command for targeted single-item feedback invalidation."""

import logging
from typing import Optional

import click
from rich.table import Table

from plexus.cli.feedback.feedback_invalidation import (
    FeedbackInvalidationError,
    invalidate_feedback_item,
)
from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.console import console

logger = logging.getLogger(__name__)


def _display_result(result):
    feedback_item = result["feedback_item"]
    resolution = result["resolution"]

    if result["status"] == "invalidated":
        console.print(
            f"[bold green]Invalidated feedback item {feedback_item['id']}[/bold green]"
        )
    else:
        console.print(
            f"[bold yellow]Feedback item {feedback_item['id']} is already invalid[/bold yellow]"
        )

    table = Table(show_header=False, padding=(0, 1))
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Requested Identifier", resolution["requested_identifier"])
    table.add_row("Resolution", resolution["method"])
    table.add_row("Resolved Item ID", resolution.get("resolved_item_id") or "-")
    table.add_row("Feedback Item ID", feedback_item["id"])
    table.add_row("Scorecard ID", feedback_item["scorecard_id"] or "-")
    table.add_row("Score ID", feedback_item["score_id"] or "-")
    table.add_row("Item ID", feedback_item["item_id"] or "-")
    table.add_row("Invalid", "Yes" if feedback_item["is_invalid"] else "No")
    table.add_row("Initial Answer", feedback_item["initial_answer_value"] or "-")
    table.add_row("Final Answer", feedback_item["final_answer_value"] or "-")
    table.add_row("Cache Key", feedback_item["cache_key"] or "-")
    console.print(table)


@click.command(name="invalidate")
@click.argument("identifier")
@click.option(
    "--scorecard",
    "scorecard_identifier",
    help="Optional scorecard identifier to disambiguate item-level matches.",
)
@click.option(
    "--score",
    "score_identifier",
    help="Optional score identifier to disambiguate item-level matches. Requires --scorecard.",
)
def invalidate_feedback(
    identifier: str,
    scorecard_identifier: Optional[str],
    score_identifier: Optional[str],
):
    """Invalidate exactly one feedback item by feedback ID or item identifier."""
    client = create_client()

    try:
        result = invalidate_feedback_item(
            client=client,
            identifier=identifier,
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
        )
        _display_result(result)
    except FeedbackInvalidationError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error invalidating feedback item")
        raise click.ClickException(f"Unexpected error invalidating feedback item: {exc}") from exc
