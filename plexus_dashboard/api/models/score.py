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
        """Get a score by its name within a scorecard"""
        # First get all sections for this scorecard
        sections_query = """
        query GetScorecardSections($scorecardId: String!) {
            listScorecardSections(filter: { scorecardId: { eq: $scorecardId } }) {
                items {
                    id
                    scores {
                        items {
                            %s
                        }
                    }
                }
            }
        }
        """ % cls.fields()
        
        sections_result = client.execute(sections_query, {'scorecardId': scorecard_id})
        if not sections_result or 'listScorecardSections' not in sections_result:
            return None
            
        # Look through all sections for a score with matching name
        for section in sections_result['listScorecardSections']['items']:
            if section.get('scores', {}).get('items'):
                for score in section['scores']['items']:
                    if score.get('name') == name:
                        return cls.from_dict(score, client)
        
        return None

    @classmethod
    def get_by_key(cls, key: str, scorecard_id: str, client: _BaseAPIClient) -> Optional['Score']:
        """Get a score by its key within a scorecard"""
        sections_query = """
        query GetScorecardSections($scorecardId: String!) {
            listScorecardSections(filter: { scorecardId: { eq: $scorecardId } }) {
                items {
                    id
                    scores {
                        items {
                            %s
                        }
                    }
                }
            }
        }
        """ % cls.fields()
        
        sections_result = client.execute(sections_query, {'scorecardId': scorecard_id})
        if not sections_result or 'listScorecardSections' not in sections_result:
            return None
            
        for section in sections_result['listScorecardSections']['items']:
            if section.get('scores', {}).get('items'):
                for score in section['scores']['items']:
                    if score.get('key') == key:
                        return cls.from_dict(score, client)
        return None

    @classmethod
    def get_by_external_id(cls, external_id: str, scorecard_id: str, 
                          client: _BaseAPIClient) -> Optional['Score']:
        """Get a score by its external ID within a scorecard"""
        sections_query = """
        query GetScorecardSections($scorecardId: String!) {
            listScorecardSections(filter: { scorecardId: { eq: $scorecardId } }) {
                items {
                    id
                    scores {
                        items {
                            %s
                        }
                    }
                }
            }
        }
        """ % cls.fields()
        
        sections_result = client.execute(sections_query, {'scorecardId': scorecard_id})
        if not sections_result or 'listScorecardSections' not in sections_result:
            return None
            
        for section in sections_result['listScorecardSections']['items']:
            if section.get('scores', {}).get('items'):
                for score in section['scores']['items']:
                    if score.get('externalId') == external_id:
                        return cls.from_dict(score, client)
        return None