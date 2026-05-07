import os
import sys

# Allow running this file directly from the repository checkout.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

from plexus.console.local_worker import main  # noqa: E402


if __name__ == "__main__":
    main()
