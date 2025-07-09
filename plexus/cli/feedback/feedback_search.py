"""
Command for searching and finding feedback items based on various criteria.
"""

import click
import logging
import traceback
import asyncio
from typing import Optional
from datetime import datetime, timezone, timedelta
import yaml
import json

from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.cli.reports.utils import resolve_account_id_for_command
from plexus.cli.memoized_resolvers import memoized_resolve_scorecard_identifier, memoized_resolve_score_identifier
from plexus.cli.feedback.feedback_service import FeedbackService

logger = logging.getLogger(__name__)

async def find_feedback_async(
    scorecard: str,
    score: str,
    days: int,
    limit: Optional[int],
    initial_value: Optional[str],
    final_value: Optional[str],
    format: str,
    account_identifier: Optional[str],
    prioritize_edit_comments: bool
):
    """
    Find feedback items for a given scorecard and score from the last N days.
    
    This command searches for feedback items based on the specified criteria and can filter
    by initial/final values, apply limits with smart prioritization, and output in multiple formats.
    """
    client = create_client()
    account_id = resolve_account_id_for_command(client, account_identifier)
    
    try:
        # Resolve scorecard identifier to ID
        scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard)
        if not scorecard_id:
            console.print(f"[bold red]Error:[/bold red] No scorecard found with identifier: {scorecard}")
            return
        
        # Resolve score identifier to ID within the scorecard
        score_id = memoized_resolve_score_identifier(client, scorecard_id, score)
        if not score_id:
            console.print(f"[bold red]Error:[/bold red] No score found with identifier: {score} in scorecard: {scorecard}")
            return
        
        if format != 'yaml':
            console.print(f"[dim]Searching for feedback items from the last {days} days...[/dim]")
            console.print(f"[dim]Scorecard: {scorecard} (ID: {scorecard_id})[/dim]")
            console.print(f"[dim]Score: {score} (ID: {score_id})[/dim]")
            console.print(f"[dim]Account: {account_id}[/dim]")
        
        # Use the shared FeedbackService for consistent behavior
        try:
            result = await FeedbackService.search_feedback(
                client=client,
                scorecard_name=scorecard,
                score_name=score,
                scorecard_id=scorecard_id,
                score_id=score_id,
                account_id=account_id,
                days=days,
                initial_value=initial_value,
                final_value=final_value,
                limit=limit,
                prioritize_edit_comments=prioritize_edit_comments
            )
            
            if format != 'yaml':
                console.print(f"[dim]Retrieved {result.context.total_found} feedback items[/dim]")
                
        except Exception as e:
            if format != 'yaml':
                console.print(f"[bold red]Error retrieving feedback items: {str(e)}[/bold red]")
            raise
        
        if not result.feedback_items:
            if format == 'yaml':
                print("# No feedback items found")
                result_dict = FeedbackService.format_search_result_as_dict(result)
                yaml_output = yaml.dump(result_dict, default_flow_style=False, allow_unicode=True, sort_keys=False, indent=2)
                print(yaml_output)
            else:
                console.print("[yellow]No feedback items found matching the criteria.[/yellow]")
            return
        
        if format == 'yaml':
            # Output using the shared format
            result_dict = FeedbackService.format_search_result_as_dict(result)
            print("# Plexus feedback search results")
            yaml_output = yaml.dump(result_dict, default_flow_style=False, allow_unicode=True, sort_keys=False, indent=2)
            print(yaml_output)
        else:
            # Human-readable output using the consistent field names
            console.print(f"\n[bold green]Found {result.context.total_found} feedback items:[/bold green]")
            
            for i, item in enumerate(result.feedback_items, 1):
                console.print(f"\n[bold cyan]Feedback Item {i}:[/bold cyan]")
                console.print(f"  [bold]Item ID:[/bold] {item.item_id}")
                
                console.print(f"  [bold]Initial Value:[/bold] {item.initial_value or 'N/A'}")
                console.print(f"  [bold]Final Value:[/bold] {item.final_value or 'N/A'}")
                
                if item.initial_explanation:
                    console.print(f"  [bold]Initial Explanation:[/bold] {item.initial_explanation}")
                if item.final_explanation:
                    console.print(f"  [bold]Final Explanation:[/bold] {item.final_explanation}")
                if item.edit_comment:
                    console.print(f"  [bold]Edit Comment:[/bold] {item.edit_comment}")
        
    except Exception as e:
        error_msg = f"Failed to search for feedback items: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        if format == 'yaml':
            print(f"# Error: {error_msg}")
            # Return empty result in consistent format
            empty_result = {
                "context": {
                    "scorecard_name": scorecard,
                    "score_name": score,
                    "scorecard_id": "",
                    "score_id": "",
                    "account_id": account_id,
                    "filters": {
                        "days": days,
                        "initial_value": initial_value,
                        "final_value": final_value,
                        "limit": limit,
                        "prioritize_edit_comments": prioritize_edit_comments
                    },
                    "total_found": 0
                },
                "feedback_items": []
            }
            yaml_output = yaml.dump(empty_result, default_flow_style=False, allow_unicode=True, sort_keys=False, indent=2)
            print(yaml_output)
        else:
            console.print(f"[bold red]{error_msg}[/bold red]")


@click.command(name="find")
@click.option('--scorecard', required=True, help='The scorecard to search feedback for (accepts ID, name, key, or external ID).')
@click.option('--score', required=True, help='The score to search feedback for (accepts ID, name, key, or external ID).')
@click.option('--days', type=int, default=30, help='Number of days to look back for feedback items.')
@click.option('--limit', type=int, help='Maximum number of feedback items to return (with smart prioritization).')
@click.option('--initial-value', 'initial_value', help='Filter by initial answer value (e.g., "Yes", "No").')
@click.option('--final-value', 'final_value', help='Filter by final answer value (e.g., "Yes", "No").')
@click.option('--format', type=click.Choice(['fixed', 'yaml']), default='fixed', help='Output format: fixed (human-readable) or yaml (structured data).')
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
@click.option('--prioritize-edit-comments/--no-prioritize-edit-comments', default=True, help='Whether to prioritize feedback items with edit comments when limiting results.')
def find_feedback(
    scorecard: str,
    score: str,
    days: int,
    limit: Optional[int],
    initial_value: Optional[str],
    final_value: Optional[str],
    format: str,
    account_identifier: Optional[str],
    prioritize_edit_comments: bool
):
    """
    Find feedback items for a given scorecard and score from the last N days.
    
    This command searches for feedback items based on the specified criteria and can filter
    by initial/final values, apply limits with smart prioritization, and output in multiple formats.
    """
    asyncio.run(find_feedback_async(
        scorecard=scorecard,
        score=score,
        days=days,
        limit=limit,
        initial_value=initial_value,
        final_value=final_value,
        format=format,
        account_identifier=account_identifier,
        prioritize_edit_comments=prioritize_edit_comments
    ))