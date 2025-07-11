"""Memoized versions of identifier resolvers to reduce API calls."""
from functools import lru_cache
from typing import Optional, Dict, List
from plexus.cli.console import console
from plexus.cli.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier, resolve_item_identifier

# Cache for scorecard lookups
_scorecard_cache: Dict[str, str] = {}
# Cache for score lookups within scorecards
_score_cache: Dict[str, Dict[str, str]] = {}
# Cache for item lookups within accounts
_item_cache: Dict[str, Dict[str, str]] = {}

def memoized_resolve_scorecard_identifier(client, identifier: str) -> Optional[str]:
    """Memoized version of resolve_scorecard_identifier.
    
    Args:
        client: The API client
        identifier: The identifier to resolve
        
    Returns:
        The scorecard ID if found, None otherwise
    """
    # Check cache first
    if identifier in _scorecard_cache:
        return _scorecard_cache[identifier]
    
    # If not in cache, resolve and cache the result
    result = resolve_scorecard_identifier(client, identifier)
    if result:
        _scorecard_cache[identifier] = result
    return result

def memoized_resolve_score_identifier(client, scorecard_id: str, identifier: str) -> Optional[str]:
    """Memoized version of resolve_score_identifier.
    
    Args:
        client: The API client
        scorecard_id: The ID of the scorecard containing the score
        identifier: The identifier to resolve
        
    Returns:
        The score ID if found, None otherwise
    """
    # Check cache first
    if scorecard_id in _score_cache and identifier in _score_cache[scorecard_id]:
        return _score_cache[scorecard_id][identifier]
    
    # If not in cache, resolve and cache the result
    result = resolve_score_identifier(client, scorecard_id, identifier)
    if result:
        if scorecard_id not in _score_cache:
            _score_cache[scorecard_id] = {}
        _score_cache[scorecard_id][identifier] = result
    return result

def memoized_resolve_item_identifier(client, identifier: str, account_id: str = None) -> Optional[str]:
    """Memoized version of resolve_item_identifier.
    
    Args:
        client: The API client
        identifier: The identifier to resolve
        account_id: Optional account ID to limit search scope
        
    Returns:
        The item ID if found, None otherwise
    """
    # Use account_id as part of cache key to avoid cross-account confusion
    cache_key = f"{account_id or 'default'}:{identifier}"
    
    # Check cache first
    account_cache_key = account_id or 'default'
    if account_cache_key in _item_cache and identifier in _item_cache[account_cache_key]:
        return _item_cache[account_cache_key][identifier]
    
    # If not in cache, resolve and cache the result
    result = resolve_item_identifier(client, identifier, account_id)
    if result:
        if account_cache_key not in _item_cache:
            _item_cache[account_cache_key] = {}
        _item_cache[account_cache_key][identifier] = result
    return result

def clear_resolver_caches():
    """Clear all resolver caches."""
    global _scorecard_cache, _score_cache, _item_cache
    _scorecard_cache.clear()
    _score_cache.clear()
    _item_cache.clear() 