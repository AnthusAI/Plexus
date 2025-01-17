from rich.console import Console
from rich.logging import RichHandler
import logging
import sys
import os
import watchtower
from datetime import datetime
import time

from dotenv import load_dotenv
load_dotenv('.env', override=True)

# Create a Rich console specifically for output
console = Console()

# Default log group name
if os.getenv("environment"):
    DEFAULT_LOG_GROUP = f'plexus/{os.getenv("environment")}'
else:
    DEFAULT_LOG_GROUP = 'plexus'

# Global variables to store the current CloudWatch handler and log group
cloudwatch_handler = None
current_log_group = DEFAULT_LOG_GROUP

def setup_logging(log_group=DEFAULT_LOG_GROUP):
    global cloudwatch_handler, current_log_group
    
    # Remove existing CloudWatch handler if present
    if cloudwatch_handler:
        logging.getLogger().removeHandler(cloudwatch_handler)
    
    handlers = [
        RichHandler(console=console, markup=True, rich_tracebacks=True, 
                   show_time=False, show_path=False)
    ]

    # Only add CloudWatch handler if AWS credentials are available
    if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY') \
            and os.getenv('AWS_REGION_NAME'):
        stream_name = f"plexus-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
        cloudwatch_handler = watchtower.CloudWatchLogHandler(
            log_group=log_group,
            stream_name=stream_name
        )
        handlers.append(cloudwatch_handler)
        current_log_group = log_group
    else:
        cloudwatch_handler = None
        current_log_group = None

    # Configure logging
    logging.basicConfig(
        force=True,
        level=logging.DEBUG if os.getenv('DEBUG') else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers
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
    # Skip if CloudWatch logging is not configured
    if not os.getenv('AWS_ACCESS_KEY_ID') or not os.getenv('AWS_SECRET_ACCESS_KEY') \
            or not os.getenv('AWS_DEFAULT_REGION'):
        logging.debug(f"CloudWatch logging not configured, skipping group change: {new_log_group}")
        return
    
    global current_log_group
    environment = os.getenv("environment")
    if environment:
        new_log_group = f"{new_log_group}/{environment}"
    
    setup_logging(new_log_group)
    current_log_group = new_log_group
    logging.info(f"Switched logging to group: {new_log_group}")

def add_log_stream(stream_name):
    """
    Add a new log stream to the current log group.
    
    :param stream_name: The name of the new log stream
    """
    global cloudwatch_handler, current_log_group
    
    # Skip if CloudWatch logging is not configured
    if not current_log_group:
        logging.debug(f"CloudWatch logging not configured, skipping stream: {stream_name}")
        return None
    
    # Create a new handler for the specific stream
    new_handler = watchtower.CloudWatchLogHandler(
        log_group=current_log_group,
        stream_name=f"plexus-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}-{stream_name}",
        use_queues=False  # To ensure immediate logging for the specific stream
    )
    
    # Add the new handler to the root logger
    logger = logging.getLogger()
    logger.addHandler(new_handler)
    
    # Log the addition of the new stream
    logging.info(f"Added new log stream: {stream_name}")
    
    return new_handler  # Return the handler in case it's needed

# Export the necessary functions and objects
__all__ = ['logging', 'set_log_group', 'add_log_stream', 'console']