"""At-most-once, TaskDispatcher-backed optimizer child launch state machine.

This module does not publish Reports.  The portfolio runner owns publication
and calls :meth:`OptimizerTaskDispatchService.step` only after the current
state has been committed to the living Report.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from numbers import Real
from typing import Any, Mapping


TERMINAL_PHASES = frozenset({
    "waiting", "running", "terminal", "dispatch_outcome_unknown",
})

_PROCEDURE_NAME = "Feedback alignment optimizer"
_PROCEDURE_CATEGORY = "optimizer"
_PROCEDURE_VERSION = "optimizer-task-dispatch-v1"


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)


def _launch_spec(request: Mapping[str, Any]) -> dict[str, Any]:
    limits = dict(request.get("limits") or {})
    required_limits = (
        "max_cost_usd", "max_samples", "max_iterations", "max_concurrency",
    )
    missing = [key for key in required_limits if limits.get(key) is None]
    if missing:
        raise ValueError(f"optimizer launch limits are incomplete: {', '.join(missing)}")
    max_cost_usd = limits["max_cost_usd"]
    if (
        isinstance(max_cost_usd, bool)
        or not isinstance(max_cost_usd, Real)
        or not isfinite(float(max_cost_usd))
        or float(max_cost_usd) <= 0
    ):
        raise ValueError("optimizer launch max_cost_usd must be a positive finite real number")
    optimizer_yaml = str(request.get("optimizer_yaml") or "")
    if not optimizer_yaml:
        raise ValueError("optimizer_yaml is required")
    spec = {
        "version": "optimizer-task-dispatch-v1",
        "account_id": str(request.get("account_id") or ""),
        "run_key": str(request.get("run_key") or ""),
        "scorecard_id": str(request.get("scorecard_id") or ""),
        "score_id": str(request.get("score_id") or ""),
        "assessment_fingerprint": str(request.get("assessment_fingerprint") or ""),
        "limits": {key: limits[key] for key in required_limits},
        "optimizer_yaml_sha256": sha256(optimizer_yaml.encode("utf-8")).hexdigest(),
    }
    if any(not spec[key] for key in (
        "account_id", "run_key", "scorecard_id", "score_id", "assessment_fingerprint",
    )):
        raise ValueError("optimizer launch identity is incomplete")
    spec["identity"] = sha256(_canonical(spec).encode("utf-8")).hexdigest()
    return spec


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("malformed launch metadata") from exc
        if isinstance(parsed, Mapping):
            return dict(parsed)
    raise ValueError("malformed launch metadata")


def _unknown(state: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        **dict(state),
        "phase": "dispatch_outcome_unknown",
        "complete": False,
        "reason": reason,
        "requires_manual_recovery": True,
    }


class OptimizerTaskDispatchService:
    """Perform one read or mutation step after Report publication."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def step(
        self,
        request: Mapping[str, Any],
        state: Mapping[str, Any] | None,
        *,
        may_mutate: bool,
    ) -> dict[str, Any]:
        state = dict(state or {})
        if not state:
            return {
                "phase": "planned",
                "complete": False,
                "launch_spec": _launch_spec(request),
            }
        expected_spec = _launch_spec(request)
        if state.get("launch_spec") != expected_spec:
            raise ValueError("optimizer launch state does not match the frozen request")
        phase = str(state.get("phase") or "")
        if phase in TERMINAL_PHASES:
            if state.get("task_id"):
                return self._observe_task(state)
            return state
        if phase == "planned":
            return {**state, "phase": "procedure_create_attempted"}
        if phase == "procedure_create_attempted":
            return self._create_or_adopt_procedure(state, may_mutate=may_mutate)
        if phase == "procedure_record_observed":
            return self._provision_procedure(
                request, state, may_mutate=may_mutate,
            )
        if phase == "procedure_provisioned":
            return {**state, "phase": "task_create_attempted"}
        if phase == "task_create_attempted":
            return self._create_or_adopt_task(state, may_mutate=may_mutate)
        if phase == "task_record_observed":
            return self._hold_verified_task(
                request, state, may_mutate=may_mutate,
            )
        if phase == "task_stage_reconcile_attempted":
            return self._hold_verified_task(
                request, state, may_mutate=may_mutate,
            )
        if phase == "task_held":
            return {**state, "phase": "release_attempted"}
        if phase == "release_attempted":
            try:
                task = self._backend.get_task(str(state["task_id"]))
            except Exception:
                return _unknown(state, "task_readback_failed")
            failure = self._validate_task_record(task, state)
            if failure:
                return _unknown(state, failure)
            if may_mutate and task.get("dispatchStatus") == "HELD":
                try:
                    self._backend.release_held_task(str(state["task_id"]))
                except Exception:
                    # The update may have succeeded. Observation below is the
                    # only safe recovery action; this step never releases twice.
                    pass
            return self._observe_task(state)
        raise ValueError(f"unsupported optimizer dispatch phase: {phase}")

    def _create_or_adopt_procedure(
        self, state: Mapping[str, Any], *, may_mutate: bool,
    ) -> dict[str, Any]:
        record = {
            "accountId": state["launch_spec"]["account_id"],
            "scorecardId": state["launch_spec"]["scorecard_id"],
            "scoreId": state["launch_spec"]["score_id"],
            "name": _PROCEDURE_NAME,
            "category": _PROCEDURE_CATEGORY,
            "version": _PROCEDURE_VERSION,
            "featured": False,
            "isTemplate": False,
            "status": "RUNNING",
            "metadata": {"optimizer_launch_spec": state["launch_spec"]},
        }
        if may_mutate:
            procedure, failure = self._find_exact(
                self._backend.procedure_pages_for_account(
                    state["launch_spec"]["account_id"]
                ),
                state["launch_spec"],
                kind="procedure",
            )
            if failure == "no_exact_procedure_match":
                try:
                    procedure = self._backend.create_procedure(record)
                except Exception:
                    procedure, failure = self._find_exact(
                        self._backend.procedure_pages_for_account(
                            state["launch_spec"]["account_id"]
                        ),
                        state["launch_spec"],
                        kind="procedure",
                    )
                    if failure:
                        return _unknown(state, failure)
            elif failure:
                return _unknown(state, failure)
        else:
            procedure, failure = self._find_exact(
                self._backend.procedure_pages_for_account(
                    state["launch_spec"]["account_id"]
                ),
                state["launch_spec"],
                kind="procedure",
            )
            if failure:
                return _unknown(state, failure)
        if not isinstance(procedure, Mapping) or not procedure.get("id"):
            return _unknown(state, "malformed_procedure_create_result")
        failure = self._validate_procedure_record(procedure, state)
        if failure:
            return _unknown(state, failure)
        return {
            **state,
            "phase": "procedure_record_observed",
            "procedure_id": str(procedure["id"]),
            "procedure": dict(procedure),
        }

    def _provision_procedure(
        self,
        request: Mapping[str, Any],
        state: Mapping[str, Any],
        *,
        may_mutate: bool,
    ) -> dict[str, Any]:
        procedure_id = str(state.get("procedure_id") or "")
        if not procedure_id:
            return _unknown(state, "malformed_procedure_record")
        try:
            procedure = self._backend.get_procedure(procedure_id)
        except Exception:
            return _unknown(state, "procedure_readback_failed")
        failure = self._validate_procedure_record(procedure, state)
        if failure:
            return _unknown(state, failure)
        procedure = dict(procedure)
        try:
            metadata = _metadata(procedure.get("metadata"))
        except ValueError:
            return _unknown(state, "malformed_procedure_metadata")
        pointer = metadata.get("code_artifact")
        if pointer is None:
            if not may_mutate:
                return _unknown(state, "procedure_attachment_outcome_unknown")
            try:
                self._backend.upload_and_verify_procedure_yaml(
                    procedure,
                    str(request["optimizer_yaml"]),
                    {
                        "optimizer_launch_spec": state["launch_spec"],
                        "optimizer_yaml_sha256": state["launch_spec"]["optimizer_yaml_sha256"],
                    },
                )
            except Exception:
                return _unknown(state, "procedure_attachment_outcome_unknown")
            try:
                procedure = self._backend.get_procedure(procedure_id)
            except Exception:
                return _unknown(state, "procedure_readback_failed")
            failure = self._validate_procedure_record(procedure, state)
            if failure:
                return _unknown(state, failure)
            procedure = dict(procedure)
            try:
                metadata = _metadata(procedure.get("metadata"))
            except ValueError:
                return _unknown(state, "malformed_procedure_metadata")
            pointer = metadata.get("code_artifact")
        if not self._verify_procedure_artifact(
            procedure, metadata, pointer, state["launch_spec"],
        ):
            return _unknown(state, "procedure_attachment_verification_failed")
        return {
            **state,
            "phase": "procedure_provisioned",
            "procedure": procedure,
            "code_artifact": dict(pointer),
        }

    def _create_or_adopt_task(
        self, state: Mapping[str, Any], *, may_mutate: bool,
    ) -> dict[str, Any]:
        procedure_id = str(state["procedure_id"])
        identity = state["launch_spec"]["identity"]
        record = {
            "accountId": state["launch_spec"]["account_id"],
            "type": "Procedure",
            "status": "PENDING",
            "target": f"procedure/{procedure_id}",
            "command": f"procedure run {procedure_id}",
            "dispatchStatus": "HELD",
            "scorecardId": state["launch_spec"]["scorecard_id"],
            "scoreId": state["launch_spec"]["score_id"],
            "metadata": {
                "type": "Procedure",
                "procedure_id": procedure_id,
                "dispatch_policy": "held_once",
                "optimizer_launch_identity": identity,
                "optimizer_launch_spec": state["launch_spec"],
            },
        }
        if may_mutate:
            task, failure = self._find_exact(
                self._backend.task_pages_for_account(
                    state["launch_spec"]["account_id"]
                ),
                state["launch_spec"],
                kind="task",
            )
            if failure == "no_exact_task_match":
                try:
                    task = self._backend.create_task(record)
                except Exception:
                    task, failure = self._find_exact(
                        self._backend.task_pages_for_account(
                            state["launch_spec"]["account_id"]
                        ),
                        state["launch_spec"],
                        kind="task",
                    )
                    if failure:
                        return _unknown(state, failure)
            elif failure:
                return _unknown(state, failure)
        else:
            task, failure = self._find_exact(
                self._backend.task_pages_for_account(
                    state["launch_spec"]["account_id"]
                ),
                state["launch_spec"],
                kind="task",
            )
            if failure:
                return _unknown(state, failure)
        failure = self._validate_task_record(task, state)
        if failure:
            return _unknown(state, failure)
        return {
            **state,
            "phase": "task_record_observed",
            "task_id": str(task["id"]),
            "task": dict(task),
        }

    def _hold_verified_task(
        self,
        request: Mapping[str, Any],
        state: Mapping[str, Any],
        *,
        may_mutate: bool,
    ) -> dict[str, Any]:
        task = self._backend.get_task(str(state["task_id"]))
        failure = self._validate_task_record(task, state)
        if failure:
            return _unknown(state, failure)
        if task.get("dispatchStatus") != "HELD":
            return self._observe_task({**state, "task": task})
        stages, stage_failure = self._read_task_stages(
            str(task["id"]), list(request.get("stages") or []),
        )
        if stage_failure == "complete":
            return {
                **state,
                "phase": "task_held",
                "task": dict(task),
                "stages": stages,
            }
        if stage_failure != "missing_task_stages":
            return _unknown(state, stage_failure)
        if not may_mutate:
            return {
                **state,
                "phase": "task_stage_reconcile_attempted",
                "task": dict(task),
                "missing_stages": stages,
            }
        try:
            self._backend.reconcile_task_stages(
                str(task["id"]), list(request.get("stages") or []),
            )
        except Exception:
            return _unknown(state, "task_stage_reconciliation_failed")
        stages, stage_failure = self._read_task_stages(
            str(task["id"]), list(request.get("stages") or []),
        )
        if stage_failure != "complete":
            return _unknown(state, stage_failure)
        return {
            **state,
            "phase": "task_held",
            "task": dict(task),
            "stages": list(stages or []),
        }

    def _observe_task(self, state: Mapping[str, Any]) -> dict[str, Any]:
        task = self._backend.get_task(str(state["task_id"]))
        if not isinstance(task, Mapping):
            return _unknown(state, "task_readback_failed")
        dispatch_status = str(task.get("dispatchStatus") or "").upper()
        task_status = str(task.get("status") or "").upper()
        observed = {**state, "task": dict(task), "complete": False}
        if task_status in {"COMPLETED", "FAILED", "CANCELED", "CANCELLED"}:
            return {**observed, "phase": "terminal", "complete": True}
        if dispatch_status == "DISPATCHING" and not task.get("celeryTaskId"):
            return _unknown(observed, "dispatching_without_celery_id")
        if dispatch_status == "PENDING":
            return {**observed, "phase": "waiting"}
        if dispatch_status in {"DISPATCHING", "DISPATCHED"} or task_status == "RUNNING":
            return {**observed, "phase": "running"}
        if dispatch_status == "HELD":
            return _unknown(observed, "release_outcome_unknown")
        return _unknown(observed, "unrecognized_task_dispatch_state")

    @staticmethod
    def _validate_procedure_record(
        procedure: Any, state: Mapping[str, Any],
    ) -> str | None:
        if not isinstance(procedure, Mapping) or not procedure.get("id"):
            return "malformed_procedure_record"
        try:
            metadata = _metadata(procedure.get("metadata"))
        except ValueError:
            return "malformed_procedure_metadata"
        expected = {
            "accountId": state["launch_spec"]["account_id"],
            "scorecardId": state["launch_spec"]["scorecard_id"],
            "scoreId": state["launch_spec"]["score_id"],
            "name": _PROCEDURE_NAME,
            "category": _PROCEDURE_CATEGORY,
            "version": _PROCEDURE_VERSION,
            "featured": False,
            "isTemplate": False,
            "status": "RUNNING",
        }
        if any(procedure.get(key) != value for key, value in expected.items()):
            return "procedure_identity_mismatch"
        if metadata.get("optimizer_launch_spec") != state["launch_spec"]:
            return "procedure_launch_spec_mismatch"
        return None

    def _verify_procedure_artifact(
        self,
        procedure: Mapping[str, Any],
        metadata: Mapping[str, Any],
        pointer: Any,
        launch_spec: Mapping[str, Any],
    ) -> bool:
        if (
            metadata.get("optimizer_launch_spec") != launch_spec
            or metadata.get("optimizer_yaml_sha256")
            != launch_spec["optimizer_yaml_sha256"]
            or not isinstance(pointer, Mapping)
        ):
            return False
        key = pointer.get("key")
        expected_key = f"procedures/{procedure['id']}/code.tac"
        if (
            key != expected_key
            or pointer.get("sha256") != launch_spec["optimizer_yaml_sha256"]
        ):
            return False
        try:
            payload = self._backend.read_procedure_artifact(str(key))
        except Exception:
            return False
        if not isinstance(payload, (bytes, bytearray)):
            return False
        return sha256(bytes(payload)).hexdigest() == launch_spec["optimizer_yaml_sha256"]

    def _read_task_stages(
        self, task_id: str, expected_stages: list[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], str]:
        expected_by_identity: dict[tuple[str, int], Mapping[str, Any]] = {}
        for stage in expected_stages:
            if not isinstance(stage, Mapping):
                return [], "malformed_expected_task_stage"
            name = stage.get("name")
            order = stage.get("order")
            if not isinstance(name, str) or not isinstance(order, int):
                return [], "malformed_expected_task_stage"
            identity = (name, order)
            if identity in expected_by_identity:
                return [], "ambiguous_expected_task_stages"
            expected_by_identity[identity] = stage

        observed: list[dict[str, Any]] = []
        seen_tokens: set[str] = set()
        expected_more = False
        try:
            pages = self._backend.task_stage_pages_for_task(task_id)
            for page in pages:
                if not isinstance(page, Mapping):
                    return [], "task_stage_scan_page_failed"
                items = page.get("items")
                if not isinstance(items, list):
                    return [], "malformed_task_stage_scan_page"
                for item in items:
                    if not isinstance(item, Mapping):
                        return [], "malformed_task_stage_scan_item"
                    if item.get("taskId") != task_id:
                        return [], "task_stage_task_mismatch"
                    name = item.get("name")
                    order = item.get("order")
                    if not isinstance(name, str) or not isinstance(order, int):
                        return [], "malformed_task_stage"
                    identity = (name, order)
                    if identity not in expected_by_identity:
                        return [], "unexpected_task_stage"
                    if any(
                        row["name"] == name and row["order"] == order
                        for row in observed
                    ):
                        return [], "ambiguous_task_stages"
                    expected = expected_by_identity[identity]
                    if item.get("status") != expected.get("status"):
                        return [], "task_stage_configuration_mismatch"
                    observed.append(dict(item))
                token = page.get("next_token")
                if token is None:
                    expected_more = False
                    break
                token = str(token)
                if token in seen_tokens:
                    return [], "task_stage_scan_token_cycle"
                seen_tokens.add(token)
                expected_more = True
        except Exception:
            return [], "task_stage_scan_page_failed"
        if expected_more:
            return [], "task_stage_scan_incomplete"
        if len(observed) == len(expected_by_identity):
            return observed, "complete"
        return [
            dict(stage) for identity, stage in expected_by_identity.items()
            if identity not in {(row["name"], row["order"]) for row in observed}
        ], "missing_task_stages"

    @staticmethod
    def _validate_task_record(
        task: Any, state: Mapping[str, Any],
    ) -> str | None:
        if not isinstance(task, Mapping) or not task.get("id"):
            return "malformed_task_record"
        try:
            metadata = _metadata(task.get("metadata"))
        except ValueError:
            return "malformed_task_metadata"
        procedure_id = str(state["procedure_id"])
        expected = {
            "accountId": state["launch_spec"]["account_id"],
            "scorecardId": state["launch_spec"]["scorecard_id"],
            "scoreId": state["launch_spec"]["score_id"],
            "type": "Procedure",
            "status": "PENDING",
            "target": f"procedure/{procedure_id}",
            "command": f"procedure run {procedure_id}",
        }
        if any(task.get(key) != value for key, value in expected.items()):
            return "task_identity_mismatch"
        if (
            metadata.get("optimizer_launch_identity")
            != state["launch_spec"]["identity"]
            or metadata.get("optimizer_launch_spec") != state["launch_spec"]
            or metadata.get("procedure_id") != procedure_id
            or metadata.get("dispatch_policy") != "held_once"
        ):
            return "task_launch_spec_mismatch"
        return None

    @staticmethod
    def _find_exact(
        pages: Any,
        launch_spec: Mapping[str, Any],
        *,
        kind: str,
    ) -> tuple[Mapping[str, Any] | None, str | None]:
        matches: list[Mapping[str, Any]] = []
        seen_tokens: set[str] = set()
        expected_more = False
        try:
            for page in pages:
                if not isinstance(page, Mapping):
                    return None, f"{kind}_scan_page_failed"
                items = page.get("items")
                if not isinstance(items, list):
                    return None, f"malformed_{kind}_scan_page"
                for item in items:
                    if not isinstance(item, Mapping):
                        return None, f"malformed_{kind}_scan_item"
                    # Account inventory necessarily contains legacy rows that
                    # predate optimizer metadata.  Apply physical target
                    # fields before inspecting metadata so unrelated rows can
                    # never poison an exhaustive idempotency scan.
                    physical_match = all(
                        item.get(record_field) == launch_spec[spec_field]
                        for record_field, spec_field in (
                            ("accountId", "account_id"),
                            ("scorecardId", "scorecard_id"),
                            ("scoreId", "score_id"),
                        )
                    )
                    metadata_value = item.get("metadata")
                    if metadata_value is None:
                        continue
                    try:
                        metadata = _metadata(metadata_value)
                    except ValueError:
                        # A non-optimizer legacy metadata value is not an
                        # adoption candidate.  Optimizer-shaped corruption is
                        # uncertain dispatch evidence and must fail closed.
                        if not physical_match or (
                            isinstance(metadata_value, str)
                            and "optimizer_launch" not in metadata_value
                        ):
                            continue
                        return None, f"malformed_{kind}_metadata"
                    optimizer_keys = {
                        "optimizer_launch_spec", "optimizer_launch_identity",
                    }
                    present_optimizer_keys = optimizer_keys.intersection(metadata)
                    if not present_optimizer_keys:
                        continue
                    candidate_spec = metadata.get("optimizer_launch_spec")
                    if not isinstance(candidate_spec, Mapping):
                        if not physical_match:
                            continue
                        return None, f"malformed_{kind}_metadata"
                    # Retain an exact immutable launch-spec match even if its
                    # physical fields were copied or corrupted.  The caller
                    # then reports the stronger identity-mismatch evidence
                    # instead of losing it as an absent child.
                    if candidate_spec == launch_spec:
                        matches.append(item)
                    elif not physical_match:
                        continue
                token = page.get("next_token")
                if token is None:
                    expected_more = False
                    break
                token = str(token)
                if token in seen_tokens:
                    return None, f"{kind}_scan_token_cycle"
                seen_tokens.add(token)
                expected_more = True
        except Exception:
            return None, f"{kind}_scan_page_failed"
        if expected_more:
            return None, f"{kind}_scan_incomplete"
        if len(matches) == 0:
            return None, f"no_exact_{kind}_match"
        if len(matches) > 1:
            return None, f"multiple_exact_{kind}_matches"
        return matches[0], None
