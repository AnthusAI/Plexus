"""Tests for memory weights."""
import pytest

from plexus.analysis.memory_weights import (
    decay,
    initial_weight,
    reinforce,
    should_prune,
    tier_from_weight,
    update_memory_weights,
)


def test_initial_weight():
    """New cluster starts with 0.5."""
    assert initial_weight() == 0.5


def test_reinforce_increases_weight():
    """Reinforced cluster weight increases."""
    w = reinforce(0.5, 20, rate=0.1)
    assert w > 0.5
    assert w <= 1.0


def test_reinforce_clamped():
    """Reinforce does not exceed 1.0."""
    w = reinforce(0.95, 100, rate=0.5)
    assert w <= 1.0


def test_decay_decreases_weight():
    """Decayed cluster weight decreases."""
    w = decay(0.7, 14, rate=0.05)
    assert w < 0.7
    assert w >= 0.0


def test_decay_clamped():
    """Decay does not go below 0.0."""
    w = decay(0.1, 100, rate=0.5)
    assert w >= 0.0


def test_tier_from_weight():
    """Tier assignment from weight."""
    assert tier_from_weight(0.8) == "hot"
    assert tier_from_weight(0.5) == "warm"
    assert tier_from_weight(0.1) == "cold"


def test_tier_boundaries():
    """Tier boundaries at thresholds."""
    assert tier_from_weight(0.7) == "hot"
    assert tier_from_weight(0.69) == "warm"
    assert tier_from_weight(0.3) == "warm"
    assert tier_from_weight(0.29) == "cold"


def test_should_prune():
    """Cold clusters below threshold are pruned."""
    assert should_prune(0.05, threshold=0.1) is True
    assert should_prune(0.1, threshold=0.1) is False
    assert should_prune(0.15, threshold=0.1) is False


def test_update_memory_weights_reinforces_active():
    """Active clusters get reinforced."""
    clusters = [
        {"cluster_id": 0, "memory_weight": 0.5},
        {"cluster_id": 1, "memory_weight": 0.7},
        {"cluster_id": 2, "memory_weight": 0.3},
        {"cluster_id": 3, "memory_weight": 0.8},
        {"cluster_id": 4, "memory_weight": 0.4},
    ]
    for c in clusters:
        c["new_docs_this_run"] = 10
    updated, pruned = update_memory_weights(clusters, active_cluster_ids=[0, 1, 3])
    updated_by_id = {c["cluster_id"]: c for c in updated}
    assert updated_by_id[0]["memory_weight"] > 0.5
    assert updated_by_id[1]["memory_weight"] > 0.7
    assert updated_by_id[3]["memory_weight"] > 0.8


def test_update_memory_weights_decays_inactive():
    """Inactive clusters decay."""
    clusters = [
        {"cluster_id": 2, "memory_weight": 0.3, "new_docs_this_run": 0},
        {"cluster_id": 4, "memory_weight": 0.4, "new_docs_this_run": 0},
    ]
    updated, _ = update_memory_weights(
        clusters, active_cluster_ids=[], days_inactive={2: 14, 4: 14}
    )
    updated_by_id = {c["cluster_id"]: c for c in updated}
    assert updated_by_id[2]["memory_weight"] < 0.3
    assert updated_by_id[4]["memory_weight"] < 0.4


def test_update_memory_weights_tiers():
    """All clusters get memory_tier."""
    clusters = [
        {"cluster_id": 0, "memory_weight": 0.5},
        {"cluster_id": 1, "memory_weight": 0.8},
    ]
    for c in clusters:
        c["new_docs_this_run"] = 10
    updated, _ = update_memory_weights(clusters, active_cluster_ids=[0, 1])
    for c in updated:
        assert c["memory_tier"] in ("hot", "warm", "cold")


def test_update_memory_weights_prunes():
    """Clusters below prune threshold are pruned."""
    clusters = [
        {"cluster_id": 0, "memory_weight": 0.5},
        {"cluster_id": 1, "memory_weight": 0.05},
    ]
    updated, pruned = update_memory_weights(
        clusters, active_cluster_ids=[0], prune_threshold=0.1, prune=True
    )
    assert 1 in pruned
    assert len(updated) == 1
    assert updated[0]["cluster_id"] == 0
