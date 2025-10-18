import asyncio
import logging
import traceback
import json
import os
from typing import Dict, Optional
from plexus.dashboard.api.models.scorecard import Scorecard as ScorecardModel
from plexus.dashboard.api.models.score import Score as ScoreModel
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.score_result import ScoreResult
# Import Item model for upsert functionality
try:
    from plexus.dashboard.api.models.item import Item
    PLEXUS_ITEM_AVAILABLE = True
except ImportError:
    PLEXUS_ITEM_AVAILABLE = False
from plexus.plexus_logging.Cloudwatch import CloudWatchLogger

# Initialize CloudWatch logger for metrics
cloudwatch_logger = CloudWatchLogger(namespace="CallCriteria/API")

async def get_plexus_client():
    """Get the Plexus Dashboard client for API operations."""
    from plexus.dashboard.api.client import PlexusDashboardClient
    return PlexusDashboardClient()

def sanitize_metadata_for_graphql(metadata: dict) -> dict:
    """
    Sanitize metadata for GraphQL compatibility.

    Handles various data types and applies size limits to ensure the metadata
    can be safely stored in GraphQL/DynamoDB:
    - Truncates long strings
    - Summarizes large complex objects
    - Removes problematic characters
    - Handles serialization errors gracefully

    Args:
        metadata: Dictionary of metadata to sanitize

    Returns:
        Sanitized metadata dictionary safe for GraphQL operations
    """
    sanitized_metadata = {}
    if metadata:
        for key, meta_value in metadata.items():
            try:
                if meta_value is None:
                    sanitized_metadata[key] = None
                elif isinstance(meta_value, bool):
                    sanitized_metadata[key] = meta_value
                elif isinstance(meta_value, (int, float)):
                    # Ensure numeric values are reasonable for GraphQL
                    if abs(meta_value) < 1e10:
                        sanitized_metadata[key] = meta_value
                elif isinstance(meta_value, str):
                    # Truncate very long strings and remove problematic characters
                    cleaned_str = meta_value.replace('\x00', '').replace('\r', '').replace('\n', ' ')
                    if len(cleaned_str) > 500:
                        cleaned_str = cleaned_str[:497] + "..."
                    sanitized_metadata[key] = cleaned_str
                elif isinstance(meta_value, (dict, list)):
                    # Convert complex objects to JSON strings with size limit
                    json_str = json.dumps(meta_value, default=str)
                    if len(json_str) > 1000:
                        # Store summary instead of full object
                        if isinstance(meta_value, dict):
                            sanitized_metadata[key] = f"{{dict with {len(meta_value)} keys}}"
                        elif isinstance(meta_value, list):
                            sanitized_metadata[key] = f"[list with {len(meta_value)} items]"
                    else:
                        sanitized_metadata[key] = json_str
                else:
                    # Convert other types to string with size limit
                    str_value = str(meta_value)[:500]
                    sanitized_metadata[key] = str_value
            except Exception as e:
                logging.warning(f"Failed to sanitize metadata key '{key}': {e}")
                # Store a safe placeholder instead of skipping
                sanitized_metadata[key] = f"<serialization_error: {type(meta_value).__name__}>"

    return sanitized_metadata

async def check_if_score_is_disabled(scorecard_external_id: str, score_external_id: str, account_id: str) -> bool:
    """
    Check if a score is currently disabled by querying the API.
    
    Args:
        scorecard_external_id: The external ID of the scorecard
        score_external_id: The external ID of the score
        account_id: The DynamoDB ID of the account
        
    Returns:
        bool: True if the score is disabled, False otherwise
    """
    try:
        if not account_id:
            logging.error("No account ID provided. Cannot check if score is disabled.")
            return False
        
        client = await get_plexus_client()
        
        # Resolve scorecard ID
        scorecard_dynamo_id = await resolve_scorecard_id(scorecard_external_id, account_id, client)
        if not scorecard_dynamo_id:
            logging.warning(f"Could not resolve scorecard {scorecard_external_id} - assuming score not disabled")
            return False
        
        # Resolve score ID and get its disabled status
        resolved_score_info = await resolve_score_id(score_external_id, scorecard_dynamo_id, client)
        if not resolved_score_info:
            logging.warning(f"Could not resolve score {score_external_id} - assuming not disabled")
            return False
            
        score_dynamo_id = resolved_score_info['id']
        
        # Get the score using SDK method to check its disabled status
        score = await asyncio.to_thread(ScoreModel.get_by_id, score_dynamo_id, client)
        
        if score:
            is_disabled = getattr(score, 'isDisabled', False)
            logging.info(f"Score {score_external_id} (ID: {score_dynamo_id}) disabled status: {is_disabled}")
            return is_disabled
        else:
            logging.warning(f"Could not fetch score data for ID: {score_dynamo_id}")
            return False
            
    except Exception as e:
        logging.error(f"Error checking if score is disabled: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        # If there's an error, assume not disabled (fail open)
        return False


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

async def get_existing_score_result(report_id: str, scorecard_id: str, score_id: str, account_id: str) -> Optional[dict]:
    """
    Check if a score result already exists for the given report, scorecard, and score.
    Now uses the new ScoreResult.find_by_cache_key method for cleaner, more maintainable code.
    
    Args:
        report_id: The external ID of the report
        scorecard_id: The external ID of the scorecard
        score_id: The external ID of the score
        account_id: The DynamoDB ID of the account
    Returns:
        A dictionary with the cached result if found, None otherwise
    """
    try:
        client = await get_plexus_client()
        
        # Use Item.find_by_identifier to get the item (consistent with cache creation)
        if PLEXUS_ITEM_AVAILABLE:
            item = await asyncio.to_thread(
                Item.find_by_identifier,
                client=client,
                account_id=account_id,
                identifier_key="reportId",  # Use input key (will be mapped to "report ID" internally)
                identifier_value=report_id,
                debug=True  # Enable debug logging to verify the fix
            )
            
            if not item:
                logging.info(f"❌ No Item found with reportId: {report_id} in account: {account_id}")
                return None
            
            logging.info(f"✅ Found Item with ID: {item.id} for reportId: {report_id}")
        else:
            logging.error("Plexus Item SDK not available")
            return None
        
        # Resolve scorecard and score IDs
        # CRITICAL: We must have valid DynamoDB IDs for both scorecard and score to prevent cache pollution.
        # Previously, using external IDs as fallbacks caused incorrect cache hits where requests for 
        # non-existent scores would return cached results from completely different scores/scorecards.
        dynamo_scorecard_id = await resolve_scorecard_id(scorecard_id, account_id, client)
        if not dynamo_scorecard_id:
            logging.warning(f"Scorecard ID {scorecard_id} could not be resolved - skipping cache lookup to prevent cross-scorecard pollution")
            return None
        
        resolved_score_info = await resolve_score_id(score_id, dynamo_scorecard_id, client)
        if not resolved_score_info:
            logging.warning(f"Score ID {score_id} could not be resolved - skipping cache lookup to prevent cross-score pollution")
            return None
        
        dynamo_score_id = resolved_score_info['id']
        
        # Use the new ScoreResult.find_by_cache_key method
        cached_score_result = await asyncio.to_thread(
            ScoreResult.find_by_cache_key,
            client=client,
            item_id=item.id,
            scorecard_id=dynamo_scorecard_id,
            score_id=dynamo_score_id,
            account_id=account_id
        )
        
        if cached_score_result:
            logging.info(f"✅ CACHE HIT: Found cached result {cached_score_result.id} with value: {cached_score_result.value}")
            logging.info(json.dumps({
                "message_type": "cache_hit_found",
                "score_result_id": cached_score_result.id,
                "report_id": report_id,
                "scorecard_id": scorecard_id,
                "score_id": score_id,
                "item_id": item.id,
                "value": cached_score_result.value,
                "updated_at": cached_score_result.updatedAt.isoformat() if cached_score_result.updatedAt else None,
                "method": "score_result_find_by_cache_key"
            }))
            
            cloudwatch_logger.log_metric(
                metric_name="CacheHit",
                metric_value=1,
                dimensions={"Environment": os.getenv('environment', 'unknown')}
            )
            
            return {
                "value": cached_score_result.value,
                "explanation": cached_score_result.explanation or ''
            }
        else:
            logging.info(f"❌ CACHE MISS: No cached result found for item_id={item.id}, scorecard_id={dynamo_scorecard_id}, score_id={dynamo_score_id}")
            logging.info(json.dumps({
                "message_type": "cache_miss_no_result",
                "report_id": report_id,
                "scorecard_id": scorecard_id,
                "score_id": score_id,
                "item_id": item.id,
                "dynamo_scorecard_id": dynamo_scorecard_id,
                "dynamo_score_id": dynamo_score_id,
                "operation": "no_cached_score_result_found"
            }))
            
            cloudwatch_logger.log_metric(
                metric_name="CacheMiss",
                metric_value=1,
                dimensions={"Environment": os.getenv('environment', 'unknown')}
            )
            
            return None
        
    except Exception as e:
        logging.error(f"Error checking for existing score result: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        logging.error(json.dumps({
            "message_type": "cache_lookup_error",
            "error": str(e),
            "report_id": report_id,
            "scorecard_id": scorecard_id,
            "score_id": score_id
        }))
        cloudwatch_logger.log_metric(
            metric_name="CacheMiss",
            metric_value=1,
            dimensions={"Environment": os.getenv('environment', 'unknown')}
        )
        return None