"""Executable specifications for exact semantic-inference budget accounting."""

from __future__ import annotations

from decimal import Decimal

import pytest


MODEL = "gpt-5-mini-2025-08-07"
PROVIDER = "openai"
PRICE_VERSION = "openai-2025-08-07-v1"


def _spec(max_cost: str = "1.00"):
    from plexus.optimization.semantic_budget import SemanticBudgetSpec

    return SemanticBudgetSpec(
        max_cost_usd=max_cost,
        pricing_version=PRICE_VERSION,
    )


def _plan(
    *,
    score_id: str = "score-1",
    target_id: str | None = None,
    call_site: str = "rubric_consistency",
    attempt: int = 1,
    max_input_tokens: int = 1_000,
    max_output_tokens: int = 100,
):
    from plexus.optimization.semantic_budget import SemanticCallPlan

    return SemanticCallPlan(
        run_key="run-1",
        target_id=target_id or f"scorecard-1:{score_id}",
        call_site=call_site,
        attempt=attempt,
        max_attempts=2,
        provider=PROVIDER,
        model=MODEL,
        pricing_version=PRICE_VERSION,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
    )


def test_checked_in_pricing_accepts_only_the_exact_immutable_model_revision():
    from plexus.optimization.semantic_budget import (
        UnknownSemanticPricing,
        load_semantic_pricing,
    )

    pricing = load_semantic_pricing(PRICE_VERSION).price_for(PROVIDER, MODEL)

    assert pricing.input_usd_per_million == Decimal("0.250")
    assert pricing.cached_input_usd_per_million == Decimal("0.025")
    assert pricing.output_usd_per_million == Decimal("2.000")
    with pytest.raises(UnknownSemanticPricing):
        load_semantic_pricing(PRICE_VERSION).price_for(PROVIDER, "gpt-5-mini")
    with pytest.raises(UnknownSemanticPricing):
        load_semantic_pricing("latest")


@pytest.mark.parametrize("value", [1, 1.0, Decimal("1"), "NaN", "Infinity", "-0.01"])
def test_budget_money_must_be_a_finite_non_negative_decimal_string(value):
    from plexus.optimization.semantic_budget import SemanticBudgetSpec

    with pytest.raises((TypeError, ValueError)):
        SemanticBudgetSpec(max_cost_usd=value, pricing_version=PRICE_VERSION)


def test_reservation_uses_exact_noncached_worst_case_pricing_and_canonical_strings():
    from plexus.optimization.semantic_budget import SemanticBudgetLedger

    ledger = SemanticBudgetLedger(run_key="run-1", spec=_spec())
    reservation = ledger.reserve(_plan())

    # 1,000 input tokens at $0.250/M + 100 output tokens at $2.000/M.
    assert reservation["reserved_usd"] == "0.00045"
    assert ledger.summary() == {
        "max_cost_usd": "1",
        "settled_usd": "0",
        "held_usd": "0.00045",
        "available_usd": "0.99955",
        "reservation_count": 1,
        "settled_count": 0,
        "outcome_unknown_count": 0,
    }
    assert all(not isinstance(value, float) for value in ledger.to_dict().values())


def test_boundary_equality_is_authorized_but_one_smallest_exact_excess_is_rejected():
    from plexus.optimization.semantic_budget import (
        SemanticBudgetExceeded,
        SemanticBudgetLedger,
    )

    exact = SemanticBudgetLedger(run_key="run-1", spec=_spec("0.00045"))
    exact.reserve(_plan())
    assert exact.summary()["available_usd"] == "0"

    insufficient = SemanticBudgetLedger(run_key="run-1", spec=_spec("0.000449999"))
    with pytest.raises(SemanticBudgetExceeded):
        insufficient.reserve(_plan())

    zero = SemanticBudgetLedger(run_key="run-1", spec=_spec("0"))
    assert zero.summary()["available_usd"] == "0"
    with pytest.raises(SemanticBudgetExceeded):
        zero.reserve(_plan())


def test_settlement_reconciles_actual_cached_usage_and_releases_the_difference():
    from plexus.optimization.semantic_budget import SemanticBudgetLedger, SemanticUsage

    ledger = SemanticBudgetLedger(run_key="run-1", spec=_spec())
    reservation = ledger.reserve(_plan())
    settled = ledger.settle(
        reservation["reservation_id"],
        SemanticUsage(
            input_tokens=800,
            cached_input_tokens=300,
            output_tokens=40,
            provider_request_id="req-1",
        ),
    )

    # 500 uncached input + 300 cached input + 40 output tokens.
    assert settled["actual_cost_usd"] == "0.0002125"
    assert ledger.summary()["settled_usd"] == "0.0002125"
    assert ledger.summary()["held_usd"] == "0"
    assert ledger.summary()["available_usd"] == "0.9997875"


def test_unknown_outcome_retains_full_reservation_and_precontact_cancellation_releases_it():
    from plexus.optimization.semantic_budget import SemanticBudgetLedger

    ledger = SemanticBudgetLedger(run_key="run-1", spec=_spec())
    unknown = ledger.reserve(_plan(score_id="unknown"))
    cancelled = ledger.reserve(_plan(score_id="cancelled"))

    ledger.mark_outcome_unknown(unknown["reservation_id"], reason="transport closed")
    ledger.cancel_pre_contact(cancelled["reservation_id"], reason="socket never opened")

    assert ledger.get(unknown["reservation_id"])["status"] == "outcome_unknown"
    assert ledger.get(cancelled["reservation_id"])["status"] == "cancelled_pre_contact"
    assert ledger.summary()["held_usd"] == unknown["reserved_usd"]
    assert ledger.summary()["outcome_unknown_count"] == 1


def test_replay_is_idempotent_and_cannot_enlarge_or_double_charge():
    from plexus.optimization.semantic_budget import (
        SemanticBudgetConflict,
        SemanticBudgetLedger,
        SemanticUsage,
    )

    ledger = SemanticBudgetLedger(run_key="run-1", spec=_spec())
    plan = _plan()
    first = ledger.reserve(plan)
    replay = ledger.reserve(plan)
    assert replay == first
    assert ledger.summary()["reservation_count"] == 1
    replay["plan"]["max_output_tokens"] = 999
    assert ledger.get(first["reservation_id"])["plan"]["max_output_tokens"] == 100

    with pytest.raises(SemanticBudgetConflict):
        ledger.reserve(_plan(max_output_tokens=101))

    usage = SemanticUsage(input_tokens=100, output_tokens=10, provider_request_id="req-1")
    settled = ledger.settle(first["reservation_id"], usage)
    assert ledger.settle(first["reservation_id"], usage) == settled
    with pytest.raises(SemanticBudgetConflict):
        ledger.settle(
            first["reservation_id"],
            SemanticUsage(input_tokens=101, output_tokens=10, provider_request_id="req-1"),
        )

    restored = SemanticBudgetLedger.from_dict(ledger.to_dict(), expected_spec=_spec())
    assert restored.to_dict() == ledger.to_dict()
    assert restored.reserve(plan) == settled
    with pytest.raises(SemanticBudgetConflict):
        SemanticBudgetLedger.from_dict(
            ledger.to_dict(), expected_spec=_spec("2")
        )


def test_multiple_targets_share_one_run_level_budget():
    from plexus.optimization.semantic_budget import SemanticBudgetExceeded, SemanticBudgetLedger

    ledger = SemanticBudgetLedger(run_key="run-1", spec=_spec("0.0009"))
    ledger.reserve(_plan(score_id="one"))
    ledger.reserve(_plan(score_id="two"))

    assert ledger.summary()["held_usd"] == "0.0009"
    with pytest.raises(SemanticBudgetExceeded):
        ledger.reserve(_plan(score_id="three"))


def test_attempts_and_usage_are_bounded_and_invalid_usage_keeps_the_reservation_held():
    from plexus.optimization.semantic_budget import (
        SemanticBudgetLedger,
        SemanticCallPlan,
        SemanticUsage,
    )

    with pytest.raises(ValueError):
        SemanticCallPlan(
            run_key="run-1",
            target_id="target",
            call_site="site",
            attempt=3,
            max_attempts=2,
            provider=PROVIDER,
            model=MODEL,
            pricing_version=PRICE_VERSION,
            max_input_tokens=100,
            max_output_tokens=10,
        )

    ledger = SemanticBudgetLedger(run_key="run-1", spec=_spec())
    reservation = ledger.reserve(_plan())
    with pytest.raises(ValueError):
        ledger.settle(
            reservation["reservation_id"],
            SemanticUsage(input_tokens=1_001, output_tokens=10),
        )
    assert ledger.get(reservation["reservation_id"])["status"] == "reserved"


@pytest.mark.parametrize(
    ("transition", "reason_field", "corruption"),
    [
        ("cancel_pre_contact", "cancellation_reason", "missing"),
        ("cancel_pre_contact", "cancellation_reason", "blank"),
        ("mark_outcome_unknown", "outcome_unknown_reason", "missing"),
        ("mark_outcome_unknown", "outcome_unknown_reason", "blank"),
    ],
)
def test_ledger_load_rejects_evidence_free_terminal_budget_states(
    transition, reason_field, corruption
):
    from plexus.optimization.semantic_budget import (
        SemanticBudgetConflict,
        SemanticBudgetLedger,
    )

    ledger = SemanticBudgetLedger(run_key="run-1", spec=_spec())
    reservation = ledger.reserve(_plan())
    getattr(ledger, transition)(reservation["reservation_id"], reason="evidence")
    durable_ledger = ledger.to_dict()
    if corruption == "missing":
        durable_ledger["entries"][0].pop(reason_field)
    else:
        durable_ledger["entries"][0][reason_field] = ""

    with pytest.raises(SemanticBudgetConflict, match=reason_field):
        SemanticBudgetLedger.from_dict(durable_ledger, expected_spec=_spec())


def test_portfolio_run_identity_freezes_the_semantic_budget_and_pricing_version():
    from plexus.optimization.portfolio_run import _run_key, _run_spec
    from plexus.optimization.semantic_budget import UnknownSemanticPricing

    base = {
        "account_id": "account-1",
        "scope": {},
        "semantic_budget": {
            "schema_version": "semantic-budget-v1",
            "max_cost_usd": "1",
            "pricing_version": PRICE_VERSION,
        },
    }
    changed_budget = {
        **base,
        "semantic_budget": {**base["semantic_budget"], "max_cost_usd": "2"},
    }
    changed_price = {
        **base,
        "semantic_budget": {
            **base["semantic_budget"],
            "pricing_version": "openai-future-v2",
        },
    }

    run_key = _run_key(base)
    assert run_key != _run_key(changed_budget)
    assert run_key == _run_key({
        **base,
        "semantic_budget": {**base["semantic_budget"], "max_cost_usd": "1.00"},
    })
    with pytest.raises(UnknownSemanticPricing):
        _run_key(changed_price)
    assert _run_spec(base, account_id="account-1", run_key=run_key)[
        "semantic_budget"
    ] == base["semantic_budget"]


def test_stakeholder_budget_evidence_reconciles_decimal_spend_and_hides_call_payloads():
    from plexus.optimization.semantic_budget import (
        SemanticBudgetLedger,
        SemanticUsage,
        stakeholder_budget_evidence,
    )

    ledger = SemanticBudgetLedger(run_key="run-1", spec=_spec())
    settled = ledger.reserve(_plan(target_id="scorecard-a:score-a", call_site="rubric_consistency"))
    ledger.settle(
        settled["reservation_id"],
        SemanticUsage(input_tokens=100, output_tokens=10, provider_request_id="req-1"),
        replay_payload={"version": 1, "kind": "plexus-direct-response", "output_text": "private"},
    )
    unknown = ledger.reserve(_plan(target_id="scorecard-b:score-b", call_site="sme_question_gate"))
    ledger.mark_outcome_unknown(unknown["reservation_id"], reason="provider timeout")
    cancelled = ledger.reserve(_plan(target_id="scorecard-c:score-c", call_site="rubric_consistency"))
    ledger.cancel_pre_contact(cancelled["reservation_id"], reason="run stopped")
    ledger.reserve(_plan(target_id="scorecard-d:score-d", call_site="rubric_consistency"))

    evidence = stakeholder_budget_evidence(
        ledger.to_dict(), evidence_reference="semantic-budget-ledger:r000007"
    )

    assert evidence["authorized_max_usd"] == "1"
    assert evidence["settled_actual_usd"] != "0"
    assert evidence["held_reserved_usd"] != "0"
    assert evidence["policy_version"] == "semantic-budget-policy-v1"
    assert evidence["budget_spec_schema_version"] == "semantic-budget-v1"
    assert evidence["ledger_schema_version"] == "semantic-budget-ledger-v1"
    assert evidence["provider"] == "openai"
    assert evidence["model"] == "gpt-5-mini-2025-08-07"
    assert evidence["pricing_version"] == "openai-2025-08-07-v1"
    assert evidence["available_usd"] == "0.999055"
    assert evidence["reservation_count"] == 4
    assert evidence["reserved_count"] == 1
    assert evidence["settled_count"] == 1
    assert evidence["unknown_count"] == 1
    assert evidence["cancelled_count"] == 1
    assert evidence["target_count"] == 4
    assert evidence["call_site_coverage"] == [
        {"call_site": "rubric_consistency", "count": 3},
        {"call_site": "sme_question_gate", "count": 1},
    ]
    assert evidence["evidence_reference"] == "semantic-budget-ledger:r000007"
    assert len(evidence["evidence_digest"]) == 64
    assert evidence["reservation_count"] == sum(
        evidence[key]
        for key in ("reserved_count", "settled_count", "unknown_count", "cancelled_count")
    )
    assert "private" not in str(evidence)
    assert "scorecard-a" not in str(evidence)
