import os
import math
import yaml
import json
import copy
import base64
import pandas as pd
import logging
import requests
import random
import time
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

from plexus.scores.LangGraphScore import LangGraphScore, BatchProcessingPause

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
        visualize: bool = False
    ):
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
        
        # Parse lists, if available.
        self.session_ids_to_sample = session_ids_to_sample
        self.subset_of_score_names = subset_of_score_names

        self.experiment_label = experiment_label
        self.max_mismatches_to_report = max_mismatches_to_report

        # Results tracking - separate results by score
        self.results_by_score = {}  # Dictionary to store results for each score
        self.processed_items_by_score = {}  # Track processed items per score
        self.all_results = []  # Keep this for backwards compatibility
        self.processed_items = 0
        self.mismatches = []
        self.total_correct = 0
        self.total_questions = 0

        # Initialize dashboard client and experiment ID
        try:
            logging.info("Initializing Plexus Dashboard client...")
            self.dashboard_client = PlexusDashboardClient.for_account(account_key)
            
            # Look up account using default key
            logging.info(f"Looking up account with key: {account_key}")
            account = Account.get_by_key(account_key, self.dashboard_client)
            logging.info(f"Found account: {account.name} ({account.id})")
            
            # Store the account ID
            self.account_id = account.id
            
            # Look up scorecard using available identifiers
            logging.info(f"Looking up scorecard with name: {self.scorecard.name}")
            if hasattr(self.scorecard, 'key'):
                logging.info(f"Using scorecard key: {self.scorecard.key}")
                scorecard = DashboardScorecard.get_by_key(self.scorecard.key, self.dashboard_client)
            elif hasattr(self.scorecard, 'id'):
                logging.info(f"Using scorecard ID: {self.scorecard.id}")
                scorecard = DashboardScorecard.get_by_id(self.scorecard.id, self.dashboard_client)
            else:
                logging.info(f"Looking up scorecard by name: {self.scorecard.name}")
                scorecard = DashboardScorecard.get_by_name(self.scorecard.name, self.dashboard_client)
            logging.info(f"Found scorecard: {scorecard.name} ({scorecard.id})")
            
            # Store the scorecard ID
            self.scorecard_id = scorecard.id

            # Create initial experiment params
            started_at = datetime.now(timezone.utc)
            experiment_params = {
                "type": "accuracy",
                "accountId": account.id,
                "scorecardId": scorecard.id,
                "status": "RUNNING",
                "accuracy": 0.0,
                "createdAt": started_at.isoformat().replace('+00:00', 'Z'),
                "updatedAt": started_at.isoformat().replace('+00:00', 'Z'),
                "totalItems": self.number_of_texts_to_sample,
                "processedItems": 0,
                "parameters": json.dumps({
                    "sampling_method": self.sampling_method,
                    "sample_size": self.number_of_texts_to_sample
                }),
                "startedAt": started_at.isoformat().replace('+00:00', 'Z'),
                "estimatedRemainingSeconds": self.number_of_texts_to_sample
            }

            # Look up score ID if we have a subset of score names
            if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
                score_name = self.subset_of_score_names[0]
                logging.info(f"Looking up score with name: {score_name}")
                try:
                    query = """
                    query GetScoreFromScorecard($scorecardId: ID!, $name: String!) {
                        getScorecard(id: $scorecardId) {
                            sections {
                                items {
                                    scores(filter: {name: {eq: $name}}) {
                                        items {
                                            id
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                    """
                    variables = {
                        "scorecardId": scorecard.id,
                        "name": score_name
                    }
                    result = self.dashboard_client.execute(query, variables)
                    logging.info(f"Raw API response: {result}")
                    
                    # Find the first score with matching name
                    matching_score = None
                    scorecard_data = result.get('getScorecard', {})
                    logging.info(f"Scorecard data: {scorecard_data}")
                    sections = scorecard_data.get('sections', {}).get('items', [])
                    logging.info(f"Sections: {sections}")
                    
                    for section in sections:
                        logging.info(f"Processing section: {section}")
                        scores = section.get('scores', {}).get('items', [])
                        logging.info(f"Found scores: {scores}")
                        if scores:  # If we have any scores
                            matching_score = scores[0]  # Take the first one since GraphQL already filtered
                            logging.info(f"Found matching score: {matching_score}")
                            break
                    
                    if matching_score:
                        self.score_id = matching_score['id']
                        logging.info(f"Found score: {matching_score['name']} ({self.score_id})")
                        experiment_params["scoreId"] = self.score_id
                        logging.info(f"Updated experiment_params with scoreId: {experiment_params}")
                    else:
                        logging.warning(f"Could not find score with name: {score_name} in scorecard: {scorecard.id}")
                        self.score_id = None
                except Exception as e:
                    logging.error(f"Error looking up score: {e}")
                    logging.error(f"Exception details: {type(e)}")
                    self.score_id = None
            else:
                self.score_id = score_id
                if self.score_id:
                    experiment_params["scoreId"] = self.score_id

            logging.info(f"Creating experiment with params: {experiment_params}")
            
            response = DashboardEvaluation.create(
                client=self.dashboard_client,
                **experiment_params
            )
            self.experiment_id = response.id
            self.started_at = started_at
            logging.info(f"Created dashboard experiment with ID: {self.experiment_id}")

        except Exception as e:
            logging.error(f"Failed to initialize dashboard client or create experiment: {str(e)}", exc_info=True)
            self.dashboard_client = None
            self.experiment_id = None

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
        """Log metrics to Plexus Dashboard with retry logic"""
        if not self.experiment_id:
            logging.warning("Experiment ID not available - skipping metrics update")
            return
        
        logging.info(f"Starting dashboard update for experiment {self.experiment_id}")
        
        try:
            elapsed_seconds = int((datetime.now(timezone.utc) - self.started_at).total_seconds())
            
            # Convert metrics to percentages for the dashboard
            metrics_list = [
                {"name": "Accuracy", "value": metrics["accuracy"] * 100},
                {"name": "Precision", "value": metrics["precision"] * 100},
                {"name": "Sensitivity", "value": metrics["sensitivity"] * 100},
                {"name": "Specificity", "value": metrics["specificity"] * 100}
            ]
            
            # Format confusion matrix data for the API
            confusion_matrix_data = metrics["confusion_matrices"][0]  # Get first score's matrix
            matrix_data = {
                "matrix": confusion_matrix_data["matrix"],
                "labels": confusion_matrix_data["labels"]
            }
            
            current_time = datetime.now(timezone.utc)
            
            # Calculate total items based on status
            if status == "COMPLETED":
                # For final update, use actual total from distribution data
                total_predictions = 0
                if metrics["predicted_distribution"]:
                    first_score = metrics["predicted_distribution"][0]["score"]
                    total_predictions = sum(item["count"] for item in metrics["predicted_distribution"] 
                                         if item["score"] == first_score)
            else:
                # During evaluation, use the initial sample size
                total_predictions = self.number_of_texts_to_sample
            
            update_params = {
                "id": self.experiment_id,
                "type": "accuracy",
                "metrics": json.dumps(metrics_list),
                "processedItems": self.processed_items,
                "totalItems": total_predictions,
                "elapsedSeconds": elapsed_seconds,
                "estimatedRemainingSeconds": int(elapsed_seconds * (total_predictions - self.processed_items) / self.processed_items) if self.processed_items > 0 else total_predictions,
                "accuracy": metrics["accuracy"] * 100,
                "updatedAt": current_time.isoformat().replace('+00:00', 'Z'),
                "status": status,
                "predictedClassDistribution": json.dumps(metrics["predicted_distribution"]),
                "datasetClassDistribution": json.dumps(metrics["actual_distribution"]),
                "confusionMatrix": json.dumps(matrix_data)
            }
            
            mutation = """
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
            
            variables = {
                "input": update_params
            }
            
            logging.info("Executing dashboard update...")
            # Execute the API call directly - no shield needed since we handle cancellation in the caller
            await asyncio.to_thread(self.dashboard_client.execute, mutation, variables)
            logging.info("Successfully completed dashboard update")
            
        except Exception as e:
            logging.error(f"Error updating dashboard experiment: {e}")
            raise

    def calculate_metrics(self, results):
        logging.info(f"\nStarting metrics calculation with {len(results)} results")
        predicted_distributions = {}
        actual_distributions = {}
        confusion_matrices = {}
        
        total_correct = 0
        total_predictions = 0
        
        # Get the primary score name - if we're evaluating a specific score, use that
        primary_score_name = None
        if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
            primary_score_name = self.subset_of_score_names[0]
        
        # First pass: build distributions and confusion matrices
        for result in results:
            logging.info(f"\nProcessing result for form_id: {result['form_id']}")
            
            for score_identifier, score_result in result['results'].items():
                # Skip if the score result is an error
                if isinstance(score_result.value, str) and score_result.value == "Error":
                    continue

                # Skip if this is a dependency score and not our primary score
                score_name = score_result.parameters.name
                if primary_score_name and score_name != primary_score_name:
                    logging.info(f"Skipping metrics for dependency score: {score_name}")
                    continue

                predicted = str(score_result.value).lower().strip()
                actual = str(score_result.metadata['human_label']).lower().strip()
                
                # Standardize empty or NA values
                predicted = 'na' if predicted in ['', 'nan', 'n/a', 'none', 'null'] else predicted
                actual = 'na' if actual in ['', 'nan', 'n/a', 'none', 'null'] else actual
                
                logging.info(f"Score: {score_name}")
                logging.info(f"Predicted: '{predicted}'")
                logging.info(f"Actual: '{actual}'")
                logging.info(f"Correct: {score_result.metadata['correct']}")
                
                # Update total correct and predictions - only for the primary score
                if score_result.metadata['correct']:
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

        # Calculate overall accuracy
        accuracy = total_correct / total_predictions if total_predictions > 0 else 0
        
        # For binary classification scores, calculate additional metrics
        precision = accuracy
        sensitivity = accuracy
        specificity = accuracy
        
        # If we have binary classification data (yes/no), calculate detailed metrics
        for score_name, matrix_data in confusion_matrices.items():
            labels = sorted(list(matrix_data['labels']))
            if len(labels) == 2 and 'yes' in labels and 'no' in labels:
                tp = matrix_data['matrix'].get('yes', {}).get('yes', 0)
                tn = matrix_data['matrix'].get('no', {}).get('no', 0)
                fp = matrix_data['matrix'].get('no', {}).get('yes', 0)
                fn = matrix_data['matrix'].get('yes', {}).get('no', 0)
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
                specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
                break  # Use the first binary score found for these metrics

        # Format confusion matrices for API
        formatted_confusion_matrices = []
        for score_name, matrix_data in confusion_matrices.items():
            labels = sorted(list(matrix_data['labels']))
            matrix = []
            
            # Initialize the matrix with zeros
            for _ in range(len(labels)):
                matrix.append([0] * len(labels))
            
            # Fill in the matrix values
            for i, actual_label in enumerate(labels):
                for j, predicted_label in enumerate(labels):
                    matrix[i][j] = matrix_data['matrix'].get(actual_label, {}).get(predicted_label, 0)
            
            formatted_confusion_matrices.append({
                "score_name": score_name,
                "matrix": matrix,
                "labels": labels
            })
            
            # Log the confusion matrix for debugging
            logging.info(f"\nConfusion Matrix for {score_name}:")
            logging.info(f"Labels: {labels}")
            for i, row in enumerate(matrix):
                logging.info(f"{labels[i]}: {row}")

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
        if not formatted_confusion_matrices:
            formatted_confusion_matrices.append({
                "score_name": primary_score_name or self.score_names()[0],
                "matrix": [[0, 0], [0, 0]],
                "labels": ['yes', 'no']
            })
        
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

        logging.info("\nCalculated metrics:")
        logging.info(f"Total predictions: {total_predictions}")
        logging.info(f"Total correct: {total_correct}")
        logging.info(f"Accuracy: {accuracy}")
        logging.info(f"Precision: {precision}")
        logging.info(f"Sensitivity: {sensitivity}")
        logging.info(f"Specificity: {specificity}")
        logging.info(f"Predicted distributions: {predicted_label_distributions}")
        logging.info(f"Actual distributions: {actual_label_distributions}")

        return {
            "accuracy": accuracy,
            "precision": precision,
            "sensitivity": sensitivity,
            "specificity": specificity,
            "predicted_distribution": predicted_label_distributions,
            "actual_distribution": actual_label_distributions,
            "confusion_matrices": formatted_confusion_matrices
        }

    async def _async_run(self):
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

    async def score_all_texts_for_score(self, selected_sample_rows, score_name: str):
        """Score all texts for a specific score concurrently"""
        if score_name not in self.results_by_score:
            self.results_by_score[score_name] = []
        if score_name not in self.processed_items_by_score:
            self.processed_items_by_score[score_name] = 0

        tasks = []
        total_rows = len(selected_sample_rows)
        for idx, (_, row) in enumerate(selected_sample_rows.iterrows()):
            task = asyncio.create_task(self.score_text(row, score_name))
            tasks.append(task)
        
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result:
                    self.results_by_score[score_name].append(result)
                    self.processed_items_by_score[score_name] += 1
                    self.processed_items = sum(self.processed_items_by_score.values())
                    # Start metrics task if needed
                    is_final_result = self.processed_items_by_score[score_name] == total_rows
                    await self.maybe_start_metrics_task(score_name, is_final_result)
            except Exception as e:
                logging.error(f"Error scoring text for {score_name}: {e}")
                raise
        
        return self.results_by_score[score_name]

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
        while not self.should_stop:
            try:
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
                    
                    # Create a task for the API call and shield it from cancellation
                    api_task = asyncio.shield(self.log_to_dashboard(metrics, status=status))
                    try:
                        await api_task
                        last_processed_count = current_count
                    except asyncio.CancelledError:
                        # If we're cancelled, still wait for the API call to finish
                        logging.info("Metrics task cancelled, ensuring API call completes")
                        try:
                            await api_task
                        except asyncio.CancelledError:
                            pass  # Ignore any additional cancellations
                        logging.info("API call completed after cancellation")
                        return  # Exit the task
                
                # Wait a bit before checking again
                await asyncio.sleep(.1)
            except asyncio.CancelledError:
                logging.info(f"Metrics computation for {score_name} cancelled")
                return  # Exit gracefully
            except Exception as e:
                logging.error(f"Error in continuous metrics computation for {score_name}: {e}")
                await asyncio.sleep(5)  # Wait longer on error

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
                        score_instance = Score.from_name(self.scorecard.name, score_identifier)
                        label_score_name = score_instance.get_label_score_name()
                        score_name = score_instance.parameters.name

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
                        score_result = Score.Result(
                            value="Error", 
                            error=str(e),
                            parameters=Score.Parameters(
                                name=score_identifier,
                                scorecard=self.scorecard_name
                            )
                        )

                # Remove the result accumulation from here since it's now handled in _async_run
                if has_processed_scores:
                    self.processed_items += 1

                return result

            except (Timeout, RequestException) as e:
                if attempt == max_attempts - 1:  # Last attempt
                    raise  # Re-raise the last error
                
                # Calculate exponential backoff delay
                delay = min(base_delay * (2 ** attempt), max_delay)
                logging.info(f"Attempt {attempt + 1} failed with error: {e}. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)

    async def _create_score_result(self, *, score_result, content_id, result):
        """Create a score result in the dashboard."""
        try:
            # Log the raw inputs
            logging.info("Creating score result with raw inputs:")
            logging.info(f"score_result value: {score_result.value}")
            logging.info(f"score_result metadata: {score_result.metadata}")
            logging.info(f"content_id: {content_id}")
            logging.info(f"result dict: {result}")

            # Create ScoreResult in a non-blocking way
            data = {
                'evaluationId': self.experiment_id,
                'itemId': result['form_id'],  # Using form_id as the itemId
                'accountId': self.account_id,
                'scorecardId': self.scorecard_id,
                'value': str(score_result.value),
                'metadata': json.dumps({
                    'item_id': result['form_id'],
                    'results': {
                        score_result.parameters.name: {
                            'value': str(score_result.value),
                            'confidence': None,
                            'explanation': score_result.metadata.get('explanation'),
                            'metadata': {
                                'human_label': score_result.metadata.get('human_label'),
                                'correct': score_result.metadata.get('correct'),
                                'human_explanation': score_result.metadata.get('human_explanation'),
                                'text': score_result.metadata.get('text')
                            }
                        }
                    }
                })
            }

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
            logging.info(f"evaluationId: {data['evaluationId']}")
            logging.info(f"itemId: {data['itemId']}")
            logging.info(f"accountId: {data['accountId']}")
            logging.info(f"scorecardId: {data['scorecardId']}")
            logging.info(f"value: {data['value']}")
            logging.info(f"metadata: {data['metadata']}")
            
            # Execute the API call in a non-blocking way
            response = await asyncio.to_thread(self.dashboard_client.execute, mutation, variables)
            
            # Log the response
            logging.info("Received response from GraphQL:")
            logging.info(f"Response: {response}")
            
        except Exception as e:
            logging.error(f"Error creating score result: {e}")
            logging.error(f"Error details:", exc_info=True)
            raise

    async def cleanup(self):
        """Clean up all resources"""
        try:
            # Stop the metrics computation task
            self.should_stop = True
            if hasattr(self, 'metrics_tasks') and self.metrics_tasks:
                logging.info("Cleaning up metrics tasks...")
                for task in self.metrics_tasks.values():
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass  # Expected during cleanup
                        except Exception as e:
                            logging.error(f"Error cleaning up metrics task: {e}")
            
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
            logging.error(f"Error during {self.__class__.__name__} cleanup: {e}")
            logging.debug("Cleanup error details:", exc_info=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__aexit__(exc_type, exc_val, exc_tb))

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

class ConsistencyEvaluation(Evaluation):
    def __init__(self, *, number_of_times_to_sample_each_text, **kwargs):
        super().__init__(**kwargs)
        self.number_of_times_to_sample_each_text = number_of_times_to_sample_each_text
    
    def log_parameters(self):
        super().log_parameters()
        mlflow.log_param("number_of_times_to_sample_each_text", self.number_of_times_to_sample_each_text)

class AccuracyEvaluation(Evaluation):
    def __init__(self, *, override_folder=None, labeled_samples=None, labeled_samples_filename=None, score_id=None, visualize=False, **kwargs):
        super().__init__(**kwargs)
        self.scorecard_name = kwargs.get('scorecard_name')
        self.override_folder = override_folder
        self.override_data = self.load_override_data() if self.override_folder else {}
        self.labeled_samples = labeled_samples
        self.labeled_samples_filename = labeled_samples_filename
        self.score_id = score_id
        self.visualize = visualize
        self.results_queue = Queue()
        self.metrics_tasks = {}  # Dictionary to track metrics computation tasks per score
        self.should_stop = False
        self.completed_scores = set()  # Track which scores have completed all their results

    def load_override_data(self):
        override_data = {}
        if os.path.exists(self.override_folder):
            logging.info(f"Loading overrides from folder: {self.override_folder}")
            override_files = [f for f in os.listdir(self.override_folder) if f.endswith(".csv")]
            logging.info(f"Found {len(override_files)} override files")
            
            for filename in override_files:
                filepath = os.path.join(self.override_folder, filename)
                try:
                    df = pd.read_csv(filepath, keep_default_na=False)
                    logging.info(f"Processing {len(df)} rows from {filename}")
                    
                    for _, row in df.iterrows():
                        form_id = None
                        if 'form_id' in row:
                            form_id = row['form_id']
                        elif 'f_id' in row:
                            form_id = row['f_id']
                            
                        question_name = None
                        if 'question_name' in row:
                            question_name = row['question_name']
                        elif 'question' in row:
                            question_name = row['question']
                            
                        correct_value = None
                        if 'correct_value' in row:
                            correct_value = row['correct_value'].strip()
                        elif 'Spot Check Answer' in row:
                            correct_value = row['Spot Check Answer'].strip()
                            
                        if form_id and question_name and correct_value:
                            if form_id not in override_data:
                                override_data[form_id] = {}
                            override_data[form_id][question_name] = correct_value
                            
                    logging.info(f"Loaded {len(override_data)} form overrides from {filename}")
                except Exception as e:
                    logging.error(f"Failed to read override file {filepath}: {e}")
        else:
            logging.info(f"No override folder found at {self.override_folder}")
        return override_data

