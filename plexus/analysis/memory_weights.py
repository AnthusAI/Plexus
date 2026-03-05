"""
Memory weights: reinforcement and decay for topic clusters.

Clusters that receive new documents are reinforced (weight -> 1.0).
Clusters with no new documents decay (weight -> 0.0).
Tiers: hot >= 0.7, warm >= 0.3, cold < 0.3.
"""

from typing import Any, Dict, List, Optional, Tuple

DEFAULT_HOT_THRESHOLD = 0.7
DEFAULT_WARM_THRESHOLD = 0.3
DEFAULT_PRUNE_THRESHOLD = 0.1


def initial_weight() -> float:
    """Neutral starting weight for new clusters."""
    return 0.5


def reinforce(weight: float, new_docs: int, rate: float = 0.1) -> float:
    """Increase weight toward 1.0 based on new document count."""
    delta = rate * min(new_docs / 10.0, 1.0)
    return min(1.0, weight + delta)


def decay(weight: float, days: int, rate: float = 0.05) -> float:
    """Decrease weight toward 0.0 based on days since last reinforcement."""
    delta = rate * min(days / 7.0, 1.0)
    return max(0.0, weight - delta)


def tier_from_weight(
    weight: float,
    hot_threshold: float = DEFAULT_HOT_THRESHOLD,
    warm_threshold: float = DEFAULT_WARM_THRESHOLD,
) -> str:
    """Map weight to hot/warm/cold tier."""
    if weight >= hot_threshold:
        return "hot"
    if weight >= warm_threshold:
        return "warm"
    return "cold"


def should_prune(weight: float, threshold: float = DEFAULT_PRUNE_THRESHOLD) -> bool:
    """Return True if weight is below prune threshold."""
    return weight < threshold


def update_memory_weights(
    existing_clusters: List[Dict[str, Any]],
    active_cluster_ids: List[int],
    days_inactive: Optional[Dict[int, int]] = None,
    reinforce_rate: float = 0.1,
    decay_rate: float = 0.05,
    prune_threshold: float = DEFAULT_PRUNE_THRESHOLD,
    prune: bool = True,
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """
    Compute updated weights and tiers for clusters.
    Returns (updated_clusters, pruned_cluster_ids).
    """
    active_set = set(active_cluster_ids)
    days_inactive = days_inactive or {}
    updated: List[Dict[str, Any]] = []
    pruned: List[int] = []

    for c in existing_clusters:
        cid = c.get("cluster_id")
        if cid is None:
            continue
        cid_int = int(cid) if isinstance(cid, str) and cid.lstrip("-").isdigit() else cid
        weight = c.get("memory_weight", initial_weight())
        if isinstance(weight, (int, float)):
            weight = float(weight)
        else:
            weight = initial_weight()

        if cid_int in active_set:
            new_docs = c.get("new_docs_this_run", 10)
            weight = reinforce(weight, new_docs, reinforce_rate)
        else:
            days = days_inactive.get(cid_int, 7)
            weight = decay(weight, days, decay_rate)

        weight = max(0.0, min(1.0, weight))
        tier = tier_from_weight(weight)

        if prune and should_prune(weight, prune_threshold):
            pruned.append(cid_int)
            continue

        updated.append({
            **c,
            "memory_weight": weight,
            "memory_tier": tier,
        })

    return updated, pruned
