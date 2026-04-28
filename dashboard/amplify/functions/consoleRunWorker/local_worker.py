"""
Local development worker for Console chat responses.

Usage:
    CONSOLE_RESPONSE_TARGET=local:ryan python local_worker.py

The dashboard writes user ChatMessage rows with responseTarget set from
NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET. This worker claims only matching pending
messages and runs the same hard-coded Tactus Console harness used by the cloud
stream Lambda.
"""

import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Allow running this file directly from the repository checkout.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

from plexus.console.chat_runtime import (  # noqa: E402
    build_response_owner,
    normalize_response_target,
    process_pending_local_messages,
)
from plexus.dashboard.api.client import PlexusDashboardClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _load_local_env() -> None:
    worker_path = Path(__file__).resolve()
    repo_root = worker_path.parents[4]
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
    api_url = str(os.getenv("PLEXUS_API_URL") or os.getenv("NEXT_PUBLIC_PLEXUS_API_URL") or "").strip()
    api_key = str(os.getenv("PLEXUS_API_KEY") or os.getenv("NEXT_PUBLIC_PLEXUS_API_KEY") or "").strip()
    if not api_url or not api_key:
        raise RuntimeError("PLEXUS_API_URL and PLEXUS_API_KEY are required")
    return PlexusDashboardClient(api_url=api_url, api_key=api_key)


def main() -> None:
    _load_local_env()
    response_target = normalize_response_target(
        os.getenv("CONSOLE_RESPONSE_TARGET") or os.getenv("NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET")
    )
    if response_target == "cloud":
        raise RuntimeError("Local worker requires CONSOLE_RESPONSE_TARGET to be local:<developer>")

    owner = build_response_owner(response_target)
    poll_interval_seconds = float(os.getenv("CONSOLE_LOCAL_WORKER_POLL_SECONDS", "1.0"))
    client = _resolve_client()

    logger.info("Local Console chat worker started (target=%s owner=%s)", response_target, owner)
    while True:
        try:
            processed = process_pending_local_messages(
                client,
                response_target=response_target,
                owner=owner,
                limit=5,
            )
            if processed:
                logger.info("Processed %s pending Console chat message(s)", processed)
        except Exception:
            logger.exception("Local Console chat worker poll failed")
        time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    main()
