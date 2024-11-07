"""
Score Model - Python representation of the GraphQL Score type.

Provides lookup methods to find scores by:
- ID (direct lookup)
- Name (using filter)
- Key (constructed from name and version)

Each score belongs to a scorecard section and can be associated with experiments.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .base import BaseModel
from ..client import PlexusAPIClient

logger = logging.getLogger(__name__)

@dataclass
class Score(BaseModel):
    name: str
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
        client: Optional[PlexusAPIClient] = None
    ):
        super().__init__(id, client)
        self.name = name
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
    def from_dict(cls, data: Dict[str, Any], client: PlexusAPIClient) -> 'Score':
        return cls(
            id=data['id'],
            name=data['name'],
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
    def get_by_name(cls, name: str, client: PlexusAPIClient) -> 'Score':
        logger.debug(f"Looking up score by name: {name}")
        query = """
        query GetScoreByName($name: String!) {
            listScores(filter: {name: {eq: $name}}) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'name': name})
        items = result['listScores']['items']
        if not items:
            raise ValueError(f"No score found with name: {name}")
        logger.debug(f"Found score: {items[0]['name']} ({items[0]['id']})")
        return cls.from_dict(items[0], client) 