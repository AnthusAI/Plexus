"""Direct memoized versions of identifier resolvers that don't use context managers."""

from typing import Optional, Dict
from plexus.cli.direct_identifier_resolution import direct_resolve_scorecard_identifier, direct_resolve_score_identifier
from plexus.CustomLogging import logging

# Cache for scorecard lookups
_scorecard_cache: Dict[str, str] = {}
# Cache for score lookups within scorecards
_score_cache: Dict[str, Dict[str, str]] = {}

def direct_memoized_resolve_scorecard_identifier(client, identifier: str) -> Optional[str]:
    """Memoized version of resolve_scorecard_identifier that doesn't require a context manager."""
    if not identifier:
        return None
        
    # Check cache first
    if identifier in _scorecard_cache:
        logging.debug(f"Cache HIT for scorecard identifier: {identifier}")
        return _scorecard_cache[identifier]
    
    logging.debug(f"Cache MISS for scorecard identifier: {identifier}")
    
    # If not in cache, resolve and cache the result
    result = None
    try:
        # Try fetching by ID first
        query = """
        query GetScorecard($id: ID!) {
            getScorecard(id: $id) {
                id
            }
        }
        """
        try:
            response = client.execute(query, {"id": identifier})
            if response and response.get("getScorecard"):
                result = identifier
        except Exception:
            pass  # Not an ID, try other identifiers
            
        if not result:
            # Try by key
            query = """
            query ListScorecardByKey($key: String!) {
                listScorecardByKey(key: $key) {
                    items {
                        id
                    }
                }
            }
            """
            try:
                response = client.execute(query, {"key": identifier})
                if response and response.get("listScorecardByKey", {}).get("items"):
                    scorecard_items = response["listScorecardByKey"]["items"]
                    if scorecard_items:
                        result = scorecard_items[0]["id"]
            except Exception:
                pass  # Not a key, try other identifiers
                
        if not result:
            # Try by name (case insensitive)
            query = """
            query ListScorecards($filter: ModelScorecardFilterInput) {
                listScorecards(filter: $filter) {
                    items {
                        id
                        name
                    }
                }
            }
            """
            try:
                # Use a filter that does case-insensitive name comparison
                filter_input = {
                    "name": {"eq": identifier}
                }
                response = client.execute(query, {"filter": filter_input})
                if response and response.get("listScorecards", {}).get("items"):
                    scorecard_items = response["listScorecards"]["items"]
                    if scorecard_items:
                        result = scorecard_items[0]["id"]
            except Exception:
                pass  # Not a name, try other identifiers
                
        if not result:
            # Try by external ID
            query = """
            query ListScorecards($filter: ModelScorecardFilterInput) {
                listScorecards(filter: $filter) {
                    items {
                        id
                        externalId
                    }
                }
            }
            """
            try:
                # Try as string first
                filter_input = {
                    "externalId": {"eq": identifier}
                }
                response = client.execute(query, {"filter": filter_input})
                if not response or not response.get("listScorecards", {}).get("items"):
                    # Try as number if string fails
                    try:
                        numeric_id = int(identifier)
                        filter_input = {
                            "externalId": {"eq": numeric_id}
                        }
                        response = client.execute(query, {"filter": filter_input})
                    except (ValueError, TypeError):
                        pass  # Not a valid number
                        
                if response and response.get("listScorecards", {}).get("items"):
                    scorecard_items = response["listScorecards"]["items"]
                    if scorecard_items:
                        result = scorecard_items[0]["id"]
            except Exception:
                pass  # Not an external ID either
    except Exception as e:
        logging.error(f"Error resolving scorecard identifier '{identifier}': {str(e)}")
        return None
    
    if result:
        # Cache the successful result
        _scorecard_cache[identifier] = result
        logging.debug(f"Resolved scorecard identifier '{identifier}' to ID: {result}")
        return result
    else:
        logging.error(f"Could not resolve scorecard identifier: {identifier}")
        error_hint = f"\nPlease check that '{identifier}' is a valid scorecard ID, key, name, or external ID."
        error_hint += "\nIf using a local scorecard, add the --yaml flag to load from YAML files."
        logging.error(error_hint)
        return None

def direct_memoized_resolve_score_identifier(client, scorecard_id: str, identifier: str) -> Optional[str]:
    """Memoized version of direct_resolve_score_identifier.
    
    Args:
        client: The API client
        scorecard_id: The ID of the scorecard containing the score
        identifier: The identifier to resolve
        
    Returns:
        The score ID if found, None otherwise
    """
    # Check cache first
    if scorecard_id in _score_cache and identifier in _score_cache[scorecard_id]:
        logging.debug(f"Cache HIT for score identifier: {identifier} in scorecard: {scorecard_id}")
        return _score_cache[scorecard_id][identifier]
    
    # If not in cache, resolve and cache the result
    logging.debug(f"Cache MISS for score identifier: {identifier} in scorecard: {scorecard_id}")
    result = direct_resolve_score_identifier(client, scorecard_id, identifier)
    if result:
        if scorecard_id not in _score_cache:
            _score_cache[scorecard_id] = {}
        logging.debug(f"Caching score identifier: {identifier} -> {result} in scorecard: {scorecard_id}")
        _score_cache[scorecard_id][identifier] = result
    return result

def clear_direct_resolver_caches():
    """Clear all resolver caches."""
    logging.debug("Clearing all direct resolver caches")
    _scorecard_cache.clear()
    _score_cache.clear() 