from __future__ import annotations

from datetime import datetime, timezone, timedelta
import socket
from typing import Optional, Tuple, Dict, Any
import logging
import json

from plexus.cli.shared.task_progress_tracker import TaskProgressTracker
from plexus.cli.shared.stage_configurations import get_procedure_stage_configs
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.procedure import Procedure as DashboardProcedure
from plexus.dashboard.api.models.task import Task

logger = logging.getLogger(__name__)


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
    
    # Build metadata
    metadata = {
        "type": "Experiment Run",
        "procedure_id": procedure_id,
        "task_type": "Experiment Run",
    }
    if scorecard_name:
        metadata["scorecard"] = scorecard_name
    if score_name:
        metadata["score"] = score_name
    
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
            task_metadata["procedure_id"] = procedure_id
            task_metadata["procedure_type"] = "run"
            
            # Update the task with the metadata
            task.update(
                accountId=task.accountId,
                type=task.type,
                status=task.status,
                target=task.target,
                command=task.command,
                metadata=task_metadata,
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
        
        # Complete Hypothesis stage and advance to Evaluation
        if tracker:
            tracker.advance_stage()  # This completes Hypothesis and starts Evaluation
            tracker.current_stage.status_message = "Running experiment evaluation"
            tracker.update(current_items=0)
        
        # Since we're not actually running evaluation yet, mark it as complete and advance to Analysis
        if tracker:
            tracker.advance_stage()  # This completes Evaluation and starts Analysis
            tracker.current_stage.status_message = "Analyzing experiment results"
            tracker.update(current_items=total_items)
        
        # Since we're not actually running analysis yet, complete the Analysis stage
        if tracker:
            tracker.current_stage.complete()  # Complete the final Analysis stage
        
        # Complete the task
        if tracker and tracker.task:
            tracker.task.update(
                accountId=tracker.task.accountId,
                type=tracker.task.type,
                status='COMPLETED',
                target=tracker.task.target,
                command=tracker.task.command,
                completedAt=datetime.now(timezone.utc).isoformat(),
                updatedAt=datetime.now(timezone.utc).isoformat(),
                output=json.dumps(experiment_result, default=str),
            )
        
        # Update result with experiment outcome
        result.update(experiment_result)
        result['status'] = 'completed'
        result['message'] = 'Experiment completed successfully'
        
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
