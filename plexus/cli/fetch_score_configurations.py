"""Functions to fetch and cache score configurations from the API."""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from ruamel.yaml import YAML

from plexus.cli.shared import get_score_yaml_path

def fetch_score_configurations(
    client,
    scorecard_data: Dict[str, Any], 
    target_scores: List[Dict[str, Any]], 
    cache_status: Dict[str, bool]
) -> Dict[str, str]:
    """Fetch and cache missing score configurations from the API.
    
    Args:
        client: GraphQL API client
        scorecard_data: The scorecard data containing name and other properties
        target_scores: List of score objects to process
        cache_status: Dictionary mapping score IDs to their cache status (from check_local_score_cache)
        
    Returns:
        Dictionary mapping score IDs to their parsed configurations
    """
    scorecard_name = scorecard_data.get('name')
    if not scorecard_name:
        logging.error("Cannot fetch configurations: No scorecard name provided")
        return {}
        
    # Count how many configurations need to be fetched
    needs_fetch = [score for score in target_scores 
                  if score.get('id') in cache_status and not cache_status[score.get('id')]]
    
    if not needs_fetch:
        logging.info("All required score configurations are already cached locally.")
        return load_cached_configurations(scorecard_data, target_scores)
    
    logging.info(f"Fetching {len(needs_fetch)} missing score configurations from API")
    
    # Initialize dictionary to store configurations
    configurations = {}
    
    # Set up YAML formatter for consistent formatting
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # Prevent line wrapping
    
    # Configure YAML formatting
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.map_indent = 2
    yaml.sequence_indent = 4
    yaml.sequence_dash_offset = 2
    
    # Configure literal block style for system_message and user_message
    def literal_presenter(dumper, data):
        if isinstance(data, str) and "\n" in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)
    
    yaml.representer.add_representer(str, literal_presenter)
    
    # Process each score that needs fetching
    for score in needs_fetch:
        score_id = score.get('id')
        score_name = score.get('name')
        champion_version_id = score.get('championVersionId')
        
        if not champion_version_id:
            logging.warning(f"No champion version ID for score: {score_name} ({score_id})")
            continue
            
        logging.info(f"Fetching configuration for score: {score_name} ({score_id})")
        
        # Get version content
        version_query = f"""
        query GetScoreVersion {{
            getScoreVersion(id: "{champion_version_id}") {{
                id
                configuration
                createdAt
                updatedAt
                note
            }}
        }}
        """
        
        try:
            version_result = client.execute(version_query)
            version_data = version_result.get('getScoreVersion')
            
            if not version_data or not version_data.get('configuration'):
                logging.error(f"No configuration found for version: {champion_version_id}")
                continue
                
            # Parse the YAML content to ensure it's valid
            config_yaml = version_data.get('configuration')
            
            try:
                # Parse the configuration to validate it
                parsed_config = yaml.load(config_yaml)
                
                # Get the YAML file path
                yaml_path = get_score_yaml_path(scorecard_name, score_name)
                
                # Write to file with proper formatting
                with open(yaml_path, 'w') as f:
                    yaml.dump(parsed_config, f)
                
                # Store the configuration
                configurations[score_id] = config_yaml
                
                logging.info(f"Saved score configuration to: {yaml_path}")
                
            except Exception as e:
                logging.error(f"Error parsing YAML for score {score_name}: {str(e)}")
                continue
                
        except Exception as e:
            logging.error(f"Error fetching score version: {str(e)}")
            continue
    
    # Now load all configurations (both freshly fetched and pre-existing)
    return load_cached_configurations(scorecard_data, target_scores)

def load_cached_configurations(
    scorecard_data: Dict[str, Any], 
    target_scores: List[Dict[str, Any]]
) -> Dict[str, str]:
    """Load all cached score configurations from the local filesystem.
    
    Args:
        scorecard_data: The scorecard data containing name and other properties
        target_scores: List of score objects to process
        
    Returns:
        Dictionary mapping score IDs to their configuration strings
    """
    scorecard_name = scorecard_data.get('name')
    if not scorecard_name:
        logging.error("Cannot load configurations: No scorecard name provided")
        return {}
        
    logging.info(f"Loading cached configurations for {len(target_scores)} scores")
    
    configurations = {}
    
    for score in target_scores:
        score_id = score.get('id')
        score_name = score.get('name')
        
        if not score_id or not score_name:
            logging.warning(f"Skipping score with missing ID or name: {score}")
            continue
            
        # Get the expected file path
        yaml_path = get_score_yaml_path(scorecard_name, score_name)
        
        # Check if the file exists
        if not yaml_path.exists():
            logging.warning(f"Configuration file not found for {score_name}: {yaml_path}")
            continue
            
        # Load the configuration
        try:
            with open(yaml_path, 'r') as f:
                configuration = f.read()
                
            configurations[score_id] = configuration
            logging.debug(f"Loaded configuration for score: {score_name}")
            
        except Exception as e:
            logging.error(f"Error loading configuration for {score_name}: {str(e)}")
            
    logging.info(f"Loaded {len(configurations)} configurations")
    return configurations 