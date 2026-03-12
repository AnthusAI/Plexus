"""
Account Model - Python representation of the GraphQL Account type.

Provides lookup methods to find accounts by:
- ID (direct lookup)
- Key (using secondary index)
- Name (using filter)
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
from .base import BaseModel

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

@dataclass
class Account(BaseModel):
    """Account model for interacting with the API."""
    name: str
    key: str
    description: Optional[str] = None
    settings: Optional[Dict] = None

    def __init__(
        self,
        id: str,
        name: str,
        key: str,
        description: Optional[str] = None,
        settings: Optional[Dict] = None,
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.name = name
        self.key = key
        self.description = description
        self.settings = settings

    @classmethod
    def fields(cls) -> str:
        return """
            id
            name
            key
            description
            settings
            createdAt
            updatedAt
        """

    @classmethod
    def get_by_key(cls, key: str, client: '_BaseAPIClient') -> Optional['Account']:
        """Get an account by its key.
        
        Args:
            key: The account key to look up
            client: The API client instance
            
        Returns:
            Account: The found account or None
        """
        query = """
        query ListAccountByKey($key: String!) {
            listAccountByKey(key: $key) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'key': key})
        items = result.get('listAccountByKey', {}).get('items', [])
        
        if not items:
            return None
            
        return cls.from_dict(items[0], client)

    @classmethod
    def list_by_key(cls, client: '_BaseAPIClient', key: str) -> Optional['Account']:
        """Get an account by its key.
        
        Args:
            client: The API client instance
            key: The account key to look up
            
        Returns:
            Account: The found account or None
        """
        return cls.get_by_key(key, client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'Account':
        """Create an Account instance from a dictionary."""
        # Convert datetime fields if present
        for date_field in ['createdAt', 'updatedAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )
        
        return cls(
            id=data['id'],
            name=data['name'],
            key=data['key'],
            description=data.get('description'),
            settings=data.get('settings'),
            client=client
        )

    @classmethod
    def get_by_id(cls, id: str, client: '_BaseAPIClient') -> 'Account':
        """Get an account by its ID."""
        query = """
        query GetAccount($id: ID!) {
            getAccount(id: $id) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'id': id})
        if not result or 'getAccount' not in result:
            raise ValueError(f"Failed to get Account {id}")

        return cls.from_dict(result['getAccount'], client)

    def update(self, **kwargs) -> 'Account':
        """Update the account."""
        mutation = """
        mutation UpdateAccount($input: UpdateAccountInput!) {
            updateAccount(input: $input) {
                %s
            }
        }
        """ % self.fields()

        input_data = {
            'id': self.id,
            **kwargs
        }

        result = self._client.execute(mutation, {'input': input_data})
        return self.from_dict(result['updateAccount'], self._client)