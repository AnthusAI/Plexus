import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.reports.blocks.scorecard_history import ScorecardHistory


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


def _version(
    version_id,
    *,
    score_id="score-1",
    created_at="2026-04-10T12:00:00+00:00",
    is_featured="true",
    parent_version_id=None,
    configuration=None,
    guidelines=None,
    note=None,
    champion_history=None,
):
    return {
        "id": version_id,
        "scoreId": score_id,
        "configuration": configuration if configuration is not None else f"name: {version_id}\n",
        "guidelines": guidelines if guidelines is not None else f"# {version_id}\n",
        "isFeatured": is_featured,
        "note": note if note is not None else f"{version_id} note",
        "branch": None,
        "parentVersionId": parent_version_id,
        "metadata": {"championHistory": champion_history or []},
        "createdAt": created_at,
        "updatedAt": created_at,
    }


def _evaluation(
    evaluation_id,
    *,
    evaluation_type,
    status="COMPLETED",
    created_at="2026-04-12T12:00:00+00:00",
    score_version_id="v1",
    accuracy=80,
    alignment=0.7,
    precision=0.6,
    recall=0.5,
    dataset_id=None,
):
    parameters = {"dataset_id": dataset_id} if dataset_id else {}
    return {
        "id": evaluation_id,
        "type": evaluation_type,
        "status": status,
        "createdAt": created_at,
        "updatedAt": created_at,
        "parameters": parameters,
        "scoreId": "score-1",
        "scoreVersionId": score_version_id,
        "accuracy": accuracy,
        "processedItems": 90,
        "totalItems": 100,
        "metrics": {
            "alignment": alignment,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
        },
        "cost": 1.25,
        "taskId": "task-1",
    }


def _summary_response(*score_ids):
    return json.dumps({
        "overall_summary": "Some included changes were promoted to champion.",
        "score_summaries": {
            score_id: f"Summary for {score_id}."
            for score_id in score_ids
        },
    })


def _block(config, api_client):
    return ScorecardHistory(config=config, params={"account_id": "acct-1"}, api_client=api_client)


@pytest.mark.asyncio
async def test_accepts_days_window(mock_api_client):
    block = _block({"scorecard": "sc-1", "days": 10}, mock_api_client)
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")

    with (
        patch.object(block, "_now_utc", return_value=datetime(2026, 5, 5, 12, tzinfo=timezone.utc)),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert output["report_type"] == "scorecard_history"
    assert output["date_range"]["start"] == "2026-04-25T12:00:00+00:00"
    assert output["date_range"]["end"] == "2026-05-05T12:00:00+00:00"
    assert output["scores"] == []


@pytest.mark.asyncio
async def test_accepts_explicit_start_and_end_window(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-15"},
        mock_api_client,
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
        ({"scorecard": "sc-1", "days": 0}, "'days' must be a positive integer"),
    ],
)
async def test_rejects_invalid_window_configs(mock_api_client, config, error):
    block = ScorecardHistory(config=config, params={}, api_client=mock_api_client)

    output, _ = await block.generate()

    assert error in output["error"]


@pytest.mark.asyncio
async def test_single_score_mode_filters_scope(mock_api_client):
    block = _block(
        {
            "scorecard": "sc-1",
            "score": "Score 1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
        },
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])) as resolve_scores,
        patch.object(
            block,
            "_fetch_versions_for_score",
            new=AsyncMock(return_value=[_version("v1", note="Tightened routing criteria.")]),
        ),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))),
    ):
        output, _ = await block.generate()

    resolve_scores.assert_awaited_once_with(scorecard_id="sc-1", score_identifier="Score 1")
    assert output["scope"] == "single_score"
    assert output["score_id"] == "score-1"
    assert [score["score_id"] for score in output["scores"]] == ["score-1"]


@pytest.mark.asyncio
async def test_filters_featured_versions_created_in_window_and_omits_unchanged_scores(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scopes = [
        SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None),
        SimpleNamespace(score_id="score-2", score_name="Score 2", champion_version_id=None),
    ]
    versions_by_score = {
        "score-1": [
            _version("v0", created_at="2026-03-25T12:00:00+00:00", is_featured="true"),
            _version("v1", created_at="2026-04-10T12:00:00+00:00", is_featured="false"),
            _version("v2", created_at="2026-04-12T12:00:00+00:00", is_featured="true"),
        ],
        "score-2": [
            _version("v3", score_id="score-2", created_at="2026-03-30T12:00:00+00:00", is_featured="true"),
            _version("v4", score_id="score-2", created_at="2026-04-12T12:00:00+00:00", is_featured="false"),
        ],
    }

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=scopes)),
        patch.object(
            block,
            "_fetch_versions_for_score",
            new=AsyncMock(side_effect=lambda score_id: versions_by_score[score_id]),
        ),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))),
    ):
        output, _ = await block.generate()

    assert [score["score_id"] for score in output["scores"]] == ["score-1"]
    assert [version["version_id"] for version in output["scores"][0]["versions"]] == ["v2"]
    assert output["summary"]["scores_changed_count"] == 1
    assert output["summary"]["featured_version_count"] == 1


@pytest.mark.asyncio
async def test_builds_parent_diff_payloads(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)
    parent = _version(
        "v0",
        created_at="2026-03-25T12:00:00+00:00",
        configuration="name: old\n",
        guidelines="# Old\n",
    )
    featured = _version(
        "v1",
        parent_version_id="v0",
        configuration="name: new\n",
        guidelines="# New\n",
        note="Changed the classification threshold.",
    )

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=[parent, featured])),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))),
    ):
        output, _ = await block.generate()

    version = output["scores"][0]["versions"][0]
    assert version["parent_version_id"] == "v0"
    assert version["diffs"]["code"]["original"] == "name: old\n"
    assert version["diffs"]["code"]["modified"] == "name: new\n"
    assert "-name: old" in version["diffs"]["code"]["unified_diff"]
    assert "+name: new" in version["diffs"]["code"]["unified_diff"]
    assert version["diffs"]["guidelines"]["original"] == "# Old\n"
    assert version["diffs"]["guidelines"]["modified"] == "# New\n"
    assert version["diffs"]["code"]["has_changes"] is True
    window_diff = output["scores"][0]["window_diff"]
    assert window_diff["baseline_version_id"] == "v0"
    assert window_diff["latest_version_id"] == "v1"
    assert window_diff["code"]["original"] == "name: old\n"
    assert window_diff["code"]["modified"] == "name: new\n"
    assert "-name: old" in window_diff["code"]["unified_diff"]
    assert "+name: new" in window_diff["code"]["unified_diff"]


@pytest.mark.asyncio
async def test_fetches_missing_parent_version_for_diff(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)
    featured = _version("v1", parent_version_id="v0", configuration="name: new\n")
    parent = _version("v0", configuration="name: old\n")

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=[featured])),
        patch.object(block, "_fetch_score_version_by_id", new=AsyncMock(return_value=parent)) as fetch_parent,
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))),
    ):
        output, _ = await block.generate()

    fetch_parent.assert_awaited_once_with("v0")
    assert output["scores"][0]["versions"][0]["diffs"]["code"]["original"] == "name: old\n"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "champion_version_id,history_by_version,expected",
    [
        ("v1", {"v1": ["2026-04-12T12:00:00+00:00"], "v2": ["2026-04-15T12:00:00+00:00"]}, "all"),
        (None, {}, "none"),
        ("v1", {"v1": ["2026-04-12T12:00:00+00:00"]}, "some"),
    ],
)
async def test_champion_coverage_all_none_some(
    mock_api_client,
    champion_version_id,
    history_by_version,
    expected,
):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=champion_version_id)

    def history_for(version_id):
        return [
            {"versionId": version_id, "enteredAt": entered_at, "previousChampionVersionId": "v0"}
            for entered_at in history_by_version.get(version_id, [])
        ]

    versions = [
        _version("v1", champion_history=history_for("v1")),
        _version("v2", created_at="2026-04-14T12:00:00+00:00", champion_history=history_for("v2")),
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=versions)),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))),
    ):
        output, _ = await block.generate()

    assert output["summary"]["champion_coverage"] == expected


@pytest.mark.asyncio
async def test_uses_llm_summary_and_score_summaries(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=[_version("v1")])),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
        patch.object(
            block,
            "_run_tac_inference",
            new=AsyncMock(return_value=json.dumps({
                "overall_summary": "Overall LLM summary.",
                "score_summaries": {"score-1": "Score-specific LLM summary."},
            })),
        ) as run_llm,
    ):
        output, _ = await block.generate()

    assert run_llm.await_count == 1
    prompt = run_llm.await_args.args[0]
    system_prompt = run_llm.await_args.kwargs["system_prompt"]
    assert "stakeholders and SMEs" in prompt
    assert "**What changed**" in prompt
    assert "**Guideline / rubric changes**" in prompt
    assert "**Scoring behavior changes**" in prompt
    assert "**Questions for SMEs / stakeholders**" in prompt
    assert "sme_question_context first" in prompt
    assert "do not include version IDs" in prompt
    assert '"champion_coverage": "none"' in prompt
    assert '"guideline_change_count": 1' in prompt
    assert '"code_change_count": 1' in prompt
    assert "Only say no rubric wording changed when overall_counts.guideline_change_count is exactly 0" in prompt
    assert "use overall_counts.champion_coverage exactly" in prompt
    assert "YAML" in prompt
    assert "Prioritize rubric meaning and operational impact" in system_prompt
    assert output["summary"]["text"] == "Overall LLM summary."
    assert "1 starred version was created" in output["scores"][0]["summary"]
    assert "v1 note" in output["scores"][0]["summary"]


@pytest.mark.asyncio
async def test_includes_procedure_sme_agenda_context_in_summary_prompt(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)
    procedure = {
        "id": "proc-1",
        "name": "Optimizer run",
        "status": "COMPLETE",
        "updatedAt": "2026-04-11T12:00:00+00:00",
        "metadata": {
            "end_of_run_report": {
                "sme_agenda": {
                    "text": "### Current medication boundary\n**Question:** Should vitamins count as current medications for dosage review?"
                }
            },
            "cycle_insights": [
                {
                    "sme_agenda": "### Pharmacy confirmation\n**Question:** Is pharmacy use enough when the customer does not explicitly confirm it?"
                }
            ],
        },
    }

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=[_version("v1")])),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
        patch.object(block, "_fetch_procedures_for_version", new=AsyncMock(return_value=[procedure])),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))) as run_llm,
    ):
        output, _ = await block.generate()

    context = output["scores"][0]["sme_question_context"]
    assert context[0]["procedure_id"] == "proc-1"
    assert "Should vitamins count" in context[0]["text"]
    prompt = run_llm.await_args.args[0]
    assert "Should vitamins count as current medications" in prompt
    assert "Is pharmacy use enough" in prompt


@pytest.mark.asyncio
async def test_llm_summary_failure_returns_report_error(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=[_version("v1")])),
        patch.object(block, "_fetch_evaluations_for_version", new=AsyncMock(return_value=[])),
        patch.object(block, "_run_tac_inference", new=AsyncMock(side_effect=RuntimeError("LLM unavailable"))),
    ):
        output, _ = await block.generate()

    assert "LLM unavailable" in output["error"]
    assert output["scores"] == []


@pytest.mark.asyncio
async def test_performance_uses_latest_in_window_version_and_created_at_predecessor(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)
    versions = [
        _version("v0", created_at="2026-03-31T12:00:00+00:00", is_featured="true"),
        _version("v1", created_at="2026-04-10T12:00:00+00:00", is_featured="true"),
        _version("v2", created_at="2026-04-20T12:00:00+00:00", is_featured="true"),
    ]
    evaluations_by_version = {
        "v0": [_evaluation("eval-v0-feedback", evaluation_type="feedback", score_version_id="v0", alignment=0.42)],
        "v2": [_evaluation("eval-v2-feedback", evaluation_type="feedback", score_version_id="v2", alignment=0.84)],
    }

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=versions)),
        patch.object(
            block,
            "_fetch_evaluations_for_version",
            new=AsyncMock(side_effect=lambda version_id: evaluations_by_version.get(version_id, [])),
        ),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))),
    ):
        output, _ = await block.generate()

    performance = output["scores"][0]["performance"]
    assert performance["current_version_id"] == "v2"
    assert performance["baseline_version_id"] == "v0"
    assert performance["recent_feedback"]["current"]["evaluation_id"] == "eval-v2-feedback"
    assert performance["recent_feedback"]["current"]["metrics"] == {
        "alignment": 0.84,
        "accuracy": 80.0,
        "precision": 0.6,
        "recall": 0.5,
    }
    assert performance["recent_feedback"]["baseline"]["evaluation_id"] == "eval-v0-feedback"
    assert performance["recent_feedback"]["baseline"]["metrics"]["alignment"] == 0.42


@pytest.mark.asyncio
async def test_regression_baseline_requires_same_dataset(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)
    versions = [
        _version("v0", created_at="2026-03-31T12:00:00+00:00"),
        _version("v1", created_at="2026-04-10T12:00:00+00:00"),
    ]
    evaluations_by_version = {
        "v0": [
            _evaluation(
                "eval-v0-regression-other",
                evaluation_type="accuracy",
                score_version_id="v0",
                alignment=0.91,
                dataset_id="dataset-other",
            ),
            _evaluation(
                "eval-v0-regression-same",
                evaluation_type="accuracy",
                score_version_id="v0",
                alignment=0.72,
                dataset_id="dataset-1",
            ),
        ],
        "v1": [
            _evaluation(
                "eval-v1-regression",
                evaluation_type="accuracy",
                score_version_id="v1",
                alignment=0.81,
                dataset_id="dataset-1",
            )
        ],
    }

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=versions)),
        patch.object(
            block,
            "_fetch_evaluations_for_version",
            new=AsyncMock(side_effect=lambda version_id: evaluations_by_version.get(version_id, [])),
        ),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))),
    ):
        output, _ = await block.generate()

    regression = output["scores"][0]["performance"]["regression"]
    assert regression["current"]["evaluation_id"] == "eval-v1-regression"
    assert regression["current"]["dataset_id"] == "dataset-1"
    assert regression["baseline"]["evaluation_id"] == "eval-v0-regression-same"
    assert regression["baseline"]["dataset_id"] == "dataset-1"


@pytest.mark.asyncio
async def test_omits_regression_without_dataset_and_omits_empty_performance(mock_api_client):
    block = _block(
        {"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        mock_api_client,
    )
    scorecard = SimpleNamespace(id="sc-1", name="Scorecard")
    scope = SimpleNamespace(score_id="score-1", score_name="Score 1", champion_version_id=None)

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_scores_for_mode", new=AsyncMock(return_value=[scope])),
        patch.object(block, "_fetch_versions_for_score", new=AsyncMock(return_value=[_version("v1")])),
        patch.object(
            block,
            "_fetch_evaluations_for_version",
            new=AsyncMock(return_value=[_evaluation("eval-v1-accuracy", evaluation_type="accuracy")]),
        ),
        patch.object(block, "_run_tac_inference", new=AsyncMock(return_value=_summary_response("score-1"))),
    ):
        output, _ = await block.generate()

    assert "performance" not in output["scores"][0]


def test_selects_best_completed_evaluation_by_alignment_then_created_at(mock_api_client):
    block = _block({"scorecard": "sc-1"}, mock_api_client)
    evaluations = [
        _evaluation("failed", evaluation_type="feedback", status="FAILED", alignment=0.99),
        _evaluation("older-best", evaluation_type="feedback", alignment=0.80, created_at="2026-04-10T12:00:00+00:00"),
        _evaluation("latest-tie", evaluation_type="feedback", alignment=0.80, created_at="2026-04-11T12:00:00+00:00"),
        _evaluation("lower-latest", evaluation_type="feedback", alignment=0.70, created_at="2026-04-12T12:00:00+00:00"),
    ]

    selected = block._select_best_evaluation(evaluations, "feedback")

    assert selected["id"] == "latest-tie"


def test_metrics_payload_extracts_list_metrics_and_omits_missing_values(mock_api_client):
    block = _block({"scorecard": "sc-1"}, mock_api_client)
    evaluation = _evaluation(
        "eval-list",
        evaluation_type="feedback",
        accuracy=None,
        alignment=None,
        precision=None,
        recall=None,
    )
    evaluation["metrics"] = [
        {"name": "Alignment", "value": 0.63},
        {"name": "Precision", "value": 0.52},
    ]

    payload = block._metrics_payload(evaluation)

    assert payload["metrics"] == {"alignment": 0.63, "precision": 0.52}
    assert "dataset_id" not in payload


def test_extracts_structured_tactus_summary_as_json(mock_api_client):
    block = _block({"scorecard": "sc-1"}, mock_api_client)

    extracted = block._extract_tactus_text({
        "text": {
            "overall_summary": "Overall.",
        }
    })

    assert json.loads(extracted) == {
        "overall_summary": "Overall.",
    }


def test_extracts_nested_tactus_message_text(mock_api_client):
    block = _block({"scorecard": "sc-1"}, mock_api_client)

    extracted = block._extract_tactus_text({
        "text": {
            "output": [
                {
                    "content": [
                        {"text": "{\"overall_summary\":\"Overall.\",\"score_summaries\":{}}"}
                    ]
                }
            ]
        }
    })

    assert extracted == "{\"overall_summary\":\"Overall.\",\"score_summaries\":{}}"
