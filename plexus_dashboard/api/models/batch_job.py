from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient
import uuid

@dataclass
class BatchJob(BaseModel):
    accountId: str
    status: str
    type: str
    provider: str
    batchId: str
    modelProvider: str
    modelName: str
    startedAt: Optional[datetime] = None
    estimatedEndAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    totalRequests: Optional[int] = None
    completedRequests: Optional[int] = None
    failedRequests: Optional[int] = None
    errorMessage: Optional[str] = None
    errorDetails: Optional[Dict] = None
    scorecardId: Optional[str] = None
    scoreId: Optional[str] = None

    def __init__(
        self,
        id: str,
        accountId: str,
        status: str,
        type: str,
        provider: str,
        batchId: str,
        modelProvider: str,
        modelName: str,
        startedAt: Optional[datetime] = None,
        estimatedEndAt: Optional[datetime] = None,
        completedAt: Optional[datetime] = None,
        totalRequests: Optional[int] = None,
        completedRequests: Optional[int] = None,
        failedRequests: Optional[int] = None,
        errorMessage: Optional[str] = None,
        errorDetails: Optional[Dict] = None,
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.status = status
        self.type = type
        self.provider = provider
        self.batchId = batchId
        self.modelProvider = modelProvider
        self.modelName = modelName
        self.startedAt = startedAt
        self.estimatedEndAt = estimatedEndAt
        self.completedAt = completedAt
        self.totalRequests = totalRequests
        self.completedRequests = completedRequests
        self.failedRequests = failedRequests
        self.errorMessage = errorMessage
        self.errorDetails = errorDetails
        self.scorecardId = scorecardId
        self.scoreId = scoreId

    @classmethod
    def fields(cls) -> str:
        return """
            id
            accountId
            status
            type
            provider
            batchId
            modelProvider
            modelName
            startedAt
            estimatedEndAt
            completedAt
            totalRequests
            completedRequests
            failedRequests
            errorMessage
            errorDetails
            scorecardId
            scoreId
        """

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        accountId: str,
        type: str,
        modelProvider: str,
        modelName: str,
        parameters: Dict,
        **kwargs
    ) -> 'BatchJob':
        input_data = {
            'accountId': accountId,
            'type': type,
            'provider': 'OPENAI',
            'batchId': str(uuid.uuid4()),
            'modelProvider': modelProvider,
            'modelName': modelName,
            'status': kwargs.pop('status', 'PENDING')
        }
        
        optional_fields = [
            'scorecardId', 'scoreId', 'errorMessage', 'errorDetails',
            'startedAt', 'estimatedEndAt', 'completedAt',
            'totalRequests', 'completedRequests', 'failedRequests'
        ]
        for field in optional_fields:
            if field in kwargs:
                input_data[field] = kwargs[field]
        
        mutation = """
        mutation CreateBatchJob($input: CreateBatchJobInput!) {
            createBatchJob(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createBatchJob'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'BatchJob':
        # Convert datetime fields
        for date_field in ['startedAt', 'estimatedEndAt', 'completedAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )
        
        # Remove fields not in constructor
        filtered_data = {k: v for k, v in data.items() 
                       if k not in ['createdAt', 'updatedAt']}
        
        return cls(
            client=client,
            **filtered_data
        )

    def update(self, **kwargs) -> 'BatchJob':
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified after creation")
            
        update_data = {
            'updatedAt': datetime.now(timezone.utc).isoformat().replace(
                '+00:00', 'Z'
            ),
            **kwargs
        }
        
        mutation = """
        mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
            updateBatchJob(input: $input) {
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
        return self.from_dict(result['updateBatchJob'], self._client)

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'BatchJob':
        query = """
        query GetBatchJob($id: ID!) {
            getBatchJob(id: $id) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'id': id})
        if not result or 'getBatchJob' not in result:
            raise Exception(f"Failed to get BatchJob {id}")
            
        return cls.from_dict(result['getBatchJob'], client) 