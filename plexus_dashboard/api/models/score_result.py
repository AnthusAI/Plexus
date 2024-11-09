from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .base import BaseModel
from ..client import _BaseAPIClient
import json

@dataclass
class ScoreResult(BaseModel):
    value: float
    itemId: str
    accountId: str
    scoringJobId: str
    scorecardId: str
    confidence: Optional[float] = None
    metadata: Optional[Dict] = None

    def __init__(
        self,
        id: str,
        value: float,
        itemId: str,
        accountId: str,
        scoringJobId: str,
        scorecardId: str,
        confidence: Optional[float] = None,
        metadata: Optional[Dict] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.value = value
        self.itemId = itemId
        self.accountId = accountId
        self.scoringJobId = scoringJobId
        self.scorecardId = scorecardId
        self.confidence = confidence
        self.metadata = metadata

    @classmethod
    def fields(cls) -> str:
        return """
            id
            value
            itemId
            accountId
            scoringJobId
            scorecardId
            confidence
            metadata
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'ScoreResult':
        """Create a ScoreResult instance from API response data.
        
        This method handles:
        - JSON deserialization of metadata
        - Optional field handling
        - Client association
        
        Args:
            data: Dictionary of score result data from API
            client: The API client instance
            
        Returns:
            ScoreResult: New instance with parsed data
            
        Implementation Notes:
            Metadata is automatically deserialized from JSON if it's
            a string, or passed through if it's already a dict.
        """
        # Parse metadata JSON if it's a string
        metadata = data.get('metadata')
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = None
                
        return cls(
            id=data['id'],
            value=data['value'],
            itemId=data['itemId'],
            accountId=data['accountId'],
            scoringJobId=data['scoringJobId'],
            scorecardId=data['scorecardId'],
            confidence=data.get('confidence'),
            metadata=metadata,
            client=client
        )

    @classmethod
    def create(cls, client: _BaseAPIClient, value: float, itemId: str, 
               accountId: str, scoringJobId: str, scorecardId: str, 
               **kwargs) -> 'ScoreResult':
        """Create a new score result.
        
        Args:
            client: The API client instance
            value: Score value (required)
            itemId: ID of scored item (required)
            accountId: Account context (required)
            scoringJobId: ID of scoring job (required)
            scorecardId: ID of scorecard used (required)
            **kwargs: Optional fields:
                     - confidence: float
                     - metadata: dict (will be JSON serialized)
        
        Returns:
            ScoreResult: The created score result instance
            
        Example:
            result = ScoreResult.create(
                client=client,
                value=0.95,
                itemId="item-123",
                accountId="acc-123",
                scoringJobId="job-123",
                scorecardId="card-123",
                confidence=0.87,
                metadata={"source": "manual"}
            )
        """
        # Convert metadata to string if present
        if 'metadata' in kwargs:
            kwargs['metadata'] = json.dumps(kwargs['metadata'])
            
        input_data = {
            'value': value,
            'itemId': itemId,
            'accountId': accountId,
            'scoringJobId': scoringJobId,
            'scorecardId': scorecardId,
            **kwargs
        }
        
        mutation = """
        mutation CreateScoreResult($input: CreateScoreResultInput!) {
            createScoreResult(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createScoreResult'], client)

    def update(self, **kwargs) -> 'ScoreResult':
        """Update this score result with new values.
        
        Args:
            **kwargs: Fields to update. Any field not provided keeps its current value.
            
        Returns:
            ScoreResult: Updated score result instance
        """
        # Convert metadata to string if present
        if 'metadata' in kwargs:
            kwargs['metadata'] = json.dumps(kwargs['metadata'])
            
        mutation = """
        mutation UpdateScoreResult($input: UpdateScoreResultInput!) {
            updateScoreResult(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        variables = {
            'input': {
                'id': self.id,
                **kwargs
            }
        }
        
        result = self._client.execute(mutation, variables)
        return self.from_dict(result['updateScoreResult'], self._client)

    @classmethod
    def batch_create(cls, client: _BaseAPIClient, items: List[Dict]) -> List['ScoreResult']:
        """Create multiple score results in a single API request.
        
        This method is more efficient than creating scores individually when you
        have multiple scores to create. It handles:
        - Metadata JSON serialization
        - Field validation
        - Single API request for all items
        
        Args:
            client: The API client instance
            items: List of dictionaries, each containing score result data:
                  - value (float, required): The score value
                  - itemId (str, required): ID of scored item
                  - accountId (str, required): Account context
                  - scoringJobId (str, required): ID of scoring job
                  - scorecardId (str, required): ID of scorecard used
                  - confidence (float, optional): Confidence in score
                  - metadata (dict, optional): Additional data
        
        Returns:
            List[ScoreResult]: List of created score result instances
            
        Example:
            results = ScoreResult.batch_create(client, [
                {
                    "value": 0.95,
                    "itemId": "item-1",
                    "accountId": "acc-1",
                    "scoringJobId": "job-1",
                    "scorecardId": "card-1",
                    "metadata": {"source": "batch"}
                },
                # ... more items ...
            ])
        """
        # Prepare all items, handling metadata JSON conversion
        mutations = []
        for item in items:
            if 'metadata' in item:
                item['metadata'] = json.dumps(item['metadata'])
            mutations.append({
                'value': item['value'],
                'itemId': item['itemId'],
                'accountId': item['accountId'],
                'scoringJobId': item['scoringJobId'],
                'scorecardId': item['scorecardId'],
                **{k:v for k,v in item.items() if k not in 
                   ['value', 'itemId', 'accountId', 'scoringJobId', 'scorecardId']}
            })

        # Build batch mutation
        mutation = """
        mutation BatchCreateScoreResults($inputs: [CreateScoreResultInput!]!) {
            batchCreateScoreResults(inputs: $inputs) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'inputs': mutations})
        return [cls.from_dict(item, client) 
                for item in result['batchCreateScoreResults']['items']]