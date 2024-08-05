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
from concurrent.futures import ThreadPoolExecutor

import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

from graphviz import Digraph
from jinja2 import Template

from plexus.scores.CompositeScore import CompositeScore
from plexus.scores.Score import Score
from .Scorecard import Scorecard
from .ScorecardResults import ScorecardResults
from .ScorecardResultsAnalysis import ScorecardResultsAnalysis

class Experiment:
    def __init__(self, *,
        scorecard: Scorecard,
        labeled_samples_filename: str = None,
        labeled_samples: list = None,
        number_of_texts_to_sample = 1,
        sampling_method = 'random',
        random_seed = None,
        session_ids_to_sample = None,
        subset_of_score_names = None,
        experiment_label = None
    ):
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

        # Configure logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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

        if hasattr(self, 'session_ids_to_sample') and self.session_ids_to_sample:
            selected_sample_rows = df[df['Session ID'].isin(self.session_ids_to_sample)]
        elif self.sampling_method == 'random':
            if hasattr(self, 'random_seed'):
                random.seed(self.random_seed)
            try:
                selected_sample_indices = random.sample(range(len(df)), self.number_of_texts_to_sample)
                selected_sample_rows = df.iloc[selected_sample_indices]
            except ValueError as e:
                logging.error(f"Sampling error: {e}")
                selected_sample_rows = df
        elif self.sampling_method == 'all':
            selected_sample_rows = df
        else:
            selected_sample_rows = df.head(self.number_of_texts_to_sample)

        # Iterate over the randomly selected DataFrame rows and classify each text
        results = []
        max_thread_pool_size = 10

        # Create a thread pool executor
        with ThreadPoolExecutor(max_workers=max_thread_pool_size) as executor:
            # Submit tasks to the executor to score each text in parallel
            future_to_index = {
                executor.submit(self.score_text, row): index
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
                logging.info(f"text {index} classified.")
                logging.debug(f"Result: {result}")
                results.append(result)
                # except Exception as e:
                #     logging.exception(f"Error processing text at index {index}: {e}")

        # pretty_printer = pprint.PrettyPrinter()
        # print("Final all scorecard results:\n")
        # pretty_printer.pprint(results)

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
                score_value = str(result['results'][question].value).lower()
                if not score_value or score_value.strip() == "":
                    score_value = "na"
                human_label = str(result['results'][question].metadata['human_label']).lower()
                logging.info(f"Question: {question}, score Label: {score_value}, Human Label: {human_label}")
                is_match = 1 if result['results'][question].metadata['correct'] else 0
                total_correct += is_match
                total_questions += 1

        analysis = ScorecardResultsAnalysis(
            scorecard_results=scorecard_results
        )

        def log_accuracy_heatmap():
            try:
                analysis.plot_accuracy_heatmap()
                mlflow.log_artifact('tmp/accuracy_heatmap.png')
            except Exception as e:
                logging.error(f"Failed to log accuracy heatmap: {e}")

        def log_html_report():
            try:
                html_report_content = analysis.generate_html_report(expenses=expenses)
                with open("tmp/scorecard_report.html", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact("tmp/scorecard_report.html")
            except Exception as e:
                logging.error(f"Failed to log HTML report: {e}")

        def log_incorrect_scores_report():
            try:
                html_report_content = analysis.generate_html_report(only_incorrect_scores=True, expenses=expenses)
                with open("tmp/scorecard_report_incorrect_scores.html", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact("tmp/scorecard_report_incorrect_scores.html")
            except Exception as e:
                logging.error(f"Failed to log incorrect scores report: {e}")

        def log_no_costs_report():
            try:
                html_report_content = analysis.generate_html_report(redact_cost_information=True)
                with open("tmp/scorecard_report_no_costs.html", "w") as file:
                    file.write(html_report_content)
                mlflow.log_artifact("tmp/scorecard_report_no_costs.html")
            except Exception as e:
                logging.error(f"Failed to log no costs report: {e}")

        def log_scorecard_costs():
            try:
                analysis.plot_scorecard_costs(results=results)
                mlflow.log_artifact('tmp/scorecard_input_output_costs.png')
                mlflow.log_artifact('tmp/histogram_of_total_costs.png')
                mlflow.log_artifact('tmp/distribution_of_input_costs.png')
                mlflow.log_artifact('tmp/total_llm_calls_by_score.png')
                mlflow.log_artifact('tmp/distribution_of_input_costs_by_element_type.png')
            except Exception as e:
                logging.error(f"Failed to log scorecard costs: {e}")

        def log_csv_report():
            try:
                with open("tmp/scorecard_report_for_incorrect_results.csv", "w") as file:
                    file.write(analysis.generate_csv_scorecard_report(results=results))
                mlflow.log_artifact("tmp/scorecard_report_for_incorrect_results.csv")
            except Exception as e:
                logging.error(f"Failed to log CSV report: {e}")

        def log_question_accuracy_csv():
            try:
                analysis.generate_question_accuracy_csv(output_file="tmp/question_accuracy_report.csv")
                mlflow.log_artifact("tmp/question_accuracy_report.csv")
            except Exception as e:
                logging.error(f"Failed to log question accuracy CSV: {e}")

        expenses = self.scorecard.get_accumulated_costs()
        expenses['cost_per_text'] = expenses['total_cost'] / len(selected_sample_rows)    

        # Create a thread pool executor
        with ThreadPoolExecutor() as executor:
            # Submit the combined analysis and logging tasks to the executor
            futures = [
                #executor.submit(log_accuracy_heatmap),
                executor.submit(log_html_report),
                executor.submit(log_incorrect_scores_report),
                executor.submit(log_no_costs_report),
                #executor.submit(log_scorecard_costs),
                executor.submit(log_csv_report),
                executor.submit(log_question_accuracy_csv)  # Ensure this function is called
            ]

            # Wait for all the tasks to complete
            for future in futures:
                future.result()

        # Run these sequentially to avoid issues with Heatmap generation.
        log_accuracy_heatmap()
        log_scorecard_costs()

        # Calculate overall accuracy
        overall_accuracy = (total_correct / total_questions) * 100 if total_questions > 0 else 0
        mlflow.log_metric("overall_accuracy", overall_accuracy)

        # Log the results to MLflow
        mlflow.log_metric("number_of_texts", len(selected_sample_rows))
        mlflow.log_metric("number_of_scores", len(self.score_names()))
        mlflow.log_metric("total_cost", expenses['total_cost'])
        mlflow.log_metric("cost_per_text", expenses['cost_per_text'])

        logging.info(f"Expenses: {expenses}")
        logging.info(f"Number of texts to sample: {len(selected_sample_rows)}")
        logging.info(f"Total cost: {expenses['total_cost']}")
        logging.info(f"Cost per text: {expenses['cost_per_text']}")
        logging.info(f"Overall accuracy: {overall_accuracy:.2f}%")

    # Function to classify a single text and collect metrics
    @retry(
        wait=wait_fixed(2),          # wait 2 seconds between attempts
        stop=stop_after_attempt(5),  # stop after 5 attempts
        before=before_log(logging.getLogger(), logging.INFO),       # log before retry
        retry=retry_if_exception_type((Timeout, RequestException))  # retry on specific exceptions
    )
    def score_text(self, row):
        logging.info(f"Columns available in this row: {row.index.tolist()}")

        text = row['text']
        content_id = row.get('content_id', '')
        session_id = row.get('Session ID', content_id)

        logging.info(f"Processing text for content_id: {content_id}, session_id: {session_id}")

        scorecard_results = self.scorecard.score_entire_text(
            text=text,
            subset_of_score_names=self.score_names_to_process()
        )

        # Extract human labels for each question from the DataFrame row
        human_labels = {}
        for question_name in scorecard_results.keys():
            label_column = question_name + '_label'
            if label_column in row.index:
                human_labels[question_name] = row[label_column]
            elif question_name in row.index:
                human_labels[question_name] = row[question_name]
            else:
                logging.warning(f"Neither '{question_name}' nor '{label_column}' found in the row. Available columns: {row.index.tolist()}")
                human_labels[question_name] = 'N/A'

        for question_name in scorecard_results.keys():
            try:
                score_result = scorecard_results[question_name]

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

                human_label = str(human_labels[question_name]).lower()
                if human_label == 'nan':
                    human_label = 'na'

                score_result.metadata['human_label'] = human_label
                score_result.metadata['correct'] = score_result_value == human_label

                # Log warnings for mismatches and append to incorrect results
                if not score_result.metadata['correct']:
                    logging.warning(f"Human label '{human_label}' does not match score '{score_result_value}' for question '{question_name}' in session '{session_id}'")

                # Also, add the full text to the score result.
                score_result.metadata['text'] = text

                logging.debug(f"Score result for {question_name}: {score_result}")

            except Exception as e:
                logging.exception(f"Error processing {question_name}: {e}")
                # Log the full response if it's an HTTPError
                if isinstance(e, requests.exceptions.HTTPError):
                    logging.error(f"HTTPError: {e.response.text}")

                score_result = Score.Result(value="Error", error=str(e))

        return {
            'content_id': content_id,
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
    def __init__(self, *, number_of_times_to_sample_each_text, **kwargs):
        super().__init__(**kwargs)
        self.number_of_times_to_sample_each_text = number_of_times_to_sample_each_text
    
    def log_parameters(self):
        super().log_parameters()
        mlflow.log_param("number_of_times_to_sample_each_text", self.number_of_times_to_sample_each_text)
