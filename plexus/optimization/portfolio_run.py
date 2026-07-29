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
            "dispatch": None,
            "reviews": [],
            "actions": [],
            "approval_requests": [],
            "promotion_candidates": [],
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

            rank = dict(self._dependencies.rank(_with_persist_false(request)))
            state["rank"] = rank
            if not _coverage_complete(rank):
                self._publish(service, "ranking_assessment", state)
                state["summary"] = self._summary(state)
                self._publish(service, "finalization", state)
                _finalize(service, "INCOMPLETE")
                return self._result("INCOMPLETE", state)

            ranked_rows = _ranked_rows(rank)
            assessment_rows: list[dict[str, Any]] = []
            for row in ranked_rows:
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

            # Ranking and assessment are deterministic and materially useful
            # on their own. Publish them before model-backed diagnosis so a
            # slow or failed semantic pass cannot hide completed evidence.
            state["assessments"] = assessment_rows
            self._publish(service, "ranking_assessment", state)

            diagnosis_rows: list[dict[str, Any]] = []
            for row, assessment in zip(ranked_rows, assessment_rows):
                scorecard_id, score_id = _exact_target(row)
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
                diagnosis_rows.append(diagnosis)

            state["diagnoses"] = diagnosis_rows
            self._publish(service, "diagnosis", state)

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
            submitted_approvals = request.get("approval_responses")
            has_submitted_approvals = "approval_responses" in request
            approvals: list[dict[str, Any]] = []
            pending_approval_requests: list[dict[str, Any]] = []
            for index, batch in enumerate(batches, start=1):
                review_request = _approval_request(
                    run_key=run_key,
                    account_id=account_id,
                    batch_number=index,
                    targets=batch,
                    report_ref=state["report_ref"],
                )
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
            self._publish(service, "approval", state)

            # A Tactus procedure may deliberately request the first action,
            # checkpoint, and call us again with its authoritative response.
            # Keep this Report/Task running; treating an unanswered action as
            # terminal would prevent ordinary replay from resuming the same URL.
            unresolved_approval = bool(pending_approval_requests)
            if request.get("wait_for_human") is True and unresolved_approval:
                return self._result("WAITING_FOR_APPROVAL", state)

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
            self._publish(service, "finalization", state)

            status = _terminal_status(
                state,
                has_unresolved_actions=bool(_non_launch_actions(diagnosis_rows) or unresolved_approval),
            )
            _finalize(service, status)
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

    @staticmethod
    def _result(status: str, state: Mapping[str, Any], *, error: str | None = None) -> dict[str, Any]:
        result = {
            "status": status,
            "run_key": state["run_key"],
            "promotion_candidates": list(state.get("promotion_candidates") or []),
            "rank": state.get("rank"),
            "summary": state.get("summary"),
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
        # A diagnosis may be a legacy packet that preserves only the assessment
        # readiness.  It must not override that ready state with an absence.
        if diagnosis is not None and not _diagnosis_permits_launch(diagnosis):
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
    states = packet.get("states")
    readiness = states.get("optimization", states.get("readiness")) if isinstance(states, Mapping) else packet.get("readiness_state")
    return _coverage_complete(packet) and readiness == "ready_to_optimize"


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
            actions.append({"kind": "stakeholder_clarification", "scorecard_id": key[0], "score_id": key[1], "questions": list(questions)})
        states = packet.get("states") if isinstance(packet.get("states"), Mapping) else {}
        feedback = states.get("feedback_collection") or packet.get("feedback_collection_state")
        if feedback in {"reduce_to_periodic_monitoring", "collect_targeted_classes", "pause_pending_repair_or_clarification"}:
            actions.append({"kind": "feedback_collection_review", "scorecard_id": key[0], "score_id": key[1], "recommendation": feedback})
    return actions


def _action_request_for_finding(
    action: Mapping[str, Any], *, account_id: str, run_key: str, report_ref: Mapping[str, Any]
) -> dict[str, Any]:
    kind = str(action["kind"])
    scorecard_id, score_id = str(action["scorecard_id"]), str(action["score_id"])
    if kind == "stakeholder_clarification":
        expiry, schema = None, {"type": "object", "required": ["response"], "properties": {"response": {"type": "string"}}}
    else:
        expiry, schema = None, {"type": "object", "required": ["decision"], "properties": {"decision": {"enum": ["acknowledge", "defer"]}}}
    return {
        "action_key": f"{kind}:{run_key}:{scorecard_id}:{score_id}", "kind": kind,
        "account_id": account_id, "title": kind.replace("_", " ").title(),
        "resource_refs": [dict(report_ref), {"system": "plexus", "kind": "score", "id": score_id, "scorecardId": scorecard_id}],
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
        "coverage": dict(coverage or {}),
        "rank": state.get("rank"),
        "assessments": list(state.get("assessments") or []),
        "diagnoses": list(state.get("diagnoses") or []),
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


def _stakeholder_view(state: Mapping[str, Any], *, milestone: str) -> dict[str, Any]:
    rank = state.get("rank") if isinstance(state.get("rank"), Mapping) else {}
    assessments = {_target_key(row): row for row in state.get("assessments") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    diagnoses = {_target_key(row): row for row in state.get("diagnoses") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    reviews = {_target_key(row): row for row in state.get("reviews") or [] if isinstance(row, Mapping) and _target_key(row) is not None}
    portfolio: list[dict[str, Any]] = []
    priorities: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for row in _ranked_rows(rank):
        key = _target_key(row)
        assessment = assessments.get(key, {})
        diagnosis = diagnoses.get(key, {})
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
        trend = _stakeholder_trend(diagnosis, assessment)
        dashboard_url = _stakeholder_dashboard_url(diagnosis, assessment, row)
        evidence_count = row.get("valid_feedback_count")
        base = {
            "scorecard_name": row.get("scorecard_name") or assessment.get("scorecard_name") or "Unlabeled scorecard",
            "score_name": row.get("score_name") or assessment.get("score_name") or "Unlabeled score",
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
            "opportunity": row.get("reviewed_error_opportunity"), "state": readiness,
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
    for row in _ranked_rows(rank):
        key = _target_key(row)
        assessment = assessments.get(key, {})
        diagnosis = diagnoses.get(key, {})
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
        outcomes.append({
            "scorecard_name": row.get("scorecard_name") or "Unlabeled scorecard",
            "score_name": row.get("score_name") or "Unlabeled score",
            "evidence_count": row.get("valid_feedback_count"),
            "outcome": review.get("post_run_state") or "not_run",
            "evidence_status": _stakeholder_coverage(review, diagnosis, assessment, rank),
            "coverage_status": _stakeholder_coverage(review, diagnosis, assessment, rank),
            "trend": _stakeholder_trend(diagnosis, assessment),
            "collection_state": collection,
            "readiness": readiness,
            "promotion_readiness": promotion,
            "rationale": rationale,
            "next_action": next_action,
            "dashboard_url": _stakeholder_dashboard_url(review, diagnosis, assessment, row),
        })
    return {
        "overview": {
            "headline": "Optimization portfolio run",
            "coverage_status": "complete" if _coverage_complete(rank) else "incomplete",
            "ranking_window": str(rank.get("window") or "pending"),
            "ranked_score_count": len(_ranked_rows(rank)),
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
