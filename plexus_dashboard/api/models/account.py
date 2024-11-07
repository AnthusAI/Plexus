from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .base import BaseModel
from ..client import PlexusAPIClient

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
        client: Optional[PlexusAPIClient] = None
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
    def from_dict(cls, data: Dict[str, Any], client: PlexusAPIClient) -> 'Account':
        return cls(
            id=data['id'],
            name=data['name'],
            key=data['key'],
            description=data.get('description'),
            client=client
        )
    
    @classmethod
    def get_by_key(cls, key: str, client: PlexusAPIClient) -> 'Account':
        query = """
        query GetAccountByKey($key: String!) {
            listAccounts(filter: {key: {eq: $key}}) {
                items {
                    id
                    name
                    key
                    description
                }
            }
        }
        """
        result = client.execute(query, {'key': key})
        items = result['listAccounts']['items']
        if not items:
            raise ValueError(f"No account found with key: {key}")
        return cls.from_dict(items[0], client)