"""Orchestrate one durable, human-governed optimization portfolio run.

This module intentionally contains no ranking, diagnosis, dispatch, or review
algorithm.  It composes the public ``optimization.*`` operations around one
living Report and translates a structured Human.review response into the exact
approved targets accepted by ``optimization.run``.

The Tactus procedure is the transport for ``human_review``.  Keeping the
orchestration transport-neutral makes checkpoint/replay deterministic and
prevents a second, slightly different portfolio decision path from emerging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from plexus.optimization.decision import (
    DEFAULT_EXECUTION_CANDIDATE_POLICY,
    EXECUTION_CANDIDATE_POLICY_PROMOTION_READY_PLUS_BOUNDED_DIAGNOSTIC,
    bounded_diagnostic_assessment_failure,
    normalize_execution_candidate_policy,
    validate_run_limits,
)
from plexus.optimization.run_report import (
    OptimizationRunIntegrityError,
    OptimizationRunPublicationError,
    OptimizationRunRetryablePublicationError,
)
from tactus.core.exceptions import ProcedureWaitingForHuman


MAX_APPROVAL_TARGETS = 5
MAX_BOUNDED_DIAGNOSTIC_TARGETS = 3
DEFAULT_MAX_EXECUTION_TARGETS: int | None = None
MAX_PRIORITY_DIAGNOSES = 10
DEFAULT_MAX_SEMANTIC_DIAGNOSES = 25
DIAGNOSIS_SCOPE_POLICY_VERSION = "portfolio-diagnosis-scope-v3"
SEMANTIC_FAILURE_CATEGORIES = frozenset({
    "budget_exhausted",
    "outcome_unknown",
    "authority_publication_failure",
})
OPTIMIZATION_APPROVAL_TTL_SECONDS = 24 * 60 * 60
RETRYABLE_PUBLICATION_RETRY_DELAY = timedelta(minutes=5)
_RETRYABLE_PUBLICATION_KEY = "optimization-report-publication"
_RETRYABLE_PUBLICATION_REASON = "retryable_report_publication"
_OPTIMIZER_CHILD_OBSERVED_PHASES = frozenset({
    "waiting", "running", "terminal", "dispatch_outcome_unknown",
})
OPTIMIZER_REVIEW_CONTRACT_VERSION = "portfolio-optimizer-review-v1"


def _retryable_publication_directive(*, now: datetime | None = None) -> dict[str, str]:
    """Return the only scheduled-retry contract exposed to the procedure.

    Exception text can contain transport/provider details, so it is never
    copied into a Tactus checkpoint, Task metadata, or stakeholder artifact.
    The key and reason are fixed; only the UTC due time advances.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    resume_at = (current.astimezone(timezone.utc) + RETRYABLE_PUBLICATION_RETRY_DELAY)
    return {
        "key": _RETRYABLE_PUBLICATION_KEY,
        "resume_at": resume_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "reason": _RETRYABLE_PUBLICATION_REASON,
    }


def drive_optimizer_child_launch(
    request: Mapping[str, Any],
    *,
    initial_state: Mapping[str, Any] | None,
    step: Callable[..., Mapping[str, Any]],
    publish: Callable[[Mapping[str, Any]], Any],
) -> dict[str, Any]:
    """Publish each child state before allowing its following mutation.

    ``step`` is deliberately Report-agnostic.  ``may_mutate`` is true only
    when this process successfully published the immediately preceding state;
    a replay starts read/reconcile-only until it reaches a newly published
    boundary.
    """
    if initial_state is None:
        state = dict(step(dict(request), None, may_mutate=False))
        publish(state)
        may_mutate = True
    else:
        state = dict(initial_state)
        may_mutate = False

    # A resumed observed state is refreshed once, without releasing again.
    if state.get("phase") in _OPTIMIZER_CHILD_OBSERVED_PHASES:
        observed = dict(step(dict(request), state, may_mutate=False))
        publish(observed)
        return observed

    for _transition in range(16):
        state = dict(step(dict(request), state, may_mutate=may_mutate))
        publish(state)
        if state.get("phase") in _OPTIMIZER_CHILD_OBSERVED_PHASES:
            return state
        may_mutate = True
    raise RuntimeError("optimizer child launch exceeded its bounded phase machine")


def _record_optimizer_child_wait_snapshot(
    dispatch_state: dict[str, Any],
    children: Sequence[Mapping[str, Any]],
    snapshots: Any,
) -> None:
    """Validate a Tactus wake snapshot against durable child identities.

    The snapshot proves why the parent was woken and is retained as evidence.
    It never replaces the dispatch backend's authoritative task readback.
    """
    if snapshots is None:
        return
    if not isinstance(snapshots, list) or not snapshots:
        raise OptimizationRunPublicationError(
            "Optimizer child wait snapshot is missing or malformed"
        )

    expected: dict[str, dict[str, Any]] = {}
    for child in children:
        launch_state = child.get("launch_state")
        if not isinstance(launch_state, Mapping) or launch_state.get("phase") not in {
            "waiting", "running",
        }:
            continue
        task_id = str(child.get("task_id") or "")
        procedure_id = str(child.get("procedure_id") or "")
        target = child.get("target")
        launch_spec = launch_state.get("launch_spec")
        identity = (
            str(launch_spec.get("identity") or "")
            if isinstance(launch_spec, Mapping)
            else ""
        )
        if (
            not identity
            or not task_id
            or not procedure_id
            or not isinstance(target, Mapping)
            or not str(target.get("scorecard_id") or "")
            or not str(target.get("score_id") or "")
        ):
            raise OptimizationRunPublicationError(
                "Durable optimizer child identity is incomplete"
            )
        expected[identity] = {
            "id": identity,
            "task_id": task_id,
            "procedure_id": procedure_id,
            "scorecard_id": str(target["scorecard_id"]),
            "score_id": str(target["score_id"]),
        }

    normalized: list[dict[str, Any]] = []
    actual: dict[str, dict[str, Any]] = {}
    for raw_snapshot in snapshots:
        if not isinstance(raw_snapshot, Mapping):
            raise OptimizationRunPublicationError(
                "Optimizer child wait snapshot is missing or malformed"
            )
        snapshot = dict(raw_snapshot)
        child_id = str(snapshot.get("id") or "")
        if (
            not child_id
            or not str(snapshot.get("task_id") or "")
            or not str(snapshot.get("procedure_id") or "")
            or not str(snapshot.get("scorecard_id") or "")
            or not str(snapshot.get("score_id") or "")
            or not isinstance(snapshot.get("terminal"), bool)
            or child_id in actual
        ):
            raise OptimizationRunPublicationError(
                "Optimizer child wait snapshot is missing or malformed"
            )
        actual[child_id] = snapshot
        normalized.append(snapshot)

    if set(actual) != set(expected):
        raise OptimizationRunPublicationError(
            "Optimizer child wait snapshot does not match durable optimizer children"
        )
    for child_id, identity in expected.items():
        snapshot = actual[child_id]
        if (
            snapshot.get("task_id") != identity["task_id"]
            or snapshot.get("procedure_id") != identity["procedure_id"]
            or snapshot.get("scorecard_id") != identity["scorecard_id"]
            or snapshot.get("score_id") != identity["score_id"]
        ):
            raise OptimizationRunPublicationError(
                "Optimizer child wait snapshot does not match durable optimizer children"
            )

    dispatch_state["last_wait_snapshot"] = normalized


@dataclass(frozen=True)
class PortfolioRunDependencies:
    """Transport adapters for the existing public optimization capabilities."""

    rank: Callable[[dict[str, Any]], Mapping[str, Any]]
    assess: Callable[[dict[str, Any]], Mapping[str, Any]]
    diagnose: Callable[[dict[str, Any]], Mapping[str, Any]]
    summary: Callable[[dict[str, Any]], Mapping[str, Any]]
    dispatch: Callable[[dict[str, Any]], Mapping[str, Any]]
    review: Callable[[dict[str, Any]], Mapping[str, Any]]
    report_service: Callable[[str, Mapping[str, Any]], Any]
    # Tactus Human.review receives this request verbatim. The ChatMessage HITL
    # adapter owns authorization and the atomic parent-response claim.
    human_review: Callable[[dict[str, Any]], Mapping[str, Any]]
    create_action: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None
    publish_update: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None
    supersede_action: Callable[[str, str], Mapping[str, Any]] | None = None
    # The living Report owns optimizer child launch authority.  Runtime
    # adapters supply a pure coordinator step plus a deterministic request
    # builder; standalone optimization.run never receives either capability.
    optimizer_child_step: Callable[..., Mapping[str, Any]] | None = None
    optimizer_child_request: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None
    diagnosis_preflight: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None


class OptimizationPortfolioRunner:
    """Run the safe, report-first portfolio lifecycle once or through replay.

    ``human_review`` may suspend through Tactus.  On replay, the Tactus
    checkpoint supplies the same accepted structured response, while the
    report service resumes the same deterministic run key and report URL.
    """

    def __init__(self, dependencies: PortfolioRunDependencies) -> None:
        self._dependencies = dependencies

    def run(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request = dict(request)
        account_id = _required_text(request, "account_id")
        execution_mode = _execution_mode(request.get("execution_mode"))
        execution_candidate_policy = normalize_execution_candidate_policy(
            request.get("execution_candidate_policy")
        )
        run_key = str(request.get("run_key") or _run_key(request))
        limits = dict(request.get("limits") or {
            key: request.get(key)
            for key in ("max_cost_usd", "max_samples", "max_iterations", "max_concurrency")
            if key in request
        })
        run_spec = _run_spec(request, account_id=account_id, run_key=run_key)
        service = self._dependencies.report_service(run_key, request)
        state: dict[str, Any] = {
            "account_id": account_id,
            "run_key": run_key,
            "run_spec": run_spec,
            "rank": None,
            "assessments": [],
            "diagnoses": [],
            "diagnosis_coverage": _pending_diagnosis_coverage(request),
            "approved_targets": [],
            "dispatch": None,
            "reviews": [],
            "actions": [],
            "approval_requests": [],
            "execution_mode": execution_mode,
            "execution_candidate_policy": execution_candidate_policy,
            "execution_decisions": _empty_execution_decisions(execution_mode),
            "promotion_candidates": [],
            "notification_failures": [],
        }

        try:
            report_state = service.start_or_resume(run_spec)
            report_id = getattr(getattr(report_state, "report", None), "id", None)
            if not report_id:
                raise RuntimeError("living report service did not return a Report ID")
            state["report_ref"] = {
                "system": "plexus",
                "kind": "report",
                "id": str(report_id),
                "relation": "optimization_run",
            }
            semantic_coordinator = None
            frozen_semantic_budget = run_spec.get("semantic_budget")
            if isinstance(frozen_semantic_budget, Mapping):
                from plexus.optimization.semantic_authority import (
                    SemanticBudgetCoordinator,
                )
                from plexus.optimization.semantic_budget import SemanticBudgetSpec

                semantic_coordinator = SemanticBudgetCoordinator.start_or_resume(
                    report_service=service,
                    run_key=run_key,
                    spec=SemanticBudgetSpec.from_dict(frozen_semantic_budget),
                )
                state["semantic_budget_evidence"] = _semantic_budget_evidence(
                    semantic_coordinator.ledger.to_dict()
                )
            checkpoint_loader = getattr(service, "load_latest_checkpoint", None)
            checkpoint = checkpoint_loader() if callable(checkpoint_loader) else None
            checkpoint_milestone: str | None = None
            if checkpoint is not None:
                _hydrate_durable_state(state, checkpoint)
                checkpoint_milestone = str(checkpoint.get("milestone") or "")
                if checkpoint_milestone == "finalization":
                    terminal_status = str(state.get("terminal_status") or "INCOMPLETE")
                    if (
                        terminal_status == "INCOMPLETE"
                        and (
                            _has_retryable_optimizer_review(state)
                            or _has_legacy_optimizer_review(state)
                        )
                    ):
                        # A prior finalization only recorded that exact-child
                        # review evidence was inconclusive. Re-enter at the
                        # review milestone so a later terminal indexed read
                        # can replace an inconclusive or legacy row; all
                        # current-version conclusive reviews stay closed.
                        checkpoint_milestone = "optimization_review"
                    else:
                        if checkpoint.get("task_terminal") is not True:
                            _finalize(service, terminal_status)
                        self._notify(
                            state,
                            event="completed",
                            milestone="COMPLETED",
                            title="Optimization portfolio run completed",
                            summary=(
                                f"Terminal state: "
                                f"{terminal_status.lower().replace('_', ' ')}."
                            ),
                        )
                        return self._result(terminal_status, state)
            else:
                self._publish(service, "started", state)
                self._notify(
                    state,
                    event="started",
                    milestone="STARTED",
                    title="Optimization portfolio analysis started",
                    summary="The living Report is available while exhaustive ranking proceeds.",
                )

            if _checkpoint_precedes(checkpoint_milestone, "ranking"):
                # ``optimization.rank`` owns exhaustive pagination and the
                # frozen feedback read.  Give that one execution a private,
                # report-only progress callback so the living Report remains
                # useful during its potentially long network-bound phases.
                # It is deliberately absent from the returned packet and
                # therefore cannot alter evidence or ranking semantics.
                def publish_ranking_progress(progress: Mapping[str, Any]) -> None:
                    payload = dict(progress)
                    service.publish_progress(
                        phase="ranking",
                        subphase=(
                            str(payload["subphase"])
                            if payload.get("subphase") is not None
                            else None
                        ),
                        current=int(payload.get("current") or 0),
                        total=(
                            int(payload["total"])
                            if payload.get("total") is not None
                            else None
                        ),
                        message=str(payload.get("message") or "Portfolio ranking is running."),
                        unit=str(payload.get("unit") or "scorecards"),
                        state=str(payload.get("state") or "active"),
                        elapsed_seconds=(
                            int(payload["elapsed_seconds"])
                            if payload.get("elapsed_seconds") is not None
                            else None
                        ),
                        next_checkpoint=(
                            str(payload["next_checkpoint"])
                            if payload.get("next_checkpoint") is not None
                            else None
                        ),
                        heartbeat_interval_seconds=(
                            int(payload["heartbeat_interval_seconds"])
                            if payload.get("heartbeat_interval_seconds") is not None
                            else None
                        ),
                    )

                rank_request = _with_persist_false(request)
                rank_request["_optimization_rank_progress"] = publish_ranking_progress
                rank = dict(self._dependencies.rank(rank_request))
                state["rank"] = rank
                self._publish(service, "ranking", state)
            else:
                rank = state.get("rank")
                if not isinstance(rank, Mapping):
                    raise OptimizationRunPublicationError(
                        "Durable ranking checkpoint is missing its rank packet"
                    )
                rank = dict(rank)
            if not _coverage_complete(rank):
                state["summary"] = self._summary(state)
                state["terminal_status"] = "INCOMPLETE"
                self._publish(service, "finalization", state)
                _finalize(service, "INCOMPLETE")
                return self._result("INCOMPLETE", state)

            ranked_rows = _ranked_rows(rank)
            assessment_total = len(ranked_rows)
            if _checkpoint_precedes(checkpoint_milestone, "assessment"):
                assessment_rows: list[dict[str, Any]] = []
                service.publish_progress(
                    phase="assessment",
                    current=0,
                    total=assessment_total,
                    message=f"Preparing to assess {assessment_total} ranked scores.",
                )
                for index, row in enumerate(ranked_rows, start=1):
                    scorecard_id, score_id = _exact_target(row)
                    assessment = dict(self._dependencies.assess({
                        "account_id": account_id,
                        "scorecard_id": scorecard_id,
                        "score_id": score_id,
                        "rank_evidence": rank,
                        "persist": False,
                    }))
                    # Names are presentation metadata from the frozen ranking.
                    # Preserve opaque IDs for every decision and mutation, but do
                    # not force humans to identify targets by those IDs.
                    if row.get("scorecard_name") and not assessment.get("scorecard_name"):
                        assessment["scorecard_name"] = row["scorecard_name"]
                    if row.get("score_name") and not assessment.get("score_name"):
                        assessment["score_name"] = row["score_name"]
                    assessment_rows.append(assessment)
                    if index % 10 == 0 or index == assessment_total:
                        scorecard_name = str(row.get("scorecard_name") or "this scorecard")
                        score_name = str(row.get("score_name") or "this score")
                        service.publish_progress(
                            phase="assessment",
                            current=index,
                            total=assessment_total,
                            message=(
                                f"Assessed {index} of {assessment_total} scores; latest: "
                                f"{scorecard_name} - {score_name}."
                            ),
                        )
            else:
                assessment_rows = [
                    dict(row) for row in state.get("assessments") or []
                    if isinstance(row, Mapping)
                ]
                if len(assessment_rows) != assessment_total:
                    raise OptimizationRunPublicationError(
                        "Durable assessment checkpoint does not cover every ranked score"
                    )

            # Ranking and assessment are deterministic and materially useful
            # on their own. Publish them before model-backed diagnosis so a
            # slow or failed semantic pass cannot hide completed evidence.
            state["assessments"] = assessment_rows
            diagnosis_targets, selected_diagnosis_coverage = _diagnosis_selection(
                ranked_rows,
                assessment_rows,
                max_semantic_diagnoses=_max_semantic_diagnoses(request),
            )
            if _checkpoint_precedes(checkpoint_milestone, "diagnosis"):
                diagnosis_coverage = selected_diagnosis_coverage
                state["diagnosis_coverage"] = diagnosis_coverage
            else:
                diagnosis_coverage = dict(state.get("diagnosis_coverage") or {})
            frozen_semantic_max = (
                Decimal(str(frozen_semantic_budget.get("max_cost_usd", "0")))
                if isinstance(frozen_semantic_budget, Mapping)
                else Decimal(0)
            )
            if diagnosis_coverage.get("scheduled_count", 0) > 0 and (
                semantic_coordinator is None or frozen_semantic_max <= 0
            ):
                diagnosis_coverage.setdefault("blockers", []).append(
                    "positive semantic diagnosis scope requires a positive frozen max_semantic_cost_usd"
                )
            if (
                _checkpoint_precedes(checkpoint_milestone, "diagnosis")
                and int(diagnosis_coverage.get("scheduled_count") or 0) > 0
                and not diagnosis_coverage.get("blockers")
                and self._dependencies.diagnosis_preflight is not None
            ):
                try:
                    preflight = self._dependencies.diagnosis_preflight({
                        "account_id": account_id,
                        "target_count": len(diagnosis_targets),
                        "targets": [
                            {
                                "scorecard_id": _exact_target(row)[0],
                                "score_id": _exact_target(row)[1],
                            }
                            for row, _assessment in diagnosis_targets
                        ],
                    })
                    preflight = (
                        dict(preflight) if isinstance(preflight, Mapping) else {}
                    )
                except Exception:
                    preflight = {
                        "complete": False,
                        "failure_category": "required_evidence_unavailable",
                        "message": (
                            "Required semantic evidence authority is unavailable; "
                            "repair worker authorization and resume."
                        ),
                    }
                if preflight.get("complete") is not True:
                    failure_category = str(
                        preflight.get("failure_category")
                        or "required_evidence_unavailable"
                    )
                    blocker = str(
                        preflight.get("message")
                        or (
                            "Required semantic evidence authority is unavailable; "
                            "repair worker authorization and resume."
                        )
                    )
                    diagnosis_coverage["prerequisite_failure_count"] = 1
                    diagnosis_coverage["failure_category"] = failure_category
                    diagnosis_coverage["selected_scope_complete"] = False
                    diagnosis_coverage.setdefault("blockers", []).append(blocker)
            if _checkpoint_precedes(checkpoint_milestone, "assessment"):
                self._publish(service, "assessment", state)

            if diagnosis_coverage["blockers"]:
                self._publish(service, "diagnosis", state)
                state["summary"] = self._summary(state)
                state["terminal_status"] = "INCOMPLETE"
                self._publish(service, "finalization", state)
                _finalize(service, "INCOMPLETE")
                return self._result("INCOMPLETE", state)

            diagnosis_checkpoint_is_new = _checkpoint_precedes(
                checkpoint_milestone, "diagnosis"
            )
            existing_diagnosis_rows = [
                dict(row) for row in state.get("diagnoses") or []
                if isinstance(row, Mapping)
            ]
            if not diagnosis_checkpoint_is_new and len(existing_diagnosis_rows) != (
                int(diagnosis_coverage.get("completed_count") or 0)
                + int(diagnosis_coverage.get("failed_count") or 0)
                + int(diagnosis_coverage.get("incomplete_count") or 0)
            ):
                raise OptimizationRunPublicationError(
                    "Durable diagnosis checkpoint has inconsistent completion evidence"
                )
            diagnosed_keys = {
                key for key in (_target_key(row) for row in existing_diagnosis_rows)
                if key is not None
            }
            remaining_diagnosis_targets = [
                (row, assessment)
                for row, assessment in diagnosis_targets
                if _target_key(assessment) not in diagnosed_keys
            ]
            resume_partial_diagnosis = (
                checkpoint_milestone == "diagnosis"
                and not diagnosis_checkpoint_is_new
                and int(diagnosis_coverage.get("failed_count") or 0) == 0
                and not diagnosis_coverage.get("blockers")
                and bool(remaining_diagnosis_targets)
                and not any(
                    _normalize_semantic_failure_category(row)
                    in SEMANTIC_FAILURE_CATEGORIES
                    for row in existing_diagnosis_rows
                )
            )
            if diagnosis_checkpoint_is_new or resume_partial_diagnosis:
                diagnosis_rows = (
                    [] if diagnosis_checkpoint_is_new else existing_diagnosis_rows
                )
                pending_diagnosis_targets = (
                    diagnosis_targets
                    if diagnosis_checkpoint_is_new
                    else remaining_diagnosis_targets
                )
                if resume_partial_diagnosis:
                    diagnosis_coverage["deferred_after_incomplete_count"] = 0
                diagnosis_total = assessment_total + len(diagnosis_targets)
                service.publish_progress(
                    phase="diagnosis",
                    current=assessment_total + len(diagnosis_rows),
                    total=diagnosis_total,
                    message=(
                        f"Starting semantic diagnosis for {len(pending_diagnosis_targets)} "
                        "remaining selected scores."
                    ),
                )
                prior_diagnosis_count = len(diagnosis_rows)
                for pending_index, (row, assessment) in enumerate(
                    pending_diagnosis_targets, start=1
                ):
                    diagnosis_index = prior_diagnosis_count + pending_index
                    scorecard_id, score_id = _exact_target(row)
                    try:
                        diagnosis = dict(self._dependencies.diagnose({
                            "account_id": account_id,
                            "scorecard_id": scorecard_id,
                            "score_id": score_id,
                            "assessment": assessment,
                            "assessment_packet": assessment,
                            "window": rank.get("window") or {},
                            "feedback_watermark": assessment.get("feedback_watermark"),
                            "_semantic_budget_coordinator": semantic_coordinator,
                            "persist": False,
                        }))
                    except Exception as exc:
                        failure_category = _semantic_exception_category(exc)
                        remaining_count = (
                            len(pending_diagnosis_targets) - pending_index
                        )
                        diagnosis_coverage["failed_count"] += 1
                        diagnosis_coverage["selected_scope_complete"] = False
                        diagnosis_coverage.setdefault("failures", []).append(str(exc))
                        failure_coverage = {
                            "complete": False,
                            "failures": [str(exc)],
                        }
                        failure_row = {
                            "scorecard_id": scorecard_id,
                            "score_id": score_id,
                            "scope": {"scorecard_id": scorecard_id, "score_id": score_id},
                            "coverage": failure_coverage,
                            "states": {"readiness": "incomplete", "optimization": "incomplete"},
                            "status": failure_category,
                        }
                        if failure_category in SEMANTIC_FAILURE_CATEGORIES:
                            failure_row["semantic_failure_category"] = failure_category
                            failure_coverage["semantic_failure_category"] = failure_category
                        diagnosis_rows.append(failure_row)
                        state["diagnoses"] = diagnosis_rows
                        if failure_category == "budget_exhausted":
                            diagnosis_coverage["budget_exhausted_count"] += 1
                            diagnosis_coverage["deferred_by_budget_count"] += remaining_count
                        else:
                            diagnosis_coverage["deferred_after_failure_count"] += remaining_count
                            if failure_category == "outcome_unknown":
                                diagnosis_coverage["outcome_unknown_count"] += 1
                            elif failure_category == "authority_publication_failure":
                                diagnosis_coverage["authority_publication_failure_count"] += 1
                        _reconcile_aggregate_semantic_failure_category(
                            diagnosis_coverage
                        )
                        break
                    if assessment.get("scorecard_name") and not diagnosis.get("scorecard_name"):
                        diagnosis["scorecard_name"] = assessment["scorecard_name"]
                    if assessment.get("score_name") and not diagnosis.get("score_name"):
                        diagnosis["score_name"] = assessment["score_name"]
                    semantic_failure_category = _normalize_semantic_failure_category(
                        diagnosis
                    )
                    if semantic_failure_category in SEMANTIC_FAILURE_CATEGORIES:
                        diagnosis["semantic_failure_category"] = semantic_failure_category
                        coverage = diagnosis.get("coverage")
                        coverage = dict(coverage) if isinstance(coverage, Mapping) else {}
                        coverage["semantic_failure_category"] = semantic_failure_category
                        diagnosis["coverage"] = coverage
                    diagnosis_rows.append(diagnosis)
                    if _diagnosis_result_incomplete(diagnosis):
                        if semantic_failure_category == "budget_exhausted":
                            diagnosis_coverage["budget_exhausted_count"] += 1
                        elif semantic_failure_category == "outcome_unknown":
                            diagnosis_coverage["outcome_unknown_count"] += 1
                        elif semantic_failure_category == "authority_publication_failure":
                            diagnosis_coverage["authority_publication_failure_count"] += 1
                        _reconcile_aggregate_semantic_failure_category(
                            diagnosis_coverage
                        )
                        diagnosis_coverage["incomplete_count"] = (
                            int(diagnosis_coverage.get("incomplete_count") or 0) + 1
                        )
                        diagnosis_coverage["selected_scope_complete"] = False
                        state["diagnoses"] = diagnosis_rows
                        service.publish_progress(
                            phase="diagnosis",
                            current=assessment_total + diagnosis_index,
                            total=diagnosis_total,
                            message=(
                                f"Semantic diagnosis {diagnosis_index} of "
                                f"{len(diagnosis_targets)} returned incomplete evidence."
                            ),
                        )
                        if semantic_failure_category in SEMANTIC_FAILURE_CATEGORIES:
                            # These categories make the safety or cost of any
                            # subsequent provider contact unknowable. Preserve
                            # the remaining exact targets without spending.
                            diagnosis_coverage["deferred_after_incomplete_count"] = (
                                len(pending_diagnosis_targets) - pending_index
                            )
                            break
                        # An ordinary inconclusive result is target-local. It
                        # cannot make this target ready, but it must not veto
                        # independent siblings while evidence and budget remain.
                        continue
                    diagnosis_coverage["completed_count"] += 1
                    service.publish_progress(
                        phase="diagnosis",
                        current=assessment_total + diagnosis_index,
                        total=diagnosis_total,
                        message=(
                            f"Completed semantic diagnosis {diagnosis_index} of "
                            f"{len(diagnosis_targets)}: "
                            f"{row.get('scorecard_name') or 'Scorecard'} - "
                            f"{row.get('score_name') or 'Score'}."
                        ),
                    )

                state["diagnoses"] = diagnosis_rows
                diagnosis_coverage["scheduled_scope_complete"] = (
                    diagnosis_coverage["completed_count"] == diagnosis_coverage["scheduled_count"]
                    and diagnosis_coverage["failed_count"] == 0
                    and int(diagnosis_coverage.get("incomplete_count") or 0) == 0
                )
                diagnosis_coverage["selected_scope_complete"] = (
                    diagnosis_coverage["scheduled_scope_complete"]
                    and diagnosis_coverage["deferred_by_cap_count"] == 0
                )
                if (
                    int(diagnosis_coverage.get("failed_count") or 0) > 0
                    or int(diagnosis_coverage.get("incomplete_count") or 0) > 0
                ):
                    state["summary"] = self._summary(state)
                self._publish(service, "diagnosis", state)
                if (
                    diagnosis_coverage["scheduled_scope_complete"]
                    and diagnosis_coverage["selected_scope_complete"]
                    and diagnosis_coverage["failed_count"] == 0
                ):
                    self._notify(
                        state,
                        event="analysis_ready",
                        milestone="COMPLETED",
                        title="Optimization portfolio analysis is ready",
                        summary=(
                            f"Assessed {len(assessment_rows)} ranked scores and completed "
                            f"{diagnosis_coverage['completed_count']} selected semantic diagnoses."
                        ),
                    )
            else:
                diagnosis_rows = existing_diagnosis_rows
                if not isinstance(state.get("summary"), Mapping):
                    state["summary"] = self._summary(state)

            if _checkpoint_precedes(checkpoint_milestone, "approval"):
                action_rows = _non_launch_actions(diagnosis_rows)
                if self._dependencies.create_action is not None:
                    action_rows = [
                        _recorded_action(
                            action,
                            self._dependencies.create_action(_action_request_for_finding(
                                action, account_id=account_id, run_key=run_key,
                                report_ref=state["report_ref"],
                            )),
                        )
                        for action in action_rows
                    ]
            else:
                action_rows = [
                    dict(row) for row in state.get("actions") or []
                    if isinstance(row, Mapping)
                ]
            independently_ready, execution_decisions = _execution_selection(
                execution_mode,
                execution_candidate_policy,
                assessment_rows,
                diagnosis_rows,
                ranked_rows=ranked_rows,
                max_samples=limits.get("max_samples"),
            )
            if execution_mode == "automatic":
                # A deferred sibling remains visible in execution_decisions but
                # cannot veto an independently complete, fresh candidate.
                ready = independently_ready
            elif (
                diagnosis_coverage.get("selected_scope_complete") is True
                and int(diagnosis_coverage.get("failed_count") or 0) == 0
            ):
                ready = independently_ready
            else:
                ready = []
                for target in independently_ready:
                    _append_execution_rejection(
                        execution_decisions,
                        {"reason": "portfolio_diagnosis_incomplete"},
                        fallback_targets=[target],
                    )
            max_execution_targets = _max_execution_targets(request)
            if execution_mode == "automatic":
                # Freshness is checked by dispatch.  Do not spend the frozen
                # accepted-target slots until that check succeeds.
                ready = list(ready)
            else:
                # Backfill cannot safely cross a human approval boundary: a
                # later candidate has not been approved.  Retain the existing
                # approval-required selection semantics, including the
                # bounded-diagnostic accepted-target policy.
                ready, deferred = _limit_execution_candidates(
                    ready, max_execution_targets=max_execution_targets,
                )
                for rejection, targets in deferred:
                    _append_execution_rejection(
                        execution_decisions, rejection, fallback_targets=targets,
                    )
            execution_decisions["selected_targets"] = [
                {
                    **_execution_target_row(target, reason="eligible_for_launch"),
                    "launch_status": "selected",
                }
                for target in ready
            ]
            execution_decisions["selected_count"] = len(ready)
            state["execution_decisions"] = execution_decisions
            batches = [ready[index:index + MAX_APPROVAL_TARGETS] for index in range(0, len(ready), MAX_APPROVAL_TARGETS)]
            all_review_requests = [
                _approval_request(
                    run_key=run_key,
                    account_id=account_id,
                    batch_number=index,
                    targets=batch,
                    report_ref=state["report_ref"],
                    limits=limits,
                    portfolio_evidence_fingerprint=_portfolio_evidence_fingerprint(state),
                )
                for index, batch in enumerate(batches, start=1)
            ]
            # Publish the pending decisions before invoking Human.review.  A
            # real Tactus adapter suspends at that call, so publishing only
            # afterward would leave the living Report claiming diagnosis was
            # still in progress for the entire human wait.
            if _checkpoint_precedes(checkpoint_milestone, "approval"):
                review_requests = list(all_review_requests)
                if execution_mode == "automatic":
                    review_requests = []
                state["approval_requests"] = list(review_requests)
                state["actions"] = action_rows
                self._publish(service, "approval", state)
            else:
                persisted_requests = [
                    dict(row) for row in state.get("approval_requests") or []
                    if isinstance(row, Mapping)
                ]
                request_by_key = {
                    str(row.get("action_key") or ""): row for row in all_review_requests
                }
                review_requests = []
                for persisted in persisted_requests:
                    action_key = str(persisted.get("action_key") or "")
                    if action_key not in request_by_key:
                        raise OptimizationRunPublicationError(
                            "Durable approval checkpoint references an unknown target batch"
                        )
                    review_requests.append(request_by_key[action_key])
            if _checkpoint_precedes(checkpoint_milestone, "approval") and (action_rows or review_requests):
                self._notify(
                    state,
                    event="action_required",
                    milestone="APPROVAL_NEEDED",
                    title="Optimization portfolio decisions need attention",
                    summary=(
                        f"{len(action_rows)} advisory actions and "
                        f"{len(review_requests)} optimization approval batches are open."
                    ),
                )

            submitted_approvals = request.get("approval_responses")
            has_submitted_approvals = "approval_responses" in request
            approvals: list[dict[str, Any]] = []
            pending_approval_requests: list[dict[str, Any]] = []
            batch_by_key = {
                request_row["action_key"]: batch
                for batch, request_row in zip(batches, all_review_requests)
            }
            if execution_mode == "automatic":
                approvals = list(ready)
            else:
                approvals = [
                    dict(row) for row in state.get("approved_targets") or []
                    if isinstance(row, Mapping)
                ]
                for review_request in review_requests:
                    batch = batch_by_key[review_request["action_key"]]
                    response = (
                        _bound_approval_response(review_request, submitted_approvals)
                        if has_submitted_approvals
                        else self._dependencies.human_review(review_request)
                    )
                    if not _response_resolves_batch(batch, response):
                        pending_approval_requests.append(review_request)
                    approvals.extend(_accepted_approval_targets(batch, response))
                    action_rows.append({
                        "kind": "optimization_approval",
                        "action_key": review_request["action_key"],
                        "target_count": len(batch),
                        "response": dict(response or {}),
                    })
            state["approval_requests"] = pending_approval_requests
            state["actions"] = action_rows
            # Automatic candidates are eligible for validation, not yet
            # accepted for launch.  Persist only validator-accepted targets
            # below so report/replay evidence never calls the whole pool
            # approved.
            if execution_mode != "automatic":
                state["approved_targets"] = list(approvals)
            elif not isinstance(state.get("dispatch"), Mapping):
                state["approved_targets"] = []
            if pending_approval_requests and len(pending_approval_requests) != len(review_requests):
                self._publish(service, "approval", state)

            # A Tactus procedure may deliberately request the first action,
            # checkpoint, and call us again with its authoritative response.
            # Keep this Report/Task running; treating an unanswered action as
            # terminal would prevent ordinary replay from resuming the same URL.
            unresolved_approval = bool(pending_approval_requests)
            if request.get("wait_for_human") is True and unresolved_approval:
                return self._result("WAITING_FOR_APPROVAL", state)

            persisted_dispatch = state.get("dispatch")
            if isinstance(persisted_dispatch, Mapping):
                dispatch_state = dict(persisted_dispatch)
                validation_batches = [
                    dict(row) for row in dispatch_state.get("batches") or []
                    if isinstance(row, Mapping)
                ]
                rejected = [
                    dict(row) for row in dispatch_state.get("rejected") or []
                    if isinstance(row, Mapping)
                ]
                children = [
                    dict(row) for row in dispatch_state.get("children") or []
                    if isinstance(row, Mapping)
                ]
                if execution_mode == "automatic":
                    approvals = [
                        dict(row) for row in state.get("approved_targets") or []
                        if isinstance(row, Mapping)
                    ]
                    execution_decisions["selected_targets"] = [
                        {
                            **_execution_target_row(target, reason="eligible_for_launch"),
                            "launch_status": "selected",
                        }
                        for target in approvals
                    ]
                    execution_decisions["selected_count"] = len(approvals)
            elif approvals:
                validation_batches = []
                rejected = []
                accepted_for_launch: list[dict[str, Any]] = []
                limit_validation = validate_run_limits(limits)
                if not limit_validation["valid"]:
                    rejection = {
                        "reason": "invalid_run_limits",
                        "invalid_fields": list(limit_validation["invalid_fields"]),
                    }
                    validation_batches.append({
                        "accepted": False,
                        "accepted_targets": [],
                        "rejected": [rejection],
                        "run_limits": limit_validation,
                        "primary_next_action": "provide_valid_run_limits",
                        "blockers": ["invalid_run_limits"],
                    })
                    rejected.append(rejection)
                    _append_execution_rejection(
                        execution_decisions, rejection, fallback_targets=approvals,
                    )
                else:
                    if execution_mode == "automatic":
                        candidates = list(approvals)
                        accepted_bounded_diagnostic_count = 0
                        for index, candidate in enumerate(candidates):
                            if (
                                max_execution_targets is not None
                                and len(accepted_for_launch) >= max_execution_targets
                            ):
                                _append_execution_rejection(
                                    execution_decisions,
                                    {"reason": "execution_target_limit"},
                                    fallback_targets=candidates[index:],
                                )
                                break
                            if (
                                candidate.get("candidate_kind") == "bounded_diagnostic"
                                and accepted_bounded_diagnostic_count
                                >= MAX_BOUNDED_DIAGNOSTIC_TARGETS
                            ):
                                _append_execution_rejection(
                                    execution_decisions,
                                    {"reason": "bounded_diagnostic_target_limit"},
                                    fallback_targets=[candidate],
                                )
                                continue
                            validation = dict(self._dependencies.dispatch({
                                "account_id": account_id,
                                # The launch adapter derives an idempotent child
                                # identity from this frozen parent-run key.  Never
                                # substitute a wall-clock retry identifier here.
                                "run_key": run_key,
                                "approved": True,
                                "execution_mode": execution_mode,
                                "execution_candidate_policy": execution_candidate_policy,
                                "authorization": {
                                    "mode": execution_mode,
                                    "source": "deterministic_policy",
                                },
                                # One deterministic target per validation makes
                                # a freshness rejection unambiguously backfill
                                # from the next evidence-ranked candidate.
                                "targets": [candidate],
                                "persist": False,
                                **limits,
                            }))
                            validation_batches.append(validation)
                            rejected.extend(
                                dict(item) for item in (validation.get("rejected") or [])
                                if isinstance(item, Mapping)
                            )
                            for item in validation.get("rejected") or []:
                                if isinstance(item, Mapping):
                                    _append_execution_rejection(
                                        execution_decisions, item, fallback_targets=[candidate],
                                    )
                            accepted = [
                                {**candidate, **dict(item)}
                                for item in (validation.get("accepted_targets") or [])
                                if isinstance(item, Mapping)
                                and _target_key(item) == _target_key(candidate)
                            ]
                            accepted_for_launch.extend(accepted)
                            accepted_bounded_diagnostic_count += sum(
                                target.get("candidate_kind") == "bounded_diagnostic"
                                for target in accepted
                            )
                        execution_decisions["selected_targets"] = [
                            {
                                **_execution_target_row(target, reason="eligible_for_launch"),
                                "launch_status": "selected",
                            }
                            for target in accepted_for_launch
                        ]
                        execution_decisions["selected_count"] = len(accepted_for_launch)
                    else:
                        for batch in _chunks(approvals, MAX_APPROVAL_TARGETS):
                            validation = dict(self._dependencies.dispatch({
                                "account_id": account_id,
                                # The launch adapter derives an idempotent child
                                # identity from this frozen parent-run key.  Never
                                # substitute a wall-clock retry identifier here.
                                "run_key": run_key,
                                "approved": True,
                                "execution_mode": execution_mode,
                                "execution_candidate_policy": execution_candidate_policy,
                                "authorization": {
                                    "mode": execution_mode,
                                    "source": "human_review",
                                },
                                "targets": batch,
                                "persist": False,
                                **limits,
                            }))
                            validation_batches.append(validation)
                            rejected.extend(
                                dict(item) for item in (validation.get("rejected") or [])
                                if isinstance(item, Mapping)
                            )
                            for item in validation.get("rejected") or []:
                                if isinstance(item, Mapping):
                                    _append_execution_rejection(
                                        execution_decisions, item, fallback_targets=batch,
                                    )
                            accepted_for_launch.extend(
                                dict(item) for item in (validation.get("accepted_targets") or [])
                                if isinstance(item, Mapping)
                            )
                if execution_mode == "automatic":
                    # Children may be launched only for validator acceptance;
                    # this is the durable approval boundary for automatic mode.
                    approvals = list(accepted_for_launch)
                    state["approved_targets"] = list(approvals)
                children = [
                    {
                        "target": {
                            "scorecard_id": str(target.get("scorecard_id") or ""),
                            "score_id": str(target.get("score_id") or ""),
                        },
                        "assessment_fingerprint": str(
                            target.get("assessment_fingerprint") or ""
                        ),
                        "launch_state": None,
                    }
                    for target in accepted_for_launch
                ]
                dispatch_state = {
                    "phase": "launching" if children else "incomplete",
                    "batches": validation_batches,
                    "rejected": rejected,
                    "children": children,
                    "processed_child_keys": [],
                }
                state["dispatch"] = dispatch_state
            else:
                validation_batches = []
                rejected = []
                children = []
                dispatch_state = {}

            _record_optimizer_child_wait_snapshot(
                dispatch_state,
                children,
                request.get("optimizer_child_snapshots"),
            )
            if dispatch_state:
                state["dispatch"] = dispatch_state
                for rejection in rejected:
                    _append_execution_rejection(
                        execution_decisions,
                        rejection,
                        fallback_targets=(
                            ready if execution_mode == "automatic" else approvals
                        ),
                    )

            if children and (
                self._dependencies.optimizer_child_step is None
                or self._dependencies.optimizer_child_request is None
            ):
                rejection = {"reason": "durable_optimizer_dispatch_authority_unavailable"}
                rejected.append(rejection)
                _append_execution_rejection(
                    execution_decisions, rejection,
                    fallback_targets=[row.get("target") for row in children if isinstance(row, Mapping)],
                )
                dispatch_state.update({
                    "phase": "incomplete",
                    "rejected": rejected,
                    "children": children,
                })
                state["dispatch"] = dispatch_state
            else:
                for index, child_source in enumerate(children):
                    child = dict(child_source)
                    target = child.get("target")
                    if not isinstance(target, Mapping):
                        rejection = {"reason": "malformed_optimizer_child_target"}
                        rejected.append(rejection)
                        _append_execution_rejection(execution_decisions, rejection)
                        continue
                    scorecard_id = str(target.get("scorecard_id") or "")
                    score_id = str(target.get("score_id") or "")
                    approved_target = next(
                        (
                            dict(row) for row in approvals
                            if str(row.get("scorecard_id") or "") == scorecard_id
                            and str(row.get("score_id") or "") == score_id
                        ),
                        None,
                    )
                    if approved_target is None:
                        rejection = {
                            "target": dict(target),
                            "reason": "optimizer_child_not_in_approved_targets",
                        }
                        rejected.append(rejection)
                        _append_execution_rejection(execution_decisions, rejection)
                        continue
                    base_request = {
                        "account_id": account_id,
                        "run_key": run_key,
                        "scorecard_id": scorecard_id,
                        "score_id": score_id,
                        "assessment_fingerprint": str(
                            approved_target.get("assessment_fingerprint") or ""
                        ),
                        "execution_candidate_policy": execution_candidate_policy,
                        "limits": dict(limits),
                        "target": approved_target,
                    }
                    child_request = dict(
                        self._dependencies.optimizer_child_request(base_request)
                    )
                    for identity_field in (
                        "account_id", "run_key", "scorecard_id", "score_id",
                        "assessment_fingerprint", "execution_candidate_policy",
                    ):
                        if child_request.get(identity_field) != base_request[identity_field]:
                            raise OptimizationRunPublicationError(
                                "Optimizer child request changed frozen launch identity"
                            )
                    if dict(child_request.get("limits") or {}) != dict(limits):
                        raise OptimizationRunPublicationError(
                            "Optimizer child request changed frozen launch limits"
                        )

                    def publish_child(
                        launch_state: Mapping[str, Any], *, child_index: int = index,
                    ) -> None:
                        current = dict(children[child_index])
                        current["launch_state"] = dict(launch_state)
                        for key in ("procedure_id", "task_id"):
                            if launch_state.get(key):
                                current[key] = str(launch_state[key])
                        children[child_index] = current
                        dispatch_state.update({
                            "phase": "launching",
                            "rejected": rejected,
                            "children": children,
                        })
                        state["dispatch"] = dispatch_state
                        self._publish(service, "optimization", state)

                    launch_state = drive_optimizer_child_launch(
                        child_request,
                        initial_state=(
                            child.get("launch_state")
                            if isinstance(child.get("launch_state"), Mapping)
                            else None
                        ),
                        step=self._dependencies.optimizer_child_step,
                        publish=publish_child,
                    )
                    children[index] = {
                        **dict(children[index]),
                        "launch_state": dict(launch_state),
                    }

                if children:
                    dispatch_state.update({
                        "rejected": rejected,
                        "children": children,
                    })
                    child_phases = {
                        str((row.get("launch_state") or {}).get("phase") or "")
                        for row in children
                        if isinstance(row, Mapping)
                    }
                    if child_phases & {"waiting", "running"}:
                        dispatch_state["phase"] = "waiting_for_children"
                    elif child_phases & {"dispatch_outcome_unknown", ""}:
                        dispatch_state["phase"] = "incomplete"
                    elif child_phases == {"terminal"}:
                        dispatch_state["phase"] = "children_terminal"
                    else:
                        dispatch_state["phase"] = "incomplete"
                    state["dispatch"] = dispatch_state
                    _reconcile_execution_launch_evidence(
                        execution_decisions, children,
                    )
                    state["execution_decisions"] = execution_decisions
                    if any(
                        isinstance(child.get("launch_state"), Mapping)
                        for child in children
                        if isinstance(child, Mapping)
                    ):
                            self._publish(service, "optimization", state)

            # Validator acceptance and child placeholders are not launch
            # evidence. Recompute exclusively from the current durable child
            # records so recovery and uncertain outcomes report truthfully.
            _reconcile_execution_launch_evidence(execution_decisions, children)
            state["execution_decisions"] = execution_decisions

            # Review every valid terminal child independently. A failed child
            # remains fail-closed for finalization, but its terminal evidence
            # still needs a durable review record. A processed key prevents
            # duplicate review on replay; the one exception is a checkpointed
            # failed_or_incomplete review, which recorded an inconclusive read
            # and may be reread for that exact child on a later resume.
            review_rows = [
                dict(row) for row in state.get("reviews") or []
                if isinstance(row, Mapping)
            ]
            processed_child_keys = {
                str(value) for value in dispatch_state.get("processed_child_keys") or []
                if str(value)
            }
            conclusive_review_keys = {
                str(review_row.get("optimizer_child_key") or "")
                for review_row in review_rows
                if str(review_row.get("optimizer_child_key") or "")
                and not _retryable_optimizer_review(review_row)
                and not _legacy_optimizer_review(review_row)
            }
            retryable_review_indexes: dict[str, int] = {}
            for index, review_row in enumerate(review_rows):
                existing_key = str(review_row.get("optimizer_child_key") or "")
                if not existing_key:
                    continue
                if existing_key in conclusive_review_keys:
                    processed_child_keys.add(existing_key)
                    continue
                if (
                    _retryable_optimizer_review(review_row)
                    or _legacy_optimizer_review(review_row)
                ):
                    retryable_review_indexes.setdefault(existing_key, index)
                    processed_child_keys.discard(existing_key)
                else:
                    processed_child_keys.add(existing_key)
            for child in children:
                if not _optimizer_child_terminal(child):
                    continue
                child_key = _optimizer_child_key(child)
                if not child_key or child_key in processed_child_keys:
                    continue
                procedure_id = str(child.get("procedure_id") or "")
                target = child.get("target")
                if not procedure_id or not isinstance(target, Mapping):
                    continue
                reviewed = dict(self._dependencies.review({
                    "account_id": account_id,
                    "procedure_id": procedure_id,
                    "persist": False,
                }))
                review_scope = (
                    dict(reviewed.get("scope"))
                    if isinstance(reviewed.get("scope"), Mapping)
                    else {}
                )
                review_scope.update({
                    "scorecard_id": str(target.get("scorecard_id") or ""),
                    "score_id": str(target.get("score_id") or ""),
                })
                review_record = {
                    **reviewed,
                    "scope": review_scope,
                    "procedure_id": procedure_id,
                    "optimizer_child_key": child_key,
                    "optimizer_review_contract_version": OPTIMIZER_REVIEW_CONTRACT_VERSION,
                    "optimizer_child_terminal_outcome": (
                        "succeeded" if _optimizer_child_succeeded(child) else "failed"
                    ),
                }
                retryable_index = retryable_review_indexes.get(child_key)
                if retryable_index is None:
                    review_rows.append(review_record)
                else:
                    # Preserve review-row cardinality and replace only the
                    # inconclusive record for this exact optimizer child.
                    review_rows[retryable_index] = review_record
                if _retryable_optimizer_review(review_record):
                    processed_child_keys.discard(child_key)
                else:
                    processed_child_keys.add(child_key)
                dispatch_state["processed_child_keys"] = sorted(processed_child_keys)
                state["dispatch"] = dispatch_state
                state["reviews"] = review_rows
                if (
                    not _retryable_optimizer_review(review_record)
                    and reviewed.get("promotion_ready") is True
                ):
                    promotion_target = {
                        "scorecard_id": str(target.get("scorecard_id") or ""),
                        "score_id": str(target.get("score_id") or ""),
                    }
                    if promotion_target not in state["promotion_candidates"]:
                        state["promotion_candidates"].append(promotion_target)
                    if self._dependencies.create_action is not None:
                        promotion = {"kind": "promotion_approval", **promotion_target}
                        action_rows.append(_recorded_action(
                            promotion,
                            self._dependencies.create_action(_promotion_action(
                                promotion_target, account_id=account_id, run_key=run_key,
                                report_ref=state["report_ref"], procedure_id=procedure_id,
                            )),
                        ))
                        state["actions"] = action_rows
                state["summary"] = self._summary(state)
                self._publish(service, "optimization_review", state)

            active_child_phases = {
                str((child.get("launch_state") or {}).get("phase") or "")
                for child in children
                if isinstance(child, Mapping)
            } & {"waiting", "running"}
            execution_decisions["rejected_count"] = len(
                execution_decisions["rejected_targets"]
            )
            state["execution_decisions"] = execution_decisions
            if active_child_phases:
                return self._result("WAITING_FOR_CHILDREN", state)

            status = _terminal_status(
                state,
                has_unresolved_actions=bool(_non_launch_actions(diagnosis_rows) or unresolved_approval),
            )
            state["terminal_status"] = status
            self._publish(service, "finalization", state)
            _finalize(service, status)
            self._notify(
                state,
                event="completed",
                milestone="COMPLETED",
                title="Optimization portfolio run completed",
                summary=f"Terminal state: {status.lower().replace('_', ' ')}.",
            )
            return self._result(status, state)
        except OptimizationRunRetryablePublicationError:
            # The immutable revision commit point was not reached. Published
            # evidence remains available, but neither the Report nor the
            # Procedure may claim terminal state. Return only a fixed safe
            # directive: Tactus owns the durable scheduled-continuation
            # checkpoint and will replay from verified evidence.
            return self._result(
                "RETRYABLE_PUBLICATION",
                state,
                retry=_retryable_publication_directive(),
            )
        except (OptimizationRunIntegrityError, OptimizationRunPublicationError) as exc:
            # Corrupt durable evidence is a safety boundary: do not continue
            # execution from an unverified checkpoint.
            try:
                service.fail(f"Optimization recovery integrity failure: {exc}")
            except Exception:  # pragma: no cover - original publication error wins
                pass
            return self._result("FAILED", state, error=str(exc))
        except ProcedureWaitingForHuman:
            # Tactus has persisted the authoritative pending ChatMessage and
            # will replay this run on response. The living report remains running.
            raise
        except Exception as exc:  # preserve the failure as an observable run outcome
            try:
                service.fail(f"Optimization portfolio run failed: {exc}")
            except Exception:  # pragma: no cover - best effort only
                pass
            self._notify(
                state,
                event="failed",
                milestone="FAILED",
                title="Optimization portfolio run failed",
                summary="Open the living Report for the durable failure evidence.",
            )
            return self._result("FAILED", state, error=str(exc))

    def _summary(self, state: Mapping[str, Any]) -> dict[str, Any]:
        packets: list[Mapping[str, Any]] = []
        if isinstance(state.get("rank"), Mapping):
            packets.append(state["rank"])
        packets.extend(row for row in state.get("assessments") or [] if isinstance(row, Mapping))
        packets.extend(row for row in state.get("diagnoses") or [] if isinstance(row, Mapping))
        packets.extend(row for row in state.get("reviews") or [] if isinstance(row, Mapping))
        summary = dict(self._dependencies.summary({"packets": packets, "persist": False}))
        evidence = state.get("semantic_budget_evidence")
        if isinstance(evidence, Mapping):
            summary["semantic_budget"] = dict(evidence)
            coverage = state.get("diagnosis_coverage")
            coverage = coverage if isinstance(coverage, Mapping) else {}
            unknown = int(evidence.get("unknown_count") or 0)
            deferred = int(
                coverage.get("deferred_by_budget_count") or 0
            )
            failures = int(coverage.get("failed_count") or 0)
            incomplete = int(coverage.get("incomplete_count") or 0)
            category_sources: list[Any] = [
                list(state.get("diagnoses") or []),
                coverage,
            ]
            for category, count in (
                (
                    "authority_publication_failure",
                    int(coverage.get("authority_publication_failure_count") or 0),
                ),
                (
                    "outcome_unknown",
                    int(coverage.get("outcome_unknown_count") or 0) + unknown,
                ),
                (
                    "budget_exhausted",
                    int(coverage.get("budget_exhausted_count") or 0) + deferred,
                ),
            ):
                if count > 0:
                    category_sources.append({"semantic_failure_category": category})
            failure_category = _normalize_semantic_failure_category(category_sources)
            projection = _semantic_failure_projection(failure_category)
            if unknown or deferred or failures or incomplete:
                summary["semantic_budget_next_action"] = (
                    projection["next_action"]
                    if projection is not None
                    else "review"
                )
                summary["semantic_budget_failure"] = (
                    (
                        f"{projection['rationale']} Reconciliation: {unknown} unknown "
                        f"outcomes, {deferred} deferred diagnoses, {failures} failures, "
                        f"and {incomplete} incomplete results."
                    )
                    if projection is not None
                    else (
                        "Semantic diagnosis is incomplete without a recognized structured "
                        "failure category; review the durable diagnosis evidence. "
                        f"Reconciliation: {unknown} unknown outcomes, {deferred} deferred "
                        f"diagnoses, {failures} failures, and {incomplete} incomplete results."
                    )
                )
        return summary

    def _publish(self, service: Any, milestone: str, state: Mapping[str, Any]) -> None:
        load_ledger = getattr(service, "load_semantic_budget_ledger", None)
        if callable(load_ledger) and state.get("semantic_budget_evidence") is not None:
            durable_ledger = load_ledger()
            if isinstance(durable_ledger, Mapping):
                # The ledger attachment is committed before every provider
                # contact/settlement. Refresh only at existing milestones,
                # never by publishing a workbook for a ledger transition.
                state["semantic_budget_evidence"] = _semantic_budget_evidence(
                    durable_ledger
                )
        evidence = _evidence_snapshot(state)
        service.publish_milestone(
            milestone,
            evidence,
            stakeholder_view=_stakeholder_view(state, milestone=milestone),
        )

    def _notify(
        self,
        state: dict[str, Any],
        *,
        event: str,
        milestone: str,
        title: str,
        summary: str,
    ) -> None:
        if self._dependencies.publish_update is None:
            return
        try:
            self._dependencies.publish_update({
                "event_key": f"optimization:{state['run_key']}:{event}",
                "account_id": state["account_id"],
                "milestone": milestone,
                "title": title,
                "summary": summary,
                "resource_refs": [dict(state["report_ref"])],
            })
        except Exception as exc:
            state.setdefault("notification_failures", []).append({
                "event": event,
                "error": str(exc),
            })

    @staticmethod
    def _result(
        status: str,
        state: Mapping[str, Any],
        *,
        error: str | None = None,
        retry: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = {
            "status": status,
            "run_key": state["run_key"],
            "promotion_candidates": list(state.get("promotion_candidates") or []),
            "rank": state.get("rank"),
            "assessments": list(state.get("assessments") or []),
            "diagnoses": list(state.get("diagnoses") or []),
            "summary": state.get("summary"),
            "diagnosis_coverage": dict(state.get("diagnosis_coverage") or {}),
            "actions": state.get("actions") or [],
            "approval_requests": state.get("approval_requests") or [],
            "execution_mode": state.get("execution_mode"),
            "execution_decisions": dict(state.get("execution_decisions") or {}),
            "dispatch": state.get("dispatch"),
            "reviews": state.get("reviews") or [],
        }
        if error:
            result["error"] = error
        if retry is not None:
            result["retry"] = dict(retry)
        return result


def _required_text(value: Mapping[str, Any], field: str) -> str:
    result = str(value.get(field) or "").strip()
    if not result:
        raise ValueError(f"{field} is required")
    return result


def _recorded_action(
    finding: Mapping[str, Any], persisted: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project ChatMessage action authority into compact report evidence."""
    row = dict(finding)
    persisted = persisted if isinstance(persisted, Mapping) else {}
    message = persisted.get("action")
    message = message if isinstance(message, Mapping) else {}
    resolution = persisted.get("resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}
    if message.get("id"):
        row["message_id"] = str(message["id"])
    if "created" in persisted:
        row["created"] = bool(persisted["created"])
    if message.get("responseStatus"):
        row["response_status"] = str(message["responseStatus"])
    if message.get("responseOwner"):
        row["response_owner"] = str(message["responseOwner"])
    if resolution.get("response_message_id"):
        row["response_message_id"] = str(resolution["response_message_id"])
    if "response" in resolution:
        row["response"] = resolution["response"]
    return row


def _run_key(request: Mapping[str, Any]) -> str:
    normalized = {
        "account_id": request.get("account_id"),
        "scope": request.get("scope") or {
            "scorecard_ids": request.get("scorecard_ids"),
            "scorecard_name_prefixes": request.get("scorecard_name_prefixes"),
        },
        "window": request.get("window"),
        "policy_versions": request.get("policy_versions"),
        "toolchain_version": _toolchain_version(request.get("toolchain_version")),
        "semantic_budget": _semantic_budget_spec(request),
        "execution_mode": _execution_mode(request.get("execution_mode")),
        "execution_candidate_policy": normalize_execution_candidate_policy(
            request.get("execution_candidate_policy")
        ),
        "max_execution_targets": _max_execution_targets(request),
    }
    return "optimization-" + sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:24]


def _run_spec(request: Mapping[str, Any], *, account_id: str, run_key: str) -> dict[str, Any]:
    run_spec = {
        "run_key": run_key,
        "account_id": account_id,
        "scope": request.get("scope") or {
            key: request[key] for key in ("scorecard_ids", "scorecard_name_prefixes") if key in request
        },
        "window": request.get("window") or {},
        "policy_versions": request.get("policy_versions") or {},
        "toolchain_version": _toolchain_version(request.get("toolchain_version")),
        "limits": dict(request.get("limits") or {
            key: request.get(key)
            for key in (
                "max_cost_usd", "max_samples", "max_iterations", "max_concurrency",
            )
            if key in request
        }),
        "execution_mode": _execution_mode(request.get("execution_mode")),
        "execution_candidate_policy": normalize_execution_candidate_policy(
            request.get("execution_candidate_policy")
        ),
        "max_execution_targets": _max_execution_targets(request),
    }
    semantic_budget = _semantic_budget_spec(request)
    if semantic_budget is not None:
        run_spec["semantic_budget"] = semantic_budget
    return run_spec


def _toolchain_version(build_identity: Any = None) -> str:
    """Return the concrete package/build identity frozen into run evidence."""
    import plexus
    import tactus

    parts = [
        f"plexus/{str(getattr(plexus, '__version__', '') or 'unversioned')}",
        f"tactus/{str(getattr(tactus, '__version__', '') or 'unversioned')}",
    ]
    revision = str(
        build_identity
        or os.getenv("AWS_COMMIT_ID")
        or os.getenv("AMPLIFY_COMMIT_ID")
        or os.getenv("CODE_SHA")
        or ""
    ).strip()
    if revision:
        parts.append(f"build/{revision}")
    return ";".join(parts)


_EXECUTION_MODES = frozenset({"automatic", "approval_required"})


def _execution_mode(value: Any) -> str:
    """Normalize the launch contract; direct runner callers fail safe."""
    mode = "approval_required" if value is None else str(value)
    if mode not in _EXECUTION_MODES:
        raise ValueError(
            "execution_mode must be exactly 'automatic' or 'approval_required'"
        )
    return mode


def _empty_execution_decisions(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "selected_targets": [],
        "rejected_targets": [],
        "selected_count": 0,
        "launched_count": 0,
        "rejected_count": 0,
    }


def _execution_target_row(
    target: Mapping[str, Any], *, reason: str, authorization_source: str = "deterministic_policy",
) -> dict[str, Any]:
    row = {
        "scorecard_id": str(target.get("scorecard_id") or ""),
        "score_id": str(target.get("score_id") or ""),
        "assessment_fingerprint": str(target.get("assessment_fingerprint") or ""),
        "reason": reason,
        "authorization_source": authorization_source,
    }
    for field in ("scorecard_name", "score_name"):
        value = target.get(field)
        if isinstance(value, str) and value.strip():
            row[field] = value
    if target.get("candidate_kind") and target.get("candidate_kind") != "promotion_ready":
        row["candidate_kind"] = str(target["candidate_kind"])
    return row


def _reconcile_execution_launch_evidence(
    decisions: dict[str, Any], children: Sequence[Any],
) -> None:
    """Derive per-target status and aggregate count from one durable boundary."""
    launched_keys: set[tuple[str, str]] = set()
    for child in children:
        if not isinstance(child, Mapping):
            continue
        target = child.get("target")
        launch_state = child.get("launch_state")
        scorecard_id = (
            str(target.get("scorecard_id") or "").strip()
            if isinstance(target, Mapping) else ""
        )
        score_id = (
            str(target.get("score_id") or "").strip()
            if isinstance(target, Mapping) else ""
        )
        procedure_id = str(child.get("procedure_id") or "").strip()
        task_id = str(child.get("task_id") or "").strip()
        if (
            not isinstance(target, Mapping)
            or not scorecard_id
            or not score_id
            or not procedure_id
            or not task_id
            or not isinstance(launch_state, Mapping)
            or launch_state.get("phase") not in {"waiting", "running", "terminal"}
        ):
            continue
        launched_keys.add((scorecard_id, score_id))
    selected_targets: list[dict[str, Any]] = []
    for target in decisions.get("selected_targets") or []:
        if not isinstance(target, Mapping):
            continue
        row = dict(target)
        key = _target_key(row)
        normalized_key = (
            (str(key[0]).strip(), str(key[1]).strip())
            if key is not None and str(key[0]).strip() and str(key[1]).strip()
            else None
        )
        row["launch_status"] = (
            "launched" if normalized_key in launched_keys else "selected"
        )
        selected_targets.append(row)
    decisions["selected_targets"] = selected_targets
    decisions["launched_count"] = sum(
        row["launch_status"] == "launched" for row in selected_targets
    )


def _append_execution_rejection(
    decisions: dict[str, Any],
    rejection: Mapping[str, Any],
    *,
    fallback_targets: Sequence[Any] = (),
) -> None:
    """Keep every non-launch decision machine-reconcilable and serializable."""
    targets: list[Mapping[str, Any]] = []
    target = rejection.get("target")
    if isinstance(target, Mapping):
        matching_fallback = next((
            row for row in fallback_targets
            if isinstance(row, Mapping) and _target_key(row) == _target_key(target)
        ), None)
        targets.append(
            {**dict(matching_fallback), **dict(target)}
            if isinstance(matching_fallback, Mapping) else target
        )
    elif rejection.get("scorecard_id") and rejection.get("score_id"):
        targets.append(rejection)
    else:
        targets = [row for row in fallback_targets if isinstance(row, Mapping)]
    reason = str(rejection.get("reason") or "dispatch_rejected")
    source = str(rejection.get("authorization_source") or "deterministic_policy")
    for target in targets:
        row = _execution_target_row(target, reason=reason, authorization_source=source)
        if row not in decisions["rejected_targets"]:
            decisions["rejected_targets"].append(row)
    decisions["rejected_count"] = len(decisions["rejected_targets"])


def _execution_selection(
    mode: str,
    execution_candidate_policy: str,
    assessments: Sequence[Mapping[str, Any]],
    diagnoses: Sequence[Mapping[str, Any]],
    *,
    ranked_rows: Sequence[Mapping[str, Any]],
    max_samples: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select only independently complete, frozen-policy execution targets."""
    decisions = _empty_execution_decisions(mode)
    diagnosis_by_target = {
        _target_key(row): row for row in diagnoses if _target_key(row) is not None
    }
    evidence_order = {
        _target_key(row): (
            int(row["evidence_rank"])
            if isinstance(row.get("evidence_rank"), int)
            else index
        )
        for index, row in enumerate(ranked_rows, start=1)
        if _target_key(row) is not None
    }
    ordered_assessments = sorted(
        (row for row in assessments if _target_key(row) is not None),
        key=lambda row: evidence_order.get(_target_key(row), 10**9),
    )
    selected: list[dict[str, Any]] = []
    for assessment in ordered_assessments:
        key = _target_key(assessment)
        diagnosis = diagnosis_by_target.get(key)
        candidate = {
            "scorecard_id": key[0], "score_id": key[1],
            "assessment_fingerprint": assessment.get("evidence_fingerprint") or assessment.get("fingerprint"),
            "champion_version": assessment.get("champion_version"),
            "feedback_watermark": assessment.get("feedback_watermark"),
            "scorecard_name": assessment.get("scorecard_name"),
            "score_name": assessment.get("score_name"),
            "assessment": dict(assessment),
        }
        if isinstance(diagnosis, Mapping):
            candidate["diagnosis"] = dict(diagnosis)
        promotion_ready = _is_ready(assessment)
        diagnostic_failure = None
        if not promotion_ready:
            if execution_candidate_policy != EXECUTION_CANDIDATE_POLICY_PROMOTION_READY_PLUS_BOUNDED_DIAGNOSTIC:
                _append_execution_rejection(decisions, {**candidate, "reason": "not_ready"})
                continue
            diagnostic_failure = _bounded_diagnostic_failure(
                assessment, diagnosis, max_samples=max_samples,
            )
            if diagnostic_failure:
                _append_execution_rejection(decisions, {**candidate, "reason": diagnostic_failure})
                continue
            candidate["candidate_kind"] = "bounded_diagnostic"
        else:
            candidate["candidate_kind"] = "promotion_ready"

        if diagnosis is None:
            reason = (
                "bounded_diagnostic_missing_diagnosis"
                if not promotion_ready else "missing_diagnosis"
            )
            _append_execution_rejection(decisions, {**candidate, "reason": reason})
        elif not _coverage_complete(diagnosis):
            reason = (
                "bounded_diagnostic_incomplete_diagnosis"
                if not promotion_ready else "incomplete_diagnosis"
            )
            _append_execution_rejection(decisions, {**candidate, "reason": reason})
        elif diagnosis.get("stakeholder_questions") or diagnosis.get("blockers"):
            reason = (
                "bounded_diagnostic_requires_clarification"
                if not promotion_ready else "diagnosis_requires_clarification"
            )
            _append_execution_rejection(decisions, {**candidate, "reason": reason})
        elif not (
            _bounded_diagnosis_permits_launch(diagnosis)
            if not promotion_ready else _diagnosis_permits_launch(diagnosis)
        ):
            reason = (
                "bounded_diagnostic_diagnosis_not_launchable"
                if not promotion_ready else "diagnosis_not_launchable"
            )
            _append_execution_rejection(decisions, {**candidate, "reason": reason})
        elif not isinstance(candidate["assessment_fingerprint"], str) or not candidate["assessment_fingerprint"]:
            _append_execution_rejection(decisions, {**candidate, "reason": "missing_assessment_fingerprint"})
        else:
            selected.append(candidate)
    decisions["rejected_count"] = len(decisions["rejected_targets"])
    return selected, decisions


def _limit_execution_candidates(
    candidates: Sequence[Mapping[str, Any]], *, max_execution_targets: int | None,
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, str], list[dict[str, Any]]]]]:
    """Apply accepted-target caps where approval prevents automatic backfill."""
    selected: list[dict[str, Any]] = []
    deferred: list[tuple[dict[str, str], list[dict[str, Any]]]] = []
    bounded_diagnostic_count = 0
    for candidate_source in candidates:
        candidate = dict(candidate_source)
        if max_execution_targets is not None and len(selected) >= max_execution_targets:
            deferred.append(({"reason": "execution_target_limit"}, [candidate]))
        elif (
            candidate.get("candidate_kind") == "bounded_diagnostic"
            and bounded_diagnostic_count >= MAX_BOUNDED_DIAGNOSTIC_TARGETS
        ):
            deferred.append(({"reason": "bounded_diagnostic_target_limit"}, [candidate]))
        else:
            selected.append(candidate)
            if candidate.get("candidate_kind") == "bounded_diagnostic":
                bounded_diagnostic_count += 1
    return selected, deferred


def _bounded_diagnostic_failure(
    assessment: Mapping[str, Any], diagnosis: Mapping[str, Any] | None, *, max_samples: Any,
) -> str | None:
    """Validate the narrower experiment path without weakening promotion gates."""
    if isinstance(max_samples, bool) or not isinstance(max_samples, int) or max_samples <= 0:
        return "bounded_diagnostic_invalid_sample_limit"
    assessment_failure = bounded_diagnostic_assessment_failure(
        assessment, max_samples=max_samples,
    )
    if assessment_failure:
        return assessment_failure
    if isinstance(diagnosis, Mapping):
        diagnosis_states = diagnosis.get("states")
        diagnosis_guideline = (
            diagnosis_states.get("guideline_health")
            if isinstance(diagnosis_states, Mapping)
            else diagnosis.get("guideline_state")
        )
        if diagnosis_guideline != "consistent":
            return "bounded_diagnostic_guideline_not_consistent"
        diagnosis_feedback = (
            diagnosis_states.get("feedback_rubric_health")
            if isinstance(diagnosis_states, Mapping)
            else diagnosis.get("feedback_rubric_state")
        )
        if diagnosis_feedback == "inconsistent":
            return "bounded_diagnostic_feedback_rubric_conflict"
    return None


def _bounded_diagnosis_permits_launch(packet: Mapping[str, Any]) -> bool:
    """Diagnostic experiments require a complete, consistent non-promotion diagnosis."""
    if not _coverage_complete(packet):
        return False
    if packet.get("stakeholder_questions") or packet.get("blockers"):
        return False
    states = packet.get("states")
    if not isinstance(states, Mapping):
        return False
    return (
        states.get("guideline_health") == "consistent"
        and states.get("feedback_rubric_health", states.get("feedback_rubric"))
        != "inconsistent"
        and states.get("optimization", states.get("readiness"))
        == "insufficient_evidence"
    )


def _semantic_budget_spec(request: Mapping[str, Any]) -> dict[str, str] | None:
    from plexus.optimization.semantic_authority import (
        SEMANTIC_PRICING_VERSION,
        semantic_budget_spec,
    )
    from plexus.optimization.semantic_budget import SemanticBudgetSpec

    if "max_semantic_cost_usd" in request:
        value = request.get("max_semantic_cost_usd")
        return semantic_budget_spec(value).to_dict()
    if "semantic_budget" not in request:
        return None
    value = request.get("semantic_budget")
    if not isinstance(value, Mapping):
        raise ValueError("semantic_budget must be an object")
    spec = SemanticBudgetSpec.from_dict(value)
    if spec.pricing_version != SEMANTIC_PRICING_VERSION:
        raise ValueError("semantic_budget must use the authorized pricing version")
    return spec.to_dict()


def _semantic_budget_evidence(ledger_value: Mapping[str, Any]) -> dict[str, Any]:
    """Project the persisted semantic ledger without exposing call contents."""
    from plexus.optimization.semantic_budget import stakeholder_budget_evidence

    revision = int(ledger_value.get("revision") or 0)
    return stakeholder_budget_evidence(
        ledger_value,
        evidence_reference=f"semantic-budget-ledger:r{revision:06d}",
    )


def _with_persist_false(value: Mapping[str, Any]) -> dict[str, Any]:
    return {**dict(value), "persist": False}


def _coverage_complete(packet: Mapping[str, Any]) -> bool:
    coverage = packet.get("coverage")
    return isinstance(coverage, Mapping) and coverage.get("complete") is True


def _ranked_rows(rank: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = rank.get("ranked") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _evidence_rows(rank: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the pre-policy evidence order without changing execution eligibility."""
    ranked = _ranked_rows(rank)
    deferred = [
        dict(row)
        for row in rank.get("unranked") or []
        if isinstance(row, Mapping) and isinstance(row.get("evidence_rank"), int)
    ]
    rows = ranked + deferred
    indexed = list(enumerate(rows))
    indexed.sort(key=lambda item: (
        int(item[1].get("evidence_rank"))
        if isinstance(item[1].get("evidence_rank"), int)
        else 10**9 + item[0]
    ))
    return [row for _index, row in indexed]


def _policy_next_action(reason: str) -> str:
    return {
        "recent_score_activity": "wait_for_cooldown",
        "disabled": "review_score_status",
        "missing_champion": "assign_champion",
        "unresolved_champion_reference": "repair_champion_reference",
        "incomplete_score_activity": "repair_activity_evidence",
    }.get(reason, "review_policy_blocker")


def _reconcile_aggregate_semantic_failure_category(
    diagnosis_coverage: dict[str, Any],
) -> None:
    categories = {
        category
        for category, count_key in (
            ("budget_exhausted", "budget_exhausted_count"),
            ("outcome_unknown", "outcome_unknown_count"),
            ("authority_publication_failure", "authority_publication_failure_count"),
        )
        if int(diagnosis_coverage.get(count_key) or 0) > 0
    }
    if len(categories) == 1:
        diagnosis_coverage["semantic_failure_category"] = next(iter(categories))
    else:
        diagnosis_coverage.pop("semantic_failure_category", None)


def _pending_diagnosis_coverage(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "policy_version": DIAGNOSIS_SCOPE_POLICY_VERSION,
        "ranked_count": 0,
        "top_priority_count": 0,
        "monitoring_candidate_count": 0,
        "overlap_count": 0,
        "selected_count": 0,
        "deterministic_repair_blocker_count": 0,
        "scheduled_count": 0,
        "deferred_by_cap_count": 0,
        "deferred_by_budget_count": 0,
        "deferred_after_failure_count": 0,
        "budget_exhausted_count": 0,
        "outcome_unknown_count": 0,
        "authority_publication_failure_count": 0,
        "completed_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "max_semantic_diagnoses": _max_semantic_diagnoses(request),
        "scheduled_scope_complete": False,
        "selected_scope_complete": False,
        "portfolio_semantic_complete": False,
        "blockers": [],
    }


def _max_semantic_diagnoses(request: Mapping[str, Any]) -> int:
    value = request.get("max_semantic_diagnoses", DEFAULT_MAX_SEMANTIC_DIAGNOSES)
    if isinstance(value, bool):
        raise ValueError("max_semantic_diagnoses must be a non-negative integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_semantic_diagnoses must be a non-negative integer") from exc
    if result < 0 or result != value:
        raise ValueError("max_semantic_diagnoses must be a non-negative integer")
    return result


def _max_execution_targets(request: Mapping[str, Any]) -> int | None:
    value = request.get("max_execution_targets", DEFAULT_MAX_EXECUTION_TARGETS)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("max_execution_targets must be an integer from one through five")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "max_execution_targets must be an integer from one through five"
        ) from exc
    if result != value or not 1 <= result <= MAX_APPROVAL_TARGETS:
        raise ValueError("max_execution_targets must be an integer from one through five")
    return result


def _diagnosis_selection(
    ranked_rows: Sequence[Mapping[str, Any]],
    assessment_rows: Sequence[Mapping[str, Any]],
    *,
    max_semantic_diagnoses: int,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], dict[str, Any]]:
    paired = [
        (dict(row), dict(assessment))
        for row, assessment in zip(ranked_rows, assessment_rows)
    ]
    top_priority_keys = {
        _target_key(row)
        for row, _assessment in paired[:MAX_PRIORITY_DIAGNOSES]
    }
    monitoring_keys = {
        _target_key(assessment)
        for _row, assessment in paired
        if _is_monitoring_candidate(assessment)
    }
    # The execution target limit is a result count, not a rank-window cutoff.
    # Walk the entire ranked actionable set in evidence order so blocked
    # leaders do not prevent lower-ranked safe targets from being considered.
    # ``max_semantic_diagnoses`` remains the explicit cost/safety bound.
    policy_selected = paired
    complete_candidates = [
        (row, assessment)
        for row, assessment in policy_selected
        if _coverage_complete(assessment)
    ]
    incomplete_assessment_count = len(policy_selected) - len(complete_candidates)
    deterministic_repair_blockers = [
        (row, assessment)
        for row, assessment in complete_candidates
        if _has_deterministic_repair_blocker(assessment)
    ]
    # A deterministic repair case has already reached its correct next action.
    # Semantic diagnosis cannot make it launchable, so it must not consume a
    # scarce model-backed slot ahead of an actionable candidate.
    selected = [
        (row, assessment)
        for row, assessment in complete_candidates
        if not _has_deterministic_repair_blocker(assessment)
    ]
    scheduled = selected[:max_semantic_diagnoses]
    deferred_by_cap_count = len(selected) - len(scheduled)
    coverage = {
        "policy_version": DIAGNOSIS_SCOPE_POLICY_VERSION,
        "ranked_count": len(paired),
        "top_priority_count": min(MAX_PRIORITY_DIAGNOSES, len(paired)),
        "monitoring_candidate_count": len(monitoring_keys - {None}),
        "overlap_count": len((top_priority_keys & monitoring_keys) - {None}),
        "selected_count": len(selected),
        "incomplete_assessment_count": incomplete_assessment_count,
        "deterministic_repair_blocker_count": len(deterministic_repair_blockers),
        "scheduled_count": len(scheduled),
        "deferred_by_cap_count": deferred_by_cap_count,
        "deferred_by_budget_count": 0,
        "deferred_after_failure_count": 0,
        "budget_exhausted_count": 0,
        "outcome_unknown_count": 0,
        "authority_publication_failure_count": 0,
        "completed_count": 0,
        "failed_count": 0,
        "skipped_count": len(paired) - len(selected),
        "max_semantic_diagnoses": max_semantic_diagnoses,
        "scheduled_scope_complete": False,
        "selected_scope_complete": False,
        "portfolio_semantic_complete": (
            len(selected) == len(paired)
            and incomplete_assessment_count == 0
            and deferred_by_cap_count == 0
        ),
        "blockers": [],
    }
    return scheduled, coverage


def _has_deterministic_repair_blocker(packet: Mapping[str, Any]) -> bool:
    """Whether deterministic assessment has already selected a repair action."""
    if _optimization_readiness(packet) == "repair_required":
        return True
    states = packet.get("states")
    state_values = states if isinstance(states, Mapping) else {}
    guideline_state = (
        state_values.get("guideline_health")
        or packet.get("guideline_state")
        or packet.get("guideline_health")
    )
    # Be fail-closed for compatible packets that have not normalized their
    # readiness field: missing/invalid guidelines are mechanical repairs, not
    # questions for a model-backed semantic pass.
    return guideline_state in _GUIDELINE_REPAIR_STATES


def _exact_target(row: Mapping[str, Any]) -> tuple[str, str]:
    scorecard_id = _required_text(row, "scorecard_id")
    score_id = _required_text(row, "score_id")
    return scorecard_id, score_id


def _ready_targets(assessments: Sequence[Mapping[str, Any]], diagnoses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    diagnosis_by_target = {
        _target_key(row): row for row in diagnoses if _target_key(row) is not None
    }
    ready: list[dict[str, Any]] = []
    for assessment in assessments:
        target_key = _target_key(assessment)
        if target_key is None or not _is_ready(assessment):
            continue
        diagnosis = diagnosis_by_target.get(target_key)
        # Deterministic assessment may identify an opportunity, but only a
        # complete semantic diagnosis can make it eligible for human approval.
        if diagnosis is None or not _diagnosis_permits_launch(diagnosis):
            continue
        scorecard_id, score_id = target_key
        fingerprint = assessment.get("evidence_fingerprint") or assessment.get("fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            continue
        ready.append({
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "assessment": dict(assessment),
            "assessment_fingerprint": fingerprint,
            "champion_version": assessment.get("champion_version"),
            "feedback_watermark": assessment.get("feedback_watermark"),
            "scorecard_name": assessment.get("scorecard_name"),
            "score_name": assessment.get("score_name"),
        })
    return ready


def _target_key(packet: Mapping[str, Any]) -> tuple[str, str] | None:
    scope = packet.get("scope")
    source = scope if isinstance(scope, Mapping) else packet
    scorecard_id = str(source.get("scorecard_id") or packet.get("scorecard_id") or "")
    score_id = str(source.get("score_id") or packet.get("score_id") or "")
    return (scorecard_id, score_id) if scorecard_id and score_id else None


def _is_ready(packet: Mapping[str, Any]) -> bool:
    return _coverage_complete(packet) and _optimization_readiness(packet) == "ready_to_optimize"


def _is_monitoring_candidate(packet: Mapping[str, Any]) -> bool:
    return _coverage_complete(packet) and _optimization_readiness(packet) == "monitoring_candidate"


def _optimization_readiness(packet: Mapping[str, Any]) -> Any:
    states = packet.get("states")
    if isinstance(states, Mapping):
        return states.get("optimization", states.get("readiness"))
    return packet.get("readiness_state")


def _diagnosis_permits_launch(packet: Mapping[str, Any]) -> bool:
    if not _coverage_complete(packet):
        return False
    if packet.get("stakeholder_questions") or packet.get("blockers"):
        return False
    states = packet.get("states")
    readiness = states.get("optimization", states.get("readiness")) if isinstance(states, Mapping) else packet.get("readiness_state")
    return readiness in (None, "inconclusive", "ready_to_optimize")


def _approval_request(
    *,
    run_key: str,
    account_id: str,
    batch_number: int,
    targets: Sequence[Mapping[str, Any]],
    report_ref: Mapping[str, Any],
    limits: Mapping[str, Any],
    portfolio_evidence_fingerprint: str | None = None,
) -> dict[str, Any]:
    # Resource references and fingerprints are intentionally typed values, not
    # dashboard URLs.  The dashboard derives routes from these opaque IDs.
    target_refs = [
        {
            "system": "plexus",
            "kind": "score",
            "id": target["score_id"],
            "scorecardId": target["scorecard_id"],
            "label": target.get("score_name"),
            "relation": "optimization_target",
        }
        for target in targets
    ]
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=OPTIMIZATION_APPROVAL_TTL_SECONDS)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "action_key": f"optimization-approval:{run_key}:{batch_number}",
        "kind": "optimization_approval",
        "title": "Approve optimization targets",
        "message": "Review each proposed optimization target independently.",
        "account_id": account_id,
        "targets": [
            {
                "scorecard_id": row["scorecard_id"],
                "score_id": row["score_id"],
                "scorecard_name": row.get("scorecard_name"),
                "score_name": row.get("score_name"),
                "assessment_fingerprint": row["assessment_fingerprint"],
            }
            for row in targets
        ],
        "resource_refs": [dict(report_ref), *target_refs],
        "preconditions": {
            "run_key": run_key,
            "limits": dict(limits),
            **(
                {"portfolio_evidence_fingerprint": portfolio_evidence_fingerprint}
                if portfolio_evidence_fingerprint
                else {}
            ),
            "targets": [
                {
                    "scorecard_id": row["scorecard_id"],
                    "score_id": row["score_id"],
                    "scorecard_name": row.get("scorecard_name"),
                    "score_name": row.get("score_name"),
                    "assessment_fingerprint": row["assessment_fingerprint"],
                    "champion_version": row.get("champion_version"),
                    "feedback_watermark": row.get("feedback_watermark"),
                }
                for row in targets
            ],
        },
        "expires_in_seconds": OPTIMIZATION_APPROVAL_TTL_SECONDS,
        "expires_at": expires_at,
        "response_schema": {
            "type": "object",
            "required": ["decisions"],
            "properties": {
                "decisions": {
                    "type": "array",
                    "minItems": len(targets),
                    "maxItems": len(targets),
                    "items": {
                        "type": "object",
                        "required": ["scorecard_id", "score_id", "decision"],
                        "properties": {
                            "scorecard_id": {"type": "string"},
                            "score_id": {"type": "string"},
                            "decision": {"enum": ["approve", "reject"]},
                            "comment": {"type": "string"},
                        },
                    },
                }
            },
        },
        "ui_schema": {"kind": "target_decision_table", "allow_independent_decisions": True},
    }


def _accepted_approval_targets(targets: Sequence[Mapping[str, Any]], response: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    decisions = response.get("decisions") if isinstance(response, Mapping) else None
    if not isinstance(decisions, list):
        return []
    exact = {(str(row["scorecard_id"]), str(row["score_id"])): dict(row) for row in targets}
    seen: set[tuple[str, str]] = set()
    accepted: list[dict[str, Any]] = []
    for row in decisions:
        if not isinstance(row, Mapping):
            return []
        key = (str(row.get("scorecard_id") or ""), str(row.get("score_id") or ""))
        if key not in exact or key in seen:
            return []
        seen.add(key)
        if str(row.get("decision") or "").lower() == "approve":
            accepted.append(exact[key])
    # Missing a decision is not an implicit approval.  It leaves every target
    # in that batch unresolved until a valid structured response is supplied.
    return accepted if len(seen) == len(exact) else []


def _bound_approval_response(
    current_request: Mapping[str, Any],
    submitted_approvals: Any,
) -> Mapping[str, Any] | None:
    """Return a response only when it belongs to this exact evidence boundary."""
    if not isinstance(submitted_approvals, Mapping):
        return None
    action_key = current_request.get("action_key")
    if not isinstance(action_key, str) or not action_key:
        return None
    submitted = submitted_approvals.get(action_key)
    if not isinstance(submitted, Mapping):
        return None
    saved_request = submitted.get("request")
    response = submitted.get("response")
    if not isinstance(saved_request, Mapping) or not isinstance(response, Mapping):
        return None

    # Expiry is enforced when the ChatMessage response is claimed. It is not
    # part of this comparison because the recomputed request receives a new
    # display expiry. Everything that defines what was reviewed is exact.
    boundary_fields = (
        "action_key",
        "resource_refs",
        "preconditions",
        "response_schema",
        "targets",
    )
    saved_boundary = {field: saved_request.get(field) for field in boundary_fields}
    current_boundary = {field: current_request.get(field) for field in boundary_fields}
    if json.dumps(saved_boundary, sort_keys=True, separators=(",", ":"), default=str) != json.dumps(
        current_boundary,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ):
        return None
    return dict(response)


def _response_resolves_batch(targets: Sequence[Mapping[str, Any]], response: Mapping[str, Any] | None) -> bool:
    decisions = response.get("decisions") if isinstance(response, Mapping) else None
    if not isinstance(decisions, list):
        return False
    keys = {(str(row.get("scorecard_id") or ""), str(row.get("score_id") or "")) for row in decisions if isinstance(row, Mapping)}
    expected = {(str(row["scorecard_id"]), str(row["score_id"])) for row in targets}
    return len(decisions) == len(expected) and keys == expected


def _chunks(values: Sequence[Mapping[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [list(values[index:index + size]) for index in range(0, len(values), size)]


def _procedure_id(row: Mapping[str, Any]) -> str | None:
    for key in ("procedure_id", "procedureId"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    result = row.get("result")
    if isinstance(result, Mapping):
        return _procedure_id(result)
    return None


def _target_for_procedure(dispatch_row: Mapping[str, Any], targets: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    source = dispatch_row.get("target") if isinstance(dispatch_row.get("target"), Mapping) else dispatch_row
    scorecard_id = source.get("scorecard_id")
    score_id = source.get("score_id")
    for target in targets:
        if target.get("scorecard_id") == scorecard_id and target.get("score_id") == score_id:
            return {"scorecard_id": scorecard_id, "score_id": score_id}
    # The canonical dispatch adapter includes the target, but retain a safe
    # compatibility path for a one-target batch from earlier adapters.  It is
    # never used to guess among more than one approved target.
    if len(targets) == 1:
        return {
            "scorecard_id": targets[0]["scorecard_id"],
            "score_id": targets[0]["score_id"],
        }
    return None


def _non_launch_actions(diagnoses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for packet in diagnoses:
        key = _target_key(packet)
        if key is None:
            continue
        questions = packet.get("stakeholder_questions") or []
        if questions:
            actions.append({
                "kind": "stakeholder_clarification",
                "scorecard_id": key[0],
                "score_id": key[1],
                "scorecard_name": packet.get("scorecard_name"),
                "score_name": packet.get("score_name"),
                "questions": list(questions),
            })
        states = packet.get("states") if isinstance(packet.get("states"), Mapping) else {}
        feedback = states.get("feedback_collection") or packet.get("feedback_collection_state")
        if feedback in {"reduce_to_periodic_monitoring", "collect_targeted_classes", "pause_pending_repair_or_clarification"}:
            actions.append({
                "kind": "feedback_collection_review",
                "scorecard_id": key[0],
                "score_id": key[1],
                "scorecard_name": packet.get("scorecard_name"),
                "score_name": packet.get("score_name"),
                "recommendation": feedback,
            })
    return actions


def _action_request_for_finding(
    action: Mapping[str, Any], *, account_id: str, run_key: str, report_ref: Mapping[str, Any]
) -> dict[str, Any]:
    kind = str(action["kind"])
    scorecard_id, score_id = str(action["scorecard_id"]), str(action["score_id"])
    scorecard_name = str(action.get("scorecard_name") or "").strip()
    score_name = str(action.get("score_name") or "").strip()
    named_target = " — ".join(value for value in (scorecard_name, score_name) if value)
    if kind == "stakeholder_clarification":
        expiry, schema = None, {"type": "object", "required": ["response"], "properties": {"response": {"type": "string"}}}
        title = f"Clarify policy for {score_name}" if score_name else "Stakeholder clarification"
        questions = [str(value).strip() for value in action.get("questions") or [] if str(value).strip()]
        message = questions[0] if questions else "A stakeholder policy decision is required."
    else:
        expiry, schema = None, {"type": "object", "required": ["decision"], "properties": {"decision": {"enum": ["acknowledge", "defer"]}}}
        title = f"Review feedback collection for {score_name}" if score_name else "Review feedback collection"
        recommendation = str(action.get("recommendation") or "").replace("_", " ").strip()
        message = f"Recommendation: {recommendation}." if recommendation else "Review the feedback collection recommendation."
    score_ref = {"system": "plexus", "kind": "score", "id": score_id, "scorecardId": scorecard_id}
    if named_target:
        score_ref["label"] = named_target
    return {
        "action_key": f"{kind}:{run_key}:{scorecard_id}:{score_id}", "kind": kind,
        "account_id": account_id, "title": title, "message": message,
        "resource_refs": [dict(report_ref), score_ref],
        "preconditions": {"run_key": run_key}, "expires_at": expiry,
        "response_schema": schema, "ui_schema": {"kind": "finding_review"}, "payload": dict(action),
    }


def _promotion_action(
    target: Mapping[str, Any], *, account_id: str, run_key: str, report_ref: Mapping[str, Any], procedure_id: str
) -> dict[str, Any]:
    expiry = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "action_key": f"promotion-approval:{run_key}:{target['scorecard_id']}:{target['score_id']}:{procedure_id}",
        "kind": "promotion_approval", "account_id": account_id, "title": "Approve champion promotion",
        "resource_refs": [dict(report_ref), {"system": "plexus", "kind": "score", "id": target["score_id"], "scorecardId": target["scorecard_id"]}, {"system": "plexus", "kind": "procedure", "id": procedure_id}],
        "preconditions": {"run_key": run_key, "procedure_id": procedure_id}, "expires_at": expiry,
        "response_schema": {"type": "object", "required": ["decision"], "properties": {"decision": {"enum": ["approve", "reject"]}}},
        "ui_schema": {"kind": "promotion_approval"},
    }


def _optimizer_child_key(child: Mapping[str, Any]) -> str | None:
    launch_state = child.get("launch_state")
    if not isinstance(launch_state, Mapping):
        return None
    launch_spec = launch_state.get("launch_spec")
    if isinstance(launch_spec, Mapping) and launch_spec.get("identity"):
        return str(launch_spec["identity"])
    target = child.get("target")
    if not isinstance(target, Mapping):
        return None
    identity = {
        "scorecard_id": str(target.get("scorecard_id") or ""),
        "score_id": str(target.get("score_id") or ""),
        "procedure_id": str(child.get("procedure_id") or ""),
        "task_id": str(child.get("task_id") or ""),
    }
    if any(not value for value in identity.values()):
        return None
    return sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _optimizer_child_succeeded(child: Mapping[str, Any]) -> bool:
    launch_state = child.get("launch_state")
    if not isinstance(launch_state, Mapping) or launch_state.get("phase") != "terminal":
        return False
    procedure = launch_state.get("procedure")
    if (
        isinstance(procedure, Mapping)
        and str(procedure.get("status") or "").upper() == "COMPLETED"
    ):
        return True
    task = launch_state.get("task")
    return (
        isinstance(task, Mapping)
        and str(task.get("status") or "").upper() == "COMPLETED"
    )


def _optimizer_child_terminal(child: Mapping[str, Any]) -> bool:
    """Return whether a child has authoritative terminal evidence to review."""
    launch_state = child.get("launch_state")
    return isinstance(launch_state, Mapping) and launch_state.get("phase") == "terminal"


def _retryable_optimizer_review(review: Mapping[str, Any]) -> bool:
    """Return whether a persisted review is explicitly inconclusive.

    Retries are deliberately limited to the public terminal-review disposition
    and remain coupled to the exact successful child above. Missing, malformed,
    or merely non-promoting review rows remain processed for compatibility and
    cannot create a new review or promotion action on replay.
    """
    if review.get("optimizer_child_terminal_outcome") == "failed":
        return False
    states = review.get("states")
    post_run_state = review.get("post_run_state")
    if post_run_state is None and isinstance(states, Mapping):
        post_run_state = states.get("post_run")
    return str(post_run_state or "").strip().lower() == "failed_or_incomplete"


def _legacy_optimizer_review(review: Mapping[str, Any]) -> bool:
    """Return whether a durable child review predates the current contract."""
    return bool(str(review.get("optimizer_child_key") or "")) and (
        review.get("optimizer_review_contract_version")
        != OPTIMIZER_REVIEW_CONTRACT_VERSION
    )


def _has_legacy_optimizer_review(state: Mapping[str, Any]) -> bool:
    """Permit one incomplete-finalization repair for unversioned child reviews."""
    return any(
        isinstance(review, Mapping) and _legacy_optimizer_review(review)
        for review in state.get("reviews") or []
    )


def _has_retryable_optimizer_review(state: Mapping[str, Any]) -> bool:
    """Allow only exact-child inconclusive reviews to reopen finalization."""
    return any(
        isinstance(review, Mapping)
        and bool(str(review.get("optimizer_child_key") or ""))
        and _retryable_optimizer_review(review)
        for review in state.get("reviews") or []
    )


def _dispatch_evidence_incomplete(state: Mapping[str, Any]) -> bool:
    approved_targets = state.get("approved_targets") or []
    dispatch = state.get("dispatch")
    if dispatch is None:
        return bool(approved_targets)
    if not isinstance(dispatch, Mapping):
        return True
    if dispatch.get("rejected"):
        return True
    if "children" not in dispatch:
        batches = dispatch.get("batches")
        reviews = state.get("reviews") or []
        reviewed_procedures = {
            str(review.get("procedure_id") or "")
            for review in reviews
            if isinstance(review, Mapping) and review.get("procedure_id")
        }
        legacy_dispatches = [
            row
            for batch in batches or []
            if isinstance(batch, Mapping) and not batch.get("rejected")
            for row in batch.get("dispatches") or []
            if isinstance(row, Mapping)
        ]
        return not (
            isinstance(batches, list)
            and all(
                isinstance(batch, Mapping) and not batch.get("rejected")
                for batch in batches
            )
            and legacy_dispatches
            and all(
                row.get("status") == "dispatched"
                and row.get("procedure_id")
                and str(row["procedure_id"]) in reviewed_procedures
                for row in legacy_dispatches
            )
        )
    children = dispatch.get("children")
    if not isinstance(children, list):
        return True
    if not children:
        return bool(approved_targets)
    if dispatch.get("phase") != "children_terminal":
        return True
    processed = {
        str(value) for value in dispatch.get("processed_child_keys") or []
        if str(value)
    }
    for child in children:
        if not isinstance(child, Mapping):
            return True
        child_key = _optimizer_child_key(child)
        if (
            not child.get("procedure_id")
            or not child.get("task_id")
            or not _optimizer_child_succeeded(child)
            or not child_key
            or child_key not in processed
        ):
            return True
    return False


def _terminal_status(state: Mapping[str, Any], *, has_unresolved_actions: bool) -> str:
    rank = state.get("rank")
    if not isinstance(rank, Mapping) or not _coverage_complete(rank):
        return "INCOMPLETE"
    if _dispatch_evidence_incomplete(state):
        return "INCOMPLETE"
    diagnosis_coverage = state.get("diagnosis_coverage")
    if (
        isinstance(diagnosis_coverage, Mapping)
        and int(diagnosis_coverage.get("selected_count") or 0) > 0
        and diagnosis_coverage.get("selected_scope_complete") is not True
    ):
        return "INCOMPLETE"
    if has_unresolved_actions:
        return "COMPLETED_WITH_UNRESOLVED_ACTIONS"
    return "COMPLETED"


def _finalize(service: Any, status: str) -> None:
    # The living report service owns persistent terminal state.  Version-tolerant
    # fallback keeps this orchestration usable while the structured-final-status
    # service API rolls out; it never turns an incomplete run into a success.
    try:
        service.finalize(status=status)
    except TypeError:
        if status == "COMPLETED":
            service.finalize()
        else:
            service.fail(f"Optimization run finalized as {status}")


_DURABLE_MILESTONE_ORDER = {
    "started": 0,
    "ranking": 1,
    "assessment": 2,
    "diagnosis": 3,
    "approval": 4,
    "optimization": 5,
    "optimization_review": 6,
    "finalization": 7,
}


def _checkpoint_precedes(checkpoint_milestone: str | None, target: str) -> bool:
    """Return whether ``target`` has not yet been durably published."""
    if checkpoint_milestone is None:
        return True
    if checkpoint_milestone not in _DURABLE_MILESTONE_ORDER:
        raise OptimizationRunPublicationError(
            f"Unknown durable optimization milestone: {checkpoint_milestone}"
        )
    return _DURABLE_MILESTONE_ORDER[checkpoint_milestone] < _DURABLE_MILESTONE_ORDER[target]


def _evidence_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    rank = state.get("rank")
    coverage = rank.get("coverage") if isinstance(rank, Mapping) else {"complete": False, "failures": ["ranking not yet available"]}
    semantic_evidence = state.get("semantic_budget_evidence")
    snapshot = {
        "run_key": state["run_key"],
        "run_spec": dict(state.get("run_spec") or {}),
        "terminal_status": state.get("terminal_status"),
        "coverage": dict(coverage or {}),
        "rank": state.get("rank"),
        "assessments": list(state.get("assessments") or []),
        "diagnoses": list(state.get("diagnoses") or []),
        "diagnosis_coverage": dict(state.get("diagnosis_coverage") or {}),
        "actions": list(state.get("actions") or []),
        "approval_requests": list(state.get("approval_requests") or []),
        "approved_targets": list(state.get("approved_targets") or []),
        "execution_mode": state.get("execution_mode"),
        "execution_candidate_policy": state.get("execution_candidate_policy"),
        "execution_decisions": dict(state.get("execution_decisions") or {}),
        "dispatch": state.get("dispatch"),
        "reviews": list(state.get("reviews") or []),
        "promotion_candidates": list(state.get("promotion_candidates") or []),
        "summary": state.get("summary"),
    }
    if isinstance(semantic_evidence, Mapping):
        normalized = dict(semantic_evidence)
        snapshot["semantic_budget_evidence"] = normalized
        snapshot["semantic_budget_evidence_fingerprint"] = sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
    snapshot["portfolio_evidence_fingerprint"] = _portfolio_evidence_fingerprint(
        state
    )
    return snapshot


def _portfolio_evidence_fingerprint(state: Mapping[str, Any]) -> str:
    """Bind the frozen semantic policy and current ledger proof to approval.

    Target assessment fingerprints deliberately remain target-specific and do
    not include run-wide spend.  The portfolio fingerprint is a separate
    stale-check boundary, so a ledger change invalidates a pending portfolio
    approval without changing a score's identity or assessment provenance.
    """
    run_spec = state.get("run_spec")
    run_spec = run_spec if isinstance(run_spec, Mapping) else {}
    evidence = state.get("semantic_budget_evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    payload = {
        "run_key": state.get("run_key"),
        "execution_mode": _execution_mode(run_spec.get("execution_mode")),
        "execution_candidate_policy": normalize_execution_candidate_policy(
            run_spec.get("execution_candidate_policy")
        ),
        "semantic_budget_policy": run_spec.get("semantic_budget"),
        "ledger_revision": evidence.get("ledger_revision"),
        "ledger_digest": evidence.get("evidence_digest"),
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _hydrate_durable_state(state: dict[str, Any], checkpoint: Mapping[str, Any]) -> None:
    evidence = checkpoint.get("evidence")
    if not isinstance(evidence, Mapping):
        raise OptimizationRunPublicationError("Latest optimization checkpoint has no evidence object")
    if str(evidence.get("run_key") or "") != str(state.get("run_key") or ""):
        raise OptimizationRunPublicationError("Latest optimization checkpoint belongs to another run")
    frozen_spec = evidence.get("run_spec")
    if frozen_spec is not None and not isinstance(frozen_spec, Mapping):
        raise OptimizationRunPublicationError("Latest optimization checkpoint run spec must be an object")
    if isinstance(frozen_spec, Mapping):
        frozen_mode = _execution_mode(frozen_spec.get("execution_mode"))
        current_mode = _execution_mode((state.get("run_spec") or {}).get("execution_mode"))
        if frozen_mode != current_mode:
            raise OptimizationRunPublicationError(
                "Latest optimization checkpoint execution mode differs from this run"
            )
        frozen_candidate_policy = normalize_execution_candidate_policy(
            frozen_spec.get("execution_candidate_policy")
        )
        current_candidate_policy = normalize_execution_candidate_policy(
            (state.get("run_spec") or {}).get("execution_candidate_policy")
        )
        if frozen_candidate_policy != current_candidate_policy:
            raise OptimizationRunPublicationError(
                "Latest optimization checkpoint execution candidate policy differs from this run"
            )
        state["execution_mode"] = current_mode
        state["execution_candidate_policy"] = current_candidate_policy
    for key in (
        "terminal_status", "rank", "dispatch", "summary",
    ):
        if key in evidence:
            state[key] = evidence.get(key)
    for key in (
        "assessments", "diagnoses", "actions", "approval_requests",
        "approved_targets", "reviews",
        "promotion_candidates",
    ):
        value = evidence.get(key)
        if value is not None and not isinstance(value, list):
            raise OptimizationRunPublicationError(
                f"Latest optimization checkpoint field {key} must be a list"
            )
        state[key] = list(value or [])
    decisions = evidence.get("execution_decisions")
    if decisions is not None and not isinstance(decisions, Mapping):
        raise OptimizationRunPublicationError(
            "Latest optimization checkpoint execution decisions must be an object"
        )
    if isinstance(decisions, Mapping):
        restored = dict(decisions)
        if _execution_mode(restored.get("mode")) != state.get("execution_mode"):
            raise OptimizationRunPublicationError(
                "Latest optimization checkpoint execution decisions have a different execution mode"
            )
        state["execution_decisions"] = restored
    coverage = evidence.get("diagnosis_coverage")
    if coverage is not None and not isinstance(coverage, Mapping):
        raise OptimizationRunPublicationError(
            "Latest optimization checkpoint diagnosis coverage must be an object"
        )
    state["diagnosis_coverage"] = dict(coverage or {})
    semantic_evidence = evidence.get("semantic_budget_evidence")
    if semantic_evidence is not None and not isinstance(semantic_evidence, Mapping):
        raise OptimizationRunPublicationError(
            "Latest optimization checkpoint semantic budget evidence must be an object"
        )
    if isinstance(semantic_evidence, Mapping):
        state["semantic_budget_evidence"] = dict(semantic_evidence)


def _stakeholder_coverage(*packets: Mapping[str, Any]) -> str:
    for packet in packets:
        if not isinstance(packet, Mapping):
            continue
        coverage = packet.get("coverage")
        if isinstance(coverage, Mapping) and "complete" in coverage:
            return "complete" if coverage.get("complete") is True else "incomplete"
    return "incomplete"


def _diagnosis_result_incomplete(packet: Mapping[str, Any]) -> bool:
    if not isinstance(packet, Mapping):
        return False
    if _normalize_semantic_failure_category(packet) in SEMANTIC_FAILURE_CATEGORIES:
        return True
    coverage = packet.get("coverage")
    if isinstance(coverage, Mapping) and coverage.get("complete") is False:
        return True
    states = packet.get("states") if isinstance(packet.get("states"), Mapping) else {}
    values = {
        str(packet.get("outcome") or "").strip().lower(),
        str(packet.get("status") or "").strip().lower(),
        str(states.get("optimization") or "").strip().lower(),
        str(states.get("readiness") or "").strip().lower(),
        str(states.get("post_run") or "").strip().lower(),
    }
    return bool(values & {
        "incomplete", "failed", "failed_or_incomplete",
        "budget_exhausted", "outcome_unknown", "authority_publication_failure",
    })


def _diagnosis_failures(packet: Mapping[str, Any]) -> list[str]:
    """Read safe failure labels from both supported diagnosis envelopes."""
    failures = packet.get("failures") if isinstance(packet, Mapping) else None
    values = list(failures) if isinstance(failures, list) else []
    coverage = packet.get("coverage") if isinstance(packet, Mapping) else None
    nested = coverage.get("failures") if isinstance(coverage, Mapping) else None
    if isinstance(nested, list):
        values.extend(nested)
    return [str(value) for value in values if str(value)]


def _normalize_semantic_failure_category(value: Any) -> str:
    """Normalize all structured category evidence without consulting prose."""
    categories: list[str] = []

    def collect(current: Any) -> None:
        if isinstance(current, Mapping):
            if "semantic_failure_category" in current:
                categories.append(
                    str(current.get("semantic_failure_category") or "").strip()
                )
            for nested in current.values():
                collect(nested)
        elif isinstance(current, (list, tuple)):
            for nested in current:
                collect(nested)

    collect(value)
    if not categories or any(
        category not in SEMANTIC_FAILURE_CATEGORIES for category in categories
    ):
        return "incomplete"
    unique = set(categories)
    return categories[0] if len(unique) == 1 else "incomplete"


def _diagnosis_outcome_unknown(packet: Mapping[str, Any]) -> bool:
    return _normalize_semantic_failure_category(packet) == "outcome_unknown"


def _semantic_failure_projection(category: str | None) -> dict[str, str] | None:
    if category == "budget_exhausted":
        return {
            "readiness": "incomplete",
            "coverage_status": "incomplete",
            "next_action": "review_semantic_budget",
            "rationale": (
                "Semantic diagnosis stopped because the frozen semantic budget "
                "could not authorize completion; review the budget and wait for "
                "authorized capacity before retrying. This score is not an "
                "optimization-ready target."
            ),
        }
    if category == "outcome_unknown":
        return {
            "readiness": "incomplete",
            "coverage_status": "incomplete",
            "next_action": "review_semantic_budget",
            "rationale": (
                "Semantic diagnosis is incomplete because the provider outcome is "
                "unknown; review the durable semantic budget evidence before any retry."
            ),
        }
    if category == "authority_publication_failure":
        return {
            "readiness": "incomplete",
            "coverage_status": "incomplete",
            "next_action": "repair_semantic_authority_publication",
            "rationale": (
                "Semantic diagnosis is incomplete because durable semantic authority "
                "evidence could not be published; repair the publication authority "
                "and retry only after durable evidence is available."
            ),
        }
    return None


def _semantic_exception_category(exc: Exception) -> str:
    from plexus.optimization.semantic_authority import (
        SemanticAuthorityPublicationError,
        SemanticOutcomeUnknown,
    )
    from plexus.optimization.semantic_budget import SemanticBudgetExceeded
    from tactus.protocols.model_attempt import ModelAttemptOutcomeUnknown

    if isinstance(exc, SemanticBudgetExceeded):
        return "budget_exhausted"
    if isinstance(exc, (SemanticOutcomeUnknown, ModelAttemptOutcomeUnknown)):
        return "outcome_unknown"
    if isinstance(exc, (
        SemanticAuthorityPublicationError,
        OptimizationRunPublicationError,
        OptimizationRunIntegrityError,
    )):
        return "authority_publication_failure"
    return "incomplete"


def _semantic_diagnosis_status(
    *,
    key: tuple[str, str] | None,
    diagnosis: Mapping[str, Any],
    selected_keys: set[tuple[str, str]],
    scheduled_keys: set[tuple[str, str]],
    milestone: str,
) -> str:
    if key is None or key not in selected_keys:
        return "not_selected"
    semantic_failure = _normalize_semantic_failure_category(diagnosis)
    if semantic_failure in SEMANTIC_FAILURE_CATEGORIES:
        return semantic_failure
    if diagnosis:
        return "incomplete" if _diagnosis_result_incomplete(diagnosis) else "complete"
    if key not in scheduled_keys:
        return "deferred"
    if milestone in {"started", "ranking", "assessment"}:
        return "pending"
    return "incomplete"


def _stakeholder_trend(*packets: Mapping[str, Any]) -> str:
    for packet in packets:
        stability = packet.get("weekly_stability") if isinstance(packet, Mapping) else None
        if not isinstance(stability, Mapping):
            continue
        counts = list(stability.get("weekly_bucket_counts") or [])
        disagreement_range = stability.get("weekly_disagreement_range")
        ac1_range = stability.get("weekly_ac1_range")
        if counts or disagreement_range is not None or ac1_range is not None:
            return (
                f"Latest complete weeks: counts {', '.join(str(value) for value in counts) or 'not available'}; "
                f"disagreement range {disagreement_range if disagreement_range is not None else 'not available'}; "
                f"AC1 range {ac1_range if ac1_range is not None else 'not available'}."
            )
    return "Not available"


def _stakeholder_dashboard_url(*packets: Mapping[str, Any]) -> str | None:
    for packet in packets:
        value = packet.get("dashboard_url") if isinstance(packet, Mapping) else None
        if isinstance(value, str) and value.startswith("https://"):
            return value
    return None


# The living Report is a decision record, not a text classifier.  These
# vocabulary sets mirror the public decision-packet contract and intentionally
# use exact values only.  In particular, a word in an operator rationale must
# never silently change the displayed disposition.
_TERMINAL_POST_RUN_DISPOSITIONS = frozenset({
    "promotion_ready",
    "validated_improvement",
    "continue_optimization",
    "stakeholder_decision_required",
    "no_safe_improvement",
    "failed_or_incomplete",
})
_PRE_OBSERVATION_CHILD_LAUNCH_PHASES = frozenset({
    # These are the durable transition states emitted by
    # OptimizerTaskDispatchService before its first task observation. A Report
    # may be recovered at any one of them, so each must take precedence over
    # an otherwise unselected portfolio row.
    "planned",
    "procedure_create_attempted",
    "procedure_record_observed",
    "procedure_provisioned",
    "task_create_attempted",
    "task_record_observed",
    "task_stage_reconcile_attempted",
    "task_held",
    "release_attempted",
    # Compatibility phases from report checkpoints created before the child
    # dispatch state machine owned each transition explicitly.
    "launching",
    "preparing",
    "dispatching",
})

_ACTIVE_CHILD_PHASE_DISPOSITIONS = {
    **{
        phase: "optimizer_launching"
        for phase in _PRE_OBSERVATION_CHILD_LAUNCH_PHASES
    },
    "waiting": "optimization_in_progress",
    "running": "optimization_in_progress",
    "terminal": "awaiting_optimizer_review",
    # Dispatch evidence is not trustworthy enough to leave an active child
    # eligible; surface it through the public incomplete-result disposition.
    "dispatch_outcome_unknown": "failed_or_incomplete",
}
_GUIDELINE_REPAIR_STATES = frozenset({"missing", "invalid", "potential_code_conflict"})
_INCOMPLETE_READINESS_STATES = frozenset({"incomplete", "insufficient_evidence"})


def _approval_target_keys(requests: Any) -> set[tuple[str, str]]:
    """Return exact target keys awaiting a recorded human decision."""
    keys: set[tuple[str, str]] = set()
    for request in requests or []:
        if not isinstance(request, Mapping):
            continue
        for target in request.get("targets") or []:
            if isinstance(target, Mapping):
                key = _target_key(target)
                if key is not None:
                    keys.add(key)
    return keys


def _invalid_run_limits_rejection(dispatch: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the global pre-launch limit rejection, including legacy batches."""
    candidates = [
        row for row in dispatch.get("rejected") or []
        if isinstance(row, Mapping)
    ]
    candidates.extend(
        row
        for batch in dispatch.get("batches") or []
        if isinstance(batch, Mapping)
        for row in batch.get("rejected") or []
        if isinstance(row, Mapping)
    )
    for rejection in candidates:
        if rejection.get("reason") == "invalid_run_limits":
            return dict(rejection)
    return None


def _primary_disposition(
    *,
    review: Mapping[str, Any],
    optimizer_child: Mapping[str, Any],
    awaiting_approval: bool,
    readiness: Any,
    collection: Any,
    guideline: Any,
    policy_disposition: Any,
    coverage_status: str,
) -> str:
    """Choose one mutually-exclusive primary disposition by fixed precedence."""
    review_states = review.get("states") if isinstance(review.get("states"), Mapping) else {}
    terminal = review.get("post_run_state") or review_states.get("post_run")
    if terminal in _TERMINAL_POST_RUN_DISPOSITIONS:
        return str(terminal)

    launch_state = (
        optimizer_child.get("launch_state")
        if isinstance(optimizer_child.get("launch_state"), Mapping)
        else {}
    )
    child_disposition = _ACTIVE_CHILD_PHASE_DISPOSITIONS.get(launch_state.get("phase"))
    if child_disposition is not None:
        return child_disposition

    if awaiting_approval:
        return "awaiting_optimization_approval"
    if readiness == "stakeholder_clarification_required":
        return "stakeholder_clarification_required"
    if guideline in _GUIDELINE_REPAIR_STATES or readiness == "repair_required":
        return "guideline_or_code_repair"
    if readiness == "feedback_curation_review":
        return "feedback_curation_review"
    if readiness == "monitoring_candidate" or collection == "reduce_to_periodic_monitoring":
        return "monitoring_or_diminishing_returns"
    if collection == "collect_targeted_classes":
        return "targeted_feedback_collection"
    if policy_disposition == "cooldown" or readiness == "cooldown_active":
        return "cooldown"
    if coverage_status == "incomplete" or readiness in _INCOMPLETE_READINESS_STATES:
        return "insufficient_evidence"
    return "not_selected"


def _secondary_issue_flags(
    *,
    guideline: Any,
    feedback_rubric: Any,
    stakeholder_questions: Any,
    coverage_status: str,
) -> list[str]:
    """Return independent issue flags in a stable stakeholder-facing order."""
    flags: list[str] = []
    if guideline == "missing":
        flags.append("missing_guidelines")
    if guideline == "invalid":
        flags.append("invalid_guidelines")
    if guideline == "potential_code_conflict":
        flags.append("potential_code_conflict")
    if feedback_rubric == "inconsistent":
        flags.append("feedback_rubric_contradiction")
    if isinstance(stakeholder_questions, list) and stakeholder_questions:
        flags.append("stakeholder_question")
    if coverage_status == "incomplete":
        flags.append("incomplete_evidence")
    return flags


_ISSUE_SEVERITY = {
    "required_evidence_unavailable": 0,
    "missing_guidelines": 0,
    "invalid_guidelines": 0,
    "potential_code_conflict": 1,
    "feedback_rubric_contradiction": 2,
    "stakeholder_question": 3,
    "incomplete_evidence": 4,
}


def _issue_rows(
    *,
    base: Mapping[str, Any],
    affected_disagreement_rate: Any,
    flags: list[str],
    guideline: Any,
    guideline_code_conflict_claim: Any,
    diagnosis_evidence_ids: Any,
    diagnosis_evidence_fingerprint: Any,
    feedback_rubric: Any,
    stakeholder_questions: Any,
    readiness: Any,
    coverage_status: str,
    rationale: str,
    next_action: str,
    dashboard_url: str | None,
) -> list[dict[str, Any]]:
    """Project each independent issue without copying opaque/raw evidence."""
    findings = {
        "required_evidence_unavailable": (
            "Required diagnosis evidence could not be read, so semantic review "
            "and optimization were stopped before additional spend."
        ),
        "missing_guidelines": "Guidelines are missing.",
        "invalid_guidelines": "Guidelines cannot be validated.",
        "potential_code_conflict": "Guidelines may conflict with score code.",
        "feedback_rubric_contradiction": "Reviewed feedback and the rubric are inconsistent.",
        "incomplete_evidence": "Evidence is incomplete, so conclusions are provisional.",
    }
    evidence_tokens = [
        *_stakeholder_diagnosis_evidence_aliases(diagnosis_evidence_fingerprint),
        *_stakeholder_evidence_reference_tokens(diagnosis_evidence_ids),
    ]
    rows: list[dict[str, Any]] = []
    for flag in flags:
        if flag == "stakeholder_question":
            for finding in stakeholder_questions:
                if isinstance(finding, str) and finding.strip():
                    rows.append({
                        **base, "kind": "stakeholder question", "issue_flag": flag,
                        "issue_severity": _ISSUE_SEVERITY[flag], "evidence_count": base.get("evidence_count"),
                        "affected_evidence_count": base.get("evidence_count"),
                        "affected_disagreement_rate": affected_disagreement_rate,
                        "evidence_references": "semantic diagnosis",
                        "state": readiness, "coverage_status": coverage_status,
                        "guideline_state": guideline, "feedback_rubric_state": feedback_rubric,
                        "finding": finding.strip(), "rationale": rationale,
                        "next_action": "answer_question", "dashboard_url": dashboard_url,
                    })
            continue
        finding = findings[flag]
        issue_next_action = next_action
        issue_evidence_references = (
            "diagnosis prerequisite check"
            if flag == "required_evidence_unavailable"
            else "decision packet"
        )
        if flag == "potential_code_conflict" and isinstance(
            guideline_code_conflict_claim, str
        ) and guideline_code_conflict_claim.strip():
            finding = guideline_code_conflict_claim.strip()
        if flag == "potential_code_conflict":
            # This is a model claim for maintainer review, not an adjudicated
            # defect.  Keep its exact wording but make the repair ownership
            # and automatic-execution consequence deterministic.
            issue_next_action = "review_and_repair_guideline_code_alignment"
            issue_evidence_references = "; ".join(
                ["semantic diagnosis packet", *evidence_tokens]
            )
        rows.append({
            **base, "kind": "issue", "issue_flag": flag,
            "issue_severity": _ISSUE_SEVERITY[flag], "evidence_count": base.get("evidence_count"),
            "affected_evidence_count": base.get("evidence_count"),
            "affected_disagreement_rate": affected_disagreement_rate,
            "evidence_references": issue_evidence_references,
            **(
                {"evidence_reference_tokens": evidence_tokens}
                if flag == "potential_code_conflict" else {}
            ),
            "state": guideline if flag in {"missing_guidelines", "invalid_guidelines", "potential_code_conflict"} else readiness,
            "coverage_status": coverage_status, "guideline_state": guideline,
            "feedback_rubric_state": feedback_rubric,
            "finding": finding, "rationale": rationale,
            "next_action": issue_next_action, "dashboard_url": dashboard_url,
        })
    return rows


def _stakeholder_opaque_ref(value: str | None) -> str | None:
    """Return a stable stakeholder-safe reference without exposing an opaque ID."""
    return sha256(value.encode("utf-8")).hexdigest()[:16] if value else None


def _stakeholder_evidence_reference_tokens(value: Any) -> list[str]:
    """Return deterministic safe aliases for restricted semantic evidence IDs."""
    if not isinstance(value, (list, tuple)):
        return []
    tokens: list[str] = []
    for source in value:
        if not isinstance(source, str) or not source:
            continue
        token = "semantic-evidence-" + sha256(source.encode("utf-8")).hexdigest()[:16]
        if token not in tokens:
            tokens.append(token)
    return tokens


def _stakeholder_diagnosis_evidence_aliases(value: Any) -> list[str]:
    """Return a safe alias for the immutable diagnosis decision packet.

    The packet fingerprint changes whenever its frozen evidence changes.  The
    stakeholder report may name a short derived alias, but never the raw
    fingerprint or a restricted evidence identifier.
    """
    if not isinstance(value, str) or not value:
        return []
    return ["semantic-diagnosis-" + sha256(value.encode("utf-8")).hexdigest()[:16]]


def _milestone_narrative(
    milestone: str,
    *,
    execution_mode: str = "approval_required",
    approved_target_count: int = 0,
    dispatched_optimizer_count: int = 0,
) -> tuple[str, str]:
    if milestone == "optimization" and approved_target_count == 0:
        if execution_mode == "automatic":
            return (
                "No optimizations were launched because no diagnosed targets passed the automatic execution policy.",
                "The run will finalize the completed analysis and explain why each candidate was excluded.",
            )
        return (
            "No optimizations were launched because no targets were approved in this run.",
            "The run will finalize the completed analysis and any unresolved human actions.",
        )
    if milestone == "optimization_review" and dispatched_optimizer_count == 0:
        return (
            "No optimization results are available because no optimizer procedure was launched.",
            "The final report will preserve the ranked findings, policy decisions, and incomplete evidence.",
        )
    narratives = {
        "started": (
            "Enumerating every scorecard and analyzing the frozen feedback window.",
            "A ranked portfolio will be published after exhaustive coverage is verified.",
        ),
        "ranking": (
            "Applying deterministic readiness and feedback-investment checks to every eligible candidate.",
            "Assessment results and the bounded semantic-diagnosis scope will be published next.",
        ),
        "assessment": (
            "Running semantic diagnosis for the selected highest-priority and monitoring candidates.",
            "Guideline conflicts, stakeholder questions, and safe optimization candidates will be published next.",
        ),
        "diagnosis": (
            "Preparing human decisions for diagnosed findings and safe optimization targets.",
            "No optimizer will start until each exact target receives an explicit decision.",
        ),
        "approval": (
            "Waiting for, or reconciling, human decisions on the exact diagnosed targets.",
            "Approved work will be rechecked for freshness before any optimizer starts.",
        ),
        "optimization": (
            "Running only the explicitly approved optimization targets and preserving their evidence.",
            "Completed evaluations will be reviewed before any promotion request is created.",
        ),
        "optimization_review": (
            "Reviewing completed optimizer and evaluation evidence for safe improvement.",
            "The final report will separate promotion-ready results, continued work, and incomplete evidence.",
        ),
        "finalization": (
            "Finalizing the durable report, workbook, unresolved actions, and audit trail.",
            "This run is ending without automatic score, guideline, feedback, or champion changes.",
        ),
    }
    if execution_mode == "automatic":
        narratives.update({
            "diagnosis": (
                "Applying the automatic execution policy to diagnosed findings and safe optimization targets.",
                "Targets that pass every frozen policy and freshness gate will launch without waiting for human approval.",
            ),
            "approval": (
                "Recording automatic policy decisions for the exact diagnosed targets.",
                "Selected targets will be rechecked for freshness before any optimizer starts.",
            ),
            "optimization": (
                "Running only targets selected by the automatic execution policy and preserving their evidence.",
                "Completed evaluations will be reviewed before any promotion request is created.",
            ),
        })
    return narratives.get(milestone, (f"Processing {milestone}.", "The next durable milestone will update this report."))


def _terminal_narrative(status: str) -> tuple[str, str]:
    narratives = {
        "completed": (
            "Portfolio analysis and review are complete.",
            "Review the ranked priorities, decisions, and attached evidence.",
        ),
        "completed_with_unresolved_actions": (
            "Portfolio analysis is complete; human decisions remain open.",
            "Resolve the outstanding actions before approved work can continue.",
        ),
        "incomplete": (
            "The run ended with incomplete coverage or evidence.",
            "Review whether a configured limit, budget, or incomplete diagnosis prevented full coverage.",
        ),
        "blocked": (
            "The run ended blocked by an unresolved dependency.",
            "Resolve the documented blocker before starting another attempt.",
        ),
        "failed": (
            "The run failed before it could publish a complete conclusion.",
            "Review the failure evidence and retry only after the cause is addressed.",
        ),
    }
    return narratives.get(status, ("The run has ended.", "Review its terminal evidence and next actions."))


def _semantic_budget_overview(
    evidence: Any,
    *,
    diagnosis_coverage: Mapping[str, Any],
) -> dict[str, Any]:
    """Flatten the safe ledger projection for report/workbook display only."""
    if not isinstance(evidence, Mapping):
        return {}
    call_sites = evidence.get("call_site_coverage")
    if not isinstance(call_sites, list):
        call_sites = []
    call_site_text = ", ".join(
        f"{item.get('call_site')}: {item.get('count')}"
        for item in call_sites
        if isinstance(item, Mapping)
    ) or "none"
    return {
        "semantic_budget_policy_version": evidence.get("policy_version"),
        "semantic_budget_spec_schema_version": evidence.get("budget_spec_schema_version"),
        "semantic_budget_ledger_schema_version": evidence.get("ledger_schema_version"),
        "semantic_budget_pricing_version": evidence.get("pricing_version"),
        "semantic_budget_provider": evidence.get("provider"),
        "semantic_budget_model": evidence.get("model"),
        "semantic_budget_authorized_usd": evidence.get("authorized_max_usd"),
        "semantic_budget_settled_actual_usd": evidence.get("settled_actual_usd"),
        "semantic_budget_held_reserved_usd": evidence.get("held_reserved_usd"),
        "semantic_budget_available_usd": evidence.get("available_usd"),
        "semantic_budget_reservation_count": evidence.get("reservation_count"),
        "semantic_budget_reserved_count": evidence.get("reserved_count"),
        "semantic_budget_settled_count": evidence.get("settled_count"),
        "semantic_budget_unknown_count": evidence.get("unknown_count"),
        "semantic_budget_cancelled_count": evidence.get("cancelled_count"),
        "semantic_budget_target_count": evidence.get("target_count"),
        "semantic_budget_call_site_coverage": call_site_text,
        "semantic_budget_ledger_revision": evidence.get("ledger_revision"),
        "semantic_budget_evidence_reference": evidence.get("evidence_reference"),
        "semantic_budget_evidence_digest": evidence.get("evidence_digest"),
        "semantic_budget_deferred_count": int(
            diagnosis_coverage.get("deferred_by_budget_count") or 0
        ),
        "semantic_diagnosis_deferred_after_failure_count": int(
            diagnosis_coverage.get("deferred_after_failure_count") or 0
        ),
        "semantic_budget_exhausted_count": int(
            diagnosis_coverage.get("budget_exhausted_count") or 0
        ),
        "semantic_diagnosis_outcome_unknown_count": int(
            diagnosis_coverage.get("outcome_unknown_count") or 0
        ),
        "semantic_authority_publication_failure_count": int(
            diagnosis_coverage.get("authority_publication_failure_count") or 0
        ),
        "semantic_budget_failure_count": int(
            diagnosis_coverage.get("failed_count") or 0
        ),
    }


def _stakeholder_view(state: Mapping[str, Any], *, milestone: str) -> dict[str, Any]:
    run_spec = state.get("run_spec") if isinstance(state.get("run_spec"), Mapping) else {}
    execution_mode = _execution_mode(
        state.get("execution_mode") or run_spec.get("execution_mode")
    )
    execution_candidate_policy = normalize_execution_candidate_policy(
        run_spec.get("execution_candidate_policy")
    )
    rank = state.get("rank") if isinstance(state.get("rank"), Mapping) else {}
    diagnosis_coverage = (
        state.get("diagnosis_coverage")
        if isinstance(state.get("diagnosis_coverage"), Mapping)
        else {}
    )
    assessments = {_target_key(row): row for row in state.get("assessments") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    diagnoses = {_target_key(row): row for row in state.get("diagnoses") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    reviews = {_target_key(row): row for row in state.get("reviews") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    dispatch = state.get("dispatch") if isinstance(state.get("dispatch"), Mapping) else {}
    optimizer_children = {
        _target_key(row.get("target")): row
        for row in dispatch.get("children") or []
        if isinstance(row, Mapping)
        and isinstance(row.get("target"), Mapping)
        and _target_key(row.get("target")) is not None
    }
    portfolio: list[dict[str, Any]] = []
    priorities: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    ranked_rows = _ranked_rows(rank)
    evidence_rows = _evidence_rows(rank)
    selected_for_review, _selection_coverage = _diagnosis_selection(
        ranked_rows,
        [assessments.get(_target_key(row), {}) for row in ranked_rows],
        max_semantic_diagnoses=int(
            (state.get("diagnosis_coverage") or {}).get(
                "max_semantic_diagnoses", DEFAULT_MAX_SEMANTIC_DIAGNOSES
            )
        ),
    )
    selected_for_review_keys = {
        _target_key(row) for row, _assessment in selected_for_review
    } - {None}
    diagnosis_prerequisite_failure_count = int(
        diagnosis_coverage.get("prerequisite_failure_count") or 0
    )
    prerequisite_failure_keys = (
        set(selected_for_review_keys)
        if diagnosis_prerequisite_failure_count > 0
        else set()
    )
    prerequisite_failure_message = str(
        next(iter(diagnosis_coverage.get("blockers") or []), "")
        or (
            "Required semantic evidence authority is unavailable; "
            "repair worker authorization and resume."
        )
    )
    all_selected, _all_selection_coverage = _diagnosis_selection(
        ranked_rows,
        [assessments.get(_target_key(row), {}) for row in ranked_rows],
        max_semantic_diagnoses=len(ranked_rows),
    )
    all_selected_keys = {
        _target_key(row) for row, _assessment in all_selected
    } - {None}
    pending_approval_keys = _approval_target_keys(state.get("approval_requests"))
    approved_target_keys = {
        _target_key(target)
        for target in state.get("approved_targets") or []
        if isinstance(target, Mapping) and _target_key(target) is not None
    }
    invalid_run_limits_rejection = _invalid_run_limits_rejection(dispatch)
    projected_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for fallback_rank, row in enumerate(evidence_rows, start=1):
        rank_position = (
            int(row.get("evidence_rank"))
            if isinstance(row.get("evidence_rank"), int)
            else fallback_rank
        )
        key = _target_key(row)
        assessment = assessments.get(key, {})
        diagnosis = diagnoses.get(key, {})
        policy_disposition = str(row.get("policy_disposition") or "eligible")
        policy_reason = str(row.get("policy_reason") or "meets_rank_policy")
        eligible_for_optimization = row.get("eligible_for_optimization") is not False
        awaiting_semantic_diagnosis = (
            eligible_for_optimization and _is_ready(assessment)
            and key in all_selected_keys
            and key not in diagnoses
            and key not in reviews
            and milestone not in {"started", "ranking", "assessment"}
        )
        review = reviews.get(key, {})
        dispatch_rejection = (
            invalid_run_limits_rejection
            if key in approved_target_keys and invalid_run_limits_rejection is not None
            else None
        )
        optimizer_child = optimizer_children.get(key, {})
        launch_state = (
            optimizer_child.get("launch_state")
            if isinstance(optimizer_child.get("launch_state"), Mapping)
            else {}
        )
        launch_phase = str(launch_state.get("phase") or "")
        states = {
            **(assessment.get("states") if isinstance(assessment.get("states"), Mapping) else {}),
            **(diagnosis.get("states") if isinstance(diagnosis.get("states"), Mapping) else {}),
            **(review.get("states") if isinstance(review.get("states"), Mapping) else {}),
        }
        readiness = states.get("optimization") or states.get("readiness") or assessment.get("readiness_state") or "inconclusive"
        next_action = review.get("primary_next_action") or diagnosis.get("primary_next_action") or assessment.get("primary_next_action") or "review"
        collection = states.get("feedback_collection") or diagnosis.get("feedback_collection_state") or assessment.get("feedback_collection_state") or "inconclusive"
        guideline = states.get("guideline_health") or diagnosis.get("guideline_state") or assessment.get("guideline_state") or "inconclusive"
        feedback_rubric = states.get("feedback_rubric_health") or states.get("feedback_rubric") or diagnosis.get("feedback_rubric_state") or assessment.get("feedback_rubric_state") or "inconclusive"
        promotion = states.get("promotion_readiness") or review.get("post_run_state") or "not_evaluated"
        rationale = review.get("rationale") or diagnosis.get("rationale") or assessment.get("rationale") or "Evidence-based priority."
        coverage_status = _stakeholder_coverage(diagnosis, assessment, rank)
        semantic_diagnosis_status = _semantic_diagnosis_status(
            key=key,
            diagnosis=diagnosis,
            selected_keys=all_selected_keys,
            scheduled_keys=selected_for_review_keys,
            milestone=milestone,
        )
        if not eligible_for_optimization:
            next_action = _policy_next_action(policy_reason)
            if policy_disposition == "cooldown":
                readiness = "cooldown_active"
                rationale = "Recent score work defers another optimization attempt, but the evidence priority remains visible for monitoring."
            elif policy_disposition == "incomplete":
                readiness = "incomplete"
                coverage_status = "incomplete"
                rationale = "Policy evidence is incomplete, so this score cannot be selected safely."
            else:
                readiness = "repair_required"
                rationale = "A structural policy gate prevents optimization until the documented issue is repaired."
        if awaiting_semantic_diagnosis:
            readiness = "incomplete"
            next_action = "await_semantic_diagnosis"
            rationale = "Deterministic assessment found an opportunity; semantic diagnosis is not complete for this score."
            coverage_status = "incomplete"
            if int(diagnosis_coverage.get("deferred_by_budget_count") or 0) > 0:
                next_action = "review_semantic_budget"
                rationale = (
                    "Semantic diagnosis was deferred because the frozen semantic "
                    "budget has no safely available reservation; this score is not "
                    "an optimization-ready target."
                )
        if key in prerequisite_failure_keys:
            readiness = "incomplete"
            next_action = "refresh_worker_authorization_and_resume"
            rationale = prerequisite_failure_message
            coverage_status = "incomplete"
            semantic_diagnosis_status = "required_evidence_unavailable"
        semantic_failure_projection = _semantic_failure_projection(
            _normalize_semantic_failure_category(diagnosis)
        )
        if semantic_failure_projection is not None:
            readiness = semantic_failure_projection["readiness"]
            coverage_status = semantic_failure_projection["coverage_status"]
            next_action = semantic_failure_projection["next_action"]
            rationale = semantic_failure_projection["rationale"]
        elif diagnosis and _diagnosis_result_incomplete(diagnosis):
            readiness = "incomplete"
            coverage_status = "incomplete"
            next_action = "review"
            rationale = (
                "Semantic diagnosis is incomplete without a recognized structured "
                "failure category; review the durable diagnosis evidence."
            )
        if dispatch_rejection is not None:
            readiness = "incomplete"
            next_action = "provide_valid_run_limits"
            rationale = "The approved optimizer was not launched because its run limits are invalid."
            coverage_status = "incomplete"
        trend = _stakeholder_trend(diagnosis, assessment)
        dashboard_url = _stakeholder_dashboard_url(diagnosis, assessment, row)
        evidence_count = row.get("valid_feedback_count")
        stakeholder_questions = list(diagnosis.get("stakeholder_questions") or assessment.get("stakeholder_questions") or [])
        primary_disposition = _primary_disposition(
            review=review,
            optimizer_child=optimizer_child,
            awaiting_approval=key in pending_approval_keys,
            readiness=readiness,
            collection=collection,
            guideline=guideline,
            policy_disposition=policy_disposition,
            coverage_status=coverage_status,
        )
        if dispatch_rejection is not None:
            primary_disposition = "failed_or_incomplete"
        secondary_issue_flags = _secondary_issue_flags(
            guideline=guideline,
            feedback_rubric=feedback_rubric,
            stakeholder_questions=stakeholder_questions,
            coverage_status=coverage_status,
        )
        if key in prerequisite_failure_keys:
            secondary_issue_flags = list(dict.fromkeys([
                *secondary_issue_flags,
                "required_evidence_unavailable",
            ]))
        base = {
            "rank": rank_position,
            "evidence_rank": rank_position,
            "candidate_rank": row.get("candidate_rank"),
            "scorecard_name": row.get("scorecard_name") or assessment.get("scorecard_name") or "Unlabeled scorecard",
            "score_name": row.get("score_name") or assessment.get("score_name") or "Unlabeled score",
            "scorecard_ref": _stakeholder_opaque_ref(key[0]) if key else None,
            "score_ref": _stakeholder_opaque_ref(key[1]) if key else None,
            "semantic_diagnosis_status": semantic_diagnosis_status,
        }
        portfolio_row = {
            **base,
            "valid_feedback_count": row.get("valid_feedback_count"),
            "reviewed_disagreements": row.get("reviewed_disagreements"),
            "disagreement_rate": row.get("disagreement_rate"),
            "reviewed_error_opportunity": row.get("reviewed_error_opportunity"),
            "policy_disposition": policy_disposition,
            "policy_reason": policy_reason,
            "review_disposition": (
                "selected_for_review"
                if key in selected_for_review_keys
                else policy_disposition
                if not eligible_for_optimization
                else "eligible_below_selection"
            ),
            "eligibility_timestamp": (
                (row.get("score_activity") or {}).get("eligible_at")
                if isinstance(row.get("score_activity"), Mapping)
                else None
            ),
            "coverage_status": coverage_status,
            "trend": trend,
            "collection_state": collection,
            "guideline_state": guideline,
            "feedback_rubric_state": feedback_rubric,
            "readiness": readiness,
            "promotion_readiness": promotion,
            "primary_disposition": primary_disposition,
            "secondary_issue_flags": secondary_issue_flags,
            "secondary_issue_summary": ", ".join(secondary_issue_flags) or "none",
            "rationale": rationale,
            "next_action": next_action,
            "dashboard_url": dashboard_url,
        }
        if dispatch_rejection is not None:
            portfolio_row["dispatch_rejection"] = dispatch_rejection
        portfolio.append(portfolio_row)
        if key is not None:
            projected_by_key[key] = portfolio_row
        priorities.append({
            **base, "evidence_count": evidence_count,
            "opportunity": row.get("reviewed_error_opportunity"),
            "disagreement_rate": row.get("disagreement_rate"),
            "policy_disposition": policy_disposition,
            "policy_reason": policy_reason,
            "review_disposition": (
                "selected_for_review"
                if key in selected_for_review_keys
                else policy_disposition
                if not eligible_for_optimization
                else "eligible_below_selection"
            ),
            "eligibility_timestamp": (
                (row.get("score_activity") or {}).get("eligible_at")
                if isinstance(row.get("score_activity"), Mapping)
                else None
            ),
            "state": readiness,
            "coverage_status": coverage_status, "trend": trend,
            "collection_state": collection, "readiness": readiness,
            "promotion_readiness": promotion, "rationale": rationale,
            "primary_disposition": primary_disposition,
            "secondary_issue_flags": secondary_issue_flags,
            "secondary_issue_summary": ", ".join(secondary_issue_flags) or "none",
            "next_action": next_action, "dashboard_url": dashboard_url,
        })
        if collection:
            feedback.append({
                **base, "evidence_count": evidence_count, "state": collection,
                "coverage_status": coverage_status, "trend": trend,
                "recommendation": collection, "readiness": readiness,
                "rationale": rationale, "next_action": next_action,
                "dashboard_url": dashboard_url,
            })
        questions.extend(_issue_rows(
            base={**base, "evidence_count": evidence_count},
            affected_disagreement_rate=row.get("disagreement_rate"),
            flags=secondary_issue_flags,
            guideline=guideline,
            guideline_code_conflict_claim=diagnosis.get("guideline_code_conflict_claim"),
            diagnosis_evidence_ids=diagnosis.get("evidence_ids"),
            diagnosis_evidence_fingerprint=(
                diagnosis.get("evidence_fingerprint") or diagnosis.get("fingerprint")
            ),
            feedback_rubric=feedback_rubric,
            stakeholder_questions=stakeholder_questions,
            readiness=readiness,
            coverage_status=coverage_status,
            rationale=str(rationale),
            next_action=str(next_action),
            dashboard_url=dashboard_url,
        ))
    outcomes = []
    # Optimization outcomes are a projection of the same evidence universe as
    # the portfolio, not merely the execution-eligible subset. A policy or
    # cooldown deferral has a truthful ``not_run`` outcome and must remain
    # reconcilable to its portfolio row.
    for rank_position, row in enumerate(evidence_rows, start=1):
        key = _target_key(row)
        assessment = assessments.get(key, {})
        diagnosis = diagnoses.get(key, {})
        optimizer_child = optimizer_children.get(key, {})
        launch_state = (
            optimizer_child.get("launch_state")
            if isinstance(optimizer_child.get("launch_state"), Mapping)
            else {}
        )
        launch_phase = str(launch_state.get("phase") or "")
        awaiting_semantic_diagnosis = (
            _is_ready(assessment)
            and key in all_selected_keys
            and key not in diagnoses
            and key not in reviews
            and milestone not in {"started", "ranking", "assessment"}
        )
        review = reviews.get(key, {})
        dispatch_rejection = (
            invalid_run_limits_rejection
            if key in approved_target_keys and invalid_run_limits_rejection is not None
            else None
        )
        states = {
            **(assessment.get("states") if isinstance(assessment.get("states"), Mapping) else {}),
            **(diagnosis.get("states") if isinstance(diagnosis.get("states"), Mapping) else {}),
            **(review.get("states") if isinstance(review.get("states"), Mapping) else {}),
        }
        readiness = states.get("optimization") or states.get("readiness") or "inconclusive"
        collection = states.get("feedback_collection") or assessment.get("feedback_collection_state") or "inconclusive"
        promotion = states.get("promotion_readiness") or review.get("post_run_state") or "not_evaluated"
        rationale = review.get("rationale") or diagnosis.get("rationale") or assessment.get("rationale") or "No optimizer outcome yet."
        next_action = review.get("primary_next_action") or diagnosis.get("primary_next_action") or assessment.get("primary_next_action") or "review"
        coverage_status = _stakeholder_coverage(review, diagnosis, assessment, rank)
        if awaiting_semantic_diagnosis:
            readiness = "incomplete"
            next_action = "await_semantic_diagnosis"
            rationale = "Deterministic assessment found an opportunity; semantic diagnosis is not complete for this score."
            coverage_status = "incomplete"
            if int(diagnosis_coverage.get("deferred_by_budget_count") or 0) > 0:
                next_action = "review_semantic_budget"
                rationale = (
                    "Semantic diagnosis was deferred because the frozen semantic "
                    "budget has no safely available reservation; this score is not "
                    "an optimization-ready target."
                )
        semantic_failure_projection = _semantic_failure_projection(
            _normalize_semantic_failure_category(diagnosis)
        )
        if semantic_failure_projection is not None:
            readiness = semantic_failure_projection["readiness"]
            coverage_status = semantic_failure_projection["coverage_status"]
            next_action = semantic_failure_projection["next_action"]
            rationale = semantic_failure_projection["rationale"]
        elif diagnosis and _diagnosis_result_incomplete(diagnosis):
            readiness = "incomplete"
            coverage_status = "incomplete"
            next_action = "review"
            rationale = (
                "Semantic diagnosis is incomplete without a recognized structured "
                "failure category; review the durable diagnosis evidence."
            )
        outcome = review.get("post_run_state") or "not_run"
        if dispatch_rejection is not None:
            outcome = "failed_or_incomplete"
            readiness = "incomplete"
            rationale = "The approved optimizer was not launched because its run limits are invalid."
            next_action = "provide_valid_run_limits"
            coverage_status = "incomplete"
        if not review and launch_phase:
            if launch_phase in {"waiting", "running"}:
                outcome = "optimization_in_progress"
                readiness = "optimization_in_progress"
                rationale = "The approved optimizer is running under the published resource limits."
                next_action = "wait_for_optimizer_completion"
                coverage_status = "pending"
            elif launch_phase == "terminal":
                outcome = "awaiting_optimizer_review"
                readiness = "review_pending"
                rationale = "The optimizer task is terminal and its evaluation evidence is awaiting review."
                next_action = "review_optimizer_evidence"
                coverage_status = "pending"
            elif launch_phase == "dispatch_outcome_unknown":
                outcome = "failed_or_incomplete"
                readiness = "incomplete"
                rationale = "Optimizer dispatch evidence is incomplete and requires manual recovery."
                next_action = "review_dispatch_evidence"
                coverage_status = "incomplete"
            else:
                outcome = "optimizer_launching"
                readiness = "optimizer_launching"
                rationale = "The approved optimizer is being prepared for durable task dispatch."
                next_action = "wait_for_optimizer_dispatch"
                coverage_status = "pending"
        projected = projected_by_key.get(key, {})
        primary_disposition = projected.get("primary_disposition") or _primary_disposition(
            review=review,
            optimizer_child=optimizer_child,
            awaiting_approval=key in pending_approval_keys,
            readiness=readiness,
            collection=collection,
            guideline=states.get("guideline_health") or diagnosis.get("guideline_state") or assessment.get("guideline_state") or "inconclusive",
            policy_disposition=row.get("policy_disposition") or "eligible",
            coverage_status=coverage_status,
        )
        outcome_row = {
            "rank": rank_position,
            "scorecard_name": row.get("scorecard_name") or "Unlabeled scorecard",
            "score_name": row.get("score_name") or "Unlabeled score",
            "scorecard_ref": _stakeholder_opaque_ref(key[0]) if key else None,
            "score_ref": _stakeholder_opaque_ref(key[1]) if key else None,
            "evidence_count": row.get("valid_feedback_count"),
            "outcome": outcome,
            "evidence_status": coverage_status,
            "coverage_status": coverage_status,
            "trend": _stakeholder_trend(diagnosis, assessment),
            "collection_state": collection,
            "readiness": readiness,
            "promotion_readiness": promotion,
            "primary_disposition": primary_disposition,
            "secondary_issue_flags": list(projected.get("secondary_issue_flags") or []),
            "secondary_issue_summary": projected.get("secondary_issue_summary") or "none",
            "semantic_diagnosis_status": projected.get(
                "semantic_diagnosis_status", "not_selected"
            ),
            "rationale": rationale,
            "next_action": next_action,
            "dashboard_url": _stakeholder_dashboard_url(review, diagnosis, assessment, row),
        }
        if isinstance(review.get("alignment_evidence"), Mapping):
            outcome_row["alignment_evidence"] = dict(review["alignment_evidence"])
        if dispatch_rejection is not None:
            outcome_row["dispatch_rejection"] = dispatch_rejection
        outcomes.append(outcome_row)
    questions.sort(key=lambda row: (
        int(row["issue_severity"]) if isinstance(row.get("issue_severity"), int) else 99,
        -int(row.get("affected_evidence_count") or 0),
        int(row.get("evidence_rank") or row.get("rank") or 10**9),
        str(row.get("scorecard_name") or "").casefold(),
        str(row.get("score_name") or "").casefold(),
        str(row.get("issue_flag") or ""),
    ))
    coverage = rank.get("coverage") if isinstance(rank.get("coverage"), Mapping) else {}
    scope_coverage = coverage.get("scope") if isinstance(coverage.get("scope"), Mapping) else {}
    activity_coverage = coverage.get("activity") if isinstance(coverage.get("activity"), Mapping) else {}
    diagnosis_coverage = state.get("diagnosis_coverage") if isinstance(state.get("diagnosis_coverage"), Mapping) else {}
    approved_target_count = len(state.get("approved_targets") or [])
    invalid_run_limit_target_count = (
        len(approved_target_keys) if invalid_run_limits_rejection is not None else 0
    )
    legacy_dispatched_optimizer_count = sum(
        1
        for batch in dispatch.get("batches") or []
        if isinstance(batch, Mapping)
        for row in batch.get("dispatches") or []
        if isinstance(row, Mapping) and row.get("status") == "dispatched"
    )
    child_dispatched_optimizer_count = sum(
        1
        for child in optimizer_children.values()
        if isinstance(child.get("launch_state"), Mapping)
        and child["launch_state"].get("phase") in {"waiting", "running", "terminal"}
        and child.get("procedure_id")
        and child.get("task_id")
    )
    # Old durable checkpoints recorded dispatches inside batches. New Report-
    # owned child launches record one child per target. Taking the larger count
    # preserves replay compatibility without double-counting mixed checkpoints.
    dispatched_optimizer_count = max(
        legacy_dispatched_optimizer_count,
        child_dispatched_optimizer_count,
    )
    terminal_status = str(state.get("terminal_status") or "").strip().lower()
    if terminal_status:
        current_activity, next_checkpoint = _terminal_narrative(terminal_status)
    else:
        current_activity, next_checkpoint = _milestone_narrative(
            milestone,
            execution_mode=execution_mode,
            approved_target_count=approved_target_count,
            dispatched_optimizer_count=dispatched_optimizer_count,
        )
    if invalid_run_limit_target_count:
        current_activity = (
            "Approved optimization targets were not launched because the run limits are invalid."
        )
        next_checkpoint = (
            "Provide valid run limits before requesting another approved optimizer run."
        )
    ranked_count = len(ranked_rows)
    evidence_ranked_count = len(evidence_rows)
    assessed_count = len(assessments)
    diagnosis_selected = int(diagnosis_coverage.get("selected_count") or 0)
    diagnosis_scheduled = int(diagnosis_coverage.get("scheduled_count") or 0)
    diagnosis_deferred = int(diagnosis_coverage.get("deferred_by_cap_count") or 0)
    diagnosis_completed = int(diagnosis_coverage.get("completed_count") or 0)
    diagnosis_failed = int(diagnosis_coverage.get("failed_count") or 0)
    diagnosis_incomplete = sum(
        1 for diagnosis in diagnoses.values()
        if _diagnosis_result_incomplete(diagnosis)
    )
    diagnosis_skipped = int(diagnosis_coverage.get("skipped_count") or 0)
    raw_diagnosis_max = diagnosis_coverage.get("max_semantic_diagnoses")
    diagnosis_max = int(
        DEFAULT_MAX_SEMANTIC_DIAGNOSES
        if raw_diagnosis_max is None
        else raw_diagnosis_max
    )
    diagnosis_top_priority = int(diagnosis_coverage.get("top_priority_count") or 0)
    diagnosis_monitoring = int(diagnosis_coverage.get("monitoring_candidate_count") or 0)
    priority_displayed = min(MAX_PRIORITY_DIAGNOSES, evidence_ranked_count)
    priority_cutoff_row = evidence_rows[priority_displayed - 1] if priority_displayed else {}
    inventory_coverage_status = (
        "pending" if not rank else "complete" if _coverage_complete(rank) else "incomplete"
    )
    if not rank or milestone in {"started", "ranking"}:
        analysis_coverage_status = "pending"
    elif diagnosis_prerequisite_failure_count > 0:
        analysis_coverage_status = "incomplete"
    elif diagnosis_completed < diagnosis_scheduled:
        analysis_coverage_status = "pending"
    elif (
        diagnosis_failed > 0
        or diagnosis_incomplete > 0
        or diagnosis_deferred > 0
        or diagnosis_completed < diagnosis_selected
    ):
        analysis_coverage_status = "incomplete"
    else:
        analysis_coverage_status = "complete"
    incomplete_label = "result" if diagnosis_incomplete == 1 else "results"
    primary_disposition_counts: dict[str, int] = {}
    secondary_issue_counts: dict[str, int] = {}
    for row in portfolio:
        disposition = str(row.get("primary_disposition") or "not_selected")
        primary_disposition_counts[disposition] = primary_disposition_counts.get(disposition, 0) + 1
        for flag in row.get("secondary_issue_flags") or []:
            secondary_issue_counts[str(flag)] = secondary_issue_counts.get(str(flag), 0) + 1
    semantic_budget = _semantic_budget_overview(
        state.get("semantic_budget_evidence"),
        diagnosis_coverage=diagnosis_coverage,
    )
    diagnosis_limit_reached = diagnosis_deferred > 0
    budget_exhausted_count = int(
        semantic_budget.get("semantic_budget_exhausted_count") or 0
    )
    budget_deferred_count = int(
        semantic_budget.get("semantic_budget_deferred_count") or 0
    )
    if inventory_coverage_status == "incomplete":
        analysis_incomplete_reason = "inventory_incomplete"
    elif diagnosis_prerequisite_failure_count > 0:
        analysis_incomplete_reason = "diagnosis_prerequisite_failure"
    elif budget_exhausted_count > 0 or budget_deferred_count > 0:
        analysis_incomplete_reason = "budget_exhausted"
    elif diagnosis_failed > 0:
        analysis_incomplete_reason = "diagnosis_execution_failure"
    elif diagnosis_incomplete > 0:
        analysis_incomplete_reason = "incomplete_diagnosis_evidence"
    elif diagnosis_limit_reached and diagnosis_completed >= diagnosis_scheduled:
        analysis_incomplete_reason = "configured_count_limit"
    else:
        analysis_incomplete_reason = None
    semantic_reference = semantic_budget.get("semantic_budget_evidence_reference")
    for rows in (portfolio, priorities, feedback, questions, outcomes):
        for row in rows:
            row.setdefault("semantic_diagnosis_status", "not_selected")
            row["semantic_budget_evidence_reference"] = semantic_reference
    semantic_issue_statuses = SEMANTIC_FAILURE_CATEGORIES | {"incomplete"}
    semantic_diagnosis_issues = [
        {
            "scorecard_name": str(row.get("scorecard_name") or "Unlabeled scorecard"),
            "score_name": str(row.get("score_name") or "Unlabeled score"),
            "semantic_diagnosis_status": str(row.get("semantic_diagnosis_status")),
            "next_action": str(row.get("next_action") or "review"),
            "rationale": str(row.get("rationale") or (
                "Semantic diagnosis is incomplete; review the durable diagnosis evidence."
            )),
        }
        for row in portfolio
        if str(row.get("semantic_diagnosis_status") or "") in semantic_issue_statuses
    ]
    semantic_diagnosis_issue_counts: dict[str, int] = {}
    for issue in semantic_diagnosis_issues:
        status = issue["semantic_diagnosis_status"]
        semantic_diagnosis_issue_counts[status] = (
            semantic_diagnosis_issue_counts.get(status, 0) + 1
        )
    return {
        "overview": {
            "headline": "Optimization portfolio run",
            "lifecycle_status": terminal_status or "running",
            "current_activity": current_activity,
            "next_checkpoint": next_checkpoint,
            "coverage_status": inventory_coverage_status,
            "inventory_coverage_status": inventory_coverage_status,
            "analysis_coverage_status": analysis_coverage_status,
            "execution_decision_status": (
                "complete"
                if milestone in {"approval", "optimization", "review", "finalization"}
                else "pending"
            ),
            "execution_candidate_policy": execution_candidate_policy,
            "ranking_window": str(rank.get("window") or "pending"),
            "scorecards_inspected": scope_coverage.get("total_scorecards_inspected", coverage.get("scorecards_discovered", 0)),
            "scorecards_in_scope": scope_coverage.get("matched_scorecard_count", 0),
            "evidence_ranked_score_count": evidence_ranked_count,
            "ranked_score_count": ranked_count,
            "unranked_score_count": len(rank.get("unranked") or []),
            "cooldown_excluded_count": rank.get("recent_activity_excluded_count", activity_coverage.get("recent_activity_excluded_count", 0)),
            "assessed_score_count": assessed_count,
            "assessment_progress": f"{assessed_count} of {ranked_count} eligible candidates assessed",
            "diagnosis_coverage": (
                f"{diagnosis_completed} of {diagnosis_scheduled} scheduled diagnoses returned; "
                f"{diagnosis_incomplete} incomplete {incomplete_label}; "
                f"{diagnosis_failed} execution failures; "
                f"{diagnosis_deferred} deferred by the configured diagnosis limit"
            ),
            "diagnosis_incomplete_count": diagnosis_incomplete,
            "diagnosis_completed_count": diagnosis_completed,
            "diagnosis_execution_failure_count": diagnosis_failed,
            "diagnosis_prerequisite_failure_count": diagnosis_prerequisite_failure_count,
            "diagnosis_failure_category": diagnosis_coverage.get("failure_category"),
            "diagnosis_blockers": list(diagnosis_coverage.get("blockers") or []),
            "ranking_cutoff": "none",
            "ranking_policy": "Evidence rank is calculated before policy gates. Cooldown, structural blockers, and incomplete evidence remain visible without changing that rank.",
            "priority_display_limit": MAX_PRIORITY_DIAGNOSES,
            "priority_displayed_count": priority_displayed,
            "priority_cutoff_rank": priority_displayed,
            "priority_cutoff_opportunity": priority_cutoff_row.get("reviewed_error_opportunity"),
            "ranked_below_priority_cutoff": max(evidence_ranked_count - priority_displayed, 0),
            "diagnosis_selection_policy": "The highest-ranked actionable candidates plus every actionable monitoring candidate are selected for semantic diagnosis. The configured diagnosis limit determines how many are examined in this run. Deterministic repair cases remain visible but do not consume semantic diagnosis capacity.",
            "diagnosis_top_priority_count": diagnosis_top_priority,
            "diagnosis_monitoring_candidate_count": diagnosis_monitoring,
            "diagnosis_selected_count": diagnosis_selected,
            "diagnosis_scheduled_count": diagnosis_scheduled,
            "diagnosis_deferred_count": diagnosis_deferred,
            "diagnosis_skipped_count": diagnosis_skipped,
            "diagnosis_max_count": diagnosis_max,
            "diagnosis_limit_reached": diagnosis_limit_reached,
            "diagnosis_limit_type": (
                "configured_count_limit" if diagnosis_limit_reached else None
            ),
            "diagnosis_limit_explanation": (
                f"This run was configured to diagnose at most {diagnosis_max} candidates. "
                f"The remaining {diagnosis_deferred} selected candidates were not examined "
                "and were not judged safe or unsafe."
                if diagnosis_limit_reached
                else None
            ),
            "analysis_incomplete_reason": analysis_incomplete_reason,
            "pending_approval_count": len(state.get("approval_requests") or []),
            "approved_target_count": approved_target_count,
            "invalid_run_limit_target_count": invalid_run_limit_target_count,
            "dispatched_optimizer_count": dispatched_optimizer_count,
            "optimizer_review_count": len(state.get("reviews") or []),
            "primary_disposition_counts": primary_disposition_counts,
            "secondary_issue_counts": secondary_issue_counts,
            "semantic_diagnosis_issue_count": len(semantic_diagnosis_issues),
            "semantic_diagnosis_issue_counts": semantic_diagnosis_issue_counts,
            "semantic_diagnosis_issues": semantic_diagnosis_issues,
            **semantic_budget,
            "notes": f"Latest milestone: {milestone}. No score, guideline, champion, or feedback setting is changed automatically.",
        },
        "portfolio": portfolio,
        "priorities": priorities,
        "feedback_investment": feedback,
        "questions_and_issues": questions,
        "optimization_outcomes": outcomes,
        "definitions": {
            "Coverage": "Whether the evidence is complete enough to support the stated conclusion.",
            "Primary disposition": "The single highest-priority current outcome for a score, selected using the published state precedence.",
            "Secondary issues": "Independent concerns that remain visible even when another primary outcome takes precedence.",
            "Evidence references": "The safe decision-stage artifact supporting a reported issue; detailed raw evidence remains restricted.",
            "Optimization approval": "A human decision is required before the optimizer can start.",
            "Promotion": "A separate human decision is required; this run never promotes a champion automatically.",
            "Semantic budget": "Exact authorized, settled, held, and available semantic-diagnosis spend from the frozen ledger. Dollar values are Decimal strings.",
            "Semantic budget evidence": "The immutable semantic-budget ledger revision and digest supporting the aggregate, without request or client content.",
            "Semantic budget policy version": "The Plexus policy contract governing semantic authorization and reconciliation.",
            "Semantic budget spec schema": "The schema version of the frozen semantic budget specification.",
            "Semantic ledger schema": "The schema version of the immutable semantic reservation ledger.",
            "Semantic model and pricing": "The exact provider model revision and immutable pricing version authorized by Plexus.",
        },
    }
