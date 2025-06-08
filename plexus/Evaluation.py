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
import mlflow
from concurrent.futures import ThreadPoolExecutor
from asyncio import Queue
import importlib
import logging
import re
import uuid

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
from plexus.cli.CommandProgress import CommandProgress

from sklearn.metrics import confusion_matrix

from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation
from plexus.dashboard.api.models.scorecard import Scorecard as DashboardScorecard
from plexus.dashboard.api.models.score import Score as DashboardScore
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.dashboard.api.models.task import Task

from plexus.scores.LangGraphScore import LangGraphScore, BatchProcessingPause
from plexus.utils.dict_utils import truncate_dict_strings_inner
from plexus.CustomLogging import logging, setup_logging, set_log_group

from plexus.cli.task_progress_tracker import StageConfig, TaskProgressTracker

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
    consistency of results. It integrates with MLFlow for tracking experiments and the Plexus
    dashboard for monitoring. The class supports:

    - Accuracy testing against labeled data
    - Consistency checking through repeated scoring
    - Automatic metrics calculation and visualization
    - Cost tracking and reporting
    - Integration with MLFlow experiments
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

    3. Using with MLFlow tracking:
        with evaluation:  # Automatically starts/ends MLFlow run
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
    ):
        # Immediately store task_id so that it is available for evaluation record creation
        self.task_id = task_id
        
        # Set up logging for evaluations
        self.logging = logging.getLogger('plexus/evaluation')
        self.logging.info("Starting Evaluation initialization...")

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
            self.logging.info("Initializing Plexus Dashboard client...")
            self.dashboard_client = PlexusDashboardClient.for_account(account_key)
            
            self.logging.info(f"Looking up account with key: {account_key}")
            account = Account.list_by_key(key=account_key, client=self.dashboard_client)
            if not account:
                raise ValueError(f"No account found with key: {account_key}")
            self.logging.info(f"Found account: {account.name} ({account.id})")
            
            self.account_id = account.id
            
            # Initialize scorecard_id as None
            self.scorecard_id = None
            
            self.logging.info(f"Looking up scorecard with name: {self.scorecard.name}")
            try:
                if hasattr(self.scorecard, 'key'):
                    self.logging.info(f"Using scorecard key: {self.scorecard.key}")
                    scorecard_obj = DashboardScorecard.get_by_key(self.scorecard.key, self.dashboard_client)
                elif hasattr(self.scorecard, 'id'):
                    self.logging.info(f"Using scorecard ID: {self.scorecard.id}")
                    scorecard_obj = DashboardScorecard.get_by_id(self.scorecard.id, self.dashboard_client)
                else:
                    self.logging.info(f"Looking up scorecard by name: {self.scorecard_name}")
                    scorecard_obj = DashboardScorecard.get_by_name(self.scorecard_name, self.dashboard_client)
                
                if scorecard_obj:
                    self.logging.info(f"Found scorecard: {scorecard_obj.name} ({scorecard_obj.id})")
                    self.scorecard_id = scorecard_obj.id
                else:
                    self.logging.error("Failed to find scorecard")
                    raise ValueError(f"Could not find scorecard with name: {self.scorecard.name}")
            except Exception as e:
                self.logging.error(f"Error looking up scorecard: {str(e)}")
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

    def __enter__(self):
        self.start_mlflow_run()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        mlflow.end_run()

    def start_mlflow_run(self):
        logging.getLogger('mlflow').setLevel(logging.WARNING)

        # First, make sure any existing run is ended
        try:
            mlflow.end_run()
        except Exception:
            pass  # Ignore any errors from ending non-existent runs

        mlflow_tracking_uri = os.getenv('MLFLOW_TRACKING_URI')
        if mlflow_tracking_uri:
            logging.info(f"Using MLFlow tracking URL: {mlflow_tracking_uri}")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        else:
            mlflow.set_tracking_uri(f'file:///{os.path.abspath("./mlruns")}')

        experiment_name = self.scorecard.__class__.name
        if os.getenv('MLFLOW_EXPERIMENT_NAME'):
            experiment_name = experiment_name + " - " + os.getenv('MLFLOW_EXPERIMENT_NAME')
        if self.experiment_label:
            experiment_name = experiment_name + " - " + self.experiment_label
        mlflow.set_experiment(experiment_name)

        # Now start the new run
        try:
            mlflow.start_run()
        except Exception as e:
            print("Error: ", e)
            print("Attempting to end the previous run and start a new one.")
            mlflow.end_run()
            mlflow.start_run()

        # Add notes about the run
        mlflow.set_tag("scorecard", self.scorecard.name)
        mlflow.set_tag("experiment_type", self.__class__.__name__)
        if self.task_id:  # Add task_id as a tag if available
            mlflow.set_tag("task_id", self.task_id)

        self.log_parameters()
    
    def log_parameters(self):
        mlflow.log_param("sampling_method", self.sampling_method)
        mlflow.log_param("number_of_texts_to_sample", self.number_of_texts_to_sample)

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
            mlflow.log_metric("execution_time", execution_time)
            mlflow.log_metric("time_per_text", time_per_text)
            print(f"{func.__name__} executed in {execution_time:.2f} seconds.")
            logging.info(f"Average time per text: {time_per_text:.2f} seconds.")
            return result

        def sync_wrapper(self, *args, **kwargs):
            start_time = time.time()
            result = func(self, *args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            time_per_text = execution_time / self.number_of_texts_to_sample if self.number_of_texts_to_sample else 0
            mlflow.log_metric("execution_time", execution_time)
            mlflow.log_metric("time_per_text", time_per_text)
            print(f"{func.__name__} executed in {execution_time:.2f} seconds.")
            logging.info(f"Average time per text: {time_per_text:.2f} seconds.")
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
                
                logging.debug(f"Updating evaluation with variables: {json.dumps(clean_variables, indent=2)}")
                
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
        # --- BEGIN NEW LOGGING ---
        self.logging.info(f"--- Entering calculate_metrics with {len(results)} results ---")
        if not results:
            self.logging.warning("calculate_metrics received an empty list of results.")
            # Return default/empty metrics to avoid crashing
            return {
                "accuracy": 0,
                "alignment": 0,  # Changed from sensitivity to alignment
                "precision": 0,
                "recall": 0,      # Changed from specificity to recall
                "predicted_distribution": [],
                "actual_distribution": [],
                "confusion_matrices": []
            }
        # --- END NEW LOGGING ---

        # Import metrics classes
        from plexus.analysis.metrics.gwet_ac1 import GwetAC1
        from plexus.analysis.metrics.accuracy import Accuracy
        from plexus.analysis.metrics.precision import Precision
        from plexus.analysis.metrics.recall import Recall
        from plexus.analysis.metrics.metric import Metric

        # Use self.logging instead of logging globally
        self.logging.info(f"\nStarting metrics calculation with {len(results)} results")
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
            logging.info(f"\nProcessing result for form_id: {result['form_id']}")
            
            for score_identifier, score_result in result['results'].items():
                # --- Add logging before skips ---
                self.logging.info(f"  Processing score_identifier: {score_identifier}")
                if hasattr(score_result, 'value'):
                    self.logging.info(f"    Score value: {score_result.value}")
                else:
                    self.logging.warning(f"    Score result object has no 'value' attribute: {score_result}")
                    continue # Skip if value is missing

                # Skip if the score result is an error
                if isinstance(score_result.value, str) and score_result.value.upper() == "ERROR":
                    self.logging.warning(f"  Skipping metrics calculation for error result: {score_identifier}")
                    continue

                # Ensure parameters attribute exists before accessing name
                if not hasattr(score_result, 'parameters') or not hasattr(score_result.parameters, 'name'):
                    self.logging.warning(f"  Skipping metrics calculation for result without valid parameters/name: {score_identifier}")
                    continue
                score_name = score_result.parameters.name
                self.logging.info(f"    Score name resolved to: {score_name}")

                # Skip if this is a dependency score and not our primary score
                if primary_score_name and score_name != primary_score_name:
                    logging.info(f"  Skipping metrics for dependency score: {score_name} (Primary: {primary_score_name})")
                    continue

                # Ensure metadata and human_label exist before accessing
                if not hasattr(score_result, 'metadata') or 'human_label' not in score_result.metadata:
                    self.logging.warning(f"  Skipping metrics calculation for result missing metadata or human_label: {score_identifier}")
                    continue
                # --- End logging ---

                # Standardize and prepare predicted & actual values
                predicted = str(score_result.value).lower().strip()
                actual = str(score_result.metadata['human_label']).lower().strip()
                
                # Standardize empty or NA values
                predicted = 'na' if predicted in ['', 'nan', 'n/a', 'none', 'null'] else predicted
                actual = 'na' if actual in ['', 'nan', 'n/a', 'none', 'null'] else actual
                
                # Collect predictions and actuals for Gwet's AC1 calculation
                all_predictions.append(predicted)
                all_actuals.append(actual)
                
                # Log the first 10 results for visual inspection
                if logged_results_count < 10:
                    self.logging.info(f"  Result {logged_results_count + 1}: Form ID: {result.get('form_id', 'N/A')}, Score: {score_name}, Predicted: '{predicted}', Actual: '{actual}'")
                    logged_results_count += 1

                self.logging.info(f"Score: {score_name}")
                self.logging.info(f"Predicted: '{predicted}'")
                self.logging.info(f"Actual: '{actual}'")
                
                # Determine correctness - check if predicted value exactly matches the actual value
                is_correct = predicted == actual
                self.logging.info(f"Correct: {is_correct}")
                
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
                # Add diagnostic logging for Accuracy inputs
                self.logging.info(f"Accuracy calculation inputs:")
                self.logging.info(f"  Predictions ({len(all_predictions)}): {all_predictions[:10]}...")
                self.logging.info(f"  Actuals ({len(all_actuals)}): {all_actuals[:10]}...")
                
                # Create an Accuracy instance and use proper Metric.Input interface
                accuracy_calculator = Accuracy()
                metric_input = Metric.Input(
                    reference=all_actuals,
                    predictions=all_predictions
                )
                result = accuracy_calculator.calculate(metric_input)
                accuracy_value = result.value
                self.logging.info(f"Calculated Accuracy: {accuracy_value}")
                self.logging.info(f"Matches: {result.metadata.get('matches', 0)}/{result.metadata.get('total', 0)}")
            except Exception as e:
                self.logging.error(f"Error calculating Accuracy: {str(e)}")
                self.logging.exception("Stack trace for Accuracy calculation error:")
                # Fall back to manual calculation if the Accuracy class fails
                accuracy_value = total_correct / total_predictions if total_predictions > 0 else 0
                self.logging.info(f"Fallback to manual accuracy calculation: {accuracy_value}")
        else:
            # If lists are empty or unequal, use the original calculation
            accuracy_value = total_correct / total_predictions if total_predictions > 0 else 0
            self.logging.info(f"Used manual accuracy calculation due to empty or unequal lists: {accuracy_value}")
        
        # Calculate Gwet's AC1 for alignment
        gwet_ac1_value = 0
        if all_predictions and all_actuals and len(all_predictions) == len(all_actuals) and len(all_predictions) > 0:
            try:
                # Add diagnostic logging for AC1 inputs
                self.logging.info(f"Gwet's AC1 calculation inputs:")
                self.logging.info(f"  Predictions ({len(all_predictions)}): {all_predictions[:10]}...")
                self.logging.info(f"  Actuals ({len(all_actuals)}): {all_actuals[:10]}...")
                
                # Calculate unique categories for debugging
                unique_categories = set(all_predictions + all_actuals)
                self.logging.info(f"  Unique categories: {unique_categories}")
                
                # Create a GwetAC1 instance and use proper Metric.Input interface
                gwet_calculator = GwetAC1()
                metric_input = Metric.Input(
                    reference=all_actuals,
                    predictions=all_predictions
                )
                result = gwet_calculator.calculate(metric_input)
                gwet_ac1_value = result.value
                self.logging.info(f"Calculated Gwet's AC1: {gwet_ac1_value}")
                
                # Map AC1 from [-1, 1] to [0, 1] for backward compatibility
                # Any negative values are mapped to 0
                gwet_ac1_mapped = max(0, (gwet_ac1_value + 1) / 2)
                self.logging.info(f"Mapped Gwet's AC1 (for backward compatibility): {gwet_ac1_mapped}")
            except Exception as e:
                self.logging.error(f"Error calculating Gwet's AC1: {str(e)}")
                self.logging.exception("Stack trace for AC1 calculation error:")
                gwet_ac1_value = 0
        
        # Calculate precision using the Precision metric class
        precision_value = accuracy_value  # Default fallback is to use accuracy
        
        # First check if we have binary classification data (yes/no) for specialized binary metrics
        binary_confusion_matrix = None
        for score_name, matrix_data in confusion_matrices.items():
            labels = sorted(list(matrix_data['labels']))
            self.logging.info(f"Checking labels for score '{score_name}' for binary metrics: {labels}")
            
            if len(labels) == 2 and 'yes' in labels and 'no' in labels:
                self.logging.info(f"Found binary classification data for score '{score_name}'")
                binary_confusion_matrix = matrix_data
                break
        
        # Calculate precision using the Precision class
        if all_predictions and all_actuals and len(all_predictions) == len(all_actuals) and len(all_predictions) > 0:
            try:
                # Add diagnostic logging for Precision inputs
                self.logging.info(f"Precision calculation inputs:")
                self.logging.info(f"  Predictions ({len(all_predictions)}): {all_predictions[:10]}...")
                self.logging.info(f"  Actuals ({len(all_actuals)}): {all_actuals[:10]}...")
                
                # Create a Precision instance and use proper Metric.Input interface
                precision_calculator = Precision(positive_labels=['yes'])
                metric_input = Metric.Input(
                    reference=all_actuals,
                    predictions=all_predictions
                )
                result = precision_calculator.calculate(metric_input)
                precision_value = result.value
                self.logging.info(f"Calculated Precision: {precision_value}")
                self.logging.info(f"True Positives: {result.metadata.get('true_positives', 0)}")
                self.logging.info(f"False Positives: {result.metadata.get('false_positives', 0)}")
                self.logging.info(f"Total Predicted Positive: {result.metadata.get('total_predicted_positive', 0)}")
            except Exception as e:
                self.logging.error(f"Error calculating Precision: {str(e)}")
                self.logging.exception("Stack trace for Precision calculation error:")
                
                # Fall back to manual calculation if the Precision class fails
                if binary_confusion_matrix:
                    # Manual calculation from confusion matrix
                    tp = binary_confusion_matrix['matrix'].get('yes', {}).get('yes', 0)
                    fp = binary_confusion_matrix['matrix'].get('no', {}).get('yes', 0)
                    precision_value = tp / (tp + fp) if (tp + fp) > 0 else 0
                    self.logging.info(f"Fallback to manual precision calculation from matrix: {precision_value}")
                else:
                    # If no binary confusion matrix, use accuracy as a fallback
                    precision_value = accuracy_value
                    self.logging.info(f"Using accuracy as fallback for precision: {precision_value}")
        elif binary_confusion_matrix:
            # If we have a binary confusion matrix but couldn't use the Precision class
            tp = binary_confusion_matrix['matrix'].get('yes', {}).get('yes', 0)
            fp = binary_confusion_matrix['matrix'].get('no', {}).get('yes', 0)
            precision_value = tp / (tp + fp) if (tp + fp) > 0 else 0
            self.logging.info(f"Calculated precision manually from confusion matrix: {precision_value}")
        else:
            # Default fallback
            self.logging.info(f"Using accuracy as fallback for precision due to insufficient data: {precision_value}")
        
        # Calculate recall using the Recall metric class
        recall_value = accuracy_value  # Default fallback is to use accuracy
        
        # Calculate recall using the Recall class
        if all_predictions and all_actuals and len(all_predictions) == len(all_actuals) and len(all_predictions) > 0:
            try:
                # Add diagnostic logging for Recall inputs
                self.logging.info(f"Recall calculation inputs:")
                self.logging.info(f"  Predictions ({len(all_predictions)}): {all_predictions[:10]}...")
                self.logging.info(f"  Actuals ({len(all_actuals)}): {all_actuals[:10]}...")
                
                # Create a Recall instance and use proper Metric.Input interface
                recall_calculator = Recall(positive_labels=['yes'])
                metric_input = Metric.Input(
                    reference=all_actuals,
                    predictions=all_predictions
                )
                result = recall_calculator.calculate(metric_input)
                recall_value = result.value
                self.logging.info(f"Calculated Recall: {recall_value}")
                self.logging.info(f"True Positives: {result.metadata.get('true_positives', 0)}")
                self.logging.info(f"False Negatives: {result.metadata.get('false_negatives', 0)}")
                self.logging.info(f"Total Actual Positive: {result.metadata.get('total_actual_positive', 0)}")
            except Exception as e:
                self.logging.error(f"Error calculating Recall: {str(e)}")
                self.logging.exception("Stack trace for Recall calculation error:")
                
                # Fall back to manual calculation if the Recall class fails
                if binary_confusion_matrix:
                    # Manual calculation from confusion matrix
                    tp = binary_confusion_matrix['matrix'].get('yes', {}).get('yes', 0)
                    fn = binary_confusion_matrix['matrix'].get('yes', {}).get('no', 0)
                    recall_value = tp / (tp + fn) if (tp + fn) > 0 else 0
                    self.logging.info(f"Fallback to manual recall calculation from matrix: {recall_value}")
                else:
                    # If no binary confusion matrix, use accuracy as a fallback
                    recall_value = accuracy_value
                    self.logging.info(f"Using accuracy as fallback for recall: {recall_value}")
        elif binary_confusion_matrix:
            # If we have a binary confusion matrix but couldn't use the Recall class
            tp = binary_confusion_matrix['matrix'].get('yes', {}).get('yes', 0)
            fn = binary_confusion_matrix['matrix'].get('yes', {}).get('no', 0)
            recall_value = tp / (tp + fn) if (tp + fn) > 0 else 0
            self.logging.info(f"Calculated recall manually from confusion matrix: {recall_value}")
        else:
            # Default fallback
            self.logging.info(f"Using accuracy as fallback for recall due to insufficient data: {recall_value}")
        
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
            self.logging.info(f"\nSelected Confusion Matrix for API (Score: {target_score_name}):")
            self.logging.info(f"Labels: {labels}")
            for i, row in enumerate(matrix):
                self.logging.info(f"{labels[i]}: {row}")
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

        # --- BEGIN NEW LOGGING ---
        self.logging.info("\n--- Calculated Metrics Summary ---")
        self.logging.info(f"Total predictions processed: {total_predictions}")
        self.logging.info(f"Total correct predictions: {total_correct}")
        self.logging.info(f"Final Accuracy: {accuracy_value}")
        self.logging.info(f"Final Precision: {precision_value}")
        self.logging.info(f"Final Alignment (Gwet's AC1): {alignment}")
        self.logging.info(f"Final Recall: {recall_value}")  # Changed from Specificity to Recall
        # --- END NEW LOGGING ---

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
        # --- BEGIN NEW LOGGING ---
        print("\n\n--- Evaluation _async_run CALLED ---\n\n")
        self.logging.info("--- Evaluation _async_run CALLED ---")
        # --- END NEW LOGGING ---

        # Configure logging
        # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

        # Determine the correct report folder
        if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
            score_instance = Score.from_name(self.scorecard_name, self.subset_of_score_names[0])
            report_folder_path = score_instance.report_directory_path()
            report_folder_path = report_folder_path.rstrip('/')
        else:
            scorecard_name = self.scorecard.name.replace(' ', '_')
            report_folder_path = f"./reports/{scorecard_name}/combined"

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
            score_instance = Score.from_name(self.scorecard_name, score_name)
            label_score_name = score_instance.get_label_score_name()
            
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
        elif self.sampling_method == 'all':
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

        logging.info("Logging scorecard results as an artifact in MLFlow.")
        scorecard_results = ScorecardResults(self.all_results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_filename = f"scorecard_results_{timestamp}.json"
        scorecard_results.save_to_file(f"{report_folder_path}/{results_filename}")
        mlflow.log_artifact(f"{report_folder_path}/{results_filename}")

        logging.info("Scoring completed.")

        # Count the number correct out of all questions.
        for result in self.all_results:
            logging.info(f"Form ID: {result['form_id']}")
            for question in self.score_names():
                score_result = next((result for result in result['results'].values() if result.parameters.name == question), None)
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
                mlflow.log_artifact(f"{report_folder_path}/accuracy_heatmap.png")
            except Exception as e:
                logging.error(f"Failed to log accuracy heatmap: {e}")

        def log_html_report():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                html_report_content = analysis.generate_html_report(expenses=expenses)
                report_filename = f"scorecard_report_{timestamp}.html"
                with open(f"{report_folder_path}/{report_filename}", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact(f"{report_folder_path}/{report_filename}")
            except Exception as e:
                logging.error(f"Failed to log HTML report: {e}")

        def log_incorrect_scores_report():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                html_report_content = analysis.generate_html_report(only_incorrect_scores=True, expenses=expenses)
                report_filename = f"scorecard_report_incorrect_scores_{timestamp}.html"
                with open(f"{report_folder_path}/{report_filename}", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact(f"{report_folder_path}/{report_filename}")
            except Exception as e:
                logging.error(f"Failed to log incorrect scores report: {e}")

        def log_no_costs_report():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                html_report_content = analysis.generate_html_report(redact_cost_information=True)
                report_filename = f"scorecard_report_no_costs_{timestamp}.html"
                with open(f"{report_folder_path}/{report_filename}", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact(f"{report_folder_path}/{report_filename}")
            except Exception as e:
                logging.error(f"Failed to log no costs report: {e}")

        def log_scorecard_costs():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                analysis.plot_scorecard_costs(results=self.all_results)
                mlflow.log_artifact(f"{report_folder_path}/scorecard_input_output_costs_{timestamp}.png")
                mlflow.log_artifact(f"{report_folder_path}/histogram_of_total_costs_{timestamp}.png")
                mlflow.log_artifact(f"{report_folder_path}/distribution_of_input_costs_{timestamp}.png")
                mlflow.log_artifact(f"{report_folder_path}/total_llm_calls_by_score_{timestamp}.png")
                mlflow.log_artifact(f"{report_folder_path}/distribution_of_input_costs_by_element_type_{timestamp}.png")
            except Exception as e:
                logging.error(f"Failed to log scorecard costs: {e}")

        def log_csv_report():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_filename = f"scorecard_report_for_incorrect_results_{timestamp}.csv"
                with open(f"{report_folder_path}/{report_filename}", "w") as file:
                    file.write(analysis.generate_csv_scorecard_report(results=self.all_results))
                mlflow.log_artifact(f"{report_folder_path}/{report_filename}")
            except Exception as e:
                logging.error(f"Failed to log CSV report: {e}")

        def log_question_accuracy_csv():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_filename = f"question_accuracy_report_{timestamp}.csv"
                analysis.generate_question_accuracy_csv(output_file=f"{report_folder_path}/{report_filename}")
                mlflow.log_artifact(f"{report_folder_path}/{report_filename}")
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
        mlflow.log_metric("overall_accuracy", overall_accuracy)

        # Log the results to MLflow
        mlflow.log_metric("number_of_texts", len(selected_sample_rows))
        mlflow.log_metric("number_of_scores", len(self.score_names()))
        mlflow.log_metric("total_cost", expenses['total_cost'])
        mlflow.log_metric("cost_per_text", expenses['cost_per_text'])

        # Generate the Excel report
        self.generate_excel_report(report_folder_path, self.all_results, selected_sample_rows)

        logging.info(f"Expenses: {expenses}")
        logging.info(f"{overall_accuracy:.1f}% accuracy / {len(selected_sample_rows)} samples")
        logging.info(f"cost: ${expenses['cost_per_text']:.6f} per call / ${expenses['total_cost']:.6f} total")

        report = self.generate_report(score_instance, overall_accuracy, expenses, len(selected_sample_rows))
        logging.info(report)

        await asyncio.to_thread(self.generate_and_log_confusion_matrix, self.all_results, report_folder_path)
        
        for question in self.score_names():
            self.create_performance_visualization(self.all_results, question, report_folder_path)

        self.generate_metrics_json(report_folder_path, len(selected_sample_rows), expenses)

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
                        tracker.current_stage.status_message = f"Generating predictions ({processed_counter}/{total_rows})"
                        tracker.update(current_items=self.processed_items)
                        
                        # Start metrics task if needed
                        is_final_result = processed_counter == total_rows
                        await self.maybe_start_metrics_task(score_name, is_final_result)
                        
                        return result
                except Exception as e:
                    logging.error(f"Error processing text at index {idx} for {score_name}: {e}")
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
        # --- DETAILED LOGGING START ---
        self.logging.info(f"[_get_update_variables ENTRY] Status: {status}, Metrics keys: {list(metrics.keys())}")
        self.logging.info(f"[_get_update_variables] Raw metrics input: {metrics}")
        # --- DETAILED LOGGING END ---
        elapsed_seconds = int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        
        # Format metrics for API
        metrics_for_api = []
        if metrics.get("accuracy") is not None:
            metrics_for_api.append({"name": "Accuracy", "value": metrics["accuracy"] * 100})
        if metrics.get("precision") is not None:
            metrics_for_api.append({"name": "Precision", "value": metrics["precision"] * 100})
        if metrics.get("alignment") is not None:
            # For alignment (Gwet's AC1), we map from [-1, 1] to [0, 100] for UI display
            # Only map if the value is negative, otherwise use the raw value scaled to percentage
            alignment_value = metrics["alignment"]
            self.logging.info(f"[_get_update_variables] Processing alignment value: {alignment_value}")
            if alignment_value < 0:
                display_value = 0  # Map negative values to 0
            else:
                display_value = alignment_value * 100  # Scale to percentage
            metrics_for_api.append({"name": "Alignment", "value": display_value})
            self.logging.info(f"[_get_update_variables] Added Alignment to metrics_for_api with value: {display_value}")
        if metrics.get("recall") is not None:
            metrics_for_api.append({"name": "Recall", "value": metrics["recall"] * 100})
        
        # Log what metrics we've prepared for API
        self.logging.info(f"[_get_update_variables] Prepared metrics_for_api: {metrics_for_api}")
        
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
                self.logging.warning(f"[_get_update_variables] Alignment exists in metrics but not in metrics_for_api!")
                # Force add it if not already there
                alignment_value = metrics["alignment"]
                display_value = 0 if alignment_value < 0 else alignment_value * 100
                metrics_for_api.append({"name": "Alignment", "value": display_value})
                self.logging.info(f"[_get_update_variables] Forced added Alignment with value: {display_value}")
            
            # Additional validation to ensure all required metrics are included
            metric_names = [m["name"] for m in metrics_for_api]
            self.logging.info(f"[_get_update_variables] Current metric names in metrics_for_api: {metric_names}")
            
            # Force append any missing metrics with default N/A value (-1 displays as N/A in UI)
            required_metrics = ["Accuracy", "Precision", "Alignment", "Recall"]
            for required_metric in required_metrics:
                if required_metric not in metric_names:
                    self.logging.warning(f"[_get_update_variables] Required metric {required_metric} missing - adding with default value")
                    metrics_for_api.append({"name": required_metric, "value": -1})
            
            # Final check and sort for consistent order
            metrics_for_api.sort(key=lambda x: required_metrics.index(x["name"]) if x["name"] in required_metrics else 999)
            
            update_input["metrics"] = json.dumps(metrics_for_api)
            self.logging.info(f"[_get_update_variables] Final metrics_for_api JSON: {json.dumps(metrics_for_api)}")
        else:
            # Create default metrics list with all required metrics if empty
            default_metrics = [
                {"name": "Accuracy", "value": metrics.get("accuracy", 0) * 100},
                {"name": "Alignment", "value": 0 if metrics.get("alignment", 0) < 0 else metrics.get("alignment", 0) * 100},
                {"name": "Precision", "value": metrics.get("precision", 0) * 100},
                {"name": "Recall", "value": metrics.get("recall", 0) * 100}
            ]
            update_input["metrics"] = json.dumps(default_metrics)
            self.logging.info(f"[_get_update_variables] Using default metrics: {json.dumps(default_metrics)}")
        
        # Add confusion matrix if available in metrics
        confusion_matrix_val = metrics.get("confusionMatrix")
        # --- DETAILED LOGGING START ---
        self.logging.info(f"[_get_update_variables] confusionMatrix value from metrics: {confusion_matrix_val}")
        # --- DETAILED LOGGING END ---
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
        # --- DETAILED LOGGING START ---
        self.logging.info(f"[_get_update_variables] predictedClassDistribution value from metrics: {predicted_dist_val}")
        # --- DETAILED LOGGING END ---
        if predicted_dist_val:
            try:
                update_input["predictedClassDistribution"] = json.dumps(predicted_dist_val)
            except (TypeError, OverflowError) as e:
                logging.error(f"Error serializing predicted class distribution: {e}")
                update_input["predictedClassDistribution"] = json.dumps([{"error": "Serialization failed"}])
        else:
            update_input["predictedClassDistribution"] = json.dumps([])

        dataset_dist_val = metrics.get("datasetClassDistribution")
        # --- DETAILED LOGGING START ---
        self.logging.info(f"[_get_update_variables] datasetClassDistribution value from metrics: {dataset_dist_val}")
        # --- DETAILED LOGGING END ---
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
            
        # Log the update fields we're sending to help diagnose issues
        # --- DETAILED LOGGING START ---
        self.logging.info(f"[_get_update_variables PRE-RETURN] Final update_input: {json.dumps(update_input, default=str)}") 
        # --- DETAILED LOGGING END ---
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
        excel_file_path = f"{report_folder_path}/Evaluation Report for {filename_safe_score_names}.xlsx"
        df_records.to_excel(excel_file_path, index=False)
        mlflow.log_artifact(excel_file_path)

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

            mlflow.log_artifact(cm_path)

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
        
        mlflow.log_artifact(f"{report_folder_path}/performance_{safe_question}.png")
        
    def generate_metrics_json(self, report_folder_path, sample_size, expenses):
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
            "number_of_samples": sample_size,
            "cost_per_call": f"{expenses['cost_per_text']:.7f}".rstrip('0').rstrip('.'),
            "total_cost": f"{expenses['total_cost']:.7f}".rstrip('0').rstrip('.')
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_filename = f"metrics_{timestamp}.json"
        metrics_file_path = f"{report_folder_path}/{metrics_filename}"
        with open(metrics_file_path, 'w') as f:
            json.dump(metrics, f, indent=2)

        mlflow.log_artifact(metrics_file_path)
        logging.info(f"Metrics JSON file generated at {metrics_file_path}")

        for key, value in metrics.items():
            if key in ["overall_accuracy", "cost_per_call", "total_cost"]:
                mlflow.log_metric(key, float(value))
            else:
                mlflow.log_metric(key, value)

    def generate_report(self, score_instance, overall_accuracy, expenses, sample_size):
        score_config = score_instance.parameters

        report = f"""
Evaluation Report:
------------------

Prompts:
{yaml.dump(score_config.graph, default_flow_style=False)}

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
        report += f"""

Overall Accuracy: {overall_accuracy:.1f}% ({self.total_correct} / {self.total_questions})
Sample Size:      {sample_size}
Cost per call:    ${expenses['cost_per_text']:.6f}
Total cost:       ${expenses['total_cost']:.6f}
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

                logging.info(f"Processing text for content_id: {content_id}, session_id: {session_id}, form_id: {form_id}")

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
                            score_instance = Score.from_name(self.scorecard_name, score_to_process)
                            if isinstance(score_instance, LangGraphScore):
                                await score_instance.async_setup()  # Ensure the graph is built
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                output_path = os.path.join('tmp', f'graph_{score_to_process}_{timestamp}.png')
                                score_instance.generate_graph_visualization(output_path)
                                logging.info(f"Generated graph visualization at {output_path}")
                
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
                            logging.warning(f"Could not find configuration for score '{current_score_name}' in self.scorecard.scores. Skipping.")
                            continue
                            
                        # Determine label score name from config or default to current score name
                        label_score_name = score_config.get('label_score_name', current_score_name)
                        score_name = current_score_name # Use the name from the result parameters
                        # --- End Refactor ---

                        # Skip if this is a dependency score and not our primary score
                        if primary_score_name and score_name != primary_score_name:
                            logging.info(f"Skipping result creation for dependency score: {score_name}")
                            continue

                        # First check for override
                        human_label = None
                        if form_id in self.override_data and score_name in self.override_data[form_id]:
                            human_label = self.override_data[form_id][score_name]
                            logging.info(f"Using override for form {form_id}, score {score_name}: {human_label}")
                        else:
                            # Fall back to row data if no override exists
                            label_column = label_score_name + '_label'
                            if label_column in row.index:
                                human_label = row[label_column]
                            elif label_score_name in row.index:
                                human_label = row[label_score_name]
                            else:
                                logging.warning(f"Neither '{score_identifier}' nor '{label_score_name}' found in the row. Available columns: {row.index.tolist()}")
                                continue

                        human_label = str(human_label).lower().rstrip('.!?')
                        if human_label == 'nan':
                            human_label = ''
                        if human_label == 'n/a':
                            human_label = 'na'

                        human_explanation = columns.get(f"{label_score_name} comment", 'None')

                        score_result_value = ' '.join(str(score_result.value).lower().strip().split())

                        if form_id in self.override_data:
                            for override_question_name, correct_value in self.override_data[form_id].items():
                                if str(override_question_name) in human_labels:
                                    logging.info(f"OVERRIDING human label for question '{override_question_name}' in form '{form_id}' from '{human_labels[str(override_question_name)]}' to '{correct_value}'")
                                    human_labels[str(override_question_name)] = correct_value

                        score_result.metadata['human_label'] = human_label
                        score_result.metadata['human_explanation'] = human_explanation
                        score_result.metadata['correct'] = score_result_value.strip() == human_label.strip()
                        score_result.metadata['text'] = text

                        # Add to filtered results only if we get here (i.e., all conditions are met)
                        filtered_results[score_identifier] = score_result
                        has_processed_scores = True

                        # Create ScoreResult in a non-blocking way only for the primary score
                        if self.dashboard_client and self.experiment_id:
                            await self._create_score_result(
                                score_result=score_result,
                                content_id=content_id,
                                result=result
                            )

                    except Exception as e:
                        logging.exception(f"Error processing {score_identifier}: {e}")
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

            except Exception as e: # Catch any other unexpected errors during scoring
                logging.error(f"Unexpected error scoring content_id {row.get('content_id')} on attempt {attempt + 1}: {e}", exc_info=True)
                if attempt == max_attempts - 1:
                    # Return an error result on the last attempt
                    return {
                        'content_id': row.get('content_id', ''),
                        'session_id': row.get('Session ID', row.get('content_id', '')),
                        'form_id': row.get('columns', {}).get('form_id', ''),
                        'results': {
                            score_name or 'processing_error': Score.Result(
                                value="Error",
                                error=f"Unexpected error after {max_attempts} attempts: {e}",
                                parameters=Score.Parameters(name=score_name or 'processing_error', scorecard=self.scorecard_name)
                           )
                        },
                        'human_labels': {}
                    }
                # Wait before retrying for unexpected errors too
                delay = min(base_delay * (2 ** attempt), max_delay)
                logging.info(f"Retrying in {delay} seconds...")
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

    async def _create_score_result(self, *, score_result, content_id, result):
        """Create a score result in the dashboard."""
        try:
            # Log the raw inputs
            logging.info("Creating score result with raw inputs:")
            logging.info(f"score_result value: {score_result.value}")
            logging.info(f"score_result metadata: {truncate_dict_strings_inner(score_result.metadata)}")
            logging.info(f"content_id: {content_id}")
            logging.info(f"result dict: {truncate_dict_strings_inner(result)}")

            # Validate required attributes are available
            if not hasattr(self, 'experiment_id') or not self.experiment_id:
                raise ValueError("experiment_id is not set")
            if not hasattr(self, 'account_id') or not self.account_id:
                raise ValueError("account_id is not set")
            if not hasattr(self, 'scorecard_id') or not self.scorecard_id:
                raise ValueError("scorecard_id is not set")

            # Ensure we have a valid string value
            value = str(score_result.value) if score_result.value is not None else "N/A"
            
            # Ensure we have valid metadata
            metadata_dict = {
                'item_id': result.get('form_id', ''),
                'results': {
                    score_result.parameters.name: {
                        'value': value,
                        'confidence': None,
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
            
            # First, create or upsert the Item record
            # We'll use the content_id as the externalId
            await self._create_or_upsert_item(content_id=content_id, score_result=score_result, result=result)
            
            # Create data dictionary with all required fields
            data = {
                'evaluationId': self.experiment_id,
                'itemId': content_id,  # Use content_id as the itemId
                'accountId': self.account_id,
                'scorecardId': self.scorecard_id,
            }
            
            # Add score_id if available and has valid format
            if hasattr(self, 'score_id') and self.score_id:
                # Validate score_id format - should be a UUID with hyphens
                if not (isinstance(self.score_id, str) and '-' in self.score_id):
                    self.logging.warning(f"WARNING: Score ID doesn't appear to be in DynamoDB UUID format: {self.score_id}")
                    self.logging.warning(f"Will not add this Score ID to the ScoreResult record.")
                else:
                    data['scoreId'] = self.score_id
                    
            data['value'] = value
            data['metadata'] = json.dumps(metadata_dict)  # Ensure metadata is a JSON string

            # Add trace data if available
            logging.info("Checking for trace data to add to score result...")            
            if score_result.metadata and 'trace' in score_result.metadata:
                logging.info(f"trace content: {score_result.metadata['trace']}")
                data['trace'] = json.dumps(score_result.metadata['trace'])
                logging.info("Added metadata trace to trace data")
            else:
                logging.info("No trace data found to add")

            # Log the data being sent
            self.logging.info("Preparing to create score result with data:")
            for key, value in data.items():
                self.logging.info(f"{key}: {truncate_dict_strings_inner(value)}")

            # Validate all required fields are present and not None
            required_fields = ['evaluationId', 'itemId', 'accountId', 'scorecardId', 'value', 'metadata']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                self.logging.error(f"Missing required fields: {', '.join(missing_fields)}")
                self.logging.error(f"Current data: {data}")
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            mutation = """
            mutation CreateScoreResult($input: CreateScoreResultInput!) {
                createScoreResult(input: $input) {
                    id
                    evaluationId
                    itemId
                    accountId
                    scorecardId
                    value
                    metadata
                    trace
                }
            }
            """
            
            variables = {
                "input": data
            }
            
            # Log the exact mutation and variables being sent
            logging.info("Sending GraphQL mutation:")
            logging.info(f"Mutation: {mutation}")
            logging.info("Variables:")
            for key, value in data.items():
                logging.info(f"{key}: {value}")
            
            # Execute the API call in a non-blocking way
            response = await asyncio.to_thread(self.dashboard_client.execute, mutation, variables)
            
            # Check for GraphQL errors in the response
            if 'errors' in response:
                error_messages = [error.get('message', 'Unknown error') for error in response.get('errors', [])]
                error_str = '; '.join(error_messages)
                logging.error(f"GraphQL errors creating score result: {error_str}")
                logging.error(f"Full error response: {response['errors']}")
                raise Exception(f"Failed to create score result: {error_str}")
            
            if not response.get('createScoreResult'):
                logging.error(f"No data returned from createScoreResult mutation. Full response: {response}")
                raise Exception("Failed to create score result - no data returned")
            
            # Log the successful response
            logging.debug("Successfully created score result:")
            logging.debug(f"Response: {truncate_dict_strings_inner(response)}")
            
        except Exception as e:
            logging.error(f"Error creating score result: {e}")
            logging.error(f"Error details:", exc_info=True)
            raise

    async def _create_or_upsert_item(self, *, content_id, score_result, result):
        """Create or update an Item record for the given content_id."""
        try:
            # First, check if an item with this externalId already exists for this account
            query = """
            query GetItemByAccountAndExternalId($accountId: String!, $externalId: String!) {
                listItems(filter: {accountId: {eq: $accountId}, externalId: {eq: $externalId}}, limit: 1) {
                    items {
                        id
                    }
                }
            }
            """
            
            variables = {
                "accountId": self.account_id,
                "externalId": content_id
            }
            
            logging.info(f"Checking if item exists with externalId: {content_id}")
            response = await asyncio.to_thread(self.dashboard_client.execute, query, variables)
            
            existing_items = response.get('listItems', {}).get('items', [])
            
            if existing_items:
                # Item exists, we'll update it
                item_id = existing_items[0]['id']
                logging.info(f"Found existing item with id: {item_id}, will update")
                
                # Update the item with latest information
                mutation = """
                mutation UpdateItem($input: UpdateItemInput!) {
                    updateItem(input: $input) {
                        id
                        externalId
                    }
                }
                """
                
                # Extract description from metadata if available
                description = ""
                if score_result.metadata and 'text' in score_result.metadata:
                    # Truncate long text for description
                    description = score_result.metadata['text'][:200] + "..." if len(score_result.metadata['text']) > 200 else score_result.metadata['text']
                
                update_variables = {
                    "input": {
                        "id": item_id,
                        "updatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                        "description": description,
                        "evaluationId": self.experiment_id
                    }
                }
                
                await asyncio.to_thread(self.dashboard_client.execute, mutation, update_variables)
                logging.info(f"Successfully updated item: {item_id}")
                
            else:
                # Item doesn't exist, create a new one
                logging.info(f"No existing item found with externalId: {content_id}, creating new item")
                
                mutation = """
                mutation CreateItem($input: CreateItemInput!) {
                    createItem(input: $input) {
                        id
                        externalId
                    }
                }
                """
                
                # Extract description from metadata if available
                description = ""
                if score_result.metadata and 'text' in score_result.metadata:
                    # Truncate long text for description
                    description = score_result.metadata['text'][:200] + "..." if len(score_result.metadata['text']) > 200 else score_result.metadata['text']
                
                # Get score name if available
                score_name = score_result.parameters.name if hasattr(score_result, 'parameters') and hasattr(score_result.parameters, 'name') else ""
                
                # Determine if this is an evaluation item
                is_evaluation = self.experiment_id is not None
                
                create_variables = {
                    "input": {
                        "externalId": content_id,
                        "description": description,
                        "accountId": self.account_id,
                        "evaluationId": self.experiment_id,
                        "isEvaluation": is_evaluation
                    }
                }
                
                # Remove None values
                create_variables["input"] = {k: v for k, v in create_variables["input"].items() if v is not None}
                
                await asyncio.to_thread(self.dashboard_client.execute, mutation, create_variables)
                logging.info(f"Successfully created new item with externalId: {content_id}")
                
        except Exception as e:
            logging.error(f"Error creating/upserting item: {e}")
            logging.error("Error details:", exc_info=True)
            # We'll continue with score result creation even if item creation fails

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
            self.logging.debug("Cleanup error details:", exc_info=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__aexit__(exc_type, exc_val, exc_tb))

class ConsistencyEvaluation(Evaluation):
    def __init__(self, *, number_of_times_to_sample_each_text, **kwargs):
        super().__init__(**kwargs)
        self.number_of_times_to_sample_each_text = number_of_times_to_sample_each_text
    
    def log_parameters(self):
        super().log_parameters()
        mlflow.log_param("number_of_times_to_sample_each_text", self.number_of_times_to_sample_each_text)

class AccuracyEvaluation(Evaluation):
    def __init__(self, *, override_folder: str, labeled_samples: list = None, labeled_samples_filename: str = None, score_id: str = None, score_version_id: str = None, visualize: bool = False, task_id: str = None, evaluation_id: str = None, account_id: str = None, scorecard_id: str = None, **kwargs):
        # Store scorecard_id before calling super().__init__
        self.scorecard_id = scorecard_id
        super().__init__(**kwargs)
        self.override_folder = override_folder
        self.labeled_samples = labeled_samples
        self.labeled_samples_filename = labeled_samples_filename
        self.score_id = score_id
        
        # Validate score_id format - should be a UUID with hyphens
        if self.score_id and not (isinstance(self.score_id, str) and '-' in self.score_id):
            self.logging.warning(f"WARNING: Score ID doesn't appear to be in DynamoDB UUID format: {self.score_id}")
            self.logging.warning(f"This may cause issues with Evaluation records. Expected format is UUID with hyphens.")
        
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
                                    
                                    self.logging.info(f"Loaded override data for score '{score_name}' from {item_list_filename}: {len([r for r in df.iterrows() if pd.notna(r[1][form_id_col])])} records")
                                else:
                                    self.logging.warning(f"CSV column '{csv_column}' not found in {item_list_filename}")
                    
                    except Exception as e:
                        self.logging.warning(f"Failed to load override data from {item_list_filename}: {e}")
            
            if self.override_data:
                total_overrides = sum(len(scores) for scores in self.override_data.values())
                self.logging.info(f"Loaded {total_overrides} override entries for {len(self.override_data)} form IDs")
            else:
                self.logging.info("No override data loaded from CSV files")
                
        except Exception as e:
            self.logging.warning(f"Failed to load override data: {e}")

    async def run(self, tracker, progress_callback=None, dry_run=False):
        # --- BEGIN NEW LOGGING ---
        print("\n\n--- AccuracyEvaluation run CALLED ---\n\n")
        self.logging.info("--- AccuracyEvaluation run CALLED ---")
        # --- END NEW LOGGING ---

        """Modified run method to accept tracker argument"""
        self.progress_callback = progress_callback
        
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
        
        # Update the evaluation record with scorecard and score IDs
        if self.dashboard_client and not dry_run:
            update_data = {}
            if self.scorecard_id:
                update_data['scorecardId'] = self.scorecard_id
            
            if self.score_id:
                # Validate score_id format - should be a UUID with hyphens
                if not (isinstance(self.score_id, str) and '-' in self.score_id):
                    self.logging.warning(f"WARNING: Score ID doesn't appear to be in DynamoDB UUID format: {self.score_id}")
                    self.logging.warning(f"This will cause issues with Evaluation records. Expected format is UUID with hyphens.")
                    self.logging.warning(f"Will not add this Score ID to the evaluation record update.")
                else:
                    update_data['scoreId'] = self.score_id
            
            if hasattr(self, 'score_version_id') and self.score_version_id:
                update_data['scoreVersionId'] = self.score_version_id
            
            if update_data:
                try:
                    self.logging.info(f"Updating evaluation record {self.experiment_id} with: {update_data}")
                    mutation = """mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                        updateEvaluation(input: $input) {
                            id
                            scorecardId
                            scoreId
                            scoreVersionId
                        }
                    }"""
                    self.dashboard_client.execute(mutation, {
                        'input': {
                            'id': self.experiment_id,
                            **update_data
                        }
                    })
                    self.logging.info("Successfully updated evaluation record with scorecard and score IDs")
                except Exception as e:
                    self.logging.error(f"Failed to update evaluation record with IDs: {str(e)}")
                    # Continue execution even if update fails
        elif dry_run:
            self.logging.info(f"[DRY RUN] Would update evaluation record with scorecard ID: {self.scorecard_id} and score ID: {self.score_id}")

        try:
            # --- BEGIN NEW LOGGING ---
            self.logging.info("--- Calling _run_evaluation from AccuracyEvaluation.run ---")
            # --- END NEW LOGGING ---
            returned_metrics = await self._run_evaluation(tracker)
            # --- BEGIN NEW LOGGING ---
            self.logging.info(f"--- _run_evaluation returned: {returned_metrics} ---")
            # --- END NEW LOGGING ---
            return returned_metrics
        except Exception as e:
            self.logging.error(f"Error during AccuracyEvaluation.run: {e}", exc_info=True)
            raise e # Re-raise after logging
        finally:
            # --- BEGIN NEW LOGGING ---
            self.logging.info("--- Exiting AccuracyEvaluation.run (finally block) ---") 
            # --- END NEW LOGGING ---
            self.should_stop = True

    async def _run_evaluation(self, tracker):
        try:
            # Load the labeled samples
            import pandas as pd
            if self.labeled_samples:
                df = pd.DataFrame(self.labeled_samples)
            else:
                df = pd.read_csv(self.labeled_samples_filename)

            # Adjust the sample size if necessary
            self.number_of_texts_to_sample = min(len(df), self.requested_sample_size)
            self.logging.info(f"Adjusted sample size from {self.requested_sample_size} to {self.number_of_texts_to_sample} based on available data")

            # Sample rows based on the sampling method
            if self.sampling_method == 'random':
                selected_sample_rows = df.sample(n=self.number_of_texts_to_sample, random_state=self.random_seed)
            elif self.sampling_method == 'sequential':
                selected_sample_rows = df.head(self.number_of_texts_to_sample)
            else:
                selected_sample_rows = df

            # Update tracker status without advancing stage
            tracker.current_stage.status_message = "Generating predictions..."
            tracker.update(current_items=0)

            # Process all scores concurrently
            score_tasks = []
            for score_name in self.score_names():
                task = asyncio.create_task(self.score_all_texts_for_score(selected_sample_rows, score_name, tracker))
                score_tasks.append(task)

            all_results = await asyncio.gather(*score_tasks)
            self.all_results = [result for score_results in all_results for result in score_results if not isinstance(result, Exception)]

            # --- BEGIN NEW LOGGING ---
            self.logging.info(f"--- Calling calculate_metrics from _run_evaluation with {len(self.all_results)} results ---")
            # --- END NEW LOGGING ---
            
            # Reset counters and mismatches
            self.total_correct = 0
            self.total_questions = 0
            self.mismatches = []
            
            # Count the number correct out of all questions and collect mismatches
            for result in self.all_results:
                for question in self.score_names():
                    score_result = next((r for r in result['results'].values() if r.parameters.name == question), None)
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

            # --- BEGIN NEW LOGGING ---
            self.logging.info(f"--- calculate_metrics from _run_evaluation returned: {metrics} ---")
            # --- END NEW LOGGING ---

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
                
                score_instance = Score.from_name(self.scorecard_name, primary_score_name)
                
                # Calculate overall_accuracy from the counters we just updated
                overall_accuracy = (self.total_correct / self.total_questions * 100) if self.total_questions > 0 else 0
                
                report = self.generate_report(score_instance, overall_accuracy, expenses, self.number_of_texts_to_sample)
                print("\n" + report + "\n")

            return metrics
        except Exception as e:
            self.logging.error(f"Error in _run_evaluation: {e}", exc_info=True)
            raise e
        finally:
            pass

