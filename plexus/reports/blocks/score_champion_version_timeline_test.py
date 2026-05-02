from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.reports.blocks.score_champion_version_timeline import ScoreChampionVersionTimeline


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


@pytest.fixture(autouse=True)
def no_optimizer_procedures_by_default(monkeypatch):
    monkeypatch.setattr(
        ScoreChampionVersionTimeline,
        "_fetch_optimizer_procedures_for_score",
        AsyncMock(return_value=[]),
    )


def _version(
    version_id,
    *,
    score_id="score-1",
    entered_at=None,
    previous_id=None,
    configuration=None,
    guidelines=None,
    note=None,
):
    history = []
    if entered_at:
        history.append(
            {
                "scoreId": score_id,
                "versionId": version_id,
                "enteredAt": entered_at,
                "exitedAt": None,
                "previousChampionVersionId": previous_id,
                "nextChampionVersionId": None,
                "transitionId": f"transition-{version_id}",
            }
        )
    return {
        "id": version_id,
        "scoreId": score_id,
        "configuration": configuration if configuration is not None else f"name: {version_id}\n",
        "guidelines": guidelines if guidelines is not None else f"# {version_id}\n",
        "note": note,
        "branch": None,
        "parentVersionId": previous_id,
        "metadata": {"championHistory": history},
        "createdAt": "2026-04-01T00:00:00+00:00",
        "updatedAt": "2026-04-01T00:00:00+00:00",
    }


def _evaluation(evaluation_id, *, evaluation_type, alignment=None, accuracy=None, created_at, cost=None, processed_items=10):
    metrics = {}
    if alignment is not None:
        metrics["alignment"] = alignment
    if accuracy is not None:
        metrics["accuracy"] = accuracy
    return {
        "id": evaluation_id,
        "type": evaluation_type,
        "status": "COMPLETED",
        "createdAt": created_at,
        "updatedAt": created_at,
        "metrics": metrics,
        "accuracy": accuracy,
        "cost": cost,
        "processedItems": processed_items,
        "totalItems": 10,
        "scoreVersionId": "v1",
    }


@pytest.mark.asyncio
async def test_accepts_days_window(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={"scorecard": "sc-1", "days": 30},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_score_versions", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert output["report_type"] == "score_champion_version_timeline"
    assert output["date_range"]["start"]
    assert output["date_range"]["end"]
    assert output["scores"] == []


@pytest.mark.asyncio
async def test_accepts_explicit_start_and_end_window(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-15"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert output["date_range"]["start"].startswith("2026-04-01T00:00:00")
    assert output["date_range"]["end"].startswith("2026-04-15T23:59:59")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config,error",
    [
        ({"scorecard": "sc-1", "start_date": "2026-04-01"}, "Both 'start_date' and 'end_date'"),
        (
            {"scorecard": "sc-1", "days": 30, "start_date": "2026-04-01", "end_date": "2026-04-15"},
            "Use either 'days' or 'start_date'+'end_date'",
        ),
    ],
)
async def test_rejects_invalid_window_configs(mock_api_client, config, error):
    block = ScoreChampionVersionTimeline(config=config, params={}, api_client=mock_api_client)

    output, _ = await block.generate()

    assert error in output["error"]


@pytest.mark.asyncio
async def test_all_score_mode_only_returns_scores_with_in_window_transitions(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scores = [
        {"score_id": "score-1", "score_name": "Score 1"},
        {"score_id": "score-2", "score_name": "Score 2"},
    ]
    versions_by_score = {
        "score-1": [
            _version("v0", configuration="name: old\n", guidelines="# Old\n"),
            _version(
                "v1",
                entered_at="2026-04-10T12:00:00+00:00",
                previous_id="v0",
                configuration="name: new\n",
                guidelines="# New\n",
            ),
        ],
        "score-2": [_version("v2", score_id="score-2")],
    }
    feedback_evals = [
        _evaluation("eval-latest", evaluation_type="feedback", alignment=0.70, accuracy=80, created_at="2026-04-12T00:00:00+00:00"),
        _evaluation("eval-best", evaluation_type="feedback", alignment=0.90, accuracy=82, created_at="2026-04-11T00:00:00+00:00"),
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=scores)),
        patch.object(
            block,
            "_fetch_score_versions",
            new=AsyncMock(side_effect=lambda score_id: versions_by_score[score_id]),
        ),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=feedback_evals)),
    ):
        output, _ = await block.generate()

    assert output["scope"] == "all_scores"
    assert len(output["scores"]) == 1
    score = output["scores"][0]
    assert score["score_id"] == "score-1"
    assert len(score["points"]) == 1
    assert score["points"][0]["version_id"] == "v1"
    assert score["points"][0]["feedback_evaluation_id"] == "eval-best"
    assert score["points"][0]["feedback_metrics"]["alignment"] == 0.90
    assert score["points"][0]["regression_metrics"] is None
    assert score["diff"]["left_version_id"] == "v0"
    assert score["diff"]["right_version_id"] == "v1"
    assert score["diff"]["configuration_left"] == "name: old\n"
    assert score["diff"]["configuration_right"] == "name: new\n"
    assert "-name: old" in score["diff"]["configuration_diff"]
    assert "+name: new" in score["diff"]["configuration_diff"]
    assert score["diff"]["guidelines_left"] == "# Old\n"
    assert score["diff"]["guidelines_right"] == "# New\n"
    assert "-# Old" in score["diff"]["guidelines_diff"]
    assert "+# New" in score["diff"]["guidelines_diff"]


@pytest.mark.asyncio
async def test_single_score_mode_filters_scope(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={
            "scorecard": "sc-1",
            "score": "Score 1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    score = SimpleNamespace(id="score-1", name="Score 1")
    versions = [
        _version("v0"),
        _version("v1", entered_at="2026-04-10T12:00:00+00:00", previous_id="v0"),
    ]
    evaluations = [
        _evaluation(
            "eval-feedback",
            evaluation_type="feedback",
            alignment=0.8,
            created_at="2026-04-11T00:00:00+00:00",
        )
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_score", new=AsyncMock(return_value=score)),
        patch.object(block, "_fetch_score_versions", new=AsyncMock(return_value=versions)),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=evaluations)),
    ):
        output, _ = await block.generate()

    assert output["scope"] == "single_score"
    assert [item["score_id"] for item in output["scores"]] == ["score-1"]


@pytest.mark.asyncio
async def test_unchanged_champion_is_omitted(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(
            block,
            "_fetch_score_versions",
            new=AsyncMock(return_value=[_version("v0", entered_at="2026-03-01T00:00:00+00:00")]),
        ),
    ):
        output, _ = await block.generate()

    assert output["scores"] == []
    assert output["summary"]["champion_change_count"] == 0
    assert "No champion version changes" in output["message"]


@pytest.mark.asyncio
async def test_initial_champion_without_previous_champion_is_omitted_by_default(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    versions = [
        _version("v1", entered_at="2026-04-10T12:00:00+00:00", previous_id=None),
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_score_versions", new=AsyncMock(return_value=versions)),
    ):
        output, _ = await block.generate()

    assert output["include_unchanged"] is False
    assert output["scores"] == []
    assert output["summary"]["champion_change_count"] == 0


@pytest.mark.asyncio
async def test_include_unchanged_omits_initial_champion_without_previous_champion_or_metrics(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={
            "scorecard": "sc-1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "include_unchanged": True,
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    versions = [
        _version("v1", entered_at="2026-04-10T12:00:00+00:00", previous_id=None),
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_score_versions", new=AsyncMock(return_value=versions)),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert output["include_unchanged"] is True
    assert output["scores"] == []
    assert output["summary"]["champion_change_count"] == 0
    assert output["summary"]["new_champion_count"] == 0
    assert output["summary"]["scores_with_champion_changes"] == 0
    assert output["summary"]["scores_with_new_champions"] == 0


@pytest.mark.asyncio
async def test_include_unchanged_keeps_initial_champion_with_evaluations(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={
            "scorecard": "sc-1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "include_unchanged": True,
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    versions = [
        _version("v1", entered_at="2026-04-10T12:00:00+00:00", previous_id=None),
    ]
    evaluations = [
        _evaluation(
            "eval-feedback",
            evaluation_type="feedback",
            alignment=0.8,
            accuracy=90,
            created_at="2026-04-11T00:00:00+00:00",
        )
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_score_versions", new=AsyncMock(return_value=versions)),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=evaluations)),
    ):
        output, _ = await block.generate()

    assert output["include_unchanged"] is True
    assert len(output["scores"]) == 1
    assert output["summary"]["champion_change_count"] == 0
    assert output["summary"]["new_champion_count"] == 1
    assert output["summary"]["scores_with_champion_changes"] == 0
    assert output["summary"]["scores_with_new_champions"] == 1
    assert output["scores"][0]["champion_change_count"] == 0
    assert output["scores"][0]["new_champion_count"] == 1
    assert output["scores"][0]["points"][0]["version_id"] == "v1"
    assert output["scores"][0]["points"][0]["previous_champion_version_id"] is None
    assert output["scores"][0]["points"][0]["feedback_evaluation_id"] == "eval-feedback"
    assert output["scores"][0]["diff"]["message"] == "Previous or latest champion version was not available for diff generation."


@pytest.mark.asyncio
async def test_diff_uses_previous_champion_before_first_transition_to_latest_transition(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    versions = [
        _version("v0", configuration="name: original\n"),
        _version("v1", entered_at="2026-04-10T12:00:00+00:00", previous_id="v0", configuration="name: middle\n"),
        _version("v2", entered_at="2026-04-20T12:00:00+00:00", previous_id="v1", configuration="name: latest\n"),
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_score_versions", new=AsyncMock(return_value=versions)),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    diff = output["scores"][0]["diff"]
    assert diff["left_version_id"] == "v0"
    assert diff["right_version_id"] == "v2"
    assert "-name: original" in diff["configuration_diff"]
    assert "+name: latest" in diff["configuration_diff"]


@pytest.mark.asyncio
async def test_date_range_normalizes_to_activity_with_one_day_padding(mock_api_client):
    block = ScoreChampionVersionTimeline(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    versions = [
        _version("v0"),
        _version("v1", entered_at="2026-04-20T12:00:00+00:00", previous_id="v0"),
    ]
    evaluations = [
        _evaluation(
            "eval-feedback",
            evaluation_type="feedback",
            alignment=0.8,
            created_at="2026-04-21T00:00:00+00:00",
        )
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_score_versions", new=AsyncMock(return_value=versions)),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=evaluations)),
    ):
        output, _ = await block.generate()

    assert output["requested_date_range"]["start"].startswith("2026-04-01T00:00:00")
    assert output["date_range"]["start"] == "2026-04-19T12:00:00+00:00"
    assert output["date_range"]["end"].startswith("2026-04-30T23:59:59")
    assert output["date_range"]["normalized_to_activity"] is True


@pytest.mark.asyncio
async def test_optimization_summary_counts_procedures_evaluations_score_results_and_costs(mock_api_client, monkeypatch):
    block = ScoreChampionVersionTimeline(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    versions = [
        _version("v0", configuration="name: old\n"),
        _version("v1", entered_at="2026-04-10T12:00:00+00:00", previous_id="v0", configuration="name: new\n"),
    ]
    evaluations = [
        _evaluation(
            "eval-1",
            evaluation_type="feedback",
            alignment=0.8,
            accuracy=90,
            cost=0.25,
            processed_items=12,
            created_at="2026-04-11T00:00:00+00:00",
        ),
        _evaluation(
            "eval-2",
            evaluation_type="accuracy",
            alignment=0.7,
            accuracy=80,
            cost=0.35,
            processed_items=18,
            created_at="2026-04-12T00:00:00+00:00",
        ),
    ]
    procedures = [
        {
            "id": "procedure-1",
            "status": "COMPLETED",
            "createdAt": "2026-04-11T00:00:00+00:00",
            "updatedAt": "2026-04-11T01:00:00+00:00",
            "metadata": {
                "procedure_type": "Optimizer Procedure",
                "dashboard_state": {
                    "costs": {
                        "totals": {
                            "overall": {"incurred": 1.5, "total": 1.5},
                            "inference": {"total": 0.4},
                            "evaluation": {"incurred": 1.1, "total": 1.1},
                        }
                    },
                    "sme_agenda_gated": "Review boundary cases with the SME.",
                    "end_of_run_report": {
                        "generated_at": "2026-04-11T02:00:00+00:00",
                        "sme_worksheet": {"text": "Confirm the transfer criteria."},
                        "run_summary": {"cycles": 2},
                    },
                },
            },
        }
    ]

    monkeypatch.setattr(
        block,
        "_fetch_optimizer_procedures_for_score",
        AsyncMock(return_value=procedures),
    )

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_score_versions", new=AsyncMock(return_value=versions)),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=evaluations)),
    ):
        output, _ = await block.generate()

    score_summary = output["scores"][0]["optimization_summary"]
    assert score_summary["procedure_count"] == 1
    assert score_summary["evaluation_count"] == 2
    assert score_summary["score_result_count"] == 30
    assert score_summary["optimization_cost"]["overall"] == 1.5
    assert score_summary["optimization_cost"]["inference"] == 0.4
    assert score_summary["optimization_cost"]["evaluation"] == 1.1
    assert score_summary["associated_evaluation_cost"] == 0.6
    assert output["summary"]["procedure_count"] == 1
    assert output["summary"]["evaluation_count"] == 2
    assert output["summary"]["score_result_count"] == 30
    assert output["summary"]["optimization_cost"]["overall"] == 1.5
    assert output["scores"][0]["sme"]["procedure_id"] == "procedure-1"
    assert output["scores"][0]["sme"]["available"] is True
    assert output["scores"][0]["sme"]["agenda"] == "Review boundary cases with the SME."
    assert output["scores"][0]["sme"]["worksheet"] == "Confirm the transfer criteria."
    assert output["scores"][0]["sme"]["run_summary"] == {"cycles": 2}
