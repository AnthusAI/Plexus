import rich
import click
import importlib
import plexus
import copy

from plexus.CustomLogging import logging
from plexus.cli.shared.console import console
from plexus.Registries import scorecard_registry

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.pretty import pprint

@click.command(help="Train and evaluate a scorecard or specific score within a scorecard.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', help='The name of the score to train.')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
def train(scorecard_name, score_name, fresh):
    """
    This command will handle dispatching to the :func:`plexus.cli.TrainingCommands.train_score` function
    for each score in the scorecard if a scorecard is specified, or for a
    single score if a score is specified.
    """
    logging.info(f"Training Scorecard [magenta1][b]{scorecard_name}[/b][/magenta1]...")

    plexus.Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)

    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    logging.info(f"Found registered Scorecard named [magenta1][b]{scorecard_class.name}[/b][/magenta1] implemented in Python class [magenta1][b]{scorecard_class.__name__}[/b][/magenta1]")

    if score_name:
        train_score(score_name, scorecard_class, fresh)
    else:
        logging.info(f"No score name provided. Training all scores for Scorecard [magenta1][b]{scorecard_class.name}[/b][/magenta1]...")
        for score_name in scorecard_class.scores.keys():
            try:
                train_score(score_name, scorecard_class)
            except Exception as e:
                logging.error(f"Failed to train score '{score_name}': {str(e)}")

def train_score(score_name, scorecard_class, fresh):
    """
    This function will train and evaluate a single score.
    """
    logging.info(f"Training Score [magenta1][b]{score_name}[/b][/magenta1]...")
    score_to_train_configuration = scorecard_class.scores[score_name]

    if score_name not in scorecard_class.scores:
        logging.error(f"Score with name '{score_name}' not found in scorecard '{scorecard_class.name}'.")
        return

    logging.info(f"Score Configuration: {rich.pretty.pretty_repr(score_to_train_configuration)}")

    # Score class instance setup

    score_class_name = score_to_train_configuration['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    if not isinstance(score_class, type):
        logging.error(f"{score_class_name} is not a class.")
        return

    # Add the scorecard name and score name to the parameters.
    score_to_train_configuration['scorecard_name'] = scorecard_class.name
    score_to_train_configuration['score_name'] = score_name
    score_instance = score_class(**score_to_train_configuration)

    # Use the new instance to log its own configuration.
    score_instance.record_configuration(score_to_train_configuration)

    # Data processing
    score_instance.load_data(data=score_to_train_configuration['data'], fresh=fresh)
    score_instance.process_data()

    # Training
    score_instance.train_model()

    # Evaluation
    score_instance.evaluate_model()