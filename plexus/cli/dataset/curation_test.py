from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from plexus.cli.dataset.curation import (
    _compute_label_distribution,
    _select_balanced_feedback_items,
    build_associated_dataset_from_feedback_window,
    collect_qualifying_feedback_items,
    resolve_score_valid_classes_from_champion_yaml,
)


def _make_feedback_item_dict(
    item_id: str,
    *,
    edited_at: str,
    final_answer: str = "Yes",
    include_item: bool = True,
):
    payload = {
        "id": item_id,
        "accountId": "account-1",
        "scorecardId": "scorecard-1",
        "scoreId": "score-1",
        "itemId": f"item-{item_id}",
        "finalAnswerValue": final_answer,
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


def test_resolve_score_valid_classes_from_champion_yaml_extracts_deterministically():
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

    classes = resolve_score_valid_classes_from_champion_yaml(
        client=client,
        score_id="score-1",
    )

    assert classes == ["Yes", "No", "Maybe", "Escalate"]


def test_resolve_score_valid_classes_from_champion_yaml_requires_champion():
    client = MagicMock()
    client.execute = MagicMock(
        return_value={"getScore": {"id": "score-1", "championVersionId": None}}
    )

    with pytest.raises(ValueError, match="No champion version configured"):
        resolve_score_valid_classes_from_champion_yaml(client=client, score_id="score-1")


def test_resolve_score_valid_classes_from_champion_yaml_fails_when_missing_classes():
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

    with pytest.raises(ValueError, match="No valid classes found"):
        resolve_score_valid_classes_from_champion_yaml(client=client, score_id="score-1")


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


@patch("plexus.cli.dataset.curation._upload_dataset_parquet", return_value="datasets/account-1/dataset-1/dataset.parquet")
@patch("plexus.cli.dataset.curation._fetch_score_champion_version", return_value=None)
@patch("plexus.cli.dataset.curation._create_associated_dataset_datasource_version", return_value=("ds-1", "dsv-1"))
@patch("plexus.cli.dataset.curation.FeedbackItems")
@patch("plexus.cli.dataset.curation._select_balanced_feedback_items")
@patch("plexus.cli.dataset.curation.resolve_score_valid_classes_from_champion_yaml", return_value=["Yes", "No"])
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
        ]
    )

    result = build_associated_dataset_from_feedback_window(
        client=mock_client,
        scorecard_id="scorecard-1",
        score_id="score-1",
        max_items=2,
        days=30,
        balance=True,
    )

    assert result["dataset_id"] == "dataset-1"
    stats = mock_create_datasource_version.call_args.kwargs["dataset_stats"]
    assert stats["row_count"] == 2
    assert stats["label_distribution"] == {"No": 1, "Yes": 1}
    assert stats["balance_applied"] is True
