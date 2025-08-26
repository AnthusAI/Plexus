from __future__ import annotations

from datetime import datetime, timezone
import socket
from typing import Optional, Tuple, Dict, Any
import logging
import json

from plexus.cli.shared.task_progress_tracker import TaskProgressTracker
from plexus.cli.shared.stage_configurations import get_experiment_stage_configs
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.experiment import Experiment as DashboardExperiment


def create_tracker_and_experiment_task(
    *,
    client: PlexusDashboardClient,
    account_id: str,
    experiment_id: str,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None,
    total_items: int = 0,
) -> Tuple[TaskProgressTracker, Optional[DashboardExperiment]]:
    """Create a TaskProgressTracker for an experiment run.

    Mirrors the evaluation behavior for experiment operations.
    Returns the tracker (with its Task created/claimed) and optionally updates the Experiment record.
    
    Args:
        client: Dashboard API client
        account_id: Account ID
        experiment_id: Experiment ID to associate with the task
        scorecard_name: Optional scorecard name for metadata
        score_name: Optional score name for metadata
        total_items: Total number of items to process (for Evaluation stage)
    
    Returns:
        Tuple of (TaskProgressTracker, Experiment record or None)
    """
    # Configure stages and create tracker (creates API Task)
    stage_configs = get_experiment_stage_configs(total_items=total_items)
    
    # Build metadata
    metadata = {
        "type": "Experiment Run",
        "experiment_id": experiment_id,
        "task_type": "Experiment Run",
    }
    if scorecard_name:
        metadata["scorecard"] = scorecard_name
    if score_name:
        metadata["score"] = score_name
    
    # Create task tracker
    tracker = TaskProgressTracker(
        total_items=total_items,
        stage_configs=stage_configs,
        target=f"experiment/run/{experiment_id}",
        command=f"experiment run {experiment_id}",
        description=f"Experiment run for {experiment_id}",
        dispatch_status="DISPATCHED",
        prevent_new_task=False,
        metadata=metadata,
        account_id=account_id,
        client=client,
    )

    # Claim task like CLI (set worker and RUNNING)
    task = tracker.task
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

    # Try to get the existing Experiment record and associate via metadata
    experiment_record = None
    try:
        experiment_record = DashboardExperiment.get_by_id(client=client, id=experiment_id)
        if experiment_record and task:
            # Store experiment ID in task metadata for the association
            # This avoids adding new schema relationships that would increase resource count
            task_metadata = task.metadata or {}
            task_metadata["experiment_id"] = experiment_id
            task_metadata["experiment_type"] = "run"
            
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
            logging.info(f"Associated Task {task.id} with Experiment {experiment_id} via metadata")
    except Exception as e:
        logging.warning(f"Could not get Experiment record {experiment_id}: {str(e)}")
        # Continue without the experiment record - the task tracking still works

    return tracker, experiment_record


async def run_experiment_with_task_tracking(
    *,
    experiment_id: str,
    client: Optional[PlexusDashboardClient] = None,
    account_id: Optional[str] = None,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None,
    total_items: int = 0,
    **experiment_options
) -> Dict[str, Any]:
    """Run an experiment with task tracking.
    
    This function creates Task and TaskStage records for progress tracking,
    then runs the actual experiment using the ExperimentService.
    
    Args:
        experiment_id: ID of the experiment to run
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
    tracker, experiment_record = create_tracker_and_experiment_task(
        client=client,
        account_id=account_id,
        experiment_id=experiment_id,
        scorecard_name=scorecard_name,
        score_name=score_name,
        total_items=total_items,
    )
    
    result = {
        'experiment_id': experiment_id,
        'task_id': tracker.task.id if tracker.task else None,
        'status': 'initiated',
        'message': 'Task tracking initialized'
    }
    
    try:
        # Start with Hypothesis stage
        if tracker:
            tracker.current_stage.status_message = "Starting experiment hypothesis generation"
            tracker.update(current_items=0)
        
        # Import and run the actual experiment using ExperimentService
        from plexus.cli.experiment.service import ExperimentService
        service = ExperimentService(client)
        
        # Run the experiment (this is the actual hypothesis generation work)
        experiment_result = await service.run_experiment(experiment_id, **experiment_options)
        
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
