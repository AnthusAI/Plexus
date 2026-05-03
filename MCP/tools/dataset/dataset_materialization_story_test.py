#!/usr/bin/env python3
"""
BDD-style scenarios for associated-dataset materialization readiness.
"""
import json
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.unit


class TestAssociatedDatasetMaterializationScenarios:
    @pytest.mark.asyncio
    async def test_build_check_happy_path_scenario(self):
        """
        Scenario: Build associated dataset -> check readiness reports materialized
        Given a score has qualifying feedback and dataset file persisted
        When build and check tools are invoked
        Then readiness is materialized and dataset_file is explicit
        """
        from tools.dataset.datasets import register_dataset_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool_decorator
        register_dataset_tools(mock_mcp)

        build_tool = registered_tools["plexus_dataset_build_from_feedback_window"]
        check_tool = registered_tools["plexus_dataset_check_associated"]

        mock_client = Mock()
        mock_client.execute.return_value = {"getDataSourceVersion": None}

        with patch("plexus.cli.dataset.datasets.create_client", return_value=mock_client), patch(
            "plexus.cli.shared.identifier_resolution.resolve_scorecard_identifier",
            return_value="sc-1",
        ), patch(
            "plexus.cli.shared.identifier_resolution.resolve_score_identifier",
            return_value="score-1",
        ), patch(
            "plexus.cli.dataset.curation.build_associated_dataset_from_feedback_window",
            return_value={
                "dataset_id": "ds-1",
                "rows_written": 120,
                "s3_key": "datasets/account/ds-1/dataset.parquet",
            },
        ), patch(
            "plexus.cli.evaluation.evaluations.validate_dataset_materialization",
            return_value={
                "is_materialized": True,
                "dataset_id": "ds-1",
                "dataset_file": "datasets/account/ds-1/dataset.parquet",
                "materialization_error": None,
                "next_step_hint": None,
            },
        ):
            build_result = json.loads(
                await build_tool(scorecard="1039", score="45425", max_items=100, days=180, balance=True)
            )
            assert build_result["dataset_id"] == "ds-1"
            assert build_result["dataset_file"] == "datasets/account/ds-1/dataset.parquet"
            assert build_result["is_materialized"] is True
            assert build_result["materialization_error"] is None

        with patch("plexus.cli.dataset.datasets.create_client", return_value=mock_client), patch(
            "plexus.cli.shared.identifier_resolution.resolve_scorecard_identifier",
            return_value="sc-1",
        ), patch(
            "plexus.cli.shared.identifier_resolution.resolve_score_identifier",
            return_value="score-1",
        ), patch(
            "plexus.cli.evaluation.evaluations.get_latest_associated_dataset_for_score",
            return_value={
                "id": "ds-1",
                "name": "Associated Dataset",
                "createdAt": "2026-04-05T10:00:00Z",
                "file": "datasets/account/ds-1/dataset.parquet",
                "dataSourceVersionId": None,
            },
        ), patch(
            "plexus.cli.evaluation.evaluations.validate_dataset_materialization",
            return_value={
                "is_materialized": True,
                "dataset_id": "ds-1",
                "dataset_file": "datasets/account/ds-1/dataset.parquet",
                "materialization_error": None,
                "next_step_hint": None,
            },
        ):
            check_result = json.loads(await check_tool(scorecard="1039", score="45425"))
            assert check_result["has_dataset"] is True
            assert check_result["dataset_id"] == "ds-1"
            assert check_result["is_materialized"] is True
            assert check_result["dataset_file"] == "datasets/account/ds-1/dataset.parquet"
            assert check_result["materialization_error"] is None

    @pytest.mark.asyncio
    async def test_check_associated_reports_non_materialized_scenario(self):
        """
        Scenario: Check-associated reports row_count but flags non-materialized dataset
        Given latest associated dataset exists without DataSet.file
        When check tool runs
        Then result reports has_dataset with materialization_error
        """
        from tools.dataset.datasets import register_dataset_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool_decorator
        register_dataset_tools(mock_mcp)
        check_tool = registered_tools["plexus_dataset_check_associated"]

        mock_client = Mock()
        mock_client.execute.return_value = {
            "getDataSourceVersion": {
                "id": "dsv-1",
                "yamlConfiguration": "dataset_stats:\n  row_count: 200\n",
            }
        }

        with patch("plexus.cli.dataset.datasets.create_client", return_value=mock_client), patch(
            "plexus.cli.shared.identifier_resolution.resolve_scorecard_identifier",
            return_value="sc-1",
        ), patch(
            "plexus.cli.shared.identifier_resolution.resolve_score_identifier",
            return_value="score-1",
        ), patch(
            "plexus.cli.evaluation.evaluations.get_latest_associated_dataset_for_score",
            return_value={
                "id": "ds-2",
                "name": "Broken Associated Dataset",
                "createdAt": "2026-04-05T11:00:00Z",
                "file": None,
                "dataSourceVersionId": "dsv-1",
            },
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
            result = json.loads(await check_tool(scorecard="1039", score="45425"))
            assert result["has_dataset"] is True
            assert result["dataset_id"] == "ds-2"
            assert result["row_count"] == 200
            assert result["is_materialized"] is False
            assert result["dataset_file"] is None
            assert result["materialization_error"] == "missing_file_pointer"

    @pytest.mark.asyncio
    async def test_build_tool_rejects_success_without_dataset_file_scenario(self):
        """
        Scenario: Builder must not emit success payload when dataset_file is absent
        Given builder returns dataset metadata without persisted file pointer
        When build-from-feedback-window tool returns
        Then tool reports explicit error instead of success JSON
        """
        from tools.dataset.datasets import register_dataset_tools

        mock_mcp = Mock()
        registered_tools = {}

        def mock_tool_decorator():
            def decorator(func):
                registered_tools[func.__name__] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool_decorator
        register_dataset_tools(mock_mcp)
        build_tool = registered_tools["plexus_dataset_build_from_feedback_window"]

        with patch("plexus.cli.dataset.datasets.create_client", return_value=Mock()), patch(
            "plexus.cli.shared.identifier_resolution.resolve_scorecard_identifier",
            return_value="sc-1",
        ), patch(
            "plexus.cli.shared.identifier_resolution.resolve_score_identifier",
            return_value="score-1",
        ), patch(
            "plexus.cli.dataset.curation.build_associated_dataset_from_feedback_window",
            return_value={
                "dataset_id": "ds-err",
                "rows_written": 200,
            },
        ), patch(
            "plexus.cli.evaluation.evaluations.validate_dataset_materialization",
            return_value={
                "is_materialized": False,
                "dataset_id": "ds-err",
                "dataset_file": None,
                "materialization_error": "missing_file_pointer",
                "next_step_hint": "Rebuild dataset and verify DataSet.file is persisted.",
            },
        ):
            result = await build_tool(scorecard="1039", score="45425", max_items=200, days=180, balance=True)
            assert result.startswith("Error:")
            assert "dataset_id=ds-err" in result
            assert "missing_file_pointer" in result
