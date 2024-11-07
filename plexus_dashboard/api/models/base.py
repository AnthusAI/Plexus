"""
Base Model - Foundation for all API model classes.

This abstract base class provides common functionality for all model classes,
establishing a consistent pattern for:
- GraphQL field definition
- Object instantiation from API responses
- ID-based record retrieval
- Client association

Each model class (Account, Experiment, etc.) inherits from this base,
ensuring consistent behavior across the API interface.
"""

from typing import Optional, Dict, Any, ClassVar, Type, TypeVar
from dataclasses import dataclass
from ..client import PlexusAPIClient

T = TypeVar('T', bound='BaseModel')

class BaseModel:
    def __init__(self, id: str, client: Optional[PlexusAPIClient] = None):
        self.id = id
        self._client = client
    
    @classmethod
    def get_by_id(cls: Type[T], id: str, client: PlexusAPIClient) -> T:
        query = f"""
        query Get{cls.__name__}($id: ID!) {{
            get{cls.__name__}(id: $id) {{
                {cls.fields()}
            }}
        }}
        """
        result = client.execute(query, {'id': id})
        return cls.from_dict(result[f'get{cls.__name__}'], client)
    
    @classmethod
    def fields(cls) -> str:
        """Return the GraphQL fields to query for this model"""
        raise NotImplementedError
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any], client: PlexusAPIClient) -> T:
        """Create an instance from a dictionary of data"""
        raise NotImplementedError