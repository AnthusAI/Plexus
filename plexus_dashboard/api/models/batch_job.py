from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient
import uuid
import logging

@dataclass
class BatchJob(BaseModel):
    accountId: str
    status: str
    type: str
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
    scoringJobCountCache: Optional[int] = None

    def __init__(
        self,
        id: str,
        accountId: str,
        status: str,
        type: str,
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
        scoringJobCountCache: Optional[int] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.status = status
        self.type = type
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
        self.scoringJobCountCache = scoringJobCountCache

    @classmethod
    def fields(cls) -> str:
        return """
            id
            accountId
            status
            type
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
            scoringJobCountCache
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
            'batchId': str(uuid.uuid4()),
            'modelProvider': modelProvider,
            'modelName': modelName,
            'status': kwargs.pop('status', 'PENDING')
        }
        
        optional_fields = [
            'scorecardId', 'scoreId', 'errorMessage', 'errorDetails',
            'startedAt', 'estimatedEndAt', 'completedAt',
            'totalRequests', 'completedRequests', 'failedRequests',
            'scoringJobCountCache'
        ]
        for field in optional_fields:
            if field in kwargs:
                input_data[field] = kwargs[field]
        
        logging.info(f"Creating BatchJob with input: {input_data}")
        
        mutation = """
        mutation CreateBatchJob($input: CreateBatchJobInput!) {
            createBatchJob(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        logging.info(f"Executing BatchJob creation mutation: {mutation}")
        result = client.execute(mutation, {'input': input_data})
        logging.info(f"BatchJob creation result: {result}")
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
        """Update batch job fields."""
        mutation = """
        mutation UpdateBatchJob($input: UpdateBatchJobInput!) {
            updateBatchJob(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        # First get current state to ensure we have all required fields
        query = """
        query GetBatchJob($id: ID!) {
            getBatchJob(id: $id) {
                accountId
                status
                type
                batchId
                modelProvider
                modelName
            }
        }
        """
        result = self._client.execute(query, {'id': self.id})
        current_data = result.get('getBatchJob', {})
        
        # Combine current required fields with updates
        input_data = {
            'id': self.id,
            'accountId': current_data['accountId'],
            'status': current_data['status'],
            'type': current_data['type'],
            'batchId': current_data['batchId'],
            'modelProvider': current_data['modelProvider'],
            'modelName': current_data['modelName'],
            **kwargs
        }
        
        result = self._client.execute(mutation, {'input': input_data})
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