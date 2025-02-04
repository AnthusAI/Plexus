import os
from dotenv import load_dotenv
load_dotenv('.env', override=True)

import sys
import click
import importlib
import builtins
import json
import random
import time
import numpy as np
import threading
import yaml
import logging
import boto3
from botocore.config import Config
from datetime import datetime, timezone, timedelta
from rich.console import Console
from collections import OrderedDict
from typing import Optional
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score
)

from .DataCommands import data
from .EvaluationCommands import evaluate
from .TrainingCommands import train
from .ReportingCommands import report
from .PredictionCommands import predict
from .TuningCommands import tuning
from .AnalyzeCommands import analyze
from .console import console
from .BatchCommands import batch
from .CommandDispatch import command

# Import dashboard-specific modules
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.evaluation import Evaluation
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.dashboard.commands.simulate import (
    generate_class_distribution,
    simulate_prediction,
    select_metrics_and_explanation,
    calculate_metrics,
    select_num_classes,
    SCORE_GOALS,
    CLASS_SETS
)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants from dashboard CLI
SCORE_TYPES = ['binary', 'multiclass']
DATA_BALANCES = ['balanced', 'unbalanced']

def generate_key(name: str) -> str:
    """Generate a URL-safe key from a name."""
    return name.lower().replace(' ', '-')

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    logger.debug(f"Using API URL: {client.api_url}")
    return client

class OrderCommands(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)

@click.group(cls=OrderCommands)
def main():
    """
    Plexus is an orchestration system for AI/ML content classification.

    For machine-learning scores that require data preparation, the `data` command includes subcommands for data analysis and preparation.

    For classifiers that require training, the `train` command includes subcommands for training and evaluating models, using MLFlow for logging experiment results.

    For evaluating LLM-based classifiers for prompt engineering, the `evaluate` command includes subcommands for evaluating prompts.

    For scoring content at inference time, the `score` command includes subcommands for scoring content.  The scoring reports will not include accuracy metrics.

    For reporting on training and evaluation results, the `report` command includes subcommands for generating reports.

    For more information, please visit https://plexus.anth.us
    """
    pass

# Add original commands
main.add_command(data)
main.add_command(evaluate)
main.add_command(train)
main.add_command(report)
main.add_command(predict)
main.add_command(tuning)
main.add_command(analyze)
main.add_command(batch)
main.add_command(command)

# Dashboard CLI Commands
@main.group()
def evaluations():
    """Manage evaluations"""
    pass

@evaluations.command()
@click.option('--account-key', default='call-criteria', help='Account key identifier')
@click.option('--type', required=True, help='Type of evaluation (e.g., accuracy, consistency)')
@click.option('--parameters', type=str, help='JSON string of evaluation parameters')
@click.option('--metrics', type=str, help='JSON string of evaluation metrics')
@click.option('--inferences', type=int, help='Number of inferences made')
@click.option('--results', type=int, help='Number of results processed')
@click.option('--cost', type=float, help='Cost of the evaluation')
@click.option('--progress', type=float, help='Progress percentage (0-100)')
@click.option('--accuracy', type=float, help='Accuracy percentage (0-100)')
@click.option('--accuracy-type', help='Type of accuracy measurement')
@click.option('--sensitivity', type=float, help='Sensitivity/recall percentage (0-100)')
@click.option('--specificity', type=float, help='Specificity percentage (0-100)')
@click.option('--precision', type=float, help='Precision percentage (0-100)')
@click.option('--status', default='PENDING', 
              type=click.Choice(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']),
              help='Status of the evaluation')
@click.option('--total-items', type=int, help='Total number of items to process')
@click.option('--processed-items', type=int, help='Number of items processed')
@click.option('--error-message', help='Error message if evaluation failed')
@click.option('--error-details', type=str, help='JSON string of detailed error information')
@click.option('--scorecard-id', help='Scorecard ID (if known)')
@click.option('--scorecard-key', help='Scorecard key to look up')
@click.option('--scorecard-name', help='Scorecard name to look up')
@click.option('--score-id', help='Score ID (if known)')
@click.option('--score-key', help='Score key to look up')
@click.option('--score-name', help='Score name to look up')
@click.option('--confusion-matrix', type=str, help='JSON string of confusion matrix data')
def create(
    account_key: str,
    type: str,
    parameters: Optional[str] = None,
    metrics: Optional[str] = None,
    inferences: Optional[int] = None,
    results: Optional[int] = None,
    cost: Optional[float] = None,
    progress: Optional[float] = None,
    accuracy: Optional[float] = None,
    accuracy_type: Optional[str] = None,
    sensitivity: Optional[float] = None,
    specificity: Optional[float] = None,
    precision: Optional[float] = None,
    status: str = 'PENDING',
    total_items: Optional[int] = None,
    processed_items: Optional[int] = None,
    error_message: Optional[str] = None,
    error_details: Optional[str] = None,
    scorecard_id: Optional[str] = None,
    scorecard_key: Optional[str] = None,
    scorecard_name: Optional[str] = None,
    score_id: Optional[str] = None,
    score_key: Optional[str] = None,
    score_name: Optional[str] = None,
    confusion_matrix: Optional[str] = None,
):
    """Create a new dashboard evaluation with specified attributes."""
    # ... [rest of the create function implementation] ...

@evaluations.command()
@click.argument('id', required=True)
@click.option('--type', help='Type of evaluation (e.g., accuracy, consistency)')
@click.option('--status',
              type=click.Choice(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']),
              help='Status of the evaluation')
@click.option('--parameters', type=str, help='JSON string of evaluation parameters')
@click.option('--metrics', type=str, help='JSON string of evaluation metrics')
@click.option('--inferences', type=int, help='Number of inferences made')
@click.option('--results', type=int, help='Number of results processed')
@click.option('--cost', type=float, help='Cost of the evaluation')
@click.option('--progress', type=float, help='Progress percentage (0-100)')
@click.option('--accuracy', type=float, help='Accuracy percentage (0-100)')
@click.option('--accuracy-type', help='Type of accuracy measurement')
@click.option('--sensitivity', type=float, help='Sensitivity/recall percentage (0-100)')
@click.option('--specificity', type=float, help='Specificity percentage (0-100)')
@click.option('--precision', type=float, help='Precision percentage (0-100)')
@click.option('--total-items', type=int, help='Total number of items to process')
@click.option('--processed-items', type=int, help='Number of items processed')
@click.option('--error-message', help='Error message if evaluation failed')
@click.option('--error-details', type=str, help='JSON string of detailed error information')
@click.option('--scorecard-id', help='Scorecard ID (if known)')
@click.option('--scorecard-key', help='Scorecard key to look up')
@click.option('--scorecard-name', help='Scorecard name to look up')
@click.option('--score-id', help='Score ID (if known)')
@click.option('--score-key', help='Score key to look up')
@click.option('--score-name', help='Score name to look up')
@click.option('--confusion-matrix', type=str, help='JSON string of confusion matrix data')
def update(
    id: str,
    type: Optional[str] = None,
    status: Optional[str] = None,
    parameters: dict = None,
    metrics: dict = None,
    inferences: list = None,
    results: list = None,
    cost: float = None,
    progress: float = None,
    accuracy: float = None,
    accuracy_type: str = None,
    sensitivity: float = None,
    specificity: float = None,
    precision: float = None,
    total_items: int = None,
    processed_items: int = None,
    error_message: str = None,
    error_details: dict = None,
    confusion_matrix: dict = None
):
    """Update an existing dashboard evaluation."""
    # ... [rest of the update function implementation] ...

@evaluations.command()
@click.argument('id', required=True)
@click.option('--limit', type=int, default=1000, help='Maximum number of results to return')
def list_results(id: str, limit: int):
    """List score results for a dashboard evaluation"""
    # ... [rest of the list_results function implementation] ...

@main.group()
def scores():
    """Manage score results"""
    pass

@scores.command()
@click.option('--value', type=float, required=True, help='Score value')
@click.option('--item-id', required=True, help='ID of the item being scored')
@click.option('--account-id', required=True, help='ID of the account')
@click.option('--scoring-job-id', required=True, help='ID of the scoring job')
@click.option('--scorecard-id', required=True, help='ID of the scorecard')
@click.option('--confidence', type=float, help='Confidence score (optional)')
@click.option('--metadata', type=str, help='JSON metadata (optional)')
def create_score(value, item_id, account_id, scoring_job_id, scorecard_id, confidence, metadata):
    """Create a new dashboard score result"""
    # ... [rest of the create_score function implementation] ...

@main.group()
def scorecards():
    """Manage scorecards"""
    pass

@scorecards.command()
@click.option('--account-key', help='Filter by account key')
@click.option('--name', help='Filter by name')
@click.option('--key', help='Filter by key')
def list_scorecards(account_key: Optional[str], name: Optional[str], key: Optional[str]):
    """List dashboard scorecards with optional filtering"""
    # ... [rest of the list_scorecards function implementation] ...

@scorecards.command()
@click.option('--account-key', default='call-criteria', help='Account key identifier')
@click.option('--directory', default='scorecards', help='Directory containing YAML scorecard files')
def sync(account_key: str, directory: str):
    """Sync YAML scorecards to the dashboard API"""
    # ... [rest of the sync function implementation] ...

@scorecards.command()
@click.option('--account-key', required=True, help='Account key')
@click.option('--fix', is_flag=True, help='Fix duplicates by removing newer copies')
def find_duplicates(account_key: str, fix: bool):
    """Find and optionally fix duplicate scores based on name+order+section combination"""
    # ... [rest of the find_duplicates function implementation] ...

@scorecards.command()
@click.option('--scorecard-id', help='Scorecard ID')
@click.option('--scorecard-key', help='Scorecard key')
@click.option('--scorecard-name', help='Scorecard name')
def list_scores(scorecard_id: Optional[str], scorecard_key: Optional[str], scorecard_name: Optional[str]):
    """List all scores for a specific dashboard scorecard"""
    # ... [rest of the list_scores function implementation] ...

def load_plexus_extensions():
    """Load Plexus extensions from the plexus_extensions directory"""
    logger.debug("Loading Plexus extensions...")
    extensions_path = os.path.join(os.getcwd(), 'plexus_extensions')
    
    if os.path.isdir(extensions_path):
        sys.path.insert(0, extensions_path)
        sys.path.insert(0, os.path.join(os.getcwd(), '.'))

        for root, _, files in os.walk(extensions_path):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    logger.debug(f"Loading extension: {file}")
                    module_name = file[:-3]
                    imported_module = importlib.import_module(module_name)
                    logger.debug(f"Loaded extension module: {module_name}")
                    
                    for attr_name in dir(imported_module):
                        attr = getattr(imported_module, attr_name)
                        if isinstance(attr, type):
                            setattr(builtins, attr_name, attr)
                            logger.debug(f"Registered class {attr_name} globally in builtins")
    else:
        logger.debug("No extensions folder found.")

# Call this function during CLI initialization
load_plexus_extensions()