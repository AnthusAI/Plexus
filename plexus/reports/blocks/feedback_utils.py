"""
Shared utilities for identifying scorecards and scores with feedback items.

This module provides reusable functions for:
- Fetching scorecards from the account
- Fetching scores for a scorecard
- Fetching feedback items for a score in a time range
- Identifying which scorecards/scores have feedback in a given time range

These utilities are used by both the FeedbackAnalysis report block and
the feedback evaluation CLI commands.
"""

from typing import Any, Dict, List, Optional
import logging
import asyncio
from datetime import datetime, timezone

from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.feedback_item import FeedbackItem

logger = logging.getLogger(__name__)


async def fetch_all_scorecards(api_client, account_id: str) -> List[Scorecard]:
    """
    Fetches all scorecards for the given account.
    
    Args:
        api_client: The API client for making GraphQL queries
        account_id: The account ID to fetch scorecards for
        
    Returns:
        List of Scorecard objects
    """
    logger.info(f"Fetching all scorecards for account {account_id}")
    
    try:
        # GraphQL query to list all scorecards for the account
        query = """
        query ListScorecards($accountId: String!) {
            listScorecards(filter: {accountId: {eq: $accountId}}, limit: 1000) {
                items {
                    id
                    name
                    key
                    externalId
                    accountId
                    createdAt
                    updatedAt
                }
            }
        }
        """
        
        variables = {"accountId": account_id}
        result = await asyncio.to_thread(api_client.execute, query, variables)
        
        if result and 'listScorecards' in result and result['listScorecards']:
            scorecard_items = result['listScorecards'].get('items', [])
            scorecards = [Scorecard.from_dict(item, api_client) for item in scorecard_items]
            logger.info(f"Found {len(scorecards)} scorecards for account {account_id}")
            return scorecards
        else:
            logger.warning("No scorecards found or unexpected response format")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching scorecards: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


async def fetch_scores_for_scorecard(api_client, scorecard_id: str) -> List[Dict[str, Any]]:
    """
    Fetches all scores with externalIds for a given scorecard.
    
    Args:
        api_client: The API client for making GraphQL queries
        scorecard_id: The ID of the scorecard to fetch scores for
        
    Returns:
        List of score info dictionaries with structure:
        [
            {
                'plexus_score_id': str,
                'plexus_score_name': str,
                'cc_question_id': str  # The externalId
            }
        ]
        Sorted by section order and score order within sections.
    """
    logger.info(f"Fetching scores for scorecard {scorecard_id}")
    
    scores_query = """
    query GetScorecardScores($scorecardId: ID!) {
        getScorecard(id: $scorecardId) {
            id
            name
            sections {
                items {
                    id
                    scores {
                        items {
                            id
                            name
                            externalId
                            order
                        }
                    }
                }
            }
        }
    }
    """
    
    try:
        result = await asyncio.to_thread(api_client.execute, scores_query, {'scorecardId': scorecard_id})
        scorecard_data = result.get('getScorecard')
        
        raw_scores_with_positions = []
        
        if scorecard_data and scorecard_data.get('sections') and scorecard_data['sections'].get('items'):
            for section_index, section in enumerate(scorecard_data['sections']['items']):
                section_order = section_index
                
                if section.get('scores') and section['scores'].get('items'):
                    for score_index, score_item in enumerate(section['scores']['items']):
                        if score_item.get('externalId'):
                            score_order = score_item.get('order', score_index)
                            raw_scores_with_positions.append({
                                'plexus_score_id': score_item['id'],
                                'plexus_score_name': score_item['name'],
                                'cc_question_id': score_item['externalId'],
                                'section_order': section_order,
                                'score_order': score_order
                            })
                        else:
                            logger.debug(f"Score '{score_item.get('name')}' (ID: {score_item.get('id')}) is missing externalId, skipping")
        
        # Sort by section order, then by score order within section
        raw_scores_with_positions.sort(key=lambda s: (s['section_order'], s['score_order']))
        
        # Remove temporary sort keys
        scores_to_process = [
            {k: v for k, v in s.items() if k not in ['section_order', 'score_order']}
            for s in raw_scores_with_positions
        ]
        
        logger.info(f"Found {len(scores_to_process)} scores with externalIds for scorecard {scorecard_id}")
        return scores_to_process
        
    except Exception as e:
        logger.error(f"Error fetching scores for scorecard {scorecard_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


async def fetch_feedback_items_for_score(
    api_client,
    account_id: str,
    scorecard_id: str,
    score_id: str,
    start_date: datetime,
    end_date: datetime
) -> List[FeedbackItem]:
    """
    Fetches FeedbackItem records for a specific score on a scorecard within a date range.
    
    Uses the optimized GSI query for efficient retrieval.
    
    Args:
        api_client: The API client for making GraphQL queries
        account_id: The account ID
        scorecard_id: The ID of the scorecard
        score_id: The ID of the score
        start_date: Start date for filtering (UTC aware)
        end_date: End date for filtering (UTC aware)
        
    Returns:
        List of FeedbackItem objects
    """
    logger.debug(f"Fetching feedback items for scorecard {scorecard_id}, score {score_id}")
    logger.debug(f"Date range: {start_date.isoformat()} to {end_date.isoformat()}")
    
    all_items_for_score = []
    
    try:
        # Use the optimized GSI query
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
                response = await asyncio.to_thread(api_client.execute, query, variables)
                
                if response and 'errors' in response:
                    logger.warning(f"GraphQL errors with GSI query: {response.get('errors')}")
                    break
                
                if response and 'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt' in response:
                    result = response['listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt']
                    item_dicts = result.get('items', [])
                    
                    # Convert to FeedbackItem objects
                    items = [FeedbackItem.from_dict(item_dict, client=api_client) for item_dict in item_dicts]
                    all_items_for_score.extend(items)
                    
                    logger.debug(f"Fetched {len(items)} items using GSI query (total: {len(all_items_for_score)})")
                    
                    # Get next token for pagination
                    next_token = result.get('nextToken')
                    if not next_token:
                        break
                else:
                    logger.warning("Unexpected response format from GSI query")
                    break
                    
            except Exception as e:
                logger.warning(f"Error during GSI query execution: {e}")
                all_items_for_score = []
                break
        
    except Exception as e:
        logger.error(f"Error during feedback item fetch for score {score_id}: {str(e)}")
    
    logger.debug(f"Total items fetched for score {score_id}: {len(all_items_for_score)}")
    return all_items_for_score


async def get_feedback_counts_by_score(
    api_client,
    account_id: str,
    scorecard_id: str,
    score_ids: List[str],
    start_date: datetime,
    end_date: datetime
) -> Dict[str, int]:
    """
    Gets feedback counts for each score in a scorecard efficiently.
    Instead of fetching all items, we fetch just enough to know which scores have feedback.
    
    Args:
        api_client: The API client for making GraphQL queries
        account_id: The account ID
        scorecard_id: The ID of the scorecard
        score_ids: List of score IDs to check
        start_date: Start date for filtering (UTC aware)
        end_date: End date for filtering (UTC aware)
        
    Returns:
        Dict mapping score_id to feedback count
    """
    logger.debug(f"Getting feedback counts for {len(score_ids)} scores in scorecard {scorecard_id}")
    
    # Fetch ALL feedback items in the date range to get accurate counts
    # We paginate through all results to ensure we don't miss any scores
    try:
        query = """
        query ListFeedbackItemsForScorecard(
            $accountId: String!,
            $scorecardId: String!,
            $startDate: String!,
            $endDate: String!,
            $limit: Int,
            $nextToken: String
        ) {
            listFeedbackItems(
                filter: {
                    accountId: {eq: $accountId},
                    scorecardId: {eq: $scorecardId},
                    editedAt: {between: [$startDate, $endDate]}
                },
                limit: $limit,
                nextToken: $nextToken
            ) {
                items {
                    scoreId
                }
                nextToken
            }
        }
        """
        
        counts_by_score = {}
        next_token = None
        
        # Paginate through all results
        while True:
            variables = {
                "accountId": account_id,
                "scorecardId": scorecard_id,
                "startDate": start_date.isoformat().replace('+00:00', 'Z'),
                "endDate": end_date.isoformat().replace('+00:00', 'Z'),
                "limit": 1000,
                "nextToken": next_token
            }
            
            response = await asyncio.to_thread(api_client.execute, query, variables)
            
            if not response or 'listFeedbackItems' not in response:
                break
                
            result = response['listFeedbackItems']
            items = result.get('items', [])
            
            # Count feedback items by score
            for item in items:
                score_id = item.get('scoreId')
                if score_id:
                    counts_by_score[score_id] = counts_by_score.get(score_id, 0) + 1
            
            # Check for more pages
            next_token = result.get('nextToken')
            if not next_token:
                break
        
        logger.debug(f"Found feedback for {len(counts_by_score)} scores in scorecard {scorecard_id} (total {sum(counts_by_score.values())} items)")
        return counts_by_score
            
    except Exception as e:
        logger.error(f"Error getting feedback counts for scorecard {scorecard_id}: {str(e)}")
        return {}


async def _check_scorecard_for_feedback(
    api_client,
    account_id: str,
    scorecard: Scorecard,
    start_date: datetime,
    end_date: datetime
) -> Optional[Dict[str, Any]]:
    """
    Helper function to check a single scorecard for feedback.
    
    Returns a result dict if the scorecard has feedback, None otherwise.
    """
    logger.debug(f"Checking scorecard '{scorecard.name}' (ID: {scorecard.id})")
    
    # Fetch scores for this scorecard
    scores = await fetch_scores_for_scorecard(api_client, scorecard.id)
    
    if not scores:
        logger.debug(f"No scores with externalIds found for scorecard '{scorecard.name}'")
        return None
    
    # Query each score individually using the optimized GSI
    # This is more accurate than sampling at the scorecard level
    scores_with_feedback = []
    total_feedback_count = 0
    
    for score_info in scores:
        score_id = score_info['plexus_score_id']
        score_name = score_info['plexus_score_name']
        external_id = score_info['cc_question_id']
        
        # Fetch feedback items for this specific score using the GSI
        feedback_items = await fetch_feedback_items_for_score(
            api_client,
            account_id,
            scorecard.id,
            score_id,
            start_date,
            end_date
        )
        
        if feedback_items:
            feedback_count = len(feedback_items)
            total_feedback_count += feedback_count
            logger.debug(f"Found {feedback_count} feedback items for score '{score_name}'")
            scores_with_feedback.append({
                "score_id": score_id,
                "score_name": score_name,
                "external_id": external_id,
                "feedback_count": feedback_count
            })
    
    # Only return result if scorecard has scores with feedback
    if scores_with_feedback:
        logger.info(f"Scorecard '{scorecard.name}' has {len(scores_with_feedback)} score(s) with feedback ({total_feedback_count} total items)")
        return {
            "scorecard": scorecard,
            "scores_with_feedback": scores_with_feedback
        }
    
    return None


async def identify_scorecards_with_feedback(
    api_client,
    account_id: str,
    start_date: datetime,
    end_date: datetime,
    max_concurrent: int = 10
) -> List[Dict[str, Any]]:
    """
    Identifies all scorecards and scores that have feedback items in the given time range.
    
    This is the main orchestration function that:
    1. Fetches all scorecards for the account
    2. For each scorecard, fetches its scores (in parallel)
    3. For each score, checks if feedback exists in the time range (in parallel)
    4. Returns only scorecards/scores with feedback
    
    Args:
        api_client: The API client for making GraphQL queries
        account_id: The account ID
        start_date: Start date for filtering (UTC aware)
        end_date: End date for filtering (UTC aware)
        max_concurrent: Maximum number of scorecards to check concurrently (default: 10)
        
    Returns:
        List of dictionaries with structure:
        [
            {
                "scorecard": Scorecard,
                "scores_with_feedback": [
                    {
                        "score_id": str,
                        "score_name": str,
                        "external_id": str,
                        "feedback_count": int
                    }
                ]
            }
        ]
        Only includes scorecards that have at least one score with feedback.
    """
    logger.info(f"Identifying scorecards with feedback from {start_date.date()} to {end_date.date()}")
    
    # Fetch all scorecards
    scorecards = await fetch_all_scorecards(api_client, account_id)
    
    if not scorecards:
        logger.warning("No scorecards found for account")
        return []
    
    logger.info(f"Checking {len(scorecards)} scorecards for feedback (max {max_concurrent} concurrent)")
    
    # Process scorecards in batches to avoid overwhelming the API
    results = []
    for i in range(0, len(scorecards), max_concurrent):
        batch = scorecards[i:i + max_concurrent]
        logger.info(f"Processing batch {i//max_concurrent + 1}/{(len(scorecards) + max_concurrent - 1)//max_concurrent} ({len(batch)} scorecards)")
        
        # Create tasks for this batch
        tasks = [
            _check_scorecard_for_feedback(api_client, account_id, scorecard, start_date, end_date)
            for scorecard in batch
        ]
        
        # Wait for all tasks in this batch to complete
        batch_results = await asyncio.gather(*tasks)
        
        # Filter out None results and add to results list
        results.extend([r for r in batch_results if r is not None])
    
    logger.info(f"Found {len(results)} scorecard(s) with feedback")
    return results

