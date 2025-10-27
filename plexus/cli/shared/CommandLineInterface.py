"""
Main entry point for the Plexus CLI.
"""

from typing import Dict, Any
import click
import os
import json
import logging

from plexus.cli.task.tasks import tasks, task
from plexus.cli.item.items import items, item
from plexus.cli.score.scores import score, scores
from plexus.cli.shared.CommandDispatch import command
from plexus.cli.batch.operations import batch
from plexus.cli.evaluation.evaluations import evaluate, evaluations
from plexus.cli.prediction.predictions import predict
from plexus.cli.analyze.analysis import analyze
from plexus.cli.tuning.operations import tuning
from plexus.cli.training.operations import train
from plexus.cli.result.results import score_results, score_result, result, results
from plexus.cli.report.reports import report
from plexus.cli.data.operations import data
from plexus.cli.dataset.datasets import dataset
from plexus.cli.score_chat.chat import score_chat
from plexus.cli.data_lake.operations import lake_group
from plexus.cli.feedback.commands import feedback
from plexus.cli.scorecard.scorecards import scorecards, scorecard
from plexus.cli.record_count.counting import count
from plexus.cli.procedure.procedures import procedure

# Define OrderCommands class for command ordering
class OrderCommands(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)

# Create the main CLI group
@click.group(cls=OrderCommands)
@click.option('--debug', is_flag=True, help="Enable debug logging.")
def cli(debug):
    """
    Plexus CLI for managing scorecards, scores, and evaluations.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    # Get the root logger and set its level. This is more robust than
    # basicConfig, which only works if no handlers are configured.
    root_logger = logging.getLogger()
    
    # If the root logger already has handlers, just update their level
    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.setLevel(log_level)
    else:
        # Otherwise, configure the basicConfig
        logging.basicConfig(level=log_level)
    
    root_logger.setLevel(log_level)

# Register all commands
cli.add_command(score)
cli.add_command(scores)
cli.add_command(tasks)
cli.add_command(task)
cli.add_command(items)
cli.add_command(item)
cli.add_command(command)
cli.add_command(batch)
cli.add_command(evaluate)
cli.add_command(predict)
cli.add_command(analyze)
cli.add_command(tuning)
cli.add_command(train)
cli.add_command(score_results)
cli.add_command(score_result)
cli.add_command(result)
cli.add_command(results)
cli.add_command(report)
cli.add_command(data)
cli.add_command(score_chat)
cli.add_command(lake_group)
cli.add_command(feedback)
cli.add_command(scorecards)
cli.add_command(scorecard)
cli.add_command(evaluations)
cli.add_command(count)
cli.add_command(dataset)
cli.add_command(procedure)

def main():
    """
    Plexus Command Line Interface.
    This function is the entry point when the `plexus` command is run.
    """
    # Load YAML configuration first to set environment variables
    try:
        from plexus.config import load_config
        load_config()
    except Exception as e:
        # Don't fail CLI startup if config loading fails, just log a warning
        logging.warning(f"Failed to load YAML configuration: {e}")
    
    # Execute the main CLI application object
    # Click will handle parsing arguments and dispatching to the correct command.
    cli()

if __name__ == '__main__':
    main()