from unittest.mock import MagicMock

import pytest

from plexus.cli.evaluation.evaluations import (
    get_latest_associated_dataset_for_score,
    list_associated_datasets_for_score,
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
