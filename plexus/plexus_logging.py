from rich.console import Console
from rich.logging import RichHandler
import logging
import sys

# Import the centralized logging configuration
from plexus.CustomLogging import setup_logging, console

# The logging configuration is now handled by CustomLogging.py
# This file is kept for backward compatibility and to provide the console object

# Create a Rich console specifically for output
console = Console()

# Configure logging to use RichHandler with explicit settings for Jupyter
logging.basicConfig(
    force = True,
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, markup=True, rich_tracebacks=True, show_time=False, show_path=False)]
)

# Ensure that logging output goes to sys.stdout
logging.getLogger().handlers[0].stream = sys.stdout