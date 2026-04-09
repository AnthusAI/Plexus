from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from plexus.utils.feedback_selection import select_feedback_items


def _item(item_id: str, ts: str):
    return SimpleNamespace(
        id=item_id,
        editedAt=datetime.fromisoformat(ts).replace(tzinfo=timezone.utc),
        createdAt=None,
    )


def test_select_feedback_items_newest_returns_most_recent_n():
    items = [
        _item("a", "2026-01-01T00:00:00"),
        _item("b", "2026-01-02T00:00:00"),
        _item("c", "2026-01-03T00:00:00"),
    ]
    selected, metadata = select_feedback_items(
        items,
        max_items=2,
        sampling_mode="newest",
        sample_seed=None,
    )
    assert [item.id for item in selected] == ["c", "b"]
    assert metadata["candidate_pool_count"] == 3
    assert metadata["selected_count"] == 2


def test_select_feedback_items_random_seed_is_deterministic():
    items = [_item(f"id-{i}", f"2026-01-{i+1:02d}T00:00:00") for i in range(10)]
    selected_one, _ = select_feedback_items(
        items,
        max_items=4,
        sampling_mode="random",
        sample_seed=1234,
    )
    selected_two, _ = select_feedback_items(
        items,
        max_items=4,
        sampling_mode="random",
        sample_seed=1234,
    )
    assert [item.id for item in selected_one] == [item.id for item in selected_two]


def test_select_feedback_items_shortfall_uses_all_available():
    items = [_item("one", "2026-01-01T00:00:00"), _item("two", "2026-01-02T00:00:00")]
    selected, metadata = select_feedback_items(
        items,
        max_items=5,
        sampling_mode="newest",
        sample_seed=None,
    )
    assert len(selected) == 2
    assert metadata["shortfall_count"] == 3


def test_select_feedback_items_seed_invalid_for_newest():
    items = [_item("one", "2026-01-01T00:00:00")]
    with pytest.raises(ValueError, match="sample_seed is only valid"):
        select_feedback_items(
            items,
            max_items=1,
            sampling_mode="newest",
            sample_seed=42,
        )

