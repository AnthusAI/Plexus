"""
Scorecard Model - Python representation of the GraphQL Scorecard type.

Provides lookup methods to find scorecards by:
- ID (direct lookup)
- Key (using secondary index)
- Name (using filter)

Each scorecard belongs to an account and contains sections with scores.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .base import BaseModel
from ..client import PlexusAPIClient

logger = logging.getLogger(__name__)

@dataclass
class Scorecard(BaseModel):
    name: str
    key: str
    externalId: str
    accountId: str
    description: Optional[str] = None

    def __init__(
        self,
        id: str,
        name: str,
        key: str,
        externalId: str,
        accountId: str,
        description: Optional[str] = None,
        client: Optional[PlexusAPIClient] = None
    ):
        super().__init__(id, client)
        self.name = name
        self.key = key
        self.externalId = externalId
        self.accountId = accountId
        self.description = description

    @classmethod
    def fields(cls) -> str:
        return """
            id
            name
            key
            externalId
            accountId
            description
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: PlexusAPIClient) -> 'Scorecard':
        return cls(
            id=data['id'],
            name=data['name'],
            key=data['key'],
            externalId=data['externalId'],
            accountId=data['accountId'],
            description=data.get('description'),
            client=client
        )

    @classmethod
    def get_by_key(cls, key: str, client: PlexusAPIClient) -> 'Scorecard':
        logger.debug(f"Looking up scorecard by key: {key}")
        query = """
        query GetScorecardByKey($key: String!) {
            listScorecards(filter: {key: {eq: $key}}) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'key': key})
        items = result['listScorecards']['items']
        if not items:
            raise ValueError(f"No scorecard found with key: {key}")
        logger.debug(f"Found scorecard: {items[0]['name']} ({items[0]['id']})")
        return cls.from_dict(items[0], client)

    @classmethod
    def get_by_name(cls, name: str, client: PlexusAPIClient) -> 'Scorecard':
        logger.debug(f"Looking up scorecard by name: {name}")
        query = """
        query GetScorecardByName($name: String!) {
            listScorecards(filter: {name: {eq: $name}}) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'name': name})
        items = result['listScorecards']['items']
        if not items:
            raise ValueError(f"No scorecard found with name: {name}")
        logger.debug(f"Found scorecard: {items[0]['name']} ({items[0]['id']})")
        return cls.from_dict(items[0], client) 