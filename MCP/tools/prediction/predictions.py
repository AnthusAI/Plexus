#!/usr/bin/env python3
"""
Prediction tools for Plexus MCP Server
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Union, Optional
from io import StringIO
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_prediction_tools(mcp: FastMCP):
    """Register prediction tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_predict(
        scorecard_name: str,
        score_name: str,
        item_id: Optional[str] = None,
        item_ids: Optional[str] = None,
        include_input: bool = False,
        include_trace: bool = False,
        output_format: str = "json",
        no_cache: bool = False,
        yaml_only: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Run predictions on one or more items using a specific score configuration.
        This helps test score behavior and validate improvements.
        
        Parameters:
        - scorecard_name: Name of the scorecard containing the score
        - score_name: Name of the specific score to run predictions with
        - item_id: ID of a single item to predict on (mutually exclusive with item_ids)
        - item_ids: Comma-separated list of item IDs to predict on (mutually exclusive with item_id)
        - include_input: Whether to include the original input text and metadata in output (default: False)  
        - include_trace: Whether to include detailed execution trace for debugging (default: False)
        - output_format: Output format - "json" or "yaml" (default: "json")
        - no_cache: If True, disable local caching entirely (always fetch from API) (default: False)
        - yaml_only: If True, load only from local YAML files without API calls (default: False)
        
        Returns:
        - Prediction results with scores, explanations, and optional input/trace data
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Validate input parameters
            if not item_id and not item_ids:
                return "Error: Either item_id or item_ids must be provided."
            if item_id and item_ids:
                return "Error: Cannot specify both item_id and item_ids. Use one or the other."
            if no_cache and yaml_only:
                return "Error: Cannot specify both no_cache and yaml_only. Use one or the other."
            
            # Try to import required modules directly
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
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
                        logger.warning(f"Captured unexpected stdout during client creation in plexus_predict: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Find the scorecard
            scorecard_id = resolve_scorecard_identifier(client, scorecard_name)
            if not scorecard_id:
                return f"Error: Scorecard '{scorecard_name}' not found."

            # Find the score within the scorecard
            scorecard_query = f"""
            query GetScorecardForPrediction {{
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
                                    championVersionId
                                    isDisabled
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

            # Resolve the specific score using CLI resolver (accept id, key, name, externalId)
            resolved_score = None
            try:
                from plexus.cli.shared.identifier_resolution import resolve_score_identifier as _resolve_score_identifier
                resolved_score_id = _resolve_score_identifier(client, scorecard_id, score_name)
            except Exception:
                resolved_score_id = None

            # Scan scorecard to select the resolved score (or match by flexible fields if resolver unavailable)
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    if (
                        (resolved_score_id and score.get('id') == resolved_score_id) or
                        score.get('id') == score_name or
                        score.get('externalId') == score_name or
                        score.get('key') == score_name or
                        score.get('name') == score_name
                    ):
                        resolved_score = score
                        break
                if resolved_score:
                    break

            if not resolved_score:
                return f"Error: Score '{score_name}' not found within scorecard '{scorecard_name}'."

            # Prepare item IDs list (raw identifiers)
            if item_id:
                target_item_ids = [item_id]
            else:
                target_item_ids = [id.strip() for id in item_ids.split(',')]

            # Resolve raw identifiers to canonical item UUIDs using CLI resolver (accepts UUID, externalId, or other identifiers)
            try:
                from plexus.dashboard.api.models.account import Account as _Account
                from plexus.cli.shared.identifier_resolution import resolve_item_identifier as _resolve_item_identifier
                # Derive account_id once (prefer env account key when available)
                account_id = None
                try:
                    account = _Account.list_by_key(key="call-criteria", client=client)
                    if account:
                        account_id = account.id
                except Exception:
                    account_id = None

                resolved_ids = []
                for raw_id in target_item_ids:
                    try:
                        resolved_id = _resolve_item_identifier(client, raw_id, account_id)
                    except Exception:
                        resolved_id = None
                    resolved_ids.append(resolved_id or raw_id)
                target_item_ids = resolved_ids
            except Exception as _resolve_err:
                logger.warning(f"Item identifier resolution skipped due to error: {_resolve_err}")

            # Validate that all items exist and get their data
            prediction_results_list = []
            
            try:
                for target_id in target_item_ids:
                    try:
                        # Get item details
                        item_query = f"""
                    query GetItem {{
                        getItem(id: "{target_id}") {{
                            id
                            description
                            metadata
                            attachedFiles
                            externalId
                            createdAt
                            updatedAt
                        }}
                    }}
                    """
                        
                        item_result = client.execute(item_query)
                        item_data = item_result.get('getItem')
                        
                        if not item_data:
                            prediction_results_list.append({
                                "item_id": target_id,
                                "error": f"Item '{target_id}' not found"
                            })
                            continue

                        # Call the actual prediction service using the shared CLI implementation
                        logger.info(f"Running actual prediction for item '{target_id}' with score '{score_name}'")
                        
                        try:
                            # Get the item text content for prediction
                            item_text = item_data.get('text', '') or item_data.get('description', '')
                            if not item_text:
                                raise Exception("No text content found in item text or description fields")
                            
                            # Parse metadata from JSON string if needed
                            metadata_raw = item_data.get('metadata', {})
                            if isinstance(metadata_raw, str):
                                try:
                                    import json
                                    metadata = json.loads(metadata_raw)
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse metadata JSON: {metadata_raw}")
                                    metadata = {}
                            else:
                                metadata = metadata_raw
                            
                            # Use the canonical Scorecard dependency system for all predictions
                            # This ensures consistent behavior with CLI, evaluations, and production
                            # IMPORTANT: Do not call Scorecard.load() here (not available in this branch).
                            # Instead, reuse the CLI loaders that support API-first and YAML-only modes.

                            use_cache = not no_cache
                            cache_mode = "YAML-only" if yaml_only else ("no-cache" if no_cache else "default")
                            logger.info(f"Using canonical Scorecard system to predict '{score_name}' from '{scorecard_name}' with {cache_mode} mode")

                            # Defer imports to runtime to avoid heavy module import on server startup
                            if yaml_only:
                                logger.info("Loading scorecard from YAML files for dependency resolution (CLI-compatible path)")
                                from plexus.cli.evaluation.evaluations import load_scorecard_from_yaml_files
                                scorecard_instance = load_scorecard_from_yaml_files(scorecard_name, score_names=[score_name])
                            else:
                                logger.info("Loading scorecard from API for dependency resolution (CLI-compatible path)")
                                from plexus.cli.evaluation.evaluations import load_scorecard_from_api
                                scorecard_instance = load_scorecard_from_api(scorecard_name, score_names=[score_name], use_cache=use_cache)
                            
                            # Use the battle-tested score_entire_text method which handles all dependency logic:
                            # - Builds dependency graphs automatically
                            # - Handles conditional dependencies (==, !=, in, not in)
                            # - Processes scores in correct dependency order
                            # - Skips scores when conditions aren't met
                            # - Handles async processing with proper error handling
                            logger.info(f"Running scorecard evaluation with canonical dependency resolution for score '{score_name}'")
                            
                            # Resolve requested score identifier to the actual score name for subset matching
                            resolved_score_name = score_name
                            try:
                                if hasattr(scorecard_instance, 'scores') and isinstance(scorecard_instance.scores, list):
                                    for s in scorecard_instance.scores:
                                        s_name = s.get('name')
                                        if not s_name:
                                            continue
                                        if (
                                            s_name == score_name or
                                            str(s.get('id', '')) == str(score_name) or
                                            str(s.get('key', '')) == str(score_name) or
                                            str(s.get('externalId', '')) == str(score_name) or
                                            str(s.get('originalExternalId', '')) == str(score_name)
                                        ):
                                            resolved_score_name = s_name
                                            break
                                if resolved_score_name != score_name:
                                    logger.info(f"Resolved score identifier '{score_name}' to score name '{resolved_score_name}' for subset matching")
                            except Exception as _resolve_err:
                                logger.warning(f"Could not resolve score identifier '{score_name}' to name: {_resolve_err}")

                            # Build name->id map to extract result by ID later
                            try:
                                _, name_to_id = scorecard_instance.build_dependency_graph([resolved_score_name])
                            except Exception:
                                name_to_id = {}

                            # Honor yaml_only by disabling API loads during backfill
                            try:
                                setattr(scorecard_instance, 'yaml_only', bool(yaml_only))
                            except Exception:
                                pass

                            results = await scorecard_instance.score_entire_text(
                                text=item_text,
                                metadata=metadata,
                                modality=None,
                                subset_of_score_names=[resolved_score_name]  # This automatically includes dependencies
                            )
                            
                            # Extract the result for our target score
                            # Extract by ID when available; fall back to name
                            score_result_obj = None
                            target_result_id = name_to_id.get(resolved_score_name)
                            if results:
                                if target_result_id and target_result_id in results:
                                    score_result_obj = results[target_result_id]
                                elif resolved_score_name in results:
                                    score_result_obj = results[resolved_score_name]

                            # Handle SKIPPED due to unmet dependency conditions
                            if score_result_obj is None:
                                if results and any(v == "SKIPPED" for v in results.values()):
                                    logger.info(f"Score '{resolved_score_name}' not applicable due to unmet dependency conditions")
                                    prediction_result = {
                                        "item_id": target_id,
                                        "scores": [
                                            {
                                                "name": score_name,
                                                "value": None,
                                                "explanation": "Not applicable due to unmet dependency conditions",
                                                "cost": {}
                                            }
                                        ]
                                    }
                                else:
                                    raise Exception(f"No result found for score '{resolved_score_name}' via scorecard")
                            else:
                                scorecard_result = score_result_obj
                                prediction_result = scorecard_result
                                logger.info(f"Successfully got result from canonical scorecard system for '{score_name}'")
                            
                            # Process results from canonical Scorecard system
                            # All results now come from scorecard_instance.score_entire_text()
                            prediction_results = prediction_result
                            
                            if prediction_results and hasattr(prediction_results, 'value') and prediction_results.value is not None:
                                explanation = (
                                    getattr(prediction_results, 'explanation', None) or
                                    prediction_results.metadata.get('explanation', '') if hasattr(prediction_results, 'metadata') and prediction_results.metadata else
                                    ''
                                )
                                
                                # Extract costs from scorecard result
                                costs = {}
                                if hasattr(prediction_results, 'cost'):
                                    costs = prediction_results.cost
                                elif hasattr(prediction_results, 'metadata') and prediction_results.metadata:
                                    costs = prediction_results.metadata.get('cost', {})
                                
                                prediction_result = {
                                    "item_id": target_id,
                                    "scores": [
                                        {
                                            "name": score_name,
                                            "value": prediction_results.value,
                                            "explanation": explanation,
                                            "cost": costs
                                        }
                                    ]
                                }
                                
                                # Extract trace information if available
                                if include_trace:
                                    trace = None
                                    if hasattr(prediction_results, 'trace'):
                                        trace = prediction_results.trace
                                    elif hasattr(prediction_results, 'metadata') and prediction_results.metadata:
                                        trace = prediction_results.metadata.get('trace')
                                    
                                    if trace:
                                        prediction_result["scores"][0]["trace"] = trace
                            else:
                                raise Exception("No valid prediction value returned from canonical scorecard system")
                            
                        except Exception as pred_error:
                            logger.error(f"Error running actual prediction: {str(pred_error)}", exc_info=True)
                            # Fall back to indicating the error
                            prediction_result = {
                                "item_id": target_id,
                                "scores": [
                                    {
                                        "name": score_name,
                                        "value": "Error",
                                        "explanation": f"Failed to execute prediction: {str(pred_error)}"
                                    }
                                ]
                            }
                        
                        # Add input data if requested
                        if include_input:
                            prediction_result["input"] = {
                                "description": item_data.get('description'),
                                "metadata": item_data.get('metadata'),
                                "attachedFiles": item_data.get('attachedFiles'),
                                "externalId": item_data.get('externalId')
                            }
                                            
                        prediction_results_list.append(prediction_result)
                        
                    except Exception as item_error:
                        logger.error(f"Error processing item '{target_id}': {str(item_error)}", exc_info=True)
                        prediction_results_list.append({
                            "item_id": target_id,
                            "error": f"Error processing item: {str(item_error)}"
                        })
            
            except Exception as loop_error:
                logger.error(f"Error in prediction loop: {str(loop_error)}", exc_info=True)
                return f"Error running predictions: {str(loop_error)}"

            # Format output based on requested format
            if output_format.lower() == "yaml":
                import yaml
                
                command_parts = [f"plexus predict --scorecard \"{scorecard_name}\" --score \"{score_name}\""]
                if item_id:
                    command_parts.append(f"--item \"{item_id}\"")
                elif item_ids:
                    command_parts.append(f"--items \"{item_ids}\"")
                if output_format.lower() == "yaml":
                    command_parts.append("--format yaml")
                if include_input:
                    command_parts.append("--input")
                if include_trace:
                    command_parts.append("--trace")
                
                result = {
                    "context": {
                        "description": "Output from plexus predict command",
                        "command": " ".join(command_parts),
                        "scorecard_id": scorecard_id,
                        "score_id": resolved_score['id'],
                        "item_count": len(target_item_ids)
                    },
                    "predictions": prediction_results_list
                }
                
                return yaml.dump(result, default_flow_style=False, sort_keys=False)
            else:
                # Return JSON format
                return {
                    "success": True,
                    "scorecard_name": scorecard_name,
                    "score_name": score_name,
                    "scorecard_id": scorecard_id,
                    "score_id": resolved_score['id'],
                    "score_version_id": resolved_score.get('championVersionId'),
                    "item_count": len(target_item_ids),
                    "options": {
                        "include_input": include_input,
                        "include_trace": include_trace,
                        "output_format": output_format
                    },
                    "predictions": prediction_results_list,
                    "note": "This MCP tool executes real predictions using the shared Plexus prediction service."
                }
            
        except Exception as e:
            logger.error(f"Error running predictions: {str(e)}", exc_info=True)
            return f"Error running predictions: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_predict: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout