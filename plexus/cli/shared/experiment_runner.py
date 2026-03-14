from __future__ import annotations

from datetime import datetime, timezone, timedelta
import socket
from typing import Optional, Tuple, Dict, Any
import logging
import json
import os
from pathlib import Path

from plexus.cli.shared.task_progress_tracker import TaskProgressTracker
from plexus.cli.shared.stage_configurations import get_procedure_stage_configs
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.procedure import Procedure as DashboardProcedure
from plexus.dashboard.api.models.task import Task

logger = logging.getLogger(__name__)


def _safe_task_metadata(raw_metadata: Any) -> Dict[str, Any]:
    if isinstance(raw_metadata, dict):
        return dict(raw_metadata)
    if isinstance(raw_metadata, str) and raw_metadata.strip():
        try:
            parsed = json.loads(raw_metadata)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def _derive_procedure_task_state(experiment_result: Dict[str, Any]) -> str:
    status = str(experiment_result.get("status") or "").upper()
    if status == "WAITING_FOR_HUMAN":
        return "WAITING_FOR_HUMAN"
    if bool(experiment_result.get("success")) or status in {"COMPLETED", "COMPLETE"}:
        return "COMPLETED"
    return "FAILED"


def _metadata_json(metadata: Dict[str, Any]) -> str:
    return json.dumps(metadata or {}, default=str)


def _read_git_sha_without_subprocess() -> Optional[str]:
    try:
        repo_root = Path(__file__).resolve().parents[3]
        git_dir = repo_root / ".git"
        head_path = git_dir / "HEAD"
        if not head_path.exists():
            return None

        head_text = head_path.read_text(encoding="utf-8").strip()
        if head_text.startswith("ref: "):
            ref_path = git_dir / head_text[5:].strip()
            if ref_path.exists():
                return ref_path.read_text(encoding="utf-8").strip()[:12] or None
            return None
        return head_text[:12] or None
    except Exception:
        return None


def _runtime_fingerprint() -> Dict[str, Any]:
    expected_sha = (os.getenv("PLEXUS_EXPECTED_GIT_SHA") or os.getenv("EXPECTED_GIT_SHA") or "").strip() or None
    build_timestamp = (os.getenv("PLEXUS_BUILD_TIMESTAMP") or os.getenv("BUILD_TIMESTAMP") or "").strip() or None
    git_sha = (os.getenv("PLEXUS_GIT_SHA") or os.getenv("GIT_SHA") or "").strip() or None

    if not git_sha:
        git_sha = _read_git_sha_without_subprocess()

    try:
        import tactus as tactus_pkg
        tactus_version = getattr(tactus_pkg, "__version__", None) or "unknown"
    except Exception:
        tactus_version = "unavailable"

    return {
        "git_sha": git_sha,
        "expected_git_sha": expected_sha,
        "build_timestamp": build_timestamp,
        "tactus_version": tactus_version,
    }


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
    
    # Find or create task for this procedure
    existing_task_id = _find_existing_task_for_procedure(procedure_id, account_id, client)

    if existing_task_id:
        logger.info(f"Reusing existing Task {existing_task_id} for procedure {procedure_id}")
        # Get the existing task directly - DON'T use TaskProgressTracker since
        # ProcedureService manages TaskStages directly via state machine
        task = Task.get_by_id(existing_task_id, client)
        tracker = None  # No tracker needed - state machine handles it
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
        reset_metadata = _safe_task_metadata(task.metadata)
        reset_metadata["procedure_id"] = procedure_id
        reset_metadata["procedure_type"] = "run"
        reset_metadata["procedure_target"] = f"procedure/run/{procedure_id}"
        reset_metadata["runtime_fingerprint"] = _runtime_fingerprint()
        task.update(
            accountId=task.accountId,
            type=task.type,
            status='RUNNING',
            target=f"procedure/run/{procedure_id}",
            command=task.command,
            workerNodeId=worker_id,
            startedAt=datetime.now(timezone.utc).isoformat(),
            updatedAt=datetime.now(timezone.utc).isoformat(),
            completedAt=None,
            errorMessage=None,
            errorDetails=None,
            stdout=None,
            stderr=None,
            metadata=_metadata_json(reset_metadata),
        )

    # Try to get the existing Procedure record and associate via metadata
    procedure_record = None
    try:
        procedure_record = DashboardProcedure.get_by_id(client=client, id=procedure_id)
        if procedure_record and task:
            # Store procedure ID in task metadata for the association
            # This avoids adding new schema relationships that would increase resource count
            task_metadata = _safe_task_metadata(task.metadata)
            task_metadata["procedure_id"] = procedure_id
            task_metadata["procedure_type"] = "run"
            task_metadata["procedure_target"] = f"procedure/run/{procedure_id}"
            task_metadata["runtime_fingerprint"] = _runtime_fingerprint()
            
            # Update the task with the metadata
            task.update(
                accountId=task.accountId,
                type=task.type,
                status=task.status,
                target=task.target,
                command=task.command,
                metadata=_metadata_json(task_metadata),
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
    
    # Create tracker and update experiment
    tracker, experiment_record, task = create_tracker_and_experiment_task(
        client=client,
        account_id=account_id,
        procedure_id=procedure_id,
        scorecard_name=scorecard_name,
        score_name=score_name,
        total_items=total_items,
    )

    result = {
        'procedure_id': procedure_id,
        'task_id': task.id if task else None,
        'status': 'initiated',
        'message': 'Task tracking initialized'
    }

    try:
        # Start with Hypothesis stage (only if we have a tracker)
        if tracker:
            tracker.current_stage.status_message = "Starting experiment hypothesis generation"
            tracker.update(current_items=0)
        
        # Import and run the actual procedure using ProcedureService
        from plexus.cli.procedure.service import ProcedureService
        service = ProcedureService(client)
        
        # Run the procedure (this is the actual hypothesis generation work)
        experiment_result = await service.run_experiment(procedure_id, **experiment_options)
        
        derived_state = _derive_procedure_task_state(experiment_result)

        # Complete progress stages only when terminally completed.
        if tracker and derived_state == 'COMPLETED':
            tracker.advance_stage()  # This completes Hypothesis and starts Evaluation
            tracker.current_stage.status_message = "Running experiment evaluation"
            tracker.update(current_items=0)
            tracker.advance_stage()  # This completes Evaluation and starts Analysis
            tracker.current_stage.status_message = "Analyzing experiment results"
            tracker.update(current_items=total_items)
            tracker.current_stage.complete()  # Complete the final Analysis stage

        active_task = (tracker.task if tracker and tracker.task else task)
        if active_task:
            task_metadata = _safe_task_metadata(active_task.metadata)
            task_metadata["procedure_status"] = derived_state
            if experiment_result.get("pending_message_id"):
                task_metadata["waiting_on_message_id"] = experiment_result.get("pending_message_id")
            task_metadata["runtime_fingerprint"] = _runtime_fingerprint()

            task_update_data = {
                "accountId": active_task.accountId,
                "type": active_task.type,
                "target": active_task.target,
                "command": active_task.command,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "metadata": _metadata_json(task_metadata),
                "output": json.dumps(experiment_result, default=str),
            }

            if derived_state == "COMPLETED":
                task_update_data["status"] = "COMPLETED"
                task_update_data["completedAt"] = datetime.now(timezone.utc).isoformat()
            elif derived_state == "WAITING_FOR_HUMAN":
                task_update_data["status"] = "RUNNING"
            else:
                error_text = (
                    experiment_result.get("error")
                    or experiment_result.get("message")
                    or "Procedure execution failed"
                )
                task_update_data["status"] = "FAILED"
                task_update_data["completedAt"] = datetime.now(timezone.utc).isoformat()
                task_update_data["errorMessage"] = str(error_text)
                task_update_data["errorDetails"] = json.dumps(experiment_result, default=str)

            active_task.update(**task_update_data)

        # Update result with experiment outcome
        result.update(experiment_result)
        if derived_state == "WAITING_FOR_HUMAN":
            result['status'] = 'waiting_for_human'
            result['message'] = 'Procedure is waiting for human input'
        elif derived_state == "COMPLETED":
            result['status'] = 'completed'
            result['message'] = 'Experiment completed successfully'
        else:
            result['status'] = 'error'
            result['message'] = f"Experiment failed: {experiment_result.get('error') or 'unknown error'}"

    except Exception as e:
        logging.error(f"Experiment run failed: {str(e)}", exc_info=True)
        
        # Update task with error
        if tracker and tracker.task:
            tracker.task.update(
                accountId=tracker.task.accountId,
                type=tracker.task.type,
                status='FAILED',
                target=tracker.task.target,
                command=tracker.task.command,
                completedAt=datetime.now(timezone.utc).isoformat(),
                updatedAt=datetime.now(timezone.utc).isoformat(),
                errorMessage=str(e),
                errorDetails=json.dumps({'error': str(e), 'type': type(e).__name__}, default=str),
            )
        
        result.update({
            'status': 'error',
            'error': str(e),
            'message': f'Experiment failed: {str(e)}'
        })
    
    return result
