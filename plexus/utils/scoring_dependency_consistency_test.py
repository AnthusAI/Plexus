from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.scores.Score import Score
from plexus.utils.scoring import enqueue_downstream_recompute_jobs, score_single_target_with_dependencies


class Registry:
    def __init__(self, configs):
        self.configs = {config["name"]: config for config in configs}

    def get_properties(self, score_name):
        return self.configs.get(score_name)


@pytest.mark.asyncio
async def test_score_single_target_uses_complete_persisted_dependencies():
    child_config = {"name": "Child", "id": "child-id", "key": "child"}
    target_config = {"name": "Composite", "id": "target-id", "key": "composite", "depends_on": ["Child"]}
    persisted_child = SimpleNamespace(
        id="child-result-1",
        value="No",
        explanation="Persisted child failed",
        metadata={},
        scoreVersionId="child-version-1",
        createdAt="2026-07-06T10:00:00Z",
        updatedAt="2026-07-06T10:00:01Z",
    )

    async def get_score_result(**kwargs):
        assert kwargs["score"] == "Composite"
        assert len(kwargs["results"]) == 1
        assert kwargs["results"][0].metadata["dependency_source"] == "persisted_score_result"
        return Score.Result(
            value="No",
            explanation="Failed: Child",
            parameters=Score.Parameters(name="Composite", id="target-id"),
        )

    scorecard = SimpleNamespace(
        name="Scorecard",
        scores=[child_config, target_config],
        score_registry=Registry([child_config, target_config]),
        get_score_result=AsyncMock(side_effect=get_score_result),
    )

    with patch(
        "plexus.dashboard.api.models.score_result.ScoreResult.find_by_cache_key",
        return_value=persisted_child,
    ):
        outcome = await score_single_target_with_dependencies(
            scorecard,
            text="text",
            metadata={},
            modality="API",
            item=SimpleNamespace(id="item-1"),
            target_score_id="target-id",
            target_score_name="Composite",
            client=MagicMock(),
            item_id="item-1",
            account_id="account-1",
        )

    assert outcome.used_persisted_dependencies is True
    assert outcome.result.metadata["trace"]["dependency_snapshot_v1"]["complete"] is True
    assert set(outcome.result.metadata.keys()) == {"trace"}


@pytest.mark.asyncio
async def test_score_single_target_respects_persisted_dependency_conditions():
    child_config = {"name": "Child", "id": "child-id", "key": "child"}
    target_config = {
        "name": "Composite",
        "id": "target-id",
        "key": "composite",
        "depends_on": {"Child": {"operator": "==", "value": "Pass"}},
    }
    persisted_child = SimpleNamespace(
        id="child-result-1",
        value="Fail",
        explanation="Persisted child failed",
        metadata={},
        scoreVersionId="child-version-1",
        createdAt="2026-07-06T10:00:00Z",
        updatedAt="2026-07-06T10:00:01Z",
    )

    scorecard = SimpleNamespace(
        name="Scorecard",
        scores=[child_config, target_config],
        score_registry=Registry([child_config, target_config]),
        get_score_result=AsyncMock(),
        build_dependency_graph=MagicMock(return_value=(
            {
                "target-id": {
                    "name": "Composite",
                    "deps": ["child-id"],
                    "conditions": {"child-id": {"operator": "==", "value": "Pass"}},
                },
                "child-id": {"name": "Child", "deps": [], "conditions": {}},
            },
            {"Composite": "target-id", "Child": "child-id"},
        )),
        check_dependency_conditions=MagicMock(return_value=False),
    )

    with patch(
        "plexus.dashboard.api.models.score_result.ScoreResult.find_by_cache_key",
        return_value=persisted_child,
    ):
        outcome = await score_single_target_with_dependencies(
            scorecard,
            text="text",
            metadata={},
            modality="API",
            item=SimpleNamespace(id="item-1"),
            target_score_id="target-id",
            target_score_name="Composite",
            client=MagicMock(),
            item_id="item-1",
            account_id="account-1",
        )

    scorecard.get_score_result.assert_not_called()
    assert outcome.dependency_unmet is True
    assert outcome.dependency_snapshot.complete is True


@pytest.mark.asyncio
async def test_score_single_target_persists_missing_dependency_before_composite():
    child_config = {"name": "Child", "id": "child-id", "key": "child"}
    target_config = {"name": "Composite", "id": "target-id", "key": "composite", "depends_on": ["Child"]}
    child_result = Score.Result(
        value="No",
        explanation="JIT child failed",
        parameters=Score.Parameters(name="Child", id="child-id"),
    )
    persisted_child = SimpleNamespace(
        id="child-result-1",
        value="No",
        explanation="Persisted JIT child failed",
        metadata={},
        scoreVersionId="child-version-1",
        createdAt="2026-07-06T10:00:00Z",
        updatedAt="2026-07-06T10:00:01Z",
    )

    async def get_score_result(**kwargs):
        assert kwargs["score"] == "Composite"
        assert len(kwargs["results"]) == 1
        assert kwargs["results"][0].metadata["dependency_source"] == "persisted_score_result"
        assert kwargs["results"][0].metadata["score_result_id"] == "child-result-1"
        return Score.Result(
            value="No",
            explanation="Failed: Child",
            parameters=Score.Parameters(name="Composite", id="target-id"),
        )

    scorecard = SimpleNamespace(
        name="Scorecard",
        scores=[child_config, target_config],
        score_registry=Registry([child_config, target_config]),
        score_entire_text=AsyncMock(return_value={"child-id": child_result}),
        get_score_result=AsyncMock(side_effect=get_score_result),
    )

    with patch(
        "plexus.dashboard.api.models.score_result.ScoreResult.find_by_cache_key",
        side_effect=[None, None, None, persisted_child],
    ), patch(
        "plexus.utils.scoring.create_score_result",
        new_callable=AsyncMock,
        return_value="child-result-1",
    ) as create_score_result, patch(
        "plexus.utils.scoring.enqueue_downstream_recompute_jobs",
        new_callable=AsyncMock,
    ) as enqueue_downstream:
        outcome = await score_single_target_with_dependencies(
            scorecard,
            text="text",
            metadata={},
            modality="API",
            item=SimpleNamespace(id="item-1"),
            target_score_id="target-id",
            target_score_name="Composite",
            client=MagicMock(),
            item_id="item-1",
            account_id="account-1",
            scorecard_id="scorecard-1",
            scoring_job_id="job-1",
            external_id="external-1",
        )

    assert outcome.used_persisted_dependencies is True
    assert outcome.result.value == "No"
    scorecard.score_entire_text.assert_awaited_once()
    assert scorecard.score_entire_text.call_args.kwargs["subset_of_score_names"] == ["Child"]
    create_score_result.assert_awaited_once()
    assert create_score_result.call_args.kwargs["score_id"] == "child-id"
    assert create_score_result.call_args.kwargs["metadata_extra"]["created_via"] == "jit_dependency_score_result"
    assert create_score_result.call_args.kwargs["metadata_extra"]["requested_score_id"] == "target-id"
    enqueue_downstream.assert_awaited_once()


@pytest.mark.asyncio
async def test_score_single_target_fails_when_jit_dependency_returns_error():
    child_config = {"name": "Child", "id": "child-id", "key": "child"}
    target_config = {"name": "Composite", "id": "target-id", "key": "composite", "depends_on": ["Child"]}
    child_result = Score.Result(
        value="ERROR",
        explanation="Dependency failed",
        parameters=Score.Parameters(name="Child", id="child-id"),
    )
    scorecard = SimpleNamespace(
        name="Scorecard",
        scores=[child_config, target_config],
        score_registry=Registry([child_config, target_config]),
        score_entire_text=AsyncMock(return_value={"child-id": child_result}),
    )

    with patch(
        "plexus.dashboard.api.models.score_result.ScoreResult.find_by_cache_key",
        return_value=None,
    ), patch(
        "plexus.utils.scoring.create_score_result",
        new_callable=AsyncMock,
    ) as create_score_result:
        with pytest.raises(ValueError, match="returned ERROR"):
            await score_single_target_with_dependencies(
                scorecard,
                text="text",
                metadata={},
                modality="API",
                item=SimpleNamespace(id="item-1"),
                target_score_id="target-id",
                target_score_name="Composite",
                client=MagicMock(),
                item_id="item-1",
                account_id="account-1",
                scorecard_id="scorecard-1",
                scoring_job_id="job-1",
                external_id="external-1",
            )

    create_score_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_enqueue_downstream_recompute_jobs_finds_reverse_dependencies():
    created_job = SimpleNamespace(id="job-1")

    with patch(
        "plexus.cli.shared.fetch_scorecard_structure.fetch_scorecard_structure",
        return_value={"id": "scorecard-id"},
    ), patch(
        "plexus.cli.shared.identify_target_scores.identify_target_scores",
        return_value=[
            {"id": "child-id", "name": "Child"},
            {"id": "composite-id", "name": "Composite"},
        ],
    ), patch(
        "plexus.cli.shared.iterative_config_fetching.iteratively_fetch_configurations",
        return_value={
            "child-id": "name: Child\n",
            "composite-id": "name: Composite\ndepends_on:\n  - Child\n",
        },
    ), patch(
        "plexus.dashboard.api.models.scoring_job.ScoringJob.find_existing_job",
        return_value=None,
    ) as find_existing, patch(
        "plexus.dashboard.api.models.scoring_job.ScoringJob.create",
        return_value=created_job,
    ) as create_job, patch(
        "plexus.utils.scoring.send_message_to_standard_scoring_request_queue",
        new_callable=AsyncMock,
    ) as send_sqs:
        enqueued = await enqueue_downstream_recompute_jobs(
            client=MagicMock(),
            account_id="account-id",
            item_id="item-id",
            scorecard_id="scorecard-id",
            dependency_score_id="child-id",
            dependency_score_name="Child",
            source_score_result_id="child-result-id",
        )

    find_existing.assert_called_once()
    create_job.assert_called_once()
    send_sqs.assert_awaited_once_with("job-1")
    assert enqueued == [{
        "scoring_job_id": "job-1",
        "score_id": "composite-id",
        "score_name": "Composite",
    }]
