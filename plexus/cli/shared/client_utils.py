"""
Utility functions for creating and managing Plexus API clients.

This module provides centralized client creation functionality to avoid circular imports.
"""

import logging
import json
from pathlib import Path
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.client import ClientContext
import os
from plexus.config.loader import load_config
from plexus.attribution.actor_context import resolve_actor_context

logger = logging.getLogger(__name__)


def _amplify_output_paths():
    repository_root = Path(__file__).resolve().parents[3]
    return (
        repository_root / "dashboard" / "amplify_outputs.json",
        repository_root / "amplify_outputs.json",
    )


def _resolve_api_url() -> str | None:
    configured = os.getenv("PLEXUS_API_URL") or os.getenv("NEXT_PUBLIC_PLEXUS_API_URL")
    if configured:
        return configured

    for path in _amplify_output_paths():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        discovered = payload.get("data", {}).get("url")
        if discovered:
            return str(discovered)
    return None


def _resolve_auth_mode() -> str:
    """Choose an explicit auth mode without silently falling back to API keys."""
    configured = os.getenv("PLEXUS_GRAPHQL_AUTH_MODE")
    if configured:
        return configured.strip().lower()
    if any(os.getenv(name) for name in (
        "AWS_LAMBDA_FUNCTION_NAME",
        "LAMBDA_TASK_ROOT",
        "ECS_CONTAINER_METADATA_URI",
        "ECS_CONTAINER_METADATA_URI_V4",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    )) or (os.getenv("AWS_EXECUTION_ENV") or "").startswith("AWS_ECS"):
        return "iam"
    return "cognito"


def create_client() -> PlexusDashboardClient:
    """Create a dashboard client with an explicit local or workload auth mode."""
    # Load Plexus configuration from .plexus/config.yaml
    # This will set all required environment variables
    load_config()
    
    # Read account key from environment (now populated by load_config)
    account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
    account_id = os.getenv('PLEXUS_ACCOUNT_ID')
    if not account_key:
        # Optionally raise an error or log a warning if key is expected
        logger.warning("PLEXUS_ACCOUNT_KEY environment variable not set.")
        
    # Dispatch-critical CLI/MCP flows must honor the explicit runtime endpoint first.
    # NEXT_PUBLIC values are frontend defaults and may point at a different checkout/env.
    api_url = _resolve_api_url()
    auth_mode = _resolve_auth_mode()
    api_key = (
        os.getenv('PLEXUS_API_KEY') or os.getenv('NEXT_PUBLIC_PLEXUS_API_KEY')
    ) if auth_mode == "api_key" else None

    actor = resolve_actor_context(explicit_source="cli")
    context = ClientContext(
        account_key=account_key,
        account_id=account_id,
        actor_user_id=actor.user_id,
        actor_type=actor.actor_type,
        actor_key=actor.actor_key,
        actor_source=actor.actor_source,
    )
    
    # Pass context to the client constructor
    client = PlexusDashboardClient(api_url=api_url, api_key=api_key, context=context, auth_mode=auth_mode)
    logger.debug(f"Using API URL: {client.api_url}")
    logger.debug(f"Client Context Account Key: {client.context.account_key}")
    return client 
