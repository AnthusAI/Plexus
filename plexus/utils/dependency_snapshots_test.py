from types import SimpleNamespace
from unittest.mock import patch

import pytest

from plexus.scores.Score import Score
from plexus.utils.dependency_snapshots import (
    DEPENDENCY_SOURCE_IN_MEMORY,
    check_score_result_dependency_snapshot_current,
    DependencySnapshot,
    snapshot_from_in_memory_results,
)


class Registry:
    def __init__(self, configs):
        self.configs = {config["name"]: config for config in configs}

    def get_properties(self, score_name):
        return self.configs.get(score_name)


def test_dependency_snapshot_hash_is_deterministic():
    dependencies = [
        {
            "score_id": "score-1",
            "score_name": "Child",
            "score_result_id": "result-1",
            "value": "Yes",
            "source": "persisted_score_result",
        }
    ]

    assert DependencySnapshot(dependencies=dependencies).hash == DependencySnapshot(dependencies=dependencies).hash


def test_snapshot_from_in_memory_results_marks_source_and_hashes_explanation():
    child_config = {"name": "Child", "id": "child-id", "key": "child"}
    target_config = {"name": "Composite", "id": "target-id", "depends_on": ["Child"]}
    scorecard = SimpleNamespace(
        scores=[child_config, target_config],
        score_registry=Registry([child_config, target_config]),
    )
    child_result = Score.Result(
        value="No",
        explanation="Child failed",
        parameters=Score.Parameters(name="Child", id="child-id", key="child"),
    )

    snapshot = snapshot_from_in_memory_results(
        scorecard_instance=scorecard,
        target_score_name="Composite",
        score_results={"child-id": child_result},
    )

    assert snapshot.complete is True
    assert snapshot.dependencies[0]["source"] == DEPENDENCY_SOURCE_IN_MEMORY
    assert snapshot.dependencies[0]["explanation_hash"] is not None
    assert snapshot.as_dict()["hash"] == snapshot.hash


def test_snapshot_from_in_memory_results_unwraps_scorecard_result_entries():
    child_config = {"name": "Child", "id": "child-id", "key": "child"}
    target_config = {"name": "Composite", "id": "target-id", "depends_on": ["Child"]}
    scorecard = SimpleNamespace(
        scores=[child_config, target_config],
        score_registry=Registry([child_config, target_config]),
    )
    child_result = Score.Result(
        value="Yes",
        explanation="Wrapped child",
        parameters=Score.Parameters(name="Child", id="child-id", key="child"),
    )

    snapshot = snapshot_from_in_memory_results(
        scorecard_instance=scorecard,
        target_score_name="Composite",
        score_results={"child-id": {"result": child_result, "metadata": {}}},
    )

    assert snapshot.complete is True
    assert snapshot.dependencies[0]["value"] == "Yes"
    assert snapshot.missing_dependencies == []


@pytest.mark.asyncio
async def test_check_score_result_dependency_snapshot_current_detects_changed_dependency():
    stored_snapshot = DependencySnapshot(dependencies=[{
        "score_id": "child-id",
        "score_name": "Child",
        "score_result_id": "old-child-result",
        "value": "Yes",
        "source": "persisted_score_result",
    }]).as_dict()
    cached_composite = SimpleNamespace(
        trace={"dependency_snapshot_v1": stored_snapshot},
        metadata={},
    )
    current_child = SimpleNamespace(
        id="new-child-result",
        value="No",
        explanation="Changed child",
        metadata={},
        createdAt="2026-07-06T11:00:00Z",
        updatedAt="2026-07-06T11:00:01Z",
    )

    with patch(
        "plexus.dashboard.api.models.score_result.ScoreResult.find_by_cache_key",
        return_value=current_child,
    ):
        check = await check_score_result_dependency_snapshot_current(
            score_result=cached_composite,
            client=SimpleNamespace(),
            item_id="item-id",
            account_id="account-id",
    )

    assert check["has_dependency_snapshot"] is True
    assert check["matches"] is False
    assert check["reason"] == "dependency_snapshot_changed_after_write"
