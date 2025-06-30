"""Functions to parse score configurations and discover dependencies."""

import logging
from typing import Dict, List, Any, Set, Optional
from ruamel.yaml import YAML

def extract_dependencies_from_config(config_yaml: str) -> List[str]:
    """Extract dependency score names from a score's YAML configuration.
    
    Args:
        config_yaml: Raw YAML configuration string for a score
        
    Returns:
        List of score names that this score depends on
    """
    yaml = YAML(typ='safe')
    try:
        # Parse the YAML configuration
        config = yaml.load(config_yaml)
        
        # Extract depends_on field if it exists
        depends_on = config.get('depends_on', [])
        
        # Handle different dependency formats
        if isinstance(depends_on, list):
            # Simple list of score names
            return depends_on
        elif isinstance(depends_on, dict):
            # Dictionary mapping score names to conditions
            return list(depends_on.keys())
        else:
            logging.warning(f"Invalid depends_on format: {depends_on}")
            return []
    except Exception as e:
        logging.error(f"Error parsing YAML to extract dependencies: {str(e)}")
        return []

def discover_dependencies(
    target_score_ids: Set[str],
    configurations: Dict[str, str],
    score_id_to_name: Dict[str, str],
    score_name_to_id: Dict[str, str]
) -> Set[str]:
    """Recursively discover all dependencies needed for the target scores.
    
    Args:
        target_score_ids: Set of score IDs that are the initial targets
        configurations: Dictionary mapping score IDs to their configuration YAML
        score_id_to_name: Dictionary mapping score IDs to score names
        score_name_to_id: Dictionary mapping score names to score IDs
        
    Returns:
        Set of all score IDs needed (targets + dependencies)
    """
    # Initialize the set of all required score IDs with the targets
    all_required_ids = set(target_score_ids)
    
    # Initialize processing queue with the target scores
    to_process = list(target_score_ids)
    
    # Track processed scores to avoid redundant processing
    processed_ids = set()
    
    # Process the queue
    while to_process:
        current_id = to_process.pop(0)
        
        # Skip if already processed
        if current_id in processed_ids:
            continue
            
        processed_ids.add(current_id)
        
        # Skip if configuration doesn't exist
        if current_id not in configurations:
            logging.warning(f"No configuration found for score ID: {current_id}")
            continue
            
        # Get the score name for better logging
        score_name = score_id_to_name.get(current_id, f"Unknown Score ({current_id})")
        
        # Extract dependencies from the configuration
        config_yaml = configurations[current_id]
        dependency_names = extract_dependencies_from_config(config_yaml)
        
        if dependency_names:
            logging.info(f"Score '{score_name}' depends on: {', '.join(dependency_names)}")
            
            # Resolve dependency names to IDs
            for dep_name in dependency_names:
                dep_id = score_name_to_id.get(dep_name)
                
                if not dep_id:
                    logging.warning(f"Could not resolve dependency '{dep_name}' for score '{score_name}'")
                    continue
                    
                # Add to required set and processing queue
                all_required_ids.add(dep_id)
                if dep_id not in processed_ids:
                    to_process.append(dep_id)
        else:
            logging.debug(f"Score '{score_name}' has no dependencies")
    
    # Log summary
    logging.info(f"Dependency discovery found {len(all_required_ids)} required scores "
                f"(started with {len(target_score_ids)} targets)")
    
    return all_required_ids

def build_name_id_mappings(scores: List[Dict[str, Any]]) -> tuple[Dict[str, str], Dict[str, str]]:
    """Build mappings between score names and IDs.
    
    Args:
        scores: List of score objects containing 'name' and 'id' fields
        
    Returns:
        Tuple of (id_to_name_map, name_to_id_map)
    """
    id_to_name = {}
    name_to_id = {}
    
    for score in scores:
        score_id = score.get('id')
        score_name = score.get('name')
        
        if score_id and score_name:
            id_to_name[score_id] = score_name
            name_to_id[score_name] = score_id
    
    return id_to_name, name_to_id 