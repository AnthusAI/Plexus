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
        account_key: str = None,
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
        - account_key: Account key to filter by when using use_latest (uses PLEXUS_ACCOUNT_KEY env var if not provided)
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
        # Use PLEXUS_ACCOUNT_KEY environment variable if no account_key provided
        if account_key is None:
            account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
            if account_key is None:
                return "Error: account_key must be provided or PLEXUS_ACCOUNT_KEY environment variable must be set"
        
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
                    "score_version_id": evaluation_info.get('score_version_id'),
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
                    "baseline_evaluation_id": evaluation_info.get('baseline_evaluation_id'),
                }

                root_cause = evaluation_info.get('root_cause')
                if root_cause:
                    payload['root_cause'] = root_cause
                misclassification_analysis = evaluation_info.get('misclassification_analysis')
                if misclassification_analysis:
                    payload['misclassification_analysis'] = misclassification_analysis

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
                    
                    # Display score version if available
                    if evaluation_info.get('score_version_id'):
                        version_id = evaluation_info['score_version_id']
                        # Show short version (first 8 chars) with full ID
                        short_version = version_id[:8] if len(version_id) > 8 else version_id
                        output_lines.append(f"Score Version: {short_version}... (Full ID: {version_id})")
                    
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
        evaluation_type: str = "accuracy",
        n_samples: int = 10,
        days: int = 7,
        max_feedback_samples: Optional[int] = None,
        sample_seed: Optional[int] = None,
        max_category_summary_items: int = 20,
        yaml: bool = True,
        version: Optional[str] = None,
        latest: bool = False,
        fresh: bool = False,
        reload: bool = False,
        allow_no_labels: bool = False,
        concurrency: int = 5,
        baseline: Optional[str] = None,
        wait: bool = True,
    ) -> str:
        """
        Run an evaluation using the same code path as CLI.

        Parameters:
        - scorecard_name: Name of the scorecard to evaluate (required)
        - score_name: Name of specific score to evaluate (optional for feedback; if omitted, runs all scores in the scorecard)
        - evaluation_type: Type of evaluation - "accuracy" (default) or "feedback"
        - n_samples: Number of samples for accuracy evaluation (default: 10)
        - days: Number of days to look back for feedback evaluation (default: 7). Use 30-60 days for more data.
        - max_feedback_samples: Optional cap for feedback evaluations. When provided, a random
                subset up to this size is evaluated.
        - sample_seed: Optional random seed for reproducible feedback sampling.
        - max_category_summary_items: Maximum misclassification items per category used in
          aggregate RCA triage summaries (default: 20).
        - yaml: Load scorecard from YAML files for accuracy evaluation (default: True)
        - version: Specific score version ID. For accuracy: version to evaluate. For feedback: if
                   provided, overrides the auto-fetched champion version.
        - latest: Use latest score version for accuracy evaluation (default: False)
        - fresh: Pull fresh, non-cached data from the data lake (default: False)
        - reload: Reload existing dataset by refreshing values for current records only (default: False)
        - allow_no_labels: Allow evaluation without ground truth labels (default: False)
                          When True, creates score results and predicted class distribution
                          but skips accuracy metrics
        - concurrency: Max parallel evaluations when running bulk (all-scores) feedback mode (default: 5)
        - baseline: Evaluation ID to use as baseline for comparison (optional). When provided,
                    the new evaluation record stores this ID so the dashboard can display
                    before-and-after gauges showing the change from the baseline metrics.
        - wait: For feedback evaluations — if True (default), block until evaluation + RCA complete
                and return full results. If False, dispatch in background and return immediately
                with the evaluation ID only.

        Returns:
        - JSON string with evaluation results including evaluation_id, metrics, and dashboard URL.
          For bulk feedback mode (no score_name), returns aggregate results for all scores.

        FEEDBACK EVALUATION BEHAVIOR:
        - Runs Mode 2 (accuracy evaluation using feedback items as ground truth) by default.
        - Automatically fetches the score's current champion version ID to use as the predictor.
        - The champion version's code is run against all feedback items in the time window,
          and predictions are compared to human-corrected labels to compute accuracy metrics.
        - If score_name is omitted, runs for ALL scores in the scorecard concurrently.
        - Supply version= explicitly to override the champion version (e.g. to test a specific version).
        """
        if not scorecard_name:
            return "Error: scorecard_name must be provided"

        # Validate evaluation type
        if evaluation_type not in ["accuracy", "feedback"]:
            return f"Error: evaluation_type must be 'accuracy' or 'feedback', got '{evaluation_type}'"

        # Validate mutually exclusive version options (same as CLI)
        if version and latest:
            return "Error: Cannot use both version and latest options. Choose one."

        if max_feedback_samples is not None and max_feedback_samples <= 0:
            return "Error: max_feedback_samples must be a positive integer"
        if max_category_summary_items <= 0:
            return "Error: max_category_summary_items must be a positive integer"

        logger.info(
            "MCP Evaluation - Type: %s, Scorecard: %s, Score: %s, Days: %s, "
            "YAML: %s, Samples: %s, MaxFeedbackSamples: %s, SampleSeed: %s, MaxCategorySummaryItems: %s",
            evaluation_type, scorecard_name, score_name, days, yaml, n_samples,
            max_feedback_samples, sample_seed, max_category_summary_items
        )

        try:
            import json
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            from click.testing import CliRunner
            from plexus.cli.evaluation.evaluations import accuracy, feedback
            from plexus.Evaluation import Evaluation

            if evaluation_type == "feedback":
                import subprocess
                import shutil
                import time as _time

                plexus_bin = shutil.which("plexus") or "/home/ryan/miniconda3/envs/py311/bin/plexus"

                # Helper: fetch all scores for the scorecard with their champion version IDs
                async def _fetch_scorecard_scores() -> List[Dict[str, Any]]:
                    from plexus.cli.shared.client_utils import create_client
                    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
                    _client = create_client()
                    sc_id = resolve_scorecard_identifier(_client, scorecard_name)
                    if not sc_id:
                        return []
                    _query = f"""
                    query GetScorecardForFeedback {{
                        getScorecard(id: "{sc_id}") {{
                            sections {{
                                items {{
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
                    _result = _client.execute(_query)
                    sc_data = (_result.get('getScorecard') or {})
                    scores = []
                    for _section in sc_data.get('sections', {}).get('items', []):
                        for _score in _section.get('scores', {}).get('items', []):
                            if _score.get('championVersionId'):
                                scores.append(_score)
                    return scores

                async def _run_feedback_sync(
                    sc: str,
                    sco: str,
                    d: int,
                    ver: Optional[str],
                    bl: Optional[str] = None,
                    max_fb_samples: Optional[int] = None,
                    seed: Optional[int] = None,
                    max_category_items: int = 20,
                ) -> subprocess.CompletedProcess:
                    """Run plexus evaluate feedback synchronously in a thread, blocking until complete."""
                    cmd = [plexus_bin, "evaluate", "feedback",
                           "--scorecard", sc, "--score", sco, "--days", str(d)]
                    if ver:
                        cmd += ["--version", ver]
                    if bl:
                        cmd += ["--baseline", bl]
                    if max_fb_samples is not None:
                        cmd += ["--max-samples", str(max_fb_samples)]
                    if seed is not None:
                        cmd += ["--sample-seed", str(seed)]
                    cmd += ["--max-category-summary-items", str(max_category_items)]
                    return await asyncio.to_thread(
                        subprocess.run,
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                async def _wait_for_completed_evaluation(spawn_time: float, timeout: float = 900.0) -> Optional[Dict[str, Any]]:
                    """Poll the API until a new evaluation created after spawn_time reaches COMPLETED status."""
                    import datetime as _dt
                    deadline = _time.monotonic() + timeout
                    evaluation_id = None
                    while _time.monotonic() < deadline:
                        await asyncio.sleep(5)
                        try:
                            eval_info = Evaluation.get_latest_evaluation(evaluation_type="feedback")
                            if not eval_info:
                                continue
                            # Only consider evaluations created after our spawn time
                            created_at_str = eval_info.get("created_at") or eval_info.get("createdAt") or ""
                            if created_at_str:
                                try:
                                    created_ts = _dt.datetime.fromisoformat(
                                        created_at_str.replace("Z", "+00:00")
                                    ).timestamp()
                                    if created_ts < spawn_time - 5:
                                        continue
                                except Exception:
                                    pass
                            eid = eval_info.get("id")
                            if not eid:
                                continue
                            evaluation_id = eid
                            status = eval_info.get("status", "")
                            if status == "COMPLETED":
                                return eval_info
                            # Keep waiting if still running
                        except Exception as poll_err:
                            logger.debug("Error polling for evaluation: %s", poll_err)
                    # Timed out — return whatever we have
                    if evaluation_id:
                        try:
                            return Evaluation.get_evaluation_info(evaluation_id)
                        except Exception:
                            pass
                    return None

                def _spawn_feedback(
                    sc: str,
                    sco: str,
                    d: int,
                    ver: Optional[str],
                    bl: Optional[str] = None,
                    max_fb_samples: Optional[int] = None,
                    seed: Optional[int] = None,
                    max_category_items: int = 20,
                ) -> None:
                    """Fire-and-forget: spawn plexus evaluate feedback as a detached background process."""
                    cmd = [plexus_bin, "evaluate", "feedback",
                           "--scorecard", sc, "--score", sco, "--days", str(d)]
                    if ver:
                        cmd += ["--version", ver]
                    if bl:
                        cmd += ["--baseline", bl]
                    if max_fb_samples is not None:
                        cmd += ["--max-samples", str(max_fb_samples)]
                    if seed is not None:
                        cmd += ["--sample-seed", str(seed)]
                    cmd += ["--max-category-summary-items", str(max_category_items)]
                    subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )

                if score_name:
                    # Single score: resolve champion version first.
                    resolved_version = version
                    if not resolved_version:
                        sc_scores = await _fetch_scorecard_scores()
                        for sc_score in sc_scores:
                            if (sc_score.get('name', '').lower() == score_name.lower() or
                                    sc_score.get('key') == score_name or
                                    sc_score.get('externalId') == score_name or
                                    sc_score.get('id') == score_name):
                                resolved_version = sc_score.get('championVersionId')
                                break
                        if resolved_version:
                            logger.info(f"Auto-fetched champion version {resolved_version} for '{score_name}'")
                        else:
                            logger.warning(f"No champion version for '{score_name}', proceeding without --version")

                    if not wait:
                        # Background mode: fire-and-forget, return as soon as evaluation record appears.
                        logger.info(f"Spawning feedback evaluation for '{score_name}' (background)")
                        spawn_time = _time.time()
                        _spawn_feedback(
                            scorecard_name,
                            score_name,
                            days,
                            resolved_version,
                            baseline,
                            max_feedback_samples,
                            sample_seed,
                            max_category_summary_items,
                        )
                        await asyncio.sleep(3)
                        # Quick poll to get the evaluation ID
                        import datetime as _dt
                        deadline = _time.monotonic() + 25
                        evaluation_id = None
                        while _time.monotonic() < deadline:
                            await asyncio.sleep(2)
                            try:
                                ei = Evaluation.get_latest_evaluation(evaluation_type="feedback")
                                if ei:
                                    ca = (ei.get("created_at") or ei.get("createdAt") or "").replace("Z", "+00:00")
                                    if ca:
                                        try:
                                            if _dt.datetime.fromisoformat(ca).timestamp() >= spawn_time - 5:
                                                evaluation_id = ei.get("id")
                                                break
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        if evaluation_id:
                            return json.dumps({
                                "status": "dispatched",
                                "evaluation_id": evaluation_id,
                                "scorecard": scorecard_name,
                                "score": score_name,
                                "days": days,
                                "champion_version_id": resolved_version,
                                "max_feedback_samples": max_feedback_samples,
                                "sample_seed": sample_seed,
                                "max_category_summary_items": max_category_summary_items,
                                "message": "Evaluation running in background. Use plexus_evaluation_info to check status.",
                                "dashboard_url": f"https://lab.callcriteria.com/lab/evaluations/{evaluation_id}",
                            })
                        else:
                            return json.dumps({
                                "status": "dispatched",
                                "evaluation_id": None,
                                "message": "Evaluation dispatched. Use plexus_evaluation_info(use_latest=True) in ~30s.",
                            })

                    # Synchronous mode (default): run CLI in thread, poll until COMPLETED + RCA done.
                    logger.info(f"Running feedback evaluation for '{score_name}' (synchronous, waiting for completion + RCA)...")
                    spawn_time = _time.time()

                    run_task = asyncio.create_task(
                        _run_feedback_sync(
                            scorecard_name,
                            score_name,
                            days,
                            resolved_version,
                            baseline,
                            max_feedback_samples,
                            sample_seed,
                            max_category_summary_items,
                        )
                    )
                    eval_info = await _wait_for_completed_evaluation(spawn_time, timeout=900.0)
                    await run_task  # ensure subprocess is fully done

                    if eval_info:
                        evaluation_id = eval_info.get("id")
                        if evaluation_id:
                            try:
                                # Re-fetch after CLI exits so payload includes final RCA/status.
                                eval_info = Evaluation.get_evaluation_info(evaluation_id)
                            except Exception as refresh_err:
                                logger.debug("Could not refresh completed evaluation %s: %s", evaluation_id, refresh_err)
                        logger.info(f"Evaluation completed: {evaluation_id}")

                        payload: Dict[str, Any] = {
                            "id": eval_info['id'],
                            "type": eval_info.get('type', 'feedback'),
                            "status": eval_info.get('status', 'COMPLETED'),
                            "scorecard": eval_info.get('scorecard_name') or scorecard_name,
                            "score": eval_info.get('score_name') or score_name,
                            "score_version_id": eval_info.get('score_version_id'),
                            "max_feedback_samples": max_feedback_samples,
                            "sample_seed": sample_seed,
                            "max_category_summary_items": max_category_summary_items,
                            "total_items": eval_info.get('total_items'),
                            "processed_items": eval_info.get('processed_items'),
                            "metrics": eval_info.get('metrics'),
                            "accuracy": eval_info.get('accuracy'),
                            "confusionMatrix": eval_info.get('confusion_matrix'),
                            "predictedClassDistribution": eval_info.get('predicted_class_distribution'),
                            "datasetClassDistribution": eval_info.get('dataset_class_distribution'),
                            "baselineEvaluationId": eval_info.get('baseline_evaluation_id'),
                            "cost": eval_info.get('cost'),
                            "started_at": eval_info.get('started_at'),
                            "created_at": eval_info.get('created_at'),
                            "updated_at": eval_info.get('updated_at'),
                            "dashboard_url": f"https://lab.callcriteria.com/lab/evaluations/{evaluation_id}",
                        }
                        root_cause = eval_info.get('root_cause')
                        if root_cause:
                            payload['root_cause'] = root_cause
                        misclassification_analysis = eval_info.get('misclassification_analysis')
                        if misclassification_analysis:
                            payload['misclassification_analysis'] = misclassification_analysis
                        return json.dumps(payload)
                    else:
                        return json.dumps({
                            "status": "timeout",
                            "scorecard": scorecard_name,
                            "score": score_name,
                            "message": "Evaluation timed out waiting for completion.",
                        })

                else:
                    # Bulk mode: always fire-and-forget (multiple scores, can't wait on all).
                    logger.info(f"Bulk feedback evaluation (background) for '{scorecard_name}'")
                    sc_scores = await _fetch_scorecard_scores()
                    if not sc_scores:
                        return json.dumps({"error": f"No scores with champion versions found in scorecard '{scorecard_name}'"})

                    dispatched = []
                    for sc_score in sc_scores:
                        sn = sc_score['name']
                        cv = sc_score['championVersionId']
                        try:
                            _spawn_feedback(
                                scorecard_name,
                                sn,
                                days,
                                cv,
                                None,
                                max_feedback_samples,
                                sample_seed,
                                max_category_summary_items,
                            )
                            dispatched.append({"score_name": sn, "status": "dispatched", "champion_version_id": cv})
                            logger.info(f"Dispatched feedback evaluation for '{sn}'")
                        except Exception as exc:
                            dispatched.append({"score_name": sn, "status": "error", "error": str(exc)})

                    return json.dumps({
                        "mode": "bulk_feedback_evaluation",
                        "status": "dispatched",
                        "scorecard": scorecard_name,
                        "days": days,
                        "max_feedback_samples": max_feedback_samples,
                        "sample_seed": sample_seed,
                        "max_category_summary_items": max_category_summary_items,
                        "total_scores": len(sc_scores),
                        "dispatched": len([d for d in dispatched if d["status"] == "dispatched"]),
                        "scores": dispatched,
                        "message": "All evaluations are running in the background. Use plexus_evaluation_info to check status of individual evaluations.",
                        "dashboard_url": "https://lab.callcriteria.com/lab/evaluations",
                    })

            else:  # accuracy evaluation
                # Build CLI arguments for accuracy evaluation
                args = [
                    '--scorecard', scorecard_name,
                    '--number-of-samples', str(n_samples),
                    '--sampling-method', 'random'
                ]

                if yaml:
                    args.append('--yaml')

                if score_name:
                    args.extend(['--score', score_name])

                if version:
                    args.extend(['--version', version])

                if latest:
                    args.append('--latest')

                if fresh:
                    args.append('--fresh')

                if reload:
                    args.append('--reload')

                if allow_no_labels:
                    args.append('--allow-no-labels')

                if baseline:
                    args.extend(['--baseline', baseline])

                # Run the CLI command in a thread pool to avoid event loop conflicts
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

            if not evaluation_record:
                return json.dumps({"error": "Evaluation completed but no record returned"})
            
            # Check if it has an id attribute
            evaluation_id = getattr(evaluation_record, 'id', None)
            if not evaluation_id:
                return json.dumps({"error": f"Evaluation record missing id attribute. Type: {type(evaluation_record)}"})

            # Get full evaluation info using the specific ID
            eval_info = Evaluation.get_evaluation_info(evaluation_id)
            
            if not eval_info:
                return json.dumps({"error": f"Could not retrieve evaluation info for id: {evaluation_id}"})

            # Return the same format - note that get_evaluation_info uses snake_case keys
            eval_id = eval_info.get('id')
            response = {
                'evaluation_id': eval_id,
                'evaluation_type': evaluation_type,
                'scorecard_id': eval_info.get('scorecard_id'),
                'score_id': eval_info.get('score_id'),
                'accuracy': eval_info.get('accuracy'),
                'metrics': eval_info.get('metrics'),
                'confusionMatrix': eval_info.get('confusion_matrix'),  # snake_case in source
                'predictedClassDistribution': eval_info.get('predicted_class_distribution'),  # snake_case in source
                'datasetClassDistribution': eval_info.get('dataset_class_distribution'),  # snake_case in source
                'baselineEvaluationId': eval_info.get('baseline_evaluation_id'),
                'root_cause': eval_info.get('root_cause'),
                'misclassification_analysis': eval_info.get('misclassification_analysis'),
                'dashboard_url': f"https://app.plexusanalytics.com/evaluations/{eval_id}" if eval_id else None
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

    @mcp.tool()
    async def plexus_score_result_investigate(
        score_result_id: str,
        topic_context: str = ""
    ) -> str:
        """
        Investigate a single score result by running LLM inference to determine why the
        prediction was wrong and suggest a concrete fix.

        This tool fetches the score result, its feedback item (with reviewer edit comment),
        the item transcript, and the score's YAML configuration, then uses an LLM to analyze
        the misclassification and suggest a specific code change.

        Use this after plexus_evaluation_score_result_find to dig deeper into specific
        misclassifications, especially items not covered by the default top-6 RCA exemplars.

        Parameters:
        - score_result_id: The ID of the score result to investigate
        - topic_context: Optional topic/cluster label for additional context (e.g., "Copay Guarantee false alarms")
        """
        import json as _json

        try:
            from plexus.dashboard.api.client import PlexusDashboardClient
            client = PlexusDashboardClient()

            # 1. Fetch the score result
            sr_query = """
            query GetScoreResult($id: ID!) {
                getScoreResult(id: $id) {
                    id
                    value
                    explanation
                    itemId
                    feedbackItemId
                    scoreId
                    metadata
                }
            }
            """
            sr_resp = client.execute(sr_query, {"id": score_result_id})
            sr = sr_resp.get('getScoreResult')
            if not sr:
                return _json.dumps({"error": f"Score result '{score_result_id}' not found"})

            predicted_value = sr.get('value', '')
            score_explanation = sr.get('explanation', '')
            item_id = sr.get('itemId')
            feedback_item_id = sr.get('feedbackItemId')
            score_id = sr.get('scoreId')

            # Parse metadata for human_label if available
            human_label = None
            md = sr.get('metadata')
            if md:
                try:
                    if isinstance(md, str):
                        md = _json.loads(md)
                    if isinstance(md, dict):
                        res_md = md.get('results') or {}
                        if isinstance(res_md, dict) and res_md:
                            key0 = next(iter(res_md))
                            inner = res_md.get(key0) or {}
                            inner_md = inner.get('metadata') or {}
                            human_label = (inner_md.get('human_label') or '').strip()
                except Exception:
                    pass

            # 2. Fetch the feedback item (edit comment + original/corrected values)
            feedback_comment = ""
            feedback_initial = ""
            feedback_final = ""
            if feedback_item_id:
                try:
                    fi_query = """
                    query GetFeedbackItem($id: ID!) {
                        getFeedbackItem(id: $id) {
                            id
                            initialAnswerValue
                            finalAnswerValue
                            editCommentValue
                            isAgreement
                        }
                    }
                    """
                    fi_resp = client.execute(fi_query, {"id": feedback_item_id})
                    fi = fi_resp.get('getFeedbackItem') or {}
                    feedback_comment = fi.get('editCommentValue') or ''
                    feedback_initial = fi.get('initialAnswerValue') or ''
                    feedback_final = fi.get('finalAnswerValue') or ''
                    if not human_label:
                        human_label = feedback_final
                except Exception as e:
                    logger.warning(f"Could not fetch feedback item {feedback_item_id}: {e}")

            # 3. Fetch the item transcript
            transcript = ""
            item_identifiers = []
            if item_id:
                try:
                    item_query = """
                    query GetItem($id: ID!) {
                        getItem(id: $id) {
                            id
                            text
                            identifiers
                        }
                    }
                    """
                    item_resp = client.execute(item_query, {"id": item_id})
                    item_data = item_resp.get('getItem') or {}
                    transcript = item_data.get('text') or ''
                    identifiers_raw = item_data.get('identifiers')
                    if identifiers_raw:
                        if isinstance(identifiers_raw, str):
                            identifiers_raw = _json.loads(identifiers_raw)
                        item_identifiers = identifiers_raw or []
                except Exception as e:
                    logger.warning(f"Could not fetch item {item_id}: {e}")

            # 4. Fetch score configuration (YAML + guidelines)
            score_yaml_code = ""
            score_guidelines = ""
            if score_id:
                try:
                    score_query = f"""
                    {{
                        getScore(id: "{score_id}") {{
                            championVersionId
                        }}
                    }}
                    """
                    score_resp = client.execute(score_query)
                    score_data = score_resp.get('getScore') or {}
                    champion_id = score_data.get('championVersionId')
                    if champion_id:
                        version_query = f"""
                        {{
                            getScoreVersion(id: "{champion_id}") {{
                                configuration
                                guidelines
                            }}
                        }}
                        """
                        ver_resp = client.execute(version_query)
                        ver_data = ver_resp.get('getScoreVersion') or {}
                        score_yaml_code = ver_data.get('configuration') or ''
                        score_guidelines = ver_data.get('guidelines') or ''
                except Exception as e:
                    logger.warning(f"Could not fetch score config for {score_id}: {e}")

            correct_label = human_label or feedback_final or ''

            # 5. Build context summary for the response (always returned)
            result = {
                "score_result_id": score_result_id,
                "item_id": item_id,
                "identifiers": item_identifiers,
                "predicted_value": predicted_value,
                "actual_value": correct_label,
                "score_explanation": score_explanation,
                "feedback_comment": feedback_comment,
                "feedback_initial_value": feedback_initial,
                "feedback_final_value": feedback_final,
            }

            # 6. Run LLM inference if we have primary input context
            if not transcript:
                result["detailed_cause"] = "(no primary input available for LLM analysis)"
                result["suggested_fix"] = ""
                return _json.dumps(result, indent=2, default=str)

            try:
                from plexus.rca_analysis import analyze_score_result, build_feedback_context

                feedback_ctx = build_feedback_context(
                    feedback_comment=feedback_comment,
                    feedback_initial=feedback_initial,
                    feedback_final=feedback_final,
                    predicted_value=predicted_value,
                )
                detailed_cause, suggested_fix = analyze_score_result(
                    primary_input=transcript,
                    predicted=predicted_value,
                    correct=correct_label,
                    explanation=score_explanation,
                    topic_label=topic_context or "Score result investigation",
                    score_guidelines=score_guidelines,
                    score_yaml_code=score_yaml_code,
                    feedback_context=feedback_ctx,
                )

                result["detailed_cause"] = detailed_cause or "(analysis returned empty)"
                result["suggested_fix"] = suggested_fix

            except Exception as e:
                logger.warning(f"LLM inference failed for score result {score_result_id}: {e}")
                result["detailed_cause"] = f"(LLM inference failed: {str(e)})"
                result["suggested_fix"] = ""

            return _json.dumps(result, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error in plexus_score_result_investigate: {e}", exc_info=True)
            return _json.dumps({"error": f"Failed to investigate score result: {str(e)}"})
