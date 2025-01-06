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
from ..client import _BaseAPIClient

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
        client: Optional[_BaseAPIClient] = None
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
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Scorecard':
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
    def get_by_key(cls, key: str, client: _BaseAPIClient) -> 'Scorecard':
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
    def create(
        cls,
        client: _BaseAPIClient,
        name: str,
        key: str,
        externalId: str,
        accountId: str,
        description: Optional[str] = None
    ) -> 'Scorecard':
        """Create a new scorecard.
        
        Args:
            client: The API client
            name: Name of the scorecard
            key: Unique key identifier
            externalId: External ID (usually from YAML)
            accountId: ID of the account this scorecard belongs to
            description: Optional description
            
        Returns:
            The created Scorecard instance
        """
        logger.debug(f"Creating scorecard: {name} ({key})")
        
        input_data = {
            'name': name,
            'key': key,
            'externalId': externalId,
            'accountId': accountId
        }
        if description is not None:
            input_data['description'] = description
            
        mutation = """
        mutation CreateScorecard($input: CreateScorecardInput!) {
            createScorecard(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createScorecard'], client)

    @classmethod
    def get_by_name(cls, name: str, client: _BaseAPIClient) -> 'Scorecard':
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

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'Scorecard':
        logger.debug(f"Looking up scorecard by ID: {id}")
        query = """
        query GetScorecardById($id: ID!) {
            getScorecard(id: $id) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'id': id})
        if not result.get('getScorecard'):
            raise ValueError(f"No scorecard found with ID: {id}")
        logger.debug(f"Found scorecard: {result['getScorecard']['name']}")
        return cls.from_dict(result['getScorecard'], client)

    @classmethod
    def get_by_external_id(cls, external_id: str, client: _BaseAPIClient) -> 'Scorecard':
        logger.debug(f"Looking up scorecard by external ID: {external_id}")
        query = """
        query GetScorecardByExternalId($externalId: String!) {
            listScorecards(filter: {externalId: {eq: $externalId}}) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'externalId': external_id})
        items = result['listScorecards']['items']
        if not items:
            raise ValueError(f"No scorecard found with external ID: {external_id}")
        logger.debug(f"Found scorecard: {items[0]['name']} ({items[0]['id']})")
        return cls.from_dict(items[0], client)
  