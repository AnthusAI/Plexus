import asyncio
import logging
import traceback
from typing import Dict, Optional
from plexus.dashboard.api.models.scorecard import Scorecard as ScorecardModel
from plexus.dashboard.api.models.score import Score as ScoreModel

async def create_scorecard_instance_for_single_score(scorecard_identifier: str, score_identifier: str) -> "Optional[ScorecardModel]":
    """Create a scorecard instance optimized for a single score request."""
    try:
        logging.info(f"Creating targeted scorecard instance for scorecard: {scorecard_identifier}, score: {score_identifier}")
        
        # Import the individual functions we need for targeted loading
        from plexus.cli.shared.direct_memoized_resolvers import direct_memoized_resolve_scorecard_identifier
        from plexus.cli.shared.fetch_scorecard_structure import fetch_scorecard_structure
        from plexus.cli.shared.identify_target_scores import identify_target_scores
        from plexus.cli.shared.iterative_config_fetching import iteratively_fetch_configurations
        from plexus.Scorecard import Scorecard
        
        # Step 1: Get API client and resolve scorecard identifier
        from plexus.dashboard.api.client import PlexusDashboardClient
        client = PlexusDashboardClient()
        
        scorecard_id = await asyncio.to_thread(direct_memoized_resolve_scorecard_identifier, client, scorecard_identifier)
        if not scorecard_id:
            logging.error(f"Could not resolve scorecard identifier: {scorecard_identifier}")
            return None
            
        logging.info(f"Resolved scorecard ID: {scorecard_id}")
        
        # Step 2: Fetch minimal scorecard structure (just metadata, not full configs)
        scorecard_structure = await asyncio.to_thread(fetch_scorecard_structure, client, scorecard_id)
        if not scorecard_structure:
            logging.error(f"Could not fetch scorecard structure for ID: {scorecard_id}")
            return None
            
        # Step 3: Find the specific target score by its identifier
        # Convert the score identifier to a list for the function
        target_scores = await asyncio.to_thread(
            identify_target_scores, 
            scorecard_structure, 
            [score_identifier]  # Only the one score we want
        )
        
        if not target_scores:
            logging.error(f"Could not find score {score_identifier} in scorecard {scorecard_identifier}")
            return None
            
        logging.info(f"Identified target score: {target_scores[0]}")
        
        # Step 4: Fetch only the required configurations (target + dependencies)
        # This will do just-in-time dependency resolution
        scorecard_configs = await asyncio.to_thread(
            iteratively_fetch_configurations,
            client,
            scorecard_structure,
            target_scores,
            use_cache=False  # Always fresh for API requests
        )
        
        if not scorecard_configs:
            logging.error(f"Could not fetch configurations for score {score_identifier}")
            return None
            
        logging.info(f"Fetched {len(scorecard_configs)} score configurations (target + dependencies)")
        
        # Step 5: Create scorecard instance with only the required scores
        # Parse string configurations into dictionaries (same as in evaluations.py)
        parsed_configs = []
        from ruamel.yaml import YAML
        yaml_parser = YAML(typ='safe')
        
        for score_id, config in scorecard_configs.items():
            try:
                # If config is a string, parse it as YAML
                if isinstance(config, str):
                    parsed_config = yaml_parser.load(config)
                    # Add the score ID as an identifier if not present
                    if 'id' not in parsed_config:
                        parsed_config['id'] = score_id
                    parsed_configs.append(parsed_config)
                elif isinstance(config, dict):
                    # If already a dict, add as is
                    if 'id' not in config:
                        config['id'] = score_id
                    parsed_configs.append(config)
                else:
                    logging.warning(f"Skipping config with unexpected type: {type(config)}")
            except Exception as parse_err:
                logging.error(f"Failed to parse configuration for score {score_id}: {str(parse_err)}")
        
        scorecard_instance = await asyncio.to_thread(
            Scorecard.create_instance_from_api_data,
            scorecard_id,
            scorecard_structure, 
            parsed_configs
        )
        
        if scorecard_instance:
            logging.info(f"Successfully created targeted scorecard instance with {len(scorecard_configs)} scores")
            return scorecard_instance
        else:
            logging.error("Failed to create scorecard instance from API data")
            return None
            
    except Exception as e:
        logging.error(f"Error creating targeted scorecard instance: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

async def resolve_scorecard_id(external_id: str, account_id: str, client) -> Optional[str]:
    """
    Resolve a scorecard external ID to its DynamoDB ID using the GSI, scoped by accountId.
    
    Args:
        external_id: The external ID of the scorecard
        account_id: The DynamoDB ID of the account
        client: The dashboard client
        
    Returns:
        The DynamoDB ID of the scorecard if found, None otherwise
    """
    try:
        # Use the Scorecard SDK method for lookup
        scorecard = await asyncio.to_thread(
            ScorecardModel.get_by_account_and_external_id,
            account_id,
            external_id,
            client
        )
        
        if scorecard:
            logging.info(f"Resolved scorecard external ID {external_id} for account {account_id} to DynamoDB ID {scorecard.id}")
            return scorecard.id
            
        logging.warning(f"Could not resolve scorecard external ID: {external_id} for account {account_id}")
        return None
    except Exception as e:
        logging.error(f"Error resolving scorecard external ID for account {account_id}: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

async def resolve_score_id(external_id: str, scorecard_dynamo_id: str, client) -> Optional[Dict[str, str]]:
    """
    Resolve a score external ID to its DynamoDB ID and name, scoped by its parent scorecard's DynamoDB ID.
    
    Args:
        external_id: The external ID of the score (e.g., "0")
        scorecard_dynamo_id: The DynamoDB ID of the parent scorecard
        client: The dashboard client
        
    Returns:
        A dictionary with 'id' (DynamoDB ID) and 'name' of the score if found, None otherwise
    """
    try:
        # Use the Score SDK method for lookup
        score_data = await asyncio.to_thread(
            ScoreModel.get_by_scorecard_and_external_id,
            scorecard_dynamo_id,
            external_id,
            client
        )
        
        if score_data:
            logging.info(f"Resolved score external ID {external_id} for scorecard {scorecard_dynamo_id} to DynamoDB ID {score_data['id']} with name {score_data['name']}")
            return {"id": score_data['id'], "name": score_data['name']}
            
        logging.warning(f"Could not resolve score external ID: {external_id} for scorecard {scorecard_dynamo_id}")
        return None
    except Exception as e:
        logging.error(f"Error resolving score external ID {external_id} for scorecard {scorecard_dynamo_id}: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None
