"""
Base Model - Foundation for all API model classes.

This abstract base class provides common functionality for all model classes,
establishing a consistent pattern for:
- GraphQL field definition
- Object instantiation from API responses
- ID-based record retrieval
- Client association

Each model class (Account, Evaluation, etc.) inherits from this base,
ensuring consistent behavior across the API interface.

Implementation Notes:
    - Uses _BaseAPIClient for GraphQL operations
    - All models support get_by_id lookups
    - Models may implement additional lookup methods (get_by_key, etc.)
    - Models may implement background processing for mutations
    - Some models support batched operations

Example Usage:
    # Direct lookup
    item = SomeModel.get_by_id("123", client)
    
    # Custom lookups (if implemented)
    account = Account.get_by_key("my-account", client)
    
    # Background mutations (if implemented)
    evaluation.update(status="RUNNING")  # Returns immediately
    
    # Batch operations (if implemented)
    ScoreResult.batch_create(client, items)
"""

from typing import Optional, Dict, Any, ClassVar, Type, TypeVar
from dataclasses import dataclass
# Lazy import to avoid circular dependency
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..client import PlexusDashboardClient

T = TypeVar('T', bound='BaseModel')

class BaseModel:
    def __init__(self, id: str, client: Optional['PlexusDashboardClient'] = None):
        self.id = id
        self._client = client
    
    @classmethod
    def get_by_id(cls: Type[T], id: str, client: 'PlexusDashboardClient') -> T:
        query = f"""
        query Get{cls.__name__}($id: ID!) {{
            get{cls.__name__}(id: $id) {{
                {cls.fields()}
            }}
        }}
        """
        result = client.execute(query, {'id': id})
        if not result:
            raise ValueError(f"API returned no result when getting {cls.__name__} with ID {id}")
        
        key = f'get{cls.__name__}'
        if key not in result:
            raise ValueError(f"API response missing {key} when getting {cls.__name__} with ID {id}")
            
        if result[key] is None:
            raise ValueError(f"Could not find {cls.__name__} with ID {id}")
            
        return cls.from_dict(result[f'get{cls.__name__}'], client)
    
    @classmethod
    def fields(cls) -> str:
        """Return the GraphQL fields to query for this model"""
        raise NotImplementedError
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any], client: 'PlexusDashboardClient') -> T:
        """Create an instance from a dictionary of data"""
        raise NotImplementedError