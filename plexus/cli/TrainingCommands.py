import rich
import click
import importlib
import plexus
from plexus.logging import logging
from plexus.cli.console import console
from plexus.Registries import scorecard_registry

@click.command()
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', required=True, help='The name of the score to train.')
def train(scorecard_name, score_name):
    """Some classifiers use machine-learning models that require training."""
    logging.info(f"Training Scorecard [magenta1][b]{scorecard_name}[/b][/magenta1]...")

    plexus.Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)

    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    logging.info(f"Found registered Scorecard named [magenta1][b]{scorecard_class.name()}[/b][/magenta1] implemented in Python class [magenta1][b]{scorecard_class.__name__}[/b][/magenta1]")

    logging.info(f"Training Score [magenta1][b]{score_name}[/b][/magenta1]...")
    score_to_train_configuration = scorecard_class.scores[score_name]
    model_configuration = score_to_train_configuration['model']

    logging.info(f"Model Configuration: {rich.pretty.pretty_repr(model_configuration)}")

    # Classifier class instance setup

    classifier_class_name = model_configuration['class']
    classifier_module_path = f'plexus.classifiers.{classifier_class_name}'
    classifier_module = importlib.import_module(classifier_module_path)
    classifier_class = getattr(classifier_module, classifier_class_name)

    if not isinstance(classifier_class, type):
        logging.error(f"{classifier_class_name} is not a class.")
        return

    classifier_parameters = model_configuration['parameters']
    # Add the scorecard name and score name to the parameters.
    classifier_parameters['scorecard_name'] = scorecard_class.name()
    classifier_parameters['score_name'] = score_name
    classifier_instance = classifier_class(**classifier_parameters)

    # Data processing
    data_queries = score_to_train_configuration['data']['queries']
    classifier_instance.load_data(queries=data_queries)
    classifier_instance.process_data()

    # Training
    classifier_instance.train_model()
