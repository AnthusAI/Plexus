from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
import uuid
import logging

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

@dataclass
class BatchJob(BaseModel):
    """Represents a batch processing job for scoring multiple items.
    
    A BatchJob manages the execution of scoring operations across multiple items,
    tracking progress, handling errors, and maintaining state throughout the
    batch processing lifecycle.
    
    :param accountId: Identifier for the account owning this batch job
    :param status: Current status of the batch job (PENDING, RUNNING, etc.)
    :param type: Type of batch operation being performed
    :param batchId: Unique identifier for this batch of operations
    :param modelProvider: Provider of the model being used
    :param modelName: Name of the model being used
    :param scoringJobCountCache: Number of scoring jobs in this batch
    :param startedAt: Timestamp when the batch job started
    :param estimatedEndAt: Estimated completion timestamp
    :param completedAt: Timestamp when the batch job completed
    :param totalRequests: Total number of requests in this batch
    :param completedRequests: Number of completed requests
    :param failedRequests: Number of failed requests
    :param errorMessage: Error message if the batch job failed
    :param errorDetails: Detailed error information
    :param scorecardId: Associated scorecard identifier
    :param scoreId: Associated score identifier
    """
    accountId: str
    status: str
    type: str
    batchId: str
    modelProvider: str
    modelName: str
    scoringJobCountCache: Optional[int] = None
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
        batchId: str,
        modelProvider: str,
        modelName: str,
        scoringJobCountCache: Optional[int] = None,
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
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.status = status
        self.type = type
        self.batchId = batchId
        self.modelProvider = modelProvider
        self.modelName = modelName
        self.scoringJobCountCache = scoringJobCountCache
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
            batchId
            modelProvider
            modelName
            scoringJobCountCache
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
        client: '_BaseAPIClient',
        accountId: str,
        type: str,
        modelProvider: str,
        modelName: str,
        parameters: Dict,
        **kwargs
    ) -> 'BatchJob':
        """Creates a new batch job.
        
        :param client: API client instance for making requests
        :param accountId: Account identifier for the batch job
        :param type: Type of batch operation
        :param modelProvider: Provider of the model
        :param modelName: Name of the model
        :param parameters: Additional parameters for job creation
        :param kwargs: Optional parameters (status, scorecardId, etc.)
        :return: New BatchJob instance
        :raises: Exception if creation fails
        """
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
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createBatchJob'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'BatchJob':
        """Creates a BatchJob instance from dictionary data.
        
        :param data: Dictionary containing batch job data
        :param client: API client instance
        :return: BatchJob instance
        """
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
        """Updates batch job fields.
        
        :param kwargs: Fields to update and their new values
        :return: Updated BatchJob instance
        :raises: ValueError if attempting to modify createdAt
        """
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified")
        
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
    def get_by_id(cls, id: str, client: '_BaseAPIClient') -> 'BatchJob':
        """Retrieves a batch job by its identifier.
        
        :param id: Batch job identifier
        :param client: API client instance
        :return: BatchJob instance
        :raises: Exception if batch job not found
        """
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