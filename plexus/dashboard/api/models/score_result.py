from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from .base import BaseModel
from ..client import _BaseAPIClient
import json

# Forward declaration for Score to handle circular dependency if Score is in another file or defined later
class Score: # Basic placeholder, ideally import the actual Score model
    id: str
    name: str

@dataclass
class ScoreResult(BaseModel):
    """
    Represents a single classification or scoring result in the Plexus dashboard.

    ScoreResult is the core data structure for tracking individual scoring operations,
    used both for real-time scoring and evaluation. It integrates with the GraphQL API
    to provide:

    - Score value tracking with confidence
    - Metadata storage for debugging and analysis
    - Links to related entities (items, accounts, scorecards)
    - Evaluation result tracking
    - Batch processing support

    Common usage patterns:
    1. Creating a single score result:
        result = ScoreResult.create(
            client=client,
            value=0.95,
            itemId="item-123",
            accountId="acc-456",
            scorecardId="card-789",
            metadata={"source": "phone_call"}
        )

    2. Batch creation for efficiency:
        results = ScoreResult.batch_create(client, [
            {
                "value": 0.95,
                "itemId": "item-123",
                "accountId": "acc-456",
                "scorecardId": "card-789"
            },
            {
                "value": 0.82,
                "itemId": "item-124",
                "accountId": "acc-456",
                "scorecardId": "card-789"
            }
        ])

    3. Updating with evaluation results:
        result.update(
            correct=True,
            evaluationId="eval-123",
            metadata={"human_label": "Yes"}
        )

    ScoreResult is commonly used with:
    - Evaluation for accuracy testing
    - ScoringJob for batch processing
    - LangGraphScore for LLM-based classification
    """

    value: str  # GraphQL schema defines this as string
    itemId: str
    accountId: str
    scorecardId: str
    scoreId: Optional[str] = None
    scoreVersionId: Optional[str] = None
    score: Optional[Dict[str, Any]] = field(default_factory=dict)
    explanation: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict] = None
    trace: Optional[Dict] = None
    scoringJobId: Optional[str] = None
    evaluationId: Optional[str] = None
    correct: Optional[bool] = None
    code: Optional[str] = None
    type: Optional[str] = None  # Type of score result: "prediction", "evaluation", etc.

    def __init__(
        self,
        id: str,
        value: str,  # GraphQL schema defines this as string
        itemId: str,
        accountId: str,
        scorecardId: str,
        scoreId: Optional[str] = None,
        scoreVersionId: Optional[str] = None,
        score: Optional[Dict[str, Any]] = None,
        explanation: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict] = None,
        trace: Optional[Dict] = None,
        scoringJobId: Optional[str] = None,
        evaluationId: Optional[str] = None,
        correct: Optional[bool] = None,
        code: Optional[str] = None,
        type: Optional[str] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.value = value
        self.itemId = itemId
        self.accountId = accountId
        self.scorecardId = scorecardId
        self.scoreId = scoreId
        self.scoreVersionId = scoreVersionId
        self.score = score if score is not None else {}
        self.explanation = explanation
        self.confidence = confidence
        self.metadata = metadata
        self.trace = trace
        self.scoringJobId = scoringJobId
        self.evaluationId = evaluationId
        self.correct = correct
        self.code = code
        self.type = type
    
    @property
    def scoreName(self) -> Optional[str]:
        """Get the score name from the related score object."""
        if self.score and isinstance(self.score, dict) and 'name' in self.score:
            return self.score['name']
        return None

    @property
    def numeric_value(self) -> Optional[float]:
        """Get the numeric value as a float, or None if invalid."""
        try:
            return float(self.value) if self.value is not None else None
        except (ValueError, TypeError):
            return None

    @classmethod
    def fields(cls) -> str:
        return """
            id
            value
            explanation
            itemId
            accountId
            scorecardId
            scoreId
            score {
                id
                name
            }
            scoreVersionId
            confidence
            metadata
            trace
            attachments
            scoringJobId
            evaluationId
            correct
            code
            type
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
        
        # Parse trace JSON if it's a string
        trace = data.get('trace')
        if isinstance(trace, str):
            try:
                trace = json.loads(trace)
            except json.JSONDecodeError:
                trace = None
                
        return cls(
            id=data['id'],
            value=data['value'],
            itemId=data['itemId'],
            accountId=data['accountId'],
            scorecardId=data['scorecardId'],
            scoreId=data.get('scoreId'),
            scoreVersionId=data.get('scoreVersionId'),
            score=data.get('score'),
            explanation=data.get('explanation'),
            confidence=data.get('confidence'),
            metadata=metadata,
            trace=trace,
            scoringJobId=data.get('scoringJobId'),
            evaluationId=data.get('evaluationId'),
            correct=data.get('correct'),
            code=data.get('code'),
            type=data.get('type'),
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
        evaluationId: Optional[str] = None,
        code: str = '200',
        type: Optional[str] = None,
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
            evaluationId: ID of evaluation (optional)
            code: HTTP response code (defaults to '200' for success)
            type: Type of score result - "prediction", "evaluation", etc. (optional)
            **kwargs: Optional fields:
                     - confidence: float
                     - metadata: dict (will be JSON serialized)
                     - correct: bool
        
        Note:
            Either scoringJobId or evaluationId should be provided, but not required
        """
        # Convert metadata to string if present
        if 'metadata' in kwargs:
            kwargs['metadata'] = json.dumps(kwargs['metadata'])
            
        input_data = {
            'value': value,
            'itemId': itemId,
            'accountId': accountId,
            'scorecardId': scorecardId,
            'code': code,
            **kwargs
        }
        
        if scoringJobId is not None:
            input_data['scoringJobId'] = scoringJobId
        if evaluationId is not None:
            input_data['evaluationId'] = evaluationId
        if type is not None:
            input_data['type'] = type
        
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
        
        # When updating any field, DynamoDB automatically updates 'updatedAt', which triggers
        # GSI composite key requirements. Must include all fields for affected GSIs:
        # - byAccountCodeAndUpdatedAt: accountId + code + updatedAt
        variables = {
            'input': {
                'id': self.id,
                'accountId': self.accountId,  # Required for byAccountCodeAndUpdatedAt GSI
                'code': getattr(self, 'code', '200'),  # Required for byAccountCodeAndUpdatedAt GSI, default to '200'
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
                
            # Add default code if not provided
            if 'code' not in item:
                item['code'] = '200'
                
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