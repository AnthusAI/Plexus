import os
import re
import sys
import click
import yaml
import pandas as pd

from plexus.CustomLogging import logging
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
from plexus.Experiment import AccuracyExperiment
from plexus.cli.console import console

import importlib
from collections import Counter
import concurrent.futures
import time
import threading

from dotenv import load_dotenv
load_dotenv()

# Add this at the top of your file
console_lock = threading.Lock()

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
def accuracy(
    scorecard_name: str,
    number_of_texts_to_sample: int = 1,
    sampling_method: str = 'random',
    random_seed: int = None,
    session_ids_to_sample: str = '',
    subset_of_score_names: str = '',
    experiment_label: str = ''):
    """
    Evaluate the accuracy of the scorecard using the current configuration against labeled samples.
    These experiment runs will generate metrics and artifacts that Plexus will log in MLFLow.
    The scoring reports from evaluation will include accuracy metrics.
    """

    config = load_configuration_from_yaml_file('./config.yaml')
    scorecard_name = scorecard_name or config.get('scorecard')

    if not scorecard_name:
        logging.error("Scorecard not specified")
        sys.exit(1)

    scorecard_folder = os.path.join('scorecards', scorecard_name)

    override_folder: str = os.path.join(scorecard_folder, 'experiments/calibrations')

    sampling_method = config.get('sampling_method', sampling_method)
    random_seed = config.get('random_seed', random_seed)
    number_of_texts_to_sample = config.get('number_of_texts_to_sample', number_of_texts_to_sample)
    session_ids_to_sample = config.get('session_ids_to_sample', session_ids_to_sample)
    subset_of_score_names = config.get('subset_of_score_names', subset_of_score_names)
    experiment_label = config.get('experiment_label', experiment_label)

    logging.info('Running accuracy experiment...')
    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_type = scorecard_registry.get(scorecard_name)
    if scorecard_type is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return
    # Instantiate the scorecard type and tell it where to find the score definition files.
    scorecard_instance = scorecard_type(scorecard_name=scorecard_name)
    logging.info(f"  Using scorecard {scorecard_name} with class {scorecard_instance.__class__.__name__}")

    # Check if any score in the scorecard uses the data-driven approach
    uses_data_driven = any('data' in score_config for score_config in scorecard_instance.scores.values())

    if uses_data_driven:
        labeled_samples = []
        for score_name, score_config in scorecard_instance.scores.items():
            if 'data' in score_config:
                labeled_samples.extend(get_data_driven_samples(scorecard_instance, scorecard_name, score_name, score_config))
    else:
        labeled_samples_filename = os.path.join('scorecards', scorecard_instance.properties.get('key'), 'experiments', 'labeled-samples.csv')

    experiment_args = {
        'scorecard': scorecard_instance,
        'override_folder': override_folder,
        'number_of_texts_to_sample': number_of_texts_to_sample,
        'sampling_method': sampling_method,
        'random_seed': random_seed,
        'session_ids_to_sample': re.split(r',\s+', session_ids_to_sample.strip()) if session_ids_to_sample.strip() else None,
        'subset_of_score_names': re.split(r',\s+', subset_of_score_names.strip()) if subset_of_score_names.strip() else None,
        'experiment_label': experiment_label
    }

    if uses_data_driven:
        experiment_args['labeled_samples'] = labeled_samples
    else:
        experiment_args['labeled_samples_filename'] = labeled_samples_filename

    with AccuracyExperiment(**experiment_args) as experiment:
        experiment.run()

def get_data_driven_samples(scorecard_instance, scorecard_name, score_name, score_config):
    score_class_name = score_config['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    score_config['scorecard_name'] = scorecard_instance.name
    score_config['score_name'] = score_name
    score_instance = score_class(**score_config)

    score_instance.load_data(queries=score_config['data'].get('queries'))
    score_instance.process_data()

    # Log dataframe information
    logging.info(f"Dataframe info for score {score_name}:")
    logging.info(f"Columns: {score_instance.dataframe.columns.tolist()}")
    logging.info(f"Shape: {score_instance.dataframe.shape}")
    logging.info(f"Sample data:\n{score_instance.dataframe.head().to_string()}")

    samples = score_instance.dataframe.to_dict('records')
    
    # Filter out rows that were included in fine-tuning training exmaples,
    # if a file exists.
    content_ids_to_exclude_filename = f"tuning/{scorecard_name}/{score_name}/{score_config['base_model_name']}_training_ids.txt"
    if os.path.exists(content_ids_to_exclude_filename):
        with open(content_ids_to_exclude_filename, 'r') as file:
            content_ids_to_exclude = file.read().splitlines()
        samples = [sample for sample in samples if sample['content_id'] not in content_ids_to_exclude]
        logging.info(f"Number of samples after filtering: {len(samples)}")

    return [{
        'text': sample.get('text', ''),
        f'{score_name}_label': sample.get(score_name, ''),
        'content_id': sample.get('content_id', ''),
        'metadata': {k: v for k, v in sample.items() if k not in ['text', score_name, 'content_id']}
    } for sample in samples]

def get_csv_samples(csv_filename):
    if not os.path.exists(csv_filename):
        logging.error(f"labeled-samples.csv not found at {csv_filename}")
        return []

    try:
        df = pd.read_csv(csv_filename)
        return df.to_dict('records')
    except Exception as e:
        logging.error(f"Failed to load or process data from {csv_filename}: {str(e)}")
        return []

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
    """
    Evaluate the distribution of scores for the scorecard using the current configuration.
    This command will generate distribution metrics and artifacts that Plexus will log in MLFlow.
    """
    start_time = time.time()
    console.print(f"[bold magenta]Starting distribution evaluation for Scorecard {scorecard_name} at {time.strftime('%H:%M:%S')}[/bold magenta]")

    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)

    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    scores_to_evaluate = subset_of_scores.split(',') if subset_of_scores else list(scorecard_class.scores.keys())[:10]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_score = {executor.submit(evaluate_score_distribution, score_name, scorecard_class, number_of_samples): score_name for score_name in scores_to_evaluate}
        for future in concurrent.futures.as_completed(future_to_score):
            score_name = future_to_score[future]
            try:
                future.result()
            except Exception as exc:
                logging.error(f'{score_name} generated an exception: {exc}')

    end_time = time.time()
    console.print(f"[bold magenta]Finished distribution evaluation at {time.strftime('%H:%M:%S')}. Total time: {end_time - start_time:.2f} seconds[/bold magenta]")

def evaluate_score_distribution(score_name, scorecard_class, number_of_samples):
    """
    This function will evaluate the distribution for a single score.
    """
    start_time = time.time()
    with console_lock:
        console.print(f"[bold blue]Started evaluating distribution for Score {score_name} at {time.strftime('%H:%M:%S')}[/bold blue]")
    
    score_configuration = scorecard_class.scores.get(score_name)

    if not score_configuration:
        logging.error(f"Score with name '{score_name}' not found in scorecard '{scorecard_class.name}'.")
        return

    # Score class instance setup
    score_class_name = score_configuration['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    if not isinstance(score_class, type):
        logging.error(f"{score_class_name} is not a class.")
        return

    # Add the scorecard name and score name to the parameters.
    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name
    score_instance = score_class(**score_configuration)

    # Use the new instance to log its own configuration.
    score_instance.record_configuration(score_configuration)

    # Data processing
    with console_lock:
        console.print(f"[yellow]Loading data for {score_name} at {time.strftime('%H:%M:%S')}[/yellow]")
    data_queries = score_configuration['data']['queries']
    score_instance.load_data(queries=data_queries)
    
    with console_lock:
        console.print(f"[yellow]Processing data for {score_name} at {time.strftime('%H:%M:%S')}[/yellow]")
    score_instance.process_data()

    # Sample and predict
    with console_lock:
        console.print(f"[yellow]Starting predictions for {score_name} at {time.strftime('%H:%M:%S')}[/yellow]")
    sample_rows = score_instance.dataframe.sample(n=number_of_samples)
    predictions = []

    for _, row in sample_rows.iterrows():
        row_dictionary = row.to_dict()
        text = row_dictionary['text']
        model_input_class = getattr(score_class, 'Input')
        prediction_result = score_instance.predict(
            model_input_class(
                text=text,
                metadata=row_dictionary
            )
        )
        predictions.append(prediction_result)

    # Count Yes/No answers
    answer_counts = Counter(pred.score for pred in predictions)
    
    with console_lock:
        console.print(f"\n[bold green]Results for {score_name}:[/bold green]")
        console.print(f"Total samples: {number_of_samples}")
        console.print(f"Yes answers: {answer_counts['Yes']}")
        console.print(f"No answers: {answer_counts['No']}")
        
        yes_percentage = (answer_counts['Yes'] / number_of_samples) * 100
        no_percentage = (answer_counts['No'] / number_of_samples) * 100
        
        console.print(f"Yes percentage: {yes_percentage:.2f}%")
        console.print(f"No percentage: {no_percentage:.2f}%")
        
        end_time = time.time()
        console.print(f"[bold blue]Finished {score_name} at {time.strftime('%H:%M:%S')}. Time taken: {end_time - start_time:.2f} seconds[/bold blue]")

    # TODO: Add more detailed distribution analysis and MLFlow logging here