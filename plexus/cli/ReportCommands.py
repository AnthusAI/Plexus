"""
Command module for Plexus report generation commands.
"""

import click
import logging
import json
import traceback
from datetime import datetime, timezone
from typing import Optional, Tuple
import sys
import os # Added for file operations
from pathlib import Path # Added for path handling

# Import necessary utilities and models
from plexus.cli.console import console
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.report_configuration import ReportConfiguration
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.task import Task
from plexus.tasks.reports import generate_report_task
from rich.table import Table # Import Table for display
from rich.panel import Panel
from rich.pretty import pretty_repr
from rich.syntax import Syntax # Added for JSON highlighting
from dataclasses import asdict
import uuid # Added for UUID validation
from gql.transport.exceptions import TransportQueryError # Added import
from gql import gql # Added import for gql function
from rich.markup import escape # Added escape import
from rich.markdown import Markdown # Add Markdown import
from rich.console import Group # Add Group import
from rich.text import Text # Add Text import

# Import the refactored service function and tracker
from plexus.reports.service import _generate_report_core
from plexus.cli.task_progress_tracker import TaskProgressTracker, StageConfig # Restore full import

from plexus.cli.utils import parse_kv_pairs # Assume this exists

# Import Account model for resolving ID
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.report_block import ReportBlock # Added for fetching blocks

from plexus.cli.reports.utils import (
    resolve_account_id_for_command,
    format_kv,
    resolve_report_config,
    build_report_info_table,
    resolve_report # Add the missing import
)

from .reports.config_commands import config as config_group
from .reports.report_commands import (
    run as run_command,
    list_reports as list_reports_command,
    show_report as show_report_command,
    show_last_report as show_last_command
)

logger = logging.getLogger(__name__)

@click.group()
def report():
    """Commands for managing and running reports."""
    pass

# Register imported command groups
report.add_command(config_group)

# Register imported individual commands
report.add_command(run_command)
report.add_command(list_reports_command, name="list") # Explicitly name list
report.add_command(show_report_command, name="show") # Explicitly name show
report.add_command(show_last_command, name="last") # Explicitly name last
