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
import string
import pprint
import asyncio
from decimal import Decimal
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, wait_fixed, stop_after_attempt, before_log, retry_if_exception_type
from requests.exceptions import Timeout, RequestException
import mlflow
from concurrent.futures import ThreadPoolExecutor

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

from sklearn.metrics import confusion_matrix

class Experiment:
    def __init__(self, *,
        scorecard_name: str,
        scorecard: Scorecard,
        labeled_samples_filename: str = None,
        labeled_samples: list = None,
        number_of_texts_to_sample = 1,
        sampling_method = 'random',
        random_seed = None,
        session_ids_to_sample = None,
        subset_of_score_names = None,
        experiment_label = None,
        max_mismatches_to_report=5
    ):
        self.scorecard_name = scorecard_name
        self.scorecard = scorecard
        self.labeled_samples_filename = labeled_samples_filename
        self.labeled_samples = labeled_samples
        self.number_of_texts_to_sample = number_of_texts_to_sample
        self.sampling_method = sampling_method
        self.random_seed = random_seed
        
        # Parse lists, if available.
        self.session_ids_to_sample = session_ids_to_sample
        self.subset_of_score_names = subset_of_score_names

        self.experiment_label = experiment_label
        self.max_mismatches_to_report = max_mismatches_to_report
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

    @staticmethod
    def time_execution(func):
        def wrapper(self, *args, **kwargs):
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
        return wrapper

    @abstractmethod
    def run(self):
        pass

class AccuracyExperiment(Experiment):
    def __init__(self, *, override_folder=None, labeled_samples=None, labeled_samples_filename=None, **kwargs):
        super().__init__(**kwargs)
        self.scorecard_name = kwargs.get('scorecard_name')
        self.override_folder = override_folder
        self.override_data = self.load_override_data() if self.override_folder else {}
        self.labeled_samples = labeled_samples
        self.labeled_samples_filename = labeled_samples_filename

    def load_override_data(self):
        override_data = {}
        if os.path.exists(self.override_folder):
            for filename in os.listdir(self.override_folder):
                if filename.endswith(".csv"):
                    filepath = os.path.join(self.override_folder, filename)
                    try:
                        df = pd.read_csv(filepath, keep_default_na=False)  # Prevents automatic conversion of "NA" to NaN
                        for _, row in df.iterrows():
                            session_id = row['session_id']
                            question_name = row['question_name'].strip()
                            correct_value = row['correct_value'].strip()
                            if correct_value:  # Ignore rows where correct_value is an empty string
                                if session_id not in override_data:
                                    override_data[session_id] = {}
                                override_data[session_id][question_name] = correct_value
                    except Exception as e:
                        print(f"Could not read {filepath}: {e}")
        return override_data

    @Experiment.time_execution
    def run(self):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._async_run())

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
        logging.info(f"CSV file loaded into DataFrame: {self.labeled_samples_filename}")
        logging.info(f"  DataFrame shape: {df.shape}")
        logging.info(f"  DataFrame columns: {df.columns}")
        logging.info(f"  DataFrame head: {df.head()}")

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
        results = await self.score_all_texts(selected_sample_rows)
        
        if not os.path.exists(report_folder_path):
            os.makedirs(report_folder_path)

        logging.info("Logging scorecard results as an artifact in MLFlow.")
        scorecard_results = ScorecardResults(results)
        scorecard_results.save_to_file(f"{report_folder_path}/scorecard_results.json")
        mlflow.log_artifact(f"{report_folder_path}/scorecard_results.json")

        logging.info("Scoring completed.")

        # Count the number correct out of all questions.
        for result in results:
            logging.info(f"Form ID: {result['form_id']}")
            for question in self.score_names():
                score_result = next((result for result in result['results'].values() if result.parameters.name == question), None)
                score_value = str(score_result.value).lower() if score_result else None
                human_label = str(score_result.metadata['human_label']).lower() if score_result else None
                logging.info(f"Question: {question}, score Label: {score_value}, Human Label: {human_label}")
                is_match = 1 if score_result and score_result.metadata.get('correct', False) else 0
                self.total_correct += is_match
                self.total_questions += 1

                if not is_match and len(self.mismatches) < self.max_mismatches_to_report:
                    self.mismatches.append({
                        'form_id': result['form_id'],
                        'question': question,
                        'predicted': score_value,
                        'ground_truth': human_label,
                        'explanation': score_result.explanation if score_result else None,
                        'transcript': score_result.metadata['text']
                    })

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
                html_report_content = analysis.generate_html_report(expenses=expenses)
                with open(f"{report_folder_path}/scorecard_report.html", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact(f"{report_folder_path}/scorecard_report.html")
            except Exception as e:
                logging.error(f"Failed to log HTML report: {e}")

        def log_incorrect_scores_report():
            try:
                html_report_content = analysis.generate_html_report(only_incorrect_scores=True, expenses=expenses)
                with open(f"{report_folder_path}/scorecard_report_incorrect_scores.html", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact(f"{report_folder_path}/scorecard_report_incorrect_scores.html")
            except Exception as e:
                logging.error(f"Failed to log incorrect scores report: {e}")

        def log_no_costs_report():
            try:
                html_report_content = analysis.generate_html_report(redact_cost_information=True)
                with open(f"{report_folder_path}/scorecard_report_no_costs.html", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact(f"{report_folder_path}/scorecard_report_no_costs.html")
            except Exception as e:
                logging.error(f"Failed to log no costs report: {e}")

        def log_scorecard_costs():
            try:
                analysis.plot_scorecard_costs(results=results)
                mlflow.log_artifact(f"{report_folder_path}/scorecard_input_output_costs.png")
                mlflow.log_artifact(f"{report_folder_path}/histogram_of_total_costs.png")
                mlflow.log_artifact(f"{report_folder_path}/distribution_of_input_costs.png")
                mlflow.log_artifact(f"{report_folder_path}/total_llm_calls_by_score.png")
                mlflow.log_artifact(f"{report_folder_path}/distribution_of_input_costs_by_element_type.png")
            except Exception as e:
                logging.error(f"Failed to log scorecard costs: {e}")

        def log_csv_report():
            try:
                with open(f"{report_folder_path}/scorecard_report_for_incorrect_results.csv", "w") as file:
                    file.write(analysis.generate_csv_scorecard_report(results=results))
                mlflow.log_artifact(f"{report_folder_path}/scorecard_report_for_incorrect_results.csv")
            except Exception as e:
                logging.error(f"Failed to log CSV report: {e}")

        def log_question_accuracy_csv():
            try:
                analysis.generate_question_accuracy_csv(output_file=f"{report_folder_path}/question_accuracy_report.csv")
                mlflow.log_artifact(f"{report_folder_path}/question_accuracy_report.csv")
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
        self.generate_excel_report(report_folder_path, results)

        logging.info(f"Expenses: {expenses}")
        logging.info(f"{overall_accuracy:.1f}% accuracy / {len(selected_sample_rows)} samples")
        logging.info(f"cost: ${expenses['cost_per_text']:.6f} per call / ${expenses['total_cost']:.6f} total")

        report = self.generate_report(score_instance, overall_accuracy, expenses, len(selected_sample_rows))
        logging.info(report)

        await asyncio.to_thread(self.generate_and_log_confusion_matrix, results, report_folder_path)
        
        for question in self.score_names():
            self.create_performance_visualization(results, question, report_folder_path)

        self.generate_metrics_json(report_folder_path, len(selected_sample_rows), expenses)

    def generate_report(self, score_instance, overall_accuracy, expenses, sample_size):
        score_config = score_instance.parameters

        report = f"""
Experiment Report:
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

        metrics_file_path = f"{report_folder_path}/metrics.json"
        with open(metrics_file_path, 'w') as f:
            json.dump(metrics, f, indent=2)

        mlflow.log_artifact(metrics_file_path)
        logging.info(f"Metrics JSON file generated at {metrics_file_path}")

        for key, value in metrics.items():
            if key in ["overall_accuracy", "cost_per_call", "total_cost"]:
                mlflow.log_metric(key, float(value))
            else:
                mlflow.log_metric(key, value)

    async def score_all_texts(self, selected_sample_rows):
        tasks = [self.score_text(row) for _, row in selected_sample_rows.iterrows()]
        results = await asyncio.gather(*tasks)
        return results

    # Function to classify a single text and collect metrics
    @retry(
        wait=wait_fixed(2),          # wait 2 seconds between attempts
        stop=stop_after_attempt(5),  # stop after 5 attempts
        before=before_log(logging.getLogger(), logging.INFO),       # log before retry
        retry=retry_if_exception_type((Timeout, RequestException))  # retry on specific exceptions
    )
    async def score_text(self, row):
        logging.info("Scoring text...")

        text = row['text']
        content_id = row.get('content_id', '')
        session_id = row.get('Session ID', content_id)
        columns = row.get('columns', {})
        form_id = columns.get('form_id', '')
        metadata_string = columns.get('metadata', {})
        
        # Check if metadata_string is already a dict, if not, try to parse it
        if isinstance(metadata_string, dict):
            metadata = metadata_string
        else:
            try:
                metadata = json.loads(metadata_string)
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse metadata as JSON. Using empty dict. Metadata: {metadata_string}")
                metadata = {}

        logging.info(f"Processing text for content_id: {content_id}, session_id: {session_id}, form_id: {form_id}")

        scorecard_results = await self.scorecard.score_entire_text(
            text=text,
            metadata=metadata,
            subset_of_score_names=self.score_names_to_process()
        )

        # Extract human labels for each question from the DataFrame row
        human_labels = {}
        for score_identifier in scorecard_results.keys():
            score_instance = Score.from_name(
                self.scorecard.properties['id'], score_identifier)
            label_score_name = score_instance.get_label_score_name()
            label_column = label_score_name + '_label'
            if label_column in row.index:
                human_labels[score_identifier] = row[label_column]
            elif label_score_name in row.index:
                human_labels[score_identifier] = row[label_score_name]
            else:
                logging.warning(f"Neither '{score_identifier}' nor '{label_score_name}' found in the row. Available columns: {row.index.tolist()}")
                human_labels[score_identifier] = 'N/A'

        for score_identifier in scorecard_results.keys():
            try:
                score_result = scorecard_results[score_identifier]

                # Normalize the score result value for comparison
                score_result_value = score_result.value.strip().lower()
                if not score_result_value:
                    score_result_value = 'na'

                # Apply overrides if available
                if session_id in self.override_data:
                    for override_question_name, correct_value in self.override_data[session_id].items():
                        if override_question_name in human_labels:
                            logging.info(f"OVERRIDING human label for question '{override_question_name}' in session '{session_id}' from '{human_labels[override_question_name]}' to '{correct_value}'")
                            human_labels[override_question_name] = correct_value

                column_name = score_identifier
                human_label = str(human_labels[column_name]).lower().rstrip('.!?')
                if human_label == 'nan':
                    human_label = 'na'

                score_result.metadata['human_label'] = human_label
                score_result.metadata['correct'] = score_result_value == human_label

                # Log warnings for mismatches and append to incorrect results
                if not score_result.metadata['correct']:
                    logging.warning(f"Human label '{human_label}' does not match score '{score_result_value}' for question '{score_identifier}' in session '{session_id}'")

                # Also, add the full text to the score result.
                score_result.metadata['text'] = text

                logging.debug(f"Score result for {score_identifier}: {score_result}")

            except Exception as e:
                logging.exception(f"Error processing {score_identifier}: {e}")
                # Log the full response if it's an HTTPError
                if isinstance(e, requests.exceptions.HTTPError):
                    logging.error(f"HTTPError: {e.response.text}")

                score_result = Score.Result(value="Error", error=str(e))

        return {
            'content_id': content_id,
            'session_id': session_id,
            'form_id': form_id,
            'results': scorecard_results,
            'human_labels': human_labels
        }

    def generate_csv_scorecard_report(self, *, results):
        report = "session_id,question_name,human_label,result_value,correct_value\n"

        for result in results:
            report += f"{result['session_id']}, {result['question_name']}, {result['human_label']}, {result['result']['value']}, ,\n"
        
        return report

    def generate_excel_report(self, report_folder_path, results):
        records = []
        score_names = self.score_names()
        all_score_names = "_".join(score_names).replace(" ", "_")
        filename_safe_score_names = "".join(c for c in all_score_names if c.isalnum() or c in "_-")
        for result in results:
            for question in score_names:
                score_result = next((result for result in result['results'].values() if result.parameters.name == question), None)
                match = score_result.metadata['correct']
                records.append({
                    'report_id': result['session_id'],
                    'form_id': result['form_id'],
                    'question_name': question,
                    'human_label': score_result.metadata['human_label'],
                    'predicted_answer': score_result.value,
                    'match': match,
                    'reasoning': score_result.explanation,
                    'original_text': score_result.metadata['text'],
                })

        df_records = pd.DataFrame(records)
        excel_file_path = f"{report_folder_path}/Evaluation Report for {filename_safe_score_names}.xlsx"
        df_records.to_excel(excel_file_path, index=False)
        mlflow.log_artifact(excel_file_path)

        logging.info(f"Excel report generated at {excel_file_path}")

    def generate_and_log_confusion_matrix(self, results, report_folder_path):
        for question in self.score_names():
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

            cm_path = f"{report_folder_path}/confusion_matrix_{question.replace(' ', '_')}.png"
            plt.savefig(cm_path, bbox_inches='tight', dpi=600)
            plt.close()

            mlflow.log_artifact(cm_path)

    def create_performance_visualization(self, results, question, report_folder_path):
        
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
        
        plt.savefig(f"{report_folder_path}/performance_{question.replace(' ', '_')}.png", bbox_inches='tight', dpi=600)
        plt.close()
        
        mlflow.log_artifact(f"{report_folder_path}/performance_{question.replace(' ', '_')}.png")
        
class ConsistencyExperiment(Experiment):
    def __init__(self, *, number_of_times_to_sample_each_text, **kwargs):
        super().__init__(**kwargs)
        self.number_of_times_to_sample_each_text = number_of_times_to_sample_each_text
    
    def log_parameters(self):
        super().log_parameters()
        mlflow.log_param("number_of_times_to_sample_each_text", self.number_of_times_to_sample_each_text)
