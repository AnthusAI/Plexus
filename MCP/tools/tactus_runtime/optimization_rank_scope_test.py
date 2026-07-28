"""Outside-in contracts for scorecard-scoped optimization ranking."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import FastMCP

from . import execute


def _card(
    card_id: str,
    name: str,
    score_id: str = "score",
    *,
    score_updated_at: str = "2024-01-01T00:00:00Z",
    latest_version_id: str | None = None,
    latest_version_created_at: str = "2024-01-01T00:00:00Z",
    champion_resolves: bool = True,
) -> dict[str, Any]:
    """Return an inventory row with deliberately old, valid activity evidence."""
    latest_version_id = latest_version_id or f"version-{score_id}"
    return {
        "id": card_id,
        "name": name,
        "sections": {"items": [{"scores": {"items": [{
            "id": score_id,
            "name": f"{name} score",
            "championVersionId": f"version-{score_id}",
            "championVersion": ({
                "id": f"version-{score_id}",
                "scoreId": score_id,
                "createdAt": latest_version_created_at,
            } if champion_resolves else None),
            "updatedAt": score_updated_at,
            "versions": {"items": [{
                "id": latest_version_id,
                "createdAt": latest_version_created_at,
            }]},
        }]}}]},
    }


def test_rank_scope_classifies_a_dangling_champion_as_structurally_unranked() -> None:
    """A dead scalar pointer is not missing cooldown metadata for an eligible score."""
    module = execute.PlexusRuntimeModule(
        FastMCP("test-rank-dangling-champion"),
        scorecards_lister=lambda _args: {
            "items": [_card("card-a", "Alpha", champion_resolves=False)],
            "nextToken": None,
        },
    )
    module._feedback_aligner_batch = lambda _args: _complete_alignment(
        [_alignment_row("card-a", "Alpha")], 1
    )

    result = module.optimization.rank({})

    assert result["exact"] is True
    assert result["ranked"] == []
    assert result["coverage"]["activity"]["incomplete_score_count"] == 0
    assert result["unranked"][0]["unranked_reason"] == "invalid_champion"
    assert result["unranked"][0]["champion_version"] == "version-score"


def _alignment_row(card_id: str, name: str, score_id: str = "score") -> dict[str, Any]:
    return {
        "scorecard_id": card_id,
        "scorecard_name": name,
        "scores": [{
            "score_id": score_id,
            "score_name": f"{name} score",
            "champion_version": f"version-{score_id}",
            "total_items": 10,
            "disagreements": 2,
        }],
    }


def _complete_alignment(rows: list[dict[str, Any]], target_count: int) -> dict[str, Any]:
    return {
        "coverage": {
            "complete": True,
            "target_count": target_count,
            "completed_count": target_count,
            "failed_count": 0,
        },
        "scorecards": rows,
    }


def test_rank_scope_exact_opaque_ids_are_forwarded_unchanged_and_exclude_other_rows() -> None:
    opaque_id = "A-awkward_UUID:with/slashes+punctuation"
    batch_calls: list[dict[str, Any]] = []
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-opaque-id"),
        scorecards_lister=lambda _args: {
            "items": [
                _card(opaque_id, "Target"),
                _card("other-id", "Other"),
            ],
            "nextToken": None,
        },
    )
    module._feedback_aligner_batch = lambda args: batch_calls.append(args) or _complete_alignment(
        [_alignment_row(opaque_id, "Target"), _alignment_row("other-id", "Other")], 1
    )

    result = module.optimization.rank({"scorecard_ids": [opaque_id]})

    assert batch_calls[0]["scorecards"] == [opaque_id]
    assert [row["scorecard_id"] for row in result["ranked"]] == [opaque_id]
    assert result["scope"] == {
        "scorecard_ids": [opaque_id],
        "scorecard_name_prefixes": [],
    }
    assert result["coverage"]["scope"] == {
        "requested_scorecard_ids": [opaque_id],
        "requested_scorecard_name_prefixes": [],
        "matched_scorecard_ids": [opaque_id],
        "matched_scorecard_count": 1,
        "unmatched_scorecard_ids": [],
        "unmatched_scorecard_name_prefixes": [],
        "total_scorecards_inspected": 2,
    }


def test_rank_scope_prefixes_are_literal_case_insensitive_and_use_union_deduplication() -> None:
    batch_calls: list[dict[str, Any]] = []
    cards = [
        _card("card-alpha", "Alpha Team"),
        _card("card-alpine", "ALPINE Team"),
        _card("card-beta", "Beta Team"),
        _card("card-noise", "Unrelated Team"),
    ]
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-prefixes"),
        scorecards_lister=lambda _args: {"items": cards, "nextToken": None},
    )
    module._feedback_aligner_batch = lambda args: batch_calls.append(args) or _complete_alignment(
        [_alignment_row(card_id, name) for card_id, name in [
            ("card-alpha", "Alpha Team"),
            ("card-alpine", "ALPINE Team"),
            ("card-beta", "Beta Team"),
            ("card-noise", "Unrelated Team"),
        ]], 3
    )

    result = module.optimization.rank({
        "scorecard_ids": ["card-alpha"],
        "scorecard_name_prefixes": ["alp", "BETA", "alpha"],
    })

    assert batch_calls[0]["scorecards"] == ["card-alpha", "card-alpine", "card-beta"]
    assert {row["scorecard_id"] for row in result["ranked"]} == {
        "card-alpha", "card-alpine", "card-beta",
    }
    assert result["coverage"]["scope"]["matched_scorecard_ids"] == [
        "card-alpha", "card-alpine", "card-beta",
    ]


def test_rank_scope_reports_unmatched_selectors_after_full_pagination() -> None:
    page_calls: list[str | None] = []
    batch_calls: list[dict[str, Any]] = []

    def list_cards(args: dict[str, Any]) -> dict[str, Any]:
        page_calls.append(args.get("next_token"))
        if args.get("next_token") is None:
            return {"items": [_card("card-a", "Alpha")], "nextToken": "page-2"}
        return {"items": [_card("card-b", "Beta")], "nextToken": None}

    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-unmatched"), scorecards_lister=list_cards
    )
    module._feedback_aligner_batch = lambda args: batch_calls.append(args) or _complete_alignment(
        [_alignment_row("card-a", "Alpha")], 1
    )

    result = module.optimization.rank({
        "scorecard_ids": ["card-a", "missing-id"],
        "scorecard_name_prefixes": ["Missing prefix"],
    })

    assert page_calls == [None, "page-2"]
    assert batch_calls[0]["scorecards"] == ["card-a"]
    assert result["exact"] is True
    assert result["coverage"]["scope"]["unmatched_scorecard_ids"] == ["missing-id"]
    assert result["coverage"]["scope"]["unmatched_scorecard_name_prefixes"] == ["Missing prefix"]
    assert result["coverage"]["scope"]["total_scorecards_inspected"] == 2


@pytest.mark.parametrize("args", [
    {"scorecard_ids": []},
    {"scorecard_name_prefixes": []},
    {"scorecard_ids": [], "scorecard_name_prefixes": []},
])
def test_rank_scope_rejects_explicit_empty_selectors(args: dict[str, list[str]]) -> None:
    module = execute.PlexusRuntimeModule(FastMCP("test-scoped-rank-empty"))

    with pytest.raises(ValueError, match="empty.*selector|selector.*empty"):
        module.optimization.rank(args)


def test_rank_scope_rejects_an_explicit_empty_selector_before_the_scores_bypass() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-empty-scores"),
        scorecards_lister=lambda _args: pytest.fail("selector validation must precede discovery"),
    )

    with pytest.raises(ValueError, match="empty.*selector|selector.*empty"):
        module.optimization.rank({
            "scorecard_ids": [],
            "scores": [{
                "scorecard_id": "card-a", "score_id": "score-a",
                "champion_version": "version-a", "total_items": 1,
            }],
            "coverage": {"complete": True},
        })


@pytest.mark.parametrize("field,value", [
    ("scorecard_ids", "card-a"),
    ("scorecard_ids", {"id": "card-a"}),
    ("scorecard_name_prefixes", 1),
    ("scorecard_name_prefixes", None),
])
def test_rank_scope_rejects_non_array_selector_values(field: str, value: Any) -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-non-array"),
        scorecards_lister=lambda _args: pytest.fail("selector validation must precede discovery"),
    )

    with pytest.raises(ValueError, match="array|list|selector"):
        module.optimization.rank({field: value})


@pytest.mark.parametrize("field,value", [
    ("scorecard_ids", ["card-a", 7]),
    ("scorecard_ids", ["card-a", "  "]),
    ("scorecard_name_prefixes", [None]),
    ("scorecard_name_prefixes", [""]),
])
def test_rank_scope_rejects_non_string_or_blank_selector_entries(field: str, value: list[Any]) -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-invalid-entry"),
        scorecards_lister=lambda _args: pytest.fail("selector validation must precede discovery"),
    )

    with pytest.raises(ValueError, match="string|blank|selector"):
        module.optimization.rank({field: value})


def test_rank_scope_zero_exact_matches_is_complete_and_skips_feedback_batch() -> None:
    batch_calls: list[dict[str, Any]] = []
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-zero"),
        scorecards_lister=lambda _args: {
            "items": [_card("card-a", "Alpha")], "nextToken": None,
        },
    )
    module._feedback_aligner_batch = lambda args: batch_calls.append(args) or _complete_alignment(
        [_alignment_row("card-a", "Alpha")], 1
    )

    result = module.optimization.rank({"scorecard_name_prefixes": ["No such scorecard"]})

    assert batch_calls == []
    assert result["exact"] is True
    assert result["total_population"] == 0
    assert result["coverage"]["complete"] is True
    assert result["coverage"]["scope"]["matched_scorecard_count"] == 0
    assert result["coverage"]["scope"]["unmatched_scorecard_name_prefixes"] == ["No such scorecard"]


def test_rank_scope_uses_one_frozen_as_of_and_returns_inventory_activity_evidence() -> None:
    """Ranking freezes the inventory/activity view before any downstream read."""
    opaque_version_id = "version:opaque/with+punctuation_123"
    page_calls: list[dict[str, Any]] = []
    alignment_calls: list[dict[str, Any]] = []

    def list_cards(args: dict[str, Any]) -> dict[str, Any]:
        page_calls.append(dict(args))
        return {
            "items": [_card(
                "card-a",
                "Alpha",
                score_updated_at="2024-02-03T04:05:06Z",
                latest_version_id=opaque_version_id,
                latest_version_created_at="2024-02-02T03:04:05Z",
            )],
            "nextToken": None,
        }

    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-activity-evidence"), scorecards_lister=list_cards
    )
    module._feedback_aligner_batch = lambda args: alignment_calls.append(args) or _complete_alignment(
        [_alignment_row("card-a", "Alpha")], 1
    )

    result = module.optimization.rank({"scorecard_ids": ["card-a"]})

    assert len(page_calls) == 1
    as_of = page_calls[0]["as_of"]
    assert as_of.endswith("Z")
    assert alignment_calls[0]["as_of"] == as_of
    assert result["coverage"]["activity"]["as_of"] == as_of
    assert result["ranked"][0]["score_activity"] == {
        "policy_version": "score-activity-cooldown-v1",
        "as_of": as_of,
        "cutoff": result["coverage"]["activity"]["cutoff"],
        "score_updated_at": "2024-02-03T04:05:06Z",
        "newest_version_id": opaque_version_id,
        "newest_version_created_at": "2024-02-02T03:04:05Z",
        "activity_source": "score_record",
        "activity_timestamp": "2024-02-03T04:05:06Z",
        "eligibility_timestamp": "2024-02-10T04:05:06Z",
        "recent": False,
        "complete": True,
        "failure": None,
    }


@pytest.mark.parametrize("broken_inventory", [
    {"updatedAt": None},
    {"updatedAt": "not-a-timestamp"},
    {"versions": {"items": []}},
    {"versions": {"items": [{"id": "version-only"}]}},
    {"versions": {"items": [{"id": 7, "createdAt": "2024-01-01T00:00:00Z"}]}},
    {"versions": {"items": [{"id": "version-only", "createdAt": "not-a-timestamp"}]}},
])
def test_rank_scope_missing_or_malformed_inventory_activity_fails_closed(
    broken_inventory: dict[str, Any],
) -> None:
    """Incomplete activity evidence must never produce an exact rank or cooldown."""
    batch_calls: list[dict[str, Any]] = []
    card = _card("card-a", "Alpha")
    score = card["sections"]["items"][0]["scores"]["items"][0]
    score.update(broken_inventory)
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-invalid-activity"),
        scorecards_lister=lambda _args: {"items": [card], "nextToken": None},
    )
    module._feedback_aligner_batch = lambda args: batch_calls.append(args) or _complete_alignment(
        [_alignment_row("card-a", "Alpha")], 1
    )

    result = module.optimization.rank({"scorecard_ids": ["card-a"]})

    assert len(batch_calls) == 1
    assert result["exact"] is False
    assert result["coverage"]["complete"] is False
    assert result["coverage"]["activity"]["complete"] is False
    assert "inventory activity" in str(result["coverage"]["failures"]).lower()
    assert result["ranked"] == []
    assert result["unranked"][0]["score_id"] == "score"
    assert result["unranked"][0]["unranked_reason"] == "incomplete_score_activity"


def test_rank_scope_failed_continuation_does_not_analyze_partial_scope_or_claim_exact() -> None:
    page_calls: list[str | None] = []
    batch_calls: list[dict[str, Any]] = []

    def list_cards(args: dict[str, Any]) -> dict[str, Any]:
        token = args.get("next_token")
        page_calls.append(token)
        if token is None:
            return {"items": [_card("card-a", "Alpha")], "nextToken": "page-2"}
        raise RuntimeError("continuation unavailable")

    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-page-failure"), scorecards_lister=list_cards
    )
    module._feedback_aligner_batch = lambda args: batch_calls.append(args) or _complete_alignment(
        [_alignment_row("card-a", "Alpha")], 1
    )

    result = module.optimization.rank({"scorecard_name_prefixes": ["Alpha"]})

    assert page_calls == [None, "page-2", "page-2"]
    assert batch_calls == []
    assert result["exact"] is False
    assert result["coverage"]["complete"] is False
    assert result["coverage"]["failures"][0]["page"] == 2


def test_rank_scope_requires_downstream_coverage_for_the_scoped_targets() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-coverage"),
        scorecards_lister=lambda _args: {
            "items": [_card("card-a", "Alpha"), _card("card-b", "Beta")],
            "nextToken": None,
        },
    )
    module._feedback_aligner_batch = lambda _args: _complete_alignment(
        [_alignment_row("card-a", "Alpha")], 0
    )

    result = module.optimization.rank({"scorecard_ids": ["card-a"]})

    assert result["exact"] is False
    assert result["coverage"]["complete"] is False
    assert "does not match discovered scope" in str(result["coverage"]["failures"])
    mismatch = next(
        failure for failure in result["coverage"]["failures"]
        if failure.get("error") == "analysis coverage does not match discovered scope"
    )
    assert mismatch["discovered_target_count"] == 1


def test_rank_scope_deduplicates_duplicate_discovered_ids_in_enumeration_order() -> None:
    batch_calls: list[dict[str, Any]] = []
    cards = [
        _card("card-a", "Alpha"),
        _card("card-b", "Beta"),
        _card("card-a", "Alpha duplicate"),
    ]
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-deduplicate"),
        scorecards_lister=lambda _args: {"items": cards, "nextToken": None},
    )
    module._feedback_aligner_batch = lambda args: batch_calls.append(args) or _complete_alignment(
        [_alignment_row("card-a", "Alpha"), _alignment_row("card-b", "Beta")], 2
    )

    result = module.optimization.rank({"scorecard_ids": ["card-a", "card-b"]})

    assert batch_calls[0]["scorecards"] == ["card-a", "card-b"]
    assert result["coverage"]["scope"]["matched_scorecard_ids"] == ["card-a", "card-b"]


def test_rank_scope_marks_unexpected_batch_rows_incomplete_and_excludes_them() -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-unexpected-row"),
        scorecards_lister=lambda _args: {
            "items": [_card("card-a", "Alpha"), _card("card-b", "Beta")],
            "nextToken": None,
        },
    )
    module._feedback_aligner_batch = lambda _args: _complete_alignment([
        _alignment_row("card-a", "Alpha"),
        _alignment_row("unexpected-card", "Unexpected"),
    ], 1)

    result = module.optimization.rank({"scorecard_ids": ["card-a"]})

    assert result["exact"] is False
    assert result["coverage"]["complete"] is False
    assert [row["scorecard_id"] for row in result["ranked"]] == ["card-a"]
    assert "unexpected" in str(result["coverage"]["failures"]).lower()


def test_rank_scope_fingerprint_binds_normalized_scope_even_with_supplied_scores() -> None:
    scores = [{
        "scorecard_id": "card-a", "score_id": "score-a", "scorecard_name": "Alpha",
        "score_name": "One", "champion_version": "version-a", "total_items": 10,
        "disagreements": 2,
    }]
    module = execute.PlexusRuntimeModule(FastMCP("test-scoped-rank-fingerprint"))

    exact_id_scope = module.optimization.rank({
        "scores": scores,
        "coverage": {"complete": True},
        "scorecard_ids": ["card-a"],
    })
    prefix_scope = module.optimization.rank({
        "scores": scores,
        "coverage": {"complete": True},
        "scorecard_name_prefixes": ["alpha"],
    })

    assert exact_id_scope["scope"] != prefix_scope["scope"]
    assert exact_id_scope["evidence_fingerprint"] != prefix_scope["evidence_fingerprint"]


def test_rank_scope_casefolds_equivalent_prefixes_for_one_fingerprint() -> None:
    scores = [{
        "scorecard_id": "card-a", "score_id": "score-a", "scorecard_name": "Alpha",
        "score_name": "One", "champion_version": "version-a", "total_items": 10,
        "disagreements": 2,
    }]
    module = execute.PlexusRuntimeModule(FastMCP("test-scoped-rank-prefix-fingerprint"))

    upper = module.optimization.rank({
        "scores": scores, "coverage": {"complete": True},
        "scorecard_name_prefixes": ["ALPHA"],
    })
    lower = module.optimization.rank({
        "scores": scores, "coverage": {"complete": True},
        "scorecard_name_prefixes": ["alpha"],
    })

    assert upper["scope"] == lower["scope"]
    assert upper["evidence_fingerprint"] == lower["evidence_fingerprint"]


@pytest.mark.parametrize("bad_score", [
    {"scorecard_id": "card-b", "score_id": "score"},
    {"scorecard_id": "card-a", "score_id": "unknown-score"},
])
def test_rank_scope_rejects_cross_attributed_or_unknown_nested_rows(
    bad_score: dict[str, str],
) -> None:
    module = execute.PlexusRuntimeModule(
        FastMCP("test-scoped-rank-corrupt-nested-row"),
        scorecards_lister=lambda _args: {
            "items": [_card("card-a", "Alpha"), _card("card-b", "Beta")],
            "nextToken": None,
        },
    )
    module._feedback_aligner_batch = lambda _args: _complete_alignment([{
        "scorecard_id": "card-a", "scorecard_name": "Alpha",
        "scores": [{
            **bad_score, "score_name": "Bad", "champion_version": "version-score",
            "total_items": 10, "disagreements": 2,
        }],
    }], 2)

    result = module.optimization.rank({"scorecard_ids": ["card-a", "card-b"]})

    assert result["exact"] is False
    assert result["ranked"] == []
    assert "unexpected" in str(result["coverage"]["failures"]).lower()
