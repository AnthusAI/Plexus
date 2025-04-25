"""
Utility functions for creating and managing Plexus API clients.

This module provides centralized client creation functionality to avoid circular imports.
"""

import logging
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.client import ClientContext
import os

logger = logging.getLogger(__name__)

def create_client() -> PlexusDashboardClient:
    """Create a client, read env vars, and log config"""
    # Read account key from environment
    account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
    if not account_key:
        # Optionally raise an error or log a warning if key is expected
        logger.warning("PLEXUS_ACCOUNT_KEY environment variable not set.")
        
    # Create context with the key
    context = ClientContext(account_key=account_key)
    
    # Pass context to the client constructor
    client = PlexusDashboardClient(context=context)
    logger.debug(f"Using API URL: {client.api_url}")
    logger.debug(f"Client Context Account Key: {client.context.account_key}")
    return client 