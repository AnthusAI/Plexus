from __future__ import annotations

from datetime import datetime, timezone, timedelta
import socket
import os
import signal
import threading
import traceback
from typing import Optional, Tuple, Dict, Any
import logging
import json
import yaml
import click

from plexus.cli.shared.task_progress_tracker import TaskProgressTracker
from plexus.cli.shared.stage_configurations import get_procedure_stage_configs
from plexus.cli.shared.task_output_storage import persist_task_output_artifact
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.procedure import Procedure as DashboardProcedure
from plexus.dashboard.api.models.task import Task
from plexus.cli.procedure.builtin_procedures import is_builtin_procedure_id

logger = logging.getLogger(__name__)


class ProcedureRunTermination(BaseException):
    """Raised when the direct CLI procedure process receives a termination signal."""

    def __init__(self, signum: int):
        self.signum = int(signum)
        try:
            self.signal_name = signal.Signals(signum).name
        except Exception:
            self.signal_name = f"SIG{signum}"
        super().__init__(f"Procedure run interrupted by {self.signal_name}")


def _to_json_safe(value: Any) -> Any:
    """Convert arbitrary values into JSON-safe structures."""
    return json.loads(json.dumps(value, default=str))


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


def _json_dumps(value: Dict[str, Any]) -> str:
    return json.dumps(_to_json_safe(value), default=str)


def _build_runtime_identity(command: Optional[str]) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "started_at": now_iso,
        "lastHeartbeatAt": now_iso,
        "command": command or "",
    }


def _load_procedure_metadata(client: PlexusDashboardClient, procedure_id: str) -> Optional[Dict[str, Any]]:
    query = """
    query GetProcedureTelemetry($id: ID!) {
        getProcedure(id: $id) {
            id
            metadata
            waitingOnMessageId
        }
    }
    """
    try:
        result = client.execute(query, {"id": procedure_id})
    except Exception as exc:
        logger.warning("Could not load procedure metadata for %s: %s", procedure_id, exc)
        return None

    procedure = result.get("getProcedure") or {}
    return _parse_json_dict(procedure.get("metadata"))


def _update_procedure_status_and_metadata(
    client: PlexusDashboardClient,
    procedure_id: str,
    *,
    status: Optional[str] = None,
    metadata_patch: Optional[Dict[str, Any]] = None,
    remove_metadata_keys: Optional[list[str]] = None,
) -> None:
    metadata = _load_procedure_metadata(client, procedure_id)
    update_input: Dict[str, Any] = {"id": procedure_id}
    if status is not None:
        update_input["status"] = status
    if metadata is not None:
        if remove_metadata_keys:
            for key in remove_metadata_keys:
                metadata.pop(key, None)
        if metadata_patch:
            metadata.update(_to_json_safe(metadata_patch))
        update_input["metadata"] = _json_dumps(metadata)
    elif metadata_patch or remove_metadata_keys:
        logger.warning(
            "Skipping procedure metadata merge for %s because current metadata could not be loaded",
            procedure_id,
        )

    mutation = """
    mutation UpdateProcedureTelemetry($input: UpdateProcedureInput!) {
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
            rootNodeId
            metadata
            waitingOnMessageId
            createdAt
            updatedAt
            accountId
            scorecardId
            scoreId
            scoreVersionId
        }
    }
    """
    client.execute(mutation, {"input": update_input})


def _merge_task_metadata(task: Task, patch: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = _parse_json_dict(task.metadata)
    if patch:
        metadata.update(_to_json_safe(patch))
    return metadata


def _current_task_phase(task: Optional[Task]) -> Optional[str]:
    if not task:
        return None

    try:
        stages = list(task.get_stages())
    except Exception as exc:
        logger.debug("Could not load task stages for %s: %s", getattr(task, "id", None), exc)
        return None

    current_stage_id = getattr(task, "currentStageId", None)
    if current_stage_id:
        stage = next((item for item in stages if item.id == current_stage_id), None)
        if stage and getattr(stage, "name", None):
            return str(stage.name)

    running_stage = next((item for item in stages if getattr(item, "status", None) == "RUNNING"), None)
    if running_stage and getattr(running_stage, "name", None):
        return str(running_stage.name)

    pending_stage = next((item for item in stages if getattr(item, "status", None) == "PENDING"), None)
    if pending_stage and getattr(pending_stage, "name", None):
        return str(pending_stage.name)

    return None


def _system_exit_is_failure(code: Any) -> bool:
    if code is None:
        return False
    if isinstance(code, int):
        return code != 0
    return True


def _extract_run_parameters_from_procedure_yaml(procedure_yaml: Optional[str]) -> Dict[str, Any]:
    """Extract resolved run parameter values from procedure YAML.

    Resolution order per parameter:
    1) explicit value
    2) default value
    """
    if not procedure_yaml:
        return {}

    try:
        config = yaml.safe_load(procedure_yaml)
    except Exception:
        return {}

    if not isinstance(config, dict):
        return {}

    resolved: Dict[str, Any] = {}

    mapping_params = config.get("params")
    if isinstance(mapping_params, dict):
        for name, definition in mapping_params.items():
            if not isinstance(definition, dict):
                continue
            if "value" in definition:
                resolved[str(name)] = definition.get("value")
            elif "default" in definition:
                resolved[str(name)] = definition.get("default")

    list_params = config.get("parameters")
    if isinstance(list_params, list):
        for definition in list_params:
            if not isinstance(definition, dict):
                continue
            name = definition.get("name")
            if not isinstance(name, str) or not name:
                continue
            if "value" in definition:
                resolved[name] = definition.get("value")
            elif "default" in definition:
                resolved[name] = definition.get("default")

    return _to_json_safe(resolved)


def _find_existing_task_for_procedure(procedure_id: str, account_id: str, client) -> Optional[str]:
    """
    Find an existing Task for a procedure by querying using the accountId GSI.

    Args:
        procedure_id: The procedure ID
        account_id: The account ID
        client: The PlexusDashboardClient

    Returns:
        Task ID if found, None otherwise
    """
    try:
        # Use GSI to query tasks for this account
        query = """
        query ListTaskByAccountIdAndUpdatedAt($accountId: String!, $updatedAt: ModelStringKeyConditionInput, $limit: Int, $nextToken: String) {
            listTaskByAccountIdAndUpdatedAt(accountId: $accountId, updatedAt: $updatedAt, limit: $limit, nextToken: $nextToken) {
                items {
                    id
                    target
                }
                nextToken
            }
        }
        """

        # Query all tasks for this account
        very_old_date = "2000-01-01T00:00:00.000Z"
        # Check for both target patterns (ProcedureService uses "procedure/{id}", TaskProgressTracker uses "procedure/run/{id}")
        target_patterns = [f"procedure/run/{procedure_id}", f"procedure/{procedure_id}"]

        next_token = None
        while True:
            variables = {
                "accountId": account_id,
                "updatedAt": {"ge": very_old_date},
                "limit": 1000
            }
            if next_token:
                variables["nextToken"] = next_token

            result = client.execute(query, variables)
            page_tasks = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])

            # Check this page for matching task - prefer "procedure/{id}" format (from ProcedureService)
            found_tasks = []
            for task in page_tasks:
                if task['target'] in target_patterns:
                    found_tasks.append((task['target'], task['id']))

            # Prefer the task created by ProcedureService (without "/run")
            for target, task_id in found_tasks:
                if target == f"procedure/{procedure_id}":
                    logger.info(f"Found existing task {task_id} with target '{target}'")
                    return task_id

            # Fall back to "/run" format if that's all we have
            for target, task_id in found_tasks:
                if target == f"procedure/run/{procedure_id}":
                    logger.info(f"Found existing task {task_id} with target '{target}'")
                    return task_id

            next_token = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('nextToken')
            if not next_token:
                break

        return None

    except Exception as e:
        logger.error(f"Error finding existing task for procedure {procedure_id}: {e}")
        return None


def create_tracker_and_experiment_task(
    *,
    client: PlexusDashboardClient,
    account_id: str,
    procedure_id: str,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None,
    total_items: int = 0,
    run_parameters: Optional[Dict[str, Any]] = None,
    run_options: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[TaskProgressTracker], Optional[DashboardProcedure], Optional['Task']]:
    """Create a TaskProgressTracker for an experiment run.

    Mirrors the evaluation behavior for experiment operations.
    Returns the tracker (with its Task created/claimed) and optionally updates the Experiment record.

    Args:
        client: Dashboard API client
        account_id: Account ID
        procedure_id: Procedure ID to associate with the task
        scorecard_name: Optional scorecard name for metadata
        score_name: Optional score name for metadata
        total_items: Total number of items to process (for Evaluation stage)

    Returns:
        Tuple of (TaskProgressTracker or None, Procedure record or None, Task)
    """
    # Configure stages and create tracker (creates API Task)
    stage_configs = get_procedure_stage_configs(total_items=total_items)
    
    # Build metadata
    metadata = {
        "type": "Experiment Run",
        "procedure_id": procedure_id,
        "task_type": "Experiment Run",
    }
    if run_parameters:
        metadata["run_parameters"] = _to_json_safe(run_parameters)
    if run_options:
        metadata["run_options"] = _to_json_safe(run_options)
    if scorecard_name:
        metadata["scorecard"] = scorecard_name
    if score_name:
        metadata["score"] = score_name
    
    # If this run was launched by CommandDispatch, bind tracking to that claimed task.
    dispatch_task_id = (os.getenv("PLEXUS_DISPATCH_TASK_ID") or "").strip()
    task: Optional[Task] = None
    tracker = None  # ProcedureService manages TaskStages directly via state machine
    if dispatch_task_id:
        try:
            candidate_task = Task.get_by_id(dispatch_task_id, client)
            if not candidate_task:
                logger.warning(
                    "PLEXUS_DISPATCH_TASK_ID=%s was provided but no task was found; falling back to procedure task lookup.",
                    dispatch_task_id,
                )
            elif candidate_task.accountId != account_id:
                logger.warning(
                    "PLEXUS_DISPATCH_TASK_ID=%s belongs to a different account (%s != %s); falling back.",
                    dispatch_task_id,
                    candidate_task.accountId,
                    account_id,
                )
            else:
                command_text = str(candidate_task.command or "")
                target_text = str(candidate_task.target or "")
                if procedure_id in command_text or procedure_id in target_text:
                    task = candidate_task
                    logger.info(
                        "Using dispatch-claimed Task %s for procedure %s from PLEXUS_DISPATCH_TASK_ID",
                        dispatch_task_id,
                        procedure_id,
                    )
                else:
                    logger.warning(
                        "PLEXUS_DISPATCH_TASK_ID=%s does not reference procedure %s; falling back.",
                        dispatch_task_id,
                        procedure_id,
                    )
        except Exception as e:
            logger.warning(
                "Could not load task from PLEXUS_DISPATCH_TASK_ID=%s (%s); falling back to procedure task lookup.",
                dispatch_task_id,
                e,
            )

    # Fallback to the existing procedure-level task model.
    if not task:
        existing_task_id = _find_existing_task_for_procedure(procedure_id, account_id, client)
        if existing_task_id:
            logger.info(f"Reusing existing Task {existing_task_id} for procedure {procedure_id}")
            task = Task.get_by_id(existing_task_id, client)
        else:
            if is_builtin_procedure_id(procedure_id):
                now_iso = datetime.now(timezone.utc).isoformat()
                logger.info("No existing task found for built-in procedure %s; creating one.", procedure_id)
                task = Task.create(
                    client=client,
                    accountId=account_id,
                    type="Procedure Run",
                    status="PENDING",
                    dispatchStatus="PENDING",
                    target=f"procedure/run/{procedure_id}",
                    command=f"procedure run {procedure_id}",
                    metadata=json.dumps(metadata),
                    createdAt=now_iso,
                    updatedAt=now_iso,
                )
            else:
                # This should never happen - ProcedureService.create_procedure() always creates a Task
                logger.error(f"No Task found for procedure {procedure_id}. This indicates the procedure was created incorrectly.")
                logger.error(f"Procedures should always have a Task created by ProcedureService.create_procedure()")
                raise RuntimeError(
                    f"No Task found for procedure {procedure_id}. "
                    f"The procedure may have been created incorrectly or the Task was deleted. "
                    f"Please recreate the procedure."
                )

    # Claim task like CLI (set worker and RUNNING)
    if task:
        worker_id = f"{socket.gethostname()}-{__import__('os').getpid()}"
        task.update(
            accountId=task.accountId,
            type=task.type,
            status='RUNNING',
            target=task.target,
            command=task.command,
            workerNodeId=worker_id,
            startedAt=datetime.now(timezone.utc).isoformat(),
            updatedAt=datetime.now(timezone.utc).isoformat(),
        )

    # Try to get the existing Procedure record and associate via metadata
    procedure_record = None
    try:
        procedure_record = DashboardProcedure.get_by_id(client=client, id=procedure_id)
        if procedure_record and task:
            # Store procedure ID in task metadata for the association
            # This avoids adding new schema relationships that would increase resource count
            task_metadata = task.metadata or {}
            if isinstance(task_metadata, str):
                try:
                    task_metadata = json.loads(task_metadata) if task_metadata else {}
                except Exception:
                    task_metadata = {}
            task_metadata["procedure_id"] = procedure_id
            task_metadata["procedure_type"] = "run"
            if run_parameters:
                task_metadata["run_parameters"] = _to_json_safe(run_parameters)
            if run_options:
                task_metadata["run_options"] = _to_json_safe(run_options)
            
            # Update the task with the metadata
            task.update(
                accountId=task.accountId,
                type=task.type,
                status=task.status,
                target=task.target,
                command=task.command,
                metadata=json.dumps(task_metadata),
                updatedAt=datetime.now(timezone.utc).isoformat(),
            )
            logging.info(f"Associated Task {task.id} with Procedure {procedure_id} via metadata")
    except Exception as e:
        logging.warning(f"Could not get Procedure record {procedure_id}: {str(e)}")
        # Continue without the procedure record - the task tracking still works

    return tracker, procedure_record, task


async def run_experiment_with_task_tracking(
    *,
    procedure_id: str,
    client: Optional[PlexusDashboardClient] = None,
    account_id: Optional[str] = None,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None,
    total_items: int = 0,
    **experiment_options
) -> Dict[str, Any]:
    """Run a procedure with task tracking.
    
    This function creates Task and TaskStage records for progress tracking,
    then runs the actual procedure using the ProcedureService.
    
    Args:
        procedure_id: ID of the procedure to run
        client: Dashboard API client
        account_id: Account ID
        scorecard_name: Optional scorecard name for metadata
        score_name: Optional score name for metadata
        total_items: Total number of items to process
        **experiment_options: Additional options to pass to the experiment runner
        
    Returns:
        Dictionary containing experiment run results and task information
    """
    if not client:
        from plexus.cli.shared.utils import create_client
        client = create_client()
        if not client:
            raise ValueError("Could not create API client")
    
    if not account_id:
        from plexus.cli.report.utils import resolve_account_id_for_command
        account_id = resolve_account_id_for_command(client, None)

    # Capture resolved run parameters and run options in task metadata so the
    # dashboard can show exactly what was used for this run.
    run_options_for_metadata: Dict[str, Any] = {}
    for key, value in experiment_options.items():
        if key.startswith("_"):
            continue
        if key in {"openai_api_key", "context"}:
            continue
        run_options_for_metadata[key] = value

    run_parameters_for_metadata: Dict[str, Any] = {}
    if not is_builtin_procedure_id(procedure_id):
        try:
            procedure_record = DashboardProcedure.get_by_id(client=client, id=procedure_id)
            run_parameters_for_metadata.update(
                _extract_run_parameters_from_procedure_yaml(getattr(procedure_record, "code", None))
            )
        except Exception as e:
            logger.debug("Could not resolve procedure YAML for run parameter capture: %s", e)

    context_params = experiment_options.get("context")
    if isinstance(context_params, dict):
        run_parameters_for_metadata.update(context_params)

    if experiment_options.get("max_iterations") is not None:
        run_parameters_for_metadata["max_iterations"] = experiment_options.get("max_iterations")
    if experiment_options.get("dry_run") is not None:
        run_parameters_for_metadata["dry_run"] = experiment_options.get("dry_run")

    # Create tracker and update experiment
    tracker, experiment_record, task = create_tracker_and_experiment_task(
        client=client,
        account_id=account_id,
        procedure_id=procedure_id,
        scorecard_name=scorecard_name,
        score_name=score_name,
        total_items=total_items,
        run_parameters=run_parameters_for_metadata,
        run_options=run_options_for_metadata,
    )

    result = {
        'procedure_id': procedure_id,
        'task_id': task.id if task else None,
        'status': 'initiated',
        'message': 'Task tracking initialized'
    }

    runtime_identity = _build_runtime_identity(
        task.command if task and getattr(task, "command", None) else f"procedure run {procedure_id}"
    )
    task_ref = tracker.task if tracker and tracker.task else task
    failure_finalized = False
    installed_signal_handlers: Dict[int, Any] = {}

    def _install_signal_guards() -> None:
        if threading.current_thread() is not threading.main_thread():
            return

        def _raise_termination(signum, _frame):
            raise ProcedureRunTermination(signum)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                installed_signal_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, _raise_termination)
            except Exception as exc:
                logger.debug("Could not install signal handler for %s: %s", sig, exc)

    def _restore_signal_guards() -> None:
        for sig, previous in installed_signal_handlers.items():
            try:
                signal.signal(sig, previous)
            except Exception as exc:
                logger.debug("Could not restore signal handler for %s: %s", sig, exc)
        installed_signal_handlers.clear()

    def _mark_run_started() -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if task_ref:
            task_metadata = _merge_task_metadata(task_ref, {"runtime": runtime_identity})
            task_ref.update(
                accountId=task_ref.accountId,
                type=task_ref.type,
                status="RUNNING",
                target=task_ref.target,
                command=task_ref.command,
                metadata=_json_dumps(task_metadata),
                startedAt=now_iso,
                updatedAt=now_iso,
                errorMessage=None,
                errorDetails=None,
            )

        if not is_builtin_procedure_id(procedure_id):
            _update_procedure_status_and_metadata(
                client,
                procedure_id,
                status="RUNNING",
                metadata_patch={"runtime": runtime_identity},
                remove_metadata_keys=["last_failure"],
            )

    def _finalize_failed(
        *,
        kind: str,
        message: str,
        signal_name: Optional[str] = None,
        exception_type: Optional[str] = None,
        traceback_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        nonlocal failure_finalized
        if failure_finalized:
            return {}
        failure_finalized = True

        from plexus.cli.procedure.procedure_executor import _fail_all_task_stages

        terminated_at = datetime.now(timezone.utc).isoformat()
        phase = _current_task_phase(task_ref)
        failure_payload = {
            "kind": kind,
            "signal": signal_name,
            "exception_type": exception_type,
            "message": str(message),
            "phase": phase,
            "terminated_at": terminated_at,
            "pid": runtime_identity.get("pid"),
            "host": runtime_identity.get("host"),
            "traceback": traceback_text,
        }

        if task_ref:
            try:
                _fail_all_task_stages(client, task_ref.id, str(message))
            except Exception as stage_exc:
                logger.warning("Could not fail task stages for %s: %s", task_ref.id, stage_exc, exc_info=True)

            try:
                task_metadata = _merge_task_metadata(task_ref, {"runtime": runtime_identity})
                task_ref.update(
                    accountId=task_ref.accountId,
                    type=task_ref.type,
                    status="FAILED",
                    target=task_ref.target,
                    command=task_ref.command,
                    metadata=_json_dumps(task_metadata),
                    updatedAt=terminated_at,
                    completedAt=terminated_at,
                    errorMessage=str(message)[:2000],
                    errorDetails=_json_dumps(failure_payload),
                )
            except Exception as task_exc:
                logger.warning("Could not persist FAILED task state for %s: %s", task_ref.id, task_exc, exc_info=True)

        if not is_builtin_procedure_id(procedure_id):
            try:
                _update_procedure_status_and_metadata(
                    client,
                    procedure_id,
                    status="FAILED",
                    metadata_patch={
                        "runtime": runtime_identity,
                        "last_failure": failure_payload,
                    },
                )
            except Exception as proc_exc:
                logger.warning(
                    "Could not persist FAILED procedure state for %s: %s",
                    procedure_id,
                    proc_exc,
                    exc_info=True,
                )

        result.update(
            {
                "status": "FAILED",
                "error": str(message),
                "message": f"Experiment failed: {message}",
                "failure": failure_payload,
            }
        )
        return failure_payload

    _install_signal_guards()

    try:
        _mark_run_started()
        from plexus.cli.procedure.stale_timeout import launch_async_stale_timeout_scan

        launch_async_stale_timeout_scan(
            account_id=account_id,
            exclude_procedure_id=procedure_id,
        )

        # Start with Hypothesis stage (only if we have a tracker)
        if tracker:
            tracker.current_stage.status_message = "Starting experiment hypothesis generation"
            tracker.update(current_items=0)

        # Import and run the actual procedure using ProcedureService
        from plexus.cli.procedure.service import ProcedureService
        service = ProcedureService(client)

        # Run the procedure (this is the actual hypothesis generation work)
        run_options = dict(experiment_options)
        run_options.setdefault("account_id", account_id)
        # Pass the task ID so the executor can update stage status in real-time
        if task_ref and task_ref.id:
            run_options.setdefault("_task_id_for_stage_tracking", task_ref.id)
        experiment_result = await service.run_experiment(procedure_id, **run_options)

        procedure_status = str(experiment_result.get("status") or "").upper()
        is_waiting_for_human = procedure_status == "WAITING_FOR_HUMAN"
        is_success = bool(experiment_result.get("success"))
        logger.info(
            f"[PROCEDURE_RUN] procedure={procedure_id} success={is_success} "
            f"status={procedure_status} result_keys={list(experiment_result.keys())}"
        )

        if is_waiting_for_human:
            mapped_task_status = "RUNNING"
            mapped_procedure_status = "WAITING_FOR_HUMAN"
        elif is_success:
            mapped_task_status = "COMPLETED"
            mapped_procedure_status = "COMPLETED"
            # Only advance tracker stages on success — on failure the executor already
            # marked them FAILED via _fail_all_task_stages.
            if tracker:
                tracker.advance_stage()  # Hypothesis → Evaluation
                tracker.current_stage.status_message = "Running experiment evaluation"
                tracker.update(current_items=0)
                tracker.advance_stage()  # Evaluation → Analysis
                tracker.current_stage.status_message = "Analyzing experiment results"
                tracker.update(current_items=total_items)
                tracker.current_stage.complete()
        else:
            mapped_task_status = "FAILED"
            mapped_procedure_status = "FAILED"
            err_text = experiment_result.get("error") or experiment_result.get("message") or "Procedure failed"
            logger.warning(
                f"[PROCEDURE_RUN] procedure={procedure_id} reported failure — "
                f"error={experiment_result.get('error')} message={experiment_result.get('message')}"
            )
            _finalize_failed(kind="exception", message=str(err_text))

        # Complete or update the task
        if task_ref and mapped_task_status != "FAILED":
            compact_output, attached_files, _attachment_key = persist_task_output_artifact(
                task_id=task_ref.id,
                output_payload=experiment_result,
                format_type="json",
                existing_attached_files=getattr(task_ref, "attachedFiles", None),
                status=mapped_task_status.lower(),
            )
            update_data = {
                "accountId": task_ref.accountId,
                "type": task_ref.type,
                "status": mapped_task_status,
                "target": task_ref.target,
                "command": task_ref.command,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "output": compact_output,
                "attachedFiles": attached_files,
            }
            if mapped_task_status in {"COMPLETED", "FAILED"}:
                update_data["completedAt"] = datetime.now(timezone.utc).isoformat()
            task_ref.update(**update_data)

        # Keep procedure status consistent with the actual run outcome for DB-backed procedures.
        if mapped_procedure_status != "FAILED" and not is_builtin_procedure_id(procedure_id):
            try:
                logger.info(f"[PROCEDURE_RUN] Updating procedure {procedure_id} status → {mapped_procedure_status}")
                _update_procedure_status_and_metadata(client, procedure_id, status=mapped_procedure_status)
            except Exception as _pe:
                logger.warning(f"Failed to update procedure status for {procedure_id}: {_pe}")

        # Update result with experiment outcome
        result.update(experiment_result)
        result["status"] = mapped_procedure_status
        result["message"] = (
            "Experiment completed successfully"
            if mapped_procedure_status == "COMPLETED"
            else result.get("message", "Experiment execution updated")
        )

    except ProcedureRunTermination as exc:
        logger.warning("Procedure %s interrupted by %s", procedure_id, exc.signal_name)
        _finalize_failed(
            kind="signal",
            signal_name=exc.signal_name,
            message=f"Procedure run interrupted by {exc.signal_name}",
        )
        raise SystemExit(128 + exc.signum) from None
    except KeyboardInterrupt:
        logger.warning("Procedure %s interrupted by keyboard", procedure_id)
        _finalize_failed(
            kind="signal",
            signal_name="SIGINT",
            message="Procedure run interrupted by SIGINT",
        )
        raise
    except click.Abort as exc:
        logger.warning("Procedure %s aborted", procedure_id)
        _finalize_failed(
            kind="abort",
            exception_type=type(exc).__name__,
            message=str(exc) or "Procedure run aborted",
        )
        raise
    except SystemExit as exc:
        if _system_exit_is_failure(exc.code):
            logger.warning("Procedure %s exited early with code %s", procedure_id, exc.code)
            _finalize_failed(
                kind="system_exit",
                exception_type=type(exc).__name__,
                message=f"Procedure run exited with status {exc.code}",
            )
        raise
    except Exception as exc:
        logging.error(f"Experiment run failed: {str(exc)}", exc_info=True)
        _finalize_failed(
            kind="exception",
            exception_type=type(exc).__name__,
            message=str(exc),
            traceback_text=traceback.format_exc(),
        )
    finally:
        _restore_signal_guards()
    
    return result
