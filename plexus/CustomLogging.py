from rich.console import Console
from rich.logging import RichHandler
import logging
import os
import watchtower
import boto3
from datetime import datetime

from dotenv import load_dotenv, find_dotenv
from plexus.logging.cloudwatch_logger import _get_data_protection_policy
from plexus.logging.redaction import RedactingLogFilter
# Use an absolute path anchored to this file so the .env loads regardless of CWD.
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
# Keep explicit runtime environment variables authoritative; .env should fill gaps only.
load_dotenv(_env_file, override=False)

# Create a Rich console for logging output on stderr.
console = Console(stderr=True)

# Default log group name
if os.getenv("environment"):
    DEFAULT_LOG_GROUP_NAME = f'plexus/{os.getenv("environment")}'
else:
    DEFAULT_LOG_GROUP_NAME = 'plexus'

# Global variables to store the current CloudWatch handler and log group
cloudwatch_handler = None
root_cloudwatch_handler = None
current_log_group_name = DEFAULT_LOG_GROUP_NAME
redaction_filter = RedactingLogFilter()

def _get_aws_logging_config():
    """Return the region needed for keyless CloudWatch logging.
    
    Returns:
        tuple: (region, is_configured)
        where is_configured indicates whether CloudWatch logging can be attempted
    """
    region = os.getenv('AWS_REGION') or os.getenv('AWS_REGION_NAME') or os.getenv('AWS_DEFAULT_REGION')
    is_configured = bool(region)
    
    if os.getenv('DEBUG'):
        logging.debug("AWS CloudWatch logging config check:")
        logging.debug(f"- Region present: {bool(region)}")
    
    return region, is_configured


def _cloudwatch_logs_client(region):
    return boto3.client("logs", region_name=region)


def _prepare_cloudwatch_log_group(logs_client, log_group_name):
    try:
        logs_client.create_log_group(logGroupName=log_group_name)
    except logs_client.exceptions.ResourceAlreadyExistsException:
        pass

    logs_client.put_data_protection_policy(
        logGroupIdentifier=log_group_name,
        policyDocument=_get_data_protection_policy(),
    )


def _is_cloudwatch_policy_access_denied(exc):
    """
    Return True for expected IAM denials when applying CloudWatch data protection.

    Lambda roles in some environments can create/write log streams but cannot
    call PutDataProtectionPolicy on legacy log groups. We still fail closed for
    CloudWatch shipping, but this is an environment permission issue rather than
    an application error and should not obscure the real worker symptom.
    """
    text = str(exc)
    return (
        "PutDataProtectionPolicy" in text
        and (
            "AccessDeniedException" in text
            or "AccessDenied" in text
            or "not authorized" in text
        )
    )


def _cloudwatch_logging_enabled():
    """
    Return True when CloudWatch log shipping is enabled.

    Local/dev runs can disable watchtower delays while still using AWS creds for
    data/API access by setting PLEXUS_DISABLE_CLOUDWATCH_LOGS=1.
    """
    disable = os.getenv("PLEXUS_DISABLE_CLOUDWATCH_LOGS", "").strip().lower()
    return disable not in {"1", "true", "yes", "on"}

def _remove_handler(logger_instance, handler):
    if handler and handler in logger_instance.handlers:
        logger_instance.removeHandler(handler)
        handler.close()


def setup_logging(log_group_name=DEFAULT_LOG_GROUP_NAME, attach_root=False):
    """
    Configure Plexus logging.

    By default this only touches the 'plexus' logger hierarchy. Host
    applications that historically imported ``logging`` from this module and
    used ``logging.info(...)`` can opt in to root CloudWatch shipping with
    ``attach_root=True``.
    """
    global cloudwatch_handler, root_cloudwatch_handler, current_log_group_name

    plexus_logger = logging.getLogger("plexus")
    root_logger = logging.getLogger()

    # Remove existing CloudWatch handler if present
    _remove_handler(plexus_logger, cloudwatch_handler)
    _remove_handler(root_logger, root_cloudwatch_handler)
    cloudwatch_handler = None
    root_cloudwatch_handler = None

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
    rich_handler.addFilter(redaction_filter)

    handlers = [rich_handler]

    region, is_configured = _get_aws_logging_config()

    # CloudWatch log shipping fails closed unless app-side redaction and
    # CloudWatch data protection are both active.
    if is_configured and _cloudwatch_logging_enabled():
        try:
            logs_client = _cloudwatch_logs_client(region)
            _prepare_cloudwatch_log_group(logs_client, log_group_name)
            log_stream_name = f"plexus-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group_name=log_group_name,
                log_stream_name=log_stream_name,
                boto3_client=logs_client,
            )
            cloudwatch_handler.setFormatter(PlexusFormatter())
            cloudwatch_handler.addFilter(redaction_filter)
            handlers.append(cloudwatch_handler)

            if attach_root:
                root_cloudwatch_handler = watchtower.CloudWatchLogHandler(
                    log_group_name=log_group_name,
                    log_stream_name=f"{log_stream_name}-root",
                    boto3_client=logs_client,
                )
                root_cloudwatch_handler.setFormatter(PlexusFormatter())
                root_cloudwatch_handler.addFilter(redaction_filter)

            current_log_group_name = log_group_name
        except Exception as e:
            if _is_cloudwatch_policy_access_denied(e):
                plexus_logger.warning(
                    "CloudWatch logging disabled for %s: missing logs:PutDataProtectionPolicy permission",
                    log_group_name,
                )
            else:
                plexus_logger.error(f"Error creating CloudWatch handler: {str(e)}")
            cloudwatch_handler = None
            root_cloudwatch_handler = None
            current_log_group_name = None
    else:
        cloudwatch_handler = None
        root_cloudwatch_handler = None
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

    if root_cloudwatch_handler:
        root_logger.addHandler(root_cloudwatch_handler)
        if root_logger.level > log_level:
            root_logger.setLevel(log_level)

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

def set_log_group(new_log_group_name, attach_root=False):
    """
    Change the CloudWatch log group for logging.
    
    :param new_log_group_name: The name of the new log group to use
    :param attach_root: Attach the redacting CloudWatch handler to the root
        logger for host apps that log via the stdlib logging module.
    """
    # Skip if CloudWatch logging is not configured
    _, is_configured = _get_aws_logging_config()
    if not is_configured:
        logging.debug(f"CloudWatch logging not configured, skipping group change: {new_log_group_name}")
        return
    
    global current_log_group_name
    environment = os.getenv("environment")
    if environment:
        new_log_group_name = f"{new_log_group_name}/{environment}"

    root_logger = logging.getLogger()
    root_attached = bool(root_cloudwatch_handler and root_cloudwatch_handler in root_logger.handlers)

    # Avoid expensive handler rebuild when already using this log group.
    if new_log_group_name == current_log_group_name and root_attached == bool(attach_root):
        logging.debug(f"Log group already active, skipping reconfiguration: {new_log_group_name}")
        return
    
    setup_logging(new_log_group_name, attach_root=attach_root)
    current_log_group_name = new_log_group_name
    logging.debug(f"Switched logging to group: {new_log_group_name}")

def add_log_stream(log_stream_name):
    """
    Add a new log stream to the current log group.
    
    :param log_stream_name: The name of the new log stream
    """
    global cloudwatch_handler, current_log_group_name
    
    # Skip if CloudWatch logging is not configured
    region, is_configured = _get_aws_logging_config()
    if not is_configured or not current_log_group_name:
        logging.debug(f"CloudWatch logging not configured, skipping stream: {log_stream_name}")
        return None

    try:
        logs_client = _cloudwatch_logs_client(region)
        _prepare_cloudwatch_log_group(logs_client, current_log_group_name)
        new_handler = watchtower.CloudWatchLogHandler(
            log_group_name=current_log_group_name,
            log_stream_name=f"plexus-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}-{log_stream_name}",
            use_queues=False,
            boto3_client=logs_client,
        )
        new_handler.addFilter(redaction_filter)
    except Exception as e:
        logging.error(f"Error creating CloudWatch stream handler: {str(e)}")
        return None
    
    # Add the new handler to the plexus logger
    plexus_logger = logging.getLogger("plexus")
    plexus_logger.addHandler(new_handler)
    
    # Log the addition of the new stream
    logging.debug(f"Added new log stream: {log_stream_name}")
    
    return new_handler

# Export the necessary functions and objects
__all__ = ['logging', 'logger', 'set_log_group', 'add_log_stream', 'console']
