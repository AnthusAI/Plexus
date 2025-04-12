"""Functions to check for locally cached score configurations."""

import logging
from pathlib import Path
from typing import Dict, List, Any, Set, Optional

from plexus.cli.shared import get_score_yaml_path

def check_local_score_cache(score_configs, scorecard_name):
    """
    Check which score configurations are already cached locally.
    
    Args:
        score_configs (dict): A dictionary of score IDs to their configurations
        scorecard_name (str): The name of the scorecard
        
    Returns:
        tuple: (list of cached score IDs, list of uncached score IDs)
    """
    cached_ids = []
    uncached_ids = []
    
    for score_id, config in score_configs.items():
        if not config:
            logging.warning(f"Empty configuration for score {score_id}")
            uncached_ids.append(score_id)
            continue
            
        score_name = None
        if isinstance(config, str):
            # Parse the YAML string to get the score name
            try:
                from ruamel.yaml import YAML
                yaml_parser = YAML(typ='safe')
                parsed_config = yaml_parser.load(config)
                score_name = parsed_config.get('name')
            except Exception as e:
                logging.warning(f"Could not parse YAML for score {score_id}: {str(e)}")
        else:
            # Assume it's already a dictionary
            score_name = config.get('name')
            
        if not score_name:
            logging.warning(f"Could not determine score name for {score_id}")
            uncached_ids.append(score_id)
            continue
            
        # Get the expected cache path
        cache_path = get_score_yaml_path(scorecard_name, score_name)
        
        # Check if the file exists and is non-empty
        if cache_path.exists() and cache_path.stat().st_size > 0:
            cached_ids.append(score_id)
            logging.info(f"Loading score configuration from cache: {score_name} ({score_id})")
        else:
            uncached_ids.append(score_id)
            logging.info(f"Fetching score configuration from API: {score_name} ({score_id})")
    
    # Log a summary of the cache check
    total = len(score_configs)
    cached = len(cached_ids)
    cache_percentage = (cached / total * 100) if total > 0 else 0
    
    if cached > 0:
        logging.info(f"Cache utilization: {cached}/{total} scores ({cache_percentage:.1f}%) found in local cache")
    else:
        logging.info(f"Cache utilization: No scores found in local cache")
        
    return cached_ids, uncached_ids 