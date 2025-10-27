#!/usr/bin/env python3
"""
Item management tools for Plexus MCP Server
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Union, Optional
from io import StringIO
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_item_tools(mcp: FastMCP):
    """Register item tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_item_last(
        minimal: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Gets the most recent item for the default account, including score results and feedback items by default.
        
        Parameters:
        - minimal: If True, returns minimal info without score results and feedback items (optional, default: False)
        
        Returns:
        - Detailed information about the most recent item
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Import plexus modules inside function to keep startup fast
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.dashboard.api.models.item import Item
                from plexus.dashboard.api.models.score_result import ScoreResult
                from plexus.cli.report.utils import resolve_account_id_for_command
            except ImportError as e:
                logger.error(f"ImportError: {str(e)}", exc_info=True)
                return f"Error: Failed to import Plexus modules: {str(e)}"
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return "Error: Missing API credentials. API_URL or API_KEY not set in environment."
            
            # Create the client
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create dashboard client."

            # Get the default account ID
            account_id = resolve_account_id_for_command(client, None)
            if not account_id:
                return "Error: Could not determine default account ID. Please check that PLEXUS_ACCOUNT_KEY is set in environment."
                
            logger.info(f"Getting latest item for account: {account_id}")
            
            # Use the GSI for proper ordering to get the most recent item
            query = f"""
            query ListItemByAccountIdAndCreatedAt($accountId: String!) {{
                listItemByAccountIdAndCreatedAt(accountId: $accountId, sortDirection: DESC, limit: 1) {{
                    items {{
                        {Item.fields()}
                    }}
                }}
            }}
            """
            
            response = client.execute(query, {'accountId': account_id})
            
            if 'errors' in response:
                error_details = json.dumps(response['errors'], indent=2)
                logger.error(f"Dashboard query returned errors: {error_details}")
                return f"Error from Dashboard query: {error_details}"
            
            items = response.get('listItemByAccountIdAndCreatedAt', {}).get('items', [])
            
            if not items:
                return "No items found for this account."
                
            # Get the most recent item
            item_data = items[0]
            item = Item.from_dict(item_data, client)
            
            # Convert item to dictionary format
            item_dict = {
                'id': item.id,
                'accountId': item.accountId,
                'evaluationId': item.evaluationId,
                'scoreId': item.scoreId,
                'description': item.description,
                'externalId': item.externalId,
                'isEvaluation': item.isEvaluation,
                'createdByType': item.createdByType,
                'metadata': item.metadata,
                'identifiers': item.identifiers,
                'attachedFiles': item.attachedFiles,
                'createdAt': item.createdAt.isoformat() if item.createdAt else None,
                'updatedAt': item.updatedAt.isoformat() if item.updatedAt else None,
                'url': _get_item_url(item.id)
            }
            
            # Get score results and feedback items by default (unless minimal mode)
            if not minimal:
                score_results = await _get_score_results_for_item(item.id, client)
                item_dict['scoreResults'] = score_results
                
                feedback_items = await _get_feedback_items_for_item(item.id, client)
                item_dict['feedbackItems'] = feedback_items
            
            logger.info(f"Successfully retrieved latest item: {item.id}")
            return item_dict
            
        except Exception as e:
            logger.error(f"Error getting latest item: {str(e)}", exc_info=True)
            return f"Error getting latest item: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during get_latest_plexus_item: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_item_info(
        item_id: str,
        minimal: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Gets detailed information about a specific item by its ID or external identifier, including score results and feedback items by default.
        
        Parameters:
        - item_id: The unique ID of the item OR an external identifier value (e.g., "277430500")
        - minimal: If True, returns minimal info without score results and feedback items (optional, default: False)
        
        Returns:
        - Detailed information about the item including text content, metadata, identifiers, and timestamps
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Import plexus modules inside function to keep startup fast
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.dashboard.api.models.item import Item
                from plexus.dashboard.api.models.score_result import ScoreResult
                from plexus.utils.identifier_search import find_item_by_identifier
            except ImportError as e:
                logger.error(f"ImportError: {str(e)}", exc_info=True)
                return f"Error: Failed to import Plexus modules: {str(e)}"
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return "Error: Missing API credentials. API_URL or API_KEY not set in environment."
            
            # Create the client
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create dashboard client."

            logger.info(f"Getting item details for ID/identifier: {item_id}")
            
            item = None
            lookup_method = "unknown"
            
            # Try direct ID lookup first
            try:
                item = Item.get_by_id(item_id, client)
                if item:
                    lookup_method = "direct_id"
                    logger.info(f"Found item by direct ID lookup: {item_id}")
            except ValueError:
                # Not found by ID, continue to identifier search
                logger.info(f"Item not found by direct ID, trying identifier search for: {item_id}")
            except Exception as e:
                logger.warning(f"Error in direct ID lookup: {str(e)}")
            
            # If direct ID lookup failed, try identifier-based lookup
            if not item:
                default_account_id = _get_default_account_id()
                if default_account_id:
                    try:
                        item = find_item_by_identifier(item_id, default_account_id, client)
                        if item:
                            lookup_method = "identifier_search"
                            logger.info(f"Found item by identifier search: {item.id} (identifier: {item_id})")
                    except Exception as e:
                        logger.warning(f"Error in identifier search: {str(e)}")
            
            # If still not found, try Identifiers table GSI lookup as final fallback
            if not item:
                default_account_id = _get_default_account_id()
                if default_account_id:
                    try:
                        # Use the Identifiers table GSI to find items by identifier value
                        query = """
                        query GetIdentifierByAccountAndValue($accountId: String!, $value: String!) {
                            listIdentifierByAccountIdAndValue(
                                accountId: $accountId,
                                value: {eq: $value},
                                limit: 1
                            ) {
                                items {
                                    itemId
                                    name
                                    value
                                    url
                                    position
                                    item {
                                        id
                                        accountId
                                        evaluationId
                                        scoreId
                                        description
                                        externalId
                                        isEvaluation
                                        text
                                        metadata
                                        identifiers
                                        attachedFiles
                                        createdAt
                                        updatedAt
                                    }
                                }
                            }
                        }
                        """
                        
                        result = client.execute(query, {
                            'accountId': default_account_id,
                            'value': item_id
                        })
                        
                        if result and 'listIdentifierByAccountIdAndValue' in result:
                            identifiers = result['listIdentifierByAccountIdAndValue'].get('items', [])
                            if identifiers:
                                identifier_data = identifiers[0]
                                item_data = identifier_data.get('item', {})
                                
                                if item_data:
                                    # Create a mock Item object from the data
                                    class MockItem:
                                        def __init__(self, data):
                                            for key, value in data.items():
                                                setattr(self, key, value)
                                            # Handle datetime parsing
                                            if hasattr(self, 'createdAt') and self.createdAt:
                                                from datetime import datetime
                                                try:
                                                    self.createdAt = datetime.fromisoformat(self.createdAt.replace('Z', '+00:00'))
                                                except:
                                                    pass
                                            if hasattr(self, 'updatedAt') and self.updatedAt:
                                                from datetime import datetime
                                                try:
                                                    self.updatedAt = datetime.fromisoformat(self.updatedAt.replace('Z', '+00:00'))
                                                except:
                                                    pass
                                    
                                    item = MockItem(item_data)
                                    lookup_method = f"identifiers_table_gsi (name: {identifier_data.get('name', 'N/A')})"
                                    logger.info(f"Found item by Identifiers table GSI: {item.id} (identifier: {item_id})")
                        
                    except Exception as e:
                        logger.warning(f"Error in Identifiers table GSI lookup: {str(e)}")
            
            if not item:
                return f"Item not found: {item_id} (tried direct ID, identifier search, and external ID lookup)"
            
            try:
                # Convert item to dictionary format with intelligent truncation
                def truncate_field(value, field_name, max_chars=5000):
                    """Truncate large text fields to prevent massive responses."""
                    if isinstance(value, str) and len(value) > max_chars:
                        truncated = value[:max_chars]
                        return f"{truncated}... (truncated from {len(value):,} to {max_chars:,} chars)"
                    return value
                
                item_dict = {
                    'id': item.id,
                    'accountId': item.accountId,
                    'evaluationId': item.evaluationId,
                    'scoreId': item.scoreId,
                    'description': truncate_field(item.description, 'description', 1000),
                    'externalId': item.externalId,
                    'isEvaluation': item.isEvaluation,
                    'createdByType': item.createdByType,
                    'text': truncate_field(item.text, 'text', 5000),  # Truncate large text content
                    'metadata': item.metadata,  # Keep metadata as-is for now
                    'identifiers': item.identifiers,
                    'attachedFiles': item.attachedFiles,
                    'createdAt': item.createdAt.isoformat() if hasattr(item.createdAt, 'isoformat') else item.createdAt,
                    'updatedAt': item.updatedAt.isoformat() if hasattr(item.updatedAt, 'isoformat') else item.updatedAt,
                    'url': _get_item_url(item.id),
                    'lookupMethod': lookup_method  # Include how the item was found for debugging
                }
                
                # Get score results and feedback items by default (unless minimal mode)
                if not minimal:
                    score_results = await _get_score_results_for_item(item.id, client)
                    item_dict['scoreResults'] = score_results
                    
                    feedback_items = await _get_feedback_items_for_item(item.id, client)
                    item_dict['feedbackItems'] = feedback_items
                
                logger.info(f"Successfully retrieved item details: {item.id} (lookup method: {lookup_method})")
                return item_dict
                
            except Exception as e:
                logger.error(f"Error processing item {item.id}: {str(e)}", exc_info=True)
                return f"Error processing item {item.id}: {str(e)}"
            
        except Exception as e:
            logger.error(f"Error getting item details for ID/identifier '{item_id}': {str(e)}", exc_info=True)
            return f"Error getting item details: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during get_plexus_item_details: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout


async def _get_score_results_for_item(item_id: str, client) -> List[Dict[str, Any]]:
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

            # Extract and surface cost if present (stored in metadata or as top-level field)
            try:
                cost_payload = None
                # Prefer explicit field if API starts returning it
                if isinstance(sr_data, dict) and 'cost' in sr_data and sr_data['cost'] is not None:
                    cost_payload = sr_data['cost']
                # Fallback to metadata.cost
                if cost_payload is None and isinstance(sr_dict.get('metadata'), dict):
                    cost_payload = sr_dict['metadata'].get('cost')
                if cost_payload is not None:
                    sr_dict['cost'] = cost_payload
            except Exception:
                # Do not fail item fetch on cost extraction failure
                pass
            
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


async def _get_feedback_items_for_item(item_id: str, client) -> List[Dict[str, Any]]:
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


def _get_item_url(item_id: str) -> str:
    """
    Generates a URL for viewing an item in the dashboard.
    
    Parameters:
    - item_id: The ID of the item
    
    Returns:
    - Full URL to the item in the dashboard
    """
    from urllib.parse import urljoin
    
    base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
    # Ensure base URL ends with a slash for urljoin to work correctly
    if not base_url.endswith('/'):
        base_url += '/'
    # Strip leading slash from path if present to avoid double slashes
    path = f"lab/items/{item_id}".lstrip('/')
    return urljoin(base_url, path)


def _get_default_account_id():
    """Get the default account ID, resolving it if necessary."""
    try:
        # Import at runtime to avoid circular imports
        from plexus.cli.report.utils import resolve_account_id_for_command
        from plexus.cli.shared.client_utils import create_client as create_dashboard_client
        
        client = create_dashboard_client()
        if client:
            return resolve_account_id_for_command(client, None)
        return None
    except Exception as e:
        logger.warning(f"Error getting default account ID: {str(e)}")
        return None