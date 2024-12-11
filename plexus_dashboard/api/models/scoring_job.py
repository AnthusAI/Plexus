from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient
import json
import logging

@dataclass
class ScoringJob(BaseModel):
    accountId: str
    status: str
    createdAt: datetime
    updatedAt: datetime
    scorecardId: str
    itemId: str
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    errorMessage: Optional[str] = None
    errorDetails: Optional[Dict] = None
    metadata: Optional[Dict] = None
    evaluationId: Optional[str] = None
    scoreId: Optional[str] = None

    def __init__(
        self,
        id: str,
        accountId: str,
        status: str,
        createdAt: datetime,
        updatedAt: datetime,
        scorecardId: str,
        itemId: str,
        startedAt: Optional[datetime] = None,
        completedAt: Optional[datetime] = None,
        errorMessage: Optional[str] = None,
        errorDetails: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        evaluationId: Optional[str] = None,
        scoreId: Optional[str] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.scorecardId = scorecardId
        self.itemId = itemId
        self.startedAt = startedAt
        self.completedAt = completedAt
        self.errorMessage = errorMessage
        self.errorDetails = errorDetails
        self.metadata = metadata
        self.evaluationId = evaluationId
        self.scoreId = scoreId

    @classmethod
    def fields(cls) -> str:
        return """
            id
            accountId
            status
            createdAt
            updatedAt
            scorecardId
            itemId
            startedAt
            completedAt
            errorMessage
            errorDetails
            metadata
            evaluationId
            scoreId
        """

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        accountId: str,
        scorecardId: str,
        itemId: str,
        parameters: Dict,
        **kwargs
    ) -> 'ScoringJob':
        # Build input data with only fields defined in the GraphQL schema
        input_data = {
            'accountId': accountId,
            'scorecardId': scorecardId,
            'itemId': itemId,
            'status': kwargs.pop('status', 'PENDING'),
        }
        
        # Add optional fields that are in the schema
        allowed_fields = {
            'scoreId',
            'evaluationId',
            'metadata',
            'errorMessage',
            'errorDetails',
            'startedAt',
            'completedAt'
        }
        
        for field in allowed_fields:
            if field in kwargs:
                if field == 'metadata' and kwargs[field]:
                    try:
                        # Ensure metadata is JSON serialized
                        input_data['metadata'] = json.dumps(kwargs[field])
                        logging.info(f"Added metadata: {input_data['metadata']}")
                    except Exception as e:
                        logging.error(f"Failed to serialize metadata: {e}")
                else:
                    input_data[field] = kwargs[field]
        
        logging.info(f"Final input data for GraphQL mutation: {input_data}")
        
        mutation = """
        mutation CreateScoringJob($input: CreateScoringJobInput!) {
            createScoringJob(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        try:
            result = client.execute(mutation, {'input': input_data})
            return cls.from_dict(result['createScoringJob'], client)
        except Exception as e:
            logging.error(f"GraphQL mutation failed with input data: {input_data}")
            logging.error(f"Error: {str(e)}")
            raise

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'ScoringJob':
        for date_field in ['createdAt', 'updatedAt', 'startedAt', 'completedAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )
        
        if data.get('metadata'):
            try:
                data['metadata'] = json.loads(data['metadata'])
                logging.info(f"Parsed metadata from JSON: {data['metadata']}")
            except Exception as e:
                logging.error(f"Failed to parse metadata JSON: {e}")
                logging.error(f"Raw metadata: {data['metadata']}")
                data['metadata'] = None

        return cls(
            client=client,
            **data
        )

    def update(self, **kwargs) -> 'ScoringJob':
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified after creation")
            
        update_data = {
            'updatedAt': datetime.now(timezone.utc).isoformat().replace(
                '+00:00', 'Z'
            ),
            **kwargs
        }
        
        mutation = """
        mutation UpdateScoringJob($input: UpdateScoringJobInput!) {
            updateScoringJob(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        variables = {
            'input': {
                'id': self.id,
                **update_data
            }
        }
        
        result = self._client.execute(mutation, variables)
        return self.from_dict(result['updateScoringJob'], self._client)

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'ScoringJob':
        query = """
        query GetScoringJob($id: ID!) {
            getScoringJob(id: $id) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'id': id})
        if not result or 'getScoringJob' not in result:
            raise Exception(f"Failed to get ScoringJob {id}")
            
        return cls.from_dict(result['getScoringJob'], client) 