"""
CloudWatch Logs integration for procedure runs.

This module provides procedure-specific wrappers around PlexusCloudWatchLogger.
"""

import logging
from typing import Optional

from plexus.logging.cloudwatch_logger import PlexusCloudWatchLogger

logger = logging.getLogger(__name__)


def _create_procedure_cloudwatch_logger(
    account_key: str,
    procedure_id: str,
    invocation_run_id: str,
) -> Optional[PlexusCloudWatchLogger]:
    """
    Create and open a CloudWatch logger for procedure execution.

    Args:
        account_key: Account identifier for log group segmentation
        procedure_id: Procedure identifier
        invocation_run_id: Unique run identifier

    Returns:
        Opened PlexusCloudWatchLogger instance, or None if initialization failed
    """
    try:
        cw = PlexusCloudWatchLogger(
            account_key=account_key,
            component_name=procedure_id,
            invocation_id=invocation_run_id,
            log_category="procedures",
        )
        cw.open()
        return cw
    except Exception as exc:
        logger.debug("Could not create PlexusCloudWatchLogger: %s", exc)
        return None
