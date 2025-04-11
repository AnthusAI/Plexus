"""
Test script to inspect sample transcript data.
"""

import logging
import sys
from pathlib import Path
from plexus.cli.bertopic.transformer import transform_transcripts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    # Test file path
    test_file = Path.home() / "projects" / "Call-Criteria-Python" / ".plexus_training_data_cache" / "dataframes" / "1039_no_score_id_Start-Date_csv.parquet"
    
    if not test_file.exists():
        logging.error(f"Test file not found: {test_file}")
        sys.exit(1)
    
    logging.info(f"Testing with file: {test_file}")
    
    # Transform transcripts with inspection enabled
    try:
        transform_transcripts(
            str(test_file),
            content_column='text',
            fresh=True,
            inspect=True
        )
    except Exception as e:
        logging.error(f"Error during transformation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 