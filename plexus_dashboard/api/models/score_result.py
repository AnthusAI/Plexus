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
    scorecardId: str
    confidence: Optional[float] = None
    metadata: Optional[Dict] = None
    scoringJobId: Optional[str] = None
    experimentId: Optional[str] = None
    correct: Optional[bool] = None

    def __init__(
        self,
        id: str,
        value: float,
        itemId: str,
        accountId: str,
        scorecardId: str,
        confidence: Optional[float] = None,
        metadata: Optional[Dict] = None,
        scoringJobId: Optional[str] = None,
        experimentId: Optional[str] = None,
        correct: Optional[bool] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.value = value
        self.itemId = itemId
        self.accountId = accountId
        self.scorecardId = scorecardId
        self.confidence = confidence
        self.metadata = metadata
        self.scoringJobId = scoringJobId
        self.experimentId = experimentId
        self.correct = correct

    @classmethod
    def fields(cls) -> str:
        return """
            id
            value
            itemId
            accountId
            scorecardId
            confidence
            metadata
            scoringJobId
            experimentId
            correct
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'ScoreResult':
        """Create a ScoreResult instance from API response data."""
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
            scorecardId=data['scorecardId'],
            confidence=data.get('confidence'),
            metadata=metadata,
            scoringJobId=data.get('scoringJobId'),
            experimentId=data.get('experimentId'),
            correct=data.get('correct'),
            client=client
        )

    @classmethod
    def create(
        cls, 
        client: _BaseAPIClient, 
        value: float, 
        itemId: str, 
        accountId: str, 
        scorecardId: str,
        scoringJobId: Optional[str] = None,
        experimentId: Optional[str] = None,
        **kwargs
    ) -> 'ScoreResult':
        """Create a new score result.
        
        Args:
            client: The API client instance
            value: Score value (required)
            itemId: ID of scored item (required)
            accountId: Account context (required)
            scorecardId: ID of scorecard used (required)
            scoringJobId: ID of scoring job (optional)
            experimentId: ID of experiment (optional)
            **kwargs: Optional fields:
                     - confidence: float
                     - metadata: dict (will be JSON serialized)
                     - correct: bool
        
        Note:
            Either scoringJobId or experimentId should be provided, but not required
        """
        # Convert metadata to string if present
        if 'metadata' in kwargs:
            kwargs['metadata'] = json.dumps(kwargs['metadata'])
            
        input_data = {
            'value': value,
            'itemId': itemId,
            'accountId': accountId,
            'scorecardId': scorecardId,
            **kwargs
        }
        
        if scoringJobId is not None:
            input_data['scoringJobId'] = scoringJobId
        if experimentId is not None:
            input_data['experimentId'] = experimentId
        
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
        """Update this score result with new values."""
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
        """Create multiple score results in a single API request."""
        # Prepare all items, handling metadata JSON conversion
        mutations = []
        required_fields = {'value', 'itemId', 'accountId', 'scorecardId'}
        
        for item in items:
            if 'metadata' in item:
                item['metadata'] = json.dumps(item['metadata'])
                
            # Verify required fields
            missing = required_fields - set(item.keys())
            if missing:
                raise ValueError(f"Missing required fields: {missing}")
                
            mutations.append({
                **item
            })

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