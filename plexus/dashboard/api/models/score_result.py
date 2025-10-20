from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from .base import BaseModel
import json

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

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
    correct: Optional[bool] = None
    cost: Optional[Dict] = None  # Cost information including tokens, API calls, and monetary cost
    attachments: Optional[List[str]] = None  # List of S3 paths for trace/log attachments
    scoringJobId: Optional[str] = None
    evaluationId: Optional[str] = None
    feedbackItemId: Optional[str] = None
    code: Optional[str] = '200'  # HTTP response code, defaults to '200' for success
    type: Optional[str] = 'prediction'  # Type of score result: "prediction", "evaluation", etc.
    status: Optional[str] = 'COMPLETED'  # Status of score result: "COMPLETED", "ERROR", etc.
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

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
        correct: Optional[bool] = None,
        cost: Optional[Dict] = None,
        attachments: Optional[List[str]] = None,
        scoringJobId: Optional[str] = None,
        evaluationId: Optional[str] = None,
        feedbackItemId: Optional[str] = None,
        code: Optional[str] = '200',
        type: Optional[str] = 'prediction',
        status: Optional[str] = 'COMPLETED',
        createdAt: Optional[datetime] = None,
        updatedAt: Optional[datetime] = None,
        client: Optional['_BaseAPIClient'] = None
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
        self.correct = correct
        self.cost = cost
        self.attachments = attachments
        self.scoringJobId = scoringJobId
        self.evaluationId = evaluationId
        self.feedbackItemId = feedbackItemId
        self.code = code
        self.type = type
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    
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
            correct
            cost
            attachments
            scoringJobId
            evaluationId
            feedbackItemId
            code
            type
            status
            createdAt
            updatedAt
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'ScoreResult':
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
        
        # Parse cost JSON if it's a string
        cost = data.get('cost')
        if isinstance(cost, str):
            try:
                cost = json.loads(cost)
            except json.JSONDecodeError:
                cost = None
        
        # Parse timestamp fields
        created_at = data.get('createdAt')
        if isinstance(created_at, str):
            try:
                from datetime import datetime
                # Handle both ISO format with and without timezone
                if created_at.endswith('Z'):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created_at = datetime.fromisoformat(created_at)
            except (ValueError, TypeError):
                created_at = None
        
        updated_at = data.get('updatedAt')
        if isinstance(updated_at, str):
            try:
                from datetime import datetime
                # Handle both ISO format with and without timezone
                if updated_at.endswith('Z'):
                    updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                else:
                    updated_at = datetime.fromisoformat(updated_at)
            except (ValueError, TypeError):
                updated_at = None
                
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
            correct=data.get('correct'),
            cost=cost,
            attachments=data.get('attachments'),
            scoringJobId=data.get('scoringJobId'),
            evaluationId=data.get('evaluationId'),
            feedbackItemId=data.get('feedbackItemId'),
            code=data.get('code'),
            type=data.get('type'),
            status=data.get('status'),
            createdAt=created_at,
            updatedAt=updated_at,
            client=client
        )

    @classmethod
    def get_by_id(cls, score_result_id: str, client: '_BaseAPIClient') -> Optional['ScoreResult']:
        """Get a ScoreResult by its ID.
        
        Args:
            score_result_id: The ID of the score result to retrieve
            client: The API client to use
            
        Returns:
            ScoreResult object if found, None otherwise
        """
        query = f"""
        query GetScoreResult($id: ID!) {{
            getScoreResult(id: $id) {{
                {cls.fields()}
            }}
        }}
        """
        
        result = client.execute(query, {'id': score_result_id})
        score_result_data = result.get('getScoreResult')
        
        if score_result_data:
            return cls.from_dict(score_result_data, client)
        return None

    @classmethod
    def create(
        cls, 
        client: '_BaseAPIClient', 
        value: float, 
        itemId: str, 
        accountId: str, 
        scorecardId: str,
        scoringJobId: Optional[str] = None,
        evaluationId: Optional[str] = None,
        code: str = '200',
        type: str = 'prediction',
        status: str = 'COMPLETED',
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
            type: Type of score result - "prediction", "evaluation", etc. (defaults to 'prediction')
            status: Status of score result (defaults to 'COMPLETED')
            **kwargs: Optional fields:
                     - confidence: float
                     - metadata: dict (will be JSON serialized)
                     - trace: dict (will be JSON serialized)
                     - cost: dict (will be JSON serialized)
                     - correct: bool
                     - attachments: List[str]
        
        Note:
            Either scoringJobId or evaluationId should be provided, but not required
        """
        # Convert JSON fields to strings if present
        # Use default=str to handle Decimal and other non-serializable types
        if 'metadata' in kwargs:
            kwargs['metadata'] = json.dumps(kwargs['metadata'], default=str)
        if 'trace' in kwargs:
            kwargs['trace'] = json.dumps(kwargs['trace'], default=str)
        if 'cost' in kwargs:
            kwargs['cost'] = json.dumps(kwargs['cost'], default=str)
            
        input_data = {
            'value': value,
            'itemId': itemId,
            'accountId': accountId,
            'scorecardId': scorecardId,
            'code': code,
            'type': type,
            'status': status,
            **kwargs
        }
        
        if scoringJobId is not None:
            input_data['scoringJobId'] = scoringJobId
        if evaluationId is not None:
            input_data['evaluationId'] = evaluationId
        
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
        # Convert JSON fields to strings if present
        # Use default=str to handle Decimal and other non-serializable types
        if 'metadata' in kwargs:
            kwargs['metadata'] = json.dumps(kwargs['metadata'], default=str)
        
        if 'cost' in kwargs:
            kwargs['cost'] = json.dumps(kwargs['cost'], default=str)
        
        if 'trace' in kwargs:
            kwargs['trace'] = json.dumps(kwargs['trace'], default=str)
            
        mutation = """
        mutation UpdateScoreResult($input: UpdateScoreResultInput!) {
            updateScoreResult(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        # When updating any field, DynamoDB automatically updates 'updatedAt', which triggers
        # GSI composite key requirements. The update() method automatically includes:
        # - byAccountCodeAndUpdatedAt: accountId + code + updatedAt
        # - byTypeStatusUpdated: type + status + updatedAt
        #
        # Callers must pass additional fields as kwargs for other composite GSIs:
        # - byScorecardItemAndCreatedAt: scorecardId + itemId + createdAt
        # - byScorecardScoreItem: scorecardId + scoreId + itemId
        # - byItemScorecardScore: itemId + scorecardId + scoreId
        variables = {
            'input': {
                'id': self.id,
                'accountId': self.accountId,  # Required for byAccountCodeAndUpdatedAt GSI
                'code': getattr(self, 'code', '200'),  # Required for byAccountCodeAndUpdatedAt GSI, default to '200'
                'type': getattr(self, 'type', 'prediction'),  # Required for byTypeStatusUpdated GSI, default to 'prediction'
                'status': getattr(self, 'status', 'COMPLETED'),  # Required for byTypeStatusUpdated GSI, default to 'COMPLETED'
                **kwargs
            }
        }
        
        result = self._client.execute(mutation, variables)
        return self.from_dict(result['updateScoreResult'], self._client)

    @classmethod
    def batch_create(cls, client: '_BaseAPIClient', items: List[Dict]) -> List['ScoreResult']:
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
    
    @classmethod
    def find_by_cache_key(
        cls,
        client: '_BaseAPIClient',
        item_id: str,
        scorecard_id: str,
        score_id: str,
        account_id: Optional[str] = None
    ) -> Optional['ScoreResult']:
        """
        Find the most recent ScoreResult using cache key components.
        
        This method encapsulates the cache lookup logic for finding existing
        ScoreResults based on the standard cache key: itemId + scorecardId + scoreId.
        It uses the time-based GSI to return the most recent result.
        
        Args:
            client: API client for database operations
            item_id: Item ID (should be resolved DynamoDB ID)
            scorecard_id: Scorecard ID (should be resolved DynamoDB ID)
            score_id: Score ID (should be resolved DynamoDB ID)
            account_id: Optional account ID for additional context/validation
            
        Returns:
            Most recent ScoreResult matching the cache key, or None if not found
            
        Example:
            # Find cached score result
            cached_result = ScoreResult.find_by_cache_key(
                client=client,
                item_id="da270073-83ab-4c43-a1e6-961851c13d92",
                scorecard_id="f4076c72-e74b-4eaf-afd6-d4f61c9f0142", 
                score_id="687361f7-44a9-466f-8920-7f9dc351bcd2"
            )
        """
        try:
            # Use the same GSI query logic from the existing cache implementation
            cache_query = """
            query GetMostRecentScoreResult(
                $itemId: String!,
                $scorecardId: String!,
                $scoreId: String!
            ) {
                listScoreResultByItemIdAndScorecardIdAndScoreIdAndUpdatedAt(
                    itemId: $itemId,
                    scorecardIdScoreIdUpdatedAt: {
                        beginsWith: {
                            scorecardId: $scorecardId,
                            scoreId: $scoreId
                        }
                    },
                    sortDirection: DESC,
                    limit: 1
                ) {
                    items {
                        %s
                    }
                }
            }
            """ % cls.fields()
            
            cache_variables = {
                "itemId": item_id,
                "scorecardId": scorecard_id,
                "scoreId": score_id
            }
            
            # Execute the query
            response = client.execute(cache_query, cache_variables)
            
            # Extract results from the response
            items = response.get('listScoreResultByItemIdAndScorecardIdAndScoreIdAndUpdatedAt', {}).get('items', [])
            
            if items:
                # Return the most recent result (first item due to DESC sort, limit 1)
                score_result_data = items[0]
                return cls.from_dict(score_result_data, client)
            else:
                # No cached result found
                return None
                
        except Exception as e:
            # Log error but don't raise - return None for cache miss
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in ScoreResult.find_by_cache_key: {e}")
            return None
    
    @classmethod
    def _resolve_ids_for_cache_key(
        cls,
        client: '_BaseAPIClient',
        item_external_id: str = None,
        item_id: str = None,
        scorecard_external_id: str = None,
        scorecard_id: str = None,
        score_external_id: str = None,
        score_id: str = None,
        account_id: str = None
    ) -> Optional[Dict[str, str]]:
        """
        Helper method to resolve external IDs to DynamoDB IDs for cache lookups.
        
        This method handles the ID resolution logic that's currently scattered
        in the Call-Criteria-Python API, making it reusable.
        
        Args:
            client: API client
            item_external_id: External item ID (e.g., "277307013")  
            item_id: Already resolved item ID
            scorecard_external_id: External scorecard ID (e.g., "1039")
            scorecard_id: Already resolved scorecard ID
            score_external_id: External score ID (e.g., "45407")
            score_id: Already resolved score ID
            account_id: Account ID for scoped lookups
            
        Returns:
            Dict with resolved IDs: {"item_id": "...", "scorecard_id": "...", "score_id": "..."}
            or None if resolution fails
        """
        try:
            resolved_ids = {}
            
            # Resolve item ID if needed
            if item_id:
                resolved_ids["item_id"] = item_id
            elif item_external_id and account_id:
                # Use Item.find_by_identifier to resolve item
                from .item import Item
                item = Item.find_by_identifier(
                    client=client,
                    account_id=account_id,
                    identifier_key="reportId",  # This should be configurable per client
                    identifier_value=item_external_id
                )
                if item:
                    resolved_ids["item_id"] = item.id
                else:
                    return None  # Item not found
            else:
                return None  # Need either item_id or (item_external_id + account_id)
            
            # For scorecard and score IDs, we'd need similar resolution logic
            # This is where the Call-Criteria-Python resolve_scorecard_id and resolve_score_id
            # functions would be called. For now, assume they're already resolved.
            resolved_ids["scorecard_id"] = scorecard_id or scorecard_external_id
            resolved_ids["score_id"] = score_id or score_external_id
            
            # Validate all IDs are present
            if all(resolved_ids.values()):
                return resolved_ids
            else:
                return None
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error resolving IDs for cache key: {e}")
            return None