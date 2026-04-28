"""
Utility functions for creating and managing Plexus API clients.

This module provides centralized client creation functionality to avoid circular imports.
"""

import logging
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.client import ClientContext
import os
from plexus.config.loader import load_config

logger = logging.getLogger(__name__)

def create_client() -> PlexusDashboardClient:
    """Create a dashboard client with explicit API endpoint and key selection."""
    # Load Plexus configuration from .plexus/config.yaml
    # This will set all required environment variables
    load_config()
    
    # Read account key from environment (now populated by load_config)
    account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
    if not account_key:
        # Optionally raise an error or log a warning if key is expected
        logger.warning("PLEXUS_ACCOUNT_KEY environment variable not set.")
        
    # Dashboard-oriented tooling should prefer the frontend API credentials when present.
    # This keeps CLI/MCP behavior aligned with the web app's active AppSync endpoint.
    api_url = (
        os.getenv('NEXT_PUBLIC_PLEXUS_API_URL')
        or os.getenv('PLEXUS_API_URL')
    )
    api_key = (
        os.getenv('NEXT_PUBLIC_PLEXUS_API_KEY')
        or os.getenv('PLEXUS_API_KEY')
    )

    # Create context with the key
    context = ClientContext(account_key=account_key)
    
    # Pass context to the client constructor
    client = PlexusDashboardClient(api_url=api_url, api_key=api_key, context=context)
    logger.debug(f"Using API URL: {client.api_url}")
    logger.debug(f"Client Context Account Key: {client.context.account_key}")
    return client 
