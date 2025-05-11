"""
Main entry point for the Plexus CLI.
"""

from typing import Dict, Any
import click
import os
import json

from plexus.cli.TaskCommands import tasks
from plexus.cli.CommandDispatch import command, create_cli
from plexus.cli.BatchCommands import batch
from plexus.cli.EvaluationCommands import evaluate, evaluations
from plexus.cli.PredictionCommands import predict
from plexus.cli.AnalyzeCommands import analyze
from plexus.cli.TuningCommands import tuning
from plexus.cli.TrainingCommands import train
from plexus.cli.ResultCommands import results
from plexus.cli.ReportCommands import report
from plexus.cli.DataCommands import data
from plexus.cli.ScoreChatCommands import score_chat
from plexus.cli.DataLakeCommands import lake_group
from plexus.cli.FeedbackCommands import feedback

# Create the main CLI application object using the factory from CommandDispatch
# This 'cli' variable can now be imported by other modules if needed.
cli = create_cli()

def main():
    """
    Plexus Command Line Interface.
    This function is the entry point when the `plexus` command is run.
    """
    # Execute the main CLI application object
    # Click will handle parsing arguments and dispatching to the correct command.
    cli()

if __name__ == '__main__':
    main()