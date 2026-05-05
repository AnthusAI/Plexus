from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import boto3

from plexus.cli.shared import get_score_guidelines_path
from plexus.cli.shared.task_output_storage import (
    resolve_task_output_attachment_bucket_name,
    upload_task_attachment_bytes,
)
from plexus.config.loader import ConfigLoader
from plexus.dashboard.api.models.task import Task

logger = logging.getLogger(__name__)

LAB_EVALUATION_BASE_URL = "https://lab.callcriteria.com/lab/evaluations"
OPTIMIZER_ARTIFACT_SCHEMA_VERSION = 1
OPTIMIZER_ARTIFACTS_METADATA_KEY = "optimizer_artifacts"
OPTIMIZER_MANIFEST_SUFFIX = "optimizer/manifest.json"
OPTIMIZER_EVENTS_SUFFIX = "optimizer/events.jsonl"
OPTIMIZER_RUNTIME_LOG_SUFFIX = "optimizer/runtime.log"
PROCEDURE_TASK_TARGETS = ("procedure/", "procedure/run/")
REPORT_BLOCK_BUCKET_ENV = "AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME"
REPORT_BLOCK_BUCKET_CONFIG_KEY = "aws.storage.report_block_details_bucket"


@dataclass
class OptimizerRunRecord:
    procedure: Dict[str, Any]
    manifest: Optional[Dict[str, Any]]
    artifact_pointer: Optional[Dict[str, Any]]
    indexed: bool


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _parse_json_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
    return []


def _to_json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _resolve_report_block_bucket_name() -> Optional[str]:
    env_bucket = os.getenv(REPORT_BLOCK_BUCKET_ENV)
    if isinstance(env_bucket, str) and env_bucket.strip():
        return env_bucket.strip()

    loader = ConfigLoader()
    loader.load_config()
    configured_bucket = loader.get_config_value(REPORT_BLOCK_BUCKET_CONFIG_KEY)
    if isinstance(configured_bucket, str) and configured_bucket.strip():
        return configured_bucket.strip()

    return None


def _download_json_from_s3(*, bucket_name: str, key: str) -> Dict[str, Any]:
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket_name, Key=key)
    raw = response["Body"].read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"S3 object {key} did not contain a JSON object.")
    return parsed


def _download_text_from_s3(*, bucket_name: str, key: str) -> str:
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket_name, Key=key)
    return response["Body"].read().decode("utf-8")


def _download_json_from_s3_key(*, bucket_name: str, key: str) -> Dict[str, Any]:
    if not key:
        raise RuntimeError("S3 key is required.")
    return _download_json_from_s3(bucket_name=bucket_name, key=key)


def _looks_like_optimizer_state(state: Any) -> bool:
    return isinstance(state, dict) and (
        "iterations" in state
        or "baseline_version_id" in state
        or "end_of_run_report" in state
        or "last_accepted_version_id" in state
    )


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _sort_by_updated_at_desc(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: _parse_iso_datetime(item.get("updatedAt")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def _evaluation_url(evaluation_id: Optional[str]) -> Optional[str]:
    return f"{LAB_EVALUATION_BASE_URL}/{evaluation_id}" if evaluation_id else None


def _finite_number(value: Any) -> Optional[float]:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _parse_metrics(value: Any) -> Dict[str, Optional[float]]:
    parsed = value
    if isinstance(parsed, str) and parsed.strip():
        try:
            parsed = json.loads(parsed)
        except Exception:
            return {"accuracy": None, "alignment": None, "precision": None, "recall": None, "cost": None}

    if isinstance(parsed, list):
        accuracy = None
        alignment = None
        precision = None
        recall = None
        cost = None
        for metric in parsed:
            if not isinstance(metric, dict):
                continue
            name = str(metric.get("name") or metric.get("label") or "").lower()
            number = _finite_number(metric.get("value"))
            if number is None:
                continue
            if accuracy is None and "accuracy" in name:
                accuracy = number
            if alignment is None and ("alignment" in name or "ac1" in name):
                alignment = number
            if precision is None and "precision" in name:
                precision = number
            if recall is None and "recall" in name:
                recall = number
            if cost is None and "cost" in name:
                cost = number
        return {"accuracy": accuracy, "alignment": alignment, "precision": precision, "recall": recall, "cost": cost}

    if isinstance(parsed, dict):
        return {
            "accuracy": _finite_number(parsed.get("accuracy")),
            "alignment": (
                _finite_number(parsed.get("alignment"))
                or _finite_number(parsed.get("ac1"))
                or _finite_number(parsed.get("agreement"))
            ),
            "precision": _finite_number(parsed.get("precision")),
            "recall": _finite_number(parsed.get("recall")),
            "cost": (
                _finite_number(parsed.get("cost"))
                or _finite_number(parsed.get("total_cost"))
                or _finite_number(parsed.get("totalCost"))
                or _finite_number(parsed.get("cost_per_item"))
                or _finite_number(parsed.get("costPerItem"))
            ),
        }

    return {"accuracy": None, "alignment": None, "precision": None, "recall": None, "cost": None}


def _extract_evaluation_metadata(parameters: Any) -> Dict[str, Optional[str]]:
    params = _parse_json_dict(parameters)
    metadata = _parse_json_dict(params.get("metadata"))
    return {
        "notes": params.get("notes") if isinstance(params.get("notes"), str) else None,
        "baseline_evaluation_id": (
            metadata.get("baseline")
            or metadata.get("baseline_evaluation_id")
            or params.get("baseline")
            or params.get("baseline_evaluation_id")
        ),
        "current_baseline_evaluation_id": (
            metadata.get("current_baseline")
            or metadata.get("current_baseline_evaluation_id")
            or params.get("current_baseline")
            or params.get("current_baseline_evaluation_id")
        ),
    }


def _extract_status(iteration: Dict[str, Any]) -> str:
    if iteration.get("skip_reason"):
        return "skipped"
    if iteration.get("disqualified") or iteration.get("disqualification_reason"):
        return "disqualified"
    if iteration.get("accepted"):
        fb_delta = ((iteration.get("recent_deltas") or {}).get("alignment"))
        if isinstance(fb_delta, (int, float)) and fb_delta > 0.005:
            return "accepted"
        return "carried"
    return "rejected"


def _find_iteration_by_version_id(iterations: List[Dict[str, Any]], version_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not version_id:
        return None
    for iteration in reversed(iterations):
        if iteration.get("score_version_id") == version_id:
            return iteration
    return None


def _candidate_summary(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "index": candidate.get("index"),
        "version_id": candidate.get("version_id") or candidate.get("score_version_id"),
        "feedback_evaluation_id": candidate.get("fb_eval_id") or candidate.get("recent_evaluation_id"),
        "accuracy_evaluation_id": candidate.get("acc_eval_id") or candidate.get("regression_evaluation_id"),
        "feedback_metrics": deepcopy(candidate.get("fb_metrics") or candidate.get("recent_metrics")),
        "accuracy_metrics": deepcopy(candidate.get("acc_metrics") or candidate.get("regression_metrics")),
        "feedback_deltas": deepcopy(candidate.get("fb_deltas") or candidate.get("recent_deltas")),
        "accuracy_deltas": deepcopy(candidate.get("acc_deltas") or candidate.get("regression_deltas")),
        "done_reason": candidate.get("done_reason"),
        "agent_reasoning": candidate.get("agent_reasoning"),
    }


def _cycle_summary(iteration: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cycle": iteration.get("iteration"),
        "version_id": iteration.get("score_version_id"),
        "status": _extract_status(iteration),
        "accepted": bool(iteration.get("accepted")),
        "skip_reason": iteration.get("skip_reason"),
        "disqualification_reason": iteration.get("disqualification_reason"),
        "done_reason": iteration.get("done_reason"),
        "synthesis_strategy": iteration.get("synthesis_strategy"),
        "synthesis_reasoning": iteration.get("synthesis_reasoning"),
        "feedback_evaluation_id": iteration.get("recent_evaluation_id"),
        "accuracy_evaluation_id": iteration.get("regression_evaluation_id"),
        "feedback_metrics": deepcopy(iteration.get("recent_metrics")),
        "accuracy_metrics": deepcopy(iteration.get("regression_metrics")),
        "feedback_deltas": deepcopy(iteration.get("recent_deltas")),
        "accuracy_deltas": deepcopy(iteration.get("regression_deltas")),
        "feedback_cost_per_item": iteration.get("recent_cost_per_item"),
        "accuracy_cost_per_item": iteration.get("regression_cost_per_item"),
        "candidates": [
            _candidate_summary(candidate)
            for candidate in (iteration.get("exploration_results") or [])
            if isinstance(candidate, dict)
        ],
        "no_version_candidates": [
            _candidate_summary(candidate)
            for candidate in (iteration.get("exploration_no_version") or [])
            if isinstance(candidate, dict)
        ],
    }


def _render_optimizer_events_jsonl(manifest: Dict[str, Any]) -> str:
    events: List[Dict[str, Any]] = []
    procedure = manifest.get("procedure", {})
    events.append(
        {
            "type": "run_indexed",
            "timestamp": manifest.get("indexed_at"),
            "procedure_id": procedure.get("id"),
            "task_id": procedure.get("task_id"),
            "stop_reason": manifest.get("summary", {}).get("stop_reason"),
            "winning_version_id": manifest.get("best", {}).get("winning_version_id"),
        }
    )
    for cycle in manifest.get("cycles", []):
        events.append(
            {
                "type": "cycle",
                "timestamp": manifest.get("indexed_at"),
                "procedure_id": procedure.get("id"),
                "cycle": cycle.get("cycle"),
                "status": cycle.get("status"),
                "version_id": cycle.get("version_id"),
                "feedback_evaluation_id": cycle.get("feedback_evaluation_id"),
                "accuracy_evaluation_id": cycle.get("accuracy_evaluation_id"),
            }
        )
    return "\n".join(json.dumps(_to_json_safe(event), sort_keys=True) for event in events) + "\n"


def _render_optimizer_runtime_log(manifest: Dict[str, Any]) -> str:
    procedure = manifest.get("procedure", {})
    summary = manifest.get("summary", {})
    best = manifest.get("best", {})
    baseline = manifest.get("baseline", {})

    lines = [
        "=== OPTIMIZER RUN SUMMARY ===",
        f"Procedure: {procedure.get('id')}",
        f"Task: {procedure.get('task_id')}",
        f"Scorecard: {procedure.get('scorecard_name') or procedure.get('scorecard_id')}",
        f"Score: {procedure.get('score_name') or procedure.get('score_id')}",
        f"Status: {procedure.get('status')}",
        f"Stop reason: {summary.get('stop_reason')}",
        f"Baseline version: {baseline.get('version_id')}",
        f"Winning version: {best.get('winning_version_id')}",
        f"Best feedback alignment evaluation: {best.get('best_feedback_evaluation_id')}",
        f"Best regression alignment evaluation: {best.get('best_accuracy_evaluation_id')}",
        "",
        "=== CYCLES ===",
    ]
    for cycle in manifest.get("cycles", []):
        fb = (cycle.get("feedback_metrics") or {}).get("alignment")
        acc = (cycle.get("accuracy_metrics") or {}).get("alignment")
        lines.append(
            f"Cycle {cycle.get('cycle')}: {cycle.get('status')} "
            f"version={cycle.get('version_id')} "
            f"feedback_ac1={fb if fb is not None else 'n/a'} "
            f"accuracy_ac1={acc if acc is not None else 'n/a'}"
        )
        if cycle.get("done_reason"):
            lines.append(f"  Rationale: {cycle.get('done_reason')}")
        if cycle.get("skip_reason"):
            lines.append(f"  Skip reason: {cycle.get('skip_reason')}")
    lines.append("")
    if summary.get("procedure_summary"):
        lines.append("=== PROCEDURE SUMMARY ===")
        lines.append(json.dumps(summary["procedure_summary"], indent=2, default=str))
    if summary.get("end_of_run_report"):
        lines.append("")
        lines.append("=== END OF RUN REPORT ===")
        lines.append(json.dumps(summary["end_of_run_report"], indent=2, default=str))
    return "\n".join(lines) + "\n"


class OptimizerResultsService:
    def __init__(self, client):
        self.client = client
        self._task_cache: Dict[str, Optional[Task]] = {}

    def _load_procedure_record(self, procedure_id: str) -> Dict[str, Any]:
        query = """
        query GetProcedureForOptimizerResults($id: ID!) {
            getProcedure(id: $id) {
                id
                name
                status
                featured
                code
                metadata
                createdAt
                updatedAt
                accountId
                scorecardId
                scoreId
                scoreVersionId
                scorecard {
                    id
                    name
                }
                score {
                    id
                    name
                }
            }
        }
        """
        result = self.client.execute(query, {"id": procedure_id})
        procedure = result.get("getProcedure")
        if not procedure:
            raise RuntimeError(f"Procedure {procedure_id} was not found.")
        return procedure

    def list_procedure_records_for_score(self, score_id: str, *, limit: int = 25) -> List[Dict[str, Any]]:
        query = """
        query ListProcedureByScoreIdAndUpdatedAtForOptimizer($scoreId: String!, $limit: Int, $nextToken: String) {
            listProcedureByScoreIdAndUpdatedAt(scoreId: $scoreId, sortDirection: DESC, limit: $limit, nextToken: $nextToken) {
                items {
                    id
                    name
                    status
                    featured
                    metadata
                    createdAt
                    updatedAt
                    accountId
                    scorecardId
                    scoreId
                    scoreVersionId
                    scorecard {
                        id
                        name
                    }
                    score {
                        id
                        name
                    }
                }
                nextToken
            }
        }
        """
        items: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        while len(items) < limit:
            variables: Dict[str, Any] = {"scoreId": score_id, "limit": min(100, limit - len(items))}
            if next_token:
                variables["nextToken"] = next_token
            result = self.client.execute(query, variables)
            payload = result.get("listProcedureByScoreIdAndUpdatedAt", {})
            page_items = payload.get("items") or []
            items.extend(item for item in page_items if isinstance(item, dict))
            next_token = payload.get("nextToken")
            if not next_token:
                break
        return items[:limit]

    def _find_task_for_procedure(self, *, procedure_id: str, account_id: str, explicit_task_id: Optional[str] = None) -> Optional[Task]:
        cache_key = explicit_task_id or procedure_id
        if cache_key in self._task_cache:
            return self._task_cache[cache_key]

        if explicit_task_id:
            try:
                task = Task.get_by_id(explicit_task_id, self.client)
                self._task_cache[cache_key] = task
                return task
            except Exception:
                self._task_cache[cache_key] = None
                return None

        query = """
        query ListTaskByAccountIdAndUpdatedAtForOptimizer(
            $accountId: String!
            $updatedAt: ModelStringKeyConditionInput
            $limit: Int
            $nextToken: String
        ) {
            listTaskByAccountIdAndUpdatedAt(accountId: $accountId, updatedAt: $updatedAt, limit: $limit, nextToken: $nextToken) {
                items {
                    id
                    target
                    updatedAt
                }
                nextToken
            }
        }
        """
        next_token: Optional[str] = None
        while True:
            variables: Dict[str, Any] = {
                "accountId": account_id,
                "updatedAt": {"ge": "2000-01-01T00:00:00.000Z"},
                "limit": 1000,
            }
            if next_token:
                variables["nextToken"] = next_token
            result = self.client.execute(query, variables)
            payload = result.get("listTaskByAccountIdAndUpdatedAt", {})
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                target = str(item.get("target") or "")
                if target == f"procedure/{procedure_id}" or target == f"procedure/run/{procedure_id}":
                    task = Task.get_by_id(item["id"], self.client)
                    self._task_cache[cache_key] = task
                    return task
            next_token = payload.get("nextToken")
            if not next_token:
                break

        self._task_cache[cache_key] = None
        return None

    def _load_optimizer_state(self, procedure: Dict[str, Any]) -> Dict[str, Any]:
        metadata = _parse_json_dict(procedure.get("metadata"))
        state_ref = metadata.get("dashboard_state") or metadata.get("state") or {}
        if isinstance(state_ref, dict) and "_s3_key" in state_ref:
            bucket_name = _resolve_report_block_bucket_name()
            if not bucket_name:
                raise RuntimeError(
                    f"{REPORT_BLOCK_BUCKET_CONFIG_KEY} is required to load optimizer state artifacts."
                )
            return _download_json_from_s3_key(bucket_name=bucket_name, key=str(state_ref["_s3_key"]))
        if isinstance(state_ref, dict):
            return state_ref
        return {}

    def build_manifest(
        self,
        *,
        procedure: Dict[str, Any],
        task: Task,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        iterations = [item for item in (state.get("iterations") or []) if isinstance(item, dict)]
        winning_version_id = state.get("winning_version_id") or state.get("last_accepted_version_id")
        winning_iteration = _find_iteration_by_version_id(iterations, winning_version_id)

        current_recent_baseline_id = state.get("current_recent_baseline_id") or state.get("last_accepted_fb_eval_id")
        current_regression_baseline_id = state.get("current_regression_baseline_id") or state.get("last_accepted_acc_eval_id")
        best_feedback_eval_id = state.get("last_accepted_fb_eval_id") or current_recent_baseline_id
        best_accuracy_eval_id = state.get("last_accepted_acc_eval_id") or current_regression_baseline_id
        end_of_run_report = deepcopy(state.get("end_of_run_report"))
        run_summary = _parse_json_dict((end_of_run_report or {}).get("run_summary"))

        manifest = {
            "schema_version": OPTIMIZER_ARTIFACT_SCHEMA_VERSION,
            "indexed_at": _utc_now_iso(),
            "procedure": {
                "id": procedure.get("id"),
                "name": procedure.get("name"),
                "status": procedure.get("status"),
                "created_at": procedure.get("createdAt"),
                "updated_at": procedure.get("updatedAt"),
                "account_id": procedure.get("accountId"),
                "scorecard_id": procedure.get("scorecardId"),
                "scorecard_name": (procedure.get("scorecard") or {}).get("name") or state.get("scorecard_name"),
                "score_id": procedure.get("scoreId"),
                "score_name": (procedure.get("score") or {}).get("name") or state.get("score_name"),
                "score_version_id": procedure.get("scoreVersionId"),
                "task_id": task.id,
                "task_status": task.status,
                "task_target": task.target,
                "task_command": task.command,
            },
            "baseline": {
                "version_id": state.get("baseline_version_id"),
                "original_feedback_evaluation_id": state.get("recent_baseline_id"),
                "original_accuracy_evaluation_id": state.get("regression_baseline_id"),
                "current_feedback_evaluation_id": current_recent_baseline_id,
                "current_accuracy_evaluation_id": current_regression_baseline_id,
                "feedback_metrics": deepcopy(
                    state.get("recent_initial_baseline_metrics")
                    or state.get("recent_baseline_metrics")
                ),
                "accuracy_metrics": deepcopy(
                    state.get("regression_initial_baseline_metrics")
                    or state.get("regression_baseline_metrics")
                ),
            },
            "best": {
                "winning_version_id": winning_version_id,
                "last_accepted_version_id": state.get("last_accepted_version_id"),
                "best_feedback_evaluation_id": best_feedback_eval_id,
                "best_accuracy_evaluation_id": best_accuracy_eval_id,
                "winning_feedback_metrics": deepcopy(
                    (winning_iteration or {}).get("recent_metrics")
                    or state.get("recent_baseline_metrics")
                ),
                "winning_accuracy_metrics": deepcopy(
                    (winning_iteration or {}).get("regression_metrics")
                    or state.get("regression_baseline_metrics")
                ),
            },
            "summary": {
                "current_cycle": state.get("current_cycle") or len(iterations),
                "completed_cycles": len(iterations),
                "configured_max_iterations": (
                    (((state.get("params") or {}).get("max_iterations")) if isinstance(state.get("params"), dict) else None)
                    or run_summary.get("cycles")
                    or None
                ),
                "stop_reason": run_summary.get("stop_reason") or state.get("stop_reason"),
                "procedure_summary": deepcopy(state.get("procedure_summary")),
                "end_of_run_report": end_of_run_report,
                "optimization_diagnostic": deepcopy(state.get("optimization_diagnostic")),
            },
            "cycles": [_cycle_summary(iteration) for iteration in iterations],
        }
        return manifest

    def _guidelines_relative_path(self, scorecard_name: str, score_name: str) -> str:
        guideline_path = get_score_guidelines_path(scorecard_name, score_name)
        scorecards_base = Path(os.environ.get("SCORECARD_CACHE_DIR", "scorecards")).resolve()
        try:
            return str(guideline_path.resolve().relative_to(scorecards_base.parent))
        except Exception:
            return str(Path("scorecards") / guideline_path.name)

    def _artifact_keys_for_task(self, task_id: str) -> Dict[str, str]:
        return {
            "manifest": f"tasks/{task_id}/{OPTIMIZER_MANIFEST_SUFFIX}",
            "events": f"tasks/{task_id}/{OPTIMIZER_EVENTS_SUFFIX}",
            "runtime_log": f"tasks/{task_id}/{OPTIMIZER_RUNTIME_LOG_SUFFIX}",
        }

    def index_optimizer_run(
        self,
        procedure_id: str,
        *,
        force: bool = False,
        state_override: Optional[Dict[str, Any]] = None,
        existing_metadata: Optional[Dict[str, Any]] = None,
        persist_metadata_pointer: bool = True,
    ) -> Dict[str, Any]:
        procedure = self._load_procedure_record(procedure_id)
        metadata = existing_metadata if isinstance(existing_metadata, dict) else _parse_json_dict(procedure.get("metadata"))
        state = state_override if isinstance(state_override, dict) else self._load_optimizer_state(procedure)
        if not _looks_like_optimizer_state(state):
            raise RuntimeError(f"Procedure {procedure_id} does not have optimizer state to index.")

        existing_pointer = _parse_json_dict(metadata.get(OPTIMIZER_ARTIFACTS_METADATA_KEY))
        explicit_task_id = existing_pointer.get("task_id") if existing_pointer else None
        task = self._find_task_for_procedure(
            procedure_id=procedure_id,
            account_id=str(procedure.get("accountId") or ""),
            explicit_task_id=explicit_task_id,
        )
        if not task:
            raise RuntimeError(f"Could not find a Task for procedure {procedure_id}.")

        bucket_name = resolve_task_output_attachment_bucket_name()
        if not bucket_name:
            raise RuntimeError("aws.storage.task_attachments_bucket is required for optimizer artifacts.")

        manifest = self.build_manifest(procedure=procedure, task=task, state=state)
        artifact_keys = self._artifact_keys_for_task(task.id)
        upload_task_attachment_bytes(
            bucket_name=bucket_name,
            key=artifact_keys["manifest"],
            body=json.dumps(manifest, indent=2, ensure_ascii=False, default=str).encode("utf-8"),
            content_type="application/json",
        )
        upload_task_attachment_bytes(
            bucket_name=bucket_name,
            key=artifact_keys["events"],
            body=_render_optimizer_events_jsonl(manifest).encode("utf-8"),
            content_type="application/x-ndjson",
        )
        upload_task_attachment_bytes(
            bucket_name=bucket_name,
            key=artifact_keys["runtime_log"],
            body=_render_optimizer_runtime_log(manifest).encode("utf-8"),
            content_type="text/plain",
        )

        attached_files = list(task.attachedFiles or [])
        changed = False
        for key in artifact_keys.values():
            if key not in attached_files:
                attached_files.append(key)
                changed = True
        if changed or force:
            task.update(attachedFiles=attached_files)

        pointer = {
            "schema_version": OPTIMIZER_ARTIFACT_SCHEMA_VERSION,
            "indexed_at": manifest["indexed_at"],
            "task_id": task.id,
            "manifest": artifact_keys["manifest"],
            "events": artifact_keys["events"],
            "runtime_log": artifact_keys["runtime_log"],
        }
        metadata[OPTIMIZER_ARTIFACTS_METADATA_KEY] = pointer

        if persist_metadata_pointer and not existing_metadata:
            mutation = """
            mutation UpdateProcedureOptimizerArtifacts($input: UpdateProcedureInput!) {
                updateProcedure(input: $input) {
                    id
                    name
                    description
                    status
                    featured
                    isTemplate
                    code
                    category
                    version
                    isDefault
                    parentProcedureId
                    waitingOnMessageId
                    metadata
                    createdAt
                    updatedAt
                    accountId
                    scorecardId
                    scoreId
                    scoreVersionId
                }
            }
            """
            self.client.execute(
                mutation,
                {"input": {"id": procedure_id, "metadata": json.dumps(_to_json_safe(metadata), default=str)}},
            )

        return {"manifest": manifest, "pointer": pointer, "task_id": task.id}

    def load_indexed_manifest_for_procedure(self, procedure: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        metadata = _parse_json_dict(procedure.get("metadata"))
        artifact_pointer = _parse_json_dict(metadata.get(OPTIMIZER_ARTIFACTS_METADATA_KEY))
        manifest_key = artifact_pointer.get("manifest")
        if not manifest_key:
            return None
        bucket_name = resolve_task_output_attachment_bucket_name()
        if not bucket_name:
            raise RuntimeError("aws.storage.task_attachments_bucket is required to load optimizer manifests.")
        return _download_json_from_s3_key(bucket_name=bucket_name, key=str(manifest_key))

    def list_optimizer_runs_for_score(self, score_id: str, *, limit: int = 25) -> List[OptimizerRunRecord]:
        records: List[OptimizerRunRecord] = []
        for procedure in self.list_procedure_records_for_score(score_id, limit=limit):
            metadata = _parse_json_dict(procedure.get("metadata"))
            artifact_pointer = _parse_json_dict(metadata.get(OPTIMIZER_ARTIFACTS_METADATA_KEY))
            manifest = None
            if artifact_pointer.get("manifest"):
                try:
                    manifest = self.load_indexed_manifest_for_procedure(procedure)
                except Exception as exc:
                    logger.warning("Failed to load indexed manifest for procedure %s: %s", procedure.get("id"), exc)
            records.append(
                OptimizerRunRecord(
                    procedure=procedure,
                    manifest=manifest,
                    artifact_pointer=artifact_pointer or None,
                    indexed=manifest is not None,
                )
            )
        return records

    def summarize_optimizer_run(self, run: OptimizerRunRecord) -> Dict[str, Any]:
        manifest = run.manifest or {}
        summary = manifest.get("summary") or {}
        best = manifest.get("best") or {}
        winning_feedback_metrics = best.get("winning_feedback_metrics") or {}
        winning_accuracy_metrics = best.get("winning_accuracy_metrics") or {}
        return {
            "procedure_id": run.procedure.get("id"),
            "name": run.procedure.get("name"),
            "status": run.procedure.get("status"),
            "updated_at": run.procedure.get("updatedAt"),
            "indexed": run.indexed,
            "completed_cycles": summary.get("completed_cycles"),
            "configured_max_iterations": summary.get("configured_max_iterations"),
            "stop_reason": summary.get("stop_reason"),
            "winning_version_id": best.get("winning_version_id"),
            "best_feedback_evaluation_id": best.get("best_feedback_evaluation_id"),
            "best_feedback_evaluation_url": _evaluation_url(best.get("best_feedback_evaluation_id")),
            "best_accuracy_evaluation_id": best.get("best_accuracy_evaluation_id"),
            "best_accuracy_evaluation_url": _evaluation_url(best.get("best_accuracy_evaluation_id")),
            "best_feedback_alignment": winning_feedback_metrics.get("alignment"),
            "best_accuracy_alignment": winning_accuracy_metrics.get("alignment"),
            "artifact_pointer": run.artifact_pointer,
        }

    def _list_score_versions(self, score_id: str, *, limit: int = 200) -> List[Dict[str, Any]]:
        query = """
        query ListScoreVersionByScoreIdAndCreatedAtForOptimizer($scoreId: String!, $limit: Int, $nextToken: String) {
            listScoreVersionByScoreIdAndCreatedAt(scoreId: $scoreId, sortDirection: DESC, limit: $limit, nextToken: $nextToken) {
                items {
                    id
                    scoreId
                    isFeatured
                    note
                    branch
                    parentVersionId
                    createdAt
                    updatedAt
                }
                nextToken
            }
        }
        """
        versions: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        while len(versions) < limit:
            variables: Dict[str, Any] = {"scoreId": score_id, "limit": min(100, limit - len(versions))}
            if next_token:
                variables["nextToken"] = next_token
            result = self.client.execute(query, variables)
            payload = result.get("listScoreVersionByScoreIdAndCreatedAt", {})
            versions.extend(item for item in payload.get("items") or [] if isinstance(item, dict))
            next_token = payload.get("nextToken")
            if not next_token:
                break
        return versions[:limit]

    def list_optimizer_candidates_for_score(self, score_id: str, *, limit_runs: int = 25) -> List[Dict[str, Any]]:
        runs = self.list_optimizer_runs_for_score(score_id, limit=limit_runs)
        versions = self._list_score_versions(score_id)
        versions_by_id = {version["id"]: version for version in versions if isinstance(version.get("id"), str)}
        aggregated: Dict[str, Dict[str, Any]] = {}

        def touch_candidate(version_id: Optional[str], candidate: Dict[str, Any], run: OptimizerRunRecord) -> None:
            if not version_id:
                return
            entry = aggregated.setdefault(
                version_id,
                {
                    "version_id": version_id,
                    "runs": [],
                    "best_feedback_evaluation_id": None,
                    "best_accuracy_evaluation_id": None,
                    "best_feedback_alignment": None,
                    "best_accuracy_alignment": None,
                    "best_feedback_metrics": None,
                    "best_accuracy_metrics": None,
                },
            )
            if run.procedure.get("id") not in entry["runs"]:
                entry["runs"].append(run.procedure.get("id"))

            feedback_metrics = candidate.get("feedback_metrics") or {}
            accuracy_metrics = candidate.get("accuracy_metrics") or {}
            feedback_alignment = feedback_metrics.get("alignment")
            accuracy_alignment = accuracy_metrics.get("alignment")

            if isinstance(feedback_alignment, (int, float)) and (
                entry["best_feedback_alignment"] is None or feedback_alignment > entry["best_feedback_alignment"]
            ):
                entry["best_feedback_alignment"] = feedback_alignment
                entry["best_feedback_evaluation_id"] = candidate.get("feedback_evaluation_id")
                entry["best_feedback_metrics"] = feedback_metrics

            if isinstance(accuracy_alignment, (int, float)) and (
                entry["best_accuracy_alignment"] is None or accuracy_alignment > entry["best_accuracy_alignment"]
            ):
                entry["best_accuracy_alignment"] = accuracy_alignment
                entry["best_accuracy_evaluation_id"] = candidate.get("accuracy_evaluation_id")
                entry["best_accuracy_metrics"] = accuracy_metrics

        for run in runs:
            manifest = run.manifest
            if not manifest:
                continue
            for cycle in manifest.get("cycles", []):
                if not isinstance(cycle, dict):
                    continue
                touch_candidate(cycle.get("version_id"), cycle, run)
                for candidate in cycle.get("candidates") or []:
                    if isinstance(candidate, dict):
                        touch_candidate(candidate.get("version_id"), candidate, run)

        candidates: List[Dict[str, Any]] = []
        for version_id, aggregated_entry in aggregated.items():
            version = versions_by_id.get(version_id, {})
            candidates.append(
                {
                    **aggregated_entry,
                    "created_at": version.get("createdAt"),
                    "updated_at": version.get("updatedAt"),
                    "note": version.get("note"),
                    "branch": version.get("branch"),
                    "parent_version_id": version.get("parentVersionId"),
                    "pinned": version.get("isFeatured") in (True, "true"),
                }
            )

        candidates.sort(
            key=lambda item: (
                item.get("best_feedback_alignment") if item.get("best_feedback_alignment") is not None else -1,
                item.get("best_accuracy_alignment") if item.get("best_accuracy_alignment") is not None else -1,
                _parse_iso_datetime(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        return candidates

    def summarize_optimizer_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        feedback_metrics = candidate.get("best_feedback_metrics") or {}
        accuracy_metrics = candidate.get("best_accuracy_metrics") or {}
        return {
            "version_id": candidate.get("version_id"),
            "runs": candidate.get("runs") or [],
            "best_feedback_evaluation_id": candidate.get("best_feedback_evaluation_id"),
            "best_feedback_evaluation_url": _evaluation_url(candidate.get("best_feedback_evaluation_id")),
            "best_accuracy_evaluation_id": candidate.get("best_accuracy_evaluation_id"),
            "best_accuracy_evaluation_url": _evaluation_url(candidate.get("best_accuracy_evaluation_id")),
            "best_feedback_alignment": candidate.get("best_feedback_alignment"),
            "best_accuracy_alignment": candidate.get("best_accuracy_alignment"),
            "best_feedback_accuracy": feedback_metrics.get("accuracy"),
            "best_accuracy_accuracy": accuracy_metrics.get("accuracy"),
            "created_at": candidate.get("created_at"),
            "updated_at": candidate.get("updated_at"),
            "note": candidate.get("note"),
            "branch": candidate.get("branch"),
            "parent_version_id": candidate.get("parent_version_id"),
            "pinned": bool(candidate.get("pinned")),
        }

    def list_score_evaluations(
        self,
        score_id: str,
        *,
        version_id: Optional[str] = None,
        sort_by: str = "updated",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = """
        query ListEvaluationByScoreIdAndUpdatedAtForOptimizerReview(
            $scoreId: String!
            $limit: Int
            $nextToken: String
        ) {
            listEvaluationByScoreIdAndUpdatedAt(scoreId: $scoreId, sortDirection: DESC, limit: $limit, nextToken: $nextToken) {
                items {
                    id
                    type
                    status
                    createdAt
                    updatedAt
                    scoreVersionId
                    accuracy
                    cost
                    processedItems
                    totalItems
                    elapsedSeconds
                    estimatedRemainingSeconds
                    parameters
                    metrics
                }
                nextToken
            }
        }
        """
        rows: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        fetch_limit = max(limit * 3, limit)
        while len(rows) < fetch_limit:
            variables: Dict[str, Any] = {
                "scoreId": score_id,
                "limit": min(100, fetch_limit - len(rows)),
            }
            if next_token:
                variables["nextToken"] = next_token
            result = self.client.execute(query, variables)
            payload = result.get("listEvaluationByScoreIdAndUpdatedAt", {})
            page_items = payload.get("items") or []
            rows.extend(item for item in page_items if isinstance(item, dict))
            next_token = payload.get("nextToken")
            if not next_token:
                break

        evaluations: List[Dict[str, Any]] = []
        for row in rows:
            if version_id and row.get("scoreVersionId") != version_id:
                continue
            parsed_metrics = _parse_metrics(row.get("metrics"))
            metadata = _extract_evaluation_metadata(row.get("parameters"))
            evaluations.append(
                {
                    "evaluation_id": row.get("id"),
                    "evaluation_url": _evaluation_url(row.get("id")),
                    "type": row.get("type"),
                    "status": row.get("status"),
                    "score_version_id": row.get("scoreVersionId"),
                    "created_at": row.get("createdAt"),
                    "updated_at": row.get("updatedAt"),
                    "accuracy": _finite_number(row.get("accuracy")) or parsed_metrics.get("accuracy"),
                    "alignment": parsed_metrics.get("alignment"),
                    "precision": parsed_metrics.get("precision"),
                    "recall": parsed_metrics.get("recall"),
                    "cost": _finite_number(row.get("cost")) or parsed_metrics.get("cost"),
                    "processed_items": row.get("processedItems"),
                    "total_items": row.get("totalItems"),
                    "elapsed_seconds": row.get("elapsedSeconds"),
                    "estimated_remaining_seconds": row.get("estimatedRemainingSeconds"),
                    "notes": metadata.get("notes"),
                    "baseline_evaluation_id": metadata.get("baseline_evaluation_id"),
                    "current_baseline_evaluation_id": metadata.get("current_baseline_evaluation_id"),
                }
            )

        if sort_by == "accuracy":
            evaluations.sort(key=lambda item: item.get("accuracy") if item.get("accuracy") is not None else -1, reverse=True)
        elif sort_by == "alignment":
            evaluations.sort(key=lambda item: item.get("alignment") if item.get("alignment") is not None else -1, reverse=True)
        elif sort_by == "precision":
            evaluations.sort(key=lambda item: item.get("precision") if item.get("precision") is not None else -1, reverse=True)
        elif sort_by == "recall":
            evaluations.sort(key=lambda item: item.get("recall") if item.get("recall") is not None else -1, reverse=True)
        elif sort_by == "cost":
            evaluations.sort(
                key=lambda item: (
                    item.get("cost") is None,
                    item.get("cost") if item.get("cost") is not None else float("inf"),
                    datetime.max.replace(tzinfo=timezone.utc)
                    - (_parse_iso_datetime(item.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)),
                )
            )
        else:
            evaluations.sort(
                key=lambda item: _parse_iso_datetime(item.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
        return evaluations[:limit]

    def build_promotion_packet_for_score(
        self,
        score_id: str,
        *,
        score_name: str,
        scorecard_name: str,
        champion_version_id: Optional[str],
        version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        candidates = self.list_optimizer_candidates_for_score(score_id)
        if not candidates:
            raise RuntimeError(f"No indexed optimizer candidates were found for score {score_id}.")

        selected = None
        if version_id:
            selected = next((candidate for candidate in candidates if candidate["version_id"] == version_id), None)
            if not selected:
                raise RuntimeError(f"Version {version_id} was not found in indexed optimizer candidates.")
        else:
            selected = candidates[0]

        selected_version_id = selected["version_id"]
        guideline_path = get_score_guidelines_path(scorecard_name, score_name)
        base_url = "https://lab.callcriteria.com/lab/evaluations"
        return {
            "score_id": score_id,
            "score_name": score_name,
            "scorecard_name": scorecard_name,
            "version_id": selected_version_id,
            "is_champion": selected_version_id == champion_version_id,
            "champion_version_id": champion_version_id,
            "best_feedback_evaluation_id": selected.get("best_feedback_evaluation_id"),
            "best_feedback_evaluation_url": (
                f"{base_url}/{selected['best_feedback_evaluation_id']}"
                if selected.get("best_feedback_evaluation_id")
                else None
            ),
            "best_accuracy_evaluation_id": selected.get("best_accuracy_evaluation_id"),
            "best_accuracy_evaluation_url": (
                f"{base_url}/{selected['best_accuracy_evaluation_id']}"
                if selected.get("best_accuracy_evaluation_id")
                else None
            ),
            "best_feedback_alignment": selected.get("best_feedback_alignment"),
            "best_accuracy_alignment": selected.get("best_accuracy_alignment"),
            "guidelines_path": str(guideline_path),
            "guidelines_relative_path": self._guidelines_relative_path(scorecard_name, score_name),
            "pinned": bool(selected.get("pinned")),
            "note": selected.get("note"),
            "branch": selected.get("branch"),
            "runs": selected.get("runs") or [],
        }

    def build_optimizer_review_packet_for_score(
        self,
        score_id: str,
        *,
        score_name: str,
        scorecard_name: str,
        champion_version_id: Optional[str],
    ) -> Dict[str, Any]:
        runs = self.list_optimizer_runs_for_score(score_id)
        candidates = self.list_optimizer_candidates_for_score(score_id)
        unindexed_count = sum(1 for run in runs if not run.indexed)
        best_candidate = candidates[0] if candidates else None
        promotion_packet = None
        recommendation = "No indexed optimizer candidates were found."
        if best_candidate:
            promotion_packet = self.build_promotion_packet_for_score(
                score_id,
                score_name=score_name,
                scorecard_name=scorecard_name,
                champion_version_id=champion_version_id,
                version_id=best_candidate["version_id"],
            )
            if promotion_packet["is_champion"]:
                recommendation = "Best indexed candidate is already champion."
            else:
                recommendation = "Best indexed candidate differs from champion; review evaluations and promote manually if accepted."

        return {
            "score_id": score_id,
            "score_name": score_name,
            "scorecard_name": scorecard_name,
            "champion_version_id": champion_version_id,
            "best_candidate": self.summarize_optimizer_candidate(best_candidate) if best_candidate else None,
            "promotion_packet": promotion_packet,
            "unindexed_run_count": unindexed_count,
            "indexed_run_count": len(runs) - unindexed_count,
            "latest_runs": [self.summarize_optimizer_run(run) for run in runs[:5]],
            "promotion_recommendation": recommendation,
        }

    def summarize_optimizer_procedure(
        self,
        procedure_id: str,
        *,
        include_runtime_log: bool = False,
        include_events: bool = False,
        log_lines: int = 80,
    ) -> Dict[str, Any]:
        procedure = self._load_procedure_record(procedure_id)
        metadata = _parse_json_dict(procedure.get("metadata"))
        artifact_pointer = _parse_json_dict(metadata.get(OPTIMIZER_ARTIFACTS_METADATA_KEY))
        manifest_key = artifact_pointer.get("manifest")
        if not manifest_key:
            raise RuntimeError(
                f"Procedure {procedure_id} is not indexed. Run 'plexus procedure index-optimizer-run {procedure_id}' first."
            )
        manifest = self.load_indexed_manifest_for_procedure(procedure)
        cycles = [
            {
                "cycle": cycle.get("cycle"),
                "status": cycle.get("status"),
                "version_id": cycle.get("version_id"),
                "feedback_evaluation_id": cycle.get("feedback_evaluation_id"),
                "feedback_evaluation_url": _evaluation_url(cycle.get("feedback_evaluation_id")),
                "accuracy_evaluation_id": cycle.get("accuracy_evaluation_id"),
                "accuracy_evaluation_url": _evaluation_url(cycle.get("accuracy_evaluation_id")),
                "feedback_alignment": (cycle.get("feedback_metrics") or {}).get("alignment"),
                "accuracy_alignment": (cycle.get("accuracy_metrics") or {}).get("alignment"),
                "accepted": cycle.get("accepted"),
                "candidate_count": len(cycle.get("candidates") or []),
                "candidates": [
                    {
                        "index": candidate.get("index"),
                        "version_id": candidate.get("version_id"),
                        "feedback_evaluation_id": candidate.get("feedback_evaluation_id"),
                        "feedback_evaluation_url": _evaluation_url(candidate.get("feedback_evaluation_id")),
                        "accuracy_evaluation_id": candidate.get("accuracy_evaluation_id"),
                        "accuracy_evaluation_url": _evaluation_url(candidate.get("accuracy_evaluation_id")),
                        "feedback_alignment": (candidate.get("feedback_metrics") or {}).get("alignment"),
                        "accuracy_alignment": (candidate.get("accuracy_metrics") or {}).get("alignment"),
                    }
                    for candidate in (cycle.get("candidates") or [])
                    if isinstance(candidate, dict)
                ],
            }
            for cycle in manifest.get("cycles", [])
            if isinstance(cycle, dict)
        ]
        raw_summary = manifest.get("summary") or {}
        raw_baseline = manifest.get("baseline") or {}
        raw_best = manifest.get("best") or {}
        baseline_feedback_metrics = raw_baseline.get("feedback_metrics") or {}
        baseline_accuracy_metrics = raw_baseline.get("accuracy_metrics") or {}
        winning_feedback_metrics = raw_best.get("winning_feedback_metrics") or {}
        winning_accuracy_metrics = raw_best.get("winning_accuracy_metrics") or {}
        payload: Dict[str, Any] = {
            "procedure_id": procedure_id,
            "procedure": manifest.get("procedure"),
            "summary": {
                "current_cycle": raw_summary.get("current_cycle"),
                "completed_cycles": raw_summary.get("completed_cycles"),
                "configured_max_iterations": raw_summary.get("configured_max_iterations"),
                "stop_reason": raw_summary.get("stop_reason"),
                "procedure_summary": raw_summary.get("procedure_summary"),
            },
            "baseline": {
                "version_id": raw_baseline.get("version_id"),
                "original_feedback_evaluation_id": raw_baseline.get("original_feedback_evaluation_id"),
                "original_feedback_evaluation_url": _evaluation_url(raw_baseline.get("original_feedback_evaluation_id")),
                "original_accuracy_evaluation_id": raw_baseline.get("original_accuracy_evaluation_id"),
                "original_accuracy_evaluation_url": _evaluation_url(raw_baseline.get("original_accuracy_evaluation_id")),
                "current_feedback_evaluation_id": raw_baseline.get("current_feedback_evaluation_id"),
                "current_feedback_evaluation_url": _evaluation_url(raw_baseline.get("current_feedback_evaluation_id")),
                "current_accuracy_evaluation_id": raw_baseline.get("current_accuracy_evaluation_id"),
                "current_accuracy_evaluation_url": _evaluation_url(raw_baseline.get("current_accuracy_evaluation_id")),
                "feedback_alignment": baseline_feedback_metrics.get("alignment"),
                "feedback_accuracy": baseline_feedback_metrics.get("accuracy"),
                "accuracy_alignment": baseline_accuracy_metrics.get("alignment"),
                "accuracy_accuracy": baseline_accuracy_metrics.get("accuracy"),
            },
            "best": {
                "winning_version_id": raw_best.get("winning_version_id"),
                "last_accepted_version_id": raw_best.get("last_accepted_version_id"),
                "best_feedback_evaluation_id": raw_best.get("best_feedback_evaluation_id"),
                "best_feedback_evaluation_url": _evaluation_url(raw_best.get("best_feedback_evaluation_id")),
                "best_accuracy_evaluation_id": raw_best.get("best_accuracy_evaluation_id"),
                "best_accuracy_evaluation_url": _evaluation_url(raw_best.get("best_accuracy_evaluation_id")),
                "feedback_alignment": winning_feedback_metrics.get("alignment"),
                "feedback_accuracy": winning_feedback_metrics.get("accuracy"),
                "accuracy_alignment": winning_accuracy_metrics.get("alignment"),
                "accuracy_accuracy": winning_accuracy_metrics.get("accuracy"),
            },
            "cycles": cycles,
            "artifact_pointer": artifact_pointer,
        }
        bucket_name = resolve_task_output_attachment_bucket_name()
        if (include_runtime_log or include_events) and not bucket_name:
            raise RuntimeError("aws.storage.task_attachments_bucket is required to load optimizer artifacts.")
        if include_runtime_log:
            runtime_key = artifact_pointer.get("runtime_log")
            runtime_text = _download_text_from_s3(bucket_name=bucket_name, key=runtime_key) if runtime_key else ""
            runtime_lines = runtime_text.splitlines()
            payload["runtime_log_excerpt"] = "\n".join(runtime_lines[-log_lines:])
        if include_events:
            events_key = artifact_pointer.get("events")
            events_text = _download_text_from_s3(bucket_name=bucket_name, key=events_key) if events_key else ""
            payload["events_excerpt"] = "\n".join(events_text.splitlines()[-log_lines:])
        return payload

    @staticmethod
    def render_promotion_packets_markdown(packets: List[Dict[str, Any]]) -> str:
        lines = [
            "| Score | Version | Champion | Feedback Alignment Evaluation | Feedback AC1 | Regression Alignment Evaluation | Regression AC1 | Guidelines |",
            "| --- | --- | --- | --- | ---: | --- | ---: | --- |",
        ]
        for packet in packets:
            lines.append(
                "| {score} | {version} | {champion} | {fb_eval} | {fb_ac1} | {acc_eval} | {acc_ac1} | {guidelines} |".format(
                    score=packet.get("score_name") or "",
                    version=packet.get("version_id") or "",
                    champion="yes" if packet.get("is_champion") else "no",
                    fb_eval=packet.get("best_feedback_evaluation_url") or "",
                    fb_ac1=(
                        f"{packet['best_feedback_alignment']:.4f}"
                        if isinstance(packet.get("best_feedback_alignment"), (int, float))
                        else ""
                    ),
                    acc_eval=packet.get("best_accuracy_evaluation_url") or "",
                    acc_ac1=(
                        f"{packet['best_accuracy_alignment']:.4f}"
                        if isinstance(packet.get("best_accuracy_alignment"), (int, float))
                        else ""
                    ),
                    guidelines=packet.get("guidelines_relative_path") or "",
                )
            )
        return "\n".join(lines)
