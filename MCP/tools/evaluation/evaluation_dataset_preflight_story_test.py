#!/usr/bin/env python3
"""
BDD-style scenarios for dataset-backed accuracy preflight readiness.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.unit


class _FakeCliResult:
    def __init__(self, exit_code=0, output="", return_value=None):
        self.exit_code = exit_code
        self.output = output
        self.return_value = return_value


class _FakeCliRunner:
    def invoke(self, _command, _args, catch_exceptions=False, standalone_mode=False):  # noqa: ARG002
        return _FakeCliResult(exit_code=0, output="", return_value=SimpleNamespace(id="eval-123"))


class TestEvaluationDatasetPreflightScenarios:
    @pytest.mark.asyncio
    async def test_dataset_backed_accuracy_starts_when_materialized_scenario(self):
        """
        Scenario: Build/check/evaluate loop proceeds when dataset is materialized
        Given a dataset-backed accuracy run with a materialized dataset
        When evaluation_run is invoked
        Then accuracy dispatch succeeds and returns evaluation_id
        """
        from tools.evaluation.evaluations import register_evaluation_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool_decorator
        register_evaluation_tools(mock_mcp)
        run_tool = registered_tools["plexus_evaluation_run"]

        with patch("plexus.cli.shared.client_utils.create_client", return_value=Mock()), patch(
            "plexus.cli.evaluation.evaluations.get_dataset_by_id",
            return_value={"id": "ds-1", "file": "datasets/account/ds-1/dataset.parquet"},
        ), patch(
            "plexus.cli.evaluation.evaluations.validate_dataset_materialization",
            return_value={
                "is_materialized": True,
                "dataset_id": "ds-1",
                "dataset_file": "datasets/account/ds-1/dataset.parquet",
                "materialization_error": None,
                "next_step_hint": None,
            },
        ), patch(
            "click.testing.CliRunner",
            return_value=_FakeCliRunner(),
        ), patch(
            "plexus.Evaluation.Evaluation.get_evaluation_info",
            return_value={
                "id": "eval-123",
                "scorecard_id": "sc-1",
                "score_id": "score-1",
                "accuracy": 0.91,
                "metrics": [],
                "confusion_matrix": None,
                "predicted_class_distribution": None,
                "dataset_class_distribution": None,
                "baseline_evaluation_id": None,
                "root_cause": None,
                "misclassification_analysis": None,
            },
        ):
            raw = await run_tool(
                scorecard_name="1039",
                score_name="45425",
                evaluation_type="accuracy",
                dataset_id="ds-1",
            )
            payload = json.loads(raw)
            assert payload["evaluation_id"] == "eval-123"
            assert payload["evaluation_type"] == "accuracy"

    @pytest.mark.asyncio
    async def test_dataset_record_without_file_pointer_fails_preflight_scenario(self):
        """
        Scenario: Dataset record exists without file pointer -> preflight fails early
        Given a dataset-backed accuracy request targets a non-materialized dataset
        When evaluation_run is invoked
        Then tool returns actionable preflight error before CLI score execution
        """
        from tools.evaluation.evaluations import register_evaluation_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool_decorator
        register_evaluation_tools(mock_mcp)
        run_tool = registered_tools["plexus_evaluation_run"]

        with patch("plexus.cli.shared.client_utils.create_client", return_value=Mock()), patch(
            "plexus.cli.evaluation.evaluations.get_dataset_by_id",
            return_value={"id": "ds-2", "file": None},
        ), patch(
            "plexus.cli.evaluation.evaluations.validate_dataset_materialization",
            return_value={
                "is_materialized": False,
                "dataset_id": "ds-2",
                "dataset_file": None,
                "materialization_error": "missing_file_pointer",
                "next_step_hint": "Rebuild dataset and verify DataSet.file is persisted.",
            },
        ):
            raw = await run_tool(
                scorecard_name="1039",
                score_name="45425",
                evaluation_type="accuracy",
                dataset_id="ds-2",
            )
            payload = json.loads(raw)
            assert payload["dataset_id"] == "ds-2"
            assert payload["readiness_failure_reason"] == "missing_file_pointer"
            assert "preflight failed" in payload["error"].lower()
            assert "rebuild dataset" in payload["next_step_hint"].lower()

    @pytest.mark.asyncio
    async def test_latest_associated_dataset_rejected_when_non_materialized_scenario(self):
        """
        Scenario: Associated dataset selected by score is newest but rejected if non-materialized
        Given latest associated dataset exists without materialized file pointer
        When use_score_associated_dataset evaluation is requested
        Then preflight rejects that dataset with reason code
        """
        from tools.evaluation.evaluations import register_evaluation_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool_decorator
        register_evaluation_tools(mock_mcp)
        run_tool = registered_tools["plexus_evaluation_run"]

        with patch("plexus.cli.shared.client_utils.create_client", return_value=Mock()), patch(
            "plexus.cli.evaluation.evaluations.resolve_primary_score_id_for_accuracy",
            return_value="score-1",
        ), patch(
            "plexus.cli.evaluation.evaluations.get_latest_associated_dataset_for_score",
            return_value={"id": "ds-new", "file": None},
        ), patch(
            "plexus.cli.evaluation.evaluations.validate_dataset_materialization",
            return_value={
                "is_materialized": False,
                "dataset_id": "ds-new",
                "dataset_file": None,
                "materialization_error": "missing_file_pointer",
                "next_step_hint": "Rebuild dataset and verify DataSet.file is persisted.",
            },
        ):
            raw = await run_tool(
                scorecard_name="1039",
                score_name="45425",
                evaluation_type="accuracy",
                use_score_associated_dataset=True,
            )
            payload = json.loads(raw)
            assert payload["dataset_id"] == "ds-new"
            assert payload["readiness_failure_reason"] == "missing_file_pointer"
