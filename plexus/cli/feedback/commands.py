import click
import logging

from plexus.cli.feedback.feedback_commands import purge_all_feedback as purge_command
from plexus.cli.feedback.feedback_invalidation_command import (
    invalidate_feedback as invalidate_command,
    list_invalidated_feedback as invalidated_command,
    uninvalidate_feedback as uninvalidate_command,
)
from plexus.cli.feedback.feedback_info import feedback_info as info_command
from plexus.cli.feedback.feedback_search import find_feedback as find_command
from plexus.cli.feedback.feedback_report import report as report_command
from plexus.cli.feedback.feedback_summary import feedback_summary as summary_command

logger = logging.getLogger(__name__)

@click.group()
def feedback():
    """Commands for managing feedback data."""
    pass

# Register individual commands
feedback.add_command(summary_command, name="summary")  # Add summary first - it should be the primary command
feedback.add_command(find_command, name="find")
feedback.add_command(info_command, name="info")
feedback.add_command(invalidate_command, name="invalidate")
feedback.add_command(uninvalidate_command, name="uninvalidate")
feedback.add_command(invalidated_command, name="invalidated")
feedback.add_command(purge_command, name="purge")
feedback.add_command(report_command, name="report")
