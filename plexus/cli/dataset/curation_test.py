from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from plexus.cli.dataset.curation import (
    _compute_label_distribution,
    _ordered_unique_feedback_ids,
    _select_balanced_feedback_items,
    build_associated_dataset_from_vetted_feedback_items,
    build_associated_dataset_from_vetted_report,
    build_associated_dataset_from_feedback_window,
    collect_qualifying_feedback_items,
    resolve_score_valid_classes_from_score_yaml,
)


def _make_feedback_item_dict(
    item_id: str,
    *,
    edited_at: str,
    final_answer: str = "Yes",
    is_invalid: bool = False,
    include_item: bool = True,
):
    payload = {
        "id": item_id,
        "accountId": "account-1",
        "scorecardId": "scorecard-1",
        "scoreId": "score-1",
        "itemId": f"item-{item_id}",
        "finalAnswerValue": final_answer,
        "isInvalid": is_invalid,
        "editedAt": edited_at,
    }
    if include_item:
        payload["item"] = {
            "id": f"item-{item_id}",
            "text": f"text-{item_id}",
            "metadata": "{}",
            "identifiers": [],
        }
    return payload


def _to_feedback_model(item_dict, **_kwargs):
    item = item_dict.get("item")
    return SimpleNamespace(
        id=item_dict.get("id"),
        accountId=item_dict.get("accountId"),
        scorecardId=item_dict.get("scorecardId"),
        scoreId=item_dict.get("scoreId"),
        finalAnswerValue=item_dict.get("finalAnswerValue"),
        isInvalid=item_dict.get("isInvalid"),
        editedAt=item_dict.get("editedAt"),
        item=SimpleNamespace(
            id=item.get("id"),
            text=item.get("text"),
        ) if item else None,
    )


def test_collect_qualifying_feedback_items_caps_and_orders():
    client = MagicMock()
    client.execute = MagicMock(
        side_effect=[
            {
                "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                    "items": [
                        _make_feedback_item_dict("b", edited_at="2026-03-02T00:00:00Z"),
                        _make_feedback_item_dict("a", edited_at="2026-03-03T00:00:00Z"),
                        _make_feedback_item_dict("skip-empty", edited_at="2026-03-04T00:00:00Z", final_answer=""),
                    ],
                    "nextToken": "NEXT",
                }
            },
            {
                "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                    "items": [
                        _make_feedback_item_dict("c", edited_at="2026-03-01T00:00:00Z"),
                    ],
                    "nextToken": None,
                }
            },
        ]
    )

    with patch("plexus.cli.dataset.curation.FeedbackItem.from_dict", side_effect=_to_feedback_model):
        items = collect_qualifying_feedback_items(
            client=client,
            account_id="account-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            max_items=2,
            days=None,
        )

    assert [item.id for item in items] == ["a", "b"]
    assert client.execute.call_count == 1


def test_collect_qualifying_feedback_items_excludes_invalid():
    client = MagicMock()
    client.execute = MagicMock(
        return_value={
            "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                "items": [
                    _make_feedback_item_dict("valid", edited_at="2026-03-03T00:00:00Z", is_invalid=False),
                    _make_feedback_item_dict("invalid", edited_at="2026-03-02T00:00:00Z", is_invalid=True),
                ],
                "nextToken": None,
            }
        }
    )

    with patch("plexus.cli.dataset.curation.FeedbackItem.from_dict", side_effect=_to_feedback_model):
        items = collect_qualifying_feedback_items(
            client=client,
            account_id="account-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            max_items=10,
            days=None,
        )

    assert [item.id for item in items] == ["valid"]


def test_collect_qualifying_feedback_items_excludes_shadow_invalid_ids():
    client = MagicMock()
    client.execute = MagicMock(
        return_value={
            "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                "items": [
                    _make_feedback_item_dict("keep", edited_at="2026-03-03T00:00:00Z", is_invalid=False),
                    _make_feedback_item_dict("shadow", edited_at="2026-03-02T00:00:00Z", is_invalid=False),
                ],
                "nextToken": None,
            }
        }
    )

    with patch("plexus.cli.dataset.curation.FeedbackItem.from_dict", side_effect=_to_feedback_model):
        items = collect_qualifying_feedback_items(
            client=client,
            account_id="account-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            max_items=10,
            days=None,
            excluded_feedback_item_ids=["shadow"],
        )

    assert [item.id for item in items] == ["keep"]


def test_collect_qualifying_feedback_items_rejects_non_positive_max():
    with pytest.raises(ValueError, match="--max-items must be greater than 0"):
        collect_qualifying_feedback_items(
            client=MagicMock(),
            account_id="account-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            max_items=0,
            days=None,
        )


def test_resolve_score_valid_classes_from_score_yaml_extracts_deterministically():
    client = MagicMock()
    client.execute = MagicMock(
        side_effect=[
            {"getScore": {"id": "score-1", "championVersionId": "sv-1"}},
            {
                "getScoreVersion": {
                    "id": "sv-1",
                    "configuration": """
classes:
  - name: Yes
  - name: No
graph:
  - name: classifier_one
    valid_classes: ["No", "Maybe"]
  - name: classifier_two
    valid_classes: ["Escalate", "Yes"]
""",
                }
            },
        ]
    )

    classes = resolve_score_valid_classes_from_score_yaml(
        client=client,
        score_id="score-1",
    )

    assert classes == ["Yes", "No"]


def test_resolve_score_valid_classes_from_score_yaml_requires_champion():
    client = MagicMock()
    client.execute = MagicMock(
        return_value={"getScore": {"id": "score-1", "championVersionId": None}}
    )

    with pytest.raises(ValueError, match="No champion version configured"):
        resolve_score_valid_classes_from_score_yaml(client=client, score_id="score-1")


def test_resolve_score_valid_classes_from_score_yaml_fails_when_missing_classes():
    client = MagicMock()
    client.execute = MagicMock(
        side_effect=[
            {"getScore": {"id": "score-1", "championVersionId": "sv-1"}},
            {
                "getScoreVersion": {
                    "id": "sv-1",
                    "configuration": """
graph:
  - name: classifier_one
""",
                }
            },
        ]
    )

    with pytest.raises(ValueError, match="No final output classes found"):
        resolve_score_valid_classes_from_score_yaml(client=client, score_id="score-1")


def test_resolve_score_valid_classes_from_conditions_output_values():
    client = MagicMock()
    client.execute = MagicMock(
        side_effect=[
            {"getScore": {"id": "score-1", "championVersionId": "sv-1"}},
            {
                "getScoreVersion": {
                    "id": "sv-1",
                    "configuration": """
graph:
  - name: decision_node
    conditions:
      - if: "something"
        output:
          value: "Yes"
      - if: "other"
        output:
          value: "No"
""",
                }
            },
        ]
    )

    classes = resolve_score_valid_classes_from_score_yaml(client=client, score_id="score-1")
    assert classes == ["Yes", "No"]


def test_resolve_score_valid_classes_uses_final_node_only():
    client = MagicMock()
    client.execute = MagicMock(
        side_effect=[
            {"getScore": {"id": "score-1", "championVersionId": "sv-1"}},
            {
                "getScoreVersion": {
                    "id": "sv-1",
                    "configuration": """
graph:
  - name: reason_classifier
    valid_classes: ["Missing School Name", "Missing Program Name"]
  - name: final_classifier
    valid_classes: ["Yes", "No"]
""",
                }
            },
        ]
    )

    classes = resolve_score_valid_classes_from_score_yaml(client=client, score_id="score-1")
    assert classes == ["Yes", "No"]


def test_resolve_score_valid_classes_from_logical_classifier_code():
    client = MagicMock()
    client.execute = MagicMock(
        side_effect=[
            {"getScore": {"id": "score-1", "championVersionId": "sv-1"}},
            {
                "getScoreVersion": {
                    "id": "sv-1",
                    "configuration": """
graph:
  - name: reason_classifier
    class: Classifier
    valid_classes: ["Missing School Name", "Missing Program Name"]
  - name: final_determiner
    class: LogicalClassifier
    code: >
      def score(parameters: Score.Parameters, input: Score.Input) -> Score.Result:
          if input.metadata.get('compliance_reason') == "None":
              return Score.Result(parameters=parameters, value="Yes")
          return Score.Result(parameters=parameters, value="No")
""",
                }
            },
        ]
    )

    classes = resolve_score_valid_classes_from_score_yaml(client=client, score_id="score-1")
    assert classes == ["Yes", "No"]


def test_resolve_score_valid_classes_from_explicit_score_version():
    client = MagicMock()
    client.execute = MagicMock(
        return_value={
            "getScoreVersion": {
                "id": "sv-explicit",
                "configuration": """
classes:
  - name: "Yes"
  - name: "No"
""",
            }
        }
    )

    classes = resolve_score_valid_classes_from_score_yaml(
        client=client,
        score_id="score-1",
        score_version_id="sv-explicit",
    )

    assert classes == ["Yes", "No"]
    first_call_query = client.execute.call_args_list[0].args[0]
    assert "GetScoreChampionVersion" not in first_call_query


def test_select_balanced_feedback_items_round_robins_and_preserves_size():
    def item(item_id: str, label: str):
        return SimpleNamespace(
            id=item_id,
            finalAnswerValue=label,
            editedAt="2026-03-03T00:00:00Z",
            scorecardId="scorecard-1",
            scoreId="score-1",
            item=SimpleNamespace(id=f"i-{item_id}", text="x"),
        )

    all_items = [
        item("1", "Yes"),
        item("2", "Yes"),
        item("3", "Yes"),
        item("4", "No"),
        item("5", "Yes"),
    ]

    selected = _select_balanced_feedback_items(
        all_qualifying_items=all_items,
        class_list=["Yes", "No"],
        max_items=4,
    )

    assert len(selected) == 4
    assert _compute_label_distribution(selected) == {"No": 1, "Yes": 3}


def test_ordered_unique_feedback_ids_preserves_input_order():
    ordered = _ordered_unique_feedback_ids(
        [
            {"feedback_item_id": "fi-3"},
            {"feedback_item_id": "fi-1"},
            {"feedback_item_id": "fi-3"},
            {"feedback_item_id": "fi-2"},
        ]
    )
    assert ordered == ["fi-3", "fi-1", "fi-2"]


@patch("plexus.cli.dataset.curation._upload_dataset_parquet", return_value="datasets/account-1/dataset-1/dataset.parquet")
@patch("plexus.cli.dataset.curation._fetch_score_champion_version", return_value=None)
@patch("plexus.cli.dataset.curation._create_associated_dataset_datasource_version", return_value=("ds-1", "dsv-1"))
@patch("plexus.cli.dataset.curation.FeedbackItems")
@patch("plexus.cli.dataset.curation._select_balanced_feedback_items")
@patch(
    "plexus.cli.dataset.curation._resolve_score_final_classes_from_yaml_details",
    return_value={
        "classes": ["Yes", "No"],
        "source": "graph[-1].LogicalClassifier.code",
        "score_version_id": "sv-explicit",
        "optimizer_shadow_invalid_feedback_item_ids": ["fb-2", "fb-1"],
    },
)
@patch("plexus.cli.dataset.curation.collect_qualifying_feedback_items")
@patch("plexus.cli.dataset.curation._fetch_scorecard_account_id", return_value="account-1")
@patch("plexus.cli.dataset.curation._fetch_score_name", return_value="Test Score")
def test_build_associated_dataset_from_feedback_window_persists_stats(
    _mock_score_name,
    _mock_account,
    mock_collect,
    _mock_class_resolver,
    mock_select_balanced,
    mock_feedback_items_class,
    mock_create_datasource_version,
    _mock_champion,
    _mock_upload,
):
    fi_yes = SimpleNamespace(
        id="fi-1",
        accountId="account-1",
        scorecardId="scorecard-1",
        scoreId="score-1",
        finalAnswerValue="Yes",
        editedAt="2026-03-03T00:00:00Z",
        item=SimpleNamespace(id="item-1", text="t1"),
    )
    fi_no = SimpleNamespace(
        id="fi-2",
        accountId="account-1",
        scorecardId="scorecard-1",
        scoreId="score-1",
        finalAnswerValue="No",
        editedAt="2026-03-02T00:00:00Z",
        item=SimpleNamespace(id="item-2", text="t2"),
    )
    mock_collect.return_value = [fi_yes, fi_no]
    mock_select_balanced.return_value = [fi_yes, fi_no]

    built_df = SimpleNamespace(empty=False)
    # Replace with DataFrame-like object used for len() and optional sort branch
    import pandas as pd
    built_df = pd.DataFrame(
        {
            "feedback_item_id": ["fi-1", "fi-2"],
            "text": ["t1", "t2"],
            "metadata": ["{}", "{}"],
            "IDs": ["[]", "[]"],
            "Test Score": ["Yes", "No"],
        }
    )
    row_builder = MagicMock()
    row_builder._create_dataset_rows.return_value = built_df
    mock_feedback_items_class.return_value = row_builder

    mock_client = MagicMock()
    mock_client.execute = MagicMock(
        side_effect=[
            {"createDataSet": {"id": "dataset-1"}},
            {"updateDataSet": {"id": "dataset-1", "file": "datasets/account-1/dataset-1/dataset.parquet"}},
            {"getDataSet": {"id": "dataset-1", "file": "datasets/account-1/dataset-1/dataset.parquet", "attachedFiles": []}},
        ]
    )

    result = build_associated_dataset_from_feedback_window(
        client=mock_client,
        scorecard_id="scorecard-1",
        score_id="score-1",
        max_items=2,
        days=30,
        balance=True,
        class_source_score_version_id="sv-explicit",
    )

    assert result["dataset_id"] == "dataset-1"
    _mock_class_resolver.assert_called_once_with(
        client=mock_client,
        score_id="score-1",
        score_version_id="sv-explicit",
    )
    assert mock_collect.call_args.kwargs["excluded_feedback_item_ids"] == ["fb-2", "fb-1"]
    stats = mock_create_datasource_version.call_args.kwargs["dataset_stats"]
    assert stats["row_count"] == 2
    assert stats["label_distribution"] == {"No": 1, "Yes": 1}
    assert stats["balance_applied"] is True
    assert stats["class_resolution_source"] == "graph[-1].LogicalClassifier.code"
    assert stats["observed_label_set"] == ["No", "Yes"]
    assert stats["class_label_overlap"] == ["No", "Yes"]
    assert stats["optimizer_shadow_invalid_feedback_item_ids"] == ["fb-2", "fb-1"]
    assert stats["score_version_id_used"] == "sv-explicit"
    assert result["optimizer_shadow_invalid_feedback_item_ids"] == ["fb-2", "fb-1"]
    assert result["score_version_id_used"] == "sv-explicit"
    assert result["feedback_target_hash"]


@patch("plexus.cli.dataset.curation._fetch_score_champion_version", return_value=None)
@patch("plexus.cli.dataset.curation._create_associated_dataset_datasource_version", return_value=("ds-1", "dsv-1"))
@patch("plexus.cli.dataset.curation.FeedbackItems")
@patch(
    "plexus.cli.dataset.curation._resolve_score_final_classes_from_yaml_details",
    return_value={
        "classes": ["Missing School Name", "Missing Program Name"],
        "source": "graph[-1].valid_classes",
        "score_version_id": "sv-explicit",
    },
)
@patch("plexus.cli.dataset.curation.collect_qualifying_feedback_items")
@patch("plexus.cli.dataset.curation._fetch_scorecard_account_id", return_value="account-1")
@patch("plexus.cli.dataset.curation._fetch_score_name", return_value="Test Score")
def test_build_associated_dataset_from_feedback_window_fails_on_low_overlap(
    _mock_score_name,
    _mock_account,
    mock_collect,
    _mock_class_resolver_details,
    _mock_feedback_items_class,
    _mock_create_datasource_version,
    _mock_champion,
):
    fi_yes = SimpleNamespace(
        id="fi-1",
        accountId="account-1",
        scorecardId="scorecard-1",
        scoreId="score-1",
        finalAnswerValue="Yes",
        editedAt="2026-03-03T00:00:00Z",
        item=SimpleNamespace(id="item-1", text="t1"),
    )
    fi_no = SimpleNamespace(
        id="fi-2",
        accountId="account-1",
        scorecardId="scorecard-1",
        scoreId="score-1",
        finalAnswerValue="No",
        editedAt="2026-03-02T00:00:00Z",
        item=SimpleNamespace(id="item-2", text="t2"),
    )
    mock_collect.return_value = [fi_yes, fi_no]

    with pytest.raises(ValueError, match="Insufficient class/label overlap for balancing"):
        build_associated_dataset_from_feedback_window(
            client=MagicMock(),
            scorecard_id="scorecard-1",
            score_id="score-1",
            max_items=2,
            days=30,
            balance=True,
            class_source_score_version_id="sv-explicit",
        )


@patch("plexus.cli.dataset.curation._upload_dataset_parquet", return_value="datasets/account-1/dataset-1/dataset.parquet")
@patch("plexus.cli.dataset.curation._fetch_score_champion_version", return_value=None)
@patch("plexus.cli.dataset.curation._create_associated_dataset_datasource_version", return_value=("ds-1", "dsv-1"))
@patch("plexus.cli.dataset.curation.FeedbackItems")
@patch("plexus.cli.dataset.curation._fetch_feedback_item_with_item")
@patch(
    "plexus.cli.dataset.curation._resolve_score_final_classes_from_yaml_details",
    return_value={
        "classes": ["Yes", "No"],
        "source": "graph[-1].LogicalClassifier.code",
        "score_version_id": "sv-explicit",
    },
)
@patch("plexus.cli.dataset.curation._fetch_scorecard_account_id", return_value="account-1")
@patch("plexus.cli.dataset.curation._fetch_score_name", return_value="Test Score")
def test_build_associated_dataset_from_vetted_feedback_items_persists_diagnostics(
    _mock_score_name,
    _mock_account,
    _mock_class_resolver,
    mock_fetch_feedback_item,
    mock_feedback_items_class,
    mock_create_datasource_version,
    _mock_champion,
    _mock_upload,
):
    def _item(fid: str, label: str):
        return SimpleNamespace(
            id=fid,
            accountId="account-1",
            scorecardId="scorecard-1",
            scoreId="score-1",
            finalAnswerValue=label,
            editedAt="2026-03-03T00:00:00Z",
            item=SimpleNamespace(id=f"item-{fid}", text="hello"),
        )

    lookup = {
        "fi-2": _item("fi-2", "No"),
        "fi-1": _item("fi-1", "Yes"),
        "fi-3": _item("fi-3", "Yes"),
    }
    mock_fetch_feedback_item.side_effect = lambda _client, fid: lookup.get(fid)

    import pandas as pd
    built_df = pd.DataFrame(
        {
            "feedback_item_id": ["fi-1", "fi-2", "fi-3"],
            "text": ["a", "b", "c"],
            "metadata": ["{}", "{}", "{}"],
            "IDs": ["[]", "[]", "[]"],
            "Test Score": ["Yes", "No", "Yes"],
        }
    )
    row_builder = MagicMock()
    row_builder._create_dataset_rows.return_value = built_df
    mock_feedback_items_class.return_value = row_builder

    mock_client = MagicMock()
    mock_client.execute = MagicMock(
        side_effect=[
            {"createDataSet": {"id": "dataset-1"}},
            {"updateDataSet": {"id": "dataset-1", "file": "datasets/account-1/dataset-1/dataset.parquet"}},
            {"getDataSet": {"id": "dataset-1", "file": "datasets/account-1/dataset-1/dataset.parquet", "attachedFiles": []}},
        ]
    )

    result = build_associated_dataset_from_vetted_feedback_items(
        client=mock_client,
        scorecard_id="scorecard-1",
        score_id="score-1",
        vetted_feedback_items=[
            {"feedback_item_id": "fi-2"},
            {"feedback_item_id": "fi-1"},
            {"feedback_item_id": "fi-3"},
        ],
        max_items=2,
        class_source_score_version_id="sv-explicit",
        report_id="report-1",
        report_block_id="block-1",
    )

    assert result["dataset_id"] == "dataset-1"
    assert result["report_id"] == "report-1"
    assert result["report_block_id"] == "block-1"
    stats = mock_create_datasource_version.call_args.kwargs["dataset_stats"]
    assert stats["class_resolution_source"] == "graph[-1].LogicalClassifier.code"
    assert stats["resolved_final_classes"] == ["Yes", "No"]
    assert stats["vetted_eligible_count"] == 3


@patch("plexus.cli.dataset.curation.build_associated_dataset_from_vetted_feedback_items")
@patch("plexus.cli.dataset.curation._run_aligned_vetting_report")
@patch("plexus.cli.dataset.curation._ensure_auto_vetted_report_configuration")
@patch("plexus.cli.dataset.curation._fetch_scorecard_account_id", return_value="account-1")
def test_build_associated_dataset_from_vetted_report_orchestrates_flow(
    _mock_account,
    mock_ensure_config,
    mock_run_report,
    mock_build_dataset,
):
    mock_ensure_config.return_value = SimpleNamespace(id="config-1")
    mock_run_report.return_value = {
        "report_id": "report-1",
        "report_task_id": "task-1",
        "report_block_id": "block-1",
        "eligible_items": [{"feedback_item_id": "fi-1"}],
        "eligibility_rule": "unanimous non-contradiction",
    }
    mock_build_dataset.return_value = {"dataset_id": "dataset-1"}

    result = build_associated_dataset_from_vetted_report(
        client=MagicMock(),
        scorecard_id="scorecard-1",
        score_id="score-1",
        max_items=10,
        days=180,
        class_source_score_version_id="sv-1",
    )

    assert result["dataset_id"] == "dataset-1"
    assert result["report_configuration_id"] == "config-1"
    assert result["report_task_id"] == "task-1"
    assert result["vetted_pool_limit"] == 10
    mock_ensure_config.assert_called_once_with(
        client=ANY,
        account_id="account-1",
        scorecard_id="scorecard-1",
        score_id="score-1",
        days=180,
        vetting_pool_limit=10,
    )
    mock_build_dataset.assert_called_once()


@patch("plexus.cli.dataset.curation.build_associated_dataset_from_vetted_feedback_items")
@patch("plexus.cli.dataset.curation._run_aligned_vetting_report")
@patch("plexus.cli.dataset.curation._ensure_auto_vetted_report_configuration")
@patch("plexus.cli.dataset.curation._fetch_scorecard_account_id", return_value="account-1")
def test_build_associated_dataset_from_vetted_report_expands_pool_until_target_or_cap(
    _mock_account,
    mock_ensure_config,
    mock_run_report,
    mock_build_dataset,
):
    mock_ensure_config.return_value = SimpleNamespace(id="config-1")
    mock_run_report.side_effect = [
        {
            "report_id": "report-1",
            "report_task_id": "task-1",
            "report_block_id": "block-1",
            "eligible_items": [{"feedback_item_id": "fi-1"}],
            "eligible_count": 1,
            "total_items_analyzed": 10,
            "eligibility_rule": "unanimous non-contradiction",
        },
        {
            "report_id": "report-2",
            "report_task_id": "task-2",
            "report_block_id": "block-2",
            "eligible_items": [{"feedback_item_id": f"fi-{i}"} for i in range(10)],
            "eligible_count": 10,
            "total_items_analyzed": 20,
            "eligibility_rule": "unanimous non-contradiction",
        },
    ]
    mock_build_dataset.return_value = {"dataset_id": "dataset-1"}

    result = build_associated_dataset_from_vetted_report(
        client=MagicMock(),
        scorecard_id="scorecard-1",
        score_id="score-1",
        max_items=10,
        days=180,
        class_source_score_version_id="sv-1",
    )

    assert result["dataset_id"] == "dataset-1"
    assert result["vetted_pool_limit"] == 20
    assert result["vetted_pool_attempts"] == 2
    assert result["vetted_pool_attempted_limits"] == [10, 20]
    assert mock_ensure_config.call_count == 2
    assert mock_build_dataset.call_args.kwargs["vetted_feedback_items"] == [
        {"feedback_item_id": f"fi-{i}"} for i in range(10)
    ]


@patch("plexus.cli.dataset.curation.build_associated_dataset_from_vetted_feedback_items")
@patch("plexus.cli.dataset.curation._run_aligned_vetting_report")
@patch("plexus.cli.dataset.curation._ensure_auto_vetted_report_configuration")
@patch("plexus.cli.dataset.curation._fetch_scorecard_account_id", return_value="account-1")
def test_build_associated_dataset_from_vetted_report_stops_when_window_exhausted(
    _mock_account,
    mock_ensure_config,
    mock_run_report,
    mock_build_dataset,
):
    mock_ensure_config.return_value = SimpleNamespace(id="config-1")
    mock_run_report.return_value = {
        "report_id": "report-1",
        "report_task_id": "task-1",
        "report_block_id": "block-1",
        "eligible_items": [{"feedback_item_id": "fi-1"}, {"feedback_item_id": "fi-2"}],
        "eligible_count": 2,
        "total_items_analyzed": 7,
        "eligibility_rule": "unanimous non-contradiction",
    }
    mock_build_dataset.return_value = {"dataset_id": "dataset-1"}

    result = build_associated_dataset_from_vetted_report(
        client=MagicMock(),
        scorecard_id="scorecard-1",
        score_id="score-1",
        max_items=10,
        days=180,
    )

    assert result["dataset_id"] == "dataset-1"
    assert result["vetted_pool_limit"] == 10
    assert result["vetted_pool_attempts"] == 1
    assert result["vetted_pool_attempted_limits"] == [10]
    mock_ensure_config.assert_called_once()
