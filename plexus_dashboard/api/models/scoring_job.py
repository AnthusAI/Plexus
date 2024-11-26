from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient

@dataclass
class ScoringJob(BaseModel):
    accountId: str
    status: str
    createdAt: datetime
    updatedAt: datetime
    scorecardId: str
    parameters: Dict
    totalItems: Optional[int] = None
    processedItems: Optional[int] = None
    errorMessage: Optional[str] = None
    errorDetails: Optional[Dict] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    elapsedSeconds: Optional[int] = None
    estimatedRemainingSeconds: Optional[int] = None
    batchSize: Optional[int] = None
    concurrency: Optional[int] = None
    cost: Optional[float] = None

    def __init__(
        self,
        id: str,
        accountId: str,
        status: str,
        createdAt: datetime,
        updatedAt: datetime,
        scorecardId: str,
        parameters: Dict,
        totalItems: Optional[int] = None,
        processedItems: Optional[int] = None,
        errorMessage: Optional[str] = None,
        errorDetails: Optional[Dict] = None,
        startedAt: Optional[datetime] = None,
        completedAt: Optional[datetime] = None,
        elapsedSeconds: Optional[int] = None,
        estimatedRemainingSeconds: Optional[int] = None,
        batchSize: Optional[int] = None,
        concurrency: Optional[int] = None,
        cost: Optional[float] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.scorecardId = scorecardId
        self.parameters = parameters
        self.totalItems = totalItems
        self.processedItems = processedItems
        self.errorMessage = errorMessage
        self.errorDetails = errorDetails
        self.startedAt = startedAt
        self.completedAt = completedAt
        self.elapsedSeconds = elapsedSeconds
        self.estimatedRemainingSeconds = estimatedRemainingSeconds
        self.batchSize = batchSize
        self.concurrency = concurrency
        self.cost = cost

    @classmethod
    def fields(cls) -> str:
        return """
            id
            accountId
            status
            createdAt
            updatedAt
            scorecardId
            parameters
            totalItems
            processedItems
            errorMessage
            errorDetails
            startedAt
            completedAt
            elapsedSeconds
            estimatedRemainingSeconds
            batchSize
            concurrency
            cost
        """

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        accountId: str,
        scorecardId: str,
        parameters: Dict,
        batchSize: Optional[int] = None,
        concurrency: Optional[int] = None,
        **kwargs
    ) -> 'ScoringJob':
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        input_data = {
            'accountId': accountId,
            'scorecardId': scorecardId,
            'parameters': parameters,
            'status': kwargs.pop('status', 'PENDING'),
            'createdAt': now,
            'updatedAt': now,
            **kwargs
        }
        
        if batchSize is not None:
            input_data['batchSize'] = batchSize
        if concurrency is not None:
            input_data['concurrency'] = concurrency
        
        mutation = """
        mutation CreateScoringJob($input: CreateScoringJobInput!) {
            createScoringJob(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createScoringJob'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'ScoringJob':
        for date_field in ['createdAt', 'updatedAt', 'startedAt', 'completedAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )

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