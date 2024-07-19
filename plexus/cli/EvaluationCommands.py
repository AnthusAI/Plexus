import os
import re
import sys
import click
import yaml

from plexus.CustomLogging import logging
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
from plexus.Experiment import AccuracyExperiment
from plexus.cli.console import console

import rich
import importlib
from rich.pretty import pprint
from plexus.scores.Score import Score
from collections import Counter

from dotenv import load_dotenv
load_dotenv()

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
    number_of_transcripts_to_sample: int = 1,
    sampling_method: str = 'random',
    random_seed: int = None,
    session_ids_to_sample: str = '',
    subset_of_score_names: str = '',
    experiment_label: str = ''):
    """
    Evaluate the accuracy of the scorecard using the current configuration against a labeled samples file.
    These experiment runs will generate metrics and artifacts that Plexus will log in MLFLow.
    The scoring reports from evaluation will include accuracy metrics.
    """

    config = load_configuration_from_yaml_file('./config.yaml')
    scorecard_name = scorecard_name or config.get('scorecard')

    if not scorecard_name:
        logging.error("Scorecard not specified")
        sys.exit(1)

    scorecard_folder = os.path.join('scorecards', scorecard_name)

    labeled_samples_filename = os.path.join(scorecard_folder, 'experiments/labeled-samples.csv')
    override_folder: str = os.path.join(scorecard_folder, 'experiments/calibrations')

    sampling_method = config.get('sampling_method', sampling_method)
    random_seed = config.get('random_seed', random_seed)
    number_of_transcripts_to_sample = config.get('number_of_transcripts_to_sample', number_of_transcripts_to_sample)
    session_ids_to_sample = config.get('session_ids_to_sample', session_ids_to_sample)
    subset_of_score_names = config.get('subset_of_score_names', subset_of_score_names)
    experiment_label = config.get('experiment_label', experiment_label)

    logging.info('Running accuracy experiment...')
    logging.info(f'  Using labeled samples from {labeled_samples_filename}')
    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_type = scorecard_registry.get(scorecard_name)
    if scorecard_type is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return
    # Instantiate the scorecard type and tell it where to find the score definition files.
    scorecard_instance = scorecard_type(scorecard_name=scorecard_name)
    logging.info(f"  Using scorecard {scorecard_name} with class {scorecard_instance.__class__.__name__}")

    with AccuracyExperiment(
        scorecard = scorecard_instance,
        
        labeled_samples_filename = labeled_samples_filename,
        override_folder = override_folder,
    
        # Randomly sample some number of transcripts
        number_of_transcripts_to_sample = number_of_transcripts_to_sample,

        # Sampling: Random or Sequential?
        sampling_method = sampling_method,  # Set to 'random' or 'sequential'
        random_seed = random_seed,

        session_ids_to_sample = re.split(r',\s+', session_ids_to_sample.strip()) if session_ids_to_sample.strip() else None,
        subset_of_score_names = re.split(r',\s+', subset_of_score_names.strip()) if subset_of_score_names.strip() else None,

        experiment_label = experiment_label
    ) as experiment:
        experiment.run()

@evaluate.command()
@click.option('--scorecard-name', required=True, help='Name of the scorecard to evaluate')
@click.option('--number-of-samples', default=100, help='Number of samples to evaluate')
@click.option('--subset-of-scores', default='', help='Comma-separated list of score names to evaluate')
def distribution(
    scorecard_name: str,
    number_of_samples: int,
    subset_of_scores: str
):
    """
    Evaluate the distribution of scores for the scorecard using the current configuration.
    This command will generate distribution metrics and artifacts that Plexus will log in MLFlow.
    """
    logging.info(f"Evaluating distribution for Scorecard [magenta1][b]{scorecard_name}[/b][/magenta1]...")

    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)

    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    logging.info(f"Found registered Scorecard named [magenta1][b]{scorecard_class.name}[/b][/magenta1] implemented in Python class [magenta1][b]{scorecard_class.__name__}[/b][/magenta1]")

    scores_to_evaluate = subset_of_scores.split(',') if subset_of_scores else list(scorecard_class.scores.keys())[:10]
    
    for score_name in scores_to_evaluate:
        evaluate_score_distribution(score_name, scorecard_class, number_of_samples)

def evaluate_score_distribution(score_name, scorecard_class, number_of_samples):
    """
    This function will evaluate the distribution for a single score.
    """
    logging.info(f"Evaluating distribution for Score [magenta1][b]{score_name}[/b][/magenta1]...")
    score_configuration = scorecard_class.scores.get(score_name)

    if not score_configuration:
        logging.error(f"Score with name '{score_name}' not found in scorecard '{scorecard_class.name}'.")
        return

    logging.info(f"Score Configuration: {rich.pretty.pretty_repr(score_configuration)}")

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
    data_queries = score_configuration['data']['queries']
    score_instance.load_data(queries=data_queries)
    score_instance.process_data()

    # Sample and predict
    sample_rows = score_instance.dataframe.sample(n=number_of_samples)
    predictions = []

    for _, row in sample_rows.iterrows():
        row_dictionary = row.to_dict()
        transcript = row_dictionary['Transcription']  # TODO: Eliminate this by making it be the first column.
        model_input_class = getattr(score_class, 'ModelInput')
        prediction_result = score_instance.predict(
            model_input_class(
                transcript=transcript,
                metadata=row_dictionary
            )
        )
        predictions.append(prediction_result)

    # Count Yes/No answers
    answer_counts = Counter(pred.score for pred in predictions)
    
    # Print results
    console.print(f"\n[bold]Results for {score_name}:[/bold]")
    console.print(f"Total samples: {number_of_samples}")
    console.print(f"Yes answers: {answer_counts['Yes']}")
    console.print(f"No answers: {answer_counts['No']}")
    
    # Calculate percentages
    yes_percentage = (answer_counts['Yes'] / number_of_samples) * 100
    no_percentage = (answer_counts['No'] / number_of_samples) * 100
    
    console.print(f"Yes percentage: {yes_percentage:.2f}%")
    console.print(f"No percentage: {no_percentage:.2f}%")

    # TODO: Add more detailed distribution analysis and MLFlow logging here