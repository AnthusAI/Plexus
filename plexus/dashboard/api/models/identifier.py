"""
Identifier Model - API interface for identifier management and exact-match searching.

This model provides the Python API interface for the new Identifier table,
enabling efficient exact-match searches by identifier value within account boundaries.

Key Features:
- O(1) exact-match lookups using GSI byAccountAndValue
- Account-scoped searches for security and performance
- Batch operations for efficient bulk lookups
- Integration with existing Item model via itemId relationship

Usage Examples:
    # Find item by exact identifier value
    identifier = Identifier.find_by_value("CUST-123456", account_id, client)
    if identifier:
        item = Item.get_by_id(identifier.itemId, client)
    
    # Create identifier for an item
    identifier = Identifier.create(
        client=client,
        itemId="item123",
        name="Customer ID", 
        value="CUST-123456",
        accountId="account123",
        url="https://crm.example.com/customers/123456"
    )
    
    # Batch exact-match lookup
    identifiers = Identifier.batch_find_by_values(
        ["CUST-123456", "ORD-789012"], account_id, client
    )

GSI Usage:
    This model leverages the following Global Secondary Indexes:
    - byAccountAndValue: Primary exact-match search (accountId + value)
    - byAccountNameAndValue: Search within identifier type (accountId + name + value)
    - byItemId: Get all identifiers for a specific item
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import PlexusDashboardClient

@dataclass
class Identifier(BaseModel):
    itemId: str
    name: str
    value: str
    accountId: str
    createdAt: datetime
    updatedAt: datetime
    url: Optional[str] = None

    def __init__(
        self,
        id: str,
        itemId: str,
        name: str,
        value: str,
        accountId: str,
        createdAt: datetime,
        updatedAt: datetime,
        url: Optional[str] = None,
        client: Optional[PlexusDashboardClient] = None
    ):
        super().__init__(id, client)
        self.itemId = itemId
        self.name = name
        self.value = value
        self.accountId = accountId
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.url = url

    @classmethod
    def fields(cls) -> str:
        return """
            id
            itemId
            name
            value
            accountId
            createdAt
            updatedAt
            url
        """

    @classmethod
    def create(
        cls, 
        client: PlexusDashboardClient, 
        itemId: str,
        name: str,
        value: str,
        accountId: str,
        url: Optional[str] = None
    ) -> 'Identifier':
        """Create a new identifier record."""
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        input_data = {
            'itemId': itemId,
            'name': name,
            'value': value,
            'accountId': accountId,
            'createdAt': now,
            'updatedAt': now,
        }
        
        if url:
            input_data['url'] = url
        
        mutation = """
        mutation CreateIdentifier($input: CreateIdentifierInput!) {
            createIdentifier(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createIdentifier'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: PlexusDashboardClient) -> 'Identifier':
        """Create an Identifier instance from API response data."""
        for date_field in ['createdAt', 'updatedAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )

        return cls(
            id=data['id'],
            itemId=data.get('itemId', ''),
            name=data.get('name', ''),
            value=data.get('value', ''),
            accountId=data.get('accountId', ''),
            createdAt=data.get('createdAt', datetime.now(timezone.utc)),
            updatedAt=data.get('updatedAt', datetime.now(timezone.utc)),
            url=data.get('url'),
            client=client
        )

    @classmethod
    def find_by_value(
        cls, 
        value: str, 
        account_id: str, 
        client: PlexusDashboardClient
    ) -> Optional['Identifier']:
        """
        Find an identifier by exact value within an account.
        
        Uses the byAccountAndValue GSI for O(1) performance.
        Returns the first matching identifier or None if not found.
        """
        query = """
        query FindIdentifierByValue($accountId: String!, $value: String!) {
            listIdentifiers(filter: {
                accountId: {eq: $accountId}
                value: {eq: $value}
            }) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {
            'accountId': account_id,
            'value': value
        })
        
        items = result.get('listIdentifiers', {}).get('items', [])
        if not items:
            return None
            
        return cls.from_dict(items[0], client)

    @classmethod
    def find_by_name_and_value(
        cls,
        name: str,
        value: str, 
        account_id: str,
        client: PlexusDashboardClient
    ) -> Optional['Identifier']:
        """
        Find an identifier by name and exact value within an account.
        
        Uses the byAccountNameAndValue GSI for efficient lookup within identifier types.
        """
        query = """
        query FindIdentifierByNameAndValue($accountId: String!, $name: String!, $value: String!) {
            listIdentifiers(filter: {
                accountId: {eq: $accountId}
                name: {eq: $name}
                value: {eq: $value}
            }) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {
            'accountId': account_id,
            'name': name,
            'value': value
        })
        
        items = result.get('listIdentifiers', {}).get('items', [])
        if not items:
            return None
            
        return cls.from_dict(items[0], client)

    @classmethod
    def list_by_item_id(
        cls, 
        item_id: str, 
        client: PlexusDashboardClient
    ) -> List['Identifier']:
        """
        Get all identifiers for a specific item.
        
        Uses the byItemId GSI for efficient lookup.
        """
        query = """
        query ListIdentifiersByItemId($itemId: String!) {
            listIdentifiers(filter: {
                itemId: {eq: $itemId}
            }) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'itemId': item_id})
        
        items = result.get('listIdentifiers', {}).get('items', [])
        return [cls.from_dict(item, client) for item in items]

    @classmethod
    def batch_find_by_values(
        cls,
        values: List[str],
        account_id: str,
        client: PlexusDashboardClient
    ) -> Dict[str, 'Identifier']:
        """
        Batch exact-match lookup for multiple identifier values.
        
        Returns a dictionary mapping value -> Identifier for found identifiers.
        Missing values will not appear in the result dictionary.
        
        Args:
            values: List of identifier values to search for
            account_id: Account to search within
            client: API client
            
        Returns:
            Dict mapping found values to their Identifier objects
        """
        if not values:
            return {}
            
        # Create OR conditions for all values
        value_conditions = [f'{{eq: "{value}"}}' for value in values]
        values_filter = f'{{or: [{", ".join(value_conditions)}]}}'
        
        query = f"""
        query BatchFindIdentifiersByValues($accountId: String!) {{
            listIdentifiers(filter: {{
                accountId: {{eq: $accountId}}
                value: {values_filter}
            }}) {{
                items {{
                    {cls.fields()}
                }}
            }}
        }}
        """
        
        result = client.execute(query, {'accountId': account_id})
        
        items = result.get('listIdentifiers', {}).get('items', [])
        
        # Build result dictionary mapping value -> Identifier
        result_dict = {}
        for item_data in items:
            identifier = cls.from_dict(item_data, client)
            result_dict[identifier.value] = identifier
            
        return result_dict

    @classmethod
    def batch_create_for_item(
        cls,
        client: PlexusDashboardClient,
        item_id: str,
        account_id: str,
        identifiers_data: List[Dict[str, Any]]
    ) -> List['Identifier']:
        """
        Create multiple identifiers for an item in a single operation.
        
        Args:
            client: API client
            item_id: ID of the item these identifiers belong to
            account_id: Account ID for data isolation
            identifiers_data: List of identifier data dicts with 'name', 'value', and optional 'url'
            
        Returns:
            List of created Identifier objects (may be fewer than input if some failed)
        """
        if not identifiers_data:
            return []
            
        created_identifiers = []
        for identifier_data in identifiers_data:
            try:
                identifier = cls.create(
                    client=client,
                    itemId=item_id,
                    accountId=account_id,
                    name=identifier_data['name'],
                    value=identifier_data['value'],
                    url=identifier_data.get('url')
                )
                created_identifiers.append(identifier)
            except Exception as e:
                # Log the error but continue with other identifiers
                import logging
                logging.error(f"Failed to create identifier {identifier_data['name']}={identifier_data['value']} for item {item_id}: {e}")
                logging.error(f"Exception type: {type(e)}")
                import traceback
                logging.error(f"Stack trace: {traceback.format_exc()}")
                # Continue processing other identifiers
                continue
            
        return created_identifiers

    def update(self, **kwargs) -> 'Identifier':
        """Update this identifier with new values."""
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified after creation")
        if 'id' in kwargs:
            raise ValueError("id cannot be modified after creation")
        if 'itemId' in kwargs:
            raise ValueError("itemId cannot be modified after creation")
        if 'accountId' in kwargs:
            raise ValueError("accountId cannot be modified after creation")
            
        update_data = {
            'updatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            **kwargs
        }
        
        mutation = """
        mutation UpdateIdentifier($input: UpdateIdentifierInput!) {
            updateIdentifier(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        variables = {
            'input': {
                'id': self.id,
                **update_data
            }
        }
        
        result = self._client.execute(mutation, variables)
        return self.from_dict(result['updateIdentifier'], self._client)

    def delete(self) -> bool:
        """Delete this identifier."""
        mutation = """
        mutation DeleteIdentifier($input: DeleteIdentifierInput!) {
            deleteIdentifier(input: $input) {
                id
            }
        }
        """
        
        variables = {'input': {'id': self.id}}
        
        try:
            self._client.execute(mutation, variables)
            return True
        except Exception:
            return False 