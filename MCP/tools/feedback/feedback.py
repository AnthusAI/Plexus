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


def register_feedback_tools(mcp: FastMCP):
    """Register feedback tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_feedback_summary(
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
            
            # Try to import required modules directly (don't rely on global PLEXUS_CORE_AVAILABLE)
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
                "tool": f"plexus_feedback_summary(scorecard_name='{scorecard_name}', score_name='{score_name}', days={days}, output_format='{output_format}')",
                "next_steps": result_dict["recommendation"]
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
            logger.error(f"[MCP] Error in plexus_feedback_summary: {e}")
            import traceback
            logger.error(f"[MCP] Traceback: {traceback.format_exc()}")
            return f"Error generating feedback summary: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_feedback_summary: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_feedback_find(
        scorecard_name: str,
        score_name: str,
        initial_value: Optional[str] = None,
        final_value: Optional[str] = None,
        limit: Optional[Union[int, float, str]] = 10,
        days: Optional[Union[int, float, str]] = 30,
        output_format: str = "json",
        prioritize_edit_comments: bool = True
    ) -> Union[str, Dict[str, Any]]:
        """
        Find feedback items where human reviewers have corrected predictions. 
        This helps identify cases where score configurations need improvement.
        
        Parameters:
        - scorecard_name: Name of the scorecard containing the score
        - score_name: Name of the specific score to search feedback for
        - initial_value: Optional filter for the original AI prediction value (e.g., "No", "Yes")
        - final_value: Optional filter for the corrected human value (e.g., "Yes", "No")
        - limit: Maximum number of feedback items to return (default: 10)
        - days: Number of days back to search (default: 30)
        - output_format: Output format - "json" or "yaml" (default: "json")
        - prioritize_edit_comments: Whether to prioritize feedback items with edit comments (default: True)
        
        Returns:
        - Feedback items with correction details, edit comments, and item information
        """
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

            # Find the specific score
            found_score_id = None
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    if (score.get('name') == score_name or 
                        score.get('key') == score_name or 
                        score.get('id') == score_name or 
                        score.get('externalId') == score_name):
                        found_score_id = score['id']
                        break
                if found_score_id:
                    break

            if not found_score_id:
                return f"Error: Score '{score_name}' not found within scorecard '{scorecard_name}'."

            # Get account ID using the same method as feedback_summary
            try:
                from plexus.cli.report.utils import resolve_account_id_for_command
                account_id = resolve_account_id_for_command(client, None)
                if not account_id:
                    return "Error: Could not determine account ID for feedback query."
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
            
            # Use the shared FeedbackService for consistent behavior with CLI
            try:
                result = await FeedbackService.search_feedback(
                    client=client,
                    scorecard_name=scorecard_name,
                    score_name=score_name,
                    scorecard_id=scorecard_id,
                    score_id=found_score_id,
                    account_id=account_id,
                    days=days_int,
                    initial_value=initial_value,
                    final_value=final_value,
                    limit=limit_int,
                    prioritize_edit_comments=prioritize_edit_comments
                )
                
                logger.info(f"Retrieved {result.context.total_found} feedback items using shared service")
                
            except Exception as e:
                logger.error(f"Error using FeedbackService: {e}")
                return f"Error retrieving feedback items: {e}"

            if not result.feedback_items:
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

            # Format output using the shared service - same structure as CLI tool
            result_dict = FeedbackService.format_search_result_as_dict(result)
            
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