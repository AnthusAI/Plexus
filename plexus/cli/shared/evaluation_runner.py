from __future__ import annotations

from datetime import datetime, timezone
import socket
from typing import Optional, Tuple
import logging

from plexus.cli.shared.task_progress_tracker import TaskProgressTracker
from plexus.cli.shared.stage_configurations import get_evaluation_stage_configs
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation


def create_tracker_and_evaluation(
    *,
    client: PlexusDashboardClient,
    account_id: str,
    scorecard_name: str,
    number_of_samples: int,
    sampling_method: str = "random",
    score_name: Optional[str] = None,
) -> Tuple[TaskProgressTracker, DashboardEvaluation]:
    """Create a TaskProgressTracker and an Evaluation record for an accuracy evaluation.

    Mirrors the CLI behavior so other callers (e.g., MCP server tools) don't duplicate logic.
    Returns the tracker (with its Task created/claimed) and the Evaluation record.
    """
    # Configure stages and create tracker (creates API Task)
    stage_configs = get_evaluation_stage_configs(total_items=number_of_samples)
    tracker = TaskProgressTracker(
        total_items=number_of_samples,
        stage_configs=stage_configs,
        target=f"evaluation/accuracy/{scorecard_name}",
        command=f"evaluate accuracy --scorecard {scorecard_name}",
        description=f"Accuracy evaluation for {scorecard_name}",
        dispatch_status="DISPATCHED",
        prevent_new_task=False,
        metadata={
            "type": "Accuracy Evaluation",
            "scorecard": scorecard_name,
            "task_type": "Accuracy Evaluation",
            **({"score": score_name} if score_name else {}),
        },
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

    # Create Evaluation record
    started_at = datetime.now(timezone.utc)
    experiment_params = {
        "type": "accuracy",
        "accountId": account_id,
        "status": "SETUP",
        "accuracy": 0.0,
        "createdAt": started_at.isoformat().replace('+00:00', 'Z'),
        "updatedAt": started_at.isoformat().replace('+00:00', 'Z'),
        "totalItems": number_of_samples,
        "processedItems": 0,
        "parameters": __import__('json').dumps({
            "sampling_method": sampling_method,
            "sample_size": number_of_samples,
        }),
        "startedAt": started_at.isoformat().replace('+00:00', 'Z'),
        "estimatedRemainingSeconds": number_of_samples,
        "taskId": task.id if task else None,
    }

    evaluation_record = DashboardEvaluation.create(client=client, **experiment_params)
    return tracker, evaluation_record


async def run_accuracy_evaluation(
    *,
    scorecard_name: str,
    score_name: Optional[str] = None,
    number_of_samples: int = 10,
    sampling_method: str = "random",
    client: Optional[PlexusDashboardClient] = None,
    account_id: Optional[str] = None,
    fresh: bool = True,
    use_yaml: bool = True
) -> dict:
    """Run a complete accuracy evaluation using the same logic as CLI.
    
    This is the shared function that both CLI and MCP should use to avoid code duplication.
    """
    from plexus.cli.evaluation.evaluations import load_scorecard_from_yaml_files, get_data_driven_samples
    from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier as _resolve_sc
    from plexus.dashboard.api.models.scorecard import Scorecard as DashboardScorecard
    from plexus.Evaluation import AccuracyEvaluation, Evaluation as DashboardEval
    from plexus.dashboard.api.models.account import Account
    import json
    
    # Use provided client or create new one
    if not client:
        from plexus.cli.shared.client_utils import create_client
        client = create_client()
    
    # Use provided account_id or resolve it
    if not account_id:
        from plexus.cli.report.utils import resolve_account_id_for_command
        account_id = resolve_account_id_for_command(client, None)
        if not account_id:
            raise ValueError("Could not resolve account ID")
    
    # Create tracker and evaluation record using shared helper
    tracker, evaluation_record = create_tracker_and_evaluation(
        client=client,
        account_id=account_id,
        scorecard_name=scorecard_name,
        number_of_samples=number_of_samples,
        sampling_method=sampling_method,
        score_name=score_name,
    )

    try:
        # Load scorecard from YAML files (same as CLI)
        target_score_identifiers = [score_name] if score_name else []
        scorecard_instance = load_scorecard_from_yaml_files(scorecard_name, target_score_identifiers)

        # Resolve scorecard ID and update evaluation record (same as CLI)
        scorecard_key = getattr(scorecard_instance, 'key', None) or getattr(scorecard_instance, 'properties', {}).get('key')
        scorecard_id = None
        score_id_for_eval = None
        
        if scorecard_key:
            scorecard_record = DashboardScorecard.list_by_key(key=scorecard_key, client=client)
            if scorecard_record:
                scorecard_id = scorecard_record.id
                
                # Update task with scorecard ID (same as CLI)
                if tracker and tracker.task:
                    tracker.task.update(scorecardId=scorecard_id)
                
                # Find primary score and resolve to DynamoDB UUID (same as CLI should do)
                primary_score_config = None
                if score_name and scorecard_instance.scores:
                    for sc_config in scorecard_instance.scores:
                        if (sc_config.get('name') == score_name or
                            sc_config.get('key') == score_name or
                            str(sc_config.get('id', '')) == score_name):
                            primary_score_config = sc_config
                            break
                
                # Use first score if no specific score found
                if not primary_score_config and scorecard_instance.scores:
                    primary_score_config = scorecard_instance.scores[0]
                
                # Resolve score to DynamoDB UUID using the dashboard Score model
                if primary_score_config:
                    from plexus.dashboard.api.models.score import Score as DashboardScore
                    try:
                        # Use the existing get_by_name method to resolve to DynamoDB ID
                        score_obj = DashboardScore.get_by_name(primary_score_config.get('name'), scorecard_id, client)
                        if score_obj and hasattr(score_obj, 'id'):
                            score_id_for_eval = score_obj.id
                        else:
                            score_id_for_eval = None
                    except Exception as e:
                        logging.warning(f"Could not resolve score '{primary_score_config.get('name')}' to DynamoDB ID: {e}")
                        score_id_for_eval = None
                
                # Update evaluation record with scorecard and score IDs (same as CLI)
                update_data = {'scorecardId': scorecard_id}
                if score_id_for_eval:
                    update_data['scoreId'] = score_id_for_eval
                
                evaluation_record.update(**update_data)
                
        # Get labeled samples (same as CLI)
        labeled_samples_data = get_data_driven_samples(
            scorecard_instance=scorecard_instance,
            scorecard_name=scorecard_name,
            score_name=primary_score_config.get('name') if primary_score_config else None,
            score_config=primary_score_config,
            fresh=fresh,
            content_ids_to_sample_set=set(),
            progress_callback=tracker.update if tracker else None,
            number_of_samples=number_of_samples,
            random_seed=None
        )

        # Determine subset of score names to evaluate (same as CLI)
        subset_of_score_names = None
        if score_name:
            subset_of_score_names = [sc.get('name') for sc in scorecard_instance.scores 
                                  if sc.get('name') and (sc.get('name') == score_name or 
                                                        sc.get('key') == score_name or 
                                                        str(sc.get('id', '')) == score_name)]
        else:
            subset_of_score_names = [sc.get('name') for sc in scorecard_instance.scores if sc.get('name')]

        # Create AccuracyEvaluation (same parameters as CLI)
        accuracy_eval = AccuracyEvaluation(
            scorecard_name=scorecard_name,
            scorecard=scorecard_instance,
            labeled_samples=labeled_samples_data,
            number_of_texts_to_sample=len(labeled_samples_data),
            sampling_method='provided',
            subset_of_score_names=subset_of_score_names,
            task_id=tracker.task.id if tracker and tracker.task else None,
            evaluation_id=evaluation_record.id,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id_for_eval,
            override_folder=f"./overrides/{scorecard_name}"
        )

        # Advance tracker to Processing stage (same as CLI)
        if tracker:
            tracker.advance_stage()

        # Run the evaluation (same as CLI)
        final_metrics = await accuracy_eval.run(tracker=tracker)

        # Complete the evaluation record and task (same as CLI)
        if evaluation_record and final_metrics:
            try:
                # Update evaluation record to COMPLETED status (same as CLI)
                update_payload_metrics = []
                if final_metrics.get("accuracy") is not None:
                    update_payload_metrics.append({"name": "Accuracy", "value": final_metrics["accuracy"] * 100})
                if final_metrics.get("alignment") is not None:
                    update_payload_metrics.append({"name": "Alignment", "value": final_metrics["alignment"] * 100})
                if final_metrics.get("precision") is not None:
                    update_payload_metrics.append({"name": "Precision", "value": final_metrics["precision"] * 100})
                if final_metrics.get("recall") is not None:
                    update_payload_metrics.append({"name": "Recall", "value": final_metrics["recall"] * 100})

                update_fields = {
                    'status': "COMPLETED",
                    'accuracy': final_metrics.get("accuracy", 0) * 100,
                    'metrics': json.dumps(update_payload_metrics),
                    'estimatedRemainingSeconds': 0,
                    'processedItems': len(labeled_samples_data),
                }
                
                evaluation_record.update(**update_fields)
                
                # Complete the current stage and task (exact same as CLI)
                if tracker:
                    # Complete the current stage using the exact same method as CLI
                    if tracker.current_stage:
                        tracker.current_stage.complete()
                        tracker._update_api_task_progress(force_critical=True)
                    
                    # Complete the overall task (final step like CLI)
                    if tracker.task:
                        tracker.task.update(
                            status='COMPLETED',
                            completedAt=datetime.now(timezone.utc).isoformat(),
                            updatedAt=datetime.now(timezone.utc).isoformat()
                        )
                        
            except Exception as e:
                logging.warning(f"Could not complete evaluation record/task: {e}")

        # Get the final evaluation info
        eval_info = DashboardEval.get_evaluation_info(evaluation_record.id, include_score_results=False)
        
        return {
            'evaluation_id': eval_info.get('id'),
            'scorecard_id': eval_info.get('scorecard_id'),
            'score_id': eval_info.get('score_id'),
            'accuracy': eval_info.get('accuracy'),
            'metrics': eval_info.get('metrics'),
            'confusionMatrix': eval_info.get('confusionMatrix'),
            'predictedClassDistribution': eval_info.get('predictedClassDistribution'),
            'datasetClassDistribution': eval_info.get('datasetClassDistribution'),
        }
        
    except Exception as e:
        # Clean up tracker if something went wrong
        if tracker:
            tracker.fail_current_stage(str(e))
        raise



