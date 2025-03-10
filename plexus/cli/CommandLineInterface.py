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
from .TaskCommands import tasks
from .ScorecardCommands import scorecards
from .ScoreCommands import scores, score
from .ResultCommands import results

# Import dashboard-specific modules
from plexus.dashboard.api.client import PlexusDashboardClient
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

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    logger.debug(f"Using API URL: {client.api_url}")
    return client

class OrderCommands(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)

@click.group(cls=OrderCommands)
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
cli.add_command(tasks)
cli.add_command(scorecards)
cli.add_command(scores)
cli.add_command(score)
cli.add_command(results)

# Helper functions
def format_scorecard_panel(scorecard, include_sections=False, detailed_scores=False):
    """
    Format a scorecard as a rich panel with consistent styling.
    
    Args:
        scorecard: The scorecard data to format
        include_sections: Whether to include sections and scores in the output
        detailed_scores: Whether to show detailed information for each score
        
    Returns:
        A rich Panel object with formatted scorecard content
    """
    # Find the longest label for alignment
    labels = ["Name:", "Key:", "External ID:", "Description:", "Created:", "Updated:", "Total Scores:"]
    max_label_length = max(len(label) for label in labels)
    
    # Prepare content with aligned columns and color-coded values
    content = []
    
    # Scorecard Information - ID is removed from content as it's already in the panel title
    content.append(f"{'Name:':<{max_label_length}} [blue]{scorecard.get('name', 'N/A')}[/blue]")
    content.append(f"{'Key:':<{max_label_length}} [blue]{scorecard.get('key', 'N/A')}[/blue]")
    content.append(f"{'External ID:':<{max_label_length}} [magenta]{scorecard.get('externalId', 'N/A')}[/magenta]")
    
    description = scorecard.get('description', '')
    if description:
        content.append(f"{'Description:':<{max_label_length}} [blue]{description}[/blue]")
    
    created_at = scorecard.get('createdAt', 'N/A')
    updated_at = scorecard.get('updatedAt', 'N/A')
    content.append(f"{'Created:':<{max_label_length}} [dim]{created_at}[/dim]")
    content.append(f"{'Updated:':<{max_label_length}} [dim]{updated_at}[/dim]")
    
    # Sections and Scores if requested
    if include_sections and 'sections' in scorecard and scorecard['sections']:
        sections = scorecard['sections'].get('items', [])
        total_scores = sum(len(section.get('scores', {}).get('items', [])) for section in sections)
        content.append("")
        content.append(f"{'Total Scores:':<{max_label_length}} [magenta]{total_scores}[/magenta]")
        
        if total_scores > 0:
            content.append("")
            content.append("[bold]Sections and Scores[/bold]")
            
            # Sort sections by order
            sorted_sections = sorted(sections, key=lambda s: s.get('order', 0))
            
            for i, section in enumerate(sorted_sections):
                section_prefix = "└── " if i == len(sorted_sections) - 1 else "├── "
                section_name = section.get('name', 'Unnamed Section')
                content.append(f"{section_prefix}[bold][blue]{section_name}[/blue][/bold]")
                
                if 'scores' in section and section['scores']:
                    # Sort scores by order
                    sorted_scores = sorted(section['scores'].get('items', []), key=lambda s: s.get('order', 0))
                    
                    for j, score in enumerate(sorted_scores):
                        is_last_score = j == len(sorted_scores) - 1
                        is_last_section = i == len(sorted_sections) - 1
                        
                        if is_last_section:
                            score_prefix = "    └── " if is_last_score else "    ├── "
                        else:
                            score_prefix = "│   └── " if is_last_score else "│   ├── "
                        
                        score_name = score.get('name', 'Unnamed Score')
                        content.append(f"{score_prefix}[blue]{score_name}[/blue]")
                        
                        # Add detailed score information if requested
                        if detailed_scores:
                            score_id = score.get('id', 'N/A')
                            score_key = score.get('key', 'N/A')
                            indent_prefix = score_prefix.replace("└──", "    ").replace("├──", "│   ")
                            content.append(f"{indent_prefix}  ID: [magenta]{score_id}[/magenta]")
                            content.append(f"{indent_prefix}  Key: [blue]{score_key}[/blue]")
    
    # Create panel with the content
    panel = rich.panel.Panel(
        "\n".join(content),
        title=f"[bold magenta]{scorecard.get('id', 'Scorecard')}[/bold magenta]",
        expand=True,
        padding=(1, 2)
    )
    
    return panel

def main():
    """Main entry point for the CLI."""
    try:
        cli(standalone_mode=False)
    except click.exceptions.Exit:
        pass
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

if __name__ == '__main__':
    main()