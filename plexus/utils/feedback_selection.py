from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional, Tuple


VALID_FEEDBACK_SAMPLING_MODES = frozenset({"newest", "random"})


def normalize_feedback_sampling_mode(mode: Optional[str]) -> str:
    normalized = (mode or "newest").strip().lower()
    if normalized not in VALID_FEEDBACK_SAMPLING_MODES:
        valid = ", ".join(sorted(VALID_FEEDBACK_SAMPLING_MODES))
        raise ValueError(f"sampling_mode must be one of: {valid}.")
    return normalized


def _timestamp_seconds(value: Any) -> float:
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    if isinstance(value, str):
        iso_value = value.strip()
        if iso_value.endswith("Z"):
            iso_value = f"{iso_value[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(iso_value)
        except ValueError:
            return float("-inf")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return float("-inf")


def _feedback_item_sort_key(item: Any) -> Tuple[float, str]:
    edited_at = getattr(item, "editedAt", None)
    created_at = getattr(item, "createdAt", None)
    ts = _timestamp_seconds(edited_at if edited_at is not None else created_at)
    item_id = str(getattr(item, "id", "") or "")
    return ts, item_id


def select_feedback_items(
    feedback_items: Iterable[Any],
    *,
    max_items: Optional[int],
    sampling_mode: Optional[str] = "newest",
    sample_seed: Optional[int] = None,
) -> tuple[List[Any], dict]:
    mode = normalize_feedback_sampling_mode(sampling_mode)
    if max_items is not None and max_items <= 0:
        raise ValueError("max_items must be a positive integer when provided.")
    if mode != "random" and sample_seed is not None:
        raise ValueError("sample_seed is only valid when sampling_mode is 'random'.")

    ordered_items = sorted(list(feedback_items), key=_feedback_item_sort_key, reverse=True)
    candidate_pool_count = len(ordered_items)

    if max_items is None or max_items >= candidate_pool_count:
        selected_items = ordered_items
    elif mode == "newest":
        selected_items = ordered_items[:max_items]
    else:
        rng = random.Random(sample_seed) if sample_seed is not None else random.Random()
        selected_indices = rng.sample(range(candidate_pool_count), max_items)
        selected_items = [ordered_items[index] for index in selected_indices]
        selected_items.sort(key=_feedback_item_sort_key, reverse=True)

    selected_ids = [
        str(getattr(item, "id", "") or "")
        for item in selected_items
        if getattr(item, "id", None)
    ]
    shortfall = max(0, int(max_items or 0) - len(selected_items)) if max_items is not None else 0
    metadata = {
        "sampling_mode": mode,
        "requested_max_items": max_items,
        "candidate_pool_count": candidate_pool_count,
        "selected_count": len(selected_items),
        "sample_seed": sample_seed if mode == "random" else None,
        "selection_order_basis": "editedAt desc, id desc",
        "selected_feedback_item_ids": selected_ids,
        "shortfall_count": shortfall,
    }
    return selected_items, metadata

