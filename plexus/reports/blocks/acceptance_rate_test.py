from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import time as pytime

import pytest

from plexus.reports.blocks.acceptance_rate import AcceptanceRate


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


@pytest.mark.asyncio
async def test_acceptance_rate_computes_item_and_score_result_acceptance(mock_api_client):
    block = AcceptanceRate(
        config={
            "scorecard": "sc-1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "include_item_acceptance_rate": True,
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    score_results = [
        {
            "id": "sr-1",
            "itemId": "item-a",
            "scoreId": "score-1",
            "value": "yes",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T10:00:00+00:00",
            "score": {"id": "score-1", "name": "Score 1"},
        },
        {
            "id": "sr-2",
            "itemId": "item-a",
            "scoreId": "score-2",
            "value": "no",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T10:01:00+00:00",
            "score": {"id": "score-2", "name": "Score 2"},
        },
        {
            "id": "sr-3",
            "itemId": "item-b",
            "scoreId": "score-1",
            "value": "yes",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T10:02:00+00:00",
            "score": {"id": "score-1", "name": "Score 1"},
        },
    ]
    feedback_items = [
        {
            "id": "fi-1",
            "itemId": "item-a",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "no",
            "isInvalid": False,
            "editedAt": "2026-04-11T10:00:00+00:00",
        },
        {
            "id": "fi-1b",
            "itemId": "item-a",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "yes",
            "isInvalid": False,
            "editedAt": "2026-04-11T09:00:00+00:00",
        },
        {
            "id": "fi-2",
            "itemId": "item-a",
            "scoreId": "score-2",
            "initialAnswerValue": "no",
            "finalAnswerValue": "no",
            "isInvalid": False,
            "editedAt": "2026-04-11T10:01:00+00:00",
        },
        {
            "id": "fi-3",
            "itemId": "item-b",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "no",
            "isInvalid": True,
            "editedAt": "2026-04-11T10:02:00+00:00",
        },
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_fetch_score_results_window", new=AsyncMock(return_value=score_results)),
        patch.object(block, "_fetch_feedback_items_window", new=AsyncMock(return_value=feedback_items)),
    ):
        output, _ = await block.generate()

    summary = output["summary"]
    assert summary["total_items"] == 2
    assert summary["accepted_items"] == 1
    assert summary["corrected_items"] == 1
    assert summary["item_acceptance_rate"] == 0.5
    assert summary["total_score_results"] == 3
    assert summary["accepted_score_results"] == 2
    assert summary["corrected_score_results"] == 1
    assert summary["score_result_acceptance_rate"] == pytest.approx(2 / 3)
    assert summary["feedback_items_total"] == 4
    assert summary["feedback_items_valid"] == 3
    assert summary["feedback_items_changed"] == 1
    assert summary["score_results_with_feedback"] == 3

    items = {item["item_id"]: item for item in output["items"]}
    assert items["item-a"]["item_accepted"] is False
    assert items["item-b"]["item_accepted"] is True
    assert items["item-a"]["feedback_items_total"] == 3
    assert items["item-a"]["feedback_items_valid"] == 3


@pytest.mark.asyncio
async def test_acceptance_rate_default_is_score_result_only(mock_api_client):
    block = AcceptanceRate(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    score_results = [
        {
            "id": "sr-1",
            "itemId": "item-a",
            "scoreId": "score-1",
            "value": "yes",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T10:00:00+00:00",
            "score": {"id": "score-1", "name": "Score 1"},
        },
    ]
    feedback_items = []

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_fetch_score_results_window", new=AsyncMock(return_value=score_results)),
        patch.object(block, "_fetch_feedback_items_window", new=AsyncMock(return_value=feedback_items)),
    ):
        output, _ = await block.generate()

    assert output["include_item_acceptance_rate"] is False

    summary = output["summary"]
    assert "item_acceptance_rate" not in summary
    assert "accepted_items" not in summary
    assert summary["total_score_results"] == 1
    assert summary["accepted_score_results"] == 1
    assert summary["corrected_score_results"] == 0
    assert summary["score_result_acceptance_rate"] == 1.0
    assert summary["feedback_items_total"] == 0
    assert summary["feedback_items_valid"] == 0
    assert summary["feedback_items_changed"] == 0
    assert summary["score_results_with_feedback"] == 0

    assert output["items"][0]["item_id"] == "item-a"
    assert "item_accepted" not in output["items"][0]
    assert output["max_items"] == 0
    assert output["items_total"] == 1
    assert output["items_returned"] == 1
    assert output["items_truncated"] is False


@pytest.mark.asyncio
async def test_acceptance_rate_zero_max_items_means_no_cap(mock_api_client):
    block = AcceptanceRate(
        config={
            "scorecard": "sc-1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "max_items": 0,
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    score_results = [
        {
            "id": "sr-1",
            "itemId": "item-a",
            "scoreId": "score-1",
            "value": "yes",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T10:00:00+00:00",
            "score": {"id": "score-1", "name": "Score 1"},
            "item": {
                "id": "item-a",
                "externalId": "item-ext-a",
                "createdAt": "2026-04-10T09:59:00+00:00",
                "updatedAt": "2026-04-10T10:01:00+00:00",
                "itemIdentifiers": {"items": [{"name": "Call ID", "value": "A-1"}]},
            },
        },
        {
            "id": "sr-2",
            "itemId": "item-b",
            "scoreId": "score-1",
            "value": "no",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T11:00:00+00:00",
            "score": {"id": "score-1", "name": "Score 1"},
            "item": {
                "id": "item-b",
                "externalId": "item-ext-b",
                "createdAt": "2026-04-10T10:59:00+00:00",
                "updatedAt": "2026-04-10T11:01:00+00:00",
                "identifiers": {"Session ID": "B-2"},
            },
        },
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_fetch_score_results_window", new=AsyncMock(return_value=score_results)),
        patch.object(block, "_fetch_feedback_items_window", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert output["items_total"] == 2
    assert output["items_returned"] == 2
    assert output["items_truncated"] is False
    first = {item["item_id"]: item for item in output["items"]}
    assert first["item-a"]["item_external_id"] == "item-ext-a"
    assert first["item-a"]["item_created_at"] == "2026-04-10T09:59:00+00:00"
    assert first["item-a"]["item_identifiers"] == [{"name": "Call ID", "value": "A-1"}]
    assert first["item-b"]["item_identifiers"] == {"Session ID": "B-2"}


@pytest.mark.asyncio
async def test_feedback_items_window_fans_out_by_score_ids_and_dedupes(mock_api_client):
    block = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 1},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    seen_score_ids = []

    def _execute(query, variables):
        score_id = variables["compositeCondition"]["between"][0]["scoreId"]
        seen_score_ids.append(score_id)
        if score_id == "score-1":
            return {
                "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                    "items": [
                        {
                            "id": "fi-dup",
                            "itemId": "item-a",
                            "scoreId": "score-1",
                            "editedAt": "2026-04-01T10:00:00+00:00",
                            "isInvalid": False,
                        }
                    ],
                    "nextToken": None,
                }
            }
        return {
            "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                "items": [
                    {
                        "id": "fi-dup",
                        "itemId": "item-a",
                        "scoreId": "score-2",
                        "editedAt": "2026-04-01T11:00:00+00:00",
                        "isInvalid": False,
                    },
                    {
                        "id": "fi-2",
                        "itemId": "item-b",
                        "scoreId": "score-2",
                        "editedAt": "2026-04-01T12:00:00+00:00",
                        "isInvalid": False,
                    },
                ],
                "nextToken": None,
            }
        }

    mock_api_client.execute.side_effect = _execute

    items = await block._fetch_feedback_items_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 4, 2, tzinfo=timezone.utc),
        score_id=None,
        score_ids=["score-1", "score-2", "score-1"],
    )

    assert sorted(seen_score_ids) == ["score-1", "score-2"]
    assert sorted(item["id"] for item in items) == ["fi-2", "fi-dup"]
    deduped = next(item for item in items if item["id"] == "fi-dup")
    assert deduped["scoreId"] == "score-2"


@pytest.mark.asyncio
async def test_feedback_items_window_uses_composite_index_when_score_is_present(mock_api_client):
    block = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 1},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    captured: dict = {}

    def _execute(query, variables):
        captured["query"] = query
        captured["variables"] = variables
        return {"listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {"items": [], "nextToken": None}}

    mock_api_client.execute.side_effect = _execute

    items = await block._fetch_feedback_items_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 4, 2, tzinfo=timezone.utc),
        score_id="score-1",
    )

    assert items == []
    assert "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt" in captured["query"]
    assert captured["variables"]["sortDirection"] == "DESC"


@pytest.mark.asyncio
async def test_feedback_rates_base_resolves_hyphenated_scorecard_name(mock_api_client):
    block = AcceptanceRate(
        config={"scorecard": "Prime - EDU 3rd Party", "days": 1},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    with (
        patch("plexus.reports.blocks.feedback_rates_base.Scorecard.get_by_key", return_value=None),
        patch(
            "plexus.reports.blocks.feedback_rates_base.Scorecard.get_by_name",
            return_value=SimpleNamespace(id="sc-1", name="Prime - EDU 3rd Party"),
        ),
        patch("plexus.reports.blocks.feedback_rates_base.Scorecard.get_by_external_id", return_value=None),
    ):
        resolved = await block._resolve_scorecard("Prime - EDU 3rd Party")

    assert resolved.id == "sc-1"
    assert resolved.name == "Prime - EDU 3rd Party"


@pytest.mark.asyncio
async def test_feedback_rates_base_resolves_score_by_name(mock_api_client):
    block = AcceptanceRate(
        config={"scorecard": "sc-1", "score": "Agent Branding", "days": 1},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    with (
        patch(
            "plexus.reports.blocks.feedback_rates_base.Score.get_by_name",
            return_value=SimpleNamespace(id="score-1", name="Agent Branding"),
        ),
        patch("plexus.reports.blocks.feedback_rates_base.Score.get_by_key", return_value=None),
        patch("plexus.reports.blocks.feedback_rates_base.Score.get_by_external_id", return_value=None),
    ):
        resolved = await block._resolve_score("Agent Branding", "sc-1")

    assert resolved.id == "score-1"
    assert resolved.name == "Agent Branding"


def test_feedback_rates_base_builds_contiguous_time_shards(mock_api_client):
    block = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 90, "fetch_shard_days": 30},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 4, 1, tzinfo=timezone.utc)

    shards = block._build_time_shards(start_date=start, end_date=end, shard_days=30)

    assert len(shards) == 3
    assert shards[0][0] == start
    assert shards[-1][1] == end
    for idx in range(1, len(shards)):
        assert shards[idx - 1][1] == shards[idx][0]

    shards_7 = block._build_time_shards(start_date=start, end_date=start + timedelta(days=7), shard_days=30)
    assert len(shards_7) == 1

    shards_365 = block._build_time_shards(start_date=start, end_date=start + timedelta(days=365), shard_days=30)
    assert len(shards_365) == 13


@pytest.mark.asyncio
async def test_feedback_rates_base_parallel_score_result_fetch_is_parity_safe(mock_api_client):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 4, 1, tzinfo=timezone.utc)

    def _build_execute():
        def _execute(_query, variables):
            shard_start = variables["startTime"]
            next_token = variables.get("nextToken")
            page_key = "p2" if next_token else "p1"
            suffix = shard_start[:10]
            item_id = f"item-{suffix}"
            rows = []
            if page_key == "p1":
                rows = [
                    {
                        "id": f"{suffix}-a",
                        "itemId": item_id,
                        "accountId": "acct-1",
                        "scorecardId": "sc-1",
                        "scoreId": "score-1",
                        "value": "Yes",
                        "type": "prediction",
                        "status": "COMPLETED",
                        "code": "200",
                        "evaluationId": None,
                        "updatedAt": f"{suffix}T10:00:00+00:00",
                    },
                    {
                        "id": "dup-id",
                        "itemId": "item-dup",
                        "accountId": "acct-1",
                        "scorecardId": "sc-1",
                        "scoreId": "score-1",
                        "value": "No",
                        "type": "prediction",
                        "status": "COMPLETED",
                        "code": "200",
                        "evaluationId": None,
                        "updatedAt": f"{suffix}T11:00:00+00:00",
                    },
                    {
                        "id": f"{suffix}-bad-acct",
                        "itemId": item_id,
                        "accountId": "wrong-account",
                        "scorecardId": "sc-1",
                        "scoreId": "score-1",
                        "value": "No",
                        "type": "prediction",
                        "status": "COMPLETED",
                        "code": "200",
                        "evaluationId": None,
                        "updatedAt": f"{suffix}T09:00:00+00:00",
                    },
                ]
            else:
                rows = [
                    {
                        "id": f"{suffix}-b",
                        "itemId": item_id,
                        "accountId": "acct-1",
                        "scorecardId": "sc-1",
                        "scoreId": "score-1",
                        "value": "No",
                        "type": "prediction",
                        "status": "COMPLETED",
                        "code": "200",
                        "evaluationId": None,
                        "updatedAt": f"{suffix}T12:00:00+00:00",
                    },
                    {
                        "id": f"{suffix}-bad-scorecard",
                        "itemId": item_id,
                        "accountId": "acct-1",
                        "scorecardId": "wrong-scorecard",
                        "scoreId": "score-1",
                        "value": "No",
                        "type": "prediction",
                        "status": "COMPLETED",
                        "code": "200",
                        "evaluationId": None,
                        "updatedAt": f"{suffix}T08:00:00+00:00",
                    },
                ]
            return {
                "listScoreResultByScorecardIdAndUpdatedAt": {
                    "items": rows,
                    "nextToken": None if next_token else "p2",
                }
            }

        return _execute

    client_seq = MagicMock()
    client_seq.execute.side_effect = _build_execute()
    block_seq = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 90, "fetch_shard_days": 30, "fetch_shard_concurrency": 1},
        params={"account_id": "acct-1"},
        api_client=client_seq,
    )

    client_par = MagicMock()
    client_par.execute.side_effect = _build_execute()
    block_par = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 90, "fetch_shard_days": 30, "fetch_shard_concurrency": 4},
        params={"account_id": "acct-1"},
        api_client=client_par,
    )

    rows_seq = await block_seq._fetch_score_results_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=start,
        end_date=end,
        score_id="score-1",
    )
    rows_par = await block_par._fetch_score_results_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=start,
        end_date=end,
        score_id="score-1",
    )

    ids_seq = sorted(row["id"] for row in rows_seq)
    ids_par = sorted(row["id"] for row in rows_par)
    assert ids_seq == ids_par
    assert "dup-id" in ids_seq
    assert ids_seq.count("dup-id") == 1


@pytest.mark.asyncio
async def test_feedback_rates_base_parallel_fetch_is_faster_under_mock_latency(mock_api_client):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 7, tzinfo=timezone.utc)

    def _slow_execute(_query, variables):
        pytime.sleep(0.03)
        shard_start = variables["startTime"][:10]
        return {
            "listScoreResultByScorecardIdAndUpdatedAt": {
                "items": [
                    {
                        "id": f"{shard_start}-1",
                        "itemId": f"item-{shard_start}",
                        "accountId": "acct-1",
                        "scorecardId": "sc-1",
                        "scoreId": "score-1",
                        "value": "Yes",
                        "type": "prediction",
                        "status": "COMPLETED",
                        "code": "200",
                        "evaluationId": None,
                        "updatedAt": f"{shard_start}T10:00:00+00:00",
                    }
                ],
                "nextToken": None,
            }
        }

    client_seq = MagicMock()
    client_seq.execute.side_effect = _slow_execute
    block_seq = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 6, "fetch_shard_days": 1, "fetch_shard_concurrency": 1},
        params={"account_id": "acct-1"},
        api_client=client_seq,
    )

    client_par = MagicMock()
    client_par.execute.side_effect = _slow_execute
    block_par = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 6, "fetch_shard_days": 1, "fetch_shard_concurrency": 3},
        params={"account_id": "acct-1"},
        api_client=client_par,
    )

    seq_started = pytime.perf_counter()
    await block_seq._fetch_score_results_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=start,
        end_date=end,
        score_id="score-1",
    )
    seq_elapsed = pytime.perf_counter() - seq_started

    par_started = pytime.perf_counter()
    await block_par._fetch_score_results_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=start,
        end_date=end,
        score_id="score-1",
    )
    par_elapsed = pytime.perf_counter() - par_started

    assert par_elapsed < seq_elapsed
