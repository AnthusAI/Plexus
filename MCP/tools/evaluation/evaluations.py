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
    async def run_plexus_evaluation(
        scorecard_name: str = "",
        score_name: str = "",
        n_samples: int = 10,
        remote: bool = False,
        yaml: bool = True,
    ) -> str:
        """Run a local YAML-based accuracy evaluation using the same code path as CLI (DRY)."""
        if not scorecard_name:
            return "Error: scorecard_name must be provided"

        try:
            # Use the shared evaluation function - no code duplication!
            from plexus.cli.shared.evaluation_runner import run_accuracy_evaluation
            import json

            # Call the shared function that both CLI and MCP use
            result = await run_accuracy_evaluation(
                scorecard_name=scorecard_name,
                score_name=score_name,
                number_of_samples=n_samples,
                sampling_method="random",
                fresh=True,
                use_yaml=yaml
            )
            
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error running Plexus evaluation: {e}", exc_info=True)
            return f"Error: {e}"