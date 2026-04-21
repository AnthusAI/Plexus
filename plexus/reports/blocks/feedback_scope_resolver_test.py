from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from plexus.reports.blocks.feedback_scope_resolver import (
    list_scores_for_scorecard,
    resolve_score_for_scorecard,
    resolve_scorecard,
)


@pytest.mark.asyncio
async def test_resolve_scorecard_accepts_hyphenated_name():
    client = MagicMock()

    with (
        patch("plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_key", return_value=None),
        patch(
            "plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_name",
            return_value=SimpleNamespace(id="sc-1", name="Prime - EDU 3rd Party"),
        ),
        patch("plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_external_id", return_value=None),
    ):
        resolved = await resolve_scorecard(client, "Prime - EDU 3rd Party")

    assert resolved.id == "sc-1"
    assert resolved.name == "Prime - EDU 3rd Party"


@pytest.mark.asyncio
async def test_resolve_score_for_scorecard_uuid_success():
    client = MagicMock()
    client.execute.return_value = {
        "getScorecard": {
            "sections": {
                "items": [
                    {
                        "id": "section-1",
                        "scores": {
                            "items": [
                                {"id": "score-1", "name": "Agent Misrepresentation", "key": "agent_misrep", "externalId": "45813", "order": 1},
                            ]
                        },
                    }
                ]
            }
        }
    }

    with patch(
        "plexus.reports.blocks.feedback_scope_resolver.Score.get_by_id",
        return_value=SimpleNamespace(id="score-1", name="Agent Misrepresentation"),
    ):
        resolved = await resolve_score_for_scorecard(
            client,
            "sc-1",
            "123e4567-e89b-12d3-a456-426614174000",
        )

    assert resolved.id == "score-1"
    assert resolved.name == "Agent Misrepresentation"


@pytest.mark.asyncio
async def test_resolve_score_for_scorecard_uuid_rejects_other_scorecard():
    client = MagicMock()
    client.execute.return_value = {
        "getScorecard": {
            "sections": {
                "items": [
                    {
                        "id": "section-1",
                        "scores": {"items": [{"id": "score-in-scope", "name": "In Scope", "key": "in_scope", "externalId": "111", "order": 1}]},
                    }
                ]
            }
        }
    }

    with patch(
        "plexus.reports.blocks.feedback_scope_resolver.Score.get_by_id",
        return_value=SimpleNamespace(id="score-out-of-scope", name="Other"),
    ):
        with pytest.raises(ValueError, match="does not belong to scorecard"):
            await resolve_score_for_scorecard(
                client,
                "sc-1",
                "123e4567-e89b-12d3-a456-426614174000",
            )


@pytest.mark.asyncio
async def test_resolve_score_for_scorecard_scoped_name_key_external_id_only():
    client = MagicMock()
    client.execute.return_value = {
        "getScorecard": {
            "sections": {
                "items": [
                    {
                        "id": "section-1",
                        "scores": {
                            "items": [
                                {"id": "score-1", "name": "Agent Misrepresentation", "key": "agent_misrep", "externalId": "45813", "order": 1},
                            ]
                        },
                    }
                ]
            }
        }
    }

    by_name = await resolve_score_for_scorecard(client, "sc-1", "Agent Misrepresentation")
    by_key = await resolve_score_for_scorecard(client, "sc-1", "agent_misrep")
    by_external = await resolve_score_for_scorecard(client, "sc-1", "45813")

    assert by_name.id == "score-1"
    assert by_key.id == "score-1"
    assert by_external.id == "score-1"


@pytest.mark.asyncio
async def test_list_scores_for_scorecard_keeps_section_and_order_sort():
    client = MagicMock()
    client.execute.return_value = {
        "getScorecard": {
            "sections": {
                "items": [
                    {
                        "id": "section-1",
                        "scores": {"items": [{"id": "score-2", "name": "Second", "key": "second", "externalId": "2", "order": 2}]},
                    },
                    {
                        "id": "section-2",
                        "scores": {"items": [{"id": "score-1", "name": "First", "key": "first", "externalId": "1", "order": 1}]},
                    },
                ]
            }
        }
    }

    scores = await list_scores_for_scorecard(client, "sc-1")

    assert [score.id for score in scores] == ["score-2", "score-1"]
