"""Functions to fetch and cache score configurations from the API."""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

from ruamel.yaml import YAML
from gql import gql

from plexus.cli.shared import get_score_yaml_path

def fetch_score_configurations(
    client,
    scorecard_data: Dict[str, Any], 
    target_scores: List[Dict[str, Any]], 
    cache_status: Union[Dict[str, bool], Tuple[List[str], List[str]]]
) -> Dict[str, str]:
    """Fetch and cache missing score configurations from the API.
    
    Args:
        client: GraphQL API client
        scorecard_data: The scorecard data containing name and other properties
        target_scores: List of score objects to process
        cache_status: Either a dictionary mapping score IDs to their cache status (bool)
                     or a tuple of (cached_ids, uncached_ids) lists
        
    Returns:
        Dictionary mapping score IDs to their parsed configurations
    """
    scorecard_name = scorecard_data.get('name')
    if not scorecard_name:
        logging.error("Cannot fetch configurations: No scorecard name provided")
        return {}
    
    # Convert different cache_status formats to a consistent format
    needs_fetch = []
    
    if isinstance(cache_status, dict):
        # Dictionary format: {score_id: is_cached}
        # Find scores that are not cached (False values)
        needs_fetch = [
            score for score in target_scores 
            if score.get('id') in cache_status and not cache_status[score.get('id')]
        ]
    elif isinstance(cache_status, tuple) and len(cache_status) == 2:
        # Tuple format: (cached_ids, uncached_ids)
        cached_ids, uncached_ids = cache_status
        # Find scores whose IDs are in the uncached_ids list
        needs_fetch = [
            score for score in target_scores 
            if score.get('id') in uncached_ids
        ]
    else:
        logging.error(f"Unsupported cache_status format: {type(cache_status)}")
        return load_cached_configurations(scorecard_data, target_scores)
        
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
        
        logging.info(f"===== FETCHING CONFIGURATION FOR SCORE =====")
        logging.info(f"Score Name: {score_name}")
        logging.info(f"Score ID: {score_id}")
        logging.info(f"Champion Version ID: {champion_version_id}")
        logging.info(f"=========================================")
        
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
            # Execute query directly without context manager
            try:
                # Try with context manager first
                with client as session:
                    version_result = session.execute(gql(version_query))
            except AttributeError:
                # Fallback to direct execution without context manager
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
                
                # Ensure parsed config is a dictionary
                if not isinstance(parsed_config, dict):
                    logging.error(f"Parsed configuration for {score_name} is not a dictionary")
                    continue
                
                # Add championVersionId to the configuration so we can use it later
                parsed_config['championVersionId'] = champion_version_id
                logging.info(f"Added championVersionId to configuration: {champion_version_id}")
                
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
        champion_version_id = score.get('championVersionId')
        
        logging.info(f"===== LOADING CACHED CONFIGURATION =====")
        logging.info(f"Score Name: {score_name}")
        logging.info(f"Score ID: {score_id}")
        logging.info(f"Champion Version ID from API: {champion_version_id}")
        logging.info(f"======================================")
        
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
                
            # Check if the cached configuration contains championVersionId
            try:
                yaml_parser = YAML(typ='safe')
                parsed_config = yaml_parser.load(configuration)
                cached_version_id = parsed_config.get('championVersionId')
                
                if cached_version_id:
                    logging.info(f"Cached configuration contains championVersionId: {cached_version_id}")
                else:
                    logging.warning(f"Cached configuration for {score_name} does not contain championVersionId")
                    
                    # If the configuration doesn't have championVersionId but we have it from the API
                    # add it to the configuration before returning
                    if champion_version_id:
                        logging.info(f"Adding missing championVersionId from API: {champion_version_id}")
                        parsed_config['championVersionId'] = champion_version_id
                        
                        # Convert updated config back to string
                        import io
                        stream = io.StringIO()
                        yaml_writer = YAML()
                        yaml_writer.dump(parsed_config, stream)
                        configuration = stream.getvalue()
                        
                        # Save the updated configuration with championVersionId
                        with open(yaml_path, 'w') as f:
                            f.write(configuration)
                        logging.info(f"Updated cached configuration with championVersionId")
            except Exception as e:
                logging.warning(f"Could not parse configuration to check for championVersionId: {str(e)}")
                
            configurations[score_id] = configuration
            logging.debug(f"Loaded configuration for score: {score_name}")
            
        except Exception as e:
            logging.error(f"Error loading configuration for {score_name}: {str(e)}")
            
    logging.info(f"Loaded {len(configurations)} configurations")
    return configurations 