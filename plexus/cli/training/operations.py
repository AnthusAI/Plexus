import rich
import click
import importlib
import plexus
import copy

from plexus.CustomLogging import logging
from plexus.cli.shared.console import console
from plexus.Registries import scorecard_registry
from plexus.training import TrainingDispatcher

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
@click.option('--training-type', type=click.Choice(['ml', 'llm-finetune']), help='Override training type (ml or llm-finetune).')
@click.option('--target', type=click.Choice(['local', 'sagemaker']), help='Override training target (local or sagemaker).')
@click.option('--epochs', type=int, help='Number of training epochs (ML training only).')
@click.option('--batch-size', type=int, help='Batch size (ML training only).')
@click.option('--learning-rate', type=float, help='Learning rate (ML training only).')
@click.option('--maximum-number', type=int, help='Total examples to generate (LLM fine-tuning only).')
@click.option('--train-ratio', type=float, help='Training/validation split ratio (LLM fine-tuning only).')
@click.option('--threads', type=int, help='Parallel processing threads (LLM fine-tuning only).')
@click.option('--clean-existing', is_flag=True, help='Remove existing output files first (LLM fine-tuning only).')
@click.option('--verbose', is_flag=True, help='Enable verbose output.')
def train(scorecard_name, score_name, fresh, training_type, target,
          epochs, batch_size, learning_rate,
          maximum_number, train_ratio, threads, clean_existing, verbose):
    """
    Unified training command for ML models and LLM fine-tuning.

    Auto-detects training type from Score configuration, with CLI overrides available.
    Supports multiple training workflows through Trainer abstraction.
    """
    logging.info(f"Training Scorecard [magenta1][b]{scorecard_name}[/b][/magenta1]...")

    # Build extra parameters from CLI flags
    extra_params = {}
    if epochs is not None:
        extra_params['epochs'] = epochs
    if batch_size is not None:
        extra_params['batch_size'] = batch_size
    if learning_rate is not None:
        extra_params['learning_rate'] = learning_rate
    if maximum_number is not None:
        extra_params['maximum_number'] = maximum_number
    if train_ratio is not None:
        extra_params['train_ratio'] = train_ratio
    if threads is not None:
        extra_params['threads'] = threads
    if clean_existing:
        extra_params['clean_existing'] = clean_existing
    if verbose:
        extra_params['verbose'] = verbose

    if score_name:
        # Train single score using TrainingDispatcher
        result = train_score_with_dispatcher(
            scorecard_name, score_name, fresh,
            training_type, target, extra_params
        )

        # Display results
        _display_training_result(result, score_name)
    else:
        # Train all scores in scorecard
        logging.info(f"No score name provided. Training all scores for Scorecard [magenta1][b]{scorecard_name}[/b][/magenta1]...")

        # Load scorecard to get score names
        plexus.Scorecard.load_and_register_scorecards('scorecards/')
        scorecard_class = scorecard_registry.get(scorecard_name)

        if not scorecard_class:
            logging.error(f"Scorecard '{scorecard_name}' not found.")
            return

        # Get score names (handle both dict and list formats)
        if isinstance(scorecard_class.scores, dict):
            score_names = list(scorecard_class.scores.keys())
        else:
            score_names = [s.get('name', 'Unknown') for s in scorecard_class.scores if isinstance(s, dict)]

        # Train each score
        results = []
        for name in score_names:
            try:
                result = train_score_with_dispatcher(
                    scorecard_name, name, fresh,
                    training_type, target, extra_params
                )
                results.append((name, result))
            except Exception as e:
                logging.error(f"Failed to train score '{name}': {str(e)}")

        # Display summary
        _display_batch_training_summary(results)


def train_score_with_dispatcher(scorecard_name: str, score_name: str,
                                 fresh: bool,
                                 training_type_override: str,
                                 target_override: str,
                                 extra_params: dict):
    """
    Train a single score using TrainingDispatcher.

    Args:
        scorecard_name: Name of the scorecard
        score_name: Name of the score
        fresh: Pull fresh data from data lake
        training_type_override: Optional training type override
        target_override: Optional target override
        extra_params: Additional parameters from CLI flags

    Returns:
        TrainingResult
    """
    dispatcher = TrainingDispatcher(
        scorecard_name=scorecard_name,
        score_name=score_name,
        training_type_override=training_type_override,
        target_override=target_override,
        fresh=fresh,
        **extra_params
    )

    return dispatcher.dispatch()


def _display_training_result(result, score_name: str):
    """Display training result in Rich format."""
    if result.success:
        logging.info(f"\n[green]✓[/green] Training completed successfully for [magenta1][b]{score_name}[/b][/magenta1]")

        # Display metrics
        if result.metrics:
            logging.info("\nMetrics:")
            for key, value in result.metrics.items():
                logging.info(f"  {key}: {value}")

        # Display artifacts
        if result.artifacts:
            logging.info("\nArtifacts:")
            for artifact_type, location in result.artifacts.items():
                logging.info(f"  {artifact_type}: {location}")
    else:
        logging.error(f"\n[red]✗[/red] Training failed for [magenta1][b]{score_name}[/b][/magenta1]")
        logging.error(f"Error: {result.error}")


def _display_batch_training_summary(results: list):
    """Display summary of batch training results."""
    successful = sum(1 for _, r in results if r.success)
    total = len(results)

    logging.info(f"\n{'='*80}")
    logging.info(f"Batch Training Summary: {successful}/{total} successful")
    logging.info(f"{'='*80}")

    for score_name, result in results:
        status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
        logging.info(f"{status} {score_name}: {result.training_type}")

        if not result.success:
            logging.error(f"    Error: {result.error}")