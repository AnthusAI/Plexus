from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from plexus.cli.dataset.curation import (
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
