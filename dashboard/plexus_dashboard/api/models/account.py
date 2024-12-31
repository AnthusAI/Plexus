"""
Account Model - Python representation of the GraphQL Account type.

Provides lookup methods to find accounts by:
- ID (direct lookup)
- Key (using secondary index)
- Name (using filter)
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from .base import BaseModel
from ..client import _BaseAPIClient

@dataclass
class Account(BaseModel):
    name: str
    key: str
    description: Optional[str] = None

    def __init__(
        self,
        id: str,
        name: str,
        key: str,
        description: Optional[str] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.name = name
        self.key = key
        self.description = description

    @classmethod
    def fields(cls) -> str:
        return """
            id
            name
            key
            description
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Account':
        return cls(
            id=data['id'],
            name=data['name'],
            key=data['key'],
            description=data.get('description'),
            client=client
        )

    @classmethod
    def get_by_key(cls, key: str, client: _BaseAPIClient) -> 'Account':
        query = """
        query GetAccountByKey($key: String!) {
            listAccounts(filter: {key: {eq: $key}}) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'key': key})
        items = result['listAccounts']['items']
        if not items:
            raise ValueError(f"No account found with key: {key}")
        return cls.from_dict(items[0], client)