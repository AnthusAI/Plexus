#!/usr/bin/env python3
"""
Shared utility functions for Plexus MCP tools
"""
import os
import sys
import logging
from io import StringIO
from urllib.parse import urljoin
from typing import Optional, Dict, Any, List
from .setup import (
    PLEXUS_CORE_AVAILABLE, DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_KEY, ACCOUNT_CACHE,
    create_dashboard_client, resolve_account_identifier, logger
)

def load_env_file(env_dir=None):
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        if env_dir:
            dotenv_path = os.path.join(env_dir, '.env')
            logger.info(f"Attempting to load .env file from specified directory: {dotenv_path}")
            if os.path.isfile(dotenv_path):
                loaded = load_dotenv(dotenv_path=dotenv_path, override=True)
                if loaded:
                    logger.info(f".env file loaded successfully from {dotenv_path}")
                    logger.info(f"Environment contains PLEXUS_API_URL: {'Yes' if os.environ.get('PLEXUS_API_URL') else 'No'}")
                    logger.info(f"Environment contains PLEXUS_API_KEY: {'Yes' if os.environ.get('PLEXUS_API_KEY') else 'No'}")
                    return True
                else:
                    logger.warning(f"Failed to load .env file from {dotenv_path}")
            else:
                logger.warning(f"No .env file found at {dotenv_path}")
        return False
    except ImportError:
        logger.warning("python-dotenv not installed, can't load .env file")
        return False

def initialize_default_account():
    """Initialize the default account ID from the environment variable PLEXUS_ACCOUNT_KEY."""
    global DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_KEY
    
    # Get account key from environment
    account_key = os.environ.get('PLEXUS_ACCOUNT_KEY')
    if not account_key:
        logger.warning("PLEXUS_ACCOUNT_KEY environment variable not set")
        return
    
    DEFAULT_ACCOUNT_KEY = account_key
    
    # Only attempt to resolve if we have the client available
    if not PLEXUS_CORE_AVAILABLE:
        logger.warning("Plexus core not available, can't resolve default account ID")
        return
    
    # Create dashboard client and resolve account ID
    try:
        client = create_dashboard_client()
        if not client:
            logger.warning("Could not create dashboard client to resolve default account")
            return
        
        account_id = resolve_account_identifier(client, account_key)
        if not account_id:
            logger.warning(f"Could not resolve account ID for key: {account_key}")
            return
        
        DEFAULT_ACCOUNT_ID = account_id
        ACCOUNT_CACHE[account_key] = account_id
        logger.info(f"Default account ID initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing default account ID: {str(e)}", exc_info=True)

def get_default_account_id():
    """Get the default account ID, resolving it if necessary."""
    global DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_KEY
    
    # If already resolved, return it
    if DEFAULT_ACCOUNT_ID:
        return DEFAULT_ACCOUNT_ID
    
    # Try to resolve it now
    initialize_default_account()
    return DEFAULT_ACCOUNT_ID

def resolve_account_id_with_cache(client, identifier):
    """Resolve an account identifier to its ID, using cache when possible."""
    if not identifier:
        return get_default_account_id()
    
    # Check cache first
    if identifier in ACCOUNT_CACHE:
        return ACCOUNT_CACHE[identifier]
    
    # Resolve and cache
    account_id = resolve_account_identifier(client, identifier)
    if account_id:
        ACCOUNT_CACHE[identifier] = account_id
    
    return account_id

def get_plexus_url(path: str) -> str:
    """
    Safely concatenates the PLEXUS_APP_URL with the provided path.
    Handles cases where base URL may or may not have trailing slashes
    and path may or may not have leading slashes.
    
    Parameters:
    - path: The URL path to append to the base URL
    
    Returns:
    - Full URL string
    """
    base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
    # Ensure base URL ends with a slash for urljoin to work correctly
    if not base_url.endswith('/'):
        base_url += '/'
    # Strip leading slash from path if present to avoid double slashes
    path = path.lstrip('/')
    return urljoin(base_url, path)

def get_report_url(report_id: str) -> str:
    """
    Generates a URL for viewing a report in the dashboard.
    
    Parameters:
    - report_id: The ID of the report
    
    Returns:
    - Full URL to the report in the dashboard
    """
    return get_plexus_url(f"lab/reports/{report_id}")

def get_item_url(item_id: str) -> str:
    """
    Generates a URL for viewing an item in the dashboard.
    
    Parameters:
    - item_id: The ID of the item
    
    Returns:
    - Full URL to the item in the dashboard
    """
    return get_plexus_url(f"lab/items/{item_id}")

def get_task_url(task_id: str) -> str:
    """
    Generates a URL for viewing a task in the dashboard.
    
    Parameters:
    - task_id: The ID of the task
    
    Returns:
    - Full URL to the task in the dashboard
    """
    return get_plexus_url(f"lab/tasks/{task_id}")

async def get_score_results_for_item(item_id: str, client) -> List[Dict[str, Any]]:
    """
    Helper function to get all score results for a specific item, sorted by updatedAt descending.
    This mirrors the functionality from the CLI ItemCommands.get_score_results_for_item function.
    """
    try:
        from plexus.dashboard.api.models.score_result import ScoreResult
        from datetime import datetime
        
        query = f"""
        query ListScoreResultByItemId($itemId: String!) {{
            listScoreResultByItemId(itemId: $itemId) {{
                items {{
                    {ScoreResult.fields()}
                    updatedAt
                    createdAt
                }}
            }}
        }}
        """
        
        result = client.execute(query, {'itemId': item_id})
        score_results_data = result.get('listScoreResultByItemId', {}).get('items', [])
        
        # Convert to ScoreResult objects and add timestamp fields manually
        score_results = []
        for sr_data in score_results_data:
            score_result = ScoreResult.from_dict(sr_data, client)
            
            # Convert to dictionary format and include timestamps
            sr_dict = {
                'id': score_result.id,
                'value': score_result.value,
                'explanation': getattr(score_result, 'explanation', None),
                'confidence': score_result.confidence,
                'correct': score_result.correct,
                'itemId': score_result.itemId,
                'scoreId': getattr(score_result, 'scoreId', None),
                'scoreName': score_result.scoreName,  # Include the score name
                'scoreVersionId': getattr(score_result, 'scoreVersionId', None),
                'scorecardId': score_result.scorecardId,
                'evaluationId': score_result.evaluationId,
                'scoringJobId': getattr(score_result, 'scoringJobId', None),
                'metadata': score_result.metadata,
                'trace': getattr(score_result, 'trace', None)
            }
            
            # Add timestamp fields
            if 'updatedAt' in sr_data:
                if isinstance(sr_data['updatedAt'], str):
                    updatedAt = datetime.fromisoformat(sr_data['updatedAt'].replace('Z', '+00:00'))
                    sr_dict['updatedAt'] = updatedAt.isoformat()
                else:
                    sr_dict['updatedAt'] = sr_data['updatedAt']
                    
            if 'createdAt' in sr_data:
                if isinstance(sr_data['createdAt'], str):
                    createdAt = datetime.fromisoformat(sr_data['createdAt'].replace('Z', '+00:00'))
                    sr_dict['createdAt'] = createdAt.isoformat()
                else:
                    sr_dict['createdAt'] = sr_data['createdAt']
            
            score_results.append(sr_dict)
        
        # Sort by updatedAt in Python since GraphQL doesn't support it
        score_results.sort(
            key=lambda sr: sr.get('updatedAt', '1970-01-01T00:00:00'),
            reverse=True
        )
        
        return score_results
        
    except Exception as e:
        logger.error(f"Error getting score results for item {item_id}: {str(e)}", exc_info=True)
        return []

async def get_feedback_items_for_item(item_id: str, client) -> List[Dict[str, Any]]:
    """
    Helper function to get all feedback items for a specific item, sorted by updatedAt descending.
    This mirrors the functionality from the CLI ItemCommands.get_feedback_items_for_item function.
    """
    try:
        from plexus.dashboard.api.models.feedback_item import FeedbackItem
        from datetime import datetime
        
        # Use the FeedbackItem.list method with filtering
        feedback_items, _ = FeedbackItem.list(
            client=client,
            filter={'itemId': {'eq': item_id}},
            limit=1000
        )
        
        # Convert to dictionary format and sort by updatedAt descending
        feedback_items_list = []
        for fi in feedback_items:
            fi_dict = {
                'id': fi.id,
                'accountId': fi.accountId,
                'scorecardId': fi.scorecardId,
                'scoreId': fi.scoreId,
                'itemId': fi.itemId,
                'cacheKey': fi.cacheKey,
                'initialAnswerValue': fi.initialAnswerValue,
                'finalAnswerValue': fi.finalAnswerValue,
                'initialCommentValue': fi.initialCommentValue,
                'finalCommentValue': fi.finalCommentValue,
                'editCommentValue': fi.editCommentValue,
                'isAgreement': fi.isAgreement,
                'editorName': fi.editorName,
                'editedAt': fi.editedAt.isoformat() if hasattr(fi.editedAt, 'isoformat') and fi.editedAt else fi.editedAt,
                'createdAt': fi.createdAt.isoformat() if hasattr(fi.createdAt, 'isoformat') and fi.createdAt else fi.createdAt,
                'updatedAt': fi.updatedAt.isoformat() if hasattr(fi.updatedAt, 'isoformat') and fi.updatedAt else fi.updatedAt,
            }
            feedback_items_list.append(fi_dict)
        
        # Sort by updatedAt descending
        feedback_items_list.sort(
            key=lambda fi: fi.get('updatedAt', '1970-01-01T00:00:00'),
            reverse=True
        )
        
        return feedback_items_list
        
    except Exception as e:
        logger.error(f"Error getting feedback items for item {item_id}: {str(e)}", exc_info=True)
        return []

async def find_score_instance(scorecard_identifier: str, score_identifier: str, client) -> Dict[str, Any]:
    """
    Helper function to find a Score instance from scorecard and score identifiers.
    
    Returns a dict containing:
    - success: bool
    - score: Score instance (if successful)
    - scorecard_name: str (if successful)
    - scorecard_id: str (if successful)
    - error: str (if failed)
    """
    try:
        from plexus.dashboard.api.models.score import Score
        from plexus.dashboard.api.models.scorecard import Scorecard
        from .setup import resolve_scorecard_identifier
        
        # Resolve scorecard identifier
        scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
        if not scorecard_id:
            return {
                "success": False,
                "error": f"Scorecard '{scorecard_identifier}' not found."
            }

        # Get scorecard name
        scorecard = Scorecard.get_by_id(scorecard_id, client)
        if not scorecard:
            return {
                "success": False,
                "error": f"Could not retrieve scorecard data for ID '{scorecard_id}'."
            }

        # Find the score within the scorecard
        scorecard_query = f"""
        query GetScorecardForScore {{
            getScorecard(id: "{scorecard_id}") {{
                sections {{
                    items {{
                        id
                        scores {{
                            items {{
                                id
                                name
                                key
                                externalId
                                type
                                order
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        result = client.execute(scorecard_query)
        scorecard_data = result.get('getScorecard')
        if not scorecard_data:
            return {
                "success": False,
                "error": f"Could not retrieve scorecard sections for '{scorecard_identifier}'."
            }

        # Find the specific score
        found_score_data = None
        found_section_id = None
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score_data in section.get('scores', {}).get('items', []):
                if (score_data.get('id') == score_identifier or 
                    score_data.get('name') == score_identifier or 
                    score_data.get('key') == score_identifier or 
                    score_data.get('externalId') == score_identifier):
                    found_score_data = score_data
                    found_section_id = section['id']
                    break
            if found_score_data:
                break

        if not found_score_data:
            return {
                "success": False,
                "error": f"Score '{score_identifier}' not found within scorecard '{scorecard_identifier}'."
            }

        # Create Score instance
        score = Score(
            id=found_score_data['id'],
            name=found_score_data['name'],
            key=found_score_data['key'],
            externalId=found_score_data['externalId'],
            type=found_score_data['type'],
            order=found_score_data['order'],
            sectionId=found_section_id,
            client=client
        )

        return {
            "success": True,
            "score": score,
            "scorecard_name": scorecard.name,
            "scorecard_id": scorecard_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error finding score: {str(e)}"
        }

def capture_stdout(func):
    """Decorator to capture stdout during tool execution"""
    def wrapper(*args, **kwargs):
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during {func.__name__}: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout
    
    return wrapper