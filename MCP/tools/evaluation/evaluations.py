#!/usr/bin/env python3
"""
Evaluation management tools for Plexus MCP Server
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Union, Optional
from io import StringIO
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_evaluation_tools(mcp: FastMCP):
    """Register evaluation tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_evaluation_info(
        evaluation_id: Optional[str] = None,
        use_latest: bool = False,
        account_key: str = 'call-criteria',
        evaluation_type: str = "",
        include_score_results: bool = False,
        include_examples: bool = False,
        predicted_value: Optional[str] = None,
        actual_value: Optional[str] = None,
        limit: int = 10,
        output_format: str = "json"
    ) -> str:
        """
        Get detailed information about an evaluation by its ID or get the latest evaluation.
        
        This tool provides comprehensive information about an evaluation including:
        - Basic details (ID, type, status)
        - Scorecard and score names (resolved from IDs)
        - Progress and metrics information
        - Timing details
        - Error information (if any)
        - Cost information
        
        Parameters:
        - evaluation_id: The unique ID of the evaluation to look up (mutually exclusive with use_latest)
        - use_latest: If True, get info about the most recent evaluation (mutually exclusive with evaluation_id)
        - account_key: Account key to filter by when using use_latest (default: 'call-criteria')
        - evaluation_type: Optional filter by evaluation type when using use_latest (e.g., 'accuracy', 'consistency')
        - include_score_results: Whether to include score results information (default: False)
        - include_examples: Whether to include examples from confusion matrix (default: False)
        - predicted_value: Filter examples where AI predicted this value (e.g., "medium", "high", "yes", "no")
        - actual_value: Filter examples where human labeled this value (e.g., "low", "yes", "no")
        - limit: Maximum number of examples per category (default: 10)
        - output_format: Output format - "json", "yaml", or "text" (default: "json")
        
        Returns:
        - Formatted string with comprehensive evaluation information
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Import the evaluation functionality
            try:
                from plexus.Evaluation import Evaluation
            except ImportError as e:
                return f"Import error: Could not import Evaluation class: {str(e)}"
            
            # Validate parameters - must specify either evaluation_id or use_latest
            if not evaluation_id and not use_latest:
                return "Error: Must specify either evaluation_id or use_latest=True"
            
            if evaluation_id and use_latest:
                return "Error: Cannot specify both evaluation_id and use_latest=True. Use one or the other."
            
            try:
                if use_latest:
                    # Get latest evaluation mode
                    eval_type_filter = evaluation_type.strip() if evaluation_type and evaluation_type.strip() else None
                    evaluation_info = Evaluation.get_latest_evaluation(account_key, eval_type_filter)
                    
                    if not evaluation_info:
                        if eval_type_filter:
                            return f"No evaluations found for account '{account_key}' with type '{eval_type_filter}'"
                        else:
                            return f"No evaluations found for account '{account_key}'"
                else:
                    # Specific evaluation ID mode
                    if not evaluation_id.strip():
                        return "Error: evaluation_id cannot be empty"
                    evaluation_info = Evaluation.get_evaluation_info(evaluation_id, include_score_results)
                
                # Build structured payload
                payload: Dict[str, Any] = {
                    "id": evaluation_info['id'],
                    "type": evaluation_info['type'],
                    "status": evaluation_info['status'],
                    "scorecard": evaluation_info['scorecard_name'] or evaluation_info['scorecard_id'],
                    "score": evaluation_info['score_name'] or evaluation_info['score_id'],
                    "total_items": evaluation_info['total_items'],
                    "processed_items": evaluation_info['processed_items'],
                    "metrics": evaluation_info['metrics'],
                    "accuracy": evaluation_info['accuracy'],
                    "confusionMatrix": evaluation_info['confusion_matrix'],
                    "predictedClassDistribution": evaluation_info['predicted_class_distribution'],
                    "datasetClassDistribution": evaluation_info['dataset_class_distribution'],
                    "cost": evaluation_info['cost'],
                    "started_at": evaluation_info['started_at'],
                    "created_at": evaluation_info['created_at'],
                    "updated_at": evaluation_info['updated_at'],
                }

                # Optionally include quadrant examples inline for consistency with feedback tools
                if include_examples:
                    from plexus.dashboard.api.client import PlexusDashboardClient
                    client = PlexusDashboardClient()
                    import json as _json

                    def fetch_examples(k: int, pred_val: Optional[str] = None, actual_val: Optional[str] = None) -> List[Dict[str, Any]]:
                        query = """
                        query ListByEval($evaluationId: String!, $limit: Int, $nextToken: String) {
                          listScoreResultByEvaluationId(evaluationId: $evaluationId, limit: $limit, nextToken: $nextToken) {
                            items { id value explanation itemId correct metadata }
                            nextToken
                          }
                        }
                        """
                        examples: List[Dict[str, Any]] = []
                        next_token = None
                        page_limit = min(max(k * 5, 50), 500)
                        while True:
                            variables = {"evaluationId": evaluation_info['id'], "limit": page_limit}
                            if next_token:
                                variables["nextToken"] = next_token
                            resp = client.execute(query, variables)
                            data = resp.get('listScoreResultByEvaluationId', {}) if resp else {}
                            items = data.get('items', [])
                            next_token = data.get('nextToken')
                            for sr in items:
                                md = sr.get('metadata')
                                try:
                                    if isinstance(md, str):
                                        md = _json.loads(md)
                                except Exception:
                                    md = None
                                human_label = None
                                if md and isinstance(md, dict):
                                    res_md = md.get('results') or {}
                                    if isinstance(res_md, dict) and res_md:
                                        key0 = next(iter(res_md))
                                        inner = res_md.get(key0) or {}
                                        inner_md = inner.get('metadata') or {}
                                        human_label = (inner_md.get('human_label') or '').strip().lower()
                                predicted = (sr.get('value') or '').strip().lower()
                                # Check if this example matches our filter criteria
                                pred_match = pred_val is None or predicted == pred_val.lower()
                                actual_match = actual_val is None or human_label == actual_val.lower()
                                matches = pred_match and actual_match
                                
                                if matches:
                                    examples.append({
                                        "score_result_id": sr.get('id'),
                                        "item_id": sr.get('itemId'),
                                        "predicted": predicted,
                                        "actual": human_label,
                                        "explanation": sr.get('explanation')
                                    })
                                    if len(examples) >= k:
                                        return examples
                            if len(examples) >= k or not next_token:
                                break
                        return examples

                    # Filter examples by predicted/actual values if specified
                    if predicted_value is not None or actual_value is not None:
                        # Filter by specific predicted/actual values
                        examples = fetch_examples(limit, predicted_value, actual_value)
                        filter_key = f"predicted_{predicted_value or 'any'}_actual_{actual_value or 'any'}"
                        payload['examples'] = {filter_key: examples}
                    else:
                        # No filtering - return all examples
                        examples = fetch_examples(limit)
                        payload['examples'] = {"all": examples}

                # Output formatting - support both structured (JSON/YAML) and formatted text
                if output_format.lower() == 'yaml':
                    try:
                        import yaml
                        return yaml.safe_dump(payload, sort_keys=False)
                    except Exception:
                        return json.dumps(payload)
                elif output_format.lower() == 'json':
                    return json.dumps(payload)
                elif output_format.lower() == 'text':
                    # Format as readable text (like the old plexus_evaluation_last)
                    output_lines = []
                    output_lines.append("=== Evaluation Information ===")
                    output_lines.append(f"ID: {evaluation_info['id']}")
                    output_lines.append(f"Type: {evaluation_info['type']}")
                    output_lines.append(f"Status: {evaluation_info['status']}")
                    
                    if evaluation_info.get('scorecard_name'):
                        output_lines.append(f"Scorecard: {evaluation_info['scorecard_name']}")
                    elif evaluation_info.get('scorecard_id'):
                        output_lines.append(f"Scorecard ID: {evaluation_info['scorecard_id']}")
                    else:
                        output_lines.append("Scorecard: Not specified")
                        
                    if evaluation_info.get('score_name'):
                        output_lines.append(f"Score: {evaluation_info['score_name']}")
                    elif evaluation_info.get('score_id'):
                        output_lines.append(f"Score ID: {evaluation_info['score_id']}")
                    else:
                        output_lines.append("Score: Not specified")
                    
                    output_lines.append("\n=== Progress & Metrics ===")
                    if evaluation_info.get('total_items'):
                        output_lines.append(f"Total Items: {evaluation_info['total_items']}")
                    if evaluation_info.get('processed_items') is not None:
                        output_lines.append(f"Processed Items: {evaluation_info['processed_items']}")
                    if evaluation_info.get('accuracy') is not None:
                        output_lines.append(f"Accuracy: {evaluation_info['accuracy']:.2f}%")
                    
                    if evaluation_info.get('metrics'):
                        output_lines.append("\n=== Detailed Metrics ===")
                        for metric in evaluation_info['metrics']:
                            if isinstance(metric, dict) and 'name' in metric and 'value' in metric:
                                output_lines.append(f"{metric['name']}: {metric['value']:.2f}")
                            else:
                                output_lines.append(f"Metric: {metric}")
                    
                    output_lines.append("\n=== Timing ===")
                    if evaluation_info.get('started_at'):
                        output_lines.append(f"Started At: {evaluation_info['started_at']}")
                    if evaluation_info.get('elapsed_seconds'):
                        output_lines.append(f"Elapsed Time: {evaluation_info['elapsed_seconds']} seconds")
                    if evaluation_info.get('estimated_remaining_seconds'):
                        output_lines.append(f"Estimated Remaining: {evaluation_info['estimated_remaining_seconds']} seconds")
                    
                    output_lines.append("\n=== Timestamps ===")
                    output_lines.append(f"Created At: {evaluation_info['created_at']}")
                    output_lines.append(f"Updated At: {evaluation_info['updated_at']}")
                    
                    if evaluation_info.get('cost'):
                        output_lines.append("\n=== Cost ===")
                        output_lines.append(f"Total Cost: ${evaluation_info['cost']:.6f}")
                    
                    if evaluation_info.get('error_message'):
                        output_lines.append("\n=== Error Information ===")
                        output_lines.append(f"Error Message: {evaluation_info['error_message']}")
                        if evaluation_info.get('error_details'):
                            output_lines.append(f"Error Details: {evaluation_info['error_details']}")
                    
                    if evaluation_info.get('task_id'):
                        output_lines.append("\n=== Task ===")
                        output_lines.append(f"Task ID: {evaluation_info['task_id']}")
                    
                    return "\n".join(output_lines)
                else:
                    # Default to JSON
                    return json.dumps(payload)
                
            except ValueError as e:
                return f"Error: {str(e)}"
            except Exception as e:
                return f"Unexpected error getting evaluation info: {str(e)}"
                
        except Exception as e:
            return f"Unexpected error: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_evaluation_info: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_evaluation_run(
        scorecard_name: str = "",
        score_name: str = "",
        n_samples: int = 10,
        yaml: bool = True,
        version: Optional[str] = None,
        latest: bool = False,
    ) -> str:
        """Run a local YAML-based accuracy evaluation using the same code path as CLI (DRY)."""
        if not scorecard_name:
            return "Error: scorecard_name must be provided"

        # Validate mutually exclusive version options (same as CLI)
        if version and latest:
            return "Error: Cannot use both version and latest options. Choose one."

        logger.info(f"MCP Evaluation - Scorecard: {scorecard_name}, Score: {score_name}, YAML: {yaml}, Samples: {n_samples}")

        try:
            import json
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            from click.testing import CliRunner
            from plexus.cli.evaluation.evaluations import accuracy
            from plexus.Evaluation import Evaluation

            # Build CLI arguments
            args = [
                '--scorecard', scorecard_name,
                '--number-of-samples', str(n_samples),
                '--sampling-method', 'random',
                '--fresh'
            ]

            if yaml:
                args.append('--yaml')

            if score_name:
                args.extend(['--score', score_name])

            if version:
                args.extend(['--version', version])

            if latest:
                args.append('--latest')

            # Run the CLI command in a thread pool to avoid event loop conflicts
            # This ensures we use the exact same code path as the CLI
            def run_cli_command():
                runner = CliRunner()
                return runner.invoke(accuracy, args, catch_exceptions=False, standalone_mode=False)

            # Execute in a thread pool to avoid "event loop already running" error
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(pool, run_cli_command)

            # Check if command succeeded
            if result.exit_code != 0:
                error_msg = f"CLI command failed with exit code {result.exit_code}"
                if result.output:
                    error_msg += f": {result.output}"
                logger.error(error_msg)
                return json.dumps({"error": error_msg})

            # Get the evaluation record returned by the CLI command
            evaluation_record = result.return_value

            if not evaluation_record or not evaluation_record.id:
                return json.dumps({"error": "Evaluation completed but no record returned"})

            # Get full evaluation info using the specific ID
            eval_info = Evaluation.get_evaluation_info(evaluation_record.id)

            # Return the same format - note that get_evaluation_info uses snake_case keys
            response = {
                'evaluation_id': eval_info.get('id'),
                'scorecard_id': eval_info.get('scorecard_id'),
                'score_id': eval_info.get('score_id'),
                'accuracy': eval_info.get('accuracy'),
                'metrics': eval_info.get('metrics'),
                'confusionMatrix': eval_info.get('confusion_matrix'),  # snake_case in source
                'predictedClassDistribution': eval_info.get('predicted_class_distribution'),  # snake_case in source
                'datasetClassDistribution': eval_info.get('dataset_class_distribution'),  # snake_case in source
            }

            return json.dumps(response)

        except Exception as e:
            logger.error(f"Error running Plexus evaluation: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def plexus_evaluation_score_result_find(
        evaluation_id: str,
        predicted_value: Optional[str] = None,
        actual_value: Optional[str] = None,
        limit: Optional[Union[int, float, str]] = 5,
        offset: Optional[Union[int, float, str]] = None,
        include_text: bool = False
    ) -> str:
        """
        Find and navigate individual score results from an evaluation using confusion matrix cell filtering.

        This tool provides the evaluation equivalent of plexus_feedback_find, allowing navigation through
        individual score results from an evaluation with confusion matrix cell-based filtering and
        offset-based pagination.

        Args:
            evaluation_id (str): The unique ID of the evaluation to examine
            predicted_value (str, optional): Filter by predicted value (e.g., "yes", "no", "high", "medium")
            actual_value (str, optional): Filter by actual/human label value (e.g., "yes", "no", "low")
            limit (int, optional): Maximum number of results to return (default: 5)
            offset (int, optional): Starting index for pagination within filtered results (default: 0)
            include_text (bool, optional): Whether to include full transcript text (default: False to prevent context overflow)

        Returns:
            str: JSON formatted list of individual score results with detailed information
        """
        try:
            from plexus.dashboard.api.client import PlexusDashboardClient
            from plexus.cli.shared.client_utils import create_client
            import json as _json
            from collections import defaultdict

            # Create client
            client = create_client()
            if not client:
                return _json.dumps({"error": "Failed to create API client"})

            # Convert parameters to proper types
            limit_int = int(limit) if limit is not None else 5
            offset_int = int(offset) if offset is not None else 0

            # Validate evaluation_id
            if not evaluation_id or not evaluation_id.strip():
                return _json.dumps({"error": "evaluation_id is required"})

            # Fetch all score results for this evaluation
            query = """
            query ListScoreResultsByEvaluation($evaluationId: String!, $limit: Int, $nextToken: String) {
                listScoreResultByEvaluationId(evaluationId: $evaluationId, limit: $limit, nextToken: $nextToken) {
                    items {
                        id
                        evaluationId
                        itemId
                        accountId
                        scorecardId
                        scoreId
                        value
                        confidence
                        explanation
                        metadata
                        trace
                        code
                        type
                        feedbackItemId
                        createdAt
                        updatedAt
                        item {
                            id
                            identifiers
                            text
                        }
                    }
                    nextToken
                }
            }
            """

            # Fetch all score results with pagination
            all_score_results = []
            next_token = None
            max_pages = 50  # Safety limit
            page_count = 0

            while page_count < max_pages:
                variables = {"evaluationId": evaluation_id, "limit": 500}
                if next_token:
                    variables["nextToken"] = next_token

                response = client.execute(query, variables)
                if 'errors' in response:
                    return _json.dumps({"error": f"GraphQL errors: {response.get('errors')}"})

                data = response.get('listScoreResultByEvaluationId', {})
                items = data.get('items', [])
                next_token = data.get('nextToken')

                all_score_results.extend(items)

                if not next_token:
                    break
                page_count += 1

            logger.info(f"[MCP] Retrieved {len(all_score_results)} total score results")

            # Group score results by confusion matrix cell (predicted_value, actual_value)
            matrix_cells = defaultdict(list)
            processed_results = []

            for sr in all_score_results:
                # Extract predicted value
                predicted = (sr.get('value') or '').strip().lower()

                # Extract actual value from metadata (same logic as plexus_evaluation_info)
                md = sr.get('metadata')
                try:
                    if isinstance(md, str):
                        md = _json.loads(md)
                except Exception:
                    md = None

                human_label = None
                if md and isinstance(md, dict):
                    res_md = md.get('results') or {}
                    if isinstance(res_md, dict) and res_md:
                        key0 = next(iter(res_md))
                        inner = res_md.get(key0) or {}
                        inner_md = inner.get('metadata') or {}
                        human_label = (inner_md.get('human_label') or '').strip().lower()

                actual = human_label or 'unknown'

                # Apply filtering if specified
                pred_match = predicted_value is None or predicted == predicted_value.lower()
                actual_match = actual_value is None or actual == actual_value.lower()

                if pred_match and actual_match:
                    # Create cell key for grouping
                    cell_key = (predicted, actual)

                    # Format the result for output
                    formatted_result = {
                        "score_result_id": sr.get('id'),
                        "evaluation_id": sr.get('evaluationId'),
                        "item_id": sr.get('itemId'),
                        "predicted": predicted,
                        "actual": actual,
                        "explanation": sr.get('explanation'),
                        "confidence": sr.get('confidence'),
                        "code": sr.get('code'),
                        "feedback_item_id": sr.get('feedbackItemId'),
                        "created_at": sr.get('createdAt'),
                        "updated_at": sr.get('updatedAt'),
                        "confusion_matrix_cell": {
                            "predicted": predicted,
                            "actual": actual
                        }
                    }

                    # Add trace data if available
                    if sr.get('trace'):
                        try:
                            trace_data = _json.loads(sr.get('trace')) if isinstance(sr.get('trace'), str) else sr.get('trace')
                            formatted_result["trace"] = trace_data
                        except Exception:
                            formatted_result["trace"] = sr.get('trace')

                    # Add detailed metadata if available (but strip transcript text unless requested)
                    if md and isinstance(md, dict):
                        if include_text:
                            # Include full metadata with transcript text
                            formatted_result["detailed_metadata"] = md
                        else:
                            # Strip transcript text from metadata to prevent context overflow
                            md_copy = _json.loads(_json.dumps(md))  # Deep copy
                            res_md = md_copy.get('results') or {}
                            if isinstance(res_md, dict):
                                for score_name, score_data in res_md.items():
                                    if isinstance(score_data, dict):
                                        inner_md = score_data.get('metadata') or {}
                                        if isinstance(inner_md, dict) and 'text' in inner_md:
                                            # Remove the transcript text field
                                            inner_md.pop('text', None)
                            formatted_result["detailed_metadata"] = md_copy

                    # Add item data if available (includes identifiers and optionally text)
                    if sr.get('item'):
                        item_data = sr.get('item')
                        formatted_result["item"] = {
                            "id": item_data.get('id'),
                            "identifiers": item_data.get('identifiers')
                        }
                        # Only include text if explicitly requested to prevent context overflow
                        if include_text and item_data.get('text'):
                            formatted_result["item"]["text"] = item_data.get('text')

                    matrix_cells[cell_key].append(formatted_result)
                    processed_results.append(formatted_result)

            logger.info(f"[MCP] After filtering: {len(processed_results)} results in {len(matrix_cells)} confusion matrix cells")

            # Log cell distribution for debugging
            for cell_key, cell_items in matrix_cells.items():
                logger.info(f"[MCP] Cell {cell_key}: {len(cell_items)} items")

            # Apply offset-based pagination
            start_idx = offset_int
            end_idx = offset_int + limit_int
            page_results = processed_results[start_idx:end_idx]

            # Calculate pagination info
            total_available = len(processed_results)
            has_next_page = end_idx < total_available
            next_offset = end_idx if has_next_page else None

            # Build response
            result = {
                "context": {
                    "evaluation_id": evaluation_id,
                    "filters": {
                        "predicted_value": predicted_value,
                        "actual_value": actual_value
                    },
                    "pagination": {
                        "current_offset": offset_int,
                        "limit": limit_int,
                        "total_available": total_available,
                        "has_next_page": has_next_page,
                        "next_offset": next_offset
                    },
                    "confusion_matrix_cells": {
                        cell_key[0] + "_" + cell_key[1]: len(cell_items)
                        for cell_key, cell_items in matrix_cells.items()
                    }
                },
                "score_results": page_results,
                "summary": {
                    "total_results_found": total_available,
                    "results_in_page": len(page_results),
                    "confusion_matrix_cells_found": len(matrix_cells)
                }
            }

            return _json.dumps(result, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error in plexus_evaluation_score_result_find: {e}", exc_info=True)
            import json
            return json.dumps({"error": f"Failed to find evaluation results: {str(e)}"})