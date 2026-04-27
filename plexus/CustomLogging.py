from rich.console import Console
from rich.logging import RichHandler
import logging
import sys
import os
import watchtower
import boto3
from datetime import datetime
import time

from dotenv import load_dotenv, find_dotenv
# Use an absolute path anchored to this file so the .env loads regardless of CWD.
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(_env_file, override=True)

# Create a Rich console for logging output on stderr.
console = Console(stderr=True)

# Default log group name
if os.getenv("environment"):
    DEFAULT_LOG_GROUP_NAME = f'plexus/{os.getenv("environment")}'
else:
    DEFAULT_LOG_GROUP_NAME = 'plexus'

# Global variables to store the current CloudWatch handler and log group
cloudwatch_handler = None
current_log_group_name = DEFAULT_LOG_GROUP_NAME

def _get_aws_credentials():
    """Helper function to check and return AWS credentials.
    
    Returns:
        tuple: (access_key, secret_key, region, is_configured)
        where is_configured is a boolean indicating if all credentials are present
    """
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_REGION') or os.getenv('AWS_REGION_NAME') or os.getenv('AWS_DEFAULT_REGION')
    
    is_configured = all([access_key, secret_key, region])
    
    if os.getenv('DEBUG'):
        logging.debug("AWS Credentials Check:")
        logging.debug(f"- Access Key present: {bool(access_key)}")
        logging.debug(f"- Secret Key present: {bool(secret_key)}")
        logging.debug(f"- Region present: {bool(region)}")
    
    return access_key, secret_key, region, is_configured


def _cloudwatch_logging_enabled():
    """
    Return True when CloudWatch log shipping is enabled.

    Local/dev runs can disable watchtower delays while still using AWS creds for
    data/API access by setting PLEXUS_DISABLE_CLOUDWATCH_LOGS=1.
    """
    disable = os.getenv("PLEXUS_DISABLE_CLOUDWATCH_LOGS", "").strip().lower()
    return disable not in {"1", "true", "yes", "on"}

def setup_logging(log_group_name=DEFAULT_LOG_GROUP_NAME):
    """
    Configure the 'plexus' named logger (NOT the root logger).

    This is safe to call at import time because it only touches the 'plexus'
    logger hierarchy, leaving the root logger — and any host application's
    logging setup (e.g. Tactus CLI) — completely untouched.
    """
    global cloudwatch_handler, current_log_group_name

    plexus_logger = logging.getLogger("plexus")

    # Remove existing CloudWatch handler if present
    if cloudwatch_handler:
        plexus_logger.removeHandler(cloudwatch_handler)

    # Create custom formatter
    class PlexusFormatter(logging.Formatter):
        def format(self, record):
            record.asctime = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
            record.log_group_name = current_log_group_name if current_log_group_name else 'plexus'
            formatted = super().format(record)
            return formatted

    # Configure Rich handler with custom settings
    rich_handler = RichHandler(
        console=console,
        markup=True,
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
        show_level=False,
        log_time_format='[%X]'
    )
    rich_handler.setFormatter(PlexusFormatter('%(asctime)s [%(log_group_name)s] [%(levelname)s] %(message)s'))

    handlers = [rich_handler]

    # Check AWS credentials
    _, _, region, is_configured = _get_aws_credentials()

    # Only add CloudWatch handler if AWS credentials are available and log
    # shipping is explicitly enabled.
    if is_configured and _cloudwatch_logging_enabled():
        try:
            log_stream_name = f"plexus-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group_name=log_group_name,
                log_stream_name=log_stream_name
            )
            cloudwatch_handler.setFormatter(PlexusFormatter())
            handlers.append(cloudwatch_handler)
            current_log_group_name = log_group_name
        except Exception as e:
            plexus_logger.error(f"Error creating CloudWatch handler: {str(e)}")
            cloudwatch_handler = None
            current_log_group_name = None
    else:
        cloudwatch_handler = None
        current_log_group_name = None

    # Remove any existing handlers from plexus logger
    for handler in plexus_logger.handlers[:]:
        plexus_logger.removeHandler(handler)

    # Set level based on environment
    log_level = logging.DEBUG if os.getenv('DEBUG') else logging.INFO
    plexus_logger.setLevel(log_level)

    # Don't propagate to root logger — plexus handles its own output
    plexus_logger.propagate = False

    # Add our handlers
    for handler in handlers:
        plexus_logger.addHandler(handler)

    # Quiet noisy libraries under the plexus namespace
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('gql.transport').setLevel(logging.WARNING)
    logging.getLogger('gql.dsl').setLevel(logging.WARNING)

# Initial setup with default log group — safe because it only touches 'plexus' logger
setup_logging()

# Pre-built plexus logger for consumers.  Usage:
#   from plexus.CustomLogging import logger
#   logger.info("something happened")
logger = logging.getLogger("plexus")

def set_log_group(new_log_group_name):
    """
    Change the CloudWatch log group for logging.
    
    :param new_log_group_name: The name of the new log group to use
    """
    # Skip if CloudWatch logging is not configured
    _, _, _, is_configured = _get_aws_credentials()
    if not is_configured:
        logging.debug(f"CloudWatch logging not configured, skipping group change: {new_log_group_name}")
        return
    
    global current_log_group_name
    environment = os.getenv("environment")
    if environment:
        new_log_group_name = f"{new_log_group_name}/{environment}"

    # Avoid expensive handler rebuild when already using this log group.
    if new_log_group_name == current_log_group_name:
        logging.debug(f"Log group already active, skipping reconfiguration: {new_log_group_name}")
        return
    
    setup_logging(new_log_group_name)
    current_log_group_name = new_log_group_name
    logging.debug(f"Switched logging to group: {new_log_group_name}")

def add_log_stream(log_stream_name):
    """
    Add a new log stream to the current log group.
    
    :param log_stream_name: The name of the new log stream
    """
    global cloudwatch_handler, current_log_group_name
    
    # Skip if CloudWatch logging is not configured
    _, _, _, is_configured = _get_aws_credentials()
    if not is_configured or not current_log_group_name:
        logging.debug(f"CloudWatch logging not configured, skipping stream: {log_stream_name}")
        return None
    
    # Create a new handler for the specific stream
    new_handler = watchtower.CloudWatchLogHandler(
        log_group_name=current_log_group_name,
        log_stream_name=f"plexus-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}-{log_stream_name}",
        use_queues=False  # To ensure immediate logging for the specific stream
    )
    
    # Add the new handler to the plexus logger
    plexus_logger = logging.getLogger("plexus")
    plexus_logger.addHandler(new_handler)
    
    # Log the addition of the new stream
    logging.debug(f"Added new log stream: {log_stream_name}")
    
    return new_handler

# Export the necessary functions and objects
__all__ = ['logging', 'logger', 'set_log_group', 'add_log_stream', 'console']
