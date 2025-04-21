"""Functions to check for locally cached score configurations."""

import logging
from pathlib import Path
from typing import Dict, List, Any, Set, Optional, Union, Tuple

from plexus.cli.shared import get_score_yaml_path

def check_local_score_cache(arg1, arg2) -> Union[Tuple[List[str], List[str]], Dict[str, bool]]:
    """
    Check which score configurations are already cached locally.
    This function can be called with two different parameter patterns:
    
    Pattern 1 (Original): 
        score_configs (dict): A dictionary of score IDs to their configurations
        scorecard_name (str): The name of the scorecard
        Returns tuple: (list of cached score IDs, list of uncached score IDs)
        
    Pattern 2 (New): 
        scorecard_data (dict): Dictionary containing scorecard information including 'name'
        score_objects (list): List of score objects with 'id' and 'name' properties
        Returns dict: Dictionary mapping score IDs to boolean cache status
    """
    # Determine which parameter pattern is being used
    if isinstance(arg1, dict) and isinstance(arg2, (str, int, float)):
        # Original pattern: (score_configs, scorecard_name)
        return _check_local_score_cache_original(arg1, arg2)
    elif isinstance(arg1, dict) and isinstance(arg2, list):
        # New pattern: (scorecard_data, score_objects)
        return _check_local_score_cache_new(arg1, arg2)
    else:
        logging.error(f"Unsupported parameter types: {type(arg1)}, {type(arg2)}")
        if isinstance(arg1, dict) and 'name' in arg1 and isinstance(arg2, list):
            # Try to recover using the new pattern even with wrong types
            return _check_local_score_cache_new(arg1, arg2)
        # Return empty results as a fallback
        return {} if isinstance(arg2, list) else ([], [])

def _check_local_score_cache_original(score_configs, scorecard_name):
    """Original implementation that takes score_configs dict and scorecard_name string."""
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
                if parsed_config and isinstance(parsed_config, dict):
                    score_name = parsed_config.get('name')
                else:
                    logging.warning(f"Parsed config is not a dictionary for score {score_id}")
            except Exception as e:
                logging.warning(f"Could not parse YAML for score {score_id}: {str(e)}")
        elif isinstance(config, dict):
            # Assume it's already a dictionary
            score_name = config.get('name')
        else:
            logging.warning(f"Unsupported config type for score {score_id}: {type(config)}")
            
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

def _check_local_score_cache_new(scorecard_data, score_objects):
    """New implementation that takes scorecard_data dict and score_objects list."""
    scorecard_name = scorecard_data.get('name')
    if not scorecard_name:
        logging.error("Cannot check cache: No scorecard name found in scorecard data")
        return {}
    
    # Create a dictionary to track cache status
    cache_status = {}
    
    for score in score_objects:
        score_id = score.get('id')
        score_name = score.get('name')
        
        if not score_id:
            logging.warning("Skipping score with no ID")
            continue
            
        if not score_name:
            logging.warning(f"Skipping score with no name: {score_id}")
            cache_status[score_id] = False
            continue
        
        # Get the expected cache path
        cache_path = get_score_yaml_path(scorecard_name, score_name)
        
        # Check if the file exists and is non-empty
        if cache_path.exists() and cache_path.stat().st_size > 0:
            cache_status[score_id] = True
            logging.info(f"Loading score configuration from cache: {score_name} ({score_id})")
        else:
            cache_status[score_id] = False
            logging.info(f"Fetching score configuration from API: {score_name} ({score_id})")
    
    # Log a summary of the cache check
    total = len(score_objects)
    cached = sum(1 for status in cache_status.values() if status)
    cache_percentage = (cached / total * 100) if total > 0 else 0
    
    if cached > 0:
        logging.info(f"Cache utilization: {cached}/{total} scores ({cache_percentage:.1f}%) found in local cache")
    else:
        logging.info(f"Cache utilization: No scores found in local cache")
        
    return cache_status 