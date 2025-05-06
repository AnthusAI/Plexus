import click
import os
import time
from dotenv import load_dotenv
from celery import Celery
from plexus.CustomLogging import logging
from kombu.utils.url import safequote
import sys
import rich
from rich.table import Table
from rich.console import Console
import importlib
import builtins
import json
import random
import numpy as np
import threading
import yaml
import logging
import boto3
from botocore.config import Config
from datetime import datetime, timezone, timedelta
from collections import OrderedDict
from typing import Optional, Tuple, List, Dict, Any
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score
)
import textwrap
from rich.markup import escape

from .DataCommands import data
from .EvaluationCommands import evaluate, evaluations
from .TrainingCommands import train
from .PredictionCommands import predict
from .TuningCommands import tuning
from .AnalyzeCommands import analyze
from .console import console
from .BatchCommands import batch
from .CommandDispatch import command, create_cli
from .TaskCommands import tasks
from .ResultCommands import results
from .client_utils import create_client
from .ScoreChatCommands import score_chat
from .ReportCommands import report

# Import dashboard-specific modules
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.evaluation import Evaluation
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.models.task_stage import TaskStage
from plexus.dashboard.commands.simulate import (
    generate_class_distribution,
    simulate_prediction,
    select_metrics_and_explanation,
    calculate_metrics,
    select_num_classes,
    SCORE_GOALS,
    CLASS_SETS
)

# Import centralized logging configuration
from plexus.CustomLogging import setup_logging

# Use centralized logging configuration
setup_logging()
logger = logging.getLogger(__name__)

# Constants from dashboard CLI
SCORE_TYPES = ['binary', 'multiclass']
DATA_BALANCES = ['balanced', 'unbalanced']

def generate_key(name: str) -> str:
    """Generate a URL-safe key from a name."""
    return name.lower().replace(' ', '-')

def main():
    """Main entry point for the CLI."""
    try:
        # Get the fully configured cli object from CommandDispatch
        cli = create_cli() 
        # Run the configured cli object
        cli(standalone_mode=False)
    except click.exceptions.Exit:
        pass
    except Exception as e:
        import traceback
        console.print(f"[red]Error: {escape(str(e))}[/red]")
        console.print(f"[red]Traceback:[/red]")
        console.print(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()