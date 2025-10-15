#!/usr/bin/env python3
"""
Simplified test script for loading a scorecard from the API.
"""

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def test_load_scorecard_from_api():
    """Test the load_scorecard_from_api function with a known scorecard."""
    from plexus.cli.evaluation.evaluations import load_scorecard_from_api
    
    # Use a known scorecard from the dashboard
    scorecard_key = "cs3dealsaver"
    score_name = "Good Call"
    
    logging.info(f"Testing loading scorecard with key: {scorecard_key}")
    
    try:
        start_time = time.time()
        scorecard_instance = load_scorecard_from_api(scorecard_key, score_name)
        elapsed_time = time.time() - start_time
        
        logging.info(f"Successfully loaded scorecard: {scorecard_instance.properties.get('name')}")
        logging.info(f"Time taken: {elapsed_time:.2f} seconds")
        
        # Verify the score exists
        score_found = False
        for score in scorecard_instance.scores:
            if score.get('name') == score_name:
                score_found = True
                logging.info(f"Found score: {score_name}")
                logging.info(f"Score properties: {score}")
                break
                
        if not score_found:
            logging.error(f"Score '{score_name}' not found in loaded scorecard")
            return False
            
        logging.info("Testing loading the same scorecard again (should use cache)")
        start_time = time.time()
        scorecard_instance2 = load_scorecard_from_api(scorecard_key, score_name)
        elapsed_time2 = time.time() - start_time
        
        logging.info(f"Second load time: {elapsed_time2:.2f} seconds")
        logging.info(f"Caching improvement: {100 * (elapsed_time - elapsed_time2) / elapsed_time:.2f}%")
        
        return True
        
    except Exception as e:
        logging.error(f"Error loading scorecard: {str(e)}")
        logging.exception("Exception details:")
        return False

def main():
    """Run the test."""
    logging.info("Starting scorecard API loading test")
    
    success = test_load_scorecard_from_api()
    
    if success:
        logging.info("Test completed successfully!")
        return 0
    else:
        logging.error("Test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 