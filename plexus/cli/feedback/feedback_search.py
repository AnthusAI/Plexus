"""
Command for searching and finding feedback items based on various criteria.
"""

import click
import logging
import traceback
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import yaml
import json

from plexus.cli.shared.console import console
from plexus.cli.shared.client_utils import create_client
from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.cli.shared.memoized_resolvers import memoized_resolve_scorecard_identifier, memoized_resolve_score_identifier
from plexus.cli.feedback.feedback_service import FeedbackService
from plexus.dashboard.api.models.feedback_item import FeedbackItem

logger = logging.getLogger(__name__)

import random

def build_date_filter(days: int) -> str:
    """Build a date filter for the last N days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff_date.isoformat()

def prioritize_feedback_with_edit_comments(feedback_items: List["FeedbackItem"], limit: int) -> List["FeedbackItem"]:
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
    items_with_comments = [item for item in feedback_items if getattr(item, "editCommentValue", None)]
    items_without_comments = [item for item in feedback_items if not getattr(item, "editCommentValue", None)]
    
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

def format_feedback_item_yaml(item: "FeedbackItem", include_metadata: bool = False) -> Dict[str, Any]:
    """Format a FeedbackItem as a dictionary for YAML output."""
    result = {
        'item_id': getattr(item, "itemId", None),
        'external_id': FeedbackService._extract_preferred_id(item),
        'initial_value': getattr(item, "initialAnswerValue", None),
        'final_value': getattr(item, "finalAnswerValue", None),
        'initial_explanation': getattr(item, "initialCommentValue", None),
        'final_explanation': getattr(item, "finalCommentValue", None),
        'edit_comment': getattr(item, "editCommentValue", None)
    }
    
    if include_metadata:
        result['metadata'] = {
            'feedback_id': getattr(item, "id", None),
            'cache_key': getattr(item, "cacheKey", None),
            'is_agreement': getattr(item, "isAgreement", None),
            'edited_at': item.editedAt.isoformat() if getattr(item, "editedAt", None) else None,
            'editor_name': getattr(item, "editorName", None),
            'created_at': item.createdAt.isoformat() if getattr(item, "createdAt", None) else None,
            'updated_at': item.updatedAt.isoformat() if getattr(item, "updatedAt", None) else None
        }
    
    return result

async def fetch_feedback_items_with_gsi(client, account_id: str, scorecard_id: str, score_id: str, 
                                       start_date: datetime, end_date: datetime) -> List[FeedbackItem]:
    """
    Fetch feedback items using the same GSI query approach as feedback_summary.py.
    This ensures we get all available data.
    """
    all_items_for_score = []
    
    try:
        # Use the optimized GSI directly with GraphQL (same approach as FeedbackAnalysis report block)
        query = """
        query ListFeedbackItemsByGSI(
            $accountId: String!,
            $composite_sk_condition: ModelFeedbackItemByAccountScorecardScoreEditedAtCompositeKeyConditionInput,
            $limit: Int,
            $nextToken: String,
            $sortDirection: ModelSortDirection
        ) {
            listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
                accountId: $accountId,
                scorecardIdScoreIdEditedAt: $composite_sk_condition,
                limit: $limit,
                nextToken: $nextToken,
                sortDirection: $sortDirection
            ) {
                items {
                    id
                    accountId
                    scorecardId
                    scoreId
                    itemId
                    cacheKey
                    initialAnswerValue
                    finalAnswerValue
                    initialCommentValue
                    finalCommentValue
                    editCommentValue
                    editedAt
                    editorName
                    isAgreement
                    createdAt
                    updatedAt
                    item {
                        id
                        identifiers
                        externalId
                        text
                    }
                }
                nextToken
            }
        }
        """
        
        # Prepare variables for the query
        variables = {
            "accountId": account_id,
            "composite_sk_condition": {
                "between": [
                    {
                        "scorecardId": str(scorecard_id),
                        "scoreId": str(score_id),
                        "editedAt": start_date.isoformat()
                    },
                    {
                        "scorecardId": str(scorecard_id),
                        "scoreId": str(score_id),
                        "editedAt": end_date.isoformat()
                    }
                ]
            },
            "limit": 100,
            "nextToken": None,
            "sortDirection": "DESC"
        }
        
        next_token = None
        
        while True:
            if next_token:
                variables["nextToken"] = next_token
            
            try:
                response = await asyncio.to_thread(client.execute, query, variables)
                
                if response and 'errors' in response:
                    logger.warning(f"GraphQL errors: {response.get('errors')}")
                    # Fall back to the original simple filter approach if GSI fails
                    return await fetch_feedback_items_fallback(client, account_id, scorecard_id, score_id, start_date, end_date)
                
                if response and 'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt' in response:
                    result = response['listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt']
                    item_dicts = result.get('items', [])
                    
                    # Convert to FeedbackItem objects
                    items = [FeedbackItem.from_dict(item_dict, client=client) for item_dict in item_dicts]
                    all_items_for_score.extend(items)
                    
                    logger.debug(f"Fetched {len(items)} items using GSI query (total: {len(all_items_for_score)})")
                    
                    # Get next token for pagination
                    next_token = result.get('nextToken')
                    if not next_token:
                        break
                else:
                    logger.warning("Unexpected response format from GSI query")
                    # Fall back to the original approach
                    return await fetch_feedback_items_fallback(client, account_id, scorecard_id, score_id, start_date, end_date)
                    
            except Exception as e:
                logger.warning(f"Error during GSI query execution: {e}. Falling back to simple filter approach.")
                return await fetch_feedback_items_fallback(client, account_id, scorecard_id, score_id, start_date, end_date)
                
    except Exception as e:
        logger.error(f"Error during feedback item fetch for score {score_id}: {str(e)}")
        return await fetch_feedback_items_fallback(client, account_id, scorecard_id, score_id, start_date, end_date)
    
    logger.debug(f"Total items fetched for score {score_id}: {len(all_items_for_score)}")
    return all_items_for_score

async def fetch_feedback_items_fallback(client, account_id: str, scorecard_id: str, score_id: str, 
                                       start_date: datetime, end_date: datetime) -> List[FeedbackItem]:
    """
    Fallback method using the simple filter approach (original implementation).
    """
    logger.warning("Using fallback simple filter approach")
    
    filter_condition = {
        "and": [
            {"accountId": {"eq": account_id}},
            {"scorecardId": {"eq": scorecard_id}},
            {"scoreId": {"eq": score_id}},
            {"editedAt": {"ge": start_date.isoformat()}},
            {"editedAt": {"le": end_date.isoformat()}}
        ]
    }
    
    try:
        feedback_items, _ = FeedbackItem.list(
            client=client,
            limit=1000,  # Use a large limit to get all matching items
            filter=filter_condition,
            fields=FeedbackItem.GRAPHQL_BASE_FIELDS
        )
        
        logger.debug(f"Retrieved {len(feedback_items)} feedback items using fallback approach")
        return feedback_items
        
    except Exception as e:
        logger.error(f"Error fetching feedback items with fallback: {e}")
        return []

@click.command(name="find")
@click.option('--scorecard', required=True, help='The scorecard to search feedback for (accepts ID, name, key, or external ID).')
@click.option('--score', required=True, help='The score to search feedback for (accepts ID, name, key, or external ID).')
@click.option('--days', type=int, default=30, help='Number of days to look back for feedback items.')
@click.option('--limit', type=int, help='Maximum number of feedback items to return (automatically randomized, prioritizing items with edit comments).')
@click.option('--initial-value', 'initial_value', help='Filter by initial answer value (e.g., "Yes", "No").')
@click.option('--final-value', 'final_value', help='Filter by final answer value (e.g., "Yes", "No").')
@click.option('--format', type=click.Choice(['fixed', 'yaml']), default='fixed', help='Output format: fixed (human-readable) or yaml (structured data).')
@click.option('--verbose', is_flag=True, help='Include detailed metadata in output (feedback IDs, timestamps, etc.).')
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
    verbose: bool,
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
        verbose=verbose,
        account_identifier=account_identifier,
        prioritize_edit_comments=prioritize_edit_comments
    ))


async def find_feedback_async(
    scorecard: str,
    score: str,
    days: int,
    limit: Optional[int],
    initial_value: Optional[str],
    final_value: Optional[str],
    format: str,
    verbose: bool,
    account_identifier: Optional[str],
    prioritize_edit_comments: bool
):
    """
    Async implementation of find_feedback command.
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
            # Human-readable output using the consistent field names, including external ID
            console.print(f"\n[bold green]Found {result.context.total_found} feedback items:[/bold green]")
            
            for i, item in enumerate(result.feedback_items, 1):
                console.print(f"\n[bold cyan]Feedback Item {i}:[/bold cyan]")
                console.print(f"  [bold]Item ID:[/bold] {item.item_id}")
                console.print(f"  [bold]External ID:[/bold] {item.external_id or 'N/A'}")
                
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