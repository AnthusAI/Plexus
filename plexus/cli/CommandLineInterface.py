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
from .EvaluationCommands import evaluate, evaluations
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

def cli():
    """
    Plexus CLI for managing scorecards, scores, and evaluations.
    """
    pass

# Add original commands
cli.add_command(data)
cli.add_command(evaluate)
cli.add_command(train)
cli.add_command(report)
cli.add_command(predict)
cli.add_command(tuning)
cli.add_command(analyze)
cli.add_command(batch)
cli.add_command(command)

# Dashboard CLI Commands
cli.add_command(evaluations)

@cli.group()
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

@cli.group()
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