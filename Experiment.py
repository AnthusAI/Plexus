import os
import json
import copy
import base64
import pandas as pd
import logging
import requests
import random
import time
import pprint
from decimal import Decimal
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, wait_fixed, stop_after_attempt, before_log, retry_if_exception_type
from requests.exceptions import Timeout, RequestException
import mlflow

import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

from graphviz import Digraph
from jinja2 import Template

from .CompositeScore import CompositeScore
from .ScoreResult import ScoreResult
from .Scorecard import Scorecard
from .ScorecardResults import ScorecardResults
from .ScorecardResultsAnalysis import ScorecardResultsAnalysis

class Experiment:
    def __init__(self, *,
        scorecard: Scorecard,
        labeled_samples_filename: str,
        number_of_transcripts_to_sample = 1,
        sampling_method = 'random',
        random_seed = None,
        session_ids_to_sample = None,
        subset_of_score_names = None
    ):
        self.scorecard = scorecard
        self.labeled_samples_filename = labeled_samples_filename
        self.number_of_transcripts_to_sample = number_of_transcripts_to_sample
        self.sampling_method = sampling_method
        self.random_seed = random_seed
        
        # Parse lists, if available.
        self.session_ids_to_sample = session_ids_to_sample
        self.subset_of_score_names = subset_of_score_names

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

        experiment_name = self.scorecard.__class__.name()
        if os.getenv('MLFLOW_EXPERIMENT_NAME'):
            experiment_name = experiment_name + " - " + os.getenv('MLFLOW_EXPERIMENT_NAME')
        mlflow.set_experiment(experiment_name)

        try:
            mlflow.start_run()
        except Exception as e:
            print("Error: ", e)
            print("Attempting to end the previous run and start a new one.")
            mlflow.end_run()
            mlflow.start_run()

        # Add notes about the run
        mlflow.set_tag("scorecard", self.scorecard.name())
        mlflow.set_tag("experiment_type", self.__class__.__name__)

        self.log_parameters()
    
    def log_parameters(self):
        mlflow.log_param("sampling_method", self.sampling_method)
        mlflow.log_param("number_of_transcripts_to_sample", self.number_of_transcripts_to_sample)

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
            time_per_transcript = execution_time / self.number_of_transcripts_to_sample if self.number_of_transcripts_to_sample else 0
            mlflow.log_metric("execution_time", execution_time)
            mlflow.log_metric("time_per_transcript", time_per_transcript)
            print(f"{func.__name__} executed in {execution_time:.2f} seconds.")
            print(f"Average time per transcript: {time_per_transcript:.2f} seconds.")
            return result
        return wrapper

    @abstractmethod
    def run(self):
        pass

class AccuracyExperiment(Experiment):
    def __init__(self, *, override_folder=None, **kwargs):
        super().__init__(**kwargs)
        self.override_folder = override_folder
        self.override_data = self.load_override_data() if self.override_folder else {}

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

        # Configure logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

        # Load the CSV file into a DataFrame
        df = pd.read_csv(self.labeled_samples_filename)
        logging.info(f"CSV file loaded into DataFrame: {self.labeled_samples_filename}")
        logging.info(f"  DataFrame shape: {df.shape}")
        logging.info(f"  DataFrame columns: {df.columns}")
        logging.info(f"  DataFrame head: {df.head()}")

        if hasattr(self, 'session_ids_to_sample') and self.session_ids_to_sample:
            selected_sample_rows = df[df['Session ID'].isin(self.session_ids_to_sample)]
        elif self.sampling_method == 'random':
            if hasattr(self, 'random_seed'):
                random.seed(self.random_seed)
            selected_sample_indices = random.sample(range(len(df)), self.number_of_transcripts_to_sample)
            selected_sample_rows = df.iloc[selected_sample_indices]
        elif self.sampling_method == 'all':
            selected_sample_rows = df
        else:
            selected_sample_rows = df.head(self.number_of_transcripts_to_sample)

        # Iterate over the randomly selected DataFrame rows and classify each transcript
        results = []
        max_thread_pool_size = 10

        # Create a thread pool executor
        with ThreadPoolExecutor(max_workers=max_thread_pool_size) as executor:
            # Submit tasks to the executor to score each transcript in parallel
            future_to_index = {
                executor.submit(self.score_transcript, row): index
                for index, row in selected_sample_rows.iterrows()
            }

            # Initialize counters outside of the loop
            total_correct = 0
            total_questions = 0
            heatmap_data = []
            annotations = []

            # Collect the results as they are completed
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                # try:
                result = future.result()
                logging.info(f"Transcript {index} classified.")
                logging.info(f"Result: {result}")
                results.append(result)
                # except Exception as e:
                #     logging.exception(f"Error processing transcript at index {index}: {e}")

        pretty_printer = pprint.PrettyPrinter()
        print("Final all scorecard results:\n")
        pretty_printer.pprint(results)

        if not os.path.exists("./tmp/"):
            os.makedirs("./tmp/")

        # Log the raw results data as an artifact in MLFlow.
        scorecard_results = ScorecardResults(results)
        scorecard_results.save_to_file("tmp/scorecard_results.json")
        mlflow.log_artifact("tmp/scorecard_results.json")

        logging.info("Scoring completed.")

        for result in results:
            logging.info(f"Session ID: {result['session_id']}")
            logging.info(f"   Results: {result['results']}")

        # Count the number correct out of all questions.
        for result in results:
            for question in self.score_names():
                score_label = str(result['results'][question].get('value', 'NA')).lower()
                human_label = str(result['results'][question].get('human_label', 'NA')).lower()
                logging.info(f"Question: {question}, score Label: {score_label}, Human Label: {human_label}")
                is_match = 1 if result['results'][question].get('correct', False) else 0
                total_correct += is_match
                total_questions += 1

        analysis = ScorecardResultsAnalysis(
            scorecard_results=scorecard_results
        )

        # Log the accuracy heatmap plot as an artifact in MLFlow
        analysis.plot_accuracy_heatmap()
        mlflow.log_artifact('tmp/accuracy_heatmap.png')

        # Generate an HTML report and log that in MLFlow, too.
        html_report_content = analysis.generate_html_report()
        with open("tmp/scorecard_report.html", "w") as file:
            file.write(html_report_content)
        mlflow.log_artifact("tmp/scorecard_report.html")

        # Only incorrect scores.
        html_report_content = analysis.generate_html_report(only_incorrect_scores=True)
        with open("tmp/scorecard_report_incorrect_scores.html", "w") as file:
            file.write(html_report_content)
        mlflow.log_artifact("tmp/scorecard_report_incorrect_scores.html")

        # Date menu: no costs.
        html_report_content = analysis.generate_html_report(redact_cost_information=True)
        with open("tmp/scorecard_report_no_costs.html", "w") as file:
            file.write(html_report_content)
        mlflow.log_artifact("tmp/scorecard_report_no_costs.html")

        # Plot costs and log in MLFlow.
        analysis.plot_scorecard_costs(results=results)
        mlflow.log_artifact('tmp/scorecard_input_output_costs.png')
        mlflow.log_artifact('tmp/histogram_of_total_costs.png')
        mlflow.log_artifact('tmp/distribution_of_input_costs.png')
        mlflow.log_artifact('tmp/total_llm_calls_by_score.png')
        mlflow.log_artifact('tmp/distribution_of_input_costs_by_element_type.png')

        expenses = self.scorecard.accumulated_expenses()
        logging.info(f"Expenses: {expenses}")

        expenses['cost_per_transcript'] = expenses['total_cost'] / len(selected_sample_rows)
        logging.info(f"Number of transcripts to sample: {len(selected_sample_rows)}")
        logging.info(f"Total cost: {expenses['total_cost']}")
        logging.info(f"Cost per transcript: {expenses['cost_per_transcript']}")

        # Calculate overall accuracy
        overall_accuracy = (total_correct / total_questions) * 100 if total_questions > 0 else 0
        logging.info(f"Overall accuracy: {overall_accuracy:.2f}%")
        mlflow.log_metric("overall_accuracy", overall_accuracy)

        # Log the results to MLflow
        mlflow.log_metric("number_of_transcripts", len(selected_sample_rows))
        mlflow.log_metric("number_of_scores", len(self.score_names()))
        mlflow.log_metric("total_cost", expenses['total_cost'])
        mlflow.log_metric("cost_per_transcript", expenses['cost_per_transcript'])

        # Write out a CSV of incorrect scores.
        with open("tmp/scorecard_report_for_incorrect_results.csv", "w") as file:
            file.write(analysis.generate_csv_scorecard_report(
                results=results))
        mlflow.log_artifact("tmp/scorecard_report_for_incorrect_results.csv")

    # Function to classify a single transcript and collect metrics
    @retry(
        wait=wait_fixed(2),          # wait 2 seconds between attempts
        stop=stop_after_attempt(5),  # stop after 5 attempts
        before=before_log(logging.getLogger(), logging.INFO),       # log before retry
        retry=retry_if_exception_type((Timeout, RequestException))  # retry on specific exceptions
    )
    def score_transcript(self, row):
        session_id = row['Session ID']
        transcript = row['Transcription']
        logging.info(f"Transcript content: {transcript}")
        
        # Some of our test data has escaped newlines, so we need to replace them with actual newlines.
        transcript = transcript.replace("\\n", "\n")

        logging.debug(f"Fixed transcript content: {transcript}")

        scorecard_results = self.scorecard.score_entire_transcript(
            transcript=transcript,
            subset_of_score_names=self.score_names_to_process()
        )

        # Extract human labels for each question from the DataFrame row
        human_labels = {question_name: row[question_name] for question_name in scorecard_results.keys()}

        for question_name in scorecard_results.keys():
            try:
                score_result = scorecard_results[question_name]

                # This is where we evaluate the score by comparing it against human labels.

                # Normalize the score result value for comparison
                score_result_value = str(score_result.get('value', 'na')).strip().lower()

                # Apply overrides if available
                if session_id in self.override_data:
                    for override_question_name, correct_value in self.override_data[session_id].items():
                        if override_question_name in human_labels:
                            logging.info(f"OVERRIDING human label for question '{override_question_name}' in session '{session_id}' from '{human_labels[override_question_name]}' to '{correct_value}'")
                            human_labels[override_question_name] = correct_value

                human_label = str(human_labels[question_name]).lower()
                if human_label == 'nan':
                    human_label = 'na'

                score_result['human_label'] = human_label
                score_result['correct'] = score_result_value == human_label

                # Log warnings for mismatches and append to incorrect results
                if not score_result['correct']:
                    logging.warning(f"Human label '{human_label}' does not match score '{score_result_value}' for question '{question_name}' in session '{session_id}'")

                # Also, add the full transcript to the score result.
                score_result['transcript'] = transcript

                logging.debug(f"Score result for {question_name}: {score_result}")

            except Exception as e:
                logging.exception(f"Error processing {question_name}: {e}")
                # Log the full response if it's an HTTPError
                if isinstance(e, requests.exceptions.HTTPError):
                    logging.error(f"HTTPError: {e.response.text}")

                score_result = ScoreResult(value="Error", error=str(e))

        # logging.info(f"Total score results: {len(self.all_score_results)}")
        # logging.info(f"Total incorrect score results: {len(self.incorrect_score_results)}")

        return {
            'session_id': session_id,
            'results': scorecard_results,
            'human_labels': human_labels
        }

    def generate_csv_scorecard_report(self, *, results):
        report = "session_id,question_name,human_label,result_value,correct_value\n"

        for result in results:
            report += f"{result['session_id']}, {result['question_name']}, {result['human_label']}, {result['result']['value']}, ,\n"
        
        return report

class ConsistencyExperiment(Experiment):
    def __init__(self, *, number_of_times_to_sample_each_transcript, **kwargs):
        super().__init__(**kwargs)
        self.number_of_times_to_sample_each_transcript = number_of_times_to_sample_each_transcript
    
    def log_parameters(self):
        super().log_parameters()
        mlflow.log_param("number_of_times_to_sample_each_transcript", self.number_of_times_to_sample_each_transcript)
