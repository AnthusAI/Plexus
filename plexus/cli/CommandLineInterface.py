"""
Main entry point for the Plexus CLI.
"""

from typing import Dict, Any
import click
import os
import json
import logging

from plexus.cli.TaskCommands import tasks, task
from plexus.cli.ItemCommands import items, item
from plexus.cli.ScoreCommands import score, scores
from plexus.cli.CommandDispatch import command
from plexus.cli.BatchCommands import batch
from plexus.cli.EvaluationCommands import evaluate, evaluations
from plexus.cli.PredictionCommands import predict
from plexus.cli.AnalyzeCommands import analyze
from plexus.cli.TuningCommands import tuning
from plexus.cli.TrainingCommands import train
from plexus.cli.ResultCommands import score_results, score_result, result, results
from plexus.cli.ReportCommands import report
from plexus.cli.DataCommands import data
from plexus.cli.DatasetCommands import dataset
from plexus.cli.ScoreChatCommands import score_chat
from plexus.cli.DataLakeCommands import lake_group
from plexus.cli.FeedbackCommands import feedback
from plexus.cli.ScorecardCommands import scorecards, scorecard
from plexus.cli.RecordCountCommands import count

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
cli.add_command(evaluations)
cli.add_command(count)
cli.add_command(dataset)

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