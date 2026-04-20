from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Sequence

from plexus.Evaluation import Evaluation
from plexus.dashboard.api.models.task import Task
from plexus.cli.shared.stage_configurations import get_feedback_evaluation_stage_configs
from plexus.utils.feedback_selection import normalize_feedback_sampling_mode


TERMINAL_EVALUATION_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "ERROR"})

SCAFFOLD_SOURCE_DESCRIPTION = "Generated directly from vetted feedback item IDs."


@dataclass(frozen=True)
class FeedbackRunnerRequest:
    scorecard: str
    score: str
    days: Optional[int] = None
    version: Optional[str] = None
    baseline: Optional[str] = None
    current_baseline: Optional[str] = None
    max_items: int = 200
    sampling_mode: str = "newest"
    sample_seed: Optional[int] = None
    max_category_summary_items: int = 20
    task_id: Optional[str] = None
    use_yaml: bool = False


def build_feedback_command(
    *,
    plexus_bin: str,
    request: FeedbackRunnerRequest,
    resolved_task_id: str,
) -> list[str]:
    cmd = [
        plexus_bin,
        "evaluate",
        "feedback",
        "--scorecard",
        request.scorecard,
        "--score",
        request.score,
        "--task-id",
        resolved_task_id,
        "--max-items",
        str(request.max_items),
        "--sampling-mode",
        request.sampling_mode,
        "--max-category-summary-items",
        str(request.max_category_summary_items),
    ]
    if request.days is not None:
        cmd.extend(["--days", str(request.days)])
    if request.use_yaml:
        cmd.append("--yaml")
    if request.version:
        cmd.extend(["--version", request.version])
    if request.baseline:
        cmd.extend(["--baseline", request.baseline])
    if request.current_baseline:
        cmd.extend(["--current-baseline", request.current_baseline])
    if request.sample_seed is not None:
        cmd.extend(["--sample-seed", str(request.sample_seed)])
    return cmd


def ensure_feedback_runner_task(
    *,
    client: Any,
    account_id: str,
    scorecard: str,
    score: str,
    version: Optional[str],
    task_id: Optional[str],
) -> str:
    """Return a valid existing task ID, or create a new feedback task with stages."""
    if task_id:
        # One path: explicit task IDs must exist.
        Task.get_by_id(task_id, client)
        return task_id

    task = Task.create(
        client=client,
        accountId=account_id,
        type="Feedback Accuracy Evaluation",
        target=f"evaluation/feedback/{scorecard}/{score}",
        command=f"evaluate feedback --scorecard {scorecard} --score {score}" + (f" --version {version}" if version else ""),
        status="RUNNING",
        dispatchStatus="DISPATCHED",
        description=f"Feedback accuracy evaluation for {scorecard} > {score}",
        metadata=json.dumps(
            {
                "type": "Feedback Accuracy Evaluation",
                "scorecard": scorecard,
                "score": score,
                "task_type": "Feedback Accuracy Evaluation",
            }
        ),
        startedAt=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

    stage_configs = get_feedback_evaluation_stage_configs(total_items=0)
    for stage_name, stage_config in stage_configs.items():
        task.create_stage(
            name=stage_name,
            order=stage_config.order,
            status="PENDING" if stage_name != "Setup" else "RUNNING",
            statusMessage=stage_config.status_message,
            totalItems=stage_config.total_items,
            processedItems=None,
            startedAt=(
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                if stage_name == "Setup"
                else None
            ),
        )

    return task.id


def _query_recent_feedback_evaluations(
    *,
    client: Any,
    account_id: str,
    limit: int = 50,
    next_token: Optional[str] = None,
) -> Dict[str, Any]:
    query = """
    query ListEvaluationByAccountIdAndUpdatedAt(
      $accountId: String!,
      $sortDirection: ModelSortDirection,
      $limit: Int,
      $nextToken: String
    ) {
      listEvaluationByAccountIdAndUpdatedAt(
        accountId: $accountId,
        sortDirection: $sortDirection,
        limit: $limit,
        nextToken: $nextToken
      ) {
        items {
          id
          type
          status
          taskId
          createdAt
          updatedAt
        }
        nextToken
      }
    }
    """
    return client.execute(
        query,
        {
            "accountId": account_id,
            "sortDirection": "DESC",
            "limit": limit,
            "nextToken": next_token,
        },
    ) or {}


def find_feedback_evaluation_id_by_task_id(
    *,
    client: Any,
    account_id: str,
    task_id: str,
    max_pages: int = 20,
) -> Optional[str]:
    next_token = None
    pages = 0
    while pages < max_pages:
        response = _query_recent_feedback_evaluations(
            client=client,
            account_id=account_id,
            limit=50,
            next_token=next_token,
        )
        block = (response or {}).get("listEvaluationByAccountIdAndUpdatedAt") or {}
        for item in block.get("items", []) or []:
            if item.get("type") != "feedback":
                continue
            if item.get("taskId") != task_id:
                continue
            return item.get("id")
        next_token = block.get("nextToken")
        pages += 1
        if not next_token:
            break
    return None


def wait_for_feedback_evaluation_id(
    *,
    client: Any,
    account_id: str,
    task_id: str,
    timeout_seconds: int = 180,
    poll_interval_seconds: int = 3,
    process: Optional[subprocess.Popen] = None,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        evaluation_id = find_feedback_evaluation_id_by_task_id(
            client=client,
            account_id=account_id,
            task_id=task_id,
        )
        if evaluation_id:
            return evaluation_id
        if process is not None:
            return_code = process.poll()
            if return_code is not None and return_code != 0:
                raise RuntimeError(
                    f"Feedback evaluation process exited before evaluation record creation (exit={return_code})."
                )
        time.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Timed out waiting for feedback evaluation record with task_id='{task_id}' after "
        f"{timeout_seconds}s."
    )


def wait_for_feedback_evaluation_terminal_status(
    *,
    evaluation_id: str,
    timeout_seconds: int = 7200,
    poll_interval_seconds: int = 5,
    process: Optional["subprocess.Popen"] = None,
    stderr_log=None,
    stdout_log=None,
) -> Dict[str, Any]:
    import subprocess as _subprocess
    deadline = time.monotonic() + timeout_seconds
    latest_info: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest_info = Evaluation.get_evaluation_info(evaluation_id)
        status = str(latest_info.get("status") or "").upper()
        if status in TERMINAL_EVALUATION_STATUSES:
            return latest_info
        # If the subprocess exited with an error, surface it immediately.
        if process is not None:
            returncode = process.poll()
            if returncode is not None and returncode != 0:
                stderr_tail = ""
                stdout_tail = ""
                if stderr_log is not None:
                    try:
                        stderr_log.seek(0)
                        stderr_tail = stderr_log.read().decode("utf-8", errors="replace")[-3000:]
                    except Exception:
                        pass
                if stdout_log is not None:
                    try:
                        stdout_log.seek(0)
                        stdout_tail = stdout_log.read().decode("utf-8", errors="replace")[-3000:]
                    except Exception:
                        pass
                raise RuntimeError(
                    f"Feedback evaluation subprocess exited with error (exit={returncode}) "
                    f"for evaluation {evaluation_id}. Last status={status}.\n"
                    f"STDERR tail:\n{stderr_tail}\n"
                    f"STDOUT tail:\n{stdout_tail}"
                )
        time.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"Timed out waiting for evaluation '{evaluation_id}' to reach terminal status after "
        f"{timeout_seconds}s."
    )


def _metric_value(metrics: Sequence[Dict[str, Any]], metric_name: str) -> Optional[float]:
    for metric in metrics or []:
        if not isinstance(metric, dict):
            continue
        if str(metric.get("name", "")).strip().lower() != metric_name.strip().lower():
            continue
        value = metric.get("value")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def build_feedback_run_summary(
    *,
    request: FeedbackRunnerRequest,
    evaluation_id: str,
    evaluation_info: Dict[str, Any],
    resolved_task_id: str,
) -> Dict[str, Any]:
    metrics = evaluation_info.get("metrics") or []
    misclassification_analysis = evaluation_info.get("misclassification_analysis") or {}
    root_cause = evaluation_info.get("root_cause") or {}
    primary_next_action = misclassification_analysis.get("primary_next_action")
    if isinstance(primary_next_action, dict):
        primary_next_action_value = primary_next_action.get("action")
    else:
        primary_next_action_value = primary_next_action

    total_items = evaluation_info.get("total_items")
    shortfall_count = None
    try:
        if total_items is not None:
            shortfall_count = max(0, int(request.max_items) - int(total_items))
    except (TypeError, ValueError):
        shortfall_count = None

    warnings = []
    if shortfall_count is not None and shortfall_count > 0:
        warnings.append(
            f"Requested {request.max_items} item(s), but only {total_items} available; proceeded with available items."
        )

    summary = {
        "evaluation_id": evaluation_id,
        "status": evaluation_info.get("status"),
        "scorecard": evaluation_info.get("scorecard_name") or evaluation_info.get("scorecard_id") or request.scorecard,
        "score": evaluation_info.get("score_name") or evaluation_info.get("score_id") or request.score,
        "score_version_id": evaluation_info.get("score_version_id"),
        "task_id": resolved_task_id,
        "baseline_evaluation_id": evaluation_info.get("baseline_evaluation_id"),
        "window_days": request.days,
        "max_items": request.max_items,
        "sampling_mode": request.sampling_mode,
        "sample_seed": request.sample_seed,
        "max_category_summary_items": request.max_category_summary_items,
        "processed_items": evaluation_info.get("processed_items"),
        "total_items": evaluation_info.get("total_items"),
        "selection_shortfall_count": shortfall_count,
        "warnings": warnings,
        "metrics": {
            "ac1": _metric_value(metrics, "Alignment"),
            "accuracy": _metric_value(metrics, "Accuracy"),
            "precision": _metric_value(metrics, "Precision"),
            "recall": _metric_value(metrics, "Recall"),
        },
        "root_cause": {
            "present": bool(root_cause),
            "topic_count": len(root_cause.get("topics") or []),
            "primary_next_action": primary_next_action_value,
            "optimization_applicability": misclassification_analysis.get("optimization_applicability"),
        },
        "dashboard_url": f"https://app.plexusanalytics.com/evaluations/{evaluation_id}",
    }
    return summary


def format_feedback_run_kanbus_comment(summary: Dict[str, Any]) -> str:
    status = summary.get("status") or "UNKNOWN"
    metrics = summary.get("metrics") or {}
    root_cause = summary.get("root_cause") or {}
    lines = [
        "### Feedback Evaluation Runner Result",
        "",
        f"- `evaluation_id`: `{summary.get('evaluation_id')}`",
        f"- `status`: `{status}`",
        f"- `scorecard`: `{summary.get('scorecard')}`",
        f"- `score`: `{summary.get('score')}`",
        f"- `score_version_id`: `{summary.get('score_version_id') or 'unset'}`",
        f"- `task_id`: `{summary.get('task_id')}`",
        f"- `window_days`: `{summary.get('window_days')}`",
        f"- `max_items`: `{summary.get('max_items')}`",
        f"- `sampling_mode`: `{summary.get('sampling_mode')}`",
        f"- `sample_seed`: `{summary.get('sample_seed')}`",
        f"- `processed/total`: `{summary.get('processed_items')}` / `{summary.get('total_items')}`",
        f"- `selection_shortfall_count`: `{summary.get('selection_shortfall_count')}`",
        f"- `AC1`: `{metrics.get('ac1')}`",
        f"- `Accuracy`: `{metrics.get('accuracy')}`",
        f"- `Precision`: `{metrics.get('precision')}`",
        f"- `Recall`: `{metrics.get('recall')}`",
        f"- `RCA present`: `{root_cause.get('present')}`",
        f"- `RCA topics`: `{root_cause.get('topic_count')}`",
        f"- `Primary next action`: `{root_cause.get('primary_next_action')}`",
        f"- `Optimization applicability`: `{root_cause.get('optimization_applicability')}`",
        f"- Dashboard: {summary.get('dashboard_url')}",
    ]
    for warning in summary.get("warnings") or []:
        lines.append(f"- `warning`: {warning}")
    return "\n".join(lines)


def post_kanbus_comment(*, issue_id: str, comment: str) -> None:
    if not issue_id:
        raise ValueError("issue_id is required.")
    if not comment:
        raise ValueError("comment is required.")
    subprocess.run(["kbs", "comment", issue_id, comment], check=True)


def run_feedback_evaluation_orchestrated(
    *,
    request: FeedbackRunnerRequest,
    client: Any,
    account_id: str,
    plexus_bin: Optional[str] = None,
    creation_timeout_seconds: int = 180,
    completion_timeout_seconds: int = 7200,
    poll_interval_seconds: int = 5,
    kanbus_issue_id: Optional[str] = None,
    on_evaluation_created: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    if request.days is not None and request.days <= 0:
        raise ValueError("days must be > 0 when provided.")
    if request.max_items <= 0:
        raise ValueError("max_items must be > 0.")
    request_sampling_mode = normalize_feedback_sampling_mode(request.sampling_mode)
    if request_sampling_mode != "random" and request.sample_seed is not None:
        raise ValueError("sample_seed is only valid when sampling_mode is 'random'.")
    if request.max_category_summary_items <= 0:
        raise ValueError("max_category_summary_items must be > 0.")

    resolved_plexus_bin = plexus_bin or os.environ.get("PLEXUS_BIN") or "plexus"
    resolved_task_id = ensure_feedback_runner_task(
        client=client,
        account_id=account_id,
        scorecard=request.scorecard,
        score=request.score,
        version=request.version,
        task_id=request.task_id,
    )
    normalized_request = FeedbackRunnerRequest(
        scorecard=request.scorecard,
        score=request.score,
        days=request.days,
        version=request.version,
        baseline=request.baseline,
        current_baseline=request.current_baseline,
        max_items=request.max_items,
        sampling_mode=request_sampling_mode,
        sample_seed=request.sample_seed,
        max_category_summary_items=request.max_category_summary_items,
        task_id=request.task_id,
        use_yaml=request.use_yaml,
    )
    command = build_feedback_command(
        plexus_bin=resolved_plexus_bin,
        request=normalized_request,
        resolved_task_id=resolved_task_id,
    )

    log_dir = os.path.join(os.path.expanduser("~"), ".plexus", "feedback-runner-logs")
    os.makedirs(log_dir, exist_ok=True)
    log_prefix = f"feedback-{resolved_task_id or 'unknown'}"
    stdout_path = os.path.join(log_dir, f"{log_prefix}-stdout.log")
    stderr_path = os.path.join(log_dir, f"{log_prefix}-stderr.log")

    with open(stdout_path, "w+b") as stdout_log, open(stderr_path, "w+b") as stderr_log:
        process = subprocess.Popen(
            command,
            stdout=stdout_log,
            stderr=stderr_log,
        )
        try:
            try:
                evaluation_id = wait_for_feedback_evaluation_id(
                    client=client,
                    account_id=account_id,
                    task_id=resolved_task_id,
                    timeout_seconds=creation_timeout_seconds,
                    poll_interval_seconds=max(1, poll_interval_seconds),
                    process=process,
                )
            except RuntimeError:
                # Capture stderr from the crashed subprocess for diagnostics
                stderr_log.seek(0)
                tail = stderr_log.read().decode("utf-8", errors="replace")[-3000:]
                stdout_log.seek(0)
                stdout_tail = stdout_log.read().decode("utf-8", errors="replace")[-3000:]
                raise RuntimeError(
                    f"Feedback evaluation process exited before evaluation record creation "
                    f"(exit={process.poll()}).\n"
                    f"Command: {' '.join(command)}\n"
                    f"STDERR tail:\n{tail}\n"
                    f"STDOUT tail:\n{stdout_tail}"
                )
            # Notify caller as soon as eval ID is known (e.g. for early notes)
            if on_evaluation_created:
                try:
                    on_evaluation_created(evaluation_id)
                except Exception:
                    pass  # Don't let callback failure break the eval
            evaluation_info = wait_for_feedback_evaluation_terminal_status(
                evaluation_id=evaluation_id,
                timeout_seconds=completion_timeout_seconds,
                poll_interval_seconds=max(1, poll_interval_seconds),
                process=process,
                stderr_log=stderr_log,
                stdout_log=stdout_log,
            )
            _killed_for_timeout = False
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                _killed_for_timeout = True
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    f"Feedback evaluation process did not exit after evaluation completion for {evaluation_id}. "
                    "Killed subprocess — evaluation data is already persisted."
                )
            if not _killed_for_timeout and process.returncode not in (0, None):
                stderr_log.seek(0)
                tail = stderr_log.read().decode("utf-8", errors="replace")[-3000:]
                raise RuntimeError(
                    "Feedback evaluation process exited non-zero "
                    f"(exit={process.returncode}) for evaluation {evaluation_id}. stderr tail:\n{tail}"
                )
        except Exception:
            if process.poll() is None:
                process.kill()
            raise

    summary = build_feedback_run_summary(
        request=normalized_request,
        evaluation_id=evaluation_id,
        evaluation_info=evaluation_info,
        resolved_task_id=resolved_task_id,
    )

    if kanbus_issue_id:
        post_kanbus_comment(
            issue_id=kanbus_issue_id,
            comment=format_feedback_run_kanbus_comment(summary),
        )

    return summary
