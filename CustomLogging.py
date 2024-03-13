import logging
import sys

# Configure logging to output to stdout and set the minimum severity to INFO
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)

# Create a logger object that you can use across your application
# logging = logging.getLogger(__name__)
logging = logging.getLogger()