"""
Shared utility functions for fetching and caching score configurations.

This module provides a unified approach to fetch score configurations from the API
and cache them locally, with consistent formatting and error handling.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union

from gql import gql
from ruamel.yaml import YAML

from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.direct_memoized_resolvers import (
    direct_memoized_resolve_scorecard_identifier,
    direct_memoized_resolve_score_identifier
)
from plexus.cli.fetch_scorecard_structure import fetch_scorecard_structure
from plexus.cli.shared import get_score_yaml_path


def fetch_and_cache_single_score(
    client: PlexusDashboardClient,
    scorecard_identifier: str,
    score_identifier: str,
    use_cache: bool = False,
    verbose: bool = False
) -> Tuple[Dict[str, Any], Path, bool]:
    """
    Fetch a single score configuration from the API and cache it locally.
    
    This function is a unified implementation that combines the best aspects of 
    both the score pull command and the evaluation command approach.
    
    Args:
        client: The GraphQL API client
        scorecard_identifier: Identifier for the scorecard (ID, key, name, external ID)
        score_identifier: Identifier for the score (ID, key, name, external ID)
        use_cache: Whether to check and use locally cached files first
                   When False (default), always fetch from API but still update cache
                   When True, check local cache first and only fetch if not found
        verbose: Whether to enable verbose logging
        
    Returns:
        Tuple of (score_configuration, yaml_path, from_cache)
        - score_configuration: The parsed score configuration as a dictionary
        - yaml_path: The path to the cached YAML file
        - from_cache: Whether the configuration was loaded from cache
        
    Raises:
        ValueError: If scorecard or score cannot be found
    """
    # Simplified verbose logging
    if verbose:
        mode = "cache-first" if use_cache else "API-first"
        logging.info(f"Fetching score '{score_identifier}' from scorecard '{scorecard_identifier}' (mode: {mode})")
    
    # 1. Resolve the scorecard identifier to an ID
    scorecard_id = direct_memoized_resolve_scorecard_identifier(client, scorecard_identifier)
    if not scorecard_id:
        error_msg = f"Could not find scorecard: {scorecard_identifier}"
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    
    # 2. Fetch scorecard structure
    try:
        scorecard_data = fetch_scorecard_structure(client, scorecard_id)
        if not scorecard_data:
            error_msg = f"Could not fetch structure for scorecard: {scorecard_id}"
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        scorecard_name = scorecard_data.get('name', 'Unknown')
        
        if verbose:
            logging.info(f"Found scorecard: {scorecard_name} (ID: {scorecard_id})")
    except Exception as e:
        error_msg = f"Error fetching scorecard structure: {str(e)}"
        logging.error(error_msg)
        raise ValueError(error_msg) from e
    
    # 3. Find the score in the scorecard
    score_id = direct_memoized_resolve_score_identifier(client, scorecard_id, score_identifier)
    if not score_id:
        error_msg = f"Could not find score: {score_identifier} in scorecard: {scorecard_name}"
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    # Find score object with additional details (name, championVersionId)
    score_object = None
    for section in scorecard_data.get('sections', {}).get('items', []):
        for item in section.get('scores', {}).get('items', []):
            if item.get('id') == score_id:
                score_object = item
                break
        if score_object:
            break
    
    if not score_object:
        error_msg = f"Score {score_id} was found but details are missing"
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    score_name = score_object.get('name', 'Unknown')
    champion_version_id = score_object.get('championVersionId')
    
    if not champion_version_id:
        error_msg = f"No champion version found for score: {score_name}"
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    if verbose:
        logging.info(f"Found score: {score_name} (ID: {score_id})")
        logging.info(f"Champion version ID: {champion_version_id}")
    
    # 4. Determine cache path and check if it exists
    yaml_path = get_score_yaml_path(scorecard_name, score_name)
    from_cache = False
    
    if use_cache and yaml_path.exists() and yaml_path.stat().st_size > 0:
        # Load from cache if requested and available
        try:
            yaml = YAML()
            yaml.preserve_quotes = True
            with open(yaml_path, 'r') as f:
                config = yaml.load(f)
            
            # Ensure consistent handling of IDs as strings
            if isinstance(config, dict) and 'id' in config and not isinstance(config['id'], str):
                config['id'] = str(config['id'])
            
            from_cache = True
            
            return config, yaml_path, from_cache
        except Exception as e:
            # If there's any error loading from cache, fall back to API
            logging.warning(f"Error loading from cache, falling back to API: {str(e)}")
    
    # 5. Fetch configuration from API if not loaded from cache
    try:
        # Get the score version content
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
        
        with client as session:
            version_result = session.execute(gql(version_query))
        
        version_data = version_result.get('getScoreVersion', {})
        
        if not version_data or not version_data.get('configuration'):
            error_msg = f"No configuration found for version: {champion_version_id}"
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        # 6. Parse and save the configuration
        try:
            content = version_data.get('configuration')
            
            # Initialize ruamel.yaml with the same settings as score pull uses
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
            
            # Parse the YAML content
            config = yaml.load(content)
            
            # Add version ID if not present (for consistency with other operations)
            if isinstance(config, dict):
                # Ensure ID is a string (if present)
                if 'id' in config and not isinstance(config['id'], str):
                    config['id'] = str(config['id'])
                
                # Add version if not present
                if 'version' not in config:
                    config['version'] = champion_version_id
            
            # Write to file
            with open(yaml_path, 'w') as f:
                yaml.dump(config, f)
            
            
            return config, yaml_path, from_cache
            
        except Exception as e:
            error_msg = f"Error parsing or saving YAML content: {str(e)}"
            logging.error(error_msg)
            raise ValueError(error_msg) from e
            
    except Exception as e:
        error_msg = f"Error fetching score configuration: {str(e)}"
        logging.error(error_msg)
        raise ValueError(error_msg) from e 