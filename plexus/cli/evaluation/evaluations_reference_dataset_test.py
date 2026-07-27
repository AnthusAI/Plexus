import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pandas as pd
from click.testing import CliRunner

from plexus.cli.evaluation.evaluations import (
    assert_dataset_materialized_for_accuracy,
    accuracy,
    _apply_feedback_rca_outcome_to_parameters,
    _fetch_accuracy_evaluation_summary_for_json,
    _run_shared_feedback_root_cause_orchestration,
    build_dataset_materialization_failure_message,
    get_data_driven_samples,
    resolve_cloud_dataset_sample_limit,
    load_samples_from_cloud_dataset,
    get_latest_associated_dataset_for_score,
    list_associated_datasets_for_score,
    validate_dataset_materialization,
)


def test_data_driven_samples_fails_when_score_has_no_data_configuration(monkeypatch):
    """A configuration error must not be silently represented as zero samples."""
    monkeypatch.setattr(
        "plexus.cli.evaluation.evaluations.Score.load",
        lambda **_kwargs: SimpleNamespace(),
    )

    with pytest.raises(RuntimeError, match="Failed to load labeled samples"):
        get_data_driven_samples(
            scorecard_instance=SimpleNamespace(),
            scorecard_name="fixture-scorecard",
            score_name="fixture-score",
            score_config={"class": "TactusScore"},
            fresh=False,
            reload=False,
            content_ids_to_sample_set=set(),
        )


def test_list_associated_datasets_for_score_orders_newest_first():
    client = MagicMock()
    client.execute.return_value = {
        "listDataSets": {
            "items": [
                {
                    "id": "ds-1",
                    "scoreId": "score-123",
                    "createdAt": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "ds-2",
                    "scoreId": "score-123",
                    "createdAt": "2026-01-03T00:00:00Z",
                },
                {
                    "id": "ds-3",
                    "scoreId": "score-123",
                    "createdAt": "2026-01-02T00:00:00Z",
                },
            ]
        }
    }

    datasets = list_associated_datasets_for_score(client, "score-123")
    assert [d["id"] for d in datasets] == ["ds-2", "ds-3", "ds-1"]


def test_list_associated_datasets_for_score_tie_breaks_by_id():
    client = MagicMock()
    client.execute.return_value = {
        "listDataSets": {
            "items": [
                {
                    "id": "ds-a",
                    "scoreId": "score-123",
                    "createdAt": "2026-01-02T00:00:00Z",
                },
                {
                    "id": "ds-b",
                    "scoreId": "score-123",
                    "createdAt": "2026-01-02T00:00:00Z",
                },
            ]
        }
    }

    datasets = list_associated_datasets_for_score(client, "score-123")
    assert [d["id"] for d in datasets] == ["ds-b", "ds-a"]


def test_get_latest_associated_dataset_for_score_returns_newest():
    client = MagicMock()
    client.execute.return_value = {
        "listDataSets": {
            "items": [
                {
                    "id": "ds-old",
                    "scoreId": "score-123",
                    "createdAt": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "ds-new",
                    "scoreId": "score-123",
                    "createdAt": "2026-02-01T00:00:00Z",
                },
            ]
        }
    }

    dataset = get_latest_associated_dataset_for_score(client, "score-123")
    assert dataset["id"] == "ds-new"


def test_get_latest_associated_dataset_for_score_raises_when_none():
    client = MagicMock()
    client.execute.return_value = {"listDataSets": {"items": []}}

    with pytest.raises(ValueError, match="No associated dataset found"):
        get_latest_associated_dataset_for_score(client, "score-123")


def test_validate_dataset_materialization_reports_missing_file_pointer():
    readiness = validate_dataset_materialization({"id": "ds-1", "file": None})
    assert readiness["is_materialized"] is False
    assert readiness["dataset_id"] == "ds-1"
    assert readiness["dataset_file"] is None
    assert readiness["materialization_error"] == "missing_file_pointer"


def test_validate_dataset_materialization_reports_unsupported_file_type():
    readiness = validate_dataset_materialization({"id": "ds-1", "file": "datasets/ds-1/data.json"})
    assert readiness["is_materialized"] is False
    assert readiness["dataset_file"] == "datasets/ds-1/data.json"
    assert readiness["materialization_error"] == "unsupported_file_type"


def test_validate_dataset_materialization_accepts_parquet_and_csv():
    parquet = validate_dataset_materialization({"id": "ds-1", "file": "datasets/ds-1/data.parquet"})
    csv = validate_dataset_materialization({"id": "ds-2", "file": "datasets/ds-2/data.csv"})
    assert parquet["is_materialized"] is True
    assert parquet["materialization_error"] is None
    assert csv["is_materialized"] is True
    assert csv["materialization_error"] is None


def test_build_dataset_materialization_failure_message_is_machine_parseable():
    message = build_dataset_materialization_failure_message(
        dataset_id="ds-1",
        reason="missing_file_pointer",
        dataset_file=None,
        next_step_hint="Rebuild dataset and verify DataSet.file is persisted.",
    )
    assert message.startswith("dataset_materialization_failed ")
    assert "dataset_id=ds-1" in message
    assert "reason=missing_file_pointer" in message
    assert "dataset_file=none" in message


def test_assert_dataset_materialized_for_accuracy_raises_for_non_materialized_dataset():
    with pytest.raises(ValueError, match="dataset_materialization_failed"):
        assert_dataset_materialized_for_accuracy({"id": "ds-1", "file": None})


def test_assert_dataset_materialized_for_accuracy_returns_readiness_for_valid_dataset():
    readiness = assert_dataset_materialized_for_accuracy(
        {"id": "ds-1", "file": "datasets/account/ds-1/dataset.parquet"}
    )
    assert readiness["is_materialized"] is True
    assert readiness["dataset_file"] == "datasets/account/ds-1/dataset.parquet"


def test_load_samples_from_cloud_dataset_preserves_feedback_linkage_fields(tmp_path):
    source_csv = Path(tmp_path) / "source.csv"
    pd.DataFrame(
        [
            {
                "text": "hello",
                "Binary Score": "Yes",
                "content_id": "content-1",
                "item_id": "item-1",
                "feedback_item_id": "fi-1",
                "extra_col": "extra",
            }
        ]
    ).to_csv(source_csv, index=False)

    dataset = {"id": "ds-1", "file": "datasets/test.csv", "attachedFiles": []}

    mock_s3 = MagicMock()
    mock_s3.download_file.side_effect = (
        lambda _bucket, _key, output_path: shutil.copy(source_csv, output_path)
    )

    with patch("plexus.cli.evaluation.evaluations.get_amplify_bucket", return_value="bucket"), patch(
        "plexus.cli.evaluation.evaluations.boto3.client",
        return_value=mock_s3,
    ):
        samples = load_samples_from_cloud_dataset(
            dataset=dataset,
            score_name="Binary Score",
            score_config={},
            number_of_samples=None,
            random_seed=None,
        )

    assert len(samples) == 1
    sample = samples[0]
    assert sample["item_id"] == "item-1"
    assert sample["feedback_item_id"] == "fi-1"
    assert "item_id" not in sample["columns"]
    assert "feedback_item_id" not in sample["columns"]


def test_load_samples_from_cloud_dataset_filters_explicit_content_ids(tmp_path):
    source_csv = Path(tmp_path) / "source.csv"
    pd.DataFrame(
        [
            {"text": "first", "Binary Score": "Yes", "content_id": "content-1"},
            {"text": "second", "Binary Score": "No", "content_id": "content-2"},
        ]
    ).to_csv(source_csv, index=False)
    mock_s3 = MagicMock()
    mock_s3.download_file.side_effect = (
        lambda _bucket, _key, output_path: shutil.copy(source_csv, output_path)
    )

    with patch("plexus.cli.evaluation.evaluations.get_amplify_bucket", return_value="bucket"), patch(
        "plexus.cli.evaluation.evaluations.boto3.client",
        return_value=mock_s3,
    ):
        samples = load_samples_from_cloud_dataset(
            dataset={"id": "ds-1", "file": "datasets/test.csv", "attachedFiles": []},
            score_name="Binary Score",
            score_config={},
            content_ids_to_sample_set={"content-2"},
        )

    assert [sample["content_id"] for sample in samples] == ["content-2"]


@pytest.mark.parametrize("extension", ["csv", "parquet"])
def test_load_samples_from_explicit_local_dataset_file_without_s3(tmp_path, extension):
    source = Path(tmp_path) / f"matched-cohort.{extension}"
    frame = pd.DataFrame(
        [
            {
                "text": "local matched example",
                "Binary Score": "Yes",
                "content_id": "content-local-1",
                "item_id": "item-local-1",
                "feedback_item_id": "feedback-local-1",
            }
        ]
    )
    if extension == "csv":
        frame.to_csv(source, index=False)
    else:
        frame.to_parquet(source, index=False)

    with patch("plexus.cli.evaluation.evaluations.boto3.client") as boto_client:
        samples = load_samples_from_cloud_dataset(
            dataset={
                "id": "local-matched-cohort",
                "file": str(source),
                "attachedFiles": [],
            },
            score_name="Binary Score",
            score_config={},
        )

    boto_client.assert_not_called()
    assert len(samples) == 1
    assert samples[0]["content_id"] == "content-local-1"
    assert samples[0]["item_id"] == "item-local-1"
    assert samples[0]["feedback_item_id"] == "feedback-local-1"
    assert samples[0]["Binary Score_label"] == "Yes"


def test_accuracy_rejects_local_file_with_cloud_dataset_selector_before_execution(tmp_path):
    source = Path(tmp_path) / "matched-cohort.parquet"
    pd.DataFrame([{"text": "example", "Binary Score": "Yes"}]).to_parquet(
        source,
        index=False,
    )

    result = CliRunner().invoke(
        accuracy,
        [
            "--scorecard",
            "fixture-scorecard",
            "--dataset-file",
            str(source),
            "--dataset-id",
            "cloud-dataset",
        ],
    )

    assert result.exit_code != 0
    assert "--dataset-file is mutually exclusive with cloud dataset selectors" in result.output


def test_resolve_cloud_dataset_sample_limit_uses_full_dataset_when_default_not_explicit():
    assert resolve_cloud_dataset_sample_limit(
        number_of_samples=1,
        number_of_samples_explicit=False,
    ) is None


def test_resolve_cloud_dataset_sample_limit_respects_explicit_sample_cap():
    assert resolve_cloud_dataset_sample_limit(
        number_of_samples=25,
        number_of_samples_explicit=True,
    ) == 25


@pytest.mark.asyncio
async def test_shared_feedback_rca_orchestration_returns_none_coverage_when_no_links():
    client = MagicMock()
    client.execute.side_effect = [
        {
            "listScoreResultByEvaluationId": {
                "items": [
                    {
                        "id": "sr-1",
                        "value": "No",
                        "metadata": json.dumps({"correct": False, "human_label": "Yes"}),
                        "explanation": "prediction explanation",
                    }
                ],
                "nextToken": None,
            }
        }
    ]

    outcome = await _run_shared_feedback_root_cause_orchestration(
        client=client,
        account_key="acct-key",
        account_id="acct-id",
        evaluation_id="eval-1",
        scorecard_identifier="scorecard-1",
        scorecard_id="scorecard-1",
        score_id="score-1",
        score_version_id="version-1",
        max_items=50,
        sampling_mode="newest",
        sample_seed=None,
        max_category_summary_items=20,
        days=None,
        tracker=None,
        apply_feedback_window_selection=False,
    )

    assert outcome["incorrect_items_total"] == 1
    assert outcome["incorrect_items_with_feedback_link"] == 0
    assert outcome["incorrect_items_without_feedback_link"] == 1
    assert outcome["incorrect_items_analyzed_for_rca"] == 0
    assert outcome["rca_coverage_status"] == "none"
    assert outcome["root_cause_required"] is False
    assert outcome["has_usable_root_cause"] is False
    assert outcome["error_message"] is None
    assert any("RCA unavailable" in warning for warning in outcome["warnings"])


@pytest.mark.asyncio
async def test_shared_feedback_rca_all_time_selection_uses_persisted_results_only():
    """All-time RCA selection must not issue a second, differently capped feedback query."""
    client = MagicMock()
    client.execute.return_value = {
        "listScoreResultByEvaluationId": {"items": [], "nextToken": None}
    }

    with patch(
        "plexus.Evaluation.FeedbackEvaluation._fetch_feedback_items",
        new=AsyncMock(return_value=[]),
    ) as fetch:
        outcome = await _run_shared_feedback_root_cause_orchestration(
            client=client,
            account_key="acct-key",
            account_id="acct-id",
            evaluation_id="eval-1",
            scorecard_identifier="scorecard-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            score_version_id="version-1",
            max_items=200,
            sampling_mode="newest",
            sample_seed=None,
            max_category_summary_items=20,
            days=None,
            tracker=None,
            apply_feedback_window_selection=True,
        )

    fetch.assert_not_awaited()
    assert outcome["selection_metadata"]["selection_order_basis"] == "persisted evaluation ScoreResults"


@pytest.mark.asyncio
async def test_shared_feedback_rca_uses_persisted_evaluation_results_as_selection_authority():
    """RCA must not discard a scored mistake because a later feedback fetch differs."""
    client = MagicMock()

    def execute_side_effect(query, _variables):
        if "ListScoreResultsForEvaluation" in query:
            return {
                "listScoreResultByEvaluationId": {
                    "items": [
                        {
                            "id": "sr-1",
                            "value": "No",
                            "metadata": json.dumps(
                                {
                                    "feedback_item_id": "fi-scored",
                                    "results": {
                                        "Score": {
                                            "metadata": {
                                                "correct": False,
                                                "human_label": "Yes",
                                            }
                                        }
                                    },
                                }
                            ),
                            "explanation": "prediction explanation",
                        }
                    ],
                    "nextToken": None,
                }
            }
        if "GetOriginalScoreResult" in query:
            return {"listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt": {"items": []}}
        raise AssertionError(f"Unexpected query in test: {query}")

    client.execute.side_effect = execute_side_effect
    scored_feedback = SimpleNamespace(id="fi-scored", itemId="item-1", scoreId="score-1")
    unrelated_feedback = SimpleNamespace(id="fi-unrelated")

    with patch(
        "plexus.Evaluation.FeedbackEvaluation._fetch_feedback_items",
        new=AsyncMock(return_value=[unrelated_feedback]),
    ), patch(
        "plexus.cli.evaluation.evaluations._fetch_feedback_items_by_ids",
        new=AsyncMock(return_value={"fi-scored": scored_feedback}),
    ), patch(
        "plexus.Evaluation.FeedbackEvaluation._run_root_cause_analysis",
        new=AsyncMock(return_value={"topics": [{"label": "Topic A"}]}),
    ), patch(
        "plexus.Evaluation.FeedbackEvaluation._persist_root_cause_for_parameters",
        return_value={"topics": [{"label": "Topic A"}]},
    ):
        outcome = await _run_shared_feedback_root_cause_orchestration(
            client=client,
            account_key="acct-key",
            account_id="acct-id",
            evaluation_id="eval-1",
            scorecard_identifier="scorecard-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            score_version_id="version-1",
            max_items=200,
            sampling_mode="newest",
            sample_seed=None,
            max_category_summary_items=20,
            days=None,
            tracker=None,
            apply_feedback_window_selection=True,
        )

    assert outcome["incorrect_items_total"] == 1
    assert outcome["incorrect_items_analyzed_for_rca"] == 1


@pytest.mark.asyncio
async def test_shared_feedback_rca_orchestration_returns_partial_coverage_for_mixed_linkage():
    client = MagicMock()

    def execute_side_effect(query, _variables):
        if "ListScoreResultsForEvaluation" in query:
            return {
                "listScoreResultByEvaluationId": {
                    "items": [
                        {
                            "id": "sr-linked",
                            "value": "No",
                            "metadata": json.dumps(
                                {
                                    "correct": False,
                                    "human_label": "Yes",
                                    "feedback_item_id": "fi-1",
                                }
                            ),
                            "explanation": "linked explanation",
                        },
                        {
                            "id": "sr-unlinked",
                            "value": "No",
                            "metadata": json.dumps({"correct": False, "human_label": "Yes"}),
                            "explanation": "unlinked explanation",
                        },
                    ],
                    "nextToken": None,
                }
            }
        if "GetOriginalScoreResult" in query:
            return {
                "listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt": {
                    "items": []
                }
            }
        raise AssertionError(f"Unexpected query in test: {query}")

    client.execute.side_effect = execute_side_effect

    feedback_item = SimpleNamespace(
        id="fi-1",
        itemId="item-1",
        scoreId="score-1",
        editCommentValue="comment",
        finalCommentValue="final comment",
    )

    with patch(
        "plexus.cli.evaluation.evaluations._fetch_feedback_items_by_ids",
        new=AsyncMock(return_value={"fi-1": feedback_item}),
    ), patch(
        "plexus.Evaluation.FeedbackEvaluation._run_root_cause_analysis",
        new=AsyncMock(return_value={"topics": [{"label": "Topic A"}]}),
    ), patch(
        "plexus.Evaluation.FeedbackEvaluation._persist_root_cause_for_parameters",
        return_value={"topics": [{"label": "Topic A"}], "rca_item_failures_total": 1},
    ):
        outcome = await _run_shared_feedback_root_cause_orchestration(
            client=client,
            account_key="acct-key",
            account_id="acct-id",
            evaluation_id="eval-1",
            scorecard_identifier="scorecard-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            score_version_id="version-1",
            max_items=50,
            sampling_mode="newest",
            sample_seed=None,
            max_category_summary_items=20,
            days=None,
            tracker=None,
            apply_feedback_window_selection=False,
        )

    assert outcome["incorrect_items_total"] == 2
    assert outcome["incorrect_items_with_feedback_link"] == 1
    assert outcome["incorrect_items_without_feedback_link"] == 1
    assert outcome["incorrect_items_analyzed_for_rca"] == 1
    assert outcome["rca_item_failures_total"] == 1
    assert outcome["rca_coverage_status"] == "partial"
    assert outcome["root_cause_required"] is True
    assert outcome["has_usable_root_cause"] is True
    assert outcome["error_message"] is None
    assert any("missing feedback_item_id linkage" in warning for warning in outcome["warnings"])
    assert any("fallback analysis for 1 item" in warning for warning in outcome["warnings"])


def test_apply_feedback_rca_outcome_to_parameters_sets_coverage_and_warnings():
    existing = {"keep": "value"}
    outcome = {
        "root_cause": {"topics": [{"label": "Topic A"}]},
        "root_cause_required": True,
        "has_usable_root_cause": True,
        "incorrect_items_total": 10,
        "incorrect_items_with_feedback_link": 8,
        "incorrect_items_without_feedback_link": 2,
        "incorrect_items_analyzed_for_rca": 8,
        "rca_item_failures_total": 2,
        "rca_coverage_status": "partial",
        "warnings": ["missing feedback_item_id linkage for 2 incorrect item(s)"],
    }

    params = _apply_feedback_rca_outcome_to_parameters(existing, outcome)

    assert params["keep"] == "value"
    assert params["root_cause_required"] is True
    assert params["has_usable_root_cause"] is True
    assert params["root_cause"] == {"topics": [{"label": "Topic A"}]}
    assert params["incorrect_items_total"] == 10
    assert params["incorrect_items_with_feedback_link"] == 8
    assert params["incorrect_items_without_feedback_link"] == 2
    assert params["incorrect_items_analyzed_for_rca"] == 8
    assert params["rca_item_failures_total"] == 2
    assert params["rca_coverage_status"] == "partial"
    assert params["rca_warnings"] == ["missing feedback_item_id linkage for 2 incorrect item(s)"]


def test_apply_feedback_rca_outcome_to_parameters_clears_warnings_when_empty():
    existing = {"rca_warnings": ["old warning"]}
    outcome = {
        "root_cause": {},
        "root_cause_required": False,
        "has_usable_root_cause": False,
        "incorrect_items_total": 0,
        "incorrect_items_with_feedback_link": 0,
        "incorrect_items_without_feedback_link": 0,
        "incorrect_items_analyzed_for_rca": 0,
        "rca_coverage_status": "none",
        "warnings": [],
    }

    params = _apply_feedback_rca_outcome_to_parameters(existing, outcome)
    assert params["root_cause_required"] is False
    assert params["has_usable_root_cause"] is False
    assert params["incorrect_items_total"] == 0
    assert params["rca_coverage_status"] == "none"
    assert "rca_warnings" not in params


def test_fetch_accuracy_evaluation_summary_for_json_extracts_persisted_fields():
    client = MagicMock()
    evaluation = SimpleNamespace(
        status="COMPLETED",
        accuracy=88.5,
        processedItems=50,
        totalItems=50,
        scoreVersionId="sv-1",
        parameters=json.dumps(
            {
                "dataset_id": "ds-1",
                "metadata": {"baseline": "eval-baseline"},
                "root_cause_required": True,
                "root_cause": {"topics": [{"label": "Topic A"}]},
                "incorrect_items_total": 5,
                "incorrect_items_with_feedback_link": 4,
                "incorrect_items_without_feedback_link": 1,
                "incorrect_items_analyzed_for_rca": 4,
                "rca_coverage_status": "partial",
                "rca_warnings": ["missing feedback linkage for 1 item"],
            }
        ),
    )

    with patch("plexus.cli.evaluation.evaluations.PlexusDashboardClient", return_value=client), patch(
        "plexus.cli.evaluation.evaluations.DashboardEvaluation.get_by_id",
        return_value=evaluation,
    ):
        summary = _fetch_accuracy_evaluation_summary_for_json("eval-1")

    assert summary["status"] == "COMPLETED"
    assert summary["accuracy"] == 88.5
    assert summary["processed_items"] == 50
    assert summary["total_items"] == 50
    assert summary["score_version_id"] == "sv-1"
    assert summary["dataset_id"] == "ds-1"
    assert summary["baseline"] == "eval-baseline"
    assert summary["root_cause_required"] is True
    assert summary["has_root_cause"] is True
    assert summary["incorrect_items_total"] == 5
    assert summary["incorrect_items_with_feedback_link"] == 4
    assert summary["incorrect_items_without_feedback_link"] == 1
    assert summary["incorrect_items_analyzed_for_rca"] == 4
    assert summary["rca_coverage_status"] == "partial"
    assert summary["rca_warnings"] == ["missing feedback linkage for 1 item"]


def test_fetch_accuracy_evaluation_summary_for_json_returns_empty_on_lookup_error():
    with patch("plexus.cli.evaluation.evaluations.PlexusDashboardClient"), patch(
        "plexus.cli.evaluation.evaluations.DashboardEvaluation.get_by_id",
        side_effect=RuntimeError("lookup failed"),
    ):
        assert _fetch_accuracy_evaluation_summary_for_json("eval-1") == {}
