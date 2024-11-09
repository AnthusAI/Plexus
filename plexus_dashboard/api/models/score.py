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
        client: Optional[_BaseAPIClient] = None
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
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Score':
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