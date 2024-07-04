from rich.console import Console
from rich.logging import RichHandler
import logging
import sys
import os

# Create a Rich console specifically for output
console = Console()

# Configure logging to use RichHandler with explicit settings for Jupyter
logging.basicConfig(
    force = True,
    level=logging.DEBUG if os.getenv('DEBUG') else logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, markup=True, rich_tracebacks=True, show_time=False, show_path=False)]
)

# Ensure that logging output goes to sys.stdout
logging.getLogger().handlers[0].stream = sys.stdout