"""Operator-facing identity specifications for optimization work."""

from plexus.optimization.operator_identity import optimization_operator_identity


def test_account_wide_portfolio_identity_is_explicit_from_the_start():
    identity = optimization_operator_identity(scope={})

    assert identity.kind == "account_wide_portfolio"
    assert identity.display_title == "Account-wide optimization portfolio"
    assert identity.display_scope == "All scorecards"


def test_prefix_and_exact_scorecard_scope_is_human_readable_without_opaque_ids():
    identity = optimization_operator_identity(scope={
        "scorecard_ids": ["3f9b66cb-a2b6-40e1-a435-69d04f476633"],
        "scorecard_name_prefixes": ["Example", "Sample"],
    })

    assert identity.kind == "scorecard_scoped_portfolio"
    assert identity.display_title == "Scorecard-scoped optimization portfolio"
    assert identity.display_scope == (
        '1 selected scorecard plus scorecard names beginning with "Example" or "Sample"'
    )
    assert "3f9b66cb" not in identity.display_scope


def test_lua_array_mappings_preserve_scorecard_scoped_identity():
    identity = optimization_operator_identity(scope={
        "scorecard_ids": {},
        "scorecard_name_prefixes": {1: "Example"},
    })

    assert identity.kind == "scorecard_scoped_portfolio"
    assert identity.display_title == "Scorecard-scoped optimization portfolio"
    assert identity.display_scope == 'scorecard names beginning with "Example"'


def test_exact_scope_can_be_enriched_with_names_after_exhaustive_enumeration():
    identity = optimization_operator_identity(
        scope={"scorecard_ids": ["opaque-one", "opaque-two"]},
        matched_scorecard_names=["Example Support", "Example Sales"],
    )

    assert identity.display_scope == "Example Sales and Example Support"
    assert "opaque" not in identity.display_scope


def test_single_score_identity_names_the_scorecard_and_score():
    identity = optimization_operator_identity(
        scorecard_name="Example Support",
        score_name="Clear greeting",
    )

    assert identity.kind == "single_score"
    assert identity.display_title == "Single-score optimization"
    assert identity.display_scope == "Example Support / Clear greeting"
