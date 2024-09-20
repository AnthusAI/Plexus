from rich.console import Console
from rich.logging import RichHandler
import logging
import sys
import os
import watchtower
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# Create a Rich console specifically for output
console = Console()

# Default log group name
if os.getenv("environment"):
    DEFAULT_LOG_GROUP = f'plexus/{os.getenv("environment")}'
else:
    DEFAULT_LOG_GROUP = 'plexus'

# Global variable to store the current CloudWatch handler
cloudwatch_handler = None

def setup_logging(log_group=DEFAULT_LOG_GROUP):
    global cloudwatch_handler
    
    # Remove existing CloudWatch handler if present
    if cloudwatch_handler:
        logging.getLogger().removeHandler(cloudwatch_handler)
    
    # Create new CloudWatch handler
    stream_name = f"plexus-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
    cloudwatch_handler = watchtower.CloudWatchLogHandler(
        log_group=log_group,
        stream_name=stream_name
    )

    # Configure logging
    logging.basicConfig(
        force=True,
        level=logging.DEBUG if os.getenv('DEBUG') else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(console=console, markup=True, rich_tracebacks=True, show_time=False, show_path=False),
            cloudwatch_handler
        ]
    )

    # Ensure that logging output goes to sys.stdout
    logging.getLogger().handlers[0].stream = sys.stdout

# Initial setup with default log group
setup_logging()

def set_log_group(new_log_group):
    """
    Change the CloudWatch log group for logging.
    
    :param new_log_group: The name of the new log group to use
    """
    environment = os.getenv("environment")
    if environment:
        new_log_group = f"{new_log_group}/{environment}"
    
    setup_logging(new_log_group)
    logging.info(f"Switched logging to group: {new_log_group}")

# Export the change_log_group function for use in other files
__all__ = ['change_log_group']