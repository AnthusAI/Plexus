"""CLI command for targeted single-item feedback invalidation."""

import json
import logging
from typing import Optional

import click
from rich.table import Table

from plexus.cli.feedback.feedback_invalidation import (
    FeedbackInvalidationError,
    invalidate_feedback_item,
    list_invalid_feedback_items_for_score,
    reinstate_feedback_item,
    reinstate_invalid_feedback_items_for_score,
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
    elif result["status"] == "reinstated":
        console.print(
            f"[bold green]Reinstated feedback item {feedback_item['id']}[/bold green]"
        )
    elif result["status"] == "already_valid":
        console.print(
            f"[bold yellow]Feedback item {feedback_item['id']} is already valid[/bold yellow]"
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


def _display_inventory(result):
    inventory = result.get("inventory", result)
    items = inventory.get("feedback_items", [])
    console.print(
        f"[bold]Invalidated feedback items for {inventory['score_identifier']}:[/bold] "
        f"{len(items)}"
    )

    table = Table(show_header=True)
    table.add_column("Feedback ID")
    table.add_column("Item ID")
    table.add_column("Initial")
    table.add_column("Final")
    table.add_column("Edited At")
    table.add_column("Cache Key")
    for item in items:
        table.add_row(
            item["id"] or "-",
            item["item_id"] or "-",
            item["initial_answer_value"] or "-",
            item["final_answer_value"] or "-",
            item["edited_at"] or "-",
            item["cache_key"] or "-",
        )
    console.print(table)

    if "status" in result:
        console.print(
            f"Status: {result['status']}; updated={result.get('updated_count', 0)}; "
            f"failed={result.get('failed_count', 0)}"
        )


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


@click.command(name="uninvalidate")
@click.argument("identifier", required=False)
@click.option(
    "--scorecard",
    "scorecard_identifier",
    help="Scorecard identifier for disambiguation, or required with --all-for-score.",
)
@click.option(
    "--score",
    "score_identifier",
    help="Score identifier for disambiguation, or required with --all-for-score.",
)
@click.option(
    "--all-for-score",
    is_flag=True,
    help="Reinstate all invalidated feedback items for the specified score.",
)
@click.option(
    "--dry-run/--execute",
    default=True,
    help="With --all-for-score, list affected rows without mutating unless --execute is used.",
)
@click.option(
    "--days",
    type=int,
    default=None,
    help="Optional editedAt lookback window for --all-for-score. Omit for all available rows.",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Required with --all-for-score --execute.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format.",
)
def uninvalidate_feedback(
    identifier: Optional[str],
    scorecard_identifier: Optional[str],
    score_identifier: Optional[str],
    all_for_score: bool,
    dry_run: bool,
    days: Optional[int],
    yes: bool,
    output_format: str,
):
    """Mark feedback valid again by feedback ID, item identifier, or score-wide reset."""
    if all_for_score:
        if identifier:
            raise click.ClickException("Do not pass an identifier with --all-for-score.")
        if not scorecard_identifier or not score_identifier:
            raise click.ClickException("--all-for-score requires --scorecard and --score.")
        if not dry_run and not yes:
            raise click.ClickException("--all-for-score --execute requires --yes.")
    elif not identifier:
        raise click.ClickException("Pass an identifier, or use --all-for-score.")

    client = create_client()

    try:
        if all_for_score:
            result = reinstate_invalid_feedback_items_for_score(
                client=client,
                scorecard_identifier=scorecard_identifier,
                score_identifier=score_identifier,
                dry_run=dry_run,
                days=days,
            )
            if output_format == "json":
                click.echo(json.dumps(result, indent=2, default=str))
            else:
                _display_inventory(result)
            return

        result = reinstate_feedback_item(
            client=client,
            identifier=identifier,
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
        )
        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            _display_result(result)
    except FeedbackInvalidationError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error reinstating feedback item")
        raise click.ClickException(f"Unexpected error reinstating feedback item: {exc}") from exc


@click.command(name="invalidated")
@click.option("--scorecard", "scorecard_identifier", required=True)
@click.option("--score", "score_identifier", required=True)
@click.option(
    "--days",
    type=int,
    default=None,
    help="Optional editedAt lookback window. Omit for all available rows.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format.",
)
def list_invalidated_feedback(
    scorecard_identifier: str,
    score_identifier: str,
    days: Optional[int],
    output_format: str,
):
    """List currently invalidated feedback for one score."""
    client = create_client()

    try:
        result = list_invalid_feedback_items_for_score(
            client=client,
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
            days=days,
        )
        if output_format == "json":
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            _display_inventory(result)
    except FeedbackInvalidationError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error listing invalidated feedback")
        raise click.ClickException(
            f"Unexpected error listing invalidated feedback: {exc}"
        ) from exc
