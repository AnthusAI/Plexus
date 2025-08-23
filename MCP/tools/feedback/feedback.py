#!/usr/bin/env python3
"""
Feedback management tools for Plexus MCP Server
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Union, Optional
from io import StringIO
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


async def _get_paginated_feedback_with_items(
    client,
    scorecard_name: str,
    score_name: str,
    scorecard_id: str,
    score_id: str,
    account_id: str,
    days: int,
    initial_value: Optional[str] = None,
    final_value: Optional[str] = None,
    limit: int = 5,
    prioritize_edit_comments: bool = True,
    offset: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get paginated feedback items with nested item details.
    
    Returns:
        Dict with 'feedback_items', 'pagination', and 'context' keys
    """
    from datetime import datetime, timezone, timedelta
    import asyncio
    
    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Build GraphQL query for feedback items with item details
    query = """
    query ListFeedbackItemsWithItems(
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
                    accountId
                    externalId
                    text
                    identifiers
                    createdAt
                    updatedAt
                }
            }
            nextToken
        }
    }
    """
    
    # Prepare composite sort key for the GSI query using correct structure
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()
    
    # Handle offset-based vs token-based pagination
    # For offset-based pagination, we need to fetch more items to implement proper skipping
    if offset is not None:
        # Fetch extra items to accommodate the offset skip (even for offset=0)
        fetch_limit = (limit * 3) + offset  # Get enough items to skip offset and return limit
    else:
        fetch_limit = limit * 2  # Normal limit for legacy pagination
    
    variables = {
        "accountId": account_id,
        "composite_sk_condition": {
            "between": [
                {
                    "scorecardId": str(scorecard_id),
                    "scoreId": str(score_id),
                    "editedAt": start_date_str
                },
                {
                    "scorecardId": str(scorecard_id),
                    "scoreId": str(score_id),
                    "editedAt": end_date_str
                }
            ]
        },
        "limit": fetch_limit,
        "sortDirection": "DESC"  # Most recent first
    }
    
    # Legacy token-based pagination has been removed - only offset method supported
    
    # Debug logging for GraphQL query
    logger.info(f"[MCP DEBUG] GraphQL variables: {variables}")
    
    # Execute the query
    response = await asyncio.to_thread(client.execute, query, variables)
    
    logger.info(f"[MCP DEBUG] GraphQL response keys: {list(response.keys()) if response else 'None'}")
    if response and 'errors' in response:
        logger.error(f"[MCP DEBUG] GraphQL errors: {response.get('errors')}")
        raise Exception(f"GraphQL errors: {response.get('errors')}")
    
    if not response or 'listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt' not in response:
        logger.error(f"[MCP DEBUG] Unexpected response format: {response}")
        raise Exception("Unexpected response format from feedback query")
    
    result = response['listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt']
    raw_items = result.get('items', [])
    next_token = result.get('nextToken')
    
    logger.info(f"[MCP DEBUG] Retrieved {len(raw_items)} raw items from GraphQL")
    
    # Filter by initial_value and final_value if specified
    filtered_items = []
    for item_data in raw_items:
        if initial_value and item_data.get('initialAnswerValue') != initial_value:
            logger.info(f"[MCP DEBUG] Filtering out item: initial_value={item_data.get('initialAnswerValue')} != {initial_value}")
            continue
        if final_value and item_data.get('finalAnswerValue') != final_value:
            logger.info(f"[MCP DEBUG] Filtering out item: final_value={item_data.get('finalAnswerValue')} != {final_value}")
            continue
        filtered_items.append(item_data)
    
    logger.info(f"[MCP DEBUG] After value filtering: {len(filtered_items)} items (from {len(raw_items)} raw items)")
    
    # Sort and prioritize items with edit comments if requested
    if prioritize_edit_comments:
        # Sort so items with edit comments come first
        filtered_items.sort(key=lambda x: (
            bool(x.get('editCommentValue')),  # Items with edit comments first
            x.get('editedAt', '')  # Then by most recent
        ), reverse=True)
    
    # Apply offset-based pagination if offset is specified
    if offset is not None:
        # Skip 'offset' items and then take 'limit' items (works for offset=0 too)
        start_idx = offset
        end_idx = offset + limit
        page_items = filtered_items[start_idx:end_idx]
    else:
        # Legacy behavior - just take the first 'limit' items
        page_items = filtered_items[:limit]
    
    # Format the items with nested item details
    formatted_items = []
    for item_data in page_items:
        formatted_item = {
            "feedback_id": item_data.get('id'),
            "item_id": item_data.get('itemId'),
            "external_id": item_data.get('item', {}).get('externalId'),
            "initial_value": item_data.get('initialAnswerValue'),
            "final_value": item_data.get('finalAnswerValue'),
            "initial_explanation": item_data.get('initialCommentValue'),
            "final_explanation": item_data.get('finalCommentValue'),
            "edit_comment": item_data.get('editCommentValue'),
            "edited_at": item_data.get('editedAt'),
            "editor_name": item_data.get('editorName'),
            "is_agreement": item_data.get('isAgreement'),
            # Nested item details - this is the key addition
            "item_details": {
                "id": item_data.get('item', {}).get('id'),
                "external_id": item_data.get('item', {}).get('externalId'),
                "text": item_data.get('item', {}).get('text'),
                "identifiers": item_data.get('item', {}).get('identifiers'),
                "created_at": item_data.get('item', {}).get('createdAt'),
                "updated_at": item_data.get('item', {}).get('updatedAt')
            }
        }
        formatted_items.append(formatted_item)
    
    # Determine pagination information based on method used
    next_page_start_id = None
    has_next_page = False
    current_offset = offset if offset is not None else 0
    
    if offset is not None:
        # Offset-based pagination: check if there are more items after current page
        total_available = len(filtered_items)
        items_after_current_page = total_available - (current_offset + len(page_items))
        has_next_page = items_after_current_page > 0
        
        # For offset pagination, next_page_start_id contains the next offset value
        if has_next_page:
            next_offset = current_offset + limit
            next_page_start_id = str(next_offset)  # Convert to string for consistency
    # Legacy token-based pagination removed - offset method only
    
    # Pagination method is always offset now
    pagination_method = "offset"
    
    return {
        "context": {
            "scorecard_name": scorecard_name,
            "score_name": score_name,
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "account_id": account_id,
            "days": days,
            "filters": {
                "initial_value": initial_value,
                "final_value": final_value,
                "prioritize_edit_comments": prioritize_edit_comments
            },
            "pagination_method": pagination_method,
            "current_offset": current_offset,
            "total_in_page": len(formatted_items)
        },
        "feedback_items": formatted_items,
        "pagination": {
            "limit": limit,
            "has_next_page": has_next_page,
            "next_page_start_id": next_page_start_id,
            "current_offset": current_offset,
            "pagination_method": pagination_method
        }
    }


def register_feedback_tools(mcp: FastMCP):
    """Register feedback tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_feedback_analysis(
        scorecard_name: str,
        score_name: str,
        days: Union[int, float, str] = 14,
        output_format: str = "json"
    ) -> str:
        """
        Generate comprehensive feedback summary with confusion matrix, accuracy, and AC1 agreement.
        
        This tool provides an overview of feedback quality and should be run BEFORE using
        the 'plexus_feedback_find' tool to examine specific feedback items. 
        
        The summary includes:
        - Overall accuracy percentage
        - Gwet's AC1 agreement coefficient  
        - Confusion matrix showing prediction vs actual patterns
        - Precision and recall metrics
        - Class distribution analysis
        - Actionable recommendations for next steps
        
        Use this tool first to understand overall performance before drilling down
        into specific feedback segments with plexus_feedback_find.
        
        Args:
            scorecard_name (str): Name of the scorecard (partial match supported)
            score_name (str): Name of the score (partial match supported) 
            days (int): Number of days back to analyze (default: 14)
            output_format (str): Output format - "json" or "yaml" (default: "json")
        
        Returns:
            str: Comprehensive feedback summary with analysis and recommendations
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # DEBUG: Log what parameters we actually received
            logger.info(f"[MCP DEBUG] Received parameters - scorecard_name: '{scorecard_name}', score_name: '{score_name}', days: '{days}', output_format: '{output_format}'")
            
            # Convert string parameters to appropriate types
            try:
                days = int(float(str(days)))  # Handle both int and float strings
            except (ValueError, TypeError):
                return f"Error: Invalid days parameter: {days}. Must be a number."
            
            logger.info(f"[MCP] Generating feedback summary for '{score_name}' on '{scorecard_name}' (last {days} days)")
            
            try:
                from plexus.cli.feedback.feedback_service import FeedbackService
            except ImportError as e:
                return f"Error: Could not import FeedbackService: {e}. Core modules may not be available."
            
            # Get client and account using existing patterns
            from plexus.cli.shared.client_utils import create_client as create_dashboard_client
            from plexus.cli.report.utils import resolve_account_id_for_command
            from plexus.costs.cost_analysis import ScoreResultCostAnalyzer
            from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
            from plexus.costs.cost_analysis import ScoreResultCostAnalyzer
            from plexus.costs.cost_analysis import ScoreResultCostAnalyzer
            
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create Plexus client. Check API credentials."
            
            account_id = resolve_account_id_for_command(client, None)
            if not account_id:
                return "Error: Could not resolve account ID."
            
            # Use the same robust score-finding logic as find_plexus_score
            from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
            
            # Find scorecard using the robust resolver
            scorecard_id = resolve_scorecard_identifier(client, scorecard_name)
            if not scorecard_id:
                return f"Error: Scorecard not found: {scorecard_name}"
                
            # Get scorecard name and score details using the same approach as find_plexus_score
            scorecard_query = f"""
            query GetScorecardWithScores {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
                    key
                    sections {{
                        items {{
                            id
                            name
                            scores {{
                                items {{
                                    id
                                    name
                                    key
                                    externalId
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            response = client.execute(scorecard_query)
            if 'errors' in response:
                return f"Error querying scorecard: {response['errors']}"
                
            scorecard_data = response.get('getScorecard')
            if not scorecard_data:
                return f"Error: Could not retrieve scorecard data for '{scorecard_name}'"
            
            # Find score using the same robust matching as find_plexus_score
            score_match = None
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    # Use same matching criteria as find_plexus_score
                    if (score.get('id') == score_name or 
                        score.get('name', '').lower() == score_name.lower() or 
                        score.get('key') == score_name or 
                        score.get('externalId') == score_name or
                        score_name.lower() in score.get('name', '').lower()):
                        score_match = score
                        break
                if score_match:
                    break
            
            if not score_match:
                return f"Error: Score not found in scorecard '{scorecard_data['name']}': {score_name}"
            
            # Use the matched scorecard data
            scorecard_match = scorecard_data
            
            logger.info(f"[MCP] Found: {scorecard_match['name']} → {score_match['name']}")
            
            # Generate summary using the shared service
            summary_result = await FeedbackService.summarize_feedback(
                client=client,
                scorecard_name=scorecard_match['name'],
                score_name=score_match['name'],
                scorecard_id=scorecard_match['id'],
                score_id=score_match['id'],
                account_id=account_id,
                days=days
            )
            
            # Convert to dictionary for output
            result_dict = FeedbackService.format_summary_result_as_dict(summary_result)
            
            # Add command context
            result_dict["command_info"] = {
                "description": "Comprehensive feedback analysis with confusion matrix and agreement metrics",
                "tool": f"plexus_feedback_analysis(scorecard_name='{scorecard_name}', score_name='{score_name}', days={days}, output_format='{output_format}')"
            }
            
            # Output in requested format
            if output_format.lower() == 'yaml':
                import yaml
                from datetime import datetime
                # Add contextual comments for YAML
                yaml_comment = f"""# Feedback Summary Analysis
# Scorecard: {scorecard_match['name']}
# Score: {score_match['name']}
# Period: Last {days} days
# Generated: {datetime.now().isoformat()}
#
# This summary provides overview metrics that help identify which specific
# feedback segments to examine using plexus_feedback_find. Use the confusion
# matrix to understand error patterns and follow the recommendation for next steps.

"""
                yaml_output = yaml.dump(result_dict, default_flow_style=False, sort_keys=False)
                return yaml_comment + yaml_output
            else:
                import json
                return json.dumps(result_dict, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"[MCP] Error in plexus_feedback_analysis: {e}")
            import traceback
            logger.error(f"[MCP] Traceback: {traceback.format_exc()}")
            return f"Error generating feedback summary: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_feedback_analysis: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_feedback_find(
        scorecard_name: str,
        score_name: str,
        initial_value: Optional[str] = None,
        final_value: Optional[str] = None,
        limit: Optional[Union[int, float, str]] = 5,
        days: Optional[Union[int, float, str]] = 30,
        output_format: str = "json",
        prioritize_edit_comments: bool = True,
        offset: Optional[Union[int, float, str]] = None
    ) -> Union[str, Dict[str, Any]]:
        logger.error(f"🔥🔥🔥 FUNCTION START: plexus_feedback_find called with scorecard='{scorecard_name}', score='{score_name}'")
        
        # TEMPORARY FIX: Call the CLI directly since it works
        try:
            import subprocess
            import json
            
            cmd = [
                'python', '-m', 'plexus.cli', 'feedback', 'find',
                '--scorecard', scorecard_name,
                '--score', score_name,
                '--limit', str(limit or 1),
                '--days', str(days or 30),
                '--format', 'yaml'
            ]
            
            if initial_value:
                cmd.extend(['--initial-value', initial_value])
            if final_value:
                cmd.extend(['--final-value', final_value])
                
            logger.error(f"🔥 CALLING CLI: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
            
            if result.returncode == 0:
                logger.error(f"🔥 CLI SUCCESS: {result.stdout[:200]}...")
                return result.stdout
            else:
                logger.error(f"🔥 CLI FAILED: {result.stderr}")
                return f"CLI Error: {result.stderr}"
                
        except Exception as cli_error:
            logger.error(f"🔥 CLI EXCEPTION: {cli_error}")
            # Fall through to original logic
            pass
        """
        Find feedback items where human reviewers have corrected predictions. 
        This helps identify cases where score configurations need improvement.
        Results are paginated and include full item details nested within each feedback edit.
        
        Parameters:
        - scorecard_name: Name of the scorecard containing the score
        - score_name: Name of the specific score to search feedback for
        - initial_value: Optional filter for the original AI prediction value (e.g., "No", "Yes")
        - final_value: Optional filter for the corrected human value (e.g., "Yes", "No")
        - limit: Maximum number of feedback items to return per page (default: 5)
        - days: Number of days back to search (default: 30)
        - output_format: Output format - "json" or "yaml" (default: "json")
        - prioritize_edit_comments: Whether to prioritize feedback items with edit comments (default: True)
        - offset: Simple numeric offset for pagination - start at result #N (e.g., 0, 5, 10). Much simpler than next_page_start_id.
        
        Returns:
        - Paginated feedback items with correction details, edit comments, and nested item information
        - Each feedback item includes full item details (text, external_id, etc.) to eliminate need for separate item_info calls
        - If more results available, includes next_page_start_id for retrieving next page
        
        Pagination:
        - Results are paginated with limit items per page (default: 5)
        - SIMPLE METHOD: Use offset parameter (recommended for AI agents)
          - offset=0 for first page, offset=5 for second page, offset=10 for third page, etc.
          - Example: plexus_feedback_find(..., limit=5, offset=0) then plexus_feedback_find(..., limit=5, offset=5)
        """
        # Validate required parameters first
        if not scorecard_name or not scorecard_name.strip():
            return {
                "error": "Missing required parameter 'scorecard_name'. You MUST provide the scorecard name.",
                "example": "plexus_feedback_find(scorecard_name='Your Scorecard Name', score_name='Your Score Name', ...)",
                "help": "Use the exact scorecard_name from your experiment context."
            }
        
        if not score_name or not score_name.strip():
            return {
                "error": "Missing required parameter 'score_name'. You MUST provide the score name.",
                "example": "plexus_feedback_find(scorecard_name='Your Scorecard Name', score_name='Your Score Name', ...)",
                "help": "Use the exact score_name from your experiment context."
            }
        
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Try to import required modules directly
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
                from plexus.cli.feedback.feedback_service import FeedbackService
            except ImportError as e:
                return f"Error: Could not import required modules: {e}. Core modules may not be available."
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                logger.warning("Missing API credentials. Ensure .env file is loaded.")
                return "Error: Missing API credentials. Use --env-file to specify your .env file path."
            
            # Create the client
            try:
                client_stdout = StringIO()
                saved_stdout = sys.stdout
                sys.stdout = client_stdout
                
                try:
                    client = create_dashboard_client()
                finally:
                    client_output = client_stdout.getvalue()
                    if client_output:
                        logger.warning(f"Captured unexpected stdout during client creation in plexus_feedback_find: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Find the scorecard (accept id, key, name, externalId)
            scorecard_id = resolve_scorecard_identifier(client, scorecard_name)
            if not scorecard_id:
                return f"Error: Scorecard '{scorecard_name}' not found."

            # Find the score within the scorecard
            scorecard_query = f"""
            query GetScorecardForFeedback {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
                    sections {{
                        items {{
                            id
                            scores {{
                                items {{
                                    id
                                    name
                                    key
                                    externalId
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            scorecard_result = client.execute(scorecard_query)
            scorecard_data = scorecard_result.get('getScorecard')
            if not scorecard_data:
                return f"Error: Could not retrieve scorecard data for '{scorecard_name}'."

            # Find the specific score using the same robust matching as plexus_feedback_analysis
            found_score_id = None
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    # Use same matching criteria as plexus_feedback_analysis
                    if (score.get('id') == score_name or 
                        score.get('name', '').lower() == score_name.lower() or 
                        score.get('key') == score_name or 
                        score.get('externalId') == score_name or
                        score_name.lower() in score.get('name', '').lower()):
                        found_score_id = score['id']
                        break
                if found_score_id:
                    break

            if not found_score_id:
                return f"Error: Score '{score_name}' not found within scorecard '{scorecard_name}'."
            
            logger.error(f"🔥 MCP TOOL DEBUG: Resolved scorecard_id: {scorecard_id}")
            logger.error(f"🔥 MCP TOOL DEBUG: Resolved score_id: {found_score_id}")
            logger.error(f"🔥 MCP TOOL DEBUG: Search parameters: initial_value={initial_value}, final_value={final_value}, days={days}, limit={limit}")

            # Get account ID using the same method as feedback_summary
            try:
                from plexus.cli.report.utils import resolve_account_id_for_command
                account_id = resolve_account_id_for_command(client, None)
                if not account_id:
                    return "Error: Could not determine account ID for feedback query."
                logger.error(f"🔥 MCP TOOL DEBUG: Resolved account_id: {account_id}")
            except Exception as e:
                logger.error(f"Error getting account ID: {e}")
                return f"Error getting account ID: {e}"
            
            # Convert days to int if provided
            if days:
                try:
                    days_int = int(days)
                except (ValueError, TypeError):
                    return f"Error: Invalid days parameter '{days}'. Must be a number."
            else:
                days_int = 30  # Default to 30 days
                
            # Convert limit to int if provided
            limit_int = None
            if limit:
                try:
                    limit_int = int(limit)
                except (ValueError, TypeError):
                    return f"Error: Invalid limit parameter '{limit}'. Must be a number."
            
            # Use custom pagination logic with item details
            try:
                # Parse offset parameter if provided
                offset_int = None
                if offset is not None:
                    try:
                        offset_int = int(float(str(offset)))
                    except (ValueError, TypeError):
                        return f"Error: Invalid offset parameter '{offset}'. Must be a number."
                
                # Get feedback items with pagination and item details
                logger.info(f"[MCP DEBUG] Calling _get_paginated_feedback_with_items with:")
                logger.info(f"  scorecard_id={scorecard_id}, score_id={found_score_id}, account_id={account_id}")
                logger.info(f"  days={days_int}, initial_value={initial_value}, final_value={final_value}")
                logger.info(f"  limit={limit_int or 5}, offset={offset_int}")
                
                paginated_result = await _get_paginated_feedback_with_items(
                    client=client,
                    scorecard_name=scorecard_name,
                    score_name=score_name,
                    scorecard_id=scorecard_id,
                    score_id=found_score_id,
                    account_id=account_id,
                    days=days_int,
                    initial_value=initial_value,
                    final_value=final_value,
                    limit=limit_int or 5,
                    prioritize_edit_comments=prioritize_edit_comments,
                    offset=offset_int
                )
                
                logger.info(f"Retrieved {len(paginated_result['feedback_items'])} feedback items with item details")
                
            except Exception as e:
                logger.error(f"Error getting paginated feedback: {e}")
                return f"Error retrieving feedback items: {e}"

            if not paginated_result['feedback_items']:
                filter_desc = []
                if initial_value:
                    filter_desc.append(f"initial value '{initial_value}'")
                if final_value:
                    filter_desc.append(f"final value '{final_value}'")
                if filter_desc:
                    filter_text = f" with {' and '.join(filter_desc)}"
                else:
                    filter_text = ""
                return f"No feedback items found for score '{score_name}' in scorecard '{scorecard_name}'{filter_text} in the last {days_int} days."

            # Format paginated result
            result_dict = paginated_result
            
            if output_format.lower() == "yaml":
                import yaml
                return yaml.dump(result_dict, default_flow_style=False, sort_keys=False)
            else:
                # Return the same JSON structure as the CLI tool would output
                return result_dict
            
        except Exception as e:
            logger.error(f"Error finding feedback items: {str(e)}", exc_info=True)
            return f"Error finding feedback items: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_feedback_find: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout