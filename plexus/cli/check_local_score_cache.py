"""Functions to check for locally cached score configurations."""

import logging
from pathlib import Path
from typing import Dict, List, Any, Set, Optional

from plexus.cli.shared import get_score_yaml_path

def check_local_score_cache(scorecard_data: Dict[str, Any], target_scores: List[Dict[str, Any]]) -> Dict[str, bool]:
    """Check if configurations for target scores are already cached locally.
    
    This function checks if the score configurations exist in the local filesystem
    following the convention used by `get_score_yaml_path`:
    ./scorecards/[scorecard_name]/[score_name].yaml
    
    Args:
        scorecard_data: The scorecard data from the API containing at least 'name'
        target_scores: List of score objects to check, each containing at least 'name' and 'id'
        
    Returns:
        Dictionary mapping score IDs to boolean values indicating if they are cached
    """
    scorecard_name = scorecard_data.get('name')
    if not scorecard_name:
        logging.error("Cannot check local cache: No scorecard name provided")
        return {}
        
    logging.info(f"Checking local cache for {len(target_scores)} scores in scorecard: {scorecard_name}")
    
    cache_status = {}
    
    for score in target_scores:
        score_id = score.get('id')
        score_name = score.get('name')
        
        if not score_id or not score_name:
            logging.warning(f"Skipping score with missing ID or name: {score}")
            continue
            
        # Get the expected local file path
        yaml_path = get_score_yaml_path(scorecard_name, score_name)
        
        # Check if the file exists
        is_cached = yaml_path.exists()
        cache_status[score_id] = is_cached
        
        log_level = logging.INFO if is_cached else logging.DEBUG
        logging.log(log_level, f"Score '{score_name}' (ID: {score_id}): {'CACHED' if is_cached else 'NOT cached'}")
    
    # Summary statistics
    cached_count = sum(1 for is_cached in cache_status.values() if is_cached)
    total_count = len(cache_status)
    
    if total_count > 0:
        cache_percentage = (cached_count / total_count) * 100
        logging.info(f"Cache status: {cached_count}/{total_count} scores cached ({cache_percentage:.1f}%)")
    else:
        logging.info("No scores to check for caching.")
    
    return cache_status 