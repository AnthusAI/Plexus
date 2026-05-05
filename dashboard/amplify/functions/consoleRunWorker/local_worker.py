"""Compatibility wrapper for the local Console chat worker.

Prefer:
    plexus chat worker --target local:<developer>
"""

import os
import sys
import logging

# Allow running this file directly from the repository checkout.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

from plexus.cli.chat.worker import run_chat_worker  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_chat_worker()


if __name__ == "__main__":
    main()
