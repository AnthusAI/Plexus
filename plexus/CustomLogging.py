"""Redacted package logging for Plexus.

Plexus configures only its own logger. Applications own log destinations,
including CloudWatch resources, IAM permissions, retention, and metrics.
"""

import logging
import os

from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

from plexus.logging.redaction import RedactingLogFilter


# Use an absolute path anchored to this file so the .env loads regardless of CWD.
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
# Keep explicit runtime environment variables authoritative; .env should fill gaps only.
load_dotenv(_env_file, override=False)

console = Console(stderr=True)
redaction_filter = RedactingLogFilter()


def setup_logging() -> None:
    """Configure redacted Rich logging for the ``plexus`` logger hierarchy only."""
    plexus_logger = logging.getLogger("plexus")

    for handler in plexus_logger.handlers[:]:
        plexus_logger.removeHandler(handler)
        handler.close()

    rich_handler = RichHandler(
        console=console,
        markup=True,
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
        show_level=False,
        log_time_format="[%X]",
    )
    rich_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    rich_handler.addFilter(redaction_filter)

    plexus_logger.setLevel(logging.DEBUG if os.getenv("DEBUG") else logging.INFO)
    plexus_logger.propagate = False
    plexus_logger.addHandler(rich_handler)

    for noisy_logger in ("urllib3", "botocore", "boto3", "gql.transport", "gql.dsl"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


setup_logging()

# Pre-built Plexus logger for consumers.
logger = logging.getLogger("plexus")

__all__ = ["logging", "logger", "setup_logging", "console"]
