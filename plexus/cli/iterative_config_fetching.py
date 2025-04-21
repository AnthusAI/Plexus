"""Functions to iteratively fetch and cache score configurations based on dependencies."""

import logging
from typing import Dict, List, Any, Set, Optional

from gql import gql

from plexus.cli.dependency_discovery import (
    extract_dependencies_from_config,
    discover_dependencies,
    build_name_id_mappings
)
from plexus.cli.check_local_score_cache import check_local_score_cache
from plexus.cli.fetch_score_configurations import (
    fetch_score_configurations,
    load_cached_configurations
)

def iteratively_fetch_configurations(
    client,
    scorecard_data: Dict[str, Any],
    target_scores: List[Dict[str, Any]],
    use_cache: bool = False
) -> Dict[str, str]:
    """Iteratively fetch score configurations including all dependencies.
    
    This function:
    1. Checks local cache for initial target scores (only if use_cache=True)
    2. Fetches missing target configurations
    3. Discovers dependencies in those configurations
    4. Iteratively fetches dependencies until all are resolved
    
    Args:
        client: GraphQL API client
        scorecard_data: The scorecard data containing name and other properties
        target_scores: List of score objects to process initially
        use_cache: Whether to use local cache files instead of always fetching from API
                  When False, will always fetch from API but still write cache files
                  When True, will check local cache first and only fetch missing configs
        
    Returns:
        Dictionary mapping score IDs to their configuration strings
    """
    scorecard_name = scorecard_data.get('name')
    if not scorecard_name:
        logging.error("Cannot fetch configurations: No scorecard name provided")
        return {}
    
    # Build name/ID mappings
    id_to_name, name_to_id = build_name_id_mappings(target_scores)
    
    # Initialize tracking sets
    all_scores = target_scores.copy()  # Keeps growing as we discover dependencies
    all_score_ids = {score.get('id') for score in target_scores if score.get('id')}
    processed_ids = set()  # Scores we've processed dependencies for
    
    # Initialize our configuration store
    configurations = {}
    
    # Store a mapping of score_id to championVersionId
    score_version_map = {}
    for score in target_scores:
        if score.get('id') and score.get('championVersionId'):
            score_version_map[score.get('id')] = score.get('championVersionId')
            logging.info(f"Tracking championVersionId {score.get('championVersionId')} for score {score.get('id')}")
    
    # Process iteratively until all dependencies are resolved
    iteration = 1
    
    while True:
        logging.info(f"Starting iteration {iteration} with {len(all_score_ids) - len(processed_ids)} scores to process")
        
        # Get current unprocessed scores
        current_scores = [
            score for score in all_scores 
            if score.get('id') in all_score_ids and score.get('id') not in processed_ids
        ]
        
        if not current_scores:
            break
        
        if use_cache:
            # Only check local cache if specifically requested to use it
            # Check which configurations we already have cached locally
            cache_status = check_local_score_cache(scorecard_data, current_scores)
            
            # Fetch missing configurations
            new_configs = fetch_score_configurations(client, scorecard_data, current_scores, cache_status)
        else:
            # When use_cache=False, force fetch all configurations from API
            # Create a cache_status dict with all scores marked as not cached
            cache_status = {score.get('id'): False for score in current_scores if score.get('id')}
            logging.info("Bypassing local cache check - fetching all configurations from API")
            
            # Fetch all configurations from API
            new_configs = fetch_score_configurations(client, scorecard_data, current_scores, cache_status)
        
        # Add to our overall configurations
        configurations.update(new_configs)
        
        # Discover dependencies from the new configurations
        current_ids = {score.get('id') for score in current_scores if score.get('id')}
        
        # Add current IDs to processed
        processed_ids.update(current_ids)
        
        # Discover dependencies using the configuration we now have
        dependencies = discover_dependencies(
            current_ids,
            configurations,
            id_to_name,
            name_to_id
        )
        
        # Find new dependencies not already tracked
        new_deps = dependencies - all_score_ids
        
        if not new_deps:
            logging.info(f"No new dependencies found in iteration {iteration}. Process complete.")
            break
            
        # We found new dependencies - fetch metadata for them
        logging.info(f"Found {len(new_deps)} new dependencies in iteration {iteration}.")
        
        # Convert IDs to dependency names (for logging/debugging)
        new_dep_names = [id_to_name.get(dep_id, f"Unknown({dep_id})") for dep_id in new_deps]
        logging.info(f"New dependencies: {', '.join(new_dep_names)}")
        
        # Fetch metadata for all sections and scores in the scorecard to find dependencies
        fetch_query = gql(f"""
        query GetScorecardDetailedStructure {{
            getScorecard(id: "{scorecard_data.get('id')}") {{
                id
                name
                key
                sections {{
                    items {{
                        id
                        name
                        scores {{
                            items {{
                                id
                                name
                                key
                                externalId
                                championVersionId
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """)
        
        try:
            with client as session:
                detailed_result = session.execute(fetch_query)
            
            detailed_data = detailed_result.get('getScorecard', {})
            
            # Extract all scores from all sections
            all_scores_data = []
            for section in detailed_data.get('sections', {}).get('items', []):
                section_scores = section.get('scores', {}).get('items', [])
                all_scores_data.extend(section_scores)
                
            # Find the score objects for our new dependency IDs
            new_dependency_scores = [
                score for score in all_scores_data
                if score.get('id') in new_deps
            ]
            
            # Add these to our tracking
            all_scores.extend(new_dependency_scores)
            all_score_ids.update(new_deps)
            
            # Update our name/ID mappings
            id_to_name, name_to_id = build_name_id_mappings(all_scores)
            
            # Update score_version_map with new dependencies
            for score in new_dependency_scores:
                if score.get('id') and score.get('championVersionId'):
                    score_version_map[score.get('id')] = score.get('championVersionId')
                    logging.info(f"Tracking championVersionId {score.get('championVersionId')} for dependency {score.get('id')}")
            
            logging.info(f"Updated score list now contains {len(all_scores)} scores")
            
        except Exception as e:
            logging.error(f"Error fetching detailed scorecard structure: {str(e)}")
            break
            
        iteration += 1
        
        # Safety to prevent infinite loops
        if iteration > 10:
            logging.warning("Too many iterations, stopping to prevent infinite loop")
            break
    
    # Ensure we've loaded all required configurations
    logging.info(f"Dependency resolution complete. Found {len(all_score_ids)} scores total.")
    logging.info(f"Have configurations for {len(configurations)} scores.")
    
    # Check for any scores we might be missing configurations for
    missing_configs = all_score_ids - set(configurations.keys())
    if missing_configs:
        missing_names = [id_to_name.get(score_id, f"Unknown({score_id})") for score_id in missing_configs]
        logging.warning(f"Missing configurations for: {', '.join(missing_names)}")
        
        # Try one final fetch for any missing configurations
        missing_scores = [score for score in all_scores if score.get('id') in missing_configs]
        if missing_scores:
            if use_cache:
                missing_cache_status = check_local_score_cache(scorecard_data, missing_scores)
            else:
                # Force fetch from API for missing configs as well
                missing_cache_status = {score.get('id'): False for score in missing_scores if score.get('id')}
                
            missing_configs = fetch_score_configurations(client, scorecard_data, missing_scores, missing_cache_status)
            configurations.update(missing_configs)
    
    # Ensure each configuration has the championVersionId
    from ruamel.yaml import YAML
    yaml_parser = YAML(typ='safe')
    
    for score_id, config_str in configurations.items():
        if score_id in score_version_map:
            try:
                # Parse the configuration
                config_dict = yaml_parser.load(config_str)
                
                # Add championVersionId if not already present
                if isinstance(config_dict, dict) and 'championVersionId' not in config_dict:
                    version_id = score_version_map.get(score_id)
                    if version_id:
                        logging.info(f"Adding missing championVersionId {version_id} to score {score_id}")
                        # We should modify the configuration directly
                        config_dict['championVersionId'] = version_id
                        
                        # Convert back to string
                        import io
                        stream = io.StringIO()
                        yaml_writer = YAML()
                        yaml_writer.dump(config_dict, stream)
                        configurations[score_id] = stream.getvalue()
            except Exception as e:
                logging.warning(f"Could not update championVersionId in configuration: {str(e)}")
    
    # Return all configurations
    return configurations 