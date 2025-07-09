"""
Command for searching and finding feedback items based on various criteria.
"""

import click
import logging
import random
import traceback
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import yaml
import json

from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.cli.reports.utils import resolve_account_id_for_command
from plexus.cli.memoized_resolvers import memoized_resolve_scorecard_identifier, memoized_resolve_score_identifier

logger = logging.getLogger(__name__)

def build_date_filter(days: int) -> str:
    """Build a date filter for the last N days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff_date.isoformat()

def prioritize_feedback_with_edit_comments(feedback_items: List[FeedbackItem], limit: int) -> List[FeedbackItem]:
    """
    Prioritize feedback items that have edit comments when applying a limit.
    
    Args:
        feedback_items: List of FeedbackItem objects
        limit: Maximum number of items to return
        
    Returns:
        List of prioritized and limited feedback items
    """
    if len(feedback_items) <= limit:
        return feedback_items
    
    # Separate items with and without edit comments
    items_with_comments = [item for item in feedback_items if item.editCommentValue]
    items_without_comments = [item for item in feedback_items if not item.editCommentValue]
    
    # Shuffle both groups for randomness when applying limits
    random.shuffle(items_with_comments)
    random.shuffle(items_without_comments)
    
    # Prioritize items with edit comments
    result = []
    
    # Add as many items with comments as possible
    comments_to_add = min(len(items_with_comments), limit)
    result.extend(items_with_comments[:comments_to_add])
    
    # Fill remaining slots with items without comments
    remaining_slots = limit - len(result)
    if remaining_slots > 0:
        result.extend(items_without_comments[:remaining_slots])
    
    return result

def format_feedback_item_yaml(item: FeedbackItem, include_metadata: bool = False) -> Dict[str, Any]:
    """Format a FeedbackItem as a dictionary for YAML output."""
    result = {
        'item_id': item.itemId,
        'initial_value': item.initialAnswerValue,
        'final_value': item.finalAnswerValue,
        'initial_explanation': item.initialCommentValue,
        'final_explanation': item.finalCommentValue,
        'edit_comment': item.editCommentValue
    }
    
    if include_metadata:
        result['metadata'] = {
            'feedback_id': item.id,
            'cache_key': item.cacheKey,
            'is_agreement': item.isAgreement,
            'edited_at': item.editedAt.isoformat() if item.editedAt else None,
            'editor_name': item.editorName,
            'created_at': item.createdAt.isoformat() if item.createdAt else None,
            'updated_at': item.updatedAt.isoformat() if item.updatedAt else None
        }
    
    return result

@click.command(name="find")
@click.option('--scorecard', required=True, help='The scorecard to search feedback for (accepts ID, name, key, or external ID).')
@click.option('--score', required=True, help='The score to search feedback for (accepts ID, name, key, or external ID).')
@click.option('--days', type=int, default=30, help='Number of days to look back for feedback items.')
@click.option('--limit', type=int, help='Maximum number of feedback items to return (randomly shuffled, prioritizing items with edit comments).')
@click.option('--initial-value', 'initial_value', help='Filter by initial answer value (e.g., "Yes", "No").')
@click.option('--final-value', 'final_value', help='Filter by final answer value (e.g., "Yes", "No").')
@click.option('--format', type=click.Choice(['fixed', 'yaml']), default='fixed', help='Output format: fixed (human-readable) or yaml (structured data).')
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
def find_feedback(
    scorecard: str,
    score: str,
    days: int,
    limit: Optional[int],
    initial_value: Optional[str],
    final_value: Optional[str],
    format: str,
    account_identifier: Optional[str]
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
        
        # Build date filter for the last N days
        cutoff_date = build_date_filter(days)
        
        if format != 'yaml':
            console.print(f"[dim]Searching for feedback items from the last {days} days...[/dim]")
            console.print(f"[dim]Scorecard: {scorecard} (ID: {scorecard_id})[/dim]")
            console.print(f"[dim]Score: {score} (ID: {score_id})[/dim]")
            console.print(f"[dim]Account: {account_id}[/dim]")
        
        # Fall back to using the standard list method with filters instead of the GSI for now
        # This will be less efficient but will work correctly
        filter_condition = {
            "and": [
                {"accountId": {"eq": account_id}},
                {"scorecardId": {"eq": scorecard_id}},
                {"scoreId": {"eq": score_id}},
                {"updatedAt": {"ge": cutoff_date}}
            ]
        }
        
        feedback_items, _ = FeedbackItem.list(
            client=client,
            limit=1000,  # Use a large limit to get all matching items for filtering
            filter=filter_condition,
            fields=FeedbackItem.GRAPHQL_BASE_FIELDS
        )
        
        if not feedback_items:
            if format == 'yaml':
                print("# No feedback items found")
                print("feedback_items: []")
            else:
                console.print("[yellow]No feedback items found matching the criteria.[/yellow]")
            return
        
        # Apply value filters if specified
        if initial_value or final_value:
            filtered_items = []
            for item in feedback_items:
                matches = True
                if initial_value and item.initialAnswerValue != initial_value:
                    matches = False
                if final_value and item.finalAnswerValue != final_value:
                    matches = False
                if matches:
                    filtered_items.append(item)
            feedback_items = filtered_items
        
        if not feedback_items:
            if format == 'yaml':
                print("# No feedback items found after filtering")
                print("feedback_items: []")
            else:
                console.print("[yellow]No feedback items found after applying value filters.[/yellow]")
            return
        
        # Apply limit with prioritization if specified
        if limit:
            feedback_items = prioritize_feedback_with_edit_comments(feedback_items, limit)
        
        # Sort by updated date descending (most recent first)
        feedback_items.sort(
            key=lambda item: item.updatedAt if item.updatedAt else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        
        if format == 'yaml':
            # Build YAML output
            yaml_data = {
                'context': {
                    'command': f'plexus feedback find --scorecard "{scorecard}" --score "{score}" --days {days}',
                    'scorecard_id': scorecard_id,
                    'score_id': score_id,
                    'account_id': account_id,
                    'filters': {
                        'days': days,
                        'initial_value': initial_value,
                        'final_value': final_value,
                        'limit': limit
                    },
                    'total_found': len(feedback_items)
                },
                'feedback_items': [
                    format_feedback_item_yaml(item, include_metadata=True)
                    for item in feedback_items
                ]
            }
            
            # Output clean YAML
            print("# Plexus feedback search results")
            yaml_output = yaml.dump(
                yaml_data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2
            )
            print(yaml_output)
        else:
            # Fixed format: human-readable output
            console.print(f"\n[bold green]Found {len(feedback_items)} feedback items:[/bold green]")
            
            for i, item in enumerate(feedback_items, 1):
                console.print(f"\n[bold cyan]Feedback Item {i}:[/bold cyan]")
                console.print(f"  [bold]Item ID:[/bold] {item.itemId}")
                console.print(f"  [bold]Cache Key:[/bold] {item.cacheKey}")
                
                console.print(f"  [bold]Initial Value:[/bold] {item.initialAnswerValue or 'N/A'}")
                console.print(f"  [bold]Final Value:[/bold] {item.finalAnswerValue or 'N/A'}")
                
                if item.initialCommentValue:
                    console.print(f"  [bold]Initial Explanation:[/bold] {item.initialCommentValue}")
                if item.finalCommentValue:
                    console.print(f"  [bold]Final Explanation:[/bold] {item.finalCommentValue}")
                if item.editCommentValue:
                    console.print(f"  [bold]Edit Comment:[/bold] {item.editCommentValue}")
                
                console.print(f"  [bold]Is Agreement:[/bold] {'Yes' if item.isAgreement else 'No'}")
                
                if item.editedAt:
                    console.print(f"  [bold]Edited At:[/bold] {item.editedAt.strftime('%Y-%m-%d %H:%M:%S')}")
                if item.editorName:
                    console.print(f"  [bold]Editor:[/bold] {item.editorName}")
                
                console.print(f"  [bold]Updated At:[/bold] {item.updatedAt.strftime('%Y-%m-%d %H:%M:%S') if item.updatedAt else 'N/A'}")
        
    except Exception as e:
        error_msg = f"Failed to search for feedback items: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        if format == 'yaml':
            print(f"# Error: {error_msg}")
            print("feedback_items: []")
        else:
            console.print(f"[bold red]{error_msg}[/bold red]") 