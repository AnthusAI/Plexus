"""
Alignment Optimizer - Programmatic interface for feedback evaluation optimization with RCA

This module provides a clean Python API for running the Tactus-based feedback alignment
optimizer procedure, enabling integration into automated systems and agentic applications.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class AlignmentOptimizer:
    """
    Programmatic interface to feedback alignment optimization using Tactus procedures.

    This class wraps the feedback_alignment_optimizer Tactus procedure, providing
    a simple Python API for running iterative score optimization with RCA-based analysis.

    Example:
        ```python
        from plexus.agentic import AlignmentOptimizer
        from plexus.dashboard.api.client import PlexusDashboardClient

        client = PlexusDashboardClient(api_key="...")
        optimizer = AlignmentOptimizer(client, mcp_server)

        result = await optimizer.optimize(
            scorecard="customer-service",
            score="empathy",
            days=90,
            max_iterations=10
        )

        print(f"Improved AC1 by {result['improvement']:.4f}")
        print(f"Completed {len(result['iterations'])} iterations")
        ```
    """

    def __init__(self, client, mcp_server):
        """
        Initialize the AlignmentOptimizer.

        Args:
            client: PlexusDashboardClient instance with valid credentials
            mcp_server: MCP server instance for tool execution
        """
        self.client = client
        self.mcp_server = mcp_server
        self._procedure_yaml = None

    def _load_procedure_yaml(self) -> str:
        """Load the feedback alignment optimizer procedure YAML."""
        if self._procedure_yaml is not None:
            return self._procedure_yaml

        # Determine procedure file path relative to this module
        current_file = Path(__file__)
        procedure_path = current_file.parent.parent / "procedures" / "feedback_alignment_optimizer.yaml"

        if not procedure_path.exists():
            raise FileNotFoundError(
                f"Procedure YAML not found at {procedure_path}. "
                "Ensure feedback_alignment_optimizer.yaml exists in plexus/procedures/"
            )

        with open(procedure_path, 'r') as f:
            self._procedure_yaml = f.read()

        return self._procedure_yaml

    async def optimize(
        self,
        scorecard: str,
        score: str,
        days: int = 90,
        max_iterations: int = 10,
        improvement_threshold: float = 0.02,
        dry_run: bool = False,
        on_iteration: Optional[Callable[[int, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Run feedback evaluation optimization for a score.

        This method executes the complete optimization workflow:
        1. Run baseline feedback evaluation with RCA
        2. Iteratively analyze RCA, propose changes, evaluate, and compare
        3. Return comprehensive results with all iteration data

        Args:
            scorecard: Scorecard identifier (name, key, or ID)
            score: Score identifier (name, key, or ID)
            days: Feedback window in days (default: 90)
            max_iterations: Maximum optimization iterations (default: 10)
            improvement_threshold: Minimum AC1 improvement to continue (default: 0.02 = 2%)
            dry_run: If True, run analysis only without making score updates (default: False)
            on_iteration: Optional callback called after each iteration with (iteration_num, iteration_data)

        Returns:
            Dict containing:
                - success: bool - Whether optimization completed successfully
                - status: str - Completion status (converged, max_iterations, user_stopped, etc.)
                - message: str - Human-readable summary message
                - baseline_evaluation_id: str - Initial baseline evaluation ID
                - final_evaluation_id: str - Final evaluation ID
                - iterations: list - Array of iteration results with metrics and deltas
                - improvement: float - Total AC1 improvement from baseline to final
                - scorecard_id: str - Resolved scorecard ID
                - score_id: str - Resolved score ID

        Raises:
            FileNotFoundError: If procedure YAML cannot be found
            Exception: If procedure execution fails
        """
        from plexus.cli.procedure.procedure_executor import execute_procedure

        logger.info(
            f"Starting alignment optimization: scorecard={scorecard}, score={score}, "
            f"days={days}, max_iterations={max_iterations}, dry_run={dry_run}"
        )

        # Load procedure YAML
        procedure_yaml = self._load_procedure_yaml()

        # Generate unique procedure ID
        procedure_id = f"optimize-{scorecard}-{score}-{int(time.time())}"

        # Build context with parameters
        context = {
            "scorecard": scorecard,
            "score": score,
            "days": days,
            "max_iterations": max_iterations,
            "improvement_threshold": improvement_threshold,
            "dry_run": dry_run
        }

        logger.info(f"Executing procedure {procedure_id} with context: {context}")

        # Execute procedure
        try:
            result = await execute_procedure(
                procedure_id=procedure_id,
                procedure_code=procedure_yaml,
                client=self.client,
                mcp_server=self.mcp_server,
                context=context
            )

            # Call iteration callback if provided
            if on_iteration and "iterations" in result:
                for iteration_data in result["iterations"]:
                    try:
                        on_iteration(iteration_data["iteration"], iteration_data)
                    except Exception as e:
                        logger.warning(f"Iteration callback failed: {e}")

            logger.info(
                f"Optimization complete: status={result.get('status')}, "
                f"improvement={result.get('improvement', 0):.4f}"
            )

            return result

        except Exception as e:
            logger.error(f"Optimization failed: {e}", exc_info=True)
            raise

    async def run_baseline_only(
        self,
        scorecard: str,
        score: str,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Run only the baseline evaluation without optimization iterations.

        This is useful for getting an initial RCA analysis before deciding
        whether to proceed with full optimization.

        Args:
            scorecard: Scorecard identifier
            score: Score identifier
            days: Feedback window in days

        Returns:
            Dict with baseline evaluation results and RCA
        """
        # Run optimization with max_iterations=0 to get baseline only
        # Note: This requires modifying the procedure to support max_iterations=0
        # For now, we use max_iterations=1 with dry_run=True
        result = await self.optimize(
            scorecard=scorecard,
            score=score,
            days=days,
            max_iterations=1,
            dry_run=True
        )

        return {
            "baseline_evaluation_id": result.get("baseline_evaluation_id"),
            "baseline_metrics": result["iterations"][0]["metrics"] if result.get("iterations") else None,
            "rca": result["iterations"][0].get("rca_summary") if result.get("iterations") else None
        }


class OptimizationMonitor:
    """
    Helper class for monitoring optimization progress in real-time.

    Example:
        ```python
        monitor = OptimizationMonitor()

        result = await optimizer.optimize(
            scorecard="customer-service",
            score="empathy",
            on_iteration=monitor.on_iteration
        )

        monitor.print_summary()
        ```
    """

    def __init__(self):
        self.iterations = []

    def on_iteration(self, iteration_num: int, iteration_data: Dict[str, Any]):
        """Callback for each completed iteration."""
        self.iterations.append(iteration_data)

        deltas = iteration_data.get("deltas", {})
        metrics = iteration_data.get("metrics", {})

        print(f"\n=== Iteration {iteration_num} ===")
        print(f"Hypothesis: {iteration_data.get('hypothesis', 'N/A')}")
        print(f"AC1: {metrics.get('alignment', 0):.4f} (Δ{deltas.get('alignment', 0):+.4f})")
        print(f"Accuracy: {metrics.get('accuracy', 0):.4f} (Δ{deltas.get('accuracy', 0):+.4f})")
        print(f"Precision: {metrics.get('precision', 0):.4f} (Δ{deltas.get('precision', 0):+.4f})")
        print(f"Recall: {metrics.get('recall', 0):.4f} (Δ{deltas.get('recall', 0):+.4f})")

    def print_summary(self):
        """Print a summary of all iterations."""
        if not self.iterations:
            print("No iterations completed.")
            return

        print("\n" + "="*60)
        print("OPTIMIZATION SUMMARY")
        print("="*60)

        first_metrics = self.iterations[0].get("metrics", {})
        last_metrics = self.iterations[-1].get("metrics", {})

        print(f"Total iterations: {len(self.iterations)}")
        print(f"\nBaseline → Final:")
        print(f"  AC1:       {first_metrics.get('alignment', 0):.4f} → {last_metrics.get('alignment', 0):.4f} "
              f"({last_metrics.get('alignment', 0) - first_metrics.get('alignment', 0):+.4f})")
        print(f"  Accuracy:  {first_metrics.get('accuracy', 0):.4f} → {last_metrics.get('accuracy', 0):.4f} "
              f"({last_metrics.get('accuracy', 0) - first_metrics.get('accuracy', 0):+.4f})")
        print(f"  Precision: {first_metrics.get('precision', 0):.4f} → {last_metrics.get('precision', 0):.4f} "
              f"({last_metrics.get('precision', 0) - first_metrics.get('precision', 0):+.4f})")
        print(f"  Recall:    {first_metrics.get('recall', 0):.4f} → {last_metrics.get('recall', 0):.4f} "
              f"({last_metrics.get('recall', 0) - first_metrics.get('recall', 0):+.4f})")

        print("\nIterations:")
        for it in self.iterations:
            deltas = it.get("deltas", {})
            print(f"  {it['iteration']}: {it.get('hypothesis', 'N/A')[:60]} "
                  f"(AC1 Δ{deltas.get('alignment', 0):+.4f})")

        print("="*60)
