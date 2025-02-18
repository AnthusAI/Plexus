"""
Score Model - Python representation of the GraphQL Score type.

Represents a scoring method within a scorecard section, tracking:
- Configuration and metadata
- AI model details
- Performance metrics
- Version history
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .base import BaseModel
from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class Score(BaseModel):
    name: str
    key: str
    externalId: str
    type: str
    order: int
    sectionId: str
    accuracy: Optional[float] = None
    version: Optional[str] = None
    aiProvider: Optional[str] = None
    aiModel: Optional[str] = None
    isFineTuned: Optional[bool] = None
    configuration: Optional[Dict] = None
    distribution: Optional[Dict] = None
    versionHistory: Optional[Dict] = None

    def __init__(
        self,
        id: str,
        name: str,
        key: str,
        externalId: str,
        type: str,
        order: int,
        sectionId: str,
        accuracy: Optional[float] = None,
        version: Optional[str] = None,
        aiProvider: Optional[str] = None,
        aiModel: Optional[str] = None,
        isFineTuned: Optional[bool] = None,
        configuration: Optional[Dict] = None,
        distribution: Optional[Dict] = None,
        versionHistory: Optional[Dict] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.name = name
        self.key = key
        self.externalId = externalId
        self.type = type
        self.order = order
        self.sectionId = sectionId
        self.accuracy = accuracy
        self.version = version
        self.aiProvider = aiProvider
        self.aiModel = aiModel
        self.isFineTuned = isFineTuned
        self.configuration = configuration
        self.distribution = distribution
        self.versionHistory = versionHistory

    @classmethod
    def fields(cls) -> str:
        return """
            id
            name
            key
            externalId
            type
            order
            sectionId
            accuracy
            version
            aiProvider
            aiModel
            isFineTuned
            configuration
            distribution
            versionHistory
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Score':
        return cls(
            id=data['id'],
            name=data['name'],
            key=data['key'],
            externalId=data['externalId'],
            type=data['type'],
            order=data['order'],
            sectionId=data['sectionId'],
            accuracy=data.get('accuracy'),
            version=data.get('version'),
            aiProvider=data.get('aiProvider'),
            aiModel=data.get('aiModel'),
            isFineTuned=data.get('isFineTuned'),
            configuration=data.get('configuration'),
            distribution=data.get('distribution'),
            versionHistory=data.get('versionHistory'),
            client=client
        )

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'Score':
        query = """
        query GetScore($id: ID!) {
            getScore(id: $id) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'id': id})
        if not result or 'getScore' not in result:
            raise Exception(f"Failed to get Score {id}")
            
        return cls.from_dict(result['getScore'], client)

    @classmethod
    def get_by_name(cls, name: str, scorecard_id: str, client: _BaseAPIClient) -> Optional['Score']:
        """Get a score by its name"""
        query = """
        query GetScoreByName($name: String!) {
            listScoreByName(name: $name) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'name': name})
        if not result or 'listScoreByName' not in result or not result['listScoreByName']['items']:
            return None
            
        return cls.from_dict(result['listScoreByName']['items'][0], client)

    @classmethod
    def get_by_key(cls, key: str, scorecard_id: str, client: _BaseAPIClient) -> Optional['Score']:
        """Get a score by its key"""
        query = """
        query GetScoreByKey($key: String!) {
            listScoreByKey(key: $key) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'key': key})
        if not result or 'listScoreByKey' not in result or not result['listScoreByKey']['items']:
            return None
            
        return cls.from_dict(result['listScoreByKey']['items'][0], client)

    @classmethod
    def get_by_external_id(cls, external_id: str, scorecard_id: str, 
                          client: _BaseAPIClient) -> Optional['Score']:
        """Get a score by its external ID"""
        query = """
        query GetScoreByExternalId($externalId: String!) {
            listScoreByExternalId(externalId: $externalId) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'externalId': external_id})
        if not result or 'listScoreByExternalId' not in result or not result['listScoreByExternalId']['items']:
            return None
            
        return cls.from_dict(result['listScoreByExternalId']['items'][0], client)

    @classmethod
    def list_by_section_id(cls, section_id: str, client: _BaseAPIClient, 
                          next_token: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """
        Get all scores for a section with pagination support
        
        Returns:
            Dict containing:
                - items: List of Score objects
                - nextToken: Token for next page if more results exist
        """
        query = """
        query ListScoresBySectionId($sectionId: String!, $limit: Int, $nextToken: String) {
            listScoreBySectionId(sectionId: $sectionId, limit: $limit, nextToken: $nextToken) {
                items {
                    %s
                }
                nextToken
            }
        }
        """ % cls.fields()
        
        variables = {
            'sectionId': section_id,
            'limit': limit
        }
        if next_token:
            variables['nextToken'] = next_token
            
        result = client.execute(query, variables)
        if not result or 'listScoreBySectionId' not in result:
            return {'items': [], 'nextToken': None}
            
        list_result = result['listScoreBySectionId']
        return {
            'items': [cls.from_dict(item, client) for item in list_result['items']],
            'nextToken': list_result.get('nextToken')
        }