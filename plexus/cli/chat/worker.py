"""Console chat worker command helpers."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

import click
from dotenv import load_dotenv

from plexus.console.chat_runtime import (
    build_response_owner,
    normalize_response_target,
    process_pending_local_messages,
)
from plexus.dashboard.api.client import PlexusDashboardClient

logger = logging.getLogger(__name__)


def load_chat_worker_env(repo_root: Optional[Path] = None) -> None:
    """Load local dashboard/chat env files in the same order as the web app."""
    root = repo_root or Path(__file__).resolve().parents[3]
    dashboard_dir = root / "dashboard"
    for env_file, override in (
        (root / ".env", False),
        (dashboard_dir / ".env", True),
        (dashboard_dir / ".env.local", True),
    ):
        if env_file.exists():
            load_dotenv(env_file, override=override)


def resolve_chat_worker_target(explicit_target: Optional[str] = None) -> str:
    target = normalize_response_target(
        explicit_target
        or os.getenv("CONSOLE_RESPONSE_TARGET")
        or os.getenv("NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET")
    )
    if target == "cloud" or not target.startswith("local:"):
        raise click.ClickException(
            "Chat worker requires a local response target. Pass --target local:<name> "
            "and set NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET to the same value for the dashboard."
        )
    return target


def create_chat_worker_client() -> PlexusDashboardClient:
    api_url = str(os.getenv("PLEXUS_API_URL") or os.getenv("NEXT_PUBLIC_PLEXUS_API_URL") or "").strip()
    api_key = str(os.getenv("PLEXUS_API_KEY") or os.getenv("NEXT_PUBLIC_PLEXUS_API_KEY") or "").strip()
    if not api_url or not api_key:
        raise click.ClickException("PLEXUS_API_URL and PLEXUS_API_KEY are required.")
    return PlexusDashboardClient(api_url=api_url, api_key=api_key)


def run_chat_worker(
    *,
    target: Optional[str] = None,
    poll_interval: float = 0.2,
    limit: int = 5,
    once: bool = False,
    client_factory: Callable[[], PlexusDashboardClient] = create_chat_worker_client,
    load_env: bool = True,
) -> None:
    if load_env:
        load_chat_worker_env()
    if poll_interval <= 0:
        raise click.ClickException("--poll-interval must be greater than zero.")
    if limit <= 0:
        raise click.ClickException("--limit must be greater than zero.")

    response_target = resolve_chat_worker_target(target)
    owner = build_response_owner(response_target)
    client = client_factory()

    logger.info("Chat worker started | target=%s owner=%s", response_target, owner)
    while True:
        try:
            processed = process_pending_local_messages(
                client,
                response_target=response_target,
                owner=owner,
                limit=limit,
            )
            if processed:
                logger.info("Processed %s pending Console chat message(s)", processed)
            if once:
                return
            if processed:
                continue
        except Exception:
            logger.exception("Chat worker poll failed")
            if once:
                raise
        time.sleep(poll_interval)
