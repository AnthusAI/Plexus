#!/usr/bin/env python3
"""
Evaluation comparison tools for Plexus MCP Server
"""
import json
import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_evaluation_comparison_tools(mcp: FastMCP):
    """Register evaluation comparison tools with the MCP server"""

    @mcp.tool()
    async def plexus_evaluation_compare(
        evaluation_id: str,
        baseline_evaluation_id: str,
        account_key: Optional[str] = None
    ) -> str:
        """
        Compare two evaluations and return metric deltas.

        This tool fetches two evaluations and calculates the difference in their metrics,
        making it easy to track improvement or regression between a baseline and current evaluation.

        Parameters:
        - evaluation_id: The current evaluation ID to compare
        - baseline_evaluation_id: The baseline evaluation ID to compare against
        - account_key: Optional account key (uses PLEXUS_ACCOUNT_KEY env var if not provided)

        Returns:
        - JSON string with:
          - evaluation_id: Current evaluation ID
          - baseline_evaluation_id: Baseline evaluation ID
          - current_metrics: Current evaluation metrics (Alignment, Accuracy, Precision, Recall)
          - baseline_metrics: Baseline evaluation metrics
          - deltas: Difference between current and baseline (current - baseline)
          - improved: Boolean indicating if Alignment improved
        """
        import os

        # Use PLEXUS_ACCOUNT_KEY environment variable if no account_key provided
        if account_key is None:
            account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
            if account_key is None:
                return json.dumps({
                    "error": "account_key must be provided or PLEXUS_ACCOUNT_KEY environment variable must be set"
                })

        try:
            from plexus.Evaluation import Evaluation
        except ImportError as e:
            return json.dumps({
                "error": f"Could not import Evaluation class: {str(e)}"
            })

        # Validate parameters
        if not evaluation_id or not evaluation_id.strip():
            return json.dumps({"error": "evaluation_id cannot be empty"})

        if not baseline_evaluation_id or not baseline_evaluation_id.strip():
            return json.dumps({"error": "baseline_evaluation_id cannot be empty"})

        try:
            # Fetch both evaluations
            current_eval = Evaluation.get_evaluation_info(evaluation_id.strip(), include_score_results=False)
            baseline_eval = Evaluation.get_evaluation_info(baseline_evaluation_id.strip(), include_score_results=False)

            if not current_eval:
                return json.dumps({"error": f"Current evaluation not found: {evaluation_id}"})

            if not baseline_eval:
                return json.dumps({"error": f"Baseline evaluation not found: {baseline_evaluation_id}"})

            # Extract metrics from both evaluations
            def extract_metrics(eval_info: Dict[str, Any]) -> Dict[str, float]:
                """Extract metrics into a clean dict"""
                metrics = {}
                if 'metrics' in eval_info and isinstance(eval_info['metrics'], list):
                    for metric in eval_info['metrics']:
                        if isinstance(metric, dict) and 'name' in metric and 'value' in metric:
                            metrics[metric['name']] = float(metric['value'])
                return metrics

            current_metrics = extract_metrics(current_eval)
            baseline_metrics = extract_metrics(baseline_eval)

            # Calculate deltas
            deltas = {}
            for key in current_metrics.keys():
                if key in baseline_metrics:
                    deltas[key] = current_metrics[key] - baseline_metrics[key]

            # Determine if improved (based on Alignment/AC1)
            improved = deltas.get('Alignment', 0) > 0

            result = {
                "evaluation_id": evaluation_id,
                "baseline_evaluation_id": baseline_evaluation_id,
                "current_metrics": current_metrics,
                "baseline_metrics": baseline_metrics,
                "deltas": deltas,
                "improved": improved
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Error comparing evaluations: {str(e)}", exc_info=True)
            return json.dumps({
                "error": f"Failed to compare evaluations: {str(e)}"
            })
