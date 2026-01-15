import os
import json
import rich
import click
import plexus
import pandas as pd
from openpyxl.styles import Font
import asyncio
import sys
import traceback
import socket
from datetime import datetime, timezone
from typing import Optional

from plexus.CustomLogging import logging
from plexus.Registries import scorecard_registry
from langgraph.errors import NodeInterrupt
from plexus.scores.LangGraphScore import BatchProcessingPause
from plexus.Scorecard import Scorecard
from plexus.scores.Score import Score
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.shared import get_scoring_jobs_for_batch
from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier, resolve_item_identifier
from plexus.cli.shared.memoized_resolvers import memoized_resolve_scorecard_identifier, memoized_resolve_item_identifier
from plexus.cli.shared.command_output import write_json_output, should_write_json_output
from plexus.cli.shared.stage_configurations import get_prediction_stage_configs
from plexus.cli.shared.task_progress_tracker import TaskProgressTracker
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.models.feedback_item import FeedbackItem


@click.command(help="Predict a scorecard or specific score(s) within a scorecard.")
@click.option('--scorecard', required=True, help='The scorecard to use (accepts ID, name, key, or external ID).')
@click.option('--score', '--scores', help='The score(s) to predict (accepts ID, name, key, or external ID), separated by commas.')
@click.option('--item', help='The item to use (accepts ID or any identifier value).')
@click.option('--items', help='Comma-separated list of item identifiers (accepts IDs or any identifier values).')
@click.option('--number', type=int, default=1, help='Number of times to iterate over the list of scores.')
@click.option('--excel', is_flag=True, help='Output results to an Excel file.')
@click.option('--use-langsmith-trace', is_flag=True, default=False, help='Activate LangSmith trace client for LangChain components')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
@click.option('--no-cache', is_flag=True, help='Disable local caching entirely (always fetch from API)')
@click.option('--yaml', is_flag=True, help='Use local YAML files only without API updates')
@click.option('--task-id', default=None, type=str, help='Task ID for progress tracking')
@click.option('--format', type=click.Choice(['fixed', 'json', 'yaml']), default='fixed', help='Output format: fixed (human-readable), json (parseable JSON), or yaml (token-efficient YAML)')
@click.option('--input', is_flag=True, help='Include input text and metadata in YAML output (only for --format=yaml)')
@click.option('--trace', is_flag=True, help='Include full execution trace in YAML output (only for --format=yaml)')
@click.option('--version', default=None, type=str, help='Specific score version ID to predict with (defaults to champion version)')
@click.option('--latest', is_flag=True, help='Use the most recent score version (overrides --version)')
@click.option('--compare-to-feedback', is_flag=True, help='Compare current prediction to historical feedback corrections for this item and score')
def predict(scorecard, score, item, items, number, excel, use_langsmith_trace, fresh, no_cache, yaml, task_id, format, input, trace, version, latest, compare_to_feedback):
    """Predict scores for a scorecard"""
    try:
        # Configure event loop with custom exception handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(
            lambda l, c: handle_exception(l, c, scorecard, score)
        )

        # Validate that only one of --item or --items is provided
        if item and items:
            raise click.BadParameter("Cannot specify both --item and --items. Use --items for multiple items.")
        
        # Validate version options (same as evaluation tool)
        if version and latest:
            raise click.BadParameter("Cannot use both --version and --latest options. Choose one.")
        
        # Create and run coroutine
        if score:
            score_names = [name.strip() for name in score.split(',')]
        else:
            score_names = []
        
        # Handle item identifiers
        if items:
            item_identifiers = [item_id.strip() for item_id in items.split(',')]
        elif item:
            item_identifiers = [item]
        else:
            item_identifiers = [None]  # Single None for random sampling
        
        coro = predict_impl(
            scorecard_identifier=scorecard, 
            score_names=score_names, 
            item_identifiers=item_identifiers, 
            number_of_times=number,
            excel=excel, 
            use_langsmith_trace=use_langsmith_trace, 
            fresh=fresh,
            no_cache=no_cache,
            yaml_only=yaml,
            task_id=task_id, 
            format=format,
            include_input=input,
            include_trace=trace,
            version=version,
            latest=latest,
            compare_to_feedback=compare_to_feedback
        )
        try:
            loop.run_until_complete(coro)
        except BatchProcessingPause as e:
            logging.info(f"Created batch job {e.batch_job_id} for thread {e.thread_id}")
            rich.print(f"[green]Created batch job {e.batch_job_id}[/green]")
            return  # Exit normally
        finally:
            # Clean up any remaining tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # Allow tasks to complete cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            
            loop.close()
    except KeyboardInterrupt:
        logging.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error during prediction: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)

async def predict_impl(
    scorecard_identifier: str,
    score_names: list,
    item_identifiers: list = None,
    number_of_times: int = 1,
    excel: bool = False,
    use_langsmith_trace: bool = False,
    fresh: bool = False,
    no_cache: bool = False,
    yaml_only: bool = False,
    task_id: str = None,
    format: str = 'fixed',
    include_input: bool = False,
    include_trace: bool = False,
    version: str = None,
    latest: bool = False,
    compare_to_feedback: bool = False
):
    """Implementation of predict command"""
    # Validate conflicting options
    if no_cache and yaml_only:
        raise click.BadParameter("Cannot use both --no-cache and --yaml options together")
    
    # Validate version options (same as evaluation tool)
    if version and latest:
        logging.error("Cannot use both --version and --latest options. Choose one.")
        raise click.BadParameter("Cannot use both --version and --latest options. Choose one.")
    
    # Determine effective version for logging
    effective_version = "latest" if latest else (version or "champion")
    logging.info(f"Prediction - Scorecard: {scorecard_identifier}, Scores: {score_names}, Version: {effective_version}")
    
    # Initialize resolved_version - will be updated later if --latest is used
    resolved_version = version if not latest else None
    
    # Handle --latest flag by resolving the latest version for the primary score (same as evaluation tool)
    if latest and score_names:
        primary_score_name = score_names[0]
        logging.info(f"--latest flag specified for primary score: {primary_score_name}")
        
        try:
            # Import required modules for version resolution
            from plexus.cli.evaluation.evaluations import load_scorecard_from_api, get_latest_score_version
            from plexus.dashboard.api.client import PlexusDashboardClient
            
            # Load scorecard temporarily to get score ID
            temp_scorecard = load_scorecard_from_api(scorecard_identifier, [primary_score_name], use_cache=yaml_only, specific_version=None)
            
            # Find the primary score's ID from the loaded scorecard
            primary_score_id = None
            if temp_scorecard and hasattr(temp_scorecard, 'score_configs'):
                for sc_config in temp_scorecard.score_configs:
                    if (sc_config.get('name') == primary_score_name or 
                        sc_config.get('key') == primary_score_name or
                        sc_config.get('externalId') == primary_score_name):
                        primary_score_id = sc_config.get('id')
                        break
            
            if primary_score_id:
                client = PlexusDashboardClient()
                latest_version_id = get_latest_score_version(client, primary_score_id)
                if latest_version_id:
                    resolved_version = latest_version_id
                    logging.info(f"Resolved --latest to version: {latest_version_id}")
                else:
                    logging.warning(f"Could not find latest version for score {primary_score_name}, using champion version")
            else:
                logging.warning(f"Could not resolve score ID for {primary_score_name}, using champion version")
        except Exception as e:
            logging.warning(f"Error resolving latest version for score {primary_score_name}: {e}, using champion version")
    
    tracker: Optional[TaskProgressTracker] = None
    task: Optional[Task] = None
    client: Optional[PlexusDashboardClient] = None
    
    try:
        # Initialize task progress tracking if task_id is provided
        if task_id:
            try:
                client = PlexusDashboardClient()
                
                # Get the account ID
                account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
                if not account_key:
                    raise Exception("PLEXUS_ACCOUNT_KEY environment variable must be set")
                logging.info(f"Looking up account with key: {account_key}...")
                account = Account.list_by_key(key=account_key, client=client)
                if not account:
                    raise Exception(f"Could not find account with key: {account_key}")
                logging.info(f"Found account: {account.name} ({account.id})")
                
                # Get existing task if task_id provided
                task = Task.get_by_id(task_id, client)
                if not task:
                    logging.error(f"Failed to get existing task {task_id}")
                    raise Exception(f"Could not find task with ID: {task_id}")
                logging.info(f"Using existing task: {task_id}")
                
                # Calculate total items for progress tracking
                # Total = (number of items) × (number of scores) × (number of iterations)
                item_count = len(item_identifiers) if item_identifiers else 1
                total_predictions = item_count * len(score_names) * number_of_times
                
                # Initialize TaskProgressTracker with prediction-specific stages
                stage_configs = get_prediction_stage_configs(total_items=total_predictions)
                
                tracker = TaskProgressTracker(
                    total_items=total_predictions,
                    stage_configs=stage_configs,
                    task_id=task.id,
                    target=f"prediction/{scorecard_identifier}",
                    command=f"predict --scorecard {scorecard_identifier}",
                    description=f"Prediction for {scorecard_identifier}",
                    dispatch_status="DISPATCHED",
                    prevent_new_task=True,
                    metadata={
                        "type": "Prediction",
                        "scorecard": scorecard_identifier,
                        "task_type": "Prediction"
                    },
                    account_id=account.id,
                    client=client
                )
                
                # Set worker ID immediately to show task as claimed
                worker_id = f"{socket.gethostname()}-{os.getpid()}"
                task.update(
                    accountId=task.accountId,
                    type=task.type,
                    status='RUNNING',
                    target=task.target,
                    command=task.command,
                    workerNodeId=worker_id,
                    startedAt=datetime.now(timezone.utc).isoformat(),
                    updatedAt=datetime.now(timezone.utc).isoformat()
                )
                logging.info(f"Successfully claimed task {task.id} with worker ID {worker_id}")
                
                # Start with Querying stage
                tracker.current_stage.status_message = "Starting prediction setup..."
                tracker.update(current_items=0)
                logging.info("==== STAGE: Querying ====")
                
                # Log all configured stages for debugging
                all_stages = tracker.get_all_stages()
                logging.info(f"TaskProgressTracker configured with stages: {list(all_stages.keys())}")
                logging.info(f"Current stage: {tracker.current_stage.name if tracker.current_stage else 'None'}")
                
            except Exception as e:
                logging.error(f"Failed to initialize task progress tracking: {str(e)}")
                logging.error(f"Full traceback: {traceback.format_exc()}")
                # Continue without tracking if setup fails
                tracker = None
                task = None
        
        # Querying stage: Looking up scorecard configuration
        if tracker:
            tracker.current_stage.status_message = "Preparing score configurations..."
            tracker.update(current_items=0)
        
        # We no longer load the entire scorecard upfront
        # Instead, we'll load individual scores as needed
        logging.info(f"Using individual score loading for scorecard '{scorecard_identifier}'")
        
        # Querying stage: Scorecard configuration loaded
        if tracker:
            tracker.current_stage.status_message = "Score configuration approach ready"
            tracker.update(current_items=0)
            
            # Complete the Querying stage
            tracker.current_stage.status_message = "Querying completed - scorecard configuration ready"
            tracker.update(current_items=0)
            logging.info("Querying stage completed")
            
            # Advance to Predicting stage
            tracker.advance_stage()
            tracker.current_stage.status_message = "Starting predictions..."
            tracker.update(current_items=0)
            logging.info(f"==== STAGE: {tracker.current_stage.name} ====")
        
        # Initialize feedback comparison variables
        scorecard_id = None
        score_ids = {}
        
        # If compare_to_feedback is enabled, we need to resolve scorecard and score IDs
        if compare_to_feedback:
            # Ensure we have a client for feedback comparison
            if client is None:
                from plexus.cli.shared.client_utils import create_client
                client = create_client()
            
            # Resolve scorecard ID
            scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
            if scorecard_id:
                logging.info(f"Resolved scorecard ID: {scorecard_id}")
            
            # Resolve score IDs for each score
            for score_name in score_names:
                score_id = resolve_score_identifier(client, scorecard_id, score_name)
                if score_id:
                    score_ids[score_name] = score_id
                    logging.info(f"Resolved score ID for {score_name}: {score_id}")
                else:
                    logging.warning(f"Could not resolve score ID for {score_name}")
            
            if not scorecard_id:
                logging.warning(f"Could not resolve scorecard ID for {scorecard_identifier}")
                logging.warning("Feedback comparison will be disabled for this run")
        
        # Track current prediction for progress
        current_prediction = 0
        results = []
        
        # Calculate total predictions and set up item identifiers
        item_count = len(item_identifiers) if item_identifiers else 1
        total_predictions = item_count * len(score_names) * number_of_times
        
        # Default to [None] if no item identifiers specified (for random sampling)
        if not item_identifiers:
            item_identifiers = [None]
        
        # If we have multiple items, process them in parallel
        if len(item_identifiers) > 1:
            # Create async tasks for each item-score combination
            async def process_single_prediction(iteration, item_idx, item_identifier, score_idx, score_name, prediction_num):
                """Process a single prediction asynchronously"""
                nonlocal current_prediction
                
                # Update progress for current prediction
                if tracker:
                    tracker.current_stage.status_message = f"Processing prediction {prediction_num}/{total_predictions} for item {item_identifier or 'random'}, score: {score_name}"
                    # Note: We don't update current_items here since it's handled by the parallel coordinator
                
                # Step 1: Look up item text and metadata
                if tracker:
                    tracker.current_stage.status_message = f"Looking up item text and metadata for prediction {prediction_num}/{total_predictions}"
                
                sample_row, used_item_id = select_sample(
                    scorecard_identifier, score_name, item_identifier, fresh, compare_to_feedback=compare_to_feedback, scorecard_id=scorecard_id, score_id=score_ids.get(score_name)
                )
                
                # Step 2: Item lookup completed
                if tracker:
                    tracker.current_stage.status_message = f"Item data loaded - running prediction {prediction_num}/{total_predictions} for score: {score_name}"
                
                row_result = {'item_id': used_item_id}
                if sample_row is not None:
                    row_result['text'] = sample_row.iloc[0].get('text', '')
                
                try:
                    # Update progress: Running prediction
                    if tracker:
                        tracker.current_stage.status_message = f"Running prediction for score: {score_name}"
                    
                    # Use centralized Scorecard path for dependency-aware predictions
                    transcript, predictions, costs = await predict_score_with_individual_loading(
                        scorecard_identifier, score_name, sample_row, used_item_id, no_cache=no_cache, yaml_only=yaml_only, specific_version=resolved_version
                    )
                    
                    if predictions:
                        if isinstance(predictions, list):
                            # Handle list of results
                            prediction = predictions[0] if predictions else None
                            if prediction:
                                row_result[f'{score_name}_value'] = prediction.value
                                row_result[f'{score_name}_explanation'] = prediction.explanation
                                row_result[f'{score_name}_cost'] = costs
                                # Extract trace information
                                if hasattr(prediction, 'trace'):
                                    row_result[f'{score_name}_trace'] = prediction.trace
                                elif hasattr(prediction, 'metadata') and prediction.metadata:
                                    row_result[f'{score_name}_trace'] = prediction.metadata.get('trace')
                                else:
                                    row_result[f'{score_name}_trace'] = None
                                logging.info(f"Got predictions: {predictions}")
                        else:
                            # Handle Score.Result object
                            if hasattr(predictions, 'value') and predictions.value is not None:
                                row_result[f'{score_name}_value'] = predictions.value
                                # ✅ ENHANCED: Get explanation from direct field first, then metadata
                                explanation = (
                                    getattr(predictions, 'explanation', None) or
                                    predictions.metadata.get('explanation', '') if hasattr(predictions, 'metadata') and predictions.metadata else
                                    ''
                                )
                                row_result[f'{score_name}_explanation'] = explanation
                                row_result[f'{score_name}_cost'] = costs
                                # Extract trace information
                                trace = None
                                logging.info(f"🔍 TRACE EXTRACTION DEBUG for {score_name}:")
                                logging.info(f"  - predictions type: {type(predictions)}")
                                logging.info(f"  - predictions attributes: {dir(predictions)}")
                                logging.info(f"  - has trace attr: {hasattr(predictions, 'trace')}")
                                logging.info(f"  - has metadata attr: {hasattr(predictions, 'metadata')}")
                                
                                if hasattr(predictions, 'trace'):
                                    trace = predictions.trace
                                    logging.info(f"  ✅ Found trace in direct attribute: {type(trace)}")
                                elif hasattr(predictions, 'metadata') and predictions.metadata:
                                    logging.info(f"  - metadata type: {type(predictions.metadata)}")
                                    logging.info(f"  - metadata keys: {list(predictions.metadata.keys()) if isinstance(predictions.metadata, dict) else 'not a dict'}")
                                    trace = predictions.metadata.get('trace')
                                    if trace:
                                        logging.info(f"  ✅ Found trace in metadata: {type(trace)}")
                                        logging.info(f"  - trace keys: {list(trace.keys()) if isinstance(trace, dict) else 'not a dict'}")
                                        if isinstance(trace, dict) and 'node_results' in trace:
                                            logging.info(f"  - node_results count: {len(trace['node_results'])}")
                                            
                                            # Add text and metadata to trace for debugging/analysis
                                            if isinstance(trace, dict):
                                                import json
                                                # Get text and metadata from sample_row
                                                input_text = sample_row.iloc[0].get('text', '') if sample_row is not None else ''
                                                input_metadata_str = sample_row.iloc[0].get('metadata', '{}') if sample_row is not None else '{}'
                                                try:
                                                    input_metadata = json.loads(input_metadata_str) if input_metadata_str else {}
                                                except json.JSONDecodeError:
                                                    input_metadata = {}
                                                
                                                trace['input_text'] = input_text
                                                trace['input_metadata'] = input_metadata
                                                logging.info(f"  ✅ Added input text ({len(input_text)} chars) and metadata ({len(input_metadata)} keys) to trace")
                                            
                                            # Test JSON serialization
                                            try:
                                                import json
                                                json_trace = json.dumps(trace, default=str)
                                                logging.info(f"  ✅ Trace is JSON serializable (length: {len(json_trace)})")
                                            except Exception as json_error:
                                                logging.error(f"  ❌ Trace is NOT JSON serializable: {json_error}")
                                                # Try to make a JSON-safe version
                                                try:
                                                    safe_trace = json.loads(json.dumps(trace, default=str))
                                                    trace = safe_trace
                                                    logging.info(f"  ✅ Created JSON-safe trace version")
                                                except Exception as safe_error:
                                                    logging.error(f"  ❌ Could not create JSON-safe trace: {safe_error}")
                                                    trace = {"error": "Trace data could not be serialized", "original_error": str(json_error)}
                                    else:
                                        logging.info(f"  ❌ No trace found in metadata")
                                        # Check for nested metadata structures
                                        if isinstance(predictions.metadata, dict):
                                            for key, value in predictions.metadata.items():
                                                if isinstance(value, dict) and 'trace' in value:
                                                    logging.info(f"  🔍 Found nested trace in metadata['{key}']['trace']")
                                                    trace = value['trace']
                                                    break
                                else:
                                    logging.info(f"  ❌ No metadata attribute found")
                                
                                if not trace:
                                    logging.warning(f"  ⚠️ No trace data found anywhere in predictions object")
                                
                                row_result[f'{score_name}_trace'] = trace
                                logging.info(f"Got predictions: {predictions}")
                    else:
                        row_result[f'{score_name}_value'] = None
                        row_result[f'{score_name}_explanation'] = None
                        row_result[f'{score_name}_cost'] = None
                        row_result[f'{score_name}_trace'] = None
                    
                    # Add feedback comparison if requested and available
                    if compare_to_feedback and sample_row is not None:
                        feedback_item = sample_row.iloc[0].get('feedback_item')
                        if feedback_item:
                            feedback_comparison = create_feedback_comparison(row_result, feedback_item, score_name)
                            row_result[f'{score_name}_feedback_comparison'] = feedback_comparison
                            logging.info(f"Added feedback comparison for {score_name}")
                        else:
                            logging.info(f"No feedback available for item {used_item_id}, score {score_name}")
                    
                except BatchProcessingPause:
                    raise
                except Exception as e:
                    logging.error(f"Error processing score {score_name}: {e}")
                    logging.error(f"Full traceback: {traceback.format_exc()}")
                    raise
                
                return row_result
            
            # Create all prediction tasks
            tasks = []
            for iteration in range(number_of_times):
                for item_idx, item_identifier in enumerate(item_identifiers):
                    for score_idx, score_name in enumerate(score_names):
                        prediction_num = iteration * len(item_identifiers) * len(score_names) + item_idx * len(score_names) + score_idx + 1
                        task = process_single_prediction(iteration, item_idx, item_identifier, score_idx, score_name, prediction_num)
                        tasks.append(task)
            
            # Run all predictions in parallel
            logging.info(f"Running {len(tasks)} predictions in parallel for {len(item_identifiers)} items")
            if tracker:
                tracker.current_stage.status_message = f"Running {len(tasks)} predictions in parallel..."
                tracker.update(current_items=0)
            
            # Execute all tasks concurrently
            prediction_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle any exceptions
            for i, result in enumerate(prediction_results):
                if isinstance(result, Exception):
                    logging.error(f"Prediction task {i+1} failed: {result}")
                    if isinstance(result, BatchProcessingPause):
                        raise result  # Re-raise BatchProcessingPause
                    # For other exceptions, we could either fail completely or continue with other results
                    # For now, let's continue but log the error
                    continue
                
                # Add successful results
                if any(result.get(f'{name}_value') is not None for name in score_names):
                    results.append(result)
                
                # Update progress
                current_prediction += 1
                if tracker:
                    tracker.current_stage.status_message = f"Completed prediction {current_prediction}/{total_predictions}"
                    tracker.update(current_items=current_prediction)
        
        else:
            # Single item or no specific item - use original sequential processing
            for iteration in range(number_of_times):
                for item_idx, item_identifier in enumerate(item_identifiers):
                    for score_idx, score_name in enumerate(score_names):
                        # Update progress for current prediction
                        if tracker:
                            prediction_num = iteration * len(item_identifiers) * len(score_names) + item_idx * len(score_names) + score_idx + 1
                            tracker.current_stage.status_message = f"Processing prediction {prediction_num}/{total_predictions} for item {item_identifier or 'random'}, score: {score_name}"
                            tracker.update(current_items=current_prediction)
                        
                        # Step 1: Look up item text and metadata
                        if tracker:
                            tracker.current_stage.status_message = f"Looking up item text and metadata for prediction {prediction_num}/{total_predictions}"
                            tracker.update(current_items=current_prediction)
                        
                        sample_row, used_item_id = select_sample(
                            scorecard_identifier, score_name, item_identifier, fresh, compare_to_feedback=compare_to_feedback, scorecard_id=scorecard_id, score_id=score_ids.get(score_name)
                        )
                        
                        # Step 2: Item lookup completed
                        if tracker:
                            tracker.current_stage.status_message = f"Item data loaded - running prediction {prediction_num}/{total_predictions} for score: {score_name}"
                            tracker.update(current_items=current_prediction)
                        
                        row_result = {'item_id': used_item_id}
                        if sample_row is not None:
                            row_result['text'] = sample_row.iloc[0].get('text', '')
                        
                        try:
                            # Update progress: Running prediction
                            if tracker:
                                tracker.current_stage.status_message = f"Running prediction for score: {score_name}"
                                tracker.update(current_items=current_prediction)
                            
                            transcript, predictions, costs = await predict_score_with_individual_loading(
                                scorecard_identifier, score_name, sample_row, used_item_id, no_cache=no_cache, yaml_only=yaml_only, specific_version=resolved_version
                            )
                            
                            if predictions:
                                if isinstance(predictions, list):
                                    # Handle list of results
                                    prediction = predictions[0] if predictions else None
                                    if prediction:
                                        row_result[f'{score_name}_value'] = prediction.value
                                        row_result[f'{score_name}_explanation'] = prediction.explanation
                                        row_result[f'{score_name}_cost'] = costs
                                        # Extract trace information
                                        if hasattr(prediction, 'trace'):
                                            row_result[f'{score_name}_trace'] = prediction.trace
                                        elif hasattr(prediction, 'metadata') and prediction.metadata:
                                            row_result[f'{score_name}_trace'] = prediction.metadata.get('trace')
                                        else:
                                            row_result[f'{score_name}_trace'] = None
                                        logging.info(f"Got predictions: {predictions}")
                                else:
                                    # Handle Score.Result object
                                    if hasattr(predictions, 'value') and predictions.value is not None:
                                        row_result[f'{score_name}_value'] = predictions.value
                                        # ✅ ENHANCED: Get explanation from direct field first, then metadata
                                        explanation = (
                                            getattr(predictions, 'explanation', None) or
                                            predictions.metadata.get('explanation', '') if hasattr(predictions, 'metadata') and predictions.metadata else
                                            ''
                                        )
                                        row_result[f'{score_name}_explanation'] = explanation
                                        row_result[f'{score_name}_cost'] = costs
                                        # Extract trace information
                                        trace = None
                                        logging.info(f"🔍 TRACE EXTRACTION DEBUG for {score_name}:")
                                        logging.info(f"  - predictions type: {type(predictions)}")
                                        logging.info(f"  - predictions attributes: {dir(predictions)}")
                                        logging.info(f"  - has trace attr: {hasattr(predictions, 'trace')}")
                                        logging.info(f"  - has metadata attr: {hasattr(predictions, 'metadata')}")
                                        
                                        if hasattr(predictions, 'trace'):
                                            trace = predictions.trace
                                            logging.info(f"  ✅ Found trace in direct attribute: {type(trace)}")
                                        elif hasattr(predictions, 'metadata') and predictions.metadata:
                                            logging.info(f"  - metadata type: {type(predictions.metadata)}")
                                            logging.info(f"  - metadata keys: {list(predictions.metadata.keys()) if isinstance(predictions.metadata, dict) else 'not a dict'}")
                                            trace = predictions.metadata.get('trace')
                                            if trace:
                                                logging.info(f"  ✅ Found trace in metadata: {type(trace)}")
                                                logging.info(f"  - trace keys: {list(trace.keys()) if isinstance(trace, dict) else 'not a dict'}")
                                                if isinstance(trace, dict) and 'node_results' in trace:
                                                    logging.info(f"  - node_results count: {len(trace['node_results'])}")
                                                    
                                                    # Add text and metadata to trace for debugging/analysis
                                                    if isinstance(trace, dict):
                                                        import json
                                                        # Get text and metadata from sample_row
                                                        input_text = sample_row.iloc[0].get('text', '') if sample_row is not None else ''
                                                        input_metadata_str = sample_row.iloc[0].get('metadata', '{}') if sample_row is not None else '{}'
                                                        try:
                                                            input_metadata = json.loads(input_metadata_str) if input_metadata_str else {}
                                                        except json.JSONDecodeError:
                                                            input_metadata = {}
                                                        
                                                        trace['input_text'] = input_text
                                                        trace['input_metadata'] = input_metadata
                                                        logging.info(f"  ✅ Added input text ({len(input_text)} chars) and metadata ({len(input_metadata)} keys) to trace")
                                                    
                                                    # Test JSON serialization
                                                    try:
                                                        import json
                                                        json_trace = json.dumps(trace, default=str)
                                                        logging.info(f"  ✅ Trace is JSON serializable (length: {len(json_trace)})")
                                                    except Exception as json_error:
                                                        logging.error(f"  ❌ Trace is NOT JSON serializable: {json_error}")
                                                        # Try to make a JSON-safe version
                                                        try:
                                                            safe_trace = json.loads(json.dumps(trace, default=str))
                                                            trace = safe_trace
                                                            logging.info(f"  ✅ Created JSON-safe trace version")
                                                        except Exception as safe_error:
                                                            logging.error(f"  ❌ Could not create JSON-safe trace: {safe_error}")
                                                            trace = {"error": "Trace data could not be serialized", "original_error": str(json_error)}
                                            else:
                                                logging.info(f"  ❌ No trace found in metadata")
                                                # Check for nested metadata structures
                                                if isinstance(predictions.metadata, dict):
                                                    for key, value in predictions.metadata.items():
                                                        if isinstance(value, dict) and 'trace' in value:
                                                            logging.info(f"  🔍 Found nested trace in metadata['{key}']['trace']")
                                                            trace = value['trace']
                                                            break
                                        else:
                                            logging.info(f"  ❌ No metadata attribute found")
                                        
                                        if not trace:
                                            logging.warning(f"  ⚠️ No trace data found anywhere in predictions object")
                                        
                                        row_result[f'{score_name}_trace'] = trace
                                        logging.info(f"Got predictions: {predictions}")
                            else:
                                row_result[f'{score_name}_value'] = None
                                row_result[f'{score_name}_explanation'] = None
                                row_result[f'{score_name}_cost'] = None
                                row_result[f'{score_name}_trace'] = None
                            
                        except BatchProcessingPause:
                            raise
                        except Exception as e:
                            logging.error(f"Error processing score {score_name}: {e}")
                            logging.error(f"Full traceback: {traceback.format_exc()}")
                            raise
                        
                        # Add feedback comparison if requested and available
                        if compare_to_feedback and sample_row is not None:
                            feedback_item = sample_row.iloc[0].get('feedback_item')
                            if feedback_item:
                                feedback_comparison = create_feedback_comparison(row_result, feedback_item, score_name)
                                row_result[f'{score_name}_feedback_comparison'] = feedback_comparison
                                logging.info(f"Added feedback comparison for {score_name}")
                            else:
                                logging.info(f"No feedback available for item {used_item_id}, score {score_name}")
                        
                        if any(row_result.get(f'{name}_value') is not None for name in score_names):
                            results.append(row_result)
                        
                        # Update progress: Prediction completed
                        current_prediction += 1
                        if tracker:
                            tracker.current_stage.status_message = f"Completed prediction {current_prediction}/{total_predictions}"
                            tracker.update(current_items=current_prediction)

        # Complete the Predicting stage
        if tracker:
            tracker.current_stage.status_message = "All predictions completed successfully"
            tracker.update(current_items=total_predictions)
            logging.info("Predicting stage completed")
            
            # Advance to Archiving stage
            tracker.advance_stage()
            tracker.current_stage.status_message = "Starting result archiving..."
            tracker.update(current_items=total_predictions)
            logging.info(f"==== STAGE: {tracker.current_stage.name} ====")
        
        if excel and results:
            if tracker:
                tracker.current_stage.status_message = "Generating Excel output file..."
                tracker.update(current_items=total_predictions)
            output_excel(results, score_names, scorecard_identifier)
            if tracker:
                tracker.current_stage.status_message = "Excel file generated successfully"
                tracker.update(current_items=total_predictions)
        elif results:
            if format == 'json':
                # JSON format: only output parseable JSON
                json_results = []
                for result in results:
                    json_result = {
                        'item_id': result.get('item_id'),
                        'scores': []
                    }
                    for name in score_names:
                        score_data = {
                            'name': name,
                            'value': result.get(f'{name}_value'),
                            'explanation': result.get(f'{name}_explanation'),
                            'cost': result.get(f'{name}_cost'),
                            'trace': result.get(f'{name}_trace')
                        }
                        # Add feedback comparison if available
                        feedback_comparison = result.get(f'{name}_feedback_comparison')
                        if feedback_comparison:
                            score_data['feedback_comparison'] = feedback_comparison
                        json_result['scores'].append(score_data)
                    
                    json_results.append(json_result)
                

                
                import json
                from decimal import Decimal
                
                # Custom JSON encoder to handle Decimal objects
                class DecimalEncoder(json.JSONEncoder):
                    def default(self, obj):
                        if isinstance(obj, Decimal):
                            return float(obj)
                        return super(DecimalEncoder, self).default(obj)
                
                # Output JSON to stdout (for backward compatibility)
                json_output = json.dumps(json_results, indent=2, cls=DecimalEncoder)
                print(json_output)
                
                # Also write to output file if we're in task dispatch mode
                if should_write_json_output():
                    if tracker:
                        tracker.current_stage.status_message = "Writing structured results to output file..."
                        tracker.update(current_items=total_predictions)
                    write_json_output(json_results, "output.json")
                    logging.info("Written structured prediction results to output.json")
                    if tracker:
                        tracker.current_stage.status_message = "Output file written successfully"
                        tracker.update(current_items=total_predictions)
                
                if tracker:
                    tracker.current_stage.status_message = "JSON results processed successfully"
                    tracker.update(current_items=total_predictions)
            elif format == 'yaml':
                # YAML format: token-efficient YAML output
                output_yaml_prediction_results(
                    results=results, 
                    score_names=score_names, 
                    scorecard_identifier=scorecard_identifier,
                    score_identifier=','.join(score_names) if score_names else None,
                    item_identifiers=item_identifiers,
                    include_input=include_input,
                    include_trace=include_trace
                )
                
                if tracker:
                    tracker.current_stage.status_message = "YAML results processed successfully"
                    tracker.update(current_items=total_predictions)
            else:
                # Fixed format: human-readable output
                rich.print("\n[bold green]Prediction Results:[/bold green]")
                for result in results:
                    rich.print(f"\n[bold]Item ID:[/bold] {result.get('item_id')}")
                    if result.get('text'):
                        text_preview = result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
                        rich.print(f"[bold]Text Preview:[/bold] {text_preview}")
                    
                    for name in score_names:
                        value = result.get(f'{name}_value')
                        explanation = result.get(f'{name}_explanation')
                        cost = result.get(f'{name}_cost')
                        trace = result.get(f'{name}_trace')
                        
                        rich.print(f"\n[bold cyan]{name} Score:[/bold cyan]")
                        rich.print(f"  [bold]Value:[/bold] {value}")
                        if explanation:
                            rich.print(f"  [bold]Explanation:[/bold] {explanation}")
                        if cost:
                            rich.print(f"  [bold]Cost:[/bold] {cost}")
                        if trace:
                            rich.print(f"  [bold]Trace:[/bold] {trace}")
                    
                    # Also log the truncated version for debugging
                    truncated_result = {
                        k: f"{str(v)[:80]}..." if isinstance(v, str) and len(str(v)) > 80 
                        else v
                        for k, v in result.items()
                    }
                    logging.info(f"Prediction result: {truncated_result}")
        else:
            if format != 'json':
                rich.print("[yellow]No prediction results to display.[/yellow]")
            else:
                print("[]")  # Empty JSON array for no results
                
        # Complete the Archiving stage
        if tracker:
            tracker.current_stage.status_message = "Archiving completed successfully"
            tracker.update(current_items=total_predictions)
            logging.info("Archiving stage completed")
            
            # Mark task as completed
            if task:
                task.update(
                    accountId=task.accountId,
                    type=task.type,
                    status='COMPLETED',
                    target=task.target,
                    command=task.command,
                    completedAt=datetime.now(timezone.utc).isoformat(),
                    updatedAt=datetime.now(timezone.utc).isoformat()
                )
                logging.info(f"Successfully marked task {task.id} as completed")
            
            # Complete all tracking
            tracker.complete()
            logging.info("All stages completed - prediction task finished successfully")
    except BatchProcessingPause:
        # Let it propagate up to be handled by the event loop handler
        raise
    except Exception as e:
        error_msg = f"Prediction failed: {str(e)}"
        logging.error(error_msg)
        logging.error(f"Full traceback: {traceback.format_exc()}")
        
        # Update task and tracker with error information
        if tracker:
            tracker.current_stage.status_message = error_msg
            tracker.update(current_items=tracker.current_items)
            tracker.fail(str(e))
        
        if task:
            try:
                task.update(
                    accountId=task.accountId,
                    type=task.type,
                    status='FAILED',
                    target=task.target,
                    command=task.command,
                    errorMessage=error_msg,
                    errorDetails=traceback.format_exc(),
                    completedAt=datetime.now(timezone.utc).isoformat(),
                    updatedAt=datetime.now(timezone.utc).isoformat()
                )
                logging.info(f"Updated task {task.id} with error information")
            except Exception as task_update_error:
                logging.error(f"Failed to update task with error information: {str(task_update_error)}")
        
        raise
    finally:
        # Final cleanup of any remaining tasks
        for task in asyncio.all_tasks():
            if not task.done() and task != asyncio.current_task():
                task.cancel()

def output_excel(results, score_names, scorecard_identifier):
    df = pd.DataFrame(results)
    
    logging.info(f"Available DataFrame columns: {df.columns.tolist()}")
    
    columns = ['item_id', 'text']
    for name in score_names:
        columns.extend([
            f'{name}_value',
            f'{name}_explanation',
            f'{name}_cost',
            f'{name}_trace'
        ])
    if len(score_names) > 1:
        columns.append('match?')
    
    logging.info(f"Requested columns: {columns}")
    existing_columns = [col for col in columns if col in df.columns]
    logging.info(f"Found columns: {existing_columns}")
    
    df = df[existing_columns]
    
    filename = f"{scorecard_identifier}_predictions.xlsx"
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Predictions')
        workbook = writer.book
        worksheet = writer.sheets['Predictions']
        
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column_letter].width = adjusted_width

        for cell in worksheet[1]:
            cell.font = Font(bold=True)

    logging.info(f"Excel file '{filename}' has been created with the prediction results.")


def select_sample(scorecard_identifier, score_name, item_identifier, fresh, compare_to_feedback=False, scorecard_id=None, score_id=None):
    """Select an item from the Plexus API using flexible identifier resolution."""
    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.item import Item
    from plexus.dashboard.api.models.feedback_item import FeedbackItem
    from plexus.cli.report.utils import resolve_account_id_for_command
    
    # Create API client
    client = create_client()
    account_id = resolve_account_id_for_command(client, None)
    
    if item_identifier:
        # Use the flexible item identifier resolution
        item_id = memoized_resolve_item_identifier(client, item_identifier, account_id)
        if not item_id:
            raise ValueError(f"No item found matching identifier: {item_identifier}")
        
        # Get the item using the standard model method
        try:
            item = Item.get_by_id(item_id, client)
            feedback_item = None
            
            # If feedback comparison is requested, fetch feedback separately
            if compare_to_feedback and scorecard_id and score_id:
                try:
                    # Use the Item's feedbackItems relationship instead of complex filtering
                    # This is more reliable and matches the working GraphQL query
                    query = """
                    query GetItemWithFeedback($id: ID!) {
                        getItem(id: $id) {
                            feedbackItems {
                                items {
                                    id
                                    scorecardId
                                    scoreId
                                    initialAnswerValue
                                    finalAnswerValue
                                    initialCommentValue
                                    finalCommentValue
                                    editCommentValue
                                    editedAt
                                    editorName
                                    isAgreement
                                    createdAt
                                    updatedAt
                                }
                            }
                        }
                    }
                    """
                    
                    variables = {"id": item_id}
                    response = client.execute(query=query, variables=variables)
                    
                    if response and 'getItem' in response and response['getItem']:
                        feedback_data = response['getItem'].get('feedbackItems', {})
                        feedback_items = feedback_data.get('items', [])
                        
                        # Filter for the specific scorecard and score
                        matching_feedback = None
                        for feedback_data in feedback_items:
                            if (feedback_data.get('scorecardId') == scorecard_id and 
                                feedback_data.get('scoreId') == score_id):
                                # Create a FeedbackItem object from the data
                                feedback_item = FeedbackItem.from_dict(feedback_data, client=client)
                                matching_feedback = feedback_item
                                break
                        
                        if matching_feedback:
                            feedback_item = matching_feedback
                            logging.info(f"Found feedback for item {item_id}, score {score_name}: initial_value={feedback_item.initialAnswerValue}, final_value={feedback_item.finalAnswerValue}")
                        else:
                            logging.info(f"No feedback available for item {item_id}, score {score_name} (scorecard: {scorecard_id}, score_id: {score_id})")
                    else:
                        logging.info(f"No feedback available for item {item_id}, score {score_name}")
                        
                except Exception as e:
                    logging.warning(f"Failed to fetch feedback for item {item_id}: {e}")
                    feedback_item = None
            
            logging.info(f"Found item {item_id} from identifier '{item_identifier}'")

            # Use Item.to_score_input() to transform the item
            # TODO: Pass item_config from scorecard YAML once available
            score_input = item.to_score_input(item_config=None)
            text_content = score_input.text
            logging.info(f"Item text length: {len(text_content)}")
            logging.info(f"Item text preview: {text_content[:200] if text_content else 'EMPTY TEXT'}")
            
            # Prepare metadata by combining Item metadata with required CLI metadata
            base_metadata = {
                "item_id": item.id,
                "account_key": os.getenv('PLEXUS_ACCOUNT_KEY', ''),
                "scorecard_identifier": scorecard_identifier,  # Use identifier instead of scorecard_key
                "score_name": score_name
            }
            
            # Merge with Item's metadata if it exists
            if item.metadata:
                logging.info(f"Item has metadata: {type(item.metadata)}")
                
                # Parse metadata if it's a JSON string
                parsed_metadata = None
                if isinstance(item.metadata, str):
                    try:
                        parsed_metadata = json.loads(item.metadata)
                        logging.info(f"Successfully parsed JSON metadata with keys: {list(parsed_metadata.keys())}")
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse metadata JSON: {e}")
                        parsed_metadata = None
                elif isinstance(item.metadata, dict):
                    parsed_metadata = item.metadata
                    logging.info(f"Metadata is already a dict with keys: {list(parsed_metadata.keys())}")
                else:
                    logging.warning(f"Metadata is unexpected type: {type(item.metadata)}")
                
                if parsed_metadata and isinstance(parsed_metadata, dict):
                    # Merge Item metadata with base metadata (base metadata takes precedence)
                    merged_metadata = {**parsed_metadata, **base_metadata}
                    logging.info(f"Merged metadata keys: {list(merged_metadata.keys())}")
                    logging.info(f"Original Item metadata: {json.dumps(parsed_metadata, indent=2)}")
                else:
                    merged_metadata = base_metadata
                    logging.warning(f"Could not parse Item metadata, using base metadata only")
            else:
                merged_metadata = base_metadata
                logging.info("Item has no metadata, using base metadata only")
            
            logging.info(f"Final metadata for scoring: {json.dumps(merged_metadata, indent=2)}")
            
            sample_data = {
                'text': text_content,
                'item_id': item.id,
                'metadata': json.dumps(merged_metadata),
                'feedback_item': feedback_item  # Add feedback data to the sample
            }
            
            # Convert to DataFrame-like structure for compatibility
            import pandas as pd
            sample_row = pd.DataFrame([sample_data])
            
            return sample_row, item.id
            
        except Exception as e:
            logging.error(f"Error retrieving item {item_id}: {e}")
            raise ValueError(f"Could not retrieve item {item_id}: {e}")
    else:
        # Get the most recent item for the account (no feedback comparison for random items)
        items = Item.list(
            client=client,
            filter={'accountId': {'eq': account_id}},
            sort={'createdAt': 'DESC'},
            limit=1
        )
        
        if not items:
            raise ValueError("No items found in the account")
        
        item = items[0]
        
        logging.info(f"Selected most recent item {item.id} from API")

        # Use Item.to_score_input() to transform the item
        # TODO: Pass item_config from scorecard YAML once available
        score_input = item.to_score_input(item_config=None)

        # Create a pandas-like row structure for compatibility
        sample_data = {
            'text': score_input.text,
            'item_id': item.id,
            'metadata': json.dumps({
                "item_id": item.id,
                "account_key": os.getenv('PLEXUS_ACCOUNT_KEY', ''),
                "scorecard_identifier": scorecard_identifier,  # Use identifier instead of scorecard_key
                "score_name": score_name
            }),
            'feedback_item': None  # No feedback for random items
        }
        
        # Convert to DataFrame-like structure for compatibility
        import pandas as pd
        sample_row = pd.DataFrame([sample_data])
        
        return sample_row, item.id


async def predict_score_with_individual_loading(scorecard_identifier, score_name, sample_row, used_item_id, no_cache=False, yaml_only=False, specific_version=None):
    """
    Predict a single score using Scorecard.score_entire_text with dependency backfilling.
    """
    try:
        from plexus.cli.shared.client_utils import create_client
        from plexus.cli.shared.direct_memoized_resolvers import direct_memoized_resolve_scorecard_identifier
        from plexus.cli.shared.fetch_scorecard_structure import fetch_scorecard_structure
        from plexus.cli.shared.identify_target_scores import identify_target_scores
        from plexus.cli.shared.iterative_config_fetching import iteratively_fetch_configurations
        
        # Resolve scorecard and fetch minimal structure
        client = create_client()
        scorecard_id = direct_memoized_resolve_scorecard_identifier(client, scorecard_identifier)
        if not scorecard_id:
            raise Exception(f"Could not resolve scorecard identifier: {scorecard_identifier}")
        scorecard_structure = fetch_scorecard_structure(client, scorecard_id)
        if not scorecard_structure:
            raise Exception(f"Could not fetch scorecard structure for: {scorecard_identifier}")

        # Identify the target score object
        targets = identify_target_scores(scorecard_structure, [score_name])
        if not targets:
            raise Exception(f"Score '{score_name}' not found in scorecard '{scorecard_identifier}'")

        # Fetch target + dependency configurations
        configs = iteratively_fetch_configurations(client, scorecard_structure, targets, use_cache=not no_cache, specific_version=specific_version)
        if not configs:
            raise Exception("Failed to fetch configurations for prediction")

        # Build a Scorecard instance with only needed scores
        scorecard_instance = Scorecard.create_instance_from_api_data(
            scorecard_id=scorecard_id,
            api_data=scorecard_structure,
            scores_config=list(configs.values())
        )
        # Honor yaml_only by preventing Score.load API calls during backfill
        try:
            setattr(scorecard_instance, 'yaml_only', bool(yaml_only))
        except Exception:
            pass

        # Prepare inputs - create Score.Input from sample row
        from plexus.scores.Score import Score

        if sample_row.empty:
            raise Exception("Empty sample row provided")

        row_dict = sample_row.iloc[0].to_dict()
        item_text = row_dict.get('text', '')
        if not item_text:
            raise Exception("No text content found in sample row")

        # Extract and parse metadata from row_dict
        metadata = {}
        if 'metadata' in row_dict:
            try:
                # The metadata in row_dict is usually a JSON string
                if isinstance(row_dict['metadata'], str):
                    import json
                    metadata = json.loads(row_dict['metadata'])
                elif isinstance(row_dict['metadata'], dict):
                    metadata = row_dict['metadata']
            except Exception as e:
                logging.warning(f"Failed to parse metadata from row_dict: {e}")
                # Fallback to including the raw value if parsing fails
                metadata = {'raw_metadata': row_dict['metadata']}

        # Add other useful context from row_dict to metadata, excluding the redundant 'metadata' field
        for key, value in row_dict.items():
            if key not in ['text', 'metadata'] and key not in metadata:
                metadata[key] = value

        # Create Score.Input object
        score_input = Score.Input(
            text=item_text,
            metadata=metadata
        )

        # Run centralized prediction with backfilling using new signature
        results = await scorecard_instance.score_entire_text(
            score_input=score_input,
            modality=None,
            subset_of_score_names=[score_name]
        )

        # Extract target result by name or ID
        prediction_result = None
        if results:
            if score_name in results:
                prediction_result = results[score_name]
            else:
                # try to find by matching parameters.name
                for _, res in results.items():
                    if hasattr(res, 'parameters') and getattr(res.parameters, 'name', None) == score_name:
                        prediction_result = res
                        break

        # Extract costs from scorecard instance accumulators
        costs = getattr(scorecard_instance, 'get_accumulated_costs', lambda: {'total_cost': 0})()

        return scorecard_instance, prediction_result, costs
    except Exception as e:
        logging.error(f"Error in predict_score_via_scorecard: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise

async def predict_score_impl(
    scorecard_class,
    score_name,
    item_id,
    input_data,
    use_langsmith_trace=False,
    fresh=False
):
    try:
        score_instance = Score.from_name(scorecard_class.properties['key'], score_name)
        async with score_instance:
            await score_instance.async_setup()
            prediction_result = await score_instance.predict(input_data)
            
            # Get costs if available
            costs = None
            if hasattr(score_instance, 'get_accumulated_costs'):
                try:
                    costs = score_instance.get_accumulated_costs()
                except Exception as e:
                    logging.warning(f"Failed to get costs: {e}")
                    costs = None
                    
            return score_instance, prediction_result, costs
            
    except BatchProcessingPause:
        # Just let it propagate up - state is already stored in batch job
        raise
    except Exception as e:
        logging.error(f"Error in predict_score_impl: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        await score_instance.cleanup()
        raise

def handle_exception(loop, context, scorecard_identifier=None, score_identifier=None):
    """Custom exception handler for the event loop"""
    exception = context.get('exception')
    message = context.get('message', '')
    
    if isinstance(exception, BatchProcessingPause):
        logging.info("=== BatchProcessingPause caught in event loop exception handler ===")
        
        # Show a nicely formatted message about the batch job
        print("\n" + "="*80)
        print("Workflow Paused for Batch Processing")
        print("=" * 80)
        print(f"\nBatch Job Created")
        print(f"Thread ID: {exception.thread_id}")
        print(f"Message: {exception.message}")
        print("\nTo resume this workflow:")
        print("1. Keep PLEXUS_ENABLE_BATCH_MODE=true for checkpointing")
        print("2. Either:")
        print("   a. Set PLEXUS_ENABLE_LLM_BREAKPOINTS=false to run without stopping")
        print("   b. Keep PLEXUS_ENABLE_LLM_BREAKPOINTS=true to continue stopping at breakpoints")
        print(f"3. Run the same command with --item {exception.thread_id}")
        print("\nExample:")
        print(f"  plexus predict --scorecard {scorecard_identifier}", end="")
        if score_identifier:
            print(f" --score {score_identifier}", end="")
        print(f" --item {exception.thread_id}")
        print("=" * 80 + "\n")
        
        # Stop the event loop gracefully
        loop.stop()
    else:
        logging.error(f"Unhandled exception in event loop: {message}")
        logging.error(f"Exception: {exception}")
        loop.default_exception_handler(context)
        loop.stop()

def get_score_instance(scorecard_identifier: str, score_name: str, no_cache=False, yaml_only=False):
    """
    Get a Score instance by loading individual score configuration.
    
    Args:
        scorecard_identifier: A string that identifies the scorecard (ID, name, key, or external ID)
        score_name: Name of the specific score to load
        no_cache: If True, don't cache API data to local YAML files (always fetch from API).
        yaml_only: If True, load only from local YAML files without API calls.
        
    Returns:
        Score: An initialized Score instance
    """
    # Convert no_cache to use_cache for the Score.load method
    use_cache = not no_cache
    return Score.load(scorecard_identifier, score_name, use_cache=use_cache, yaml_only=yaml_only)


def create_feedback_comparison(
    current_prediction: dict,
    feedback_item: FeedbackItem,
    score_name: str
) -> dict:
    """
    Create a comparison between current prediction and historical feedback.
    
    Args:
        current_prediction: Current prediction result dict
        feedback_item: FeedbackItem object from GraphQL
        score_name: Name of the score being compared
        
    Returns:
        Dictionary with comparison data
    """
    current_value = current_prediction.get(f'{score_name}_value')
    final_value = feedback_item.finalAnswerValue
    
    # Compute isAgreement: true if current prediction matches the final corrected value
    is_agreement = str(current_value).lower() == str(final_value).lower() if current_value and final_value else False
    
    return {
        "current_prediction": {
            "value": current_value,
            "explanation": current_prediction.get(f'{score_name}_explanation'),
        },
        "ground_truth": final_value,
        "isAgreement": is_agreement
    }


def output_yaml_prediction_results(
    results: list,
    score_names: list,
    scorecard_identifier: str,
    score_identifier: str = None,
    item_identifiers: list = None,
    include_input: bool = False,
    include_trace: bool = False
):
    """Output prediction results in token-efficient YAML format."""
    import yaml
    from decimal import Decimal
    import json
    
    # Build the command that was used
    command_parts = ['plexus predict', f'--scorecard "{scorecard_identifier}"']
    if score_identifier:
        command_parts.append(f'--score "{score_identifier}"')
    if item_identifiers:
        if len(item_identifiers) == 1 and item_identifiers[0] is not None:
            command_parts.append(f'--item "{item_identifiers[0]}"')
        elif len(item_identifiers) > 1:
            command_parts.append(f'--items "{",".join(str(i) for i in item_identifiers if i is not None)}"')
    command_parts.append('--format yaml')
    if include_input:
        command_parts.append('--input')
    if include_trace:
        command_parts.append('--trace')
    
    command_string = ' '.join(command_parts)
    
    # Custom YAML representer for Decimal objects
    def decimal_representer(dumper, data):
        return dumper.represent_float(float(data))
    
    yaml.add_representer(Decimal, decimal_representer)
    
    # Build the output structure
    output_data = {}
    
    # Add context with just command information
    output_data['context'] = {
        'command': command_string
    }
    
    # Process each result
    predictions = []
    for result in results:
        prediction_data = {
            'item_id': result.get('item_id')
        }
        
        # Include input data if requested
        if include_input:
            input_data = {}
            if result.get('text'):
                input_data['text'] = result['text']
            if result.get('metadata'):
                try:
                    # Parse metadata if it's a string
                    if isinstance(result['metadata'], str):
                        input_data['metadata'] = json.loads(result['metadata'])
                    else:
                        input_data['metadata'] = result['metadata']
                except (json.JSONDecodeError, TypeError):
                    input_data['metadata'] = result['metadata']
            
            if input_data:
                prediction_data['input'] = input_data
        
        # Add score results
        scores = []
        for score_name in score_names:
            score_data = {
                'name': score_name
            }
            
            # Always include value and explanation (core data)
            value = result.get(f'{score_name}_value')
            explanation = result.get(f'{score_name}_explanation')
            
            if value is not None:
                score_data['value'] = value
            if explanation:
                score_data['explanation'] = explanation
            
            # Include cost if available
            cost_data = result.get(f'{score_name}_cost')
            if cost_data is not None:
                score_data['cost'] = cost_data

            # Include trace if requested and available
            if include_trace:
                trace_data = result.get(f'{score_name}_trace')
                if trace_data is not None:
                    score_data['trace'] = trace_data
            
            # Include feedback comparison if available
            feedback_comparison = result.get(f'{score_name}_feedback_comparison')
            if feedback_comparison:
                score_data['feedback_comparison'] = feedback_comparison
            
            # Only add if we have data beyond just the name
            if len(score_data) > 1:  # More than just 'name'
                scores.append(score_data)
        
        if scores:
            prediction_data['scores'] = scores
        
        predictions.append(prediction_data)
    
    output_data['predictions'] = predictions
    
    # Output the YAML with a clean format
    yaml_output = yaml.dump(
        output_data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        indent=2
    )
    
    # Print with a simple comment header
    print("# Plexus prediction results")
    print(yaml_output)