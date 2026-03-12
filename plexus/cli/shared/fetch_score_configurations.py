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
    cache_status: Union[Dict[str, bool], Tuple[List[str], List[str]]],
    use_cache: bool = True
) -> Dict[str, str]:
    """Fetch and cache missing score configurations from the API.
    
    Args:
        client: GraphQL API client
        scorecard_data: The scorecard data containing name and other properties
        target_scores: List of score objects to process
        cache_status: Either a dictionary mapping score IDs to their cache status (bool)
                     or a tuple of (cached_ids, uncached_ids) lists
        use_cache: Whether to return configurations from cache (True) or use in-memory data (False)
                  When True: after fetching, load everything from cache files
                  When False: return API results directly without loading from cache
        
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
        if use_cache:
            return load_cached_configurations(scorecard_data, target_scores)
        else:
            return {}
        
    # Initialize configurations with empty dict
    configurations = {}
    
    # If all scores are already in cache and we're using cache, load cached configurations
    if not needs_fetch and use_cache:
        logging.info("All required score configurations are already cached locally.")
        return load_cached_configurations(scorecard_data, target_scores)
    
    # If nothing needs fetching and we're not using cache, return empty dict
    if not needs_fetch and not use_cache:
        logging.info("No score configurations to fetch.")
        return configurations
    
    # Fetching missing score configurations from API
    
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
    
    # Fetch each needed configuration
    for score in needs_fetch:
        score_id = score.get('id')
        score_name = score.get('name')
        champion_version_id = score.get('championVersionId')
        
        logging.info(f"==== FETCHING SCORE CONFIGURATION ====")
        logging.info(f"Score Name: {score_name}")
        logging.info(f"Score ID: {score_id}")
        logging.info(f"Version ID to fetch: {champion_version_id}")
        logging.info(f"======================================")
        
        if not score_id or not score_name or not champion_version_id:
            logging.error(f"Missing required properties for score: {score}")
            continue
        
        # Build the GraphQL query
        query = """
        query GetScoreVersion($id: ID!) {
            getScoreVersion(id: $id) {
                id
                configuration
            }
        }
        """
        
        try:
            # Execute the query
            with client as session:
                result = session.execute(gql(query), variable_values={"id": champion_version_id})
            
            # Extract the configuration
            version_data = result.get('getScoreVersion', {})
            
            if not version_data or 'configuration' not in version_data:
                logging.error(f"No configuration found for version: {champion_version_id}")
                continue
                
            # Parse the YAML content to ensure it's valid
            config_yaml = version_data.get('configuration')
            
            logging.info(f"==== FETCHED YAML CONFIGURATION ====")
            logging.info(f"Score: {score_name}")
            logging.info(f"Version: {champion_version_id}")
            logging.info(f"YAML Content (first 500 chars):")
            logging.info(f"{config_yaml[:500]}...")
            logging.info(f"=====================================")
            
            try:
                # Parse the configuration to validate it
                parsed_config = yaml.load(config_yaml)
                
                # Ensure parsed config is a dictionary
                if not isinstance(parsed_config, dict):
                    logging.error(f"Parsed configuration for {score_name} is not a dictionary")
                    continue
                
                # Reorder fields in the exact order: name, key, id, version, parent
                ordered_config = {}
                
                # Add name if it exists
                if 'name' in parsed_config:
                    ordered_config['name'] = parsed_config['name']
                
                # Add key if it exists
                if 'key' in parsed_config:
                    ordered_config['key'] = parsed_config['key']
                
                # Add id if it exists
                if 'id' in parsed_config:
                    ordered_config['id'] = parsed_config['id']
                
                # Add version
                ordered_config['version'] = champion_version_id
                logging.info(f"YAML version field set to: {champion_version_id}")
                
                # Add parent if it exists
                if 'parent' in parsed_config:
                    ordered_config['parent'] = parsed_config['parent']
                
                # Add all other fields
                for key, value in parsed_config.items():
                    if key not in ['name', 'key', 'id', 'version', 'parent']:
                        ordered_config[key] = value
                
                # Get the YAML file path
                yaml_path = get_score_yaml_path(scorecard_name, score_name)
                
                # Write to file with proper formatting
                with open(yaml_path, 'w') as f:
                    yaml.dump(ordered_config, f)
                
                # Store the configuration in memory
                configurations[score_id] = config_yaml
                
                logging.info(f"==== CONFIGURATION SAVED ====")
                logging.info(f"Score: {score_name}")
                logging.info(f"Version: {champion_version_id}")
                logging.info(f"Saved to: {yaml_path}")
                logging.info(f"===============================")
                
            except Exception as e:
                logging.error(f"Error parsing YAML for score {score_name}: {str(e)}")
                continue
                
        except Exception as e:
            logging.error(f"Error fetching score version: {str(e)}")
            continue
    
    # If we're using cache, load everything from cache
    if use_cache:
        logging.info("Using cached configurations - loading from disk")
        return load_cached_configurations(scorecard_data, target_scores)
    else:
        # If we're not using cache, we need to return the in-memory configurations
        # But we might need to fill in any missing configurations from the target_scores
        # that weren't included in needs_fetch (if cache_status doesn't have all scores)
        if len(configurations) < len(target_scores):
            logging.info("Not using cache - returning in-memory configurations")
            logging.info(f"Have {len(configurations)} configurations in memory, need {len(target_scores)}")
            
            # For any scores that are missing from configurations, load them from disk
            # This ensures we have complete data even if cache_status was incomplete
            for score in target_scores:
                score_id = score.get('id')
                if not score_id or score_id in configurations:
                    continue
                
                score_name = score.get('name')
                if not score_name:
                    continue
                
                yaml_path = get_score_yaml_path(scorecard_name, score_name)
                if not yaml_path.exists():
                    logging.warning(f"Configuration file not found for {score_name}: {yaml_path}")
                    continue
                
                try:
                    with open(yaml_path, 'r') as f:
                        configuration = f.read()
                    configurations[score_id] = configuration
                    logging.info(f"Added missing configuration for {score_name} from disk")
                except Exception as e:
                    logging.error(f"Error loading configuration for {score_name}: {str(e)}")
        
        logging.info(f"Returning {len(configurations)} configurations from memory")
        return configurations

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
        
        logging.debug(f"Loading cached configuration")
        logging.debug(f"Score: {score_name}")
        # Score ID for debug: {score_id}
        # Champion version: {champion_version_id}
        # End debug info
        
        # Validate score_id format - should be a UUID with hyphens
        if score_id and not (isinstance(score_id, str) and '-' in score_id):
            logging.warning(f"WARNING: Score ID doesn't appear to be in DynamoDB UUID format: {score_id}")
            logging.warning(f"This may cause issues with Evaluation records. Expected format is UUID with hyphens.")
            # Check for externalId which is often incorrectly used
            if 'externalId' in score:
                logging.warning(f"Found externalId: {score.get('externalId')} - this should NOT be used as the Score ID")
        
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
                
            # Check if the cached configuration contains version
            try:
                yaml_parser = YAML(typ='safe')
                parsed_config = yaml_parser.load(configuration)
                cached_version_id = parsed_config.get('version')
                
                if cached_version_id:
                    logging.info(f"Cached configuration contains version: {cached_version_id}")
                else:
                    logging.warning(f"Cached configuration for {score_name} does not contain version")
                    
                    # If the configuration doesn't have version but we have it from the API
                    # add it to the configuration before returning
                    if champion_version_id:
                        logging.info(f"Adding missing version from API: {champion_version_id}")
                        
                        # Reorder fields in the exact order: name, key, id, version, parent
                        ordered_config = {}
                        
                        # Add name if it exists
                        if 'name' in parsed_config:
                            ordered_config['name'] = parsed_config['name']
                        
                        # Add key if it exists
                        if 'key' in parsed_config:
                            ordered_config['key'] = parsed_config['key']
                        
                        # Add id if it exists
                        if 'id' in parsed_config:
                            ordered_config['id'] = parsed_config['id']
                        
                        # Add version
                        ordered_config['version'] = champion_version_id
                        
                        # Add parent if it exists
                        if 'parent' in parsed_config:
                            ordered_config['parent'] = parsed_config['parent']
                        
                        # Add all other fields
                        for key, value in parsed_config.items():
                            if key not in ['name', 'key', 'id', 'version', 'parent']:
                                ordered_config[key] = value
                        
                        # Convert updated config back to string
                        import io
                        stream = io.StringIO()
                        yaml_writer = YAML()
                        yaml_writer.dump(ordered_config, stream)
                        configuration = stream.getvalue()
                        
                        # Save the updated configuration with version
                        with open(yaml_path, 'w') as f:
                            f.write(configuration)
                        logging.info(f"Updated cached configuration with version")
            except Exception as e:
                logging.warning(f"Could not parse configuration to check for version: {str(e)}")
                
            configurations[score_id] = configuration
            logging.debug(f"Loaded configuration for score: {score_name}")
            
        except Exception as e:
            logging.error(f"Error loading configuration for {score_name}: {str(e)}")
            
    logging.info(f"Loaded {len(configurations)} configurations")
    return configurations 