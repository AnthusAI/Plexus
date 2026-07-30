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
from typing import Any, Callable, Mapping, Sequence

from plexus.optimization.run_report import OptimizationRunPublicationError
from tactus.core.exceptions import ProcedureWaitingForHuman


MAX_APPROVAL_TARGETS = 5
MAX_PRIORITY_DIAGNOSES = 10
DEFAULT_MAX_SEMANTIC_DIAGNOSES = 25
DIAGNOSIS_SCOPE_POLICY_VERSION = "portfolio-diagnosis-scope-v1"
OPTIMIZATION_APPROVAL_TTL_SECONDS = 24 * 60 * 60


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
            "rank": None,
            "assessments": [],
            "diagnoses": [],
            "diagnosis_coverage": _pending_diagnosis_coverage(request),
            "dispatch": None,
            "reviews": [],
            "actions": [],
            "approval_requests": [],
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
            self._publish(service, "started", state)
            self._notify(
                state,
                event="started",
                milestone="STARTED",
                title="Optimization portfolio analysis started",
                summary="The living Report is available while exhaustive ranking proceeds.",
            )

            rank = dict(self._dependencies.rank(_with_persist_false(request)))
            state["rank"] = rank
            self._publish(service, "ranking", state)
            if not _coverage_complete(rank):
                state["summary"] = self._summary(state)
                state["terminal_status"] = "INCOMPLETE"
                self._publish(service, "finalization", state)
                _finalize(service, "INCOMPLETE")
                return self._result("INCOMPLETE", state)

            ranked_rows = _ranked_rows(rank)
            assessment_rows: list[dict[str, Any]] = []
            assessment_total = len(ranked_rows)
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

            # Ranking and assessment are deterministic and materially useful
            # on their own. Publish them before model-backed diagnosis so a
            # slow or failed semantic pass cannot hide completed evidence.
            state["assessments"] = assessment_rows
            diagnosis_targets, diagnosis_coverage = _diagnosis_selection(
                ranked_rows,
                assessment_rows,
                max_semantic_diagnoses=_max_semantic_diagnoses(request),
            )
            state["diagnosis_coverage"] = diagnosis_coverage
            self._publish(service, "assessment", state)

            if diagnosis_coverage["blockers"]:
                self._publish(service, "diagnosis", state)
                state["summary"] = self._summary(state)
                state["terminal_status"] = "INCOMPLETE"
                self._publish(service, "finalization", state)
                _finalize(service, "INCOMPLETE")
                return self._result("INCOMPLETE", state)

            diagnosis_rows: list[dict[str, Any]] = []
            diagnosis_total = assessment_total + len(diagnosis_targets)
            service.publish_progress(
                phase="diagnosis",
                current=assessment_total,
                total=diagnosis_total,
                message=(
                    f"Starting semantic diagnosis for {len(diagnosis_targets)} "
                    "selected scores."
                ),
            )
            for diagnosis_index, (row, assessment) in enumerate(diagnosis_targets, start=1):
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
                        "persist": False,
                    }))
                except Exception:
                    diagnosis_coverage["failed_count"] += 1
                    diagnosis_coverage["selected_scope_complete"] = False
                    state["diagnoses"] = diagnosis_rows
                    raise
                if assessment.get("scorecard_name") and not diagnosis.get("scorecard_name"):
                    diagnosis["scorecard_name"] = assessment["scorecard_name"]
                if assessment.get("score_name") and not diagnosis.get("score_name"):
                    diagnosis["score_name"] = assessment["score_name"]
                diagnosis_rows.append(diagnosis)
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
            diagnosis_coverage["selected_scope_complete"] = (
                diagnosis_coverage["completed_count"] == diagnosis_coverage["selected_count"]
                and diagnosis_coverage["failed_count"] == 0
            )
            self._publish(service, "diagnosis", state)
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
            ready = _ready_targets(assessment_rows, diagnosis_rows)
            batches = [ready[index:index + MAX_APPROVAL_TARGETS] for index in range(0, len(ready), MAX_APPROVAL_TARGETS)]
            review_requests = [
                _approval_request(
                    run_key=run_key,
                    account_id=account_id,
                    batch_number=index,
                    targets=batch,
                    report_ref=state["report_ref"],
                )
                for index, batch in enumerate(batches, start=1)
            ]
            # Publish the pending decisions before invoking Human.review.  A
            # real Tactus adapter suspends at that call, so publishing only
            # afterward would leave the living Report claiming diagnosis was
            # still in progress for the entire human wait.
            state["approval_requests"] = list(review_requests)
            state["actions"] = action_rows
            self._publish(service, "approval", state)
            if action_rows or review_requests:
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
            for batch, review_request in zip(batches, review_requests):
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
            if pending_approval_requests and len(pending_approval_requests) != len(review_requests):
                self._publish(service, "approval", state)

            # A Tactus procedure may deliberately request the first action,
            # checkpoint, and call us again with its authoritative response.
            # Keep this Report/Task running; treating an unanswered action as
            # terminal would prevent ordinary replay from resuming the same URL.
            unresolved_approval = bool(pending_approval_requests)
            if request.get("wait_for_human") is True and unresolved_approval:
                return self._result("WAITING_FOR_APPROVAL", state)

            self._publish(service, "optimization", state)
            dispatches: list[dict[str, Any]] = []
            rejected: list[dict[str, Any]] = []
            for batch in _chunks(approvals, MAX_APPROVAL_TARGETS):
                dispatch = dict(self._dependencies.dispatch({
                    "account_id": account_id,
                    "approved": True,
                    "targets": batch,
                    "persist": False,
                    **limits,
                }))
                dispatches.append(dispatch)
                rejected.extend(
                    item for item in (dispatch.get("rejected") or []) if isinstance(item, Mapping)
                )
            state["dispatch"] = {"batches": dispatches, "rejected": rejected}
            # Make procedure IDs and launch rejections visible before any
            # potentially long terminal-evidence review.
            self._publish(service, "optimization", state)

            # Only a successfully dispatched optimizer procedure may reach
            # review.  In particular, stale evidence never becomes a promotion
            # candidate merely because it was approved by a human earlier.
            review_rows: list[dict[str, Any]] = []
            if not rejected:
                for dispatch in dispatches:
                    for row in dispatch.get("dispatches") or []:
                        if not isinstance(row, Mapping) or row.get("status") != "dispatched":
                            continue
                        procedure_id = _procedure_id(row)
                        if not procedure_id:
                            continue
                        reviewed = dict(self._dependencies.review({
                            "account_id": account_id,
                            "procedure_id": procedure_id,
                            "persist": False,
                        }))
                        review_rows.append(reviewed)
                        if reviewed.get("promotion_ready") is True:
                            target = _target_for_procedure(row, approvals)
                            if target is not None:
                                state["promotion_candidates"].append(target)
                                if self._dependencies.create_action is not None:
                                    promotion = {"kind": "promotion_approval", **target}
                                    action_rows.append(_recorded_action(
                                        promotion,
                                        self._dependencies.create_action(_promotion_action(
                                            target, account_id=account_id, run_key=run_key,
                                            report_ref=state["report_ref"], procedure_id=procedure_id,
                                        )),
                                    ))
            state["reviews"] = review_rows
            state["summary"] = self._summary(state)
            self._publish(service, "optimization_review", state)

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
        except OptimizationRunPublicationError as exc:
            # Publication is a safety boundary: never execute ahead of the
            # stakeholder-visible Report.  `fail` itself is best effort.
            try:
                service.fail(f"Report publication failed: {exc}")
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
        return dict(self._dependencies.summary({"packets": packets, "persist": False}))

    def _publish(self, service: Any, milestone: str, state: Mapping[str, Any]) -> None:
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
    def _result(status: str, state: Mapping[str, Any], *, error: str | None = None) -> dict[str, Any]:
        result = {
            "status": status,
            "run_key": state["run_key"],
            "promotion_candidates": list(state.get("promotion_candidates") or []),
            "rank": state.get("rank"),
            "summary": state.get("summary"),
            "diagnosis_coverage": dict(state.get("diagnosis_coverage") or {}),
            "actions": state.get("actions") or [],
            "approval_requests": state.get("approval_requests") or [],
            "dispatch": state.get("dispatch"),
            "reviews": state.get("reviews") or [],
        }
        if error:
            result["error"] = error
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
        "toolchain_version": request.get("toolchain_version"),
    }
    return "optimization-" + sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:24]


def _run_spec(request: Mapping[str, Any], *, account_id: str, run_key: str) -> dict[str, Any]:
    return {
        "run_key": run_key,
        "account_id": account_id,
        "scope": request.get("scope") or {
            key: request[key] for key in ("scorecard_ids", "scorecard_name_prefixes") if key in request
        },
        "window": request.get("window") or {},
        "policy_versions": request.get("policy_versions") or {},
        "toolchain_version": request.get("toolchain_version") or "unknown",
    }


def _with_persist_false(value: Mapping[str, Any]) -> dict[str, Any]:
    return {**dict(value), "persist": False}


def _coverage_complete(packet: Mapping[str, Any]) -> bool:
    coverage = packet.get("coverage")
    return isinstance(coverage, Mapping) and coverage.get("complete") is True


def _ranked_rows(rank: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = rank.get("ranked") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _pending_diagnosis_coverage(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "policy_version": DIAGNOSIS_SCOPE_POLICY_VERSION,
        "ranked_count": 0,
        "top_priority_count": 0,
        "monitoring_candidate_count": 0,
        "overlap_count": 0,
        "selected_count": 0,
        "completed_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "max_semantic_diagnoses": _max_semantic_diagnoses(request),
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
    selected_keys = (top_priority_keys | monitoring_keys) - {None}
    selected = [
        (row, assessment)
        for row, assessment in paired
        if _target_key(row) in selected_keys
    ]
    blockers: list[dict[str, Any]] = []
    if len(selected) > max_semantic_diagnoses:
        blockers.append({
            "code": "semantic_diagnosis_limit_exceeded",
            "selected_count": len(selected),
            "max_semantic_diagnoses": max_semantic_diagnoses,
        })
    coverage = {
        "policy_version": DIAGNOSIS_SCOPE_POLICY_VERSION,
        "ranked_count": len(paired),
        "top_priority_count": min(MAX_PRIORITY_DIAGNOSES, len(paired)),
        "monitoring_candidate_count": len(monitoring_keys - {None}),
        "overlap_count": len((top_priority_keys & monitoring_keys) - {None}),
        "selected_count": len(selected),
        "completed_count": 0,
        "failed_count": 0,
        "skipped_count": len(paired) - len(selected),
        "max_semantic_diagnoses": max_semantic_diagnoses,
        "selected_scope_complete": False,
        "portfolio_semantic_complete": len(selected) == len(paired),
        "blockers": blockers,
    }
    return selected, coverage


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


def _approval_request(*, run_key: str, account_id: str, batch_number: int, targets: Sequence[Mapping[str, Any]], report_ref: Mapping[str, Any]) -> dict[str, Any]:
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


def _terminal_status(state: Mapping[str, Any], *, has_unresolved_actions: bool) -> str:
    rank = state.get("rank")
    if not isinstance(rank, Mapping) or not _coverage_complete(rank):
        return "INCOMPLETE"
    dispatch = state.get("dispatch") or {}
    if (dispatch.get("rejected") or []):
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


def _evidence_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    rank = state.get("rank")
    coverage = rank.get("coverage") if isinstance(rank, Mapping) else {"complete": False, "failures": ["ranking not yet available"]}
    return {
        "run_key": state["run_key"],
        "terminal_status": state.get("terminal_status"),
        "coverage": dict(coverage or {}),
        "rank": state.get("rank"),
        "assessments": list(state.get("assessments") or []),
        "diagnoses": list(state.get("diagnoses") or []),
        "diagnosis_coverage": dict(state.get("diagnosis_coverage") or {}),
        "actions": list(state.get("actions") or []),
        "approval_requests": list(state.get("approval_requests") or []),
        "dispatch": state.get("dispatch"),
        "reviews": list(state.get("reviews") or []),
        "summary": state.get("summary"),
    }


def _stakeholder_coverage(*packets: Mapping[str, Any]) -> str:
    for packet in packets:
        if not isinstance(packet, Mapping):
            continue
        coverage = packet.get("coverage")
        if isinstance(coverage, Mapping) and "complete" in coverage:
            return "complete" if coverage.get("complete") is True else "incomplete"
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


def _milestone_narrative(milestone: str) -> tuple[str, str]:
    narratives = {
        "started": (
            "Enumerating every scorecard and analyzing the frozen feedback window.",
            "A ranked portfolio will be published after exhaustive coverage is verified.",
        ),
        "ranking": (
            "Applying deterministic readiness and feedback-investment checks to every ranked score.",
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
            "The run ended with incomplete evidence.",
            "Review the documented coverage failures before relying on its conclusions.",
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


def _stakeholder_view(state: Mapping[str, Any], *, milestone: str) -> dict[str, Any]:
    rank = state.get("rank") if isinstance(state.get("rank"), Mapping) else {}
    assessments = {_target_key(row): row for row in state.get("assessments") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    diagnoses = {_target_key(row): row for row in state.get("diagnoses") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    reviews = {_target_key(row): row for row in state.get("reviews") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    portfolio: list[dict[str, Any]] = []
    priorities: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    ranked_rows = _ranked_rows(rank)
    for rank_position, row in enumerate(ranked_rows, start=1):
        key = _target_key(row)
        assessment = assessments.get(key, {})
        diagnosis = diagnoses.get(key, {})
        awaiting_semantic_diagnosis = (
            _is_ready(assessment)
            and key not in diagnoses
            and milestone not in {"started", "ranking", "assessment"}
        )
        review = reviews.get(key, {})
        states = {
            **(assessment.get("states") if isinstance(assessment.get("states"), Mapping) else {}),
            **(diagnosis.get("states") if isinstance(diagnosis.get("states"), Mapping) else {}),
            **(review.get("states") if isinstance(review.get("states"), Mapping) else {}),
        }
        readiness = states.get("optimization") or states.get("readiness") or assessment.get("readiness_state") or "inconclusive"
        next_action = diagnosis.get("primary_next_action") or assessment.get("primary_next_action") or "review"
        collection = states.get("feedback_collection") or diagnosis.get("feedback_collection_state") or assessment.get("feedback_collection_state") or "inconclusive"
        guideline = states.get("guideline_health") or diagnosis.get("guideline_state") or assessment.get("guideline_state") or "inconclusive"
        feedback_rubric = states.get("feedback_rubric_health") or states.get("feedback_rubric") or diagnosis.get("feedback_rubric_state") or assessment.get("feedback_rubric_state") or "inconclusive"
        promotion = states.get("promotion_readiness") or review.get("post_run_state") or "not_evaluated"
        rationale = diagnosis.get("rationale") or assessment.get("rationale") or "Evidence-based priority."
        coverage_status = _stakeholder_coverage(diagnosis, assessment, rank)
        if awaiting_semantic_diagnosis:
            readiness = "incomplete"
            next_action = "await_semantic_diagnosis"
            rationale = "Deterministic assessment found an opportunity; semantic diagnosis is not complete for this score."
            coverage_status = "incomplete"
        trend = _stakeholder_trend(diagnosis, assessment)
        dashboard_url = _stakeholder_dashboard_url(diagnosis, assessment, row)
        evidence_count = row.get("valid_feedback_count")
        base = {
            "rank": rank_position,
            "scorecard_name": row.get("scorecard_name") or assessment.get("scorecard_name") or "Unlabeled scorecard",
            "score_name": row.get("score_name") or assessment.get("score_name") or "Unlabeled score",
            "scorecard_ref": sha256(key[0].encode("utf-8")).hexdigest()[:16] if key else None,
        }
        portfolio.append({
            **base,
            "valid_feedback_count": row.get("valid_feedback_count"),
            "reviewed_disagreements": row.get("reviewed_disagreements"),
            "disagreement_rate": row.get("disagreement_rate"),
            "reviewed_error_opportunity": row.get("reviewed_error_opportunity"),
            "coverage_status": coverage_status,
            "trend": trend,
            "collection_state": collection,
            "guideline_state": guideline,
            "feedback_rubric_state": feedback_rubric,
            "readiness": readiness,
            "promotion_readiness": promotion,
            "rationale": rationale,
            "next_action": next_action,
            "dashboard_url": dashboard_url,
        })
        priorities.append({
            **base, "evidence_count": evidence_count,
            "opportunity": row.get("reviewed_error_opportunity"),
            "disagreement_rate": row.get("disagreement_rate"),
            "state": readiness,
            "coverage_status": coverage_status, "trend": trend,
            "collection_state": collection, "readiness": readiness,
            "promotion_readiness": promotion, "rationale": rationale,
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
        for finding in diagnosis.get("stakeholder_questions") or []:
            questions.append({
                "kind": "stakeholder question", **base, "evidence_count": evidence_count,
                "state": readiness, "coverage_status": coverage_status,
                "guideline_state": guideline, "feedback_rubric_state": feedback_rubric,
                "finding": finding, "rationale": rationale, "next_action": "answer_question",
                "dashboard_url": dashboard_url,
            })
        if guideline in {"missing", "invalid", "potential_code_conflict"}:
            questions.append({
                "kind": "guideline or rubric", **base, "evidence_count": evidence_count,
                "state": guideline, "coverage_status": coverage_status,
                "guideline_state": guideline, "feedback_rubric_state": feedback_rubric,
                "finding": guideline, "rationale": rationale, "next_action": next_action,
                "dashboard_url": dashboard_url,
            })
    outcomes = []
    for rank_position, row in enumerate(ranked_rows, start=1):
        key = _target_key(row)
        assessment = assessments.get(key, {})
        diagnosis = diagnoses.get(key, {})
        awaiting_semantic_diagnosis = (
            _is_ready(assessment)
            and key not in diagnoses
            and milestone not in {"started", "ranking", "assessment"}
        )
        review = reviews.get(key, {})
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
        outcomes.append({
            "rank": rank_position,
            "scorecard_name": row.get("scorecard_name") or "Unlabeled scorecard",
            "score_name": row.get("score_name") or "Unlabeled score",
            "scorecard_ref": sha256(key[0].encode("utf-8")).hexdigest()[:16] if key else None,
            "evidence_count": row.get("valid_feedback_count"),
            "outcome": review.get("post_run_state") or "not_run",
            "evidence_status": coverage_status,
            "coverage_status": coverage_status,
            "trend": _stakeholder_trend(diagnosis, assessment),
            "collection_state": collection,
            "readiness": readiness,
            "promotion_readiness": promotion,
            "rationale": rationale,
            "next_action": next_action,
            "dashboard_url": _stakeholder_dashboard_url(review, diagnosis, assessment, row),
        })
    coverage = rank.get("coverage") if isinstance(rank.get("coverage"), Mapping) else {}
    scope_coverage = coverage.get("scope") if isinstance(coverage.get("scope"), Mapping) else {}
    activity_coverage = coverage.get("activity") if isinstance(coverage.get("activity"), Mapping) else {}
    diagnosis_coverage = state.get("diagnosis_coverage") if isinstance(state.get("diagnosis_coverage"), Mapping) else {}
    terminal_status = str(state.get("terminal_status") or "").strip().lower()
    if terminal_status:
        current_activity, next_checkpoint = _terminal_narrative(terminal_status)
    else:
        current_activity, next_checkpoint = _milestone_narrative(milestone)
    ranked_count = len(ranked_rows)
    assessed_count = len(assessments)
    diagnosis_selected = int(diagnosis_coverage.get("selected_count") or 0)
    diagnosis_completed = int(diagnosis_coverage.get("completed_count") or 0)
    diagnosis_failed = int(diagnosis_coverage.get("failed_count") or 0)
    diagnosis_skipped = int(diagnosis_coverage.get("skipped_count") or 0)
    raw_diagnosis_max = diagnosis_coverage.get("max_semantic_diagnoses")
    diagnosis_max = int(
        DEFAULT_MAX_SEMANTIC_DIAGNOSES
        if raw_diagnosis_max is None
        else raw_diagnosis_max
    )
    diagnosis_top_priority = int(diagnosis_coverage.get("top_priority_count") or 0)
    diagnosis_monitoring = int(diagnosis_coverage.get("monitoring_candidate_count") or 0)
    priority_displayed = min(MAX_PRIORITY_DIAGNOSES, ranked_count)
    priority_cutoff_row = ranked_rows[priority_displayed - 1] if priority_displayed else {}
    coverage_status = (
        "pending" if not rank else "complete" if _coverage_complete(rank) else "incomplete"
    )
    return {
        "overview": {
            "headline": "Optimization portfolio run",
            "lifecycle_status": terminal_status or "running",
            "current_activity": current_activity,
            "next_checkpoint": next_checkpoint,
            "coverage_status": coverage_status,
            "ranking_window": str(rank.get("window") or "pending"),
            "scorecards_inspected": scope_coverage.get("total_scorecards_inspected", coverage.get("scorecards_discovered", 0)),
            "scorecards_in_scope": scope_coverage.get("matched_scorecard_count", 0),
            "ranked_score_count": ranked_count,
            "unranked_score_count": len(rank.get("unranked") or []),
            "cooldown_excluded_count": rank.get("recent_activity_excluded_count", activity_coverage.get("recent_activity_excluded_count", 0)),
            "assessment_progress": f"{assessed_count} of {ranked_count} ranked scores complete",
            "diagnosis_coverage": f"{diagnosis_completed} of {diagnosis_selected} selected diagnoses complete; {diagnosis_failed} failed",
            "ranking_cutoff": "none",
            "ranking_policy": "All eligible scores are ranked by reviewed disagreements; no ranking cutoff is applied.",
            "priority_display_limit": MAX_PRIORITY_DIAGNOSES,
            "priority_displayed_count": priority_displayed,
            "priority_cutoff_rank": priority_displayed,
            "priority_cutoff_opportunity": priority_cutoff_row.get("reviewed_error_opportunity"),
            "ranked_below_priority_cutoff": max(ranked_count - priority_displayed, 0),
            "diagnosis_selection_policy": "The highest-ranked opportunities plus every monitoring candidate receive semantic diagnosis, subject to the safety cap.",
            "diagnosis_top_priority_count": diagnosis_top_priority,
            "diagnosis_monitoring_candidate_count": diagnosis_monitoring,
            "diagnosis_selected_count": diagnosis_selected,
            "diagnosis_skipped_count": diagnosis_skipped,
            "diagnosis_max_count": diagnosis_max,
            "pending_approval_count": len(state.get("approval_requests") or []),
            "notes": f"Latest milestone: {milestone}. No score, guideline, champion, or feedback setting is changed automatically.",
        },
        "portfolio": portfolio,
        "priorities": priorities,
        "feedback_investment": feedback,
        "questions_and_issues": questions,
        "optimization_outcomes": outcomes,
        "definitions": {
            "Coverage": "Whether the evidence is complete enough to support the stated conclusion.",
            "Optimization approval": "A human decision is required before the optimizer can start.",
            "Promotion": "A separate human decision is required; this run never promotes a champion automatically.",
        },
    }
