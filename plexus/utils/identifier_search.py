"""
Identifier Search Utilities - High-level functions for finding items by identifier values.

This module provides convenient functions for exact-match identifier searches,
building on the low-level Identifier model to provide common use cases.

Key Functions:
- find_item_by_identifier: Find a single item by exact identifier value
- find_items_by_identifier_type: Find all items with identifiers of a specific type
- batch_find_items_by_identifiers: Efficiently find multiple items by identifier values

Performance Characteristics:
- All functions use O(1) exact-match GSI lookups, not scans
- Account-scoped for security and performance
- Efficient batch operations for bulk lookups
- No cross-account data leakage

Usage Examples:
    from plexus.utils.identifier_search import find_item_by_identifier
    from plexus.dashboard.api.client import 'PlexusDashboardClient'
    
    client = 'PlexusDashboardClient'.for_account("my-account")
    
    # Find single item by exact identifier value
    item = find_item_by_identifier("CUST-123456", "my-account", client)
    if item:
        print(f"Found item: {item.id}")
    
    # Find all items with "Customer ID" identifiers
    items = find_items_by_identifier_type("Customer ID", "my-account", client)
    
    # Batch lookup multiple items
    items_dict = batch_find_items_by_identifiers(
        ["CUST-123456", "ORD-789012"], "my-account", client
    )
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from plexus.dashboard.api.models import Identifier, Item

if TYPE_CHECKING:
    from plexus.dashboard.api.client import PlexusDashboardClient


def find_item_by_identifier(
    identifier_value: str, 
    account_id: str, 
    client: 'PlexusDashboardClient'
) -> Optional[Item]:
    """
    Find an item by exact identifier value within an account.
    
    This is the primary search function for exact-match lookups.
    Uses O(1) GSI lookup for consistent performance.
    
    Args:
        identifier_value: Exact value to search for (e.g., "CUST-123456")
        account_id: Account to search within
        client: API client
        
    Returns:
        Item object if found, None if not found
        
    Example:
        item = find_item_by_identifier("CUST-123456", "account123", client)
        if item:
            print(f"Found item {item.id} with data: {item.data}")
    """
    identifier = Identifier.find_by_value(identifier_value, account_id, client)
    if not identifier:
        return None
        
    try:
        return Item.get_by_id(identifier.itemId, client)
    except ValueError:
        # Item was deleted but identifier remains - clean up orphaned identifier
        identifier.delete()
        return None


def find_items_by_identifier_type(
    identifier_name: str,
    account_id: str, 
    client: 'PlexusDashboardClient',
    limit: Optional[int] = None
) -> List[Item]:
    """
    Find all items that have identifiers of a specific type.
    
    Args:
        identifier_name: Name of identifier type (e.g., "Customer ID", "Order ID")
        account_id: Account to search within
        client: API client
        limit: Optional limit on number of results
        
    Returns:
        List of Item objects that have identifiers of the specified type
        
    Example:
        # Find all items with "Customer ID" identifiers
        items = find_items_by_identifier_type("Customer ID", "account123", client)
        for item in items:
            print(f"Item {item.id} has customer identifier")
    """
    # Query for all identifiers of this type in the account
    query = """
    query FindIdentifiersByType($accountId: String!, $name: String!, $limit: Int) {
        listIdentifiers(
            filter: {
                accountId: {eq: $accountId}
                name: {eq: $name}
            }
            limit: $limit
        ) {
            items {
                %s
            }
        }
    }
    """ % Identifier.fields()
    
    variables = {
        'accountId': account_id,
        'name': identifier_name
    }
    if limit:
        variables['limit'] = limit
    
    result = client.execute(query, variables)
    
    identifier_items = result.get('listIdentifiers', {}).get('items', [])
    
    # Get unique item IDs
    item_ids = list(set(item['itemId'] for item in identifier_items))
    
    # Fetch all items
    items = []
    for item_id in item_ids:
        try:
            item = Item.get_by_id(item_id, client)
            items.append(item)
        except ValueError:
            # Item was deleted but identifier remains - skip
            continue
            
    return items


def batch_find_items_by_identifiers(
    identifier_values: List[str],
    account_id: str,
    client: 'PlexusDashboardClient'
) -> Dict[str, Item]:
    """
    Efficiently find multiple items by their identifier values.
    
    Uses batch lookup for optimal performance when searching for many items.
    
    Args:
        identifier_values: List of exact values to search for
        account_id: Account to search within
        client: API client
        
    Returns:
        Dictionary mapping identifier_value -> Item for found items.
        Missing identifier values will not appear in the result.
        
    Example:
        items_dict = batch_find_items_by_identifiers(
            ["CUST-123456", "ORD-789012", "TICKET-555"], 
            "account123", 
            client
        )
        
        for value, item in items_dict.items():
            print(f"Identifier {value} -> Item {item.id}")
            
        # Check if specific identifier was found
        if "CUST-123456" in items_dict:
            customer_item = items_dict["CUST-123456"]
    """
    if not identifier_values:
        return {}
    
    # Batch lookup identifiers
    identifiers_dict = Identifier.batch_find_by_values(
        identifier_values, account_id, client
    )
    
    if not identifiers_dict:
        return {}
    
    # Get unique item IDs
    item_ids = list(set(identifier.itemId for identifier in identifiers_dict.values()))
    
    # Fetch all items
    items_by_id = {}
    for item_id in item_ids:
        try:
            item = Item.get_by_id(item_id, client)
            items_by_id[item_id] = item
        except ValueError:
            # Item was deleted but identifier remains - skip
            continue
    
    # Build final result mapping identifier_value -> Item
    result = {}
    for value, identifier in identifiers_dict.items():
        if identifier.itemId in items_by_id:
            result[value] = items_by_id[identifier.itemId]
    
    return result


def find_item_by_typed_identifier(
    identifier_name: str,
    identifier_value: str,
    account_id: str,
    client: 'PlexusDashboardClient'
) -> Optional[Item]:
    """
    Find an item by identifier name and exact value.
    
    More specific than find_item_by_identifier when you know the identifier type.
    Useful when the same value might exist for different identifier types.
    
    Args:
        identifier_name: Name of identifier type (e.g., "Customer ID")
        identifier_value: Exact value to search for (e.g., "123456")
        account_id: Account to search within
        client: API client
        
    Returns:
        Item object if found, None if not found
        
    Example:
        # Find item with specifically a "Customer ID" of "123456"
        # (ignoring any "Order ID" or other types with same value)
        item = find_item_by_typed_identifier(
            "Customer ID", "123456", "account123", client
        )
    """
    identifier = Identifier.find_by_name_and_value(
        identifier_name, identifier_value, account_id, client
    )
    if not identifier:
        return None
        
    try:
        return Item.get_by_id(identifier.itemId, client)
    except ValueError:
        # Item was deleted but identifier remains - clean up orphaned identifier
        identifier.delete()
        return None


def get_item_identifiers(item_id: str, client: 'PlexusDashboardClient') -> List[Dict[str, Any]]:
    """
    Get all identifiers for a specific item in a format compatible with the UI.
    
    Returns identifiers in the same format as the deprecated JSON field,
    ensuring compatibility with existing UI components.
    
    Args:
        item_id: ID of the item to get identifiers for
        client: API client
        
    Returns:
        List of identifier dictionaries with 'name', 'id' (value), and optional 'url'
        
    Example:
        identifiers = get_item_identifiers("item123", client)
        # Returns: [
        #     {"name": "Customer ID", "id": "CUST-123456", "url": "https://..."},
        #     {"name": "Order ID", "id": "ORD-789012"}
        # ]
    """
    identifier_records = Identifier.list_by_item_id(item_id, client)
    
    # Convert to UI-compatible format
    identifiers = []
    for identifier in identifier_records:
        identifier_dict = {
            'name': identifier.name,
            'id': identifier.value  # UI expects 'id' field for the value
        }
        if identifier.url:
            identifier_dict['url'] = identifier.url
        identifiers.append(identifier_dict)
    
    return identifiers


def create_identifiers_for_item(
    item_id: str,
    account_id: str,
    identifiers_data: List[Dict[str, Any]],
    client: 'PlexusDashboardClient'
) -> List[Identifier]:
    """
    Create identifier records for an item from JSON-style data.
    
    Converts from the old JSON format to separate Identifier records.
    Useful for migration and dual-write scenarios.
    
    Args:
        item_id: ID of the item these identifiers belong to
        account_id: Account ID for data isolation
        identifiers_data: List of identifier dicts in JSON format:
                         [{"name": "Customer ID", "id": "CUST-123", "url": "..."}]
        client: API client
        
    Returns:
        List of created Identifier objects (may be empty if all fail)
        
    Example:
        # Convert from JSON format to Identifier records
        json_identifiers = [
            {"name": "Customer ID", "id": "CUST-123456", "url": "https://..."},
            {"name": "Order ID", "id": "ORD-789012"}
        ]
        
        identifier_records = create_identifiers_for_item(
            "item123", "account123", json_identifiers, client
        )
    """
    if not identifiers_data:
        return []
    
    try:
        # Convert from JSON format (with 'id' field) to Identifier format (with 'value' field)
        normalized_data = []
        for identifier_data in identifiers_data:
            normalized = {
                'name': identifier_data['name'],
                'value': identifier_data.get('id', identifier_data.get('value', ''))
            }
            if 'url' in identifier_data:
                normalized['url'] = identifier_data['url']
            normalized_data.append(normalized)
        
        return Identifier.batch_create_for_item(
            client=client,
            item_id=item_id,
            account_id=account_id,
            identifiers_data=normalized_data
        )
    except Exception as e:
        # Log error but don't propagate to avoid breaking main workflow
        import logging
        logging.error(f"Failed to create identifiers for item {item_id}: {e}")
        logging.error(f"Exception type: {type(e)}")
        import traceback
        logging.error(f"Stack trace: {traceback.format_exc()}")
        logging.error(f"Identifier data that failed: {identifiers_data}")
        return [] 