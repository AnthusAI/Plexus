import os
import json
import base64
import pandas as pd
import logging
import requests
import random
import time
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

from Scorecard import Scorecard
from CompositeScore import CompositeScore
from ScoreResult import ScoreResult

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

        self.all_score_results = []
        self.incorrect_score_results = []

    def __enter__(self):
        self.start_mlflow_run()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        mlflow.end_run()

    def start_mlflow_run(self):
        mlflow.set_experiment("Accuracy: " + self.scorecard.__class__.name())

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
        if not hasattr(self, 'memoized_score_names'):
            self.memoized_score_names = self.subset_of_score_names if self.subset_of_score_names is not None else self.scorecard.score_names()
        return self.memoized_score_names

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
        for filename in os.listdir(self.override_folder):
            if filename.endswith(".csv"):
                filepath = os.path.join(self.override_folder, filename)
                df = pd.read_csv(filepath, keep_default_na=False)  # Prevents automatic conversion of "NA" to NaN
                for _, row in df.iterrows():
                    session_id = row['session_id']
                    question_name = row['question_name'].strip()
                    correct_value = row['correct_value'].strip()
                    if correct_value:  # Ignore rows where correct_value is an empty string
                        if session_id not in override_data:
                            override_data[session_id] = {}
                        override_data[session_id][question_name] = correct_value
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
                try:
                    result = future.result()
                    logging.info(f"Transcript {index} classified.")
                    logging.info(f"Result: {result}")
                    results.append(result)
                except Exception as e:
                    logging.exception(f"Error processing transcript at index {index}: {e}")

        # Iterate over the results to compute accuracy for each one
        for result in results:
            # Compute accuracy for the current result
            result['accuracy'] = self.compare_scorecard_results(
                human_labels=result['human_labels'],
                scorecard_results=result['results']
            )

        logging.info("Random classification completed.")
        for result in results:
            logging.info(f"Session ID: {result['session_id']}")
            logging.info(f"  Results: {result['results']}")
            logging.info(f"  Human Labels: {result['human_labels']}")
            logging.info(f"  Accuracy: {result['accuracy']}")

        for result in results:
            data_row = []
            annotation_row = []
            for question in self.score_names():
                score_label = str(result['results'].get(question, 'NA')).lower()
                human_label = str(result['human_labels'][question]).lower()
                logging.info(f"Question: {question}, score Label: {score_label}, Human Label: {human_label}")
                is_match = 1 if score_label[:2] == human_label[:2] else 0
                total_correct += is_match
                total_questions += 1
                data_row.append(is_match)  # Use 1 for match, 0 for mismatch for the heatmap
                annotation_row.append(f"{score_label}\nh:{human_label}")
            heatmap_data.append(data_row)
            annotations.append(annotation_row)
        
        # Calculate overall accuracy
        overall_accuracy = (total_correct / total_questions) * 100 if total_questions > 0 else 0

        logging.info(f"Overall accuracy: {overall_accuracy:.2f}%")

        # Call the function with the results
        self.plot_accuracy_heatmap(
            results = results,
            overall_accuracy = overall_accuracy,
            heatmap_data = heatmap_data,
            annotations = annotations
        )

        # Log the plot as an artifact in MLFlow
        mlflow.log_artifact('mlruns/accuracy_heatmap.png')

        self.plot_scorecard_costs(results=self.all_score_results)

        expenses = self.scorecard.accumulated_expenses()
        logging.info(f"Expenses: {expenses}")

        expenses['cost_per_transcript'] = expenses['total_cost'] / len(selected_sample_rows)
        logging.info(f"Number of transcripts to sample: {len(selected_sample_rows)}")
        logging.info(f"Total cost: {expenses['total_cost']}")
        logging.info(f"Cost per transcript: {expenses['cost_per_transcript']}")

        # Log the results to MLflow
        mlflow.log_metric("number_of_transcripts", len(selected_sample_rows))
        mlflow.log_metric("number_of_scores", len(self.score_names()))
        mlflow.log_metric("total_cost", expenses['total_cost'])
        mlflow.log_metric("cost_per_transcript", expenses['cost_per_transcript'])

        # Write out a CSV of incorrect scores.
        with open("mlruns/scorecard_report_for_incorrect_results.csv", "w") as file:
            file.write(self.generate_csv_scorecard_report(
                results=self.incorrect_score_results))
        mlflow.log_artifact("mlruns/scorecard_report_for_incorrect_results.csv")

        # Write the report string to an .html file and log that as an artifact in MLFlow.
        with open("mlruns/scorecard_report_for_incorrect_results.html", "w") as file:
            file.write(self.generate_scorecard_report(
                results=self.incorrect_score_results,
                overall_accuracy=overall_accuracy,
                expenses=expenses,
                title="Scoring Report for Incorrect Scores",
                subtitle="The following scoring results did not match the human labels for the same call sessions."))
        mlflow.log_artifact("mlruns/scorecard_report_for_incorrect_results.html")

        with open("mlruns/scorecard_report.html", "w") as file:
            file.write(self.generate_scorecard_report(
                results=self.all_score_results,
                overall_accuracy=overall_accuracy,
                expenses=expenses,
                title="Scoring Report",
                subtitle="This report includes the detailed scoring results from every question."))
        mlflow.log_artifact("mlruns/scorecard_report.html")

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

        logging.info(f"Fixed transcript content: {transcript}")

        # Extract human labels for each question from the DataFrame row
        human_labels = {question_name: row[question_name] for question_name in self.score_names()}

        scorecard_results = self.scorecard.score_entire_transcript(
            transcript=transcript,
            subset_of_score_names=self.score_names()
        )

        for question_name in self.score_names():
            try:
                score_result = scorecard_results[question_name]
                if score_result is None:
                    logging.error(f"No score result for {question_name}")
                    scorecard_results[question_name] = None
                else:
                    scorecard_results[question_name] = score_result.value

                # Normalize the score result value for comparison
                score_result_value = 'na' if \
                    score_result is None else str(score_result.value).strip().lower()

                # Apply overrides if available
                if session_id in self.override_data:
                    for question_name, correct_value in self.override_data[session_id].items():
                        if question_name in human_labels:
                            logging.info(f"OVERRIDING human label for question '{question_name}' in session '{session_id}' from '{human_labels[question_name]}' to '{correct_value}'")
                            human_labels[question_name] = correct_value

                human_label = str(human_labels[question_name]).lower()
                if human_label == 'nan':
                    human_label = 'na'

                correct = score_result_value == human_label

                # For the Scorecard Evaluation Report
                scorecard_report_data = {
                    'session_id': session_id,
                    'question_name': question_name,
                    'overall_question': score_result.metadata.get('overall_question', None),
                    'reasoning': score_result.metadata.get('reasoning', None),
                    'relevant_quote': score_result.metadata.get('relevant_quote', None),
                    'human_label': human_label,
                    'correct': correct,
                    'result': score_result,
                    'prompt_tokens': score_result.metadata.get('prompt_tokens', 0),
                    'completion_tokens': score_result.metadata.get('completion_tokens', 0),
                    'llm_request_count': score_result.metadata.get('llm_request_count', 0),
                    'total_cost': score_result.metadata.get('total_cost', 0),
                    'input_cost': score_result.metadata.get('input_cost', 0),
                    'output_cost': score_result.metadata.get('output_cost', 0),
                    'transcript': transcript
                }

                # Log warnings for mismatches and append to incorrect results
                if not correct:
                    logging.warning(f"Human label '{human_label}' does not match score '{score_result_value}' for question '{question_name}' in session '{session_id}'")
                    self.incorrect_score_results.append(scorecard_report_data)

                self.all_score_results.append(scorecard_report_data)

                logging.debug(f"Score result for {question_name}: {score_result}")
            except Exception as e:
                logging.exception(f"Error processing {question_name}: {e}")
                # Log the full response if it's an HTTPError
                if isinstance(e, requests.exceptions.HTTPError):
                    logging.error(f"HTTPError: {e.response.text}")

                score_result = ScoreResult(value="Error", error=str(e))

                scorecard_report_data = {
                    'session_id': session_id,
                    'question_name': question_name,
                    'overall_question': None,
                    'reasoning': None,
                    'relevant_quote': None,
                    'human_label': human_label,
                    'correct': correct,
                    'result': score_result,
                    'prompt_tokens': score_result.metadata['prompt_tokens'] if score_result else 0,
                    'completion_tokens': score_result.metadata['completion_tokens'] if score_result else 0,
                    'llm_request_count': score_result.metadata['llm_request_count'] if score_result else 0,
                    'total_cost': score_result.metadata['total_cost'] if score_result else 0,
                    'input_cost': score_result.metadata['input_cost'] if score_result else 0,
                    'output_cost': score_result.metadata['output_cost'] if score_result else 0,
                    'transcript': transcript
                }
                self.all_score_results.append(scorecard_report_data)
                self.incorrect_score_results.append(scorecard_report_data)


        logging.info(f"Total score results: {len(self.all_score_results)}")
        logging.info(f"Total incorrect score results: {len(self.incorrect_score_results)}")

        return {
            'session_id': session_id,
            'results': scorecard_results,
            'human_labels': human_labels
        }

    def compare_scorecard_results(self, human_labels, scorecard_results):
        correct_count = 0
        total_count = len(self.score_names())

        logging.info(f"Comparing human labels and classifications for {total_count} questions.")
        logging.info(f"Human labels: {human_labels}")
        logging.info(f"Scorecard results: {scorecard_results}")
        
        for question in self.score_names():
            # Ensure that we only compare questions that are in the subset and have a human label
            if question in human_labels:
                score_label = scorecard_results.get(question, 'NA')
                logging.debug(f"Score label for question '{question}': {score_label}")
                if score_label is None:
                    logging.warning(f"No scorecard result label found for question '{question}'")
                    continue
                score_label = score_label.lower()
                human_label = str(human_labels[question]).lower()
                
                if human_label[:2] == score_label[:2]:
                    correct_count += 1
        
        accuracy = correct_count / total_count if total_count > 0 else 0
        return accuracy

    def plot_accuracy_heatmap(self, *, results, overall_accuracy, heatmap_data, annotations):

        # Convert the list of rows into a DataFrame
        heatmap_df = pd.DataFrame(heatmap_data, columns=self.score_names())

        # Check if the DataFrame is empty
        if heatmap_df.empty:
            raise ValueError("The heatmap DataFrame is empty. Please check the data.")

        # Define the custom colormap
        cmap = ListedColormap(['red', 'green'])

        # Ensure the color range includes both 0 and 1 even if all values are the same
        vmin, vmax = 0, 1

        # Dynamically adjust the width of the figure based on the number of columns
        # and set a minimum height to ensure the heatmap is not squashed
        heatmap_width = max(len(heatmap_df.columns) * 1, 10)  # 1 inch per column or minimum 10 inches
        heatmap_height = max(len(heatmap_df) * 1, 4)

        fig, ax = plt.subplots(figsize=(heatmap_width, heatmap_height))

        # Plot the heatmap with specified value range
        sns.heatmap(heatmap_df, annot=np.array(annotations), fmt='', cmap=cmap, linewidths=.5, cbar=False, ax=ax, vmin=vmin, vmax=vmax)

        # Add a title and subtitle
        ax.set_title('Accuracy Compared With Human Labels', fontsize=16)
        ax.set_xlabel(f"Overall Accuracy: {overall_accuracy:.2f}%", fontsize=14)  # Subtitle with overall accuracy

        # Log the overall accuracy in the current MLflow run
        mlflow.log_metric("overall_accuracy", overall_accuracy)

        # Annotate with the first five characters of ID numbers on the left and accuracy on the right
        for i, result in enumerate(results):
            transcript_id = result['session_id'][:5]  # Only use the first five characters of the session ID
            accuracy = result['accuracy']
            ax.text(-0.4, i + 0.5, transcript_id, va='center', ha='right', transform=ax.transData, fontsize=14)
            ax.text(len(heatmap_df.columns) + 0.1, i + 0.5, f"{accuracy:.2%}", va='center', ha='left', transform=ax.transData, fontsize=14, family='monospace')

        # Adjust the layout so that there is no overlapping content
        plt.tight_layout()
        
        plt.savefig('mlruns/accuracy_heatmap.png', bbox_inches='tight', pad_inches=0.2)
        # plt.show()

    def plot_scorecard_costs(self, *, results):
        input_costs = [float(result['input_cost']) for result in results]
        output_costs = [float(result['output_cost']) for result in results]
        total_costs = [float(result['total_cost']) for result in results]
        llm_calls = [result['llm_request_count'] for result in results]
        score_names = [result['question_name'] for result in results]

        # Define colors
        sky_blue = (0.012, 0.635, 0.996)
        fuchsia = (0.815, 0.2, 0.51)
        golden_rod = (0.855, 0.647, 0.125)

        # Plot for input and output costs
        fig, ax = plt.subplots(figsize=(10, 10))
        bar_width = 0.35
        index = np.arange(len(results))

        bars1 = ax.bar(index, input_costs, bar_width, color=sky_blue, label='Input Costs')
        bars2 = ax.bar(index + bar_width, output_costs, bar_width, color=fuchsia, label='Output Costs')

        ax.set_xlabel('Scores')
        ax.set_ylabel('Costs')
        ax.set_title('Input and Output Costs by Score')
        ax.set_xticks(index + bar_width / 2)
        ax.set_xticklabels(score_names, rotation=45, ha="right")
        ax.legend()

        fig.tight_layout()
        plt.savefig('mlruns/input_output_costs.png')
        mlflow.log_artifact('mlruns/input_output_costs.png')

        # Plot for total costs histogram
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.hist(total_costs, bins=20, color=fuchsia)
        ax.set_title('Histogram of Total Costs')
        ax.set_xlabel('Total Cost')
        ax.set_ylabel('Frequency')

        plt.savefig('mlruns/total_costs_histogram.png')
        mlflow.log_artifact('mlruns/total_costs_histogram.png')

        # Plot for LLM calls by score
        fig, ax = plt.subplots(figsize=(10, 10))
        bars3 = ax.bar(index, llm_calls, bar_width, color=golden_rod, label='LLM Calls')

        ax.set_xlabel('Scores')
        ax.set_ylabel('Number of LLM Calls')
        ax.set_title('LLM Calls by Score')
        ax.set_xticks(index)
        ax.set_xticklabels(score_names, rotation=45, ha="right")
        ax.legend()

        fig.tight_layout()
        plt.savefig('mlruns/llm_calls_by_score.png')
        mlflow.log_artifact('mlruns/llm_calls_by_score.png')

    def generate_csv_scorecard_report(self, *, results):
        report = "session_id,question_name,human_label,result_value,correct_value\n"

        for result in results:
            report += f"{result['session_id']}, {result['question_name']}, {result['human_label']}, {result['result'].value}, ,\n"
        
        return report

    def generate_scorecard_report(self, *, results,
        overall_accuracy, expenses,
        title="Scorecard Evaluation Report", subtitle=None):

        logging.info(f"Generating scorecard report with {len(results)} results.")

        for result in results:
            # Generate visualization image for the current score result
            visualization_image_path = self.visualize_decision_path(
                score_result=result['result'],
                decision_tree=result['result'].decision_tree,
                element_results=result['result'].element_results,
                session_id=result['session_id']
            )
            
            # Encode the image as base64
            with open(visualization_image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Embed the base64-encoded image in the HTML
            result['visualization_image_base64'] = encoded_string

        # Fetch the current run's data
        run = mlflow.get_run(mlflow.active_run().info.run_id)
        parameters = run.data.params
        metrics = run.data.metrics

        report = ''
        template_string = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{title}}</title>
    <meta name="description" content="{{subtitle}}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400..900&display=swap" rel="stylesheet">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400..900&family=Montserrat:ital,wght@0,100..900;1,100..900&display=swap" rel="stylesheet">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inconsolata:wght@200..900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
    <style>
    :root {
        --background: #ffffff;
        --focus-background: #f1f9fe;
        --neutral: #DDD;
        --red: #d33;
        --green: #393;
        --text: #333;
        --red-text: #d33;
        --green-text: #393;
    }
    h1, .cinzel-700 {
        font-family: "Cinzel", serif;
        font-optical-sizing: auto;
        font-weight: 700;
        font-style: normal;
        margin: 0;
    }
    h2 {
        margin-block-start: 0;
        margin-block-end: 0;
    }
    body, p, .montserrat {
        font-family: "Montserrat", sans-serif;
        font-optical-sizing: auto;
        font-weight: 400;
        font-style: normal;
    }
    .inconsolata, .fixed {
        font-family: "Inconsolata", monospace;
        font-optical-sizing: auto;
        font-weight: 700;
        font-style: bold;
        font-variation-settings:
            "wdth" 100;
    }
    body {
      margin: 2em 1em;
      color: var(--text);
      background-color: var(--background);
    }
    header {
        display: block;
        margin: 0 0 1em 0;
        padding: 1em;
        border: 1em solid var(--neutral);
        border-radius: 1em;
    }
    section.session {
        padding: 0;
        border: 1em solid var(--focus-background);
        border-radius: 1em;
        margin: 0 -1em 3em -1em;
        background-color: var(--focus-background);
    }
    section.session > metadata {
        display: block;
        border: 1em solid var(--neutral);
        border-radius: 1em;
        margin: 0 0 1em 0;
    }
    score {
        display: block;
        margin: 0 0 1em 0;
        padding: 0;
        border: 1px solid var(--neutral);
        border-radius: 1em;
        overflow: hidden;
    }
    score.correct {
        background-color: var(--green);
        border-color: var(--green);
    }
    score.incorrect {
        background-color: var(--red);
        border-color: var(--red)
    }
    metadata {
        display: block;
        margin: 1em;
        padding: calc(1em - 1px);
        border: 1px solid var(--neutral);
        color: var(--text);
        background-color: var(--background);
        border-radius: .7em;
    }
    metadata.top {
        margin: 0 1em 1em 1em;
    }
    element {
        display: block;
        margin: 1em 0 0 0;
        padding: calc(1em - 1px);
        border: 1px solid var(--neutral);
        color: var(--text);
        background-color: var(--background);
        border-radius: .7em;
    }
    session.correct element {
        border-color: var(--green);
    }
    session.incorrect element {
        border-color: var(--red)
    }
    metadata, element {
      position: relative;
    }
    .correct {
      color: var(--green-text);
    }
    .incorrect {
      color: var(--red-text);
    }
    .label {
        font-weight: 900;
        letter-spacing: 0.2ex;
        padding: 1ex;
        border-radius: 1ex;
        color: var(--text);
        background-color: var(--neutral);
        text-align: center;
    }
    .label.correct {
        color: white;
        background-color: var(--green-text);
    }
    .label.incorrect {
        color: white;
        background-color: var(--red-text);
    }
    .collapsible_content {
      max-height: 0;
      overflow: hidden;
      transition: max-height 0.2s ease-out;
    }
    .collapsible_toggle:checked ~ .collapsible_content {
      max-height: unset;
    }
    .checkbox {
      display: inline-block;
    }
    .icon {
      position: absolute;
      top: 1em;
      right: 1em;
    }
    .fixed {
        font-family: "Inconsolata", monospace;
    }
    </style>
    <script>
        function enlargeImage(base64Image) {
            // Create an overlay div
            var overlay = document.createElement("div");
            overlay.setAttribute("style", "position:fixed;top:0;left:0;width:100%;height:100%;background-color:rgba(0,0,0,0.85);z-index:1000;display:flex;justify-content:center;align-items:center;");
            overlay.addEventListener("click", function() {
                document.body.removeChild(overlay);
            });

            // Create an img element
            var img = document.createElement("img");
            img.setAttribute("src", base64Image);
            img.setAttribute("style", "max-width:90%;max-height:90%;");

            // Append img to overlay, then overlay to body
            overlay.appendChild(img);
            document.body.appendChild(overlay);
        }
    </script>
</head>
<body>
{% if results|length == 0 %}
    No results found.
{% else %}
    <header>
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>
        <table>
            <tr><td>Number of transcripts processed:</td> <td class="fixed">{{ metrics['number_of_transcripts']|round|int }}</td></tr>
            <tr><td>Sampling method:</td> <td class="fixed">{{ parameters['sampling_method'] }}</td></tr>
            <tr><td>Overall Accuracy</td> <td class="fixed">{{ metrics['overall_accuracy']|round|int }}%</td></tr>
            <tr><td>Total cost:</td> <td class="fixed">${{ metrics['total_cost']|round(6) }}</td></tr>
            <tr><td>Cost per transcript:</td> <td class="fixed">${{ metrics['cost_per_transcript']|round(6) }}</td></tr>
        </table>
    </header>
{% endif %}

{% set context = namespace(current_session_id='', section_opened=false) %}
{% for result in results %}
    {% if result.session_id != context.current_session_id %}
        {% if context.section_opened %}
            <!-- Close the previous section if it's not the first iteration -->
            </section>
        {% endif %}
        <!-- Start a new section for a new session ID -->
        <section class="session">
            <metadata class="top">
                <i class="fas fa-phone icon"></i>
                <h2>Call Session <span class="fixed">{{ result.session_id }}</span></h2>
            </metadata>
        {% set context.current_session_id = result.session_id %}
        {% set context.section_opened = true %}
    {% endif %}
    <score class="{{ 'correct' if result.correct else 'incorrect' }}">
        <metadata>
            <div style="display: flex; flex-direction: column; gap: 1em;">
                <div style="display: flex; justify-content: space-between; gap: 2em;">
                    <div style="flex: 3; display: flex; flex-direction: column; gap: 1em;">
                        <div><h2>Score: {{ result.question_name }}</h2></div>
                        <div><b>Overall question:</b> {{ result.overall_question }}</div>
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); font-weight: bold; margin: 0 10%; gap: 3em;">
                            <div>Answer</div>
                            <div>Label</div>
                            <div>Match?</div>
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 3em; margin: 0 10%;">
                            <div class="label">{{ result.result.value|upper }}</div>
                            <div class="label">{{ result.human_label|upper }}</div>
                            <div class="label {{ 'correct' if result.correct else 'incorrect' }}">{{ 'YES' if result.correct else 'NO' }}</div>
                        </div>
                        <div><b>Reasoning:</b> {{ result.reasoning|replace("\n", "<br/>") }}</div>
                        <div><b>Relevant quote:</b> <i>"{{ result.relevant_quote }}"</i></div>
                    </div>
                    <div style="flex: 2; display: flex; justify-content: center; align-items: start;">
                        <img onclick="enlargeImage(this.src)" style="width: 100%; height: auto; max-width: 500px; margin-top: 2em;" src="data:image/png;base64,{{ result.visualization_image_base64 }}" alt="Decision Path Visualization">
                    </div>
                </div>
                <div>
                    <b>Cost:</b>
                    <div class="collapsible_section">
                        <label for="collapsible">Click to expand</label>
                        <input type="checkbox" class="collapsible_toggle">
                        <div class="collapsible_content">
                            <br/>
                            <div style="display: flex; align-items: flex-start; gap: 1em;">
                                <div style="flex: 1; display: grid; grid-template-columns: repeat(2, auto); gap: 10px;">
                                    <div>LLM request count:</div>
                                    <div class="fixed">{{ result.llm_request_count }}</div>

                                    <div>Prompt tokens:</div>
                                    <div class="fixed">{{ result.prompt_tokens }}</div>

                                    <div>Completion tokens:</div>
                                    <div class="fixed">{{ result.completion_tokens }}</div>

                                    <div>Input cost:</div>
                                    <div class="fixed">${{ "%.6f"|format(result.input_cost) }}</div>

                                    <div>Output cost:</div>
                                    <div class="fixed">${{ "%.6f"|format(result.output_cost) }}</div>

                                    <div>Total cost:</div>
                                    <div class="fixed">${{ "%.6f"|format(result.total_cost) }}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div>
                    <b>Full Transcript:</b>
                    <div class="collapsible_section">
                        <label for="collapsible">Click to expand</label>
                        <input type="checkbox" class="collapsible_toggle">
                        <div class="collapsible_content">
                            <br/>
                            {{ result.transcript|replace("\n", "<br/>")|default("No transcript available", true) }}
                        </div>
                    </div>
                </div>
                <div>
                    <b>Decision Elements:</b>
                    <div class="collapsible_section">
                        <label for="collapsible">Click to expand</label>
                        <input type="checkbox" class="collapsible_toggle">
                        <div class="collapsible_content">
                            <elements class="collapsible_content">
                                {% for element in result.result.element_results %}
                                    <element>
                                        <i class="{{ 'fas fa-comments icon' if 'clarification_reasoning' in element.metadata else 'fas fa-comment icon' }}"></i>
                                        <div style="display: flex; flex-direction: column; gap: 1em;">

                                            <div class="question">
                                                <h2>Decision Element: <span class="fixed">{{ element.metadata['element_name'] }}</span></h2>
                                            </div>
                                            <div class="result_value">
                                                <div class="label {{ 'correct' if element.metadata['value'].lower() == 'yes' else 'incorrect' }}">{{ element.metadata['value']|upper }}</div>
                                            </div>
                                            <div class="reasoning">
                                                <b>Reasoning</b> <span>{{ element.metadata['reasoning']|replace("\n", "<br/>") }}</span>
                                            </div>
                                            {% if 'clarification_reasoning' in element.metadata %}
                                                <div class="reasoning"><b>Reasoning about rules</b> <span>{{ element.metadata['clarification_reasoning']|replace("\n", "<br/>") }}</span></div>
                                            {% endif %}
                                            <div class="prompt"><b>Prompt</b>
                                                <div class="collapsible_section">
                                                    <label for="collapsible">Click to expand</label>
                                                    <input type="checkbox" class="collapsible_toggle">
                                                    <div class="collapsible_content">
                                                        <br/>
                                                        {{ element.metadata['prompt']|replace("\n", "<br/>") }}
                                                    </div>
                                                </div>
                                            </div>
                                            {% if 'transcript' in element.metadata %}
                                                <div class="transcript"><b>Transcript Chunk</b>
                                                    <div class="collapsible_section">
                                                        <label for="collapsible">Click to expand</label>
                                                        <input type="checkbox" class="collapsible_toggle">
                                                        <div class="collapsible_content">
                                                            <br/>
                                                            {{ element.metadata['transcript']|replace("\\n", "\n")|replace("\n", "<br/>") }}
                                                        </div>
                                                    </div>
                                                </div>
                                            {% endif %}
                                            {% if 'chat_history' in element.metadata %}
                                                <div class="transcript"><b>Chat History</b>
                                                    <div class="collapsible_section">
                                                        <label for="collapsible">Click to expand</label>
                                                        <input type="checkbox" class="collapsible_toggle">
                                                        <div class="collapsible_content">
                                                            <br/>
                                                            {% for message in element.metadata['chat_history'] %}
                                                                <p><b>{{ message['role'] }}:</b> {{ message['content']|replace("\n", "<br/>") }}</p>
                                                            {% endfor %}
                                                        </div>
                                                    </div>
                                                </div>
                                            {% endif %}
                                        </div>
                                    </element>
                                {% endfor %}
                            </elements>
                        </div>
                    </div>
                </div>
            </div>
        </metadata>

    </score>
{% else %}
    <p>No results found.</p>
{% endfor %}

{% if context.section_opened %}
    <!-- Close the last section if any sections were opened -->
    </section>
{% endif %}

</body>
</html>
"""
        
        template = Template(template_string)
        report = template.render(
            metrics=metrics,
            parameters=parameters,
            results=results,
            title=title,
            subtitle=subtitle)

        return report


    def visualize_decision_path(self, *, score_result, decision_tree, element_results, session_id):
        # Define the outcome nodes with unique IDs at the beginning of the method
        outcome_nodes = {
            'yes': 'node_yes',
            'no': 'node_no',
            'na': 'node_na'
        }

        logging.debug(f"Score result: {score_result.value}")

        if decision_tree is None:
            logging.error("Decision tree is not provided. Aborting visualization.")
            return

        logging.debug("Elements results:")
        for element in element_results:
            logging.debug(f"  {element.metadata['element_name']}: {element.value}")

        # Initialize the dictionary to keep track of created nodes and their IDs
        created_nodes = {}

        dot = Digraph(comment='Decision Path Visualization')
        dot.attr(rankdir='TB')
        dot.attr('node', style='filled, rounded', shape='box', fontname='Helvetica-Bold', fontsize='14')
        dot.attr('edge', fontname='Helvetica-Bold', fontsize='14')
        dot.graph_attr['dpi'] = '300'

        # Default colors for outcome nodes
        outcome_colors = {
            'yes': '#666666',
            'no': '#666666',
            'na': '#666666'
        }

        # Update the color of the correct outcome node based on the score_result
        final_outcome = score_result.value.lower()
        if final_outcome in outcome_colors:
            if final_outcome == 'yes':
                outcome_colors[final_outcome] = '#339933'  # Green
            elif final_outcome == 'no':
                outcome_colors[final_outcome] = '#DD3333'  # Red
            elif final_outcome == 'na':
                outcome_colors[final_outcome] = '#000000'  # Black

        # Create the outcome nodes with the determined colors
        dot.attr(rankdir='TB')
        with dot.subgraph() as s:
            s.attr(rank='sink')
            # Create the outcome nodes within this subgraph
            for outcome, color in outcome_colors.items():
                s.node(outcome_nodes[outcome], outcome.upper(), color=color, fontcolor='white')

        def did_element_decision_happen(element_name, element_results):
            return any(result.metadata['element_name'] == element_name for result in element_results)

        def was_element_positive(element_name, element_results):
            # Check if any result for the element is 'Yes'
            return any(result.value.lower() == 'yes' for result in element_results if result.metadata['element_name'] == element_name)

        # Recursive function to add nodes and edges to the graph for the entire decision tree
        def add_to_graph(tree, parent_id=None, parent_element_name=None, decision_made=None, created_nodes=created_nodes):
            # Connect outcome nodes to their parent.
            if isinstance(tree, str):
                # Connect to the appropriate outcome node
                outcome_node_id = outcome_nodes[tree.lower()]
                if parent_id is not None:
                    edge_color = '#999999'
                    edge_penwidth = '1'
                    # Check if this is the final decision leading to the outcome
                    if tree.lower() == final_outcome:
                        # Check if the decision that led to this outcome node is part of the actual decision path
                        if any(result.metadata['element_name'] == CompositeScore.normalize_element_name(parent_element_name) and result.value.lower() == decision_made.lower() for result in element_results):
                            edge_color = '#000000'  # Dark color for the final decision edge
                            edge_penwidth = '3'  # Thicker edge for the final decision
                    logging.debug(f"Creating edge from {parent_id} to {outcome_node_id} with label {decision_made}")
                    dot.edge(parent_id, outcome_node_id, label=decision_made, color=edge_color, fontcolor=edge_color, penwidth=edge_penwidth, labeldistance='5')
                return
    
            # Check if the node has already been created
            if tree['element'] in created_nodes:
                node_id = created_nodes[tree['element']]
            else:
                node_id = f"node_{len(created_nodes)}"
                created_nodes[tree['element']] = node_id
                decision_label = tree['element']
                normalized_decision_label = CompositeScore.normalize_element_name(decision_label)
                it_was_positive = was_element_positive(normalized_decision_label, element_results)
                node_color = '#339933' if it_was_positive else '#DD3333' if normalized_decision_label in [result.metadata['element_name'] for result in element_results] else '#666666'
                dot.node(node_id, decision_label, style='filled, rounded', color=node_color, fontcolor='white')

            # Connect decision nodes to their parent.
            logging.debug(f"Creating edge from {parent_id} to {node_id} with label {decision_made}")
            if parent_id is not None:
                parent_decision_result = was_element_positive(CompositeScore.normalize_element_name(parent_element_name), element_results)
                did_decision_happen = did_element_decision_happen(CompositeScore.normalize_element_name(normalized_decision_label), element_results)
                if did_decision_happen and decision_made == 'yes' and parent_decision_result:
                    dot.edge(parent_id, node_id, label=decision_made, penwidth='3', labeldistance='5')
                elif did_decision_happen and decision_made == 'no' and not parent_decision_result:
                    dot.edge(parent_id, node_id, label=decision_made, penwidth='3', labeldistance='5')
                else:
                    dot.edge(parent_id, node_id, label=decision_made, color='#999999', fontcolor='#999999', labeldistance='5')
        
            # Recursive calls for true and false branches
            if True in tree:
                add_to_graph(tree[True], node_id, tree['element'], 'yes', created_nodes)
            if True in tree:
                add_to_graph(tree[False], node_id, tree['element'], 'no', created_nodes)

        # Start adding nodes and edges from the root of the decision tree
        add_to_graph(decision_tree)

        # Render the graph to a file
        filename = f'/tmp/decision_path_visualization_{session_id}'
        dot.render(filename, format='png', view=False)
        return filename + '.png'

class ConsistencyExperiment(Experiment):
    def __init__(self, *, number_of_times_to_sample_each_transcript, **kwargs):
        super().__init__(**kwargs)
        self.number_of_times_to_sample_each_transcript = number_of_times_to_sample_each_transcript
    
    def log_parameters(self):
        super().log_parameters()
        mlflow.log_param("number_of_times_to_sample_each_transcript", self.number_of_times_to_sample_each_transcript)
