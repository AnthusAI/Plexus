from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from .batch_job import BatchJob
import json
import logging
from plexus.utils.dict_utils import truncate_dict_strings_inner

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

@dataclass
class ScoringJob(BaseModel):
    """Represents an individual scoring operation job.
    
    A ScoringJob tracks the execution of a single scoring operation on an item,
    managing its lifecycle from creation through completion or failure.
    
    :param accountId: Identifier for the account owning this job
    :param status: Current status of the scoring job
    :param createdAt: Timestamp when the job was created
    :param updatedAt: Timestamp of the last update
    :param scorecardId: Associated scorecard identifier
    :param itemId: Identifier of the item being scored
    :param startedAt: Timestamp when scoring started
    :param completedAt: Timestamp when scoring completed
    :param errorMessage: Error message if scoring failed
    :param errorDetails: Detailed error information
    :param metadata: Additional metadata about the scoring job
    :param evaluationId: Associated evaluation identifier
    :param scoreId: Associated score identifier
    :param batchId: Identifier of the batch this job belongs to
    """
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
    batchId: Optional[str] = None

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
        batchId: Optional[str] = None,
        client: Optional['_BaseAPIClient'] = None
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
        self.batchId = batchId

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
        client: '_BaseAPIClient',
        accountId: str,
        scorecardId: str,
        itemId: str,
        parameters: Dict,
        **kwargs
    ) -> 'ScoringJob':
        """Creates a new scoring job.
        
        :param client: API client instance for making requests
        :param accountId: Account identifier for the job
        :param scorecardId: Associated scorecard identifier
        :param itemId: Item identifier to be scored
        :param parameters: Additional parameters for job creation
        :param kwargs: Optional parameters (status, metadata, etc.)
        :return: New ScoringJob instance
        :raises: Exception if creation fails
        """
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
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'ScoringJob':
        """Creates a ScoringJob instance from dictionary data.
        
        :param data: Dictionary containing scoring job data
        :param client: API client instance
        :return: ScoringJob instance
        """
        for date_field in ['createdAt', 'updatedAt', 'startedAt', 'completedAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )
        
        if data.get('metadata'):
            try:
                data['metadata'] = json.loads(data['metadata'])
                logging.info(f"Parsed metadata from JSON: {truncate_dict_strings_inner(data['metadata'])}")
            except Exception as e:
                logging.error(f"Failed to parse metadata JSON: {e}")
                logging.error(f"Raw metadata: {truncate_dict_strings_inner(data['metadata'])}")
                data['metadata'] = None

        return cls(
            client=client,
            **data
        )

    def update(self, **kwargs) -> 'ScoringJob':
        """Updates scoring job fields.
        
        :param kwargs: Fields to update and their new values
        :return: Updated ScoringJob instance
        :raises: ValueError if attempting to modify createdAt
        """
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
    def get_by_id(cls, id: str, client: '_BaseAPIClient') -> 'ScoringJob':
        """Retrieves a scoring job by its identifier.
        
        :param id: Scoring job identifier
        :param client: API client instance
        :return: ScoringJob instance
        :raises: Exception if scoring job not found
        """
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

    @classmethod
    def find_by_item_id(cls, item_id: str, client: '_BaseAPIClient') -> Optional['ScoringJob']:
        """Finds a scoring job by its associated item identifier.
        
        :param item_id: Item identifier to search for
        :param client: API client instance
        :return: ScoringJob instance if found, None otherwise
        """
        query = """
        query FindScoringJobByItemId($itemId: String!) {
            listScoringJobByItemId(itemId: $itemId) {
                items {
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
                }
            }
        }
        """
        
        result = client.execute(query, {'itemId': item_id})
        items = result.get('listScoringJobByItemId', {}).get('items', [])
        
        if items:
            return cls.from_dict(items[0], client)
        return None

    @classmethod
    def get_batch_job(cls, scoring_job_id: str, client: '_BaseAPIClient') -> Optional[BatchJob]:
        """Gets the associated batch job for a scoring job through the join table.
        
        :param scoring_job_id: ID of the scoring job
        :param client: API client instance
        :return: BatchJob instance if found, None otherwise
        """
        query = """
        query GetBatchJobForScoringJob($scoringJobId: String!) {
            listBatchJobScoringJobs(filter: {scoringJobId: {eq: $scoringJobId}}) {
                items {
                    batchJob {
                        %s
                    }
                }
            }
        }
        """ % BatchJob.fields()
        
        result = client.execute(query, {'scoringJobId': scoring_job_id})
        items = result.get('listBatchJobScoringJobs', {}).get('items', [])
        return BatchJob.from_dict(items[0]['batchJob'], client) if items else None