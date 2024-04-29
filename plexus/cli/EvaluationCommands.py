import os
import re
import sys
import click
import yaml

from plexus.CustomLogging import logging

from plexus.Registries import scorecard_registry
from plexus.scorecards.TermLifeAI import TermLifeAI

from plexus.Experiment import AccuracyExperiment

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
@click.option('--scorecard', 'scorecard_name', default=None, help='Name of the scorecard to evaluate')
def accuracy(
    scorecard_name: str = 'term-life-ai',
    scorecard_folder: str = 'scorecards/TermLifeAI',
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
    scorecard_type = scorecard_registry.get(scorecard_name)
    if scorecard_type is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return
    # Instantiate the scorecard type and tell it where to find the score definition files.
    scorecard_instance = scorecard_type(scorecard_folder_path="scorecards/TermLifeAI")
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

