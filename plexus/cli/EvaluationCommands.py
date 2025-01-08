import os
from dotenv import load_dotenv
load_dotenv(override=True, verbose=True)

import re
import sys
import json
import click
import yaml
import asyncio
import pandas as pd
import traceback

from plexus.CustomLogging import logging, set_log_group
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
from plexus.Evaluation import AccuracyEvaluation
from plexus.cli.console import console

import importlib
from collections import Counter
import concurrent.futures
import time
import threading

set_log_group('plexus/cli/evaluation')

from plexus.scores.Score import Score

@click.group()
def evaluate():
    """
    Evaluating current scorecard configurations against labeled samples.
    """
    pass

def load_configuration_from_yaml_file(configuration_file_path):
    if os.path.exists(configuration_file_path):
        with open(configuration_file_path, 'r') as file:
            return yaml.safe_load(file)
    else:
        logging.info(f"Configuration file not found: {configuration_file_path}")
        return {}

@evaluate.command()
@click.option('--scorecard-name', 'scorecard_name', default=None, help='Name of the scorecard to evaluate')
@click.option('--use-langsmith-trace', is_flag=True, default=False, help='Activate LangSmith trace client for LangGraphScore')
@click.option('--number-of-samples', default=1, type=int, help='Number of texts to sample')
@click.option('--sampling-method', default='random', type=str, help='Method for sampling texts')
@click.option('--random-seed', default=None, type=int, help='Random seed for sampling')
@click.option('--content-ids-to-sample', default='', type=str, help='Comma-separated list of content IDs to sample')
@click.option('--score-name', default='', type=str, help='Comma-separated list of score names to evaluate')
@click.option('--experiment-label', default='', type=str, help='Label for the experiment')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
def accuracy(
    scorecard_name: str,
    use_langsmith_trace: bool,
    number_of_samples: int,
    sampling_method: str,
    random_seed: int,
    content_ids_to_sample: str,
    score_name: str,
    experiment_label: str,
    fresh: bool
    ):
    """
    Evaluate the accuracy of the scorecard using the current configuration against labeled samples.
    """
    async def _run_accuracy():
        experiment = None
        try:
            if use_langsmith_trace:
                os.environ['LANGCHAIN_TRACING_V2'] = 'true'
            else:
                os.environ.pop('LANGCHAIN_TRACING_V2', None)

            if not scorecard_name:
                logging.error("Scorecard not specified")
                sys.exit(1)

            scorecard_folder = os.path.join('scorecards', scorecard_name)
            override_folder: str = os.path.join(scorecard_folder, 'experiments/calibrations')

            logging.info('Running accuracy experiment...')
            Scorecard.load_and_register_scorecards('scorecards/')
            scorecard_type = scorecard_registry.get(scorecard_name)
            if scorecard_type is None:
                logging.error(f"Scorecard with name '{scorecard_name}' not found.")
                return

            scorecard_instance = scorecard_type(scorecard=scorecard_name)
            logging.info(f"Using scorecard {scorecard_name} with class {scorecard_instance.__class__.__name__}")

            # Check if any score in the scorecard uses the data-driven approach
            uses_data_driven = any('data' in score_config for score_config in scorecard_instance.scores)

            # We used to support multiple, comma-separated score names.  But lots of our
            # score names have commas in them.  So, we don't support that anymore.
            if score_name is not None and score_name != '':
                score_names = [score_name]
            else:
                # Fix: Get score names from the list of score dictionaries
                score_names = [score['name'] for score in scorecard_instance.scores]
            
            if not score_names:
                logging.error("No score names specified")
                return

            content_ids_to_sample_set = set(re.split(r',\s+', content_ids_to_sample.strip())) if content_ids_to_sample.strip() else None

            for single_score_name in score_names:
                logging.info(f"Running experiment for score: {single_score_name}")
                
                single_score_labeled_samples = []
                labeled_samples_filename = None
                
                # Look up Score ID from the API
                score_config = next((score for score in scorecard_instance.scores 
                                   if score['name'] == single_score_name), None)
                
                if score_config and 'id' in score_config:
                    score_id = score_config['id']
                    logging.info(f"Found Score ID {score_id} for {single_score_name}")
                else:
                    logging.warning(f"Could not find Score ID for {single_score_name}")
                    score_id = None

                if uses_data_driven:
                    if score_config:
                        single_score_labeled_samples = get_data_driven_samples(
                            scorecard_instance, scorecard_name, single_score_name, 
                            score_config, fresh, content_ids_to_sample_set)
                    else:
                        logging.warning(f"Score '{single_score_name}' not found in scorecard. Skipping.")
                        continue
                else:
                    # Use the default labeled samples file if not data-driven
                    labeled_samples_filename = os.path.join(scorecard_folder, 'experiments', 'labeled-samples.csv')

                single_score_experiment_args = {
                    'scorecard_name': scorecard_name,
                    'scorecard': scorecard_instance,
                    'override_folder': override_folder,
                    'number_of_texts_to_sample': number_of_samples,
                    'sampling_method': sampling_method,
                    'random_seed': random_seed,
                    'subset_of_score_names': [single_score_name],
                    'experiment_label': experiment_label,
                    'score_id': score_id
                }
                
                if uses_data_driven:
                    if not single_score_labeled_samples:
                        raise ValueError("The dataset is empty. Cannot proceed with the experiment.")
                    single_score_experiment_args['labeled_samples'] = single_score_labeled_samples
                else:
                    single_score_experiment_args['labeled_samples_filename'] = labeled_samples_filename
                
                async with AccuracyEvaluation(**single_score_experiment_args) as experiment:
                    # Here we can set the score_id on the experiment instance if needed
                    await experiment.run()

                logging.info("All score experiments completed.")

        finally:
            if experiment:
                await experiment.cleanup()

    # Create and run the event loop only once at the top level
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_run_accuracy())
    except asyncio.CancelledError:
        logging.info("Task was cancelled - cleaning up...")
    except Exception as e:
        logging.error(f"Error during execution: {e}")
        raise
    finally:
        try:
            tasks = [t for t in asyncio.all_tasks(loop) 
                    if not t.done()]
            if tasks:
                loop.run_until_complete(
                    asyncio.wait(tasks, timeout=2.0)
                )
            loop.close()
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

def get_data_driven_samples(scorecard_instance, scorecard_name, score_name, score_config, fresh, content_ids_to_sample_set):
    score_class_name = score_config['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    score_config['scorecard_name'] = scorecard_instance.name
    score_config['score_name'] = score_name
    score_instance = score_class(**score_config)

    score_instance.load_data(data=score_config['data'], fresh=fresh)
    score_instance.process_data()

    # Log dataframe information
    logging.info(f"Dataframe info for score {score_name}:")
    logging.info(f"Columns: {score_instance.dataframe.columns.tolist()}")
    logging.info(f"Shape: {score_instance.dataframe.shape}")

    samples = score_instance.dataframe.to_dict('records')

    if 'Good Call comment' in score_instance.dataframe.columns:
        value_counts = score_instance.dataframe['Good Call comment'].value_counts()
        logging.info("Distribution of Good Call comments:")
        logging.info(f"\n{value_counts.to_string()}")
    
    content_ids_to_exclude_filename = f"tuning/{scorecard_name}/{score_name}/training_ids.txt"
    if os.path.exists(content_ids_to_exclude_filename):
        with open(content_ids_to_exclude_filename, 'r') as file:
            content_ids_to_exclude = file.read().splitlines()
        samples = [sample for sample in samples if sample['content_id'] not in content_ids_to_exclude]
        logging.info(f"Number of samples after filtering out training examples: {len(samples)}")

    # Filter samples based on content_ids_to_sample if provided
    if content_ids_to_sample_set:
        content_ids_as_integers = {int(content_id) for content_id in content_ids_to_sample_set}
        samples = [sample for sample in samples if sample['content_id'] in content_ids_as_integers]
        logging.info(f"Number of samples after filtering by specified content IDs: {len(samples)}")

    score_name_column_name = score_name
    if score_config.get('label_score_name'):
        score_name = score_config['label_score_name']
    if score_config.get('label_field'):
        score_name_column_name = f"{score_name} {score_config['label_field']}"

    return [{
        'text': sample.get('text', ''),
        f'{score_name_column_name}_label': sample.get(score_name_column_name, ''),
        'content_id': sample.get('content_id', ''),
        'columns': {k: v for k, v in sample.items() if k not in ['text', score_name, 'content_id']}
    } for sample in samples]

def get_csv_samples(csv_filename):
    if not os.path.exists(csv_filename):
        logging.error(f"labeled-samples.csv not found at {csv_filename}")
        return []

    df = pd.read_csv(csv_filename)
    return df.to_dict('records')

@evaluate.command()
@click.option('--scorecard-name', required=True, help='Name of the scorecard to evaluate')
@click.option('--number-of-samples', default=100, help='Number of samples to evaluate')
@click.option('--subset-of-scores', default='', help='Comma-separated list of score names to evaluate')
@click.option('--max-workers', default=10, help='Maximum number of parallel workers')
def distribution(
    scorecard_name: str,
    number_of_samples: int,
    subset_of_scores: str,
    max_workers: int
):
    start_time = time.time()
    logging.info(f"Starting distribution evaluation for Scorecard {scorecard_name} at {time.strftime('%H:%M:%S')}")

    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)

    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    # We're removing support for a list of scores.
    # scores_to_evaluate = subset_of_scores.split(',') if subset_of_scores else list(scorecard_class.scores.keys())[:10]
    scores_to_evaluate = subset_of_scores
    total_scores = len(scores_to_evaluate)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_score = {executor.submit(evaluate_score_distribution, score_name, scorecard_class, number_of_samples): score_name for score_name in scores_to_evaluate}
        for future in concurrent.futures.as_completed(future_to_score):
            score_name = future_to_score[future]
            try:
                future.result()
            except Exception as exc:
                logging.error(f'{score_name} generated an exception: {exc}')

    end_time = time.time()
    logging.info(f"Finished distribution evaluation at {time.strftime('%H:%M:%S')}. Total time: {end_time - start_time:.2f} seconds")

def evaluate_score_distribution(score_name, scorecard_class, number_of_samples):
    start_time = time.time()
    logging.info(f"Started evaluating distribution for Score {score_name} at {time.strftime('%H:%M:%S')}")
    
    score_configuration = next((score for score in scorecard_class.scores if score['name'] == score_name), {})

    if not score_configuration:
        logging.error(f"Score with name '{score_name}' not found in scorecard '{scorecard_class.name}'.")
        return

    score_class_name = score_configuration['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    if not isinstance(score_class, type):
        logging.error(f"{score_class_name} is not a class.")
        return

    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name
    score_instance = score_class(**score_configuration)

    score_instance.record_configuration(score_configuration)

    logging.info(f"Loading data for {score_name} at {time.strftime('%H:%M:%S')}")
    score_instance.load_data(data=score_configuration['data'])
    
    logging.info(f"Processing data for {score_name} at {time.strftime('%H:%M:%S')}")
    score_instance.process_data()

    logging.info(f"Starting predictions for {score_name} at {time.strftime('%H:%M:%S')}")
    sample_rows = score_instance.dataframe.sample(n=number_of_samples)
    predictions = []

    for _, row in sample_rows.iterrows():
        row_dictionary = row.to_dict()
        text = row_dictionary.get('text', '')
        metadata_str = row_dictionary.get('metadata', '{}')
        metadata = json.loads(metadata_str)
        model_input_class = getattr(score_class, 'Input')
        # Add required metadata for LangGraphScore
        if score_class_name == 'LangGraphScore':
            account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
            if not account_key:
                raise ValueError("PLEXUS_ACCOUNT_KEY not found in environment")
            metadata.update({
                'account_key': account_key,
                'scorecard_key': scorecard_class.key,
                'score_name': score_name
            })
        prediction_result = score_instance.predict(
            model_input_class(
                text=text,
                metadata=metadata
            )
        )
        predictions.append(prediction_result)

    answer_counts = Counter(pred.score for pred in predictions)
    
    logging.info(f"\nResults for {score_name}:")
    logging.info(f"Total samples: {number_of_samples}")
    logging.info(f"Yes answers: {answer_counts['Yes']}")
    logging.info(f"No answers: {answer_counts['No']}")
    
    yes_percentage = (answer_counts['Yes'] / number_of_samples) * 100
    no_percentage = (answer_counts['No'] / number_of_samples) * 100
    
    logging.info(f"Yes percentage: {yes_percentage:.2f}%")
    logging.info(f"No percentage: {no_percentage:.2f}%")
    
    end_time = time.time()
    logging.info(f"Finished {score_name} at {time.strftime('%H:%M:%S')}. Time taken: {end_time - start_time:.2f} seconds")