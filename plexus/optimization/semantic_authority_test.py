from __future__ import annotations

from copy import deepcopy

import pytest

from plexus.optimization.semantic_authority import (
    SEMANTIC_MODEL,
    SemanticAuthorityError,
    SemanticAuthorityPublicationError,
    SemanticBudgetCoordinator,
    SemanticReplayBlocked,
    semantic_budget_spec,
)
from plexus.optimization.semantic_budget import SemanticBudgetConflict, SemanticUsage


class _Report:
    def __init__(self):
        self.value = None
        self.commits = []

    def load_semantic_budget_ledger(self):
        return deepcopy(self.value)

    def persist_semantic_budget_ledger(self, value):
        self.value = deepcopy(value)
        self.commits.append(deepcopy(value))


def _coordinator(report=None):
    report = report or _Report()
    coordinator = SemanticBudgetCoordinator.start_or_resume(
        report_service=report,
        run_key="run-1",
        spec=semantic_budget_spec("1"),
    )
    return coordinator, report


def test_load_and_commit_failures_have_specific_publication_type_but_missing_authority_does_not():
    class LoadFailure(_Report):
        def load_semantic_budget_ledger(self):
            raise RuntimeError("contradictory budget exhausted prose")

    class CommitFailure(_Report):
        def persist_semantic_budget_ledger(self, value):
            raise RuntimeError("contradictory outcome unknown prose")

    with pytest.raises(SemanticAuthorityPublicationError):
        _coordinator(LoadFailure())
    with pytest.raises(SemanticAuthorityPublicationError):
        _coordinator(CommitFailure())
    with pytest.raises(SemanticAuthorityError) as exc_info:
        SemanticBudgetCoordinator.start_or_resume(
            report_service=object(), run_key="run-1", spec=semantic_budget_spec("1")
        )
    assert not isinstance(exc_info.value, SemanticAuthorityPublicationError)


def test_reservation_commit_failure_uses_specific_publication_type():
    coordinator, report = _coordinator()

    def fail_commit(_value):
        raise RuntimeError("misleading insufficient remaining budget prose")

    coordinator._persist = fail_commit
    view = coordinator.view(target_id="a", call_site="direct", max_attempts=1)
    plan = view.direct_plan(
        attempt=1, max_input_tokens=10, max_output_tokens=2,
        request_payload={"prompt": "test"},
    )

    with pytest.raises(SemanticAuthorityPublicationError):
        view.reserve_direct(plan)
    assert report.value is not None


def test_report_resume_reuses_settled_tactus_replay_without_contact_or_double_charge():
    from tactus.protocols.model_attempt import (
        ModelAttemptOutcome,
        ModelAttemptPlan,
        ModelAttemptUsage,
    )

    coordinator, report = _coordinator()
    authority = coordinator.view(target_id="card:score", call_site="sme", max_attempts=2)
    plan = ModelAttemptPlan(
        call_id="call-1",
        attempt_id="call-1:1",
        attempt_number=1,
        max_attempts=2,
        provider="openai",
        model=SEMANTIC_MODEL,
        max_input_tokens=100,
        max_output_tokens=10,
        request_hash="request-a",
    )
    reservation = authority.reserve(plan)
    assert reservation.status == "approved"
    authority.settle(ModelAttemptOutcome(
        plan=plan,
        reservation_id=reservation.reservation_id,
        status="succeeded",
        usage=ModelAttemptUsage(input_tokens=12, output_tokens=3, total_tokens=15, cached_tokens=2),
        provider_request_id="req-1",
        replay_payload={
            "version": 1,
            "kind": "prediction",
            "fields": {"text": "settled"},
            "typed_fields": {},
        },
    ))
    spent = coordinator.ledger.summary()["settled_usd"]

    resumed = SemanticBudgetCoordinator.start_or_resume(
        report_service=report,
        run_key="run-1",
        spec=semantic_budget_spec("1"),
    )
    replay = resumed.view(
        target_id="card:score", call_site="sme", max_attempts=2
    ).reserve(plan)

    assert replay.status == "replay"
    assert replay.replay_payload["fields"]["text"] == "settled"
    assert resumed.ledger.summary()["settled_usd"] == spent
    assert len(report.commits) == 3  # declaration, reservation, settlement


def test_tactus_changed_request_hash_conflicts_and_reserved_or_unknown_resume_rejects():
    from tactus.protocols.model_attempt import ModelAttemptPlan

    coordinator, _ = _coordinator()
    authority = coordinator.view(target_id="card:score", call_site="sme", max_attempts=2)
    base = dict(
        call_id="call-1", attempt_id="call-1:1", attempt_number=1,
        max_attempts=2, provider="openai", model=SEMANTIC_MODEL,
        max_input_tokens=100, max_output_tokens=10,
    )
    plan = ModelAttemptPlan(**base, request_hash="request-a")
    assert authority.reserve(plan).status == "approved"
    assert authority.reserve(plan).status == "rejected"
    changed_identity = {
        **base,
        "call_id": "call-from-changed-request",
        "attempt_id": "call-from-changed-request:1",
    }
    with pytest.raises(SemanticBudgetConflict):
        authority.reserve(ModelAttemptPlan(**changed_identity, request_hash="request-b"))

    with pytest.raises(Exception, match="unauthorized model"):
        authority.reserve(ModelAttemptPlan(
            **{**base, "model": "gpt-5-mini"}, request_hash="request-a"
        ))


def test_aggregate_cap_is_shared_across_target_and_call_site_views_at_exact_boundary():
    report = _Report()
    coordinator = SemanticBudgetCoordinator.start_or_resume(
        report_service=report,
        run_key="run-1",
        spec=semantic_budget_spec("0.00009"),
    )
    first = coordinator.view(target_id="a", call_site="direct", max_attempts=1)
    second = coordinator.view(target_id="b", call_site="sme", max_attempts=1)
    first.reserve_direct(first.direct_plan(
        attempt=1, max_input_tokens=200, max_output_tokens=20,
        request_payload={"prompt": "a"},
    ))
    with pytest.raises(Exception, match="exceeds the frozen run budget"):
        second.reserve_direct(second.direct_plan(
            attempt=1, max_input_tokens=1, max_output_tokens=1,
            request_payload={"prompt": "b"},
        ))


def test_settled_direct_attempt_replays_versioned_output_envelope():
    coordinator, report = _coordinator()
    view = coordinator.view(target_id="a", call_site="direct", max_attempts=2)
    plan = view.direct_plan(
        attempt=1, max_input_tokens=100, max_output_tokens=10,
        request_payload={"prompt": "exact"},
    )
    decision = view.reserve_direct(plan)
    view.settle_direct(
        decision.reservation_id,
        SemanticUsage(input_tokens=8, output_tokens=2, provider_request_id="req-direct"),
        output_text='{"status":"consistent","paragraph":"ok"}',
    )
    resumed = SemanticBudgetCoordinator.start_or_resume(
        report_service=report, run_key="run-1", spec=semantic_budget_spec("1")
    )
    replay = resumed.view(target_id="a", call_site="direct", max_attempts=2).reserve_direct(plan)
    assert replay.status == "replay"
    assert replay.replay_payload["kind"] == "plexus-direct-response"
