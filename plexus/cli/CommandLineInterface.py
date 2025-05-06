"""
Main entry point for the Plexus CLI.
"""

from typing import Dict, Any
import click
import os
import json

from plexus.cli.TaskCommands import tasks
from plexus.cli.CommandDispatch import command
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

@click.group()
def main():
    """
    Plexus Command Line Interface.
    """
    pass

main.add_command(tasks)
main.add_command(command)
main.add_command(batch)
main.add_command(evaluate)
main.add_command(evaluations)
main.add_command(predict)
main.add_command(analyze)
main.add_command(tuning)
main.add_command(train)
main.add_command(results)
main.add_command(report)
main.add_command(data)
main.add_command(score_chat)
main.add_command(lake_group)
main.add_command(feedback)

if __name__ == '__main__':
    main()