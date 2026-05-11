from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from plexus.console.chat_runtime import (
    build_response_owner,
    normalize_response_target,
    process_pending_local_messages,
)
from plexus.dashboard.api.client import PlexusDashboardClient

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_local_env() -> None:
    repo_root = _repo_root()
    dashboard_dir = repo_root / "dashboard"
    env_load_order = (
        (repo_root / ".env", False),
        (dashboard_dir / ".env", True),
        (dashboard_dir / ".env.local", True),
    )
    for env_file, override in env_load_order:
        if env_file.exists():
            load_dotenv(env_file, override=override)


def _resolve_client() -> PlexusDashboardClient:
    _load_local_env()
    api_url = str(
        os.getenv("PLEXUS_API_URL") or os.getenv("NEXT_PUBLIC_PLEXUS_API_URL") or ""
    ).strip()
    api_key = str(
        os.getenv("PLEXUS_API_KEY") or os.getenv("NEXT_PUBLIC_PLEXUS_API_KEY") or ""
    ).strip()
    if not api_url or not api_key:
        raise RuntimeError("PLEXUS_API_URL and PLEXUS_API_KEY are required")
    return PlexusDashboardClient(api_url=api_url, api_key=api_key)


def _default_local_response_target() -> str:
    developer = (
        os.getenv("USER")
        or os.getenv("LOGNAME")
        or os.getenv("USERNAME")
        or "developer"
    )
    return f"local:{developer}"


def _resolve_response_target(explicit_target: Optional[str]) -> str:
    target = normalize_response_target(
        explicit_target
        or os.getenv("CONSOLE_RESPONSE_TARGET")
        or os.getenv("NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET")
        or _default_local_response_target()
    )
    if target == "cloud":
        raise RuntimeError("Local worker requires CONSOLE_RESPONSE_TARGET to be local:<developer>")
    return target


def _resolve_poll_interval_seconds(explicit_interval: Optional[float]) -> float:
    if explicit_interval is not None:
        return explicit_interval
    value = (
        os.getenv("CONSOLE_LOCAL_WORKER_IDLE_POLL_SECONDS")
        or os.getenv("CONSOLE_LOCAL_WORKER_POLL_SECONDS")
        or "0.2"
    )
    try:
        interval = float(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid CONSOLE_LOCAL_WORKER_IDLE_POLL_SECONDS={value!r}"
        ) from exc
    if interval < 0:
        raise RuntimeError("CONSOLE_LOCAL_WORKER_IDLE_POLL_SECONDS must be non-negative")
    return interval


def main(
    *,
    response_target: Optional[str] = None,
    poll_interval_seconds: Optional[float] = None,
    limit: int = 5,
    once: bool = False,
) -> None:
    _load_local_env()
    resolved_target = _resolve_response_target(response_target)
    owner = build_response_owner(resolved_target)
    idle_poll_interval_seconds = _resolve_poll_interval_seconds(poll_interval_seconds)
    client = _resolve_client()

    logger.info(
        "Local Console chat worker started (target=%s owner=%s)",
        resolved_target,
        owner,
    )
    while True:
        try:
            processed = process_pending_local_messages(
                client,
                response_target=resolved_target,
                owner=owner,
                limit=limit,
            )
            if processed:
                logger.info("Processed %s pending Console chat message(s)", processed)
                if once:
                    return
                continue
        except Exception:
            logger.exception("Local Console chat worker poll failed")
            if once:
                raise

        if once:
            return
        time.sleep(idle_poll_interval_seconds)
