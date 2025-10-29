from __future__ import annotations

import os
import math
import yaml
import json
import copy
import base64
import pandas as pd
import requests
import random
import time
import traceback
from datetime import datetime, timezone
import string
import pprint
import asyncio
from decimal import Decimal
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, wait_fixed, stop_after_attempt, before_log, retry_if_exception_type, AsyncRetrying, wait_exponential
from requests.exceptions import Timeout, RequestException
from concurrent.futures import ThreadPoolExecutor
from asyncio import Queue
import importlib
import logging
import re
import uuid
import traceback

import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from collections import Counter

from graphviz import Digraph
from jinja2 import Template

from plexus.scores.CompositeScore import CompositeScore
from plexus.scores.Score import Score
from .Scorecard import Scorecard
from .ScorecardResults import ScorecardResults
from .ScorecardResultsAnalysis import ScorecardResultsAnalysis
from plexus.cli.shared.CommandProgress import CommandProgress

from sklearn.metrics import confusion_matrix

from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation
from plexus.dashboard.api.models.scorecard import Scorecard as DashboardScorecard
from plexus.dashboard.api.models.score import Score as DashboardScore
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.dashboard.api.models.task import Task

from plexus.scores.LangGraphScore import LangGraphScore, BatchProcessingPause
import inspect
from plexus.utils.dict_utils import truncate_dict_strings_inner
from plexus.CustomLogging import logging, setup_logging, set_log_group

from plexus.cli.shared.task_progress_tracker import StageConfig, TaskProgressTracker
from typing import Optional

from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric
from plexus.analysis.metrics.accuracy import Accuracy
from plexus.analysis.metrics.precision import Precision
from plexus.analysis.metrics.recall import Recall

# Set up logging for evaluations
set_log_group('plexus/evaluation')
setup_logging()

class Evaluation:
    """
    Base class for evaluating Scorecard performance through accuracy testing and consistency checking.

    Evaluation is used to measure how well a Scorecard performs against labeled data or to check
    consistency of results. It integrates with the Plexus dashboard for monitoring. The class supports:

    - Accuracy testing against labeled data
    - Consistency checking through repeated scoring
    - Automatic metrics calculation and visualization
    - Cost tracking and reporting
    - Real-time progress tracking in the dashboard

    There are two main subclasses:
    1. AccuracyEvaluation: Tests scorecard results against labeled data
    2. ConsistencyEvaluation: Checks if scores are consistent when run multiple times

    Common usage patterns:
    1. Running an accuracy evaluation:
        evaluation = AccuracyEvaluation(
            scorecard_name="qa",
            scorecard=scorecard,
            labeled_samples_filename="labeled_data.csv"
        )
        await evaluation.run()

    2. Running a consistency check:
        evaluation = ConsistencyEvaluation(
            scorecard_name="qa",
            scorecard=scorecard,
            number_of_texts_to_sample=100,
            number_of_times_to_sample_each_text=3
        )
        await evaluation.run()

    3. Using with context management:
        with evaluation:
            await evaluation.run()

    4. Monitoring in dashboard:
        evaluation = AccuracyEvaluation(
            scorecard_name="qa",
            scorecard=scorecard,
            account_key="my-account",
            score_id="score-123"
        )
        await evaluation.run()  # Progress visible in dashboard

    The Evaluation class is commonly used during model development to measure performance
    and during production to monitor for accuracy drift.
    """

    def __init__(self, *,
        scorecard_name: str,
        scorecard: Scorecard,
        labeled_samples_filename: str = None,
        labeled_samples: list = None,
        number_of_texts_to_sample = 100,
        sampling_method = 'random',
        random_seed = None,
        session_ids_to_sample = None,
        subset_of_score_names = None,
        experiment_label = None,
        max_mismatches_to_report=5,
        account_key: str = 'call-criteria',
        score_id: str = None,
        visualize: bool = False,
        task_id: str = None,
        allow_no_labels: bool = False,
    ):
        # Immediately store task_id so that it is available for evaluation record creation
        self.allow_no_labels = allow_no_labels
        self.task_id = task_id
        
        # Set up logging for evaluations
        self.logging = logging.getLogger('plexus/evaluation')
        # Initialize evaluation

        # Initialize basic parameters
        self.scorecard_name = scorecard_name
        self.scorecard = scorecard
        self.labeled_samples_filename = labeled_samples_filename
        self.labeled_samples = labeled_samples
        self.requested_sample_size = number_of_texts_to_sample
        self.number_of_texts_to_sample = number_of_texts_to_sample
        self.sampling_method = sampling_method
        self.random_seed = random_seed
        self.score_id = score_id
        self.account_key = account_key  # Store the account key
        self.visualize = visualize
        self.task_id = task_id  # Ensure task_id is stored
        
        # Parse lists, if available.
        self.session_ids_to_sample = session_ids_to_sample
        self.subset_of_score_names = subset_of_score_names

        self.experiment_label = experiment_label
        self.max_mismatches_to_report = max_mismatches_to_report

        # Initialize dashboard client
        try:
            self.dashboard_client = PlexusDashboardClient.for_account(account_key)
            
            account = Account.list_by_key(key=account_key, client=self.dashboard_client)
            if not account:
                raise ValueError(f"No account found with key: {account_key}")
            self.logging.info(f"Initialized evaluation for account: {account.name}")
            
            self.account_id = account.id
            
            # Initialize scorecard_id as None - will be set immediately below
            self.scorecard_id = None
            
            # Prefer deterministic ID resolution shared with CLI helpers
            # Determine a display identifier to resolve the scorecard ID
            scorecard_display_name = None
            if hasattr(self.scorecard, 'name') and callable(self.scorecard.name):
                scorecard_display_name = self.scorecard.name()
            elif hasattr(self.scorecard, 'properties') and isinstance(self.scorecard.properties, dict):
                scorecard_display_name = self.scorecard.properties.get('name') or self.scorecard.properties.get('key')
            else:
                scorecard_display_name = str(self.scorecard_name)

            try:
                # Use the same identifier resolution helpers as the CLI to get DynamoDB IDs
                from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
                resolved_scorecard_id = resolve_scorecard_identifier(self.dashboard_client, scorecard_display_name or self.scorecard_name)
                if not resolved_scorecard_id:
                    # As a backup, try the raw scorecard_name
                    resolved_scorecard_id = resolve_scorecard_identifier(self.dashboard_client, self.scorecard_name)
                if not resolved_scorecard_id:
                    self.logging.error("Failed to resolve scorecard ID via identifier resolution")
                    raise ValueError(f"Could not resolve scorecard ID for: {scorecard_display_name or self.scorecard_name}")
                self.scorecard_id = resolved_scorecard_id

                # Resolve score ID if a single target score is specified
                single_score_name = None
                if self.subset_of_score_names and isinstance(self.subset_of_score_names, (list, tuple)) and len(self.subset_of_score_names) == 1:
                    single_score_name = self.subset_of_score_names[0]
                
                if single_score_name:
                    try:
                        resolved_score_id = resolve_score_identifier(self.dashboard_client, self.scorecard_id, single_score_name)
                        if resolved_score_id:
                            self.score_id = resolved_score_id
                            self.logging.info(f"Resolved score identifier to UUID: {self.score_id}")
                        else:
                            self.logging.warning(f"Could not resolve score identifier for score: {single_score_name}")
                    except Exception as score_lookup_error:
                        self.logging.warning(f"Failed to lookup score: {score_lookup_error}")

                # Update the evaluation record immediately with both IDs now that they're both set
                if hasattr(self, 'evaluation_id') and self.evaluation_id:
                    update_data = {'scorecardId': self.scorecard_id}
                    if getattr(self, 'score_id', None) and isinstance(self.score_id, str) and '-' in self.score_id and len(self.score_id.split('-')) == 5:
                        update_data['scoreId'] = self.score_id
                    try:
                        mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                            updateEvaluation(input: $input) {
                                id
                                scorecardId
                                scoreId
                            }
                        }"""
                        self.dashboard_client.execute(mutation, {
                            'input': {
                                'id': self.evaluation_id,
                                **update_data
                            }
                        })
                    except Exception as e:
                        self.logging.error(f"Failed to update evaluation record: {str(e)}")
                        # Continue initialization even if update fails
            except Exception as e:
                self.logging.error(f"Error resolving IDs: {str(e)}")
                raise

        except Exception as e:
            self.logging.error(f"Failed to initialize dashboard client: {str(e)}", exc_info=True)
            self.dashboard_client = None
            self.experiment_id = None
            self.scorecard_id = None

        # Results tracking - separate results by score
        self.results_by_score = {}  # Dictionary to store results for each score
        self.processed_items_by_score = {}  # Track processed items per score
        self.all_results = []  # Keep this for backwards compatibility
        self.processed_items = 0
        self.mismatches = []
        self.total_correct = 0
        self.total_questions = 0
        self.total_skipped = 0  # Track scores skipped due to unmet conditions


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def start_mlflow_run(self):
        pass
    
    def log_parameters(self):
        pass

    def score_names(self):
        return self.subset_of_score_names if self.subset_of_score_names is not None else self.scorecard.score_names()

    def score_names_to_process(self):
        all_score_names_to_process = self.scorecard.score_names_to_process()
        if self.subset_of_score_names is not None:
            return [score_name for score_name in self.subset_of_score_names if score_name in all_score_names_to_process]
        else:
            return all_score_names_to_process

    def time_execution(func):
        async def async_wrapper(self, *args, **kwargs):
            start_time = time.time()
            result = await func(self, *args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            time_per_text = execution_time / self.number_of_texts_to_sample if self.number_of_texts_to_sample else 0
            logging.info(f"{func.__name__} executed in {execution_time:.2f} seconds. Average per text: {time_per_text:.2f}s")
            return result

        def sync_wrapper(self, *args, **kwargs):
            start_time = time.time()
            result = func(self, *args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            time_per_text = execution_time / self.number_of_texts_to_sample if self.number_of_texts_to_sample else 0
            logging.info(f"{func.__name__} executed in {execution_time:.2f} seconds. Average per text: {time_per_text:.2f}s")
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    @time_execution
    async def run(self):
        """Now this is an async function that just runs _async_run directly"""
        try:
            return await self._async_run()
        finally:
            # Signal metrics tasks to stop gracefully
            self.should_stop = True
            
            if self.metrics_tasks:
                logging.info("Waiting for metrics tasks to complete...")
                try:
                    # Wait for all tasks to complete naturally
                    done, pending = await asyncio.wait(
                        self.metrics_tasks.values(),
                        timeout=30.0,
                        return_when=asyncio.ALL_COMPLETED
                    )
                    
                    if pending:
                        logging.warning(f"{len(pending)} metrics tasks still running after 30s wait")
                        # Instead of canceling, wait a bit longer for final updates
                        try:
                            await asyncio.wait(pending, timeout=5.0)
                        except Exception as e:
                            logging.error(f"Error waiting for pending tasks: {e}")
                    
                    # Check for any exceptions in completed tasks
                    for task in done:
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass  # Ignore cancellation errors
                        except Exception as e:
                            logging.error(f"Error in metrics task: {e}")
                            
                except Exception as e:
                    logging.error(f"Error during metrics task cleanup: {e}")
                
                logging.info("Metrics task cleanup completed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def log_to_dashboard(self, metrics, status="RUNNING"):
        """Log metrics to the Plexus Dashboard with retry logic"""
        if not self.task_id:
            logging.info("No task_id provided, skipping metrics logging")
            return

        class MethodSafeEncoder(json.JSONEncoder):
            """Custom JSON encoder that safely handles methods and other non-serializable objects."""
            def default(self, obj):
                if inspect.ismethod(obj) or inspect.isfunction(obj) or callable(obj):
                    return f"<method: {obj.__name__ if hasattr(obj, '__name__') else str(obj)}>"
                elif hasattr(obj, 'tolist') and callable(obj.tolist):
                    # Handle numpy arrays and similar objects with tolist method
                    return obj.tolist()
                elif hasattr(obj, '__dict__'):
                    # Handle custom objects by converting to dict when possible
                    try:
                        return {k: v for k, v in obj.__dict__.items() 
                                if not k.startswith('_') and not callable(v)}
                    except (TypeError, AttributeError):
                        return str(obj)
                else:
                    try:
                        return super().default(obj)
                    except (TypeError, OverflowError):
                        return str(obj)

        def safe_json_dumps(obj):
            """Convert object to JSON string using our safe encoder"""
            try:
                return json.dumps(obj, cls=MethodSafeEncoder)
            except (TypeError, OverflowError) as e:
                # If we still have serialization errors, try to identify the problematic paths
                problematic_paths = []
                
                def find_problematic_paths(obj, path=""):
                    """Recursively identify paths to non-serializable objects"""
                    if obj is None or isinstance(obj, (str, int, float, bool)):
                        return []
                    
                    problems = []
                    
                    # Check if this object itself is problematic
                    try:
                        json.dumps(obj)
                    except (TypeError, OverflowError):
                        problems.append(path)
                    
                    # Recursively check components
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            problems.extend(find_problematic_paths(v, f"{path}.{k}" if path else k))
                    elif isinstance(obj, (list, tuple)):
                        for i, item in enumerate(obj):
                            problems.extend(find_problematic_paths(item, f"{path}[{i}]"))
                    elif hasattr(obj, '__dict__'):
                        try:
                            for k, v in obj.__dict__.items():
                                if not k.startswith('_'):
                                    problems.extend(find_problematic_paths(v, f"{path}.{k}" if path else k))
                        except Exception:
                            # If we can't access __dict__ attributes, mark the whole object
                            problems.append(path)
                    
                    return problems
                
                problematic_paths = find_problematic_paths(obj)
                logging.error(f"JSON serialization error: {e}. Problematic paths: {problematic_paths}")
                
                # Try again with a simpler encoder that just converts everything to strings
                cleaned_obj = {}
                for k, v in obj.items() if isinstance(obj, dict) else []:
                    try:
                        json.dumps({k: v})
                        cleaned_obj[k] = v
                    except (TypeError, OverflowError):
                        cleaned_obj[k] = str(v)
                
                return json.dumps(cleaned_obj)

        # Create a fresh client for each update
        client = PlexusDashboardClient()
        try:
            # Construct the mutation for updateEvaluation
            mutation = self._get_update_mutation()
            
            # Construct the variables
            variables = self._get_update_variables(metrics, status)
            
            # Ensure we have valid JSON before sending
            try:
                # Serialize variables safely and log them for debugging
                serialized_variables = safe_json_dumps(variables)
                clean_variables = json.loads(serialized_variables)
                
                # Updating evaluation metrics
                
                # Execute the mutation with proper client handling
                # Use asyncio.to_thread for the synchronous execute method
                result = await asyncio.to_thread(client.execute, mutation, clean_variables)
                
                # Log the success
                logging.info(f"Successfully updated evaluation metrics for task {self.task_id}")
                return result
                
            except json.JSONDecodeError as je:
                logging.error(f"JSON serialization error: {je}. Unable to prepare variables for API call.")
                raise
                
        except Exception as e:
            # Log full error details including the mutation and variables
            logging.error(f"Error updating evaluation metrics for task {self.task_id}: {str(e)}")
            if variables:
                logging.error(f"Failed mutation variables: {variables}")
            
            # Re-raise for retry
            raise
            
        finally:
            # Ensure client is properly closed
            if hasattr(client, 'close') and callable(client.close):
                try:
                    await client.close()
                except Exception as e:
                    logging.warning(f"Error closing GraphQL client: {str(e)}")

    def calculate_metrics(self, results):
        if not results:
            self.logging.warning("No results to calculate metrics")
            # Return default/empty metrics to avoid crashing
            return {
                "accuracy": 0,
                "alignment": 0,
                "precision": 0,
                "recall": 0,
                "confusionMatrix": {
                    "matrix": [[0, 0], [0, 0]],
                    "labels": ['yes', 'no']
                },
                "predictedClassDistribution": [{
                    "score": "no_data",
                    "label": "no_data",
                    "count": 0,
                    "percentage": 0
                }],
                "datasetClassDistribution": [{
                    "score": "no_data", 
                    "label": "no_data",
                    "count": 0,
                    "percentage": 0
                }]
            }

        # Import metrics classes
        from plexus.analysis.metrics.gwet_ac1 import GwetAC1
        from plexus.analysis.metrics.accuracy import Accuracy
        from plexus.analysis.metrics.precision import Precision
        from plexus.analysis.metrics.recall import Recall
        from plexus.analysis.metrics.metric import Metric

        self.logging.info(f"Calculating metrics for {len(results)} results")
        predicted_distributions = {}
        actual_distributions = {}
        confusion_matrices = {}
        
        total_correct = 0
        total_predictions = 0
        
        # For Gwet's AC1 calculation, track all predictions and actuals
        all_predictions = []
        all_actuals = []
        
        # Get the primary score name - if we're evaluating a specific score, use that
        primary_score_name = None
        if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
            primary_score_name = self.subset_of_score_names[0]
        
        # First pass: build distributions and confusion matrices
        logged_results_count = 0
        for result in results:
            for score_identifier, score_result in result['results'].items():
                if not hasattr(score_result, 'value'):
                    self.logging.warning(f"Score result has no 'value' attribute: {score_identifier}")
                    continue

                # Skip if the score result is a system error (has error attribute) or was skipped due to unmet conditions
                # Note: Don't skip if "error" is a legitimate class label (no error attribute)
                if isinstance(score_result.value, str) and score_result.value.upper() == "SKIPPED":
                    continue
                if isinstance(score_result.value, str) and score_result.value.upper() == "ERROR" and hasattr(score_result, 'error') and score_result.error:
                    continue

                # Ensure parameters attribute exists before accessing name
                if not hasattr(score_result, 'parameters') or not hasattr(score_result.parameters, 'name'):
                    self.logging.warning(f"Skipping result without valid parameters: {score_identifier}")
                    continue
                score_name = score_result.parameters.name

                # Skip if this is a dependency score and not our primary score
                if primary_score_name and score_name != primary_score_name:
                    continue

                # Ensure metadata and human_label exist before accessing
                if not hasattr(score_result, 'metadata') or 'human_label' not in score_result.metadata:
                    self.logging.warning(f"Skipping result missing metadata: {score_identifier}")
                    continue

                # Standardize and prepare predicted & actual values
                predicted = str(score_result.value).lower().strip()
                actual = str(score_result.metadata['human_label']).lower().strip()
                
                # Standardize empty or NA values
                predicted = 'na' if predicted in ['', 'nan', 'n/a', 'none', 'null'] else predicted
                actual = 'na' if actual in ['', 'nan', 'n/a', 'none', 'null'] else actual
                
                # Collect predictions and actuals for Gwet's AC1 calculation
                all_predictions.append(predicted)
                all_actuals.append(actual)
                
                # Log the first few results for inspection
                if logged_results_count < 5:
                    self.logging.info(f"Sample {logged_results_count + 1}: {score_name} - Predicted: '{predicted}', Actual: '{actual}'")
                    logged_results_count += 1

                # Determine correctness - check if predicted value exactly matches the actual value
                is_correct = predicted == actual
                
                # Update score_result metadata to ensure correct value is set
                score_result.metadata['correct'] = is_correct
                
                # Update total correct and predictions
                if is_correct:
                    total_correct += 1
                total_predictions += 1
                
                # Update actual label distribution
                if score_name not in actual_distributions:
                    actual_distributions[score_name] = {}
                if actual not in actual_distributions[score_name]:
                    actual_distributions[score_name][actual] = 0
                actual_distributions[score_name][actual] += 1
                
                # Update predicted distribution
                if score_name not in predicted_distributions:
                    predicted_distributions[score_name] = {}
                if predicted not in predicted_distributions[score_name]:
                    predicted_distributions[score_name][predicted] = 0
                predicted_distributions[score_name][predicted] += 1
                
                # Initialize confusion matrix for this score if needed
                if score_name not in confusion_matrices:
                    confusion_matrices[score_name] = {
                        'matrix': {},
                        'labels': set()
                    }
                
                # Add labels to set
                confusion_matrices[score_name]['labels'].add(actual)
                confusion_matrices[score_name]['labels'].add(predicted)
                
                # Initialize matrix entry if needed
                if actual not in confusion_matrices[score_name]['matrix']:
                    confusion_matrices[score_name]['matrix'][actual] = {}
                if predicted not in confusion_matrices[score_name]['matrix'][actual]:
                    confusion_matrices[score_name]['matrix'][actual][predicted] = 0
                
                # Update confusion matrix
                confusion_matrices[score_name]['matrix'][actual][predicted] += 1

        # Calculate overall accuracy using the Accuracy metric class
        accuracy_value = 0
        if all_predictions and all_actuals and len(all_predictions) == len(all_actuals) and len(all_predictions) > 0:
            try:
                # Calculate accuracy
                
                # Create an Accuracy instance and use proper Metric.Input interface
                accuracy_calculator = Accuracy()
                metric_input = Metric.Input(
                    reference=all_actuals,
                    predictions=all_predictions
                )
                result = accuracy_calculator.calculate(metric_input)
                accuracy_value = result.value
                # Accuracy calculated successfully
            except Exception as e:
                self.logging.error(f"Error calculating Accuracy: {str(e)}")
                # Fall back to manual calculation if the Accuracy class fails
                accuracy_value = total_correct / total_predictions if total_predictions > 0 else 0
        else:
            # If lists are empty or unequal, use the original calculation
            accuracy_value = total_correct / total_predictions if total_predictions > 0 else 0
        
        # Calculate Gwet's AC1 for alignment
        gwet_ac1_value = 0
        if all_predictions and all_actuals and len(all_predictions) == len(all_actuals) and len(all_predictions) > 0:
            try:
                # Calculate AC1
                
                # Create a GwetAC1 instance and use proper Metric.Input interface
                gwet_calculator = GwetAC1()
                metric_input = Metric.Input(
                    reference=all_actuals,
                    predictions=all_predictions
                )
                result = gwet_calculator.calculate(metric_input)
                gwet_ac1_value = result.value
                # Map AC1 from [-1, 1] to [0, 1] for backward compatibility
                # Any negative values are mapped to 0
                gwet_ac1_mapped = max(0, (gwet_ac1_value + 1) / 2)
            except Exception as e:
                self.logging.error(f"Error calculating Gwet's AC1: {str(e)}")
                gwet_ac1_value = 0
        
        # Calculate precision using the Precision metric class
        precision_value = accuracy_value  # Default fallback is to use accuracy
        
        # First check if we have binary classification data (yes/no) for specialized binary metrics
        binary_confusion_matrix = None
        for score_name, matrix_data in confusion_matrices.items():
            labels = sorted(list(matrix_data['labels']))
            
            if len(labels) == 2 and 'yes' in labels and 'no' in labels:
                binary_confusion_matrix = matrix_data
                break
        
        # Calculate precision using the Precision class
        if all_predictions and all_actuals and len(all_predictions) == len(all_actuals) and len(all_predictions) > 0:
            try:
                # Calculate Precision
                
                # Create a Precision instance and use proper Metric.Input interface
                precision_calculator = Precision(positive_labels=['yes'])
                metric_input = Metric.Input(
                    reference=all_actuals,
                    predictions=all_predictions
                )
                result = precision_calculator.calculate(metric_input)
                precision_value = result.value
                precision_value = result.value
            except Exception as e:
                self.logging.error(f"Error calculating Precision: {str(e)}")
                self.logging.exception("Stack trace for Precision calculation error:")
                
                # Fall back to manual calculation if the Precision class fails
                if binary_confusion_matrix:
                    # Manual calculation from confusion matrix
                    tp = binary_confusion_matrix['matrix'].get('yes', {}).get('yes', 0)
                    fp = binary_confusion_matrix['matrix'].get('no', {}).get('yes', 0)
                    precision_value = tp / (tp + fp) if (tp + fp) > 0 else 0
                    # Fallback to manual precision calculation from matrix
                else:
                    # If no binary confusion matrix, use accuracy as a fallback
                    precision_value = accuracy_value
                    # Using accuracy as fallback for precision
        elif binary_confusion_matrix:
            # If we have a binary confusion matrix but couldn't use the Precision class
            tp = binary_confusion_matrix['matrix'].get('yes', {}).get('yes', 0)
            fp = binary_confusion_matrix['matrix'].get('no', {}).get('yes', 0)
            precision_value = tp / (tp + fp) if (tp + fp) > 0 else 0
            self.logging.info(f"Calculated precision manually from confusion matrix: {precision_value}")
        else:
            # Default fallback - using accuracy as fallback for precision due to insufficient data
            precision_value = accuracy_value
        
        # Calculate recall using the Recall metric class
        recall_value = accuracy_value  # Default fallback is to use accuracy
        
        # Calculate recall using the Recall class
        if all_predictions and all_actuals and len(all_predictions) == len(all_actuals) and len(all_predictions) > 0:
            try:
                # Calculate Recall
                
                # Create a Recall instance and use proper Metric.Input interface
                recall_calculator = Recall(positive_labels=['yes'])
                metric_input = Metric.Input(
                    reference=all_actuals,
                    predictions=all_predictions
                )
                result = recall_calculator.calculate(metric_input)
                recall_value = result.value
                recall_value = result.value
            except Exception as e:
                self.logging.error(f"Error calculating Recall: {str(e)}")
                self.logging.exception("Stack trace for Recall calculation error:")
                
                # Fall back to manual calculation if the Recall class fails
                if binary_confusion_matrix:
                    # Manual calculation from confusion matrix
                    tp = binary_confusion_matrix['matrix'].get('yes', {}).get('yes', 0)
                    fn = binary_confusion_matrix['matrix'].get('yes', {}).get('no', 0)
                    recall_value = tp / (tp + fn) if (tp + fn) > 0 else 0
                    # Fallback to manual recall calculation from matrix
                else:
                    # If no binary confusion matrix, use accuracy as a fallback
                    recall_value = accuracy_value
                    # Using accuracy as fallback for recall
        elif binary_confusion_matrix:
            # If we have a binary confusion matrix but couldn't use the Recall class
            tp = binary_confusion_matrix['matrix'].get('yes', {}).get('yes', 0)
            fn = binary_confusion_matrix['matrix'].get('yes', {}).get('no', 0)
            recall_value = tp / (tp + fn) if (tp + fn) > 0 else 0
            self.logging.info(f"Calculated recall manually from confusion matrix: {recall_value}")
        else:
            # Default fallback - using accuracy as fallback for recall due to insufficient data
            recall_value = accuracy_value
        
        # Alignment is calculated with Gwet's AC1
        alignment = gwet_ac1_value

        # Format the confusion matrix for the primary score (or first score) for the API
        primary_confusion_matrix_dict = None
        # Determine primary score name again for clarity
        primary_score_name_for_cm = None
        if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
            primary_score_name_for_cm = self.subset_of_score_names[0]

        target_score_name = primary_score_name_for_cm
        if target_score_name and target_score_name in confusion_matrices:
            matrix_data = confusion_matrices[target_score_name]
        elif confusion_matrices: # Fallback to the first matrix if primary not found or not set
            first_score_name = next(iter(confusion_matrices))
            matrix_data = confusion_matrices[first_score_name]
            target_score_name = first_score_name # Update target name for logging
        else:
            matrix_data = None # No matrices calculated

        if matrix_data:
            labels = sorted(list(matrix_data['labels']))
            matrix = []
            
            # Initialize the matrix with zeros
            for _ in range(len(labels)):
                matrix.append([0] * len(labels))
            
            # Fill in the matrix values
            for i, actual_label in enumerate(labels):
                for j, predicted_label in enumerate(labels):
                    matrix[i][j] = matrix_data['matrix'].get(actual_label, {}).get(predicted_label, 0)

            primary_confusion_matrix_dict = {
                "matrix": matrix,
                "labels": labels
            }
            # Confusion matrix prepared for API
        else:
            # Create a default empty matrix if none were generated
            self.logging.warning("No confusion matrix data generated, creating default structure.")
            primary_confusion_matrix_dict = {
                "matrix": [[0, 0], [0, 0]],
                "labels": ['yes', 'no'] # Default labels
            }

        # Format distributions for API - now including score names in the distribution
        predicted_label_distributions = []
        for score_name, distribution in predicted_distributions.items():
            total_score_predictions = sum(distribution.values())
            for label, count in distribution.items():
                predicted_label_distributions.append({
                    "score": score_name,
                    "label": label,
                    "count": count,
                    "percentage": (count / total_score_predictions * 100) if total_score_predictions > 0 else 0
                })

        actual_label_distributions = []
        for score_name, distribution in actual_distributions.items():
            total_score_actuals = sum(distribution.values())
            for label, count in distribution.items():
                actual_label_distributions.append({
                    "score": score_name,
                    "label": label,
                    "count": count,
                    "percentage": (count / total_score_actuals * 100) if total_score_actuals > 0 else 0
                })

        # Ensure we have at least one entry in each required field
        if not primary_confusion_matrix_dict:
            primary_confusion_matrix_dict = {
                "matrix": [[0, 0], [0, 0]],
                "labels": ['yes', 'no']
            }
        
        if not predicted_label_distributions:
            predicted_label_distributions.append({
                "score": primary_score_name or self.score_names()[0],
                "label": "no_data",
                "count": 0,
                "percentage": 0
            })
            
        if not actual_label_distributions:
            actual_label_distributions.append({
                "score": primary_score_name or self.score_names()[0],
                "label": "no_data",
                "count": 0,
                "percentage": 0
            })

        # Log final metrics summary
        self.logging.info(f"Metrics: {total_correct}/{total_predictions} correct, Accuracy: {accuracy_value:.3f}, Precision: {precision_value:.3f}, Alignment: {alignment:.3f}, Recall: {recall_value:.3f}")

        return {
            "accuracy": accuracy_value,
            "precision": precision_value,
            "alignment": alignment,  # Changed from sensitivity to alignment
            "recall": recall_value,        # Changed from specificity to recall
            "confusionMatrix": primary_confusion_matrix_dict, # Use the new single dict
            "predictedClassDistribution": predicted_label_distributions,
            "datasetClassDistribution": actual_label_distributions,
            # "confusion_matrices": formatted_confusion_matrices # Removed old key
        }

    async def _async_run(self):
        # Starting evaluation

        # Configure logging
        # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

        # Determine the correct report folder
        if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
            try:
                score_instance = self.get_score_instance(self.subset_of_score_names[0])
                report_folder_path = score_instance.report_directory_path()
                report_folder_path = report_folder_path.rstrip('/')
            except ValueError as e:
                self.logging.info(f"Could not get score instance for report folder: {e}")
                # Fallback to default report folder structure
                scorecard_name = self.scorecard.name.replace(' ', '_') if hasattr(self.scorecard, 'name') and callable(self.scorecard.name) else str(self.scorecard_name).replace(' ', '_')
                score_name = self.subset_of_score_names[0].replace(' ', '_')
                report_folder_path = f"./score_results/{scorecard_name}/{score_name}"
        else:
            scorecard_name = self.scorecard.name.replace(' ', '_')
            report_folder_path = f"./score_results/{scorecard_name}/combined"

        # Ensure the report folder exists
        os.makedirs(report_folder_path, exist_ok=True)

        logging.info(f"Report folder set to: {report_folder_path}")

        if self.labeled_samples:
            df = pd.DataFrame(self.labeled_samples)
        else:
            df = pd.read_csv(self.labeled_samples_filename)
        
        # Update number_of_texts_to_sample if dataframe is smaller
        self.number_of_texts_to_sample = min(len(df), self.requested_sample_size)
        logging.info(f"Adjusted sample size from {self.requested_sample_size} to {self.number_of_texts_to_sample} based on available data")

        # Calculate original label distribution before sampling
        label_distributions = []
        is_dataset_balanced = True  # Track overall dataset balance
        
        for score_name in self.score_names():
            try:
                score_instance = self.get_score_instance(score_name)
                label_score_name = score_instance.get_label_score_name()
            except ValueError as e:
                self.logging.info(f"Could not get score instance for label distribution: {e}, skipping {score_name}")
                continue
            
            # Try both possible column names for labels
            label_column = label_score_name + '_label'
            if label_column in df.columns:
                labels = df[label_column]
            elif label_score_name in df.columns:
                labels = df[label_score_name]
            else:
                logging.warning(f"No label column found for {score_name}")
                continue
            
            # Clean and standardize labels
            labels = labels.astype(str).str.lower().str.strip()
            labels = labels.replace({'nan': 'na', 'n/a': 'na', '': 'na'})
            
            # Calculate distribution
            value_counts = labels.value_counts()
            
            # Format distribution to match expected format exactly
            distribution = [
                {"label": str(label), "count": int(count)}
                for label, count in value_counts.items()
            ]
            
            # Check if distribution is balanced
            total = sum(d["count"] for d in distribution)
            expected_count = total / len(distribution)
            tolerance = 0.2  # 20% tolerance
            score_is_balanced = all(
                abs(d["count"] - expected_count) <= expected_count * tolerance 
                for d in distribution
            )
            
            # Update overall balance status
            is_dataset_balanced = is_dataset_balanced and score_is_balanced
            
            # Only include the distribution in the format expected by the API
            label_distributions.extend(distribution)

        # Update the experiment with the original distribution
        if self.dashboard_client and self.experiment_id:
            try:
                self.dashboard_client.updateEvaluation(
                    id=self.experiment_id,
                    datasetClassDistribution=json.dumps(label_distributions),
                    isDatasetClassDistributionBalanced=is_dataset_balanced
                )
            except Exception as e:
                logging.error(f"Failed to update dataset distribution: {e}")

        # Ensure we have the necessary columns
        if 'text' not in df.columns:
            raise ValueError("The dataframe must contain a 'text' column")

        if 'content_id' not in df.columns:
            logging.warning("'content_id' column not found. Using index as content_id.")
            df['content_id'] = df.index.astype(str)

        if 'Session ID' not in df.columns:
            logging.warning("'Session ID' column not found. Using content_id as Session ID.")
            df['Session ID'] = df['content_id']

        # Optional: 'feedback_item_id' column can be included to link score results to existing feedback items
        if 'feedback_item_id' in df.columns:
            logging.info("Found 'feedback_item_id' column - will link score results to existing feedback items")
        else:
            logging.info("No 'feedback_item_id' column found - score results will be created without feedback item links")

        fine_tuning_ids = set()
        fine_tuning_ids_file = f"tuning/{self.scorecard_name}/{self.subset_of_score_names[0]}/training_ids.txt"
        original_shape = df.shape
        if os.path.exists(fine_tuning_ids_file):
            with open(fine_tuning_ids_file, 'r') as f:
                fine_tuning_ids = set(f.read().splitlines())
            logging.info(f"Loaded {len(fine_tuning_ids)} IDs used in fine-tuning")
            
            # Debug: Check the types and some sample values
            logging.info(f"Sample fine-tuning IDs: {list(fine_tuning_ids)[:5]}")
            logging.info(f"Sample content_ids from DataFrame: {df['content_id'].head().tolist()}")
            logging.info(f"content_id dtype: {df['content_id'].dtype}")
            
            # Convert fine_tuning_ids to the same type as content_id
            fine_tuning_ids = set(df['content_id'].dtype.type(id) for id in fine_tuning_ids)
            
            # Check for any matches
            matching_ids = df['content_id'].isin(fine_tuning_ids)
            logging.info(f"Number of matching IDs: {matching_ids.sum()}")
            
            df = df[~df['content_id'].isin(fine_tuning_ids)]
            logging.info(f"Excluded fine-tuning IDs. Original DataFrame shape: {original_shape}, New DataFrame shape: {df.shape}")
            
            # If still no change, let's check for any partial matches
            if original_shape == df.shape:
                partial_matches = df['content_id'].apply(lambda x: any(str(x) in str(id) for id in fine_tuning_ids))
                logging.info(f"Number of partial matches: {partial_matches.sum()}")
                if partial_matches.sum() > 0:
                    logging.info("Sample partial matches:")
                    for idx, content_id in df[partial_matches]['content_id'].head().items():
                        matching_fine_tuning_ids = [id for id in fine_tuning_ids if str(content_id) in str(id)]
                        logging.info(f"DataFrame ID: {content_id}, Matching fine-tuning IDs: {matching_fine_tuning_ids}")

        if hasattr(self, 'session_ids_to_sample') and self.session_ids_to_sample:
            selected_sample_rows = df[df['Session ID'].isin(self.session_ids_to_sample)]
        elif self.sampling_method == 'random':
            logging.info(f"Random seed: {self.random_seed}")
            logging.info(f"DataFrame shape before sampling: {df.shape}")
            logging.info(f"First few DataFrame indices: {df.index[:5].tolist()}")
            logging.info(f"First few Session IDs: {df['Session ID'].head(5).tolist()}")
            
            try:
                if self.number_of_texts_to_sample > len(df):
                    logging.warning("Requested number of samples is larger than the dataframe size. Using the entire dataframe.")
                    selected_sample_rows = df
                else:
                    selected_sample_rows = df.sample(
                        n=self.number_of_texts_to_sample,
                        random_state=self.random_seed
                    )

                logging.info(f"Sampled DataFrame shape: {selected_sample_rows.shape}")
                logging.info(f"First few sampled indices: {selected_sample_rows.index[:5].tolist()}")
                logging.info(f"First few sampled Session IDs: {selected_sample_rows['Session ID'].head(5).tolist()}")
            except ValueError as e:
                logging.error(f"Sampling error: {e}")
                selected_sample_rows = df
        elif self.sampling_method == 'sequential':
            logging.info(f"DataFrame shape before sampling: {df.shape}")
            logging.info(f"First few DataFrame indices: {df.index[:5].tolist()}")
            logging.info(f"First few session IDs: {df['Session ID'].head(5).tolist()}")

            logging.info("Using sequential sampling.")
            selected_sample_rows = df.head(self.number_of_texts_to_sample)
            
            logging.info(f"Sampled DataFrame shape: {selected_sample_rows.shape}")
            logging.info(f"First few sampled indices: {selected_sample_rows.index[:5].tolist()}")
            logging.info(f"First few sampled session IDs: {selected_sample_rows['Session ID'].head(5).tolist()}")
        elif self.sampling_method == 'provided':
            # Samples are already provided and pre-processed, use them as-is
            selected_sample_rows = df
            self.logging.info(f"Using {len(df)} provided samples without additional sampling")
        else:
            logging.warning(f"Unknown sampling method '{self.sampling_method}'. Defaulting to random.")
            selected_sample_rows = df.sample(
                n=self.number_of_texts_to_sample,
                random_state=self.random_seed
            )

        # Process all results concurrently for each score
        score_tasks = []
        for score_name in self.score_names():
            task = asyncio.create_task(self.score_all_texts_for_score(selected_sample_rows, score_name))
            score_tasks.append(task)

        # Wait for all score evaluations to complete
        all_results = await asyncio.gather(*score_tasks)
        # Flatten results from all scores and filter out exceptions
        self.all_results = [
            result for score_results in all_results 
            for result in score_results 
            if not isinstance(result, Exception)
        ]

        if not os.path.exists(report_folder_path):
            os.makedirs(report_folder_path)

        scorecard_results = ScorecardResults(self.all_results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_filename = f"scorecard_results_{timestamp}.json"
        scorecard_results.save_to_file(f"{report_folder_path}/{results_filename}")

        logging.info("Scoring completed.")

        # Count the number correct out of all questions.
        for result in self.all_results:
            logging.info(f"Form ID: {result['form_id']}")
            for question in self.score_names():
                score_result = next((result for result in result['results'].values() if result.parameters.name == question), None)
                
                # Skip counting if score was skipped due to unmet conditions
                if score_result and isinstance(score_result.value, str) and score_result.value.upper() == "SKIPPED":
                    logging.info(f"Question: {question}, skipped due to unmet dependency conditions")
                    self.total_skipped += 1
                    continue
                
                score_value = str(score_result.value).lower() if score_result else None
                human_label = str(score_result.metadata['human_label']).lower() if score_result and hasattr(score_result, 'metadata') and 'human_label' in score_result.metadata else None
                logging.info(f"Question: {question}, score Label: {score_value}, Human Label: {human_label}")
                is_match = 1 if score_result and hasattr(score_result, 'metadata') and score_result.metadata.get('correct', False) else 0
                self.total_correct += is_match
                self.total_questions += 1

                if not is_match and len(self.mismatches) < self.max_mismatches_to_report:
                    mismatch_data = {
                        'form_id': result['form_id'],
                        'question': question,
                        'predicted': score_value,
                        'ground_truth': human_label,
                        'explanation': score_result.metadata['explanation'] if score_result and hasattr(score_result, 'metadata') and 'explanation' in score_result.metadata else None,
                        'transcript': score_result.metadata['text'] if score_result and hasattr(score_result, 'metadata') and 'text' in score_result.metadata else None
                    }
                    # Only append if we have either a transcript or an explanation
                    if mismatch_data['transcript'] is not None or mismatch_data['explanation'] is not None:
                        self.mismatches.append(mismatch_data)

        analysis = ScorecardResultsAnalysis(
            scorecard_results=scorecard_results
        )

        def log_accuracy_heatmap():
            try:
                analysis.plot_accuracy_heatmap()
            except Exception as e:
                logging.error(f"Failed to log accuracy heatmap: {e}")

        def log_html_report():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                html_report_content = analysis.generate_html_report(expenses=expenses)
                report_filename = f"scorecard_report_{timestamp}.html"
                with open(f"{report_folder_path}/{report_filename}", "w") as file:
                    file.write(html_report_content)
            except Exception as e:
                logging.error(f"Failed to log HTML report: {e}")

        def log_incorrect_scores_report():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                html_report_content = analysis.generate_html_report(only_incorrect_scores=True, expenses=expenses)
                report_filename = f"scorecard_report_incorrect_scores_{timestamp}.html"
                with open(f"{report_folder_path}/{report_filename}", "w") as file:
                    file.write(html_report_content)
            except Exception as e:
                logging.error(f"Failed to log incorrect scores report: {e}")

        def log_no_costs_report():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                html_report_content = analysis.generate_html_report(redact_cost_information=True)
                report_filename = f"scorecard_report_no_costs_{timestamp}.html"
                with open(f"{report_folder_path}/{report_filename}", "w") as file:
                    file.write(html_report_content)
            except Exception as e:
                logging.error(f"Failed to log no costs report: {e}")

        def log_scorecard_costs():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                analysis.plot_scorecard_costs(results=self.all_results)
            except Exception as e:
                logging.error(f"Failed to log scorecard costs: {e}")

        def log_csv_report():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_filename = f"scorecard_report_for_incorrect_results_{timestamp}.csv"
                with open(f"{report_folder_path}/{report_filename}", "w") as file:
                    file.write(analysis.generate_csv_scorecard_report(results=self.all_results))
            except Exception as e:
                logging.error(f"Failed to log CSV report: {e}")

        def log_question_accuracy_csv():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_filename = f"question_accuracy_report_{timestamp}.csv"
                analysis.generate_question_accuracy_csv(output_file=f"{report_folder_path}/{report_filename}")
            except Exception as e:
                logging.error(f"Failed to log question accuracy CSV: {e}")

        expenses = self.scorecard.get_accumulated_costs()
        expenses['cost_per_text'] = expenses['total_cost'] / len(selected_sample_rows)    

        loop = asyncio.get_running_loop()

        # Run these operations concurrently
        await asyncio.gather(
            asyncio.to_thread(log_html_report),
            asyncio.to_thread(log_incorrect_scores_report),
            asyncio.to_thread(log_no_costs_report),
            asyncio.to_thread(log_csv_report),
            asyncio.to_thread(log_question_accuracy_csv)
        )

        # Run these sequentially to avoid issues with Heatmap generation.
        await asyncio.to_thread(log_accuracy_heatmap)
        await asyncio.to_thread(log_scorecard_costs)

        # Calculate overall accuracy
        overall_accuracy = (self.total_correct / self.total_questions) * 100 if self.total_questions > 0 else 0

        # Generate the Excel report
        self.generate_excel_report(report_folder_path, self.all_results, selected_sample_rows)

        logging.info(f"Expenses: {expenses}")
        logging.info(f"{overall_accuracy:.1f}% accuracy / {len(selected_sample_rows)} samples")
        if self.total_skipped > 0:
            logging.info(f"Skipped {self.total_skipped} score results due to unmet dependency conditions")
        logging.info(f"cost: ${expenses['cost_per_text']:.6f} per call / ${expenses['total_cost']:.6f} total")

        # Build confusion matrix metrics for the summary
        confusion_metrics = self._build_confusion_metrics_from_results()

        # Analyze confidence calibration if confidence features are detected (preserve raw values)
        calibration_report = None
        try:
            from plexus.confidence_calibration import (
                detect_confidence_feature_enabled,
                extract_confidence_accuracy_pairs,
                compute_isotonic_regression_calibration,
                serialize_calibration_model,
                generate_calibration_report
            )

            logging.info(f"About to check confidence detection on {len(self.all_results)} results")
            print(f"DEBUG: About to check confidence detection on {len(self.all_results)} results")
            confidence_detected = detect_confidence_feature_enabled(self.all_results)
            logging.info(f"Confidence detection result: {confidence_detected}")
            print(f"DEBUG: Confidence detection result: {confidence_detected}")

            if confidence_detected:
                logging.info("Confidence feature detected - computing isotonic regression calibration")

                # Extract confidence-accuracy pairs
                confidence_scores, accuracy_labels = extract_confidence_accuracy_pairs(self.all_results)

                if len(confidence_scores) >= 10:
                    # Compute calibration model
                    calibration_model = compute_isotonic_regression_calibration(confidence_scores, accuracy_labels)

                    if calibration_model is not None:
                        # Generate calibration report with serialized model data
                        calibration_report = generate_calibration_report(
                            confidence_scores, accuracy_labels, calibration_model
                        )

                        # Add serialized calibration data for future use
                        calibration_report["calibration_model"] = serialize_calibration_model(calibration_model)

                        # Generate reliability diagram visualization
                        try:
                            from plexus.confidence_calibration import plot_reliability_diagram
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            reliability_plot_path = f"{report_folder_path}/reliability_diagram_{timestamp}.png"

                            plot_reliability_diagram(
                                confidence_scores=confidence_scores,
                                accuracy_labels=accuracy_labels,
                                save_path=reliability_plot_path,
                                title="Confidence Calibration - Raw Model Output",
                                n_bins=20  # 5% buckets
                            )

                            logging.info(f"Reliability diagram saved to: {reliability_plot_path}")
                        except Exception as e:
                            logging.warning(f"Could not generate reliability diagram: {e}")

                        logging.info(f"Computed isotonic regression calibration from {len(confidence_scores)} confidence scores")
                        logging.info(f"Expected Calibration Error: {calibration_report.get('expected_calibration_error', 'N/A'):.4f}")
                        logging.info("Raw confidence values preserved - calibration data stored for future application")
                    else:
                        logging.warning("Could not compute calibration model")
                else:
                    logging.info(f"Insufficient data for calibration: {len(confidence_scores)} samples (need at least 10)")
            else:
                logging.debug("No confidence features detected - skipping calibration")

        except ImportError:
            logging.warning("sklearn not available - skipping confidence calibration")
        except Exception as e:
            logging.error(f"Error during confidence calibration: {e}")

        report = self.generate_report(score_instance, overall_accuracy, expenses, len(selected_sample_rows), confusion_metrics)
        logging.info(report)

        await asyncio.to_thread(self.generate_and_log_confusion_matrix, self.all_results, report_folder_path)
        
        for question in self.score_names():
            self.create_performance_visualization(self.all_results, question, report_folder_path)

        self.generate_metrics_json(report_folder_path, len(selected_sample_rows), expenses, calibration_report)

    async def score_all_texts_for_score(self, selected_sample_rows, score_name: str, tracker):
        """Score all texts for a specific score with controlled concurrency"""
        if score_name not in self.results_by_score:
            self.results_by_score[score_name] = []
        if score_name not in self.processed_items_by_score:
            self.processed_items_by_score[score_name] = 0

        # Create a semaphore to limit concurrency
        # Default to 20 concurrent operations
        concurrency_limit = getattr(self, 'concurrency_limit', 20)
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        # Use an atomic counter for tracking progress
        processed_counter = 0
        total_rows = len(selected_sample_rows)
        
        # Add counter for ScoreResult creation attempts
        self.scoreresult_creation_attempts = getattr(self, 'scoreresult_creation_attempts', 0)
        self.scoreresult_creation_successes = getattr(self, 'scoreresult_creation_successes', 0)
        self.scoreresult_creation_failures = getattr(self, 'scoreresult_creation_failures', 0)
        
        async def process_text(row, idx):
            async with semaphore:  # This ensures only N concurrent operations
                try:
                    result = await self.score_text(row, score_name)
                    if result:
                        # Use nonlocal to modify the counter from within the nested function
                        nonlocal processed_counter
                        processed_counter += 1
                        
                        # Store result in order received
                        self.results_by_score[score_name].append(result)
                        self.processed_items_by_score[score_name] = processed_counter
                        self.processed_items = sum(self.processed_items_by_score.values())
                        
                        # Update tracker with actual count of processed items
                        if tracker and tracker.current_stage:
                            tracker.current_stage.status_message = f"Generating predictions ({processed_counter}/{total_rows})"
                        if tracker:
                            tracker.update(current_items=self.processed_items)
                        
                        # Start metrics task if needed
                        is_final_result = processed_counter == total_rows
                        await self.maybe_start_metrics_task(score_name, is_final_result)
                        
                        return result
                except Exception as e:
                    # Enhanced error logging with more context
                    error_context = {
                        'score_name': score_name,
                        'text_index': idx,
                        'content_id': row.get('content_id', 'unknown'),
                        'text_preview': str(row.get('text', ''))[:100] + '...' if row.get('text') else 'No text',
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'traceback': traceback.format_exc()
                    }
                    logging.error(f"Error processing text at index {idx} for {score_name}: {e}")
                    logging.error(f"Error context: {json.dumps(error_context, indent=2)}")
                    
                    # For NoneType iteration errors, provide specific guidance
                    if 'NoneType' in str(e) and 'iterable' in str(e):
                        logging.error("DEBUGGING TIP: This error usually occurs when None is used with 'in' operator or iteration")
                        logging.error("Check for None values in metadata, score parameters, or workflow state")
                    
                    raise

        # Create tasks for all rows but process them with controlled concurrency
        tasks = [
            asyncio.create_task(process_text(row, idx))
            for idx, (_, row) in enumerate(selected_sample_rows.iterrows())
        ]
        
        # Wait for all tasks to complete
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result:
                    results.append(result)
            except Exception as e:
                logging.error(f"Error in task for {score_name}: {e}")
        
        return results

    async def maybe_start_metrics_task(self, score_name: str, is_final_result: bool = False):
        """Start a metrics computation task if one isn't running, or if this is the final result"""
        if is_final_result:
            # For final results, always compute metrics
            self.completed_scores.add(score_name)
            if score_name in self.metrics_tasks:
                task = self.metrics_tasks[score_name]
                if not task.done():
                    task.cancel()
            self.metrics_tasks[score_name] = asyncio.create_task(self.continuous_metrics_computation(score_name))
        elif score_name not in self.metrics_tasks or self.metrics_tasks[score_name].done():
            # Start new task if none exists or previous one is done
            self.metrics_tasks[score_name] = asyncio.create_task(self.continuous_metrics_computation(score_name))

    async def continuous_metrics_computation(self, score_name: str):
        """Background task that continuously computes and posts metrics for a specific score"""
        last_processed_count = 0
        try:
            while not self.should_stop:
                # Check if we have any new results for this score
                current_count = len(self.results_by_score.get(score_name, []))
                if current_count > 0 and current_count != last_processed_count:
                    # Combine results from all scores for metrics calculation
                    combined_results = []
                    for score, results in self.results_by_score.items():
                        combined_results.extend(results)
                    
                    metrics = self.calculate_metrics(combined_results)
                    # If this is the final update (score is complete), mark it as completed
                    status = "COMPLETED" if score_name in self.completed_scores else "RUNNING"
                    
                    # For final updates, use synchronous execution
                    if status == "COMPLETED":
                        try:
                            # Create a client instance specifically for this final update
                            final_client = PlexusDashboardClient()
                            update_variables = self._get_update_variables(metrics, status)
                            if self.task_id:  # Ensure taskId is preserved in final update
                                update_variables['input']['taskId'] = self.task_id
                            # Use the new client instance for the synchronous call
                            final_client.execute(
                                self._get_update_mutation(),
                                update_variables
                            )
                            last_processed_count = current_count
                            # Close the client if possible (assuming synchronous close or relying on GC)
                            if hasattr(final_client, 'close') and callable(final_client.close):
                                try:
                                    # If close is async, this needs await asyncio.to_thread(final_client.close)
                                    # Assuming sync close or GC for now.
                                    pass
                                except Exception as close_err:
                                    self.logging.warning(f"Error closing final update client: {close_err}")

                        except Exception as e:
                            self.logging.error(f"Error in final metrics update: {e}")
                    else:
                        # For progress updates, use async with shield
                        try:
                            api_task = asyncio.shield(self.log_to_dashboard(metrics, status=status))
                            await api_task
                            last_processed_count = current_count
                        except asyncio.CancelledError:
                            # If cancelled during progress update, just log and continue
                            self.logging.info("Progress update cancelled")
                        except Exception as e:
                            self.logging.error(f"Error in progress update: {e}")
                
                # Wait a bit before checking again
                await asyncio.sleep(.1)

        except asyncio.CancelledError:
            # Handle final cleanup if needed
            if score_name in self.completed_scores:
                try:
                    # Ensure final metrics are posted synchronously
                    combined_results = []
                    for score, results in self.results_by_score.items():
                        combined_results.extend(results)
                    metrics = self.calculate_metrics(combined_results)
                    update_variables = self._get_update_variables(metrics, "COMPLETED")
                    if self.task_id:  # Ensure taskId is preserved in final cleanup
                        update_variables['input']['taskId'] = self.task_id
                    self.dashboard_client.execute(
                        self._get_update_mutation(),
                        update_variables
                    )
                except Exception as e:
                    self.logging.error(f"Error during final metrics update: {e}")
            self.logging.info(f"Metrics computation for {score_name} cancelled")
        except Exception as e:
            self.logging.error(f"Error in metrics computation for {score_name}: {e}")

    def _get_update_mutation(self):
        """Get the GraphQL mutation for updating metrics"""
        return """
        mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
            updateEvaluation(input: $input) {
                id
                type
                accountId
                status
                createdAt
                updatedAt
                parameters
                metrics
                inferences
                accuracy
                cost
                startedAt
                elapsedSeconds
                estimatedRemainingSeconds
                totalItems
                processedItems
                errorMessage
                errorDetails
                scorecardId
                scoreId
                confusionMatrix
                scoreGoal
                datasetClassDistribution
                isDatasetClassDistributionBalanced
                predictedClassDistribution
                isPredictedClassDistributionBalanced
            }
        }
        """

    def _get_update_variables(self, metrics, status):
        """Get the variables for the update mutation"""
        elapsed_seconds = int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        
        # Format metrics for API
        metrics_for_api = []
        if metrics.get("alignment") is not None:
            # For alignment (Gwet's AC1), store the raw value in range [-1, 1]
            alignment_value = metrics["alignment"]
            metrics_for_api.append({"name": "Alignment", "value": alignment_value})
            # Added alignment to metrics
        if metrics.get("accuracy") is not None:
            metrics_for_api.append({"name": "Accuracy", "value": metrics["accuracy"] * 100})
        if metrics.get("precision") is not None:
            metrics_for_api.append({"name": "Precision", "value": metrics["precision"] * 100})
        if metrics.get("recall") is not None:
            metrics_for_api.append({"name": "Recall", "value": metrics["recall"] * 100})
        
        # Metrics prepared for API
        
        # Get first score's confusion matrix
        confusion_matrix_data = metrics.get("confusion_matrices", [{}])[0] if metrics.get("confusion_matrices") else {}
        matrix_data = {}
        if confusion_matrix_data:
            matrix_data = {
                "matrix": confusion_matrix_data.get("matrix", {}),
                "labels": list(confusion_matrix_data.get("labels", []))
            }
        
        # Calculate total items based on status
        total_predictions = 0
        if status == "COMPLETED":
            # For final update, use actual total from distribution data
            if metrics.get("predicted_distribution"):
                first_score = next(iter(metrics["predicted_distribution"]), {}).get("score")
                if first_score:
                    total_predictions = sum(item.get("count", 0) for item in metrics["predicted_distribution"] 
                                         if item.get("score") == first_score)
        else:
            # During evaluation, use the initial sample size
            total_predictions = self.number_of_texts_to_sample
        
        # Build update input with only valid fields for UpdateEvaluationInput
        # Only include the fields that are allowed by the schema
        update_input = {
            "id": self.experiment_id,
            "status": status,
            "accuracy": metrics["accuracy"] * 100,
            "processedItems": self.processed_items  # Add processed items count for progress tracking
        }
        
        # Add score ID and version ID if available
        if hasattr(self, 'score_id') and self.score_id:
            # Validate score_id format - should be a UUID with hyphens
            if not (isinstance(self.score_id, str) and '-' in self.score_id):
                self.logging.warning(f"WARNING: Score ID doesn't appear to be in DynamoDB UUID format: {self.score_id}")
                self.logging.warning(f"This will cause issues with Evaluation records. Expected format is UUID with hyphens.")
                self.logging.warning(f"Will not add this Score ID to the evaluation record update.")
            else:
                update_input["scoreId"] = self.score_id
        
        if hasattr(self, 'score_version_id') and self.score_version_id:
            update_input["scoreVersionId"] = self.score_version_id
        
        # Add metrics if valid - ensure we always have all metrics represented
        if metrics_for_api:  # Ensure the list is not empty
            # Double check that we have our alignment metric if it should be there
            has_alignment = any(m["name"] == "Alignment" for m in metrics_for_api)
            if "alignment" in metrics and not has_alignment:
                # Force add alignment if missing
                alignment_value = metrics["alignment"]
                display_value = 0 if alignment_value < 0 else alignment_value * 100
                metrics_for_api.append({"name": "Alignment", "value": display_value})
            
            # Additional validation to ensure all required metrics are included
            metric_names = [m["name"] for m in metrics_for_api]
            
            # Force append any missing metrics with default N/A value (-1 displays as N/A in UI)
            required_metrics = ["Alignment", "Accuracy", "Precision", "Recall"]
            for required_metric in required_metrics:
                if required_metric not in metric_names:
                    metrics_for_api.append({"name": required_metric, "value": -1})
            
            # Final check and sort for consistent order
            metrics_for_api.sort(key=lambda x: required_metrics.index(x["name"]) if x["name"] in required_metrics else 999)
            
            update_input["metrics"] = json.dumps(metrics_for_api)
        else:
            # Create default metrics list with all required metrics if empty
            default_metrics = [
                {"name": "Alignment", "value": metrics.get("alignment", 0)},
                {"name": "Accuracy", "value": metrics.get("accuracy", 0) * 100},
                {"name": "Precision", "value": metrics.get("precision", 0) * 100},
                {"name": "Recall", "value": metrics.get("recall", 0) * 100}
            ]
            update_input["metrics"] = json.dumps(default_metrics)
        
        # Add confusion matrix if available in metrics
        confusion_matrix_val = metrics.get("confusionMatrix")
        if confusion_matrix_val:
            try:
                update_input["confusionMatrix"] = json.dumps(confusion_matrix_val)
            except (TypeError, OverflowError) as e:
                logging.error(f"Error serializing confusion matrix: {e}")
                update_input["confusionMatrix"] = json.dumps({"error": "Serialization failed"})
        else:
            update_input["confusionMatrix"] = json.dumps(None)

        # Add class distributions if available
        predicted_dist_val = metrics.get("predictedClassDistribution")
        if predicted_dist_val:
            try:
                update_input["predictedClassDistribution"] = json.dumps(predicted_dist_val)
            except (TypeError, OverflowError) as e:
                logging.error(f"Error serializing predicted class distribution: {e}")
                update_input["predictedClassDistribution"] = json.dumps([{"error": "Serialization failed"}])
        else:
            update_input["predictedClassDistribution"] = json.dumps([])

        dataset_dist_val = metrics.get("datasetClassDistribution")
        if dataset_dist_val:
            try:
                update_input["datasetClassDistribution"] = json.dumps(dataset_dist_val)
            except (TypeError, OverflowError) as e:
                logging.error(f"Error serializing dataset class distribution: {e}")
                update_input["datasetClassDistribution"] = json.dumps([{"error": "Serialization failed"}])
        else:
            update_input["datasetClassDistribution"] = json.dumps([])
            
        # Add estimatedRemainingSeconds if appropriate
        if self.processed_items > 0 and total_predictions > self.processed_items and status != "COMPLETED":
            estimate = int(elapsed_seconds * (total_predictions - self.processed_items) / self.processed_items)
            update_input["estimatedRemainingSeconds"] = estimate
        elif status == "COMPLETED":
            update_input["estimatedRemainingSeconds"] = 0
            
        # Log the update fields we're sending (summary only for performance)
        # logging.info(f"Sending update to evaluation {self.experiment_id} with fields: {json.dumps(update_input, default=str)}") # Comment out previous log

        return {
            "input": update_input
        }

    async def score_all_texts(self, selected_sample_rows):
        """Score all texts concurrently"""
        tasks = []
        for _, row in selected_sample_rows.iterrows():
            task = asyncio.create_task(self.score_text(row))
            tasks.append(task)
        
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                logging.error(f"Error scoring text: {e}")
        
        return results

    def generate_csv_scorecard_report(self, *, results):
        report = "session_id,question_name,human_label,result_value,correct_value\n"

        for result in results:
            report += f"{result['session_id']}, {result['question_name']}, {result['human_label']}, {result['result']['value']}, ,\n"
        
        return report

    def generate_excel_report(self, report_folder_path, results, selected_sample_rows):
        records = []
        score_names = self.score_names()
        all_score_names = "_".join(score_names).replace(" ", "_")
        filename_safe_score_names = "".join(c for c in all_score_names if c.isalnum() or c in "_-")
        for result in results:
            for question in score_names:
                score_result = next((r for r in result['results'].values() if r.parameters.name == question), None)
                if score_result:  # We know if it exists, it has metadata since we cleaned up score_text
                    records.append({
                        'report_id': result['session_id'],
                        'form_id': result['form_id'],
                        'question_name': question,
                        'human_label': score_result.metadata['human_label'],
                        'human_explanation': score_result.metadata['human_explanation'],
                        'predicted_answer': score_result.value,
                        'match': score_result.metadata['correct'],
                        'explanation': score_result.metadata.get('explanation'),
                        'original_text': score_result.metadata['text'],
                    })

        df_records = pd.DataFrame(records)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_file_path = f"{report_folder_path}/Evaluation Report for {filename_safe_score_names}_{timestamp}.xlsx"
        df_records.to_excel(excel_file_path, index=False)
        
        logging.info(f"Excel report generated at {excel_file_path}")

    def generate_and_log_confusion_matrix(self, results, report_folder_path):
        for question in self.score_names():
            # Sanitize the question name for use in filename
            safe_question = question.replace('/', '_').replace('\\', '_').replace(':', '_')
            safe_question = "".join(c for c in safe_question if c.isalnum() or c in "_- ")
            
            y_true = []
            y_pred = []
            class_names = set()

            for result in results:
                score_result = next((result for result in result['results'].values() if result.parameters.name == question), None)
                if score_result:
                    true_label = score_result.metadata['human_label']
                    pred_label = str(score_result.value).lower()
                    
                    y_true.append(true_label)
                    y_pred.append(pred_label)
                    class_names.update([true_label, pred_label])

            if not class_names:
                logging.warning(f"No labels found for question '{question}'. Skipping confusion matrix generation.")
                continue

            class_names = sorted(list(class_names))
            
            if len(class_names) < 2:
                logging.warning(f"Only one unique label found for question '{question}'. Skipping confusion matrix generation.")
                continue

            cm = confusion_matrix(y_true, y_pred, labels=class_names)

            plt.figure(figsize=(10, 10))
            sns.heatmap(cm, annot=True, fmt='d', cmap='cool', 
                        xticklabels=class_names, yticklabels=class_names, square=True,
                        cbar=False)
            plt.title(f'Confusion Matrix for {question}', fontsize=12)
            plt.xlabel('Predicted', fontsize=10)
            plt.ylabel('True', fontsize=10)
            plt.tick_params(axis='both', which='major', labelsize=16)

            cm_path = f"{report_folder_path}/confusion_matrix_{safe_question}.png"
            plt.savefig(cm_path, bbox_inches='tight', dpi=600)
            plt.close()

    def create_performance_visualization(self, results, question, report_folder_path):
        # Sanitize the question name for use in filename
        safe_question = question.replace('/', '_').replace('\\', '_').replace(':', '_')
        safe_question = "".join(c for c in safe_question if c.isalnum() or c in "_- ")
        
        true_labels = []
        pred_labels = []
        for result in results:
            score_result = next((r for r in result['results'].values() if r.parameters.name == question), None)
            if score_result:
                true_labels.append(score_result.metadata['human_label'])
                pred_labels.append(str(score_result.value).lower())
        
        unique_labels = sorted(set(true_labels + pred_labels))
        
        true_counts = [true_labels.count(label) for label in unique_labels]
        pred_counts = [pred_labels.count(label) for label in unique_labels]
        
        accuracies = []
        for label in unique_labels:
            correct = sum((t == p == label) for t, p in zip(true_labels, pred_labels))
            total = true_labels.count(label)
            accuracies.append(correct / total if total > 0 else 0)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)
        
        x = np.arange(len(unique_labels))
        width = 0.35
        
        ax1.bar(x - width/2, true_counts, width, label='Ground Truth', color=(0.012, 0.635, 0.996))
        ax1.bar(x + width/2, pred_counts, width, label='Predicted', color=(0.815, 0.2, 0.51))
        ax1.set_ylabel('Count', fontsize=10)
        ax1.set_title(f'Label Distribution for {question}', fontsize=12)
        ax1.legend(fontsize=10)
        ax1.tick_params(axis='both', which='major', labelsize=8)
        
        incorrect = [1 - acc for acc in accuracies]
        ax2.bar(x, incorrect, width*2, bottom=accuracies, color='#d33', label='Incorrect')
        ax2.bar(x, accuracies, width*2, color='#393', label='Correct')
        ax2.set_ylabel('Accuracy (%)', fontsize=10)
        ax2.set_ylim(0, 1)
        ax2.set_yticklabels([f'{int(x*100)}%' for x in ax2.get_yticks()], fontsize=8)
        ax2.set_xlabel('Labels (Based on Ground Truth)', fontsize=10)
        ax2.set_title(f'Accuracy by Label for {question}', fontsize=12)
        ax2.legend(fontsize=10)
        ax2.tick_params(axis='both', which='major', labelsize=8)
        
        plt.xticks(x, unique_labels, rotation=45, ha='right', fontsize=16)
        plt.tight_layout()
        
        # Use the sanitized question name in the file path
        plt.savefig(f"{report_folder_path}/performance_{safe_question}.png", bbox_inches='tight', dpi=600)
        plt.close()
        
    def generate_metrics_json(self, report_folder_path, sample_size, expenses, calibration_report=None):
        overall_accuracy = None if self.total_questions == 0 else (self.total_correct / self.total_questions) * 100
        
        if sample_size < 120:
            accuracy_format = "{:.0f}"
        elif sample_size < 10000:
            accuracy_format = "{:.1f}"
        else:
            accuracy_format = "{:.2f}"
        
        metrics = {
            "overall_accuracy": accuracy_format.format(overall_accuracy) if overall_accuracy is not None else 0,
            "number_correct": self.total_correct,
            "total_questions": self.total_questions,
            "total_skipped": self.total_skipped,
            "number_of_samples": sample_size,
            "cost_per_call": f"{expenses['cost_per_text']:.7f}".rstrip('0').rstrip('.'),
            "total_cost": f"{expenses['total_cost']:.7f}".rstrip('0').rstrip('.')
        }

        # Add calibration report if available
        if calibration_report is not None:
            metrics["confidence_calibration"] = calibration_report

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_filename = f"metrics_{timestamp}.json"
        metrics_file_path = f"{report_folder_path}/{metrics_filename}"
        with open(metrics_file_path, 'w') as f:
            json.dump(metrics, f, indent=2)

        logging.info(f"Metrics JSON file generated at {metrics_file_path}")

    def _format_confusion_matrix_for_summary(self, final_metrics):
        """Format confusion matrix for the concise evaluation summary."""
        confusion_matrix = final_metrics.get('confusionMatrix')
        predicted_dist = final_metrics.get('predictedClassDistribution', {})
        dataset_dist = final_metrics.get('datasetClassDistribution', {})
        
        if not confusion_matrix:
            return ""
        
        summary_lines = []
        
        # Handle different confusion matrix formats (similar to evaluations.py)
        matrix_dict = {}
        all_classes = set()
        
        if isinstance(confusion_matrix, dict):
            if 'matrix' in confusion_matrix and 'labels' in confusion_matrix:
                # Format: {'matrix': [[7, 0], [2, 10]], 'labels': ['no', 'yes']}
                matrix_2d = confusion_matrix['matrix']
                labels = confusion_matrix['labels']
                
                if isinstance(matrix_2d, list) and isinstance(labels, list):
                    all_classes = set(labels)
                    matrix_dict = {}
                    for i, actual_class in enumerate(labels):
                        matrix_dict[actual_class] = {}
                        for j, pred_class in enumerate(labels):
                            if i < len(matrix_2d) and j < len(matrix_2d[i]):
                                matrix_dict[actual_class][pred_class] = matrix_2d[i][j]
                            else:
                                matrix_dict[actual_class][pred_class] = 0
            else:
                # Standard nested dict format
                matrix_dict = confusion_matrix
                for actual, predicted_dict in confusion_matrix.items():
                    all_classes.add(actual)
                    if isinstance(predicted_dict, dict):
                        all_classes.update(predicted_dict.keys())
        
        if not matrix_dict or not all_classes:
            return ""
        
        all_classes = sorted(list(all_classes))
        
        # Create concise confusion matrix
        summary_lines.append("CONFUSION MATRIX:")
        summary_lines.append("                    Predicted")
        header = "              "
        for pred_class in all_classes:
            header += f"{pred_class}".rjust(8)
        summary_lines.append(header)
        summary_lines.append("Actual      " + "-" * (8 * len(all_classes)))
        
        for actual_class in all_classes:
            row = f"{actual_class}".ljust(10) + " | "
            for pred_class in all_classes:
                count = matrix_dict.get(actual_class, {}).get(pred_class, 0)
                row += f"{count}".rjust(8)
            summary_lines.append(row)
        
        # Add key insights
        summary_lines.append("")
        summary_lines.append("Key Insights:")
        
        # Find most common errors
        errors = []
        for actual_class in all_classes:
            for pred_class in all_classes:
                if actual_class != pred_class:
                    count = matrix_dict.get(actual_class, {}).get(pred_class, 0)
                    if count > 0:
                        errors.append((count, actual_class, pred_class))
        
        errors.sort(reverse=True)  # Sort by count, highest first
        
        if errors:
            summary_lines.append(f"• Most common error: {errors[0][1]} → {errors[0][2]} ({errors[0][0]} cases)")
            if len(errors) > 1:
                summary_lines.append(f"• Second most common: {errors[1][1]} → {errors[1][2]} ({errors[1][0]} cases)")
        
        # Add per-class accuracy
        for cls in all_classes:
            tp = matrix_dict.get(cls, {}).get(cls, 0)
            total_actual = sum(matrix_dict.get(cls, {}).get(pred_cls, 0) for pred_cls in all_classes)
            if total_actual > 0:
                class_accuracy = tp / total_actual
                summary_lines.append(f"• '{cls}' accuracy: {class_accuracy:.1%} ({tp}/{total_actual})")
        
        return "\n".join(summary_lines)

    def _build_confusion_metrics_from_results(self):
        """Build confusion matrix metrics from the evaluation results."""
        if not hasattr(self, 'all_results') or not self.all_results:
            return {}
        
        # For now, focus on the first score (primary score)
        score_names = self.score_names()
        if not score_names:
            return {}
        
        primary_score_name = score_names[0]
        
        # Collect actual and predicted labels
        y_true = []
        y_pred = []
        
        for result in self.all_results:
            score_result = next((r for r in result['results'].values() if r.parameters.name == primary_score_name), None)
            if score_result:
                true_label = score_result.metadata['human_label']
                pred_label = str(score_result.value).lower()
                y_true.append(true_label)
                y_pred.append(pred_label)
        
        if not y_true or not y_pred:
            return {}
        
        # Get unique classes
        all_classes = sorted(list(set(y_true + y_pred)))
        
        # Build confusion matrix in the format expected by the summary formatter
        matrix_dict = {}
        for actual_class in all_classes:
            matrix_dict[actual_class] = {}
            for pred_class in all_classes:
                matrix_dict[actual_class][pred_class] = 0
        
        # Fill in the counts
        for actual, pred in zip(y_true, y_pred):
            matrix_dict[actual][pred] += 1
        
        # Build class distributions
        from collections import Counter
        dataset_dist = dict(Counter(y_true))
        predicted_dist = dict(Counter(y_pred))
        
        return {
            'confusionMatrix': {
                'matrix': [[matrix_dict[actual].get(pred, 0) for pred in all_classes] for actual in all_classes],
                'labels': all_classes
            },
            'datasetClassDistribution': dataset_dist,
            'predictedClassDistribution': predicted_dist
        }

    def generate_report(self, score_instance, overall_accuracy, expenses, sample_size, final_metrics=None):
        score_config = score_instance.parameters

        report = f"""
Evaluation Report:
------------------

Prompts:
{yaml.dump(score_config.graph, default_flow_style=False) if hasattr(score_config, 'graph') else 'N/A (non-LangGraph score)'}

Mismatches (up to {self.max_mismatches_to_report}):
"""
        for mismatch in self.mismatches:
            report += f"""
Form ID:      {mismatch['form_id']}
Question:     {mismatch['question']}

Predicted:    {mismatch['predicted']}
Ground Truth: {mismatch['ground_truth']}
QA Reasoning for Ground Truth: {mismatch['human_explanation']}

Explanation:
{mismatch['explanation']}

Transcript:
{mismatch['transcript']}

---
"""
        # Add confusion matrix summary if available
        confusion_summary = ""
        if final_metrics and final_metrics.get('confusionMatrix'):
            confusion_summary = self._format_confusion_matrix_for_summary(final_metrics)
        
        report += f"""

Overall Accuracy: {overall_accuracy:.1f}% ({self.total_correct} / {self.total_questions})
Sample Size:      {sample_size}
Skipped Results:  {self.total_skipped} (due to unmet dependency conditions)
Cost per call:    ${expenses['cost_per_text']:.6f}
Total cost:       ${expenses['total_cost']:.6f}

{confusion_summary}
"""            

        return report

    async def score_text(self, row, score_name: str = None):
        """Score text with retry logic for handling timeouts and request exceptions"""
        max_attempts = 5
        base_delay = 4
        max_delay = 10
        
        for attempt in range(max_attempts):
            try:
                text = row['text']
                content_id = row.get('content_id', '')
                session_id = row.get('Session ID', content_id)
                columns = row.get('columns', {})
                form_id = columns.get('form_id', '')
                metadata_string = columns.get('metadata', {})
                
                # Get feedback_item_id from the dataset if available
                feedback_item_id = row.get('feedback_item_id', None)
                
                # Extract feedback_item_id if available
                
                # Initialize human_labels dictionary
                human_labels = {}
                
                if isinstance(metadata_string, dict):
                    metadata = metadata_string
                else:
                    try:
                        metadata = json.loads(metadata_string)
                    except json.JSONDecodeError:
                        logging.warning(f"Failed to parse metadata as JSON. Using empty dict. Metadata: {metadata_string}")
                        metadata = {}

                # Processing text

                # If score_name is provided, only process that score
                score_names_to_process = [score_name] if score_name else self.score_names_to_process()
                
                # Check if we need to generate visualization for any LangGraphScores
                if hasattr(self, 'visualize') and self.visualize:
                    for score_to_process in score_names_to_process:
                        # Find score config in the scores list
                        score_config = next(
                            (score for score in self.scorecard.properties['scores'] 
                             if score.get('name') == score_to_process),
                            {}
                        )
                        if score_config.get('class') == 'LangGraphScore':
                            try:
                                score_instance = self.get_score_instance(score_to_process)
                                if isinstance(score_instance, LangGraphScore):
                                    await score_instance.async_setup()  # Ensure the graph is built
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    output_path = os.path.join('tmp', f'graph_{score_to_process}_{timestamp}.png')
                                    score_instance.generate_graph_visualization(output_path)
                                    # Generated graph visualization
                            except ValueError as e:
                                # Skip visualization if score instance not found
                                pass
                
                scorecard_results = await self.scorecard.score_entire_text(
                    text=text,
                    metadata=metadata,
                    subset_of_score_names=score_names_to_process
                )

                # Create a new dictionary for filtered results
                filtered_results = {}

                result = {
                    'content_id': content_id,
                    'session_id': session_id,
                    'form_id': form_id,
                    'results': filtered_results,  # Use the filtered results dictionary
                    'human_labels': human_labels
                }
                
                # Preserve all original dataframe columns for identifier extraction
                # This ensures FeedbackItems IDs column and other dataset-specific columns are available
                for col_name in row.index:
                    if col_name not in result:  # Don't overwrite the explicitly set keys above
                        result[col_name] = row[col_name]

                # Track if we've processed any scores for this text
                has_processed_scores = False

                # Get the primary score name if we're evaluating a specific score
                primary_score_name = score_name if score_name else (
                    self.subset_of_score_names[0] if self.subset_of_score_names and len(self.subset_of_score_names) == 1 
                    else None
                )

                for score_identifier in scorecard_results.keys():
                    try:
                        score_result = scorecard_results[score_identifier]
                        
                        # --- Refactor: Get score config directly from loaded scorecard --- 
                        score_config = None
                        current_score_name = getattr(score_result.parameters, 'name', score_identifier)
                        for config in self.scorecard.scores:
                            if config.get('name') == current_score_name or config.get('id') == score_identifier:
                                score_config = config
                                break
                        
                        if not score_config:
                            logging.warning(f"Score configuration not found: {current_score_name}")
                            continue
                            
                        # Determine label score name from config or default to current score name
                        label_score_name = score_config.get('label_score_name', current_score_name)
                        score_name = current_score_name # Use the name from the result parameters
                        # --- End Refactor ---

                        # Skip if this is a dependency score and not our primary score
                        if primary_score_name and score_name != primary_score_name:
                            continue
                        
                        # Handle skipped scores - don't try to process them for evaluation
                        if isinstance(score_result.value, str) and score_result.value.upper() == "SKIPPED":
                            logging.info(f"Score '{score_name}' was skipped due to unmet dependency conditions for content_id {content_id}")
                            self.total_skipped += 1
                            continue

                        # First check for override
                        human_label = None
                        label_found = False
                        
                        if form_id in self.override_data and score_name in self.override_data[form_id]:
                            human_label = self.override_data[form_id][score_name]
                            label_found = True
                            logging.info(f"Using override for form {form_id}, score {score_name}: {human_label}")
                        else:
                            # Fall back to row data if no override exists
                            label_column = label_score_name + '_label'
                            if label_column in row.index:
                                human_label = row[label_column]
                                label_found = True
                            elif label_score_name in row.index:
                                human_label = row[label_score_name]
                                label_found = True
                            else:
                                # Check if we're allowing evaluations without labels
                                if not getattr(self, 'allow_no_labels', False):
                                    logging.warning(f"Label column not found for score: {score_identifier}")
                                    continue
                                else:
                                    # No label found, but that's okay - we're in label-optional mode
                                    logging.debug(f"No label found for score: {score_identifier}, continuing in label-optional mode")
                                    human_label = None
                                    label_found = False

                        # Process label if found
                        if label_found and human_label is not None:
                            human_label = str(human_label).lower().rstrip('.!?')
                            if human_label == 'nan':
                                human_label = ''
                            if human_label == 'n/a':
                                human_label = 'na'
                        else:
                            human_label = ''  # Empty string for no label

                        human_explanation = columns.get(f"{label_score_name} comment", 'None')

                        score_result_value = ' '.join(str(score_result.value).lower().strip().split())

                        if form_id in self.override_data:
                            for override_question_name, correct_value in self.override_data[form_id].items():
                                if str(override_question_name) in human_labels:
                                    # Override applied
                                    human_labels[str(override_question_name)] = correct_value

                        score_result.metadata['human_label'] = human_label
                        score_result.metadata['human_explanation'] = human_explanation
                        # Only calculate correctness if we have a label
                        if label_found and human_label:
                            score_result.metadata['correct'] = score_result_value.strip() == human_label.strip()
                        else:
                            score_result.metadata['correct'] = None  # No label to compare against
                        score_result.metadata['text'] = text

                        # Add to filtered results only if we get here (i.e., all conditions are met)
                        filtered_results[score_identifier] = score_result
                        has_processed_scores = True

                        # Create ScoreResult in a non-blocking way only for the primary score
                        logging.info(f"DEBUG: About to check ScoreResult creation conditions - dry_run={getattr(self, 'dry_run', False)}, dashboard_client={self.dashboard_client is not None}, experiment_id={self.experiment_id}")
                        if getattr(self, 'dry_run', False):
                            pass  # Skip ScoreResult creation in dry run
                        elif self.dashboard_client and self.experiment_id:
                            try:
                                self.scoreresult_creation_attempts = getattr(self, 'scoreresult_creation_attempts', 0) + 1
                                await self._create_score_result(
                                    score_result=score_result,
                                    content_id=content_id,
                                    result=result,
                                    feedback_item_id=feedback_item_id
                                )
                                self.scoreresult_creation_successes = getattr(self, 'scoreresult_creation_successes', 0) + 1
                            except Exception as score_result_error:
                                self.scoreresult_creation_failures = getattr(self, 'scoreresult_creation_failures', 0) + 1
                                self.logging.error(f"Failed to create ScoreResult: {str(score_result_error)}")
                                # Don't re-raise - continue with evaluation but log the failure

                    except Exception as e:
                        # Enhanced error logging for score processing
                        error_info = {
                            'score_identifier': score_identifier,
                            'content_id': content_id,
                            'error_type': type(e).__name__,
                            'error_message': str(e),
                            'text_preview': text[:200] + '...' if len(text) > 200 else text
                        }
                        
                        logging.error(f"Error processing {score_identifier}: {e}")
                        logging.error(f"Detailed error info: {json.dumps(error_info, indent=2)}")
                        
                        # Specific handling for NoneType iteration errors
                        if 'NoneType' in str(e) and 'iterable' in str(e):
                            logging.error(f"NoneType iteration error in score '{score_identifier}'")
                            logging.error("This usually indicates None values in score configuration or workflow state")
                            logging.error("Common causes: missing parameters, None metadata values, or None results")
                        
                        logging.exception(f"Full traceback for {score_identifier}:")
                        
                        # Ensure parameters uses the correct scorecard name string
                        score_result = Score.Result(
                            value="ERROR", 
                            error=str(e),
                            parameters=Score.Parameters(
                                name=score_identifier,
                                scorecard=self.scorecard_name # Use string name here too
                            )
                        )
                        # Add the error result to filtered_results so it's logged/counted
                        filtered_results[score_identifier] = score_result

                # Remove the result accumulation from here since it's now handled in _run_evaluation / score_all_texts_for_score
                # We still need to track overall progress if only one score is being evaluated
                if has_processed_scores and score_name: # Check if we are processing a specific score
                    self.processed_items_by_score[score_name] = self.processed_items_by_score.get(score_name, 0) + 1
                    self.processed_items = sum(self.processed_items_by_score.values())

                return result # Return the processed result dict

            except (Timeout, RequestException) as e:
                if attempt == max_attempts - 1:  # Last attempt
                    logging.error(f"Max attempts reached for content_id {row.get('content_id')}. Error: {e}")
                    # Return an error result instead of raising
                    return {
                        'content_id': row.get('content_id', ''),
                        'session_id': row.get('Session ID', row.get('content_id', '')),
                        'form_id': row.get('columns', {}).get('form_id', ''),
                        'results': {
                             score_name or 'processing_error': Score.Result(
                                 value="Error",
                                 error=f"Timeout/RequestException after {max_attempts} attempts: {e}",
                                 parameters=Score.Parameters(name=score_name or 'processing_error', scorecard=self.scorecard_name)
                            )
                        },
                        'human_labels': {}
                    }
                
                # Calculate exponential backoff delay
                delay = min(base_delay * (2 ** attempt), max_delay)
                logging.info(f"Attempt {attempt + 1} failed for content_id {row.get('content_id')} with error: {e}. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)

        # If loop completes without returning (e.g., all attempts failed but didn't hit max_attempts check correctly)
        logging.error(f"Scoring loop completed for content_id {row.get('content_id')} without returning a result or error after {max_attempts} attempts.")
        return {
            'content_id': row.get('content_id', ''),
            'session_id': row.get('Session ID', row.get('content_id', '')),
            'form_id': row.get('columns', {}).get('form_id', ''),
            'results': {
                score_name or 'processing_error': Score.Result(
                    value="Error",
                    error=f"Scoring failed after {max_attempts} attempts.",
                    parameters=Score.Parameters(name=score_name or 'processing_error', scorecard=self.scorecard_name)
                )
            },
            'human_labels': {}
        }

    async def _create_score_result(self, *, score_result, content_id, result, feedback_item_id=None):
        """Create a score result in the dashboard."""
        logging.info(f"DEBUG: _create_score_result called for content_id={content_id}")
        try:
            # Validate required attributes are available
            if not hasattr(self, 'experiment_id') or not self.experiment_id:
                raise ValueError("experiment_id is not set")
            if not hasattr(self, 'account_id') or not self.account_id:
                raise ValueError("account_id is not set")
            if not hasattr(self, 'scorecard_id') or not self.scorecard_id:
                raise ValueError("scorecard_id is not set")

            # Ensure we have a valid string value
            value = str(score_result.value) if score_result.value is not None else "N/A"
            
            # Extract feedback_item_id if available
            feedback_item_id = score_result.metadata.get('feedback_item_id') if score_result.metadata else None
            
            # Ensure we have valid metadata
            metadata_dict = {
                'item_id': result.get('form_id', ''),
                'results': {
                    score_result.parameters.name: {
                        'value': value,
                        'confidence': score_result.confidence,
                        'explanation': score_result.metadata.get('explanation', ''),
                        'metadata': {
                            'human_label': score_result.metadata.get('human_label', ''),
                            'correct': score_result.metadata.get('correct', False),
                            'human_explanation': score_result.metadata.get('human_explanation', ''),
                            'text': score_result.metadata.get('text', '')
                        }
                    }
                }
            }
            
            # Add feedback_item_id to metadata if available
            if feedback_item_id:
                metadata_dict['feedback_item_id'] = feedback_item_id
            
            # The Item should already exist from dataset creation - evaluations don't create Items
            # Use content_id as the itemId since Items are created by the data loading process
            
            # Create data dictionary with all required fields
            # MARKER: CODE VERSION 2025-10-17-v3 - This ensures we're using the updated code
            data = {
                'evaluationId': self.experiment_id,
                'itemId': content_id,  # Use content_id directly
                'accountId': self.account_id,
                'scorecardId': self.scorecard_id,
                'metadata': json.dumps(metadata_dict),  # Add the metadata that was created earlier
                'value': value,  # Add the score result value
                'confidence': score_result.confidence,  # Add confidence from Score.Result
                'explanation': score_result.explanation,  # Add explanation from Score.Result
                'code': '200',  # Add success code
                'status': 'COMPLETED',  # Add status
                'type': 'evaluation',  # Add type field required by byTypeStatusUpdated GSI
            }
            logging.info(f"🔧 CODE VERSION 2025-10-17-v3 ACTIVE - Creating ScoreResult with type='{data.get('type')}' and status='{data.get('status')}'")
            logging.info(f"🔧 Full data dict keys: {list(data.keys())}")
            
            # Add scoreId - try multiple sources
            score_id = None
            if hasattr(score_result, 'parameters') and hasattr(score_result.parameters, 'id'):
                score_id = score_result.parameters.id
            elif hasattr(self, 'score_id') and self.score_id is not None:
                score_id = self.score_id
            else:
                self.logging.warning("No score ID found")
            
            if score_id is not None:
                data['scoreId'] = score_id
            else:
                logging.error("score_id is None, not adding to data")
            
            # Add feedback item ID if provided from the dataset
            if feedback_item_id:
                data['feedbackItemId'] = feedback_item_id

            # Add feedbackItemId as a direct field if available
            if feedback_item_id:
                data['feedbackItemId'] = feedback_item_id

            # Add trace data if available           
            if score_result.metadata and 'trace' in score_result.metadata:
                data['trace'] = json.dumps(score_result.metadata['trace'])

            # Prepare data for GraphQL mutation

            # Validate feedback_item_id if present
            feedback_item_id = score_result.metadata.get('feedback_item_id') if score_result.metadata else None

            # Debug logging to see what's actually in the data dict
            logging.info(f"DEBUG: ScoreResult data keys: {list(data.keys())}")
            logging.info(f"DEBUG: type={data.get('type')}, status={data.get('status')}, updatedAt={data.get('updatedAt')}")

            # Validate all required fields are present and not None
            required_fields = ['evaluationId', 'itemId', 'accountId', 'scorecardId', 'scoreId', 'value', 'metadata', 'code', 'status']
            missing_fields = [field for field in required_fields if field not in data or data[field] is None]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            mutation = """
            mutation CreateScoreResult($input: CreateScoreResultInput!) {
                createScoreResult(input: $input) {
                    id
                    evaluationId
                    itemId
                    accountId
                    scorecardId
                    scoreId
                    value
                    confidence
                    explanation
                    metadata
                    trace
                    code
                    type
                    feedbackItemId
                    status
                }
            }
            """
            
            variables = {
                "input": data
            }

            # DEBUG: Log the data being sent to GraphQL
            logging.info(f"🚀 CREATING SCORERESULT WITH DATA:")
            logging.info(f"   value = {data.get('value')!r}")
            logging.info(f"   confidence = {data.get('confidence')!r}")
            logging.info(f"   explanation = {data.get('explanation')!r}")
            logging.info(f"   evaluationId = {data.get('evaluationId')!r}")

            # Execute the API call in a non-blocking way
            response = await asyncio.to_thread(self.dashboard_client.execute, mutation, variables)
            
            # Check for GraphQL errors in the response
            if 'errors' in response:
                error_messages = [error.get('message', 'Unknown error') for error in response.get('errors', [])]
                error_str = '; '.join(error_messages)
                self.logging.error(f"GraphQL errors creating score result: {error_str}")
                raise Exception(f"Failed to create score result: {error_str}")
            
            if not response.get('createScoreResult'):
                raise Exception("Failed to create score result - no data returned")

            # DEBUG: Log the response from GraphQL
            created_result = response.get('createScoreResult', {})
            logging.info(f"✅ SCORERESULT CREATED SUCCESSFULLY:")
            logging.info(f"   id = {created_result.get('id')!r}")
            logging.info(f"   confidence = {created_result.get('confidence')!r}")
            logging.info(f"   explanation = {created_result.get('explanation')!r}")
            logging.info(f"   value = {created_result.get('value')!r}")
            
        except Exception as e:
            self.logging.error(f"ScoreResult creation failed: {str(e)}")
            raise

    # REMOVED: _create_or_upsert_item method
    # Items should already exist from dataset creation (FeedbackItems, CallCriteriaDBCache)
    # Evaluations should not be creating Items - that's duplication of functionality

    # REMOVED: _extract_identifiers_from_dataset_row method
    # This was only used for Item creation, which evaluations shouldn't be doing

    # DEPRECATED: This method is no longer used. feedback_item_id now comes directly from the dataset.
    async def _find_feedback_item(self, *, content_id: str, score_name: str) -> str | None:
        """Find the feedback item associated with this content_id and score."""
        try:
            # Query for feedback items that match the item and score
            query = """
            query FindFeedbackItem($accountId: String!, $scorecardId: String!, $scoreId: String!, $itemId: String!) {
                listFeedbackItems(
                    filter: {
                        accountId: { eq: $accountId }
                        scorecardId: { eq: $scorecardId }
                        scoreId: { eq: $scoreId }
                        itemId: { eq: $itemId }
                    }
                    limit: 1
                ) {
                    items {
                        id
                        editCommentValue
                    }
                }
            }
            """
            
            variables = {
                "accountId": self.account_id,
                "scorecardId": self.scorecard_id,
                "scoreId": self.score_id,
                "itemId": content_id
            }
            
            response = await asyncio.to_thread(self.dashboard_client.execute, query, variables)
            
            if response.get('listFeedbackItems', {}).get('items'):
                feedback_item = response['listFeedbackItems']['items'][0]
                logging.info(f"Found feedback item for content_id {content_id}: {feedback_item['id']}")
                return feedback_item['id']
            else:
                # No feedback item found
                return None
                
        except Exception as e:
            logging.warning(f"Error finding feedback item for content_id {content_id}: {e}")
            return None

    async def cleanup(self):
        """Clean up all resources"""
        try:
            # Stop the metrics computation task
            self.should_stop = True
            if hasattr(self, 'metrics_tasks') and self.metrics_tasks:
                self.logging.info("Cleaning up metrics tasks...")
                for task in self.metrics_tasks.values():
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass  # Expected during cleanup
                        except Exception as e:
                            self.logging.error(f"Error cleaning up metrics task: {e}")
            
            # Clean up scorecard
            if hasattr(self, 'scorecard'):
                if isinstance(self.scorecard, LangGraphScore):
                    await self.scorecard.cleanup()
                elif hasattr(self.scorecard, 'cleanup'):
                    await self.scorecard.cleanup()
            
            # Wait for any remaining tasks
            tasks = [task for task in asyncio.all_tasks() 
                    if task != asyncio.current_task()]
            if tasks:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                try:
                    await asyncio.wait(tasks, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

        except Exception as e:
            self.logging.error(f"Error during {self.__class__.__name__} cleanup: {e}")
            # Cleanup completed with errors

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__aexit__(exc_type, exc_val, exc_tb))

    @staticmethod
    def get_evaluation_info(evaluation_id: str, include_score_results: bool = False) -> dict:
        """
        Get detailed information about an evaluation by its ID.
        
        Args:
            evaluation_id: The ID of the evaluation to look up
            include_score_results: Whether to include score results in the response
            
        Returns:
            dict: Evaluation information including scorecard name, score name, and metrics
        """
        from plexus.dashboard.api.client import PlexusDashboardClient
        from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation
        from plexus.dashboard.api.models.scorecard import Scorecard as DashboardScorecard
        from plexus.dashboard.api.models.score import Score as DashboardScore
        import json
        
        try:
            client = PlexusDashboardClient()
            
            # Get the evaluation
            evaluation = DashboardEvaluation.get_by_id(evaluation_id, client, include_score_results=include_score_results)
            
            # Get scorecard name if scorecard ID is available
            scorecard_name = None
            if evaluation.scorecardId:
                try:
                    scorecard = DashboardScorecard.get_by_id(evaluation.scorecardId, client)
                    scorecard_name = scorecard.name
                except Exception as e:
                    logging.warning(f"Could not fetch scorecard name for ID {evaluation.scorecardId}: {e}")
                    scorecard_name = evaluation.scorecardId
            
            # Get score name if score ID is available
            score_name = None
            if evaluation.scoreId:
                try:
                    score = DashboardScore.get_by_id(evaluation.scoreId, client)
                    score_name = score.name
                except Exception as e:
                    logging.warning(f"Could not fetch score name for ID {evaluation.scoreId}: {e}")
                    score_name = evaluation.scoreId
            
            # Parse metrics if available
            metrics = None
            if evaluation.metrics:
                try:
                    if isinstance(evaluation.metrics, str):
                        metrics = json.loads(evaluation.metrics)
                    else:
                        metrics = evaluation.metrics
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Could not parse metrics: {e}")
                    metrics = evaluation.metrics
            
            # Parse parameters if available
            parameters = None
            if evaluation.parameters:
                try:
                    if isinstance(evaluation.parameters, str):
                        parameters = json.loads(evaluation.parameters)
                    else:
                        parameters = evaluation.parameters
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Could not parse parameters: {e}")
                    parameters = evaluation.parameters
            
            # Parse confusion matrix if available
            confusion_matrix = None
            if evaluation.confusionMatrix:
                try:
                    if isinstance(evaluation.confusionMatrix, str):
                        confusion_matrix = json.loads(evaluation.confusionMatrix)
                    else:
                        confusion_matrix = evaluation.confusionMatrix
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Could not parse confusion matrix: {e}")
                    confusion_matrix = evaluation.confusionMatrix
            
            # Parse class distributions if available
            predicted_class_distribution = None
            if evaluation.predictedClassDistribution:
                try:
                    if isinstance(evaluation.predictedClassDistribution, str):
                        predicted_class_distribution = json.loads(evaluation.predictedClassDistribution)
                    else:
                        predicted_class_distribution = evaluation.predictedClassDistribution
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Could not parse predicted class distribution: {e}")
                    predicted_class_distribution = evaluation.predictedClassDistribution
            
            dataset_class_distribution = None
            if evaluation.datasetClassDistribution:
                try:
                    if isinstance(evaluation.datasetClassDistribution, str):
                        dataset_class_distribution = json.loads(evaluation.datasetClassDistribution)
                    else:
                        dataset_class_distribution = evaluation.datasetClassDistribution
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Could not parse dataset class distribution: {e}")
                    dataset_class_distribution = evaluation.datasetClassDistribution
            
            result = {
                'id': evaluation.id,
                'type': evaluation.type,
                'status': evaluation.status,
                'scorecard_name': scorecard_name,
                'scorecard_id': evaluation.scorecardId,
                'score_name': score_name,
                'score_id': evaluation.scoreId,
                'accuracy': evaluation.accuracy,
                'metrics': metrics,
                'parameters': parameters,
                'confusion_matrix': confusion_matrix,
                'predicted_class_distribution': predicted_class_distribution,
                'dataset_class_distribution': dataset_class_distribution,
                'total_items': evaluation.totalItems,
                'processed_items': evaluation.processedItems,
                'cost': evaluation.cost,
                'elapsed_seconds': evaluation.elapsedSeconds,
                'estimated_remaining_seconds': evaluation.estimatedRemainingSeconds,
                'started_at': evaluation.startedAt.isoformat() if evaluation.startedAt else None,
                'created_at': evaluation.createdAt.isoformat() if evaluation.createdAt else None,
                'updated_at': evaluation.updatedAt.isoformat() if evaluation.updatedAt else None,
                'error_message': evaluation.errorMessage,
                'error_details': evaluation.errorDetails,
                'task_id': evaluation.taskId
            }
            
            if include_score_results:
                # Score results would be available in the evaluation object if requested
                # For now, we'll indicate that this feature could be added
                result['score_results_available'] = True
            
            return result
            
        except Exception as e:
            logging.error(f"Error getting evaluation info for ID {evaluation_id}: {str(e)}")
            raise ValueError(f"Could not get evaluation info: {str(e)}")
    
    @staticmethod  
    def get_latest_evaluation(account_key: str = None, evaluation_type: str = None) -> dict:
        """
        Get information about the most recent evaluation.
        
        Args:
            account_key: Account key to filter by (default: from PLEXUS_ACCOUNT_KEY env var)
            evaluation_type: Optional filter by evaluation type (e.g., 'accuracy')
            
        Returns:
            dict: Latest evaluation information
        """
        import os
        from plexus.dashboard.api.client import PlexusDashboardClient
        from plexus.dashboard.api.models.account import Account
        
        try:
            # Use PLEXUS_ACCOUNT_KEY environment variable if no account_key provided
            if account_key is None:
                account_key = os.getenv('PLEXUS_ACCOUNT_KEY', 'call-criteria')
            
            client = PlexusDashboardClient()
            
            # Get the account
            account = Account.list_by_key(key=account_key, client=client)
            if not account:
                raise ValueError(f"No account found with key: {account_key}")
            
            # Use the proper GraphQL query with sorting by updatedAt
            query = """
            query ListEvaluationByAccountIdAndUpdatedAt($accountId: String!, $sortDirection: ModelSortDirection, $limit: Int) {
                listEvaluationByAccountIdAndUpdatedAt(accountId: $accountId, sortDirection: $sortDirection, limit: $limit) {
                    items {
                        id
                        type
                        accountId
                        status
                        createdAt
                        updatedAt
                        parameters
                        metrics
                        inferences
                        accuracy
                        cost
                        startedAt
                        elapsedSeconds
                        estimatedRemainingSeconds
                        totalItems
                        processedItems
                        errorMessage
                        errorDetails
                        scorecardId
                        scoreId
                        confusionMatrix
                        scoreGoal
                        datasetClassDistribution
                        isDatasetClassDistributionBalanced
                        predictedClassDistribution
                        isPredictedClassDistributionBalanced
                        taskId
                    }
                }
            }
            """
            
            variables = {
                'accountId': account.id,
                'sortDirection': 'DESC',
                'limit': 1  # Get just the most recent
            }
            
            # Add type filter if provided
            if evaluation_type:
                # If type filtering is needed, we'll need to get more results and filter client-side
                # since the specialized query doesn't support type filtering
                variables['limit'] = 10
            
            result = client.execute(query, variables)
            
            if not result or 'listEvaluationByAccountIdAndUpdatedAt' not in result or not result['listEvaluationByAccountIdAndUpdatedAt']['items']:
                return None
            
            evaluations = result['listEvaluationByAccountIdAndUpdatedAt']['items']
            
            # Filter by type if specified
            if evaluation_type:
                evaluations = [e for e in evaluations if e.get('type') == evaluation_type]
                if not evaluations:
                    return None
            
            latest_evaluation_data = evaluations[0]
            
            # Use the existing get_evaluation_info method to get full details
            return Evaluation.get_evaluation_info(latest_evaluation_data['id'])
            
        except Exception as e:
            logging.error(f"Error getting latest evaluation: {str(e)}")
            raise ValueError(f"Could not get latest evaluation: {str(e)}")

class ConsistencyEvaluation(Evaluation):
    def __init__(self, *, number_of_times_to_sample_each_text, **kwargs):
        super().__init__(**kwargs)
        self.number_of_times_to_sample_each_text = number_of_times_to_sample_each_text
    
    def log_parameters(self):
        super().log_parameters()

class AccuracyEvaluation(Evaluation):
    def __init__(self, *, override_folder: Optional[str] = None, labeled_samples: list = None, labeled_samples_filename: str = None, score_id: str = None, score_version_id: str = None, visualize: bool = False, task_id: str = None, evaluation_id: str = None, account_id: str = None, scorecard_id: str = None, **kwargs):
        # Store scorecard_id before calling super().__init__
        self.scorecard_id = scorecard_id
        super().__init__(**kwargs)
        self.override_folder = override_folder
        self.labeled_samples = labeled_samples
        self.labeled_samples_filename = labeled_samples_filename
        self.score_id = score_id
        
        self.score_version_id = score_version_id  # Store score version ID
        self.visualize = visualize
        self.task_id = task_id  # Store task ID
        self.evaluation_id = evaluation_id  # Store evaluation ID
        self.account_id = account_id  # Store account ID
        # Don't overwrite scorecard_id here since it's already set
        self.results_queue = Queue()
        self.metrics_tasks = {}  # Dictionary to track metrics tasks per score
        self.should_stop = False
        self.completed_scores = set()  # Track which scores have completed all their results
        self.override_data = {}  # Initialize empty override data dictionary
        self.logger = logging.getLogger('plexus/evaluation')  # Add dedicated logger
        
        # Load override data from CSV files
        self._load_override_data_from_csv()

    def _load_override_data_from_csv(self):
        """Load override data from CSV files using the scorecard's configuration."""
        try:
            # Look for scores that have column mappings defined in their data configuration
            for score_config in self.scorecard.scores:
                score_name = score_config.get('name')
                if not score_name:
                    continue
                
                # Check if this score has data configuration with column mappings
                data_config = score_config.get('data', {})
                if not data_config:
                    continue
                
                # Look for searches with column mappings
                searches = data_config.get('searches', [])
                for search in searches:
                    item_list_filename = search.get('item_list_filename')
                    column_mappings = search.get('column_mappings', [])
                    
                    if not item_list_filename or not column_mappings:
                        continue
                    
                    try:
                        # Load the CSV file
                        df = pd.read_csv(item_list_filename)
                        
                        # Find form_id column
                        form_id_col = None
                        for col in df.columns:
                            if col.lower() in ['form_id', 'f_id']:
                                form_id_col = col
                                break
                        
                        if form_id_col is None:
                            self.logging.warning(f"No form_id column found in {item_list_filename}")
                            continue
                        
                        # Process each column mapping
                        for mapping in column_mappings:
                            dataframe_column = mapping.get('dataframe_column')
                            csv_column = mapping.get('csv_column')
                            
                            if not dataframe_column or not csv_column:
                                continue
                            
                            # Check if the dataframe_column matches our score name
                            if dataframe_column == score_name:
                                # Find the CSV column (case-insensitive)
                                actual_csv_col = None
                                for col in df.columns:
                                    if col.lower() == csv_column.lower():
                                        actual_csv_col = col
                                        break
                                
                                if actual_csv_col:
                                    # Load the override data
                                    for _, row in df.iterrows():
                                        form_id = row[form_id_col]
                                        if pd.isna(form_id):
                                            continue
                                        
                                        form_id = int(form_id)
                                        answer_value = row[actual_csv_col]
                                        
                                        if pd.notna(answer_value):
                                            if form_id not in self.override_data:
                                                self.override_data[form_id] = {}
                                            self.override_data[form_id][score_name] = str(answer_value).strip().lower()
                                    
                                    # Override data loaded for score
                                else:
                                    self.logging.warning(f"CSV column not found: {csv_column}")
                    
                    except Exception as e:
                        self.logging.warning(f"Failed to load override data from {item_list_filename}: {e}")
            
            if self.override_data:
                total_overrides = sum(len(scores) for scores in self.override_data.values())
                self.logging.info(f"Loaded {total_overrides} override entries for {len(self.override_data)} form IDs")
            else:
                self.logging.info("No override data loaded from CSV files")
                
        except Exception as e:
            self.logging.warning(f"Failed to load override data: {e}")

    async def run(self, tracker=None, progress_callback=None, dry_run=False):
        # Starting accuracy evaluation

        """Run the accuracy evaluation.

        tracker is optional to maintain backward compatibility with callers that
        did not pass a tracker. When None, stage/progress updates are skipped.
        """
        self.progress_callback = progress_callback
        self.dry_run = dry_run  # Store dry_run flag for use in ScoreResult creation
        
        # Store the evaluation ID from the parent process
        self.experiment_id = self.evaluation_id
        
        # Only require evaluation_id if not in dry_run mode
        if not self.experiment_id and not dry_run:
            self.logging.error("No evaluation_id provided to AccuracyEvaluation")
            raise ValueError("No evaluation_id provided to AccuracyEvaluation")
        elif not self.experiment_id and dry_run:
            self.logging.info("[DRY RUN] Using mock evaluation ID")
            self.experiment_id = "mock-evaluation-id-for-dry-run"
        
        # Initialize started_at for elapsed time calculations
        self.started_at = datetime.now(timezone.utc)
        
        self.logging.info(f"Using evaluation record with ID: {self.experiment_id}")
        
        # Scorecard and Score IDs are now set during initialization and should already be updated in the evaluation record

        try:
            returned_metrics = await self._run_evaluation(tracker)
            return returned_metrics
        except Exception as e:
            self.logging.error(f"Error during AccuracyEvaluation.run: {e}", exc_info=True)
            raise e # Re-raise after logging
        finally:
            self.should_stop = True

    async def _run_evaluation(self, tracker):
        try:
            # Use labeled_samples that were provided during AccuracyEvaluation construction
            import pandas as pd
            df = None

            # Check if we have labeled_samples from the constructor
            if self.labeled_samples:
                df = pd.DataFrame(self.labeled_samples)
                self.logging.info(f"Using {len(df)} labeled samples provided to AccuracyEvaluation")
            elif self.labeled_samples_filename:
                df = pd.read_csv(self.labeled_samples_filename)
                self.logging.info(f"Loaded {len(df)} samples from file: {self.labeled_samples_filename}")
            else:
                # Fallback: try to load data from score YAML (for backwards compatibility)
                try:
                    from plexus.data.FeedbackItems import FeedbackItems
                    # For AccuracyEvaluation, we don't have get_scores_to_process method
                    # so we'll work with what we have in the scorecard
                    if hasattr(self, 'subset_of_score_names') and self.subset_of_score_names:
                        primary_score_name = self.subset_of_score_names[0]
                    else:
                        primary_score_name = self.scorecard.scores[0].get('name') if self.scorecard.scores else None

                    score_config = None
                    for sc in self.scorecard.scores:
                        if sc.get('name') == primary_score_name:
                            score_config = sc
                            break
                    if not score_config:
                        score_config = self.scorecard.scores[0] if self.scorecard.scores else {}

                    data_section = score_config.get('data') or {}
                    if data_section:
                        cls = data_section.get('class')
                        params = data_section.get('parameters') or {}
                        # Support shorthand where params are at root
                        if not params:
                            params = {k: v for k, v in data_section.items() if k != 'class'}

                        # Map known aliases to fully-qualified class
                        if cls in ['FeedbackItems', 'plexus.data.FeedbackItems']:
                            data_cache = FeedbackItems(**params)
                            df = data_cache.load_dataframe(data=params, fresh=True)
                            self.logging.info(f"Loaded {len(df)} samples from FeedbackItems data source")
                except Exception as e:
                    self.logging.warning(f"Could not load data from score YAML: {e}")

            if df is None or len(df) == 0:
                raise ValueError("Dataset not found. No labeled samples were provided and score YAML data loading failed.")

            # Adjust the sample size if necessary
            self.number_of_texts_to_sample = min(len(df), self.requested_sample_size)
            self.logging.info(f"Adjusted sample size from {self.requested_sample_size} to {self.number_of_texts_to_sample} based on available data")

            # Sample rows based on the sampling method
            if self.sampling_method == 'random':
                selected_sample_rows = df.sample(n=self.number_of_texts_to_sample, random_state=self.random_seed)
            elif self.sampling_method == 'sequential':
                selected_sample_rows = df.head(self.number_of_texts_to_sample)
            elif self.sampling_method == 'provided':
                # Samples are already provided and pre-processed, use them as-is
                selected_sample_rows = df
                self.logging.info(f"Using {len(df)} provided samples without additional sampling")
            else:
                selected_sample_rows = df

            # Update tracker status without advancing stage
            if tracker and tracker.current_stage:
                tracker.current_stage.status_message = "Generating predictions..."
            if tracker:
                tracker.update(current_items=0)

            # Process all scores concurrently
            score_tasks = []
            for score_name in self.score_names():
                task = asyncio.create_task(self.score_all_texts_for_score(selected_sample_rows, score_name, tracker))
                score_tasks.append(task)

            all_results = await asyncio.gather(*score_tasks)
            self.all_results = [result for score_results in all_results for result in score_results if not isinstance(result, Exception)]

            # Advance to Finalizing stage after all processing is complete
            if tracker:
                tracker.advance_stage()
                self.logging.info("==== STAGE: Finalizing ====")

            # Calculate metrics from results
            
            # Reset counters and mismatches
            self.total_correct = 0
            self.total_questions = 0
            self.total_skipped = 0
            self.mismatches = []
            
            # Count the number correct out of all questions and collect mismatches
            for result in self.all_results:
                for question in self.score_names():
                    score_result = next((r for r in result['results'].values() if r.parameters.name == question), None)
                    
                    # Skip counting if score was skipped due to unmet conditions
                    if score_result and isinstance(score_result.value, str) and score_result.value.upper() == "SKIPPED":
                        self.total_skipped += 1
                        continue
                    
                    score_value = str(score_result.value).lower() if score_result else None
                    human_label = str(score_result.metadata['human_label']).lower() if score_result and hasattr(score_result, 'metadata') and 'human_label' in score_result.metadata else None
                    
                    is_match = 1 if score_result and hasattr(score_result, 'metadata') and score_result.metadata.get('correct', False) else 0
                    self.total_correct += is_match
                    self.total_questions += 1

                    if not is_match and len(self.mismatches) < self.max_mismatches_to_report:
                        mismatch_data = {
                            'form_id': result['form_id'],
                            'question': question,
                            'predicted': score_value,
                            'ground_truth': human_label,
                            'explanation': score_result.metadata['explanation'] if score_result and hasattr(score_result, 'metadata') and 'explanation' in score_result.metadata else None,
                            'transcript': score_result.metadata['text'] if score_result and hasattr(score_result, 'metadata') and 'text' in score_result.metadata else None,
                            'human_explanation': score_result.metadata['human_explanation'] if score_result and hasattr(score_result, 'metadata') and 'human_explanation' in score_result.metadata else None
                        }
                        # Only append if we have either a transcript or an explanation
                        if mismatch_data['transcript'] is not None or mismatch_data['explanation'] is not None:
                            self.mismatches.append(mismatch_data)

            # Calculate metrics from the results
            metrics = self.calculate_metrics(self.all_results)

            # Metrics calculated
            
            # Log ScoreResult creation statistics
            attempts = getattr(self, 'scoreresult_creation_attempts', 0)
            successes = getattr(self, 'scoreresult_creation_successes', 0)
            failures = getattr(self, 'scoreresult_creation_failures', 0)
            if attempts > 0:
                success_rate = (successes / attempts) * 100
                self.logging.info(f"ScoreResult creation: {successes}/{attempts} successful ({success_rate:.1f}%)")
            else:
                self.logging.warning("No ScoreResult creation attempts made")

            if hasattr(self, 'progress_callback') and self.progress_callback:
                self.progress_callback(self.number_of_texts_to_sample)
            
            # Generate and print evaluation report
            if self.all_results:
                expenses = self.scorecard.get_accumulated_costs()
                expenses['cost_per_text'] = expenses['total_cost'] / self.number_of_texts_to_sample
                
                # Get the primary score name if we're evaluating a specific score
                primary_score_name = None
                if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
                    primary_score_name = self.subset_of_score_names[0]
                else:
                    primary_score_name = self.score_names()[0]
                
                # Try to get score instance for report generation, but skip if not found in registry
                # (This can happen with API-loaded scorecards that aren't registered)
                try:
                    score_instance = self.get_score_instance(primary_score_name)
                    
                    # Calculate overall_accuracy from the counters we just updated
                    overall_accuracy = (self.total_correct / self.total_questions * 100) if self.total_questions > 0 else 0
                    
                    # Build confusion matrix metrics for the summary
                    confusion_metrics = self._build_confusion_metrics_from_results()
                    
                    report = self.generate_report(score_instance, overall_accuracy, expenses, self.number_of_texts_to_sample, confusion_metrics)
                    logging.info(f"\nEvaluation Report:\n{report}\n")
                except ValueError as e:
                    if "not found" in str(e):
                        # Calculate overall_accuracy anyway for logging
                        overall_accuracy = (self.total_correct / self.total_questions * 100) if self.total_questions > 0 else 0
                        self.logging.info(f"Overall accuracy: {overall_accuracy}%")
                    else:
                        raise

                # Generate reports - determine the correct report folder
                if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
                    try:
                        score_instance = self.get_score_instance(self.subset_of_score_names[0])
                        report_folder_path = score_instance.report_directory_path()
                        report_folder_path = report_folder_path.rstrip('/')
                    except ValueError as e:
                        if "not found" in str(e):
                            # Use default report folder when scorecard not found in registry
                            scorecard_name = self.scorecard.name.replace(' ', '_') if hasattr(self.scorecard, 'name') and callable(self.scorecard.name) else str(self.scorecard_name).replace(' ', '_')
                            score_name = self.subset_of_score_names[0].replace(' ', '_')
                            report_folder_path = f"./score_results/{scorecard_name}/{score_name}"
                        else:
                            raise
                else:
                    scorecard_name = self.scorecard.name.replace(' ', '_')
                    report_folder_path = f"./score_results/{scorecard_name}/combined"

                # Ensure the report folder exists
                os.makedirs(report_folder_path, exist_ok=True)
                self.logging.info(f"Report folder set to: {report_folder_path}")

                # Generate Excel report
                self.generate_excel_report(report_folder_path, self.all_results, selected_sample_rows)

                # Generate CSV reports
                analysis = ScorecardResultsAnalysis(scorecard_results=ScorecardResults(self.all_results))
                
                # Generate CSV report for incorrect results
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_report_filename = f"scorecard_report_for_incorrect_results_{timestamp}.csv"
                with open(f"{report_folder_path}/{csv_report_filename}", "w") as file:
                    file.write(analysis.generate_csv_scorecard_report(results=self.all_results))
                self.logging.info(f"CSV report generated at {report_folder_path}/{csv_report_filename}")

                # Generate question accuracy CSV
                question_accuracy_filename = f"question_accuracy_report_{timestamp}.csv"
                analysis.generate_question_accuracy_csv(output_file=f"{report_folder_path}/{question_accuracy_filename}")
                self.logging.info(f"Question accuracy CSV generated at {report_folder_path}/{question_accuracy_filename}")

                # Generate confusion matrices and performance visualizations
                self.generate_and_log_confusion_matrix(self.all_results, report_folder_path)
                for question in self.score_names():
                    self.create_performance_visualization(self.all_results, question, report_folder_path)

                # Generate metrics JSON
                self.generate_metrics_json(report_folder_path, self.number_of_texts_to_sample, expenses)

                # Analyze confidence calibration if confidence features are detected (preserve raw values)
                calibration_report = None
                try:
                    from plexus.confidence_calibration import (
                        detect_confidence_feature_enabled,
                        extract_confidence_accuracy_pairs,
                        compute_two_stage_calibration,
                        serialize_calibration_model,
                        generate_calibration_report
                    )

                    logging.info(f"About to check confidence detection on {len(self.all_results)} results")
                    print(f"DEBUG: About to check confidence detection on {len(self.all_results)} results")
                    confidence_detected = detect_confidence_feature_enabled(self.all_results)
                    logging.info(f"Confidence detection result: {confidence_detected}")
                    print(f"DEBUG: Confidence detection result: {confidence_detected}")

                    if confidence_detected:
                        logging.info("Confidence feature detected - computing two-stage calibration (temperature scaling + isotonic regression)")

                        # Extract confidence-accuracy pairs
                        confidence_scores, accuracy_labels = extract_confidence_accuracy_pairs(self.all_results)

                        if len(confidence_scores) >= 10:
                            # Compute two-stage calibration model
                            optimal_temperature, isotonic_model, temp_scaled_scores = compute_two_stage_calibration(
                                confidence_scores, accuracy_labels
                            )

                            if isotonic_model is not None:
                                # Generate calibration report with isotonic model data
                                calibration_report = generate_calibration_report(
                                    temp_scaled_scores, accuracy_labels, isotonic_model
                                )

                                # Add temperature scaling info and serialized calibration data
                                calibration_report["temperature_scaling"] = {
                                    "optimal_temperature": float(optimal_temperature),
                                    "method": "two_stage_calibration"
                                }
                                calibration_report["calibration_model"] = serialize_calibration_model(isotonic_model)

                                # Generate reliability diagram visualization with all three series
                                try:
                                    from plexus.confidence_calibration import plot_reliability_diagram
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    reliability_plot_path = f"{report_folder_path}/reliability_diagram_{timestamp}.png"

                                    # Apply final calibration to get fully calibrated confidence scores
                                    final_calibrated_scores = isotonic_model.predict(temp_scaled_scores)

                                    plot_reliability_diagram(
                                        confidence_scores=confidence_scores,
                                        accuracy_labels=accuracy_labels,
                                        save_path=reliability_plot_path,
                                        title=f"Two-Stage Confidence Calibration (T={optimal_temperature:.3f})",
                                        n_bins=20,  # 5% buckets
                                        temperature_scaled_scores=temp_scaled_scores,
                                        calibrated_confidence_scores=final_calibrated_scores.tolist()
                                    )

                                    logging.info(f"Two-stage reliability diagram saved to: {reliability_plot_path}")
                                    logging.info(f"Temperature scaling: T={optimal_temperature:.4f}")
                                    print(f"DEBUG: Two-stage reliability diagram saved to: {reliability_plot_path}")
                                    print(f"DEBUG: Temperature scaling: T={optimal_temperature:.4f}")

                                    # Save calibration metrics to JSON file
                                    calibration_metrics_path = f"{report_folder_path}/calibration_metrics_{timestamp}.json"
                                    with open(calibration_metrics_path, 'w') as f:
                                        import json
                                        json.dump(calibration_report, f, indent=2)
                                    logging.info(f"Calibration metrics saved to: {calibration_metrics_path}")

                                except Exception as viz_error:
                                    logging.error(f"Error generating two-stage reliability diagram: {viz_error}")
                                    print(f"DEBUG: Error generating two-stage reliability diagram: {viz_error}")
                            else:
                                logging.warning("Could not compute two-stage calibration model (isotonic regression failed)")
                        else:
                            logging.info(f"Insufficient confidence data for calibration analysis: {len(confidence_scores)} samples (need >= 10)")
                            print(f"DEBUG: Insufficient confidence data: {len(confidence_scores)} samples")
                    else:
                        logging.info("No confidence features detected - skipping calibration analysis")
                        print(f"DEBUG: No confidence features detected")

                except Exception as calib_error:
                    logging.error(f"Error in confidence calibration analysis: {calib_error}")
                    print(f"DEBUG: Error in calibration analysis: {calib_error}")

            return metrics
        except Exception as e:
            self.logging.error(f"Error in _run_evaluation: {e}", exc_info=True)
            'raise e'
        finally:
            pass

    def get_score_instance(self, score_name: str):
        """
        Get a Score instance using the standardized Score.load() method.
        
        This method now uses the DRY, tested Score.load() approach that handles:
        - API loading with local caching
        - YAML-only loading from local files
        - Proper error handling and dependency resolution
        """
        # Use the standardized Score.load() method
        # This handles both API-loaded and YAML-loaded scorecards automatically
        # Use cache for evaluations to support --yaml mode
        return Score.load(
            scorecard_identifier=self.scorecard_name,
            score_name=score_name,
            use_cache=True,  # Use cached YAML files when available (supports --yaml mode)
            yaml_only=False  # Allow API calls if needed
        )

