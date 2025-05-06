"""
Command module for Plexus feedback management commands.
"""

import click
import logging
from typing import Optional

from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.feedback_change_detail import FeedbackChangeDetail
from plexus.cli.feedback.feedback_commands import purge_all_feedback as purge_command
from plexus.cli.feedback.create_sample_data import create_sample_feedback as create_sample_command
from plexus.cli.feedback.feedback_info import feedback_info as info_command

logger = logging.getLogger(__name__)

@click.group()
def feedback():
    """Commands for managing feedback data."""
    pass

# Register individual commands
feedback.add_command(purge_command, name="purge")
feedback.add_command(create_sample_command, name="create-sample")
feedback.add_command(info_command, name="info") 