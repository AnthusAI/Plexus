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
        threads = 16,
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
        self.threads = threads
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

        if hasattr(self, 'session_ids_to_sample') and self.session_ids_to_sample:
            selected_sample_rows = df[df['Session ID'].isin(self.session_ids_to_sample)]
        elif self.sampling_method == 'random':
            if hasattr(self, 'random_seed'):
                random.seed(self.random_seed)
            try:
                if self.number_of_texts_to_sample > len(df):
                    logging.warning("Requested number of samples is larger than the dataframe size. Using the entire dataframe.")
                    selected_sample_rows = df
                else:
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
        max_thread_pool_size = self.threads

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

        if not os.path.exists(report_folder_path):
            os.makedirs(report_folder_path)

        # Log the raw results data as an artifact in MLFlow.
        scorecard_results = ScorecardResults(results)
        scorecard_results.save_to_file(f"{report_folder_path}/scorecard_results.json")
        mlflow.log_artifact(f"{report_folder_path}/scorecard_results.json")

        logging.info("Scoring completed.")

        for result in results:
            logging.info(f"Form ID: {result['form_id']}")
            logging.info(f"Results: {result['results']}")

        # Count the number correct out of all questions.
        for result in results:
            for question in self.score_names():
                score_value = str(result['results'][question].value).lower()
                if not score_value or score_value.strip() == "":
                    score_value = "na"
                human_label = str(result['results'][question].metadata['human_label']).lower()
                logging.info(f"Question: {question}, score Label: {score_value}, Human Label: {human_label}")
                is_match = 1 if result['results'][question].metadata['correct'] else 0
                self.total_correct += is_match
                self.total_questions += 1

                if not is_match and len(self.mismatches) < self.max_mismatches_to_report:
                    self.mismatches.append({
                        'form_id': result['form_id'],
                        'question': question,
                        'predicted': score_value,
                        'ground_truth': human_label,
                        'explanation': result['results'][question].explanation,
                        'transcript': result['results'][question].metadata['text']
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
        overall_accuracy = (self.total_correct / self.total_questions) * 100 if self.total_questions > 0 else 0
        mlflow.log_metric("overall_accuracy", overall_accuracy)

        # Log the results to MLflow
        mlflow.log_metric("number_of_texts", len(selected_sample_rows))
        mlflow.log_metric("number_of_scores", len(self.score_names()))
        mlflow.log_metric("total_cost", expenses['total_cost'])
        mlflow.log_metric("cost_per_text", expenses['cost_per_text'])

        # Generate the Excel report
        self.generate_excel_report(report_folder_path, results)

        # Log the model names for all scores as a JSON object
        model_names = {}
        for score_name in self.score_names():
            model_name = self.scorecard.get_model_name(score_name)
            model_names[score_name] = model_name
            logging.info(f"Model name for {score_name}: {model_name}")
        
        mlflow.log_param("model_names", json.dumps(model_names))
        logging.info(f"Logged model names: {model_names}")

        logging.info(f"Expenses: {expenses}")
        logging.info(f"{overall_accuracy:.1f}% accuracy / {len(selected_sample_rows)} samples")
        logging.info(f"cost: ${expenses['cost_per_text']:.6f} per call / ${expenses['total_cost']:.6f} total")

        report = self.generate_report(score_instance, overall_accuracy, expenses, len(selected_sample_rows))
        logging.info(report)

        self.generate_and_log_confusion_matrix(results, report_folder_path)
        
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
        overall_accuracy = (self.total_correct / self.total_questions) * 100
        
        if sample_size < 120:
            accuracy_format = "{:.0f}"
        elif sample_size < 10000:
            accuracy_format = "{:.1f}"
        else:
            accuracy_format = "{:.2f}"
        
        metrics = {
            "overall_accuracy": accuracy_format.format(overall_accuracy),
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

    # Function to classify a single text and collect metrics
    @retry(
        wait=wait_fixed(2),          # wait 2 seconds between attempts
        stop=stop_after_attempt(5),  # stop after 5 attempts
        before=before_log(logging.getLogger(), logging.INFO),       # log before retry
        retry=retry_if_exception_type((Timeout, RequestException))  # retry on specific exceptions
    )
    async def score_text(self, row):
        logging.info(f"Columns available in this row: {row.index.tolist()}")

        text = row['text']
        content_id = row.get('content_id', '')
        session_id = row.get('Session ID', content_id)
        columns = row.get('columns', {})
        form_id = columns.get('form_id', '')
        metadata_string = columns.get('metadata', {})
        metadata = json.loads(metadata_string)
        logging.info(f"Processing text for content_id: {content_id}, session_id: {session_id}, form_id: {form_id}")

        scorecard_results = self.scorecard.score_entire_text(
            text=text,
            metadata=metadata,
            subset_of_score_names=self.score_names_to_process()
        )

        # Extract human labels for each question from the DataFrame row
        human_labels = {}
        for question_name in scorecard_results.keys():
            score_instance = Score.from_name(self.scorecard_name, question_name)
            label_score_name = score_instance.get_label_score_name()
            label_column = label_score_name + '_label'
            if label_column in row.index:
                human_labels[question_name] = row[label_column]
            elif label_score_name in row.index:
                human_labels[question_name] = row[label_score_name]
            else:
                logging.warning(f"Neither '{question_name}' nor '{label_score_name}' found in the row. Available columns: {row.index.tolist()}")
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

                column_name = question_name
                human_label = str(human_labels[column_name]).lower().rstrip('.!?')
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
                score_result = result['results'][question]
                match = score_result.metadata['correct']
                records.append({
                    'session_id': result['session_id'],
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
                true_label = result['results'][question].metadata['human_label']
                pred_label = str(result['results'][question].value).lower()
                
                y_true.append(true_label)
                y_pred.append(pred_label)
                class_names.update([true_label, pred_label])

            class_names = sorted(list(class_names))
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
        true_labels = [r['results'][question].metadata['human_label'] for r in results]
        pred_labels = [str(r['results'][question].value).lower() for r in results]
        
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
