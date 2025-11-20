"""
AggregatedMetrics Model - Python representation of the GraphQL AggregatedMetrics type.

This model represents pre-computed aggregation counts for Items, ScoreResults, 
Tasks, and Evaluations across different time buckets (1, 5, 15, 60 minutes).

Key Features:
- Query aggregated metrics by time range
- Create or update aggregation records (upsert logic)
- Support for multiple record types (items, scoreResults, tasks, evaluations)
- Hierarchical time bucketing for efficient queries
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

@dataclass
class AggregatedMetrics(BaseModel):
    """AggregatedMetrics model for interacting with the API."""
    accountId: str
    compositeKey: str
    recordType: str
    timeRangeStart: datetime
    timeRangeEnd: datetime
    numberOfMinutes: int
    count: int
    complete: bool
    createdAt: datetime
    updatedAt: datetime
    scorecardId: Optional[str] = None
    scoreId: Optional[str] = None
    cost: Optional[int] = None
    decisionCount: Optional[int] = None
    externalAiApiCount: Optional[int] = None
    cachedAiApiCount: Optional[int] = None
    errorCount: Optional[int] = None
    metadata: Optional[Dict] = None

    def __init__(
        self,
        id: str,
        accountId: str,
        compositeKey: str,
        recordType: str,
        timeRangeStart: datetime,
        timeRangeEnd: datetime,
        numberOfMinutes: int,
        count: int,
        complete: bool,
        createdAt: datetime,
        updatedAt: datetime,
        client: Optional['_BaseAPIClient'] = None,
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        cost: Optional[int] = None,
        decisionCount: Optional[int] = None,
        externalAiApiCount: Optional[int] = None,
        cachedAiApiCount: Optional[int] = None,
        errorCount: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.compositeKey = compositeKey
        self.recordType = recordType
        self.timeRangeStart = timeRangeStart
        self.timeRangeEnd = timeRangeEnd
        self.numberOfMinutes = numberOfMinutes
        self.count = count
        self.complete = complete
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.scorecardId = scorecardId
        self.scoreId = scoreId
        self.cost = cost
        self.decisionCount = decisionCount
        self.externalAiApiCount = externalAiApiCount
        self.cachedAiApiCount = cachedAiApiCount
        self.errorCount = errorCount
        self.metadata = metadata
    
    @staticmethod
    def generate_composite_key(record_type: str, time_range_start: datetime, number_of_minutes: int) -> str:
        """Generate composite key for AggregatedMetrics."""
        time_str = time_range_start.isoformat().replace('+00:00', 'Z')
        return f"{record_type}#{time_str}#{number_of_minutes}"

    def __repr__(self) -> str:
        return (
            f"AggregatedMetrics(id={self.id}, recordType={self.recordType}, "
            f"timeRange={self.timeRangeStart.isoformat()} to {self.timeRangeEnd.isoformat()}, "
            f"bucket={self.numberOfMinutes}min, count={self.count}, complete={self.complete})"
        )

    @classmethod
    def fields(cls) -> str:
        """Fields to request in queries and mutations"""
        return """
            accountId
            compositeKey
            scorecardId
            scoreId
            recordType
            timeRangeStart
            timeRangeEnd
            numberOfMinutes
            count
            cost
            decisionCount
            externalAiApiCount
            cachedAiApiCount
            errorCount
            metadata
            complete
            createdAt
            updatedAt
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'AggregatedMetrics':
        """Create an AggregatedMetrics instance from a dictionary."""
        # Convert datetime fields
        for date_field in ['timeRangeStart', 'timeRangeEnd', 'createdAt', 'updatedAt']:
            if data.get(date_field):
                if isinstance(data[date_field], str):
                    data[date_field] = datetime.fromisoformat(
                        data[date_field].replace('Z', '+00:00')
                    )
        
        # For composite key, id is derived from accountId#compositeKey
        record_id = f"{data['accountId']}#{data['compositeKey']}"
        
        return cls(
            id=record_id,
            accountId=data['accountId'],
            compositeKey=data['compositeKey'],
            recordType=data['recordType'],
            timeRangeStart=data['timeRangeStart'],
            timeRangeEnd=data['timeRangeEnd'],
            numberOfMinutes=data['numberOfMinutes'],
            count=data['count'],
            complete=data['complete'],
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            client=client,
            scorecardId=data.get('scorecardId'),
            scoreId=data.get('scoreId'),
            cost=data.get('cost'),
            decisionCount=data.get('decisionCount'),
            externalAiApiCount=data.get('externalAiApiCount'),
            cachedAiApiCount=data.get('cachedAiApiCount'),
            errorCount=data.get('errorCount'),
            metadata=data.get('metadata'),
        )

    @classmethod
    def list_by_time_range(
        cls,
        client: '_BaseAPIClient',
        account_id: str,
        start_time: datetime,
        end_time: datetime,
        record_type: Optional[str] = None
    ) -> List['AggregatedMetrics']:
        """
        Query aggregated metrics by time range using the GSI.
        
        Args:
            client: The API client instance
            account_id: The account ID to filter by
            start_time: Start of the time range
            end_time: End of the time range
            record_type: Optional record type filter (items, scoreResults, tasks, evaluations)
            
        Returns:
            List of AggregatedMetrics instances
        """
        query = """
        query ListAggregatedMetricsByTimeRange(
            $accountId: String!,
            $startTime: AWSDateTime!,
            $nextToken: String
        ) {
            listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType(
                accountId: $accountId,
                timeRangeStartRecordType: { beginsWith: { timeRangeStart: $startTime } },
                limit: 1000,
                nextToken: $nextToken
            ) {
                items {
                    %s
                }
                nextToken
            }
        }
        """ % cls.fields()

        # Paginate through all results
        all_items = []
        next_token = None
        
        while True:
            variables = {
                'accountId': account_id,
                'startTime': start_time.isoformat().replace('+00:00', 'Z')
            }
            if next_token:
                variables['nextToken'] = next_token
                
            result = client.execute(query, variables)
            items = result.get('listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType', {}).get('items', [])
            
            # Filter by time range and record type in memory
            filtered_items = []
            for item in items:
                item_time_str = item.get('timeRangeStart')
                if item_time_str:
                    item_time = datetime.fromisoformat(item_time_str.replace('Z', '+00:00'))
                    if start_time <= item_time <= end_time:
                        if record_type is None or item.get('recordType') == record_type:
                            filtered_items.append(item)
            items = filtered_items
            
            all_items.extend([cls.from_dict(item, client) for item in items])
            
            next_token = result.get('listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType', {}).get('nextToken')
            if not next_token:
                break
        
        return all_items

    @classmethod
    def create_or_update(
        cls,
        client: '_BaseAPIClient',
        account_id: str,
        record_type: str,
        time_range_start: datetime,
        time_range_end: datetime,
        number_of_minutes: int,
        count: int,
        complete: bool = True,
        scorecard_id: Optional[str] = None,
        score_id: Optional[str] = None,
        cost: Optional[int] = None,
        decision_count: Optional[int] = None,
        external_ai_api_count: Optional[int] = None,
        cached_ai_api_count: Optional[int] = None,
        error_count: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> 'AggregatedMetrics':
        """
        Create or update an aggregated metrics record (upsert logic).
        
        This method first queries for an existing record matching the key fields
        (accountId, recordType, timeRangeStart, numberOfMinutes), then either
        updates it or creates a new one.
        
        Args:
            client: The API client instance
            account_id: The account ID
            record_type: Type of record (items, scoreResults, tasks, evaluations)
            time_range_start: Start of the time range
            time_range_end: End of the time range
            number_of_minutes: Bucket size in minutes
            count: The aggregated count
            complete: Whether this bucket is complete
            scorecard_id: Optional scorecard ID
            score_id: Optional score ID
            cost: Optional cost value
            decision_count: Optional decision count
            external_ai_api_count: Optional external AI API count
            cached_ai_api_count: Optional cached AI API count
            error_count: Optional error count
            metadata: Optional metadata dictionary
            
        Returns:
            The created or updated AggregatedMetrics instance
        """
        # Generate composite key
        composite_key = cls.generate_composite_key(record_type, time_range_start, number_of_minutes)
        
        now = datetime.now(timezone.utc)
        
        # Try update first (more common case)
        update_mutation = """
        mutation UpdateAggregatedMetrics($input: UpdateAggregatedMetricsInput!) {
            updateAggregatedMetrics(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        update_input = {
            'accountId': account_id,
            'compositeKey': composite_key,
            'recordType': record_type,
            'timeRangeStart': time_range_start.isoformat().replace('+00:00', 'Z'),
            'timeRangeEnd': time_range_end.isoformat().replace('+00:00', 'Z'),
            'numberOfMinutes': number_of_minutes,
            'count': count,
            'complete': complete,
            'updatedAt': now.isoformat().replace('+00:00', 'Z')
        }
        
        # Add optional GSI fields
        if scorecard_id:
            update_input['scorecardId'] = scorecard_id
        if score_id:
            update_input['scoreId'] = score_id
            
        # Add optional fields if provided
        if cost is not None:
            update_input['cost'] = cost
        if decision_count is not None:
            update_input['decisionCount'] = decision_count
        if external_ai_api_count is not None:
            update_input['externalAiApiCount'] = external_ai_api_count
        if cached_ai_api_count is not None:
            update_input['cachedAiApiCount'] = cached_ai_api_count
        if error_count is not None:
            update_input['errorCount'] = error_count
        if metadata is not None:
            update_input['metadata'] = metadata
        
        try:
            # Try update first
            result = client.execute(update_mutation, {'input': update_input})
            return cls.from_dict(result['updateAggregatedMetrics'], client)
        except Exception as e:
            # If update fails (record doesn't exist), create it
            error_msg = str(e).lower()
            if 'not found' in error_msg or 'does not exist' in error_msg:
                create_mutation = """
                mutation CreateAggregatedMetrics($input: CreateAggregatedMetricsInput!) {
                    createAggregatedMetrics(input: $input) {
                        %s
                    }
                }
                """ % cls.fields()
                
                create_input = {
                    'accountId': account_id,
                    'compositeKey': composite_key,
                    'recordType': record_type,
                    'timeRangeStart': time_range_start.isoformat().replace('+00:00', 'Z'),
                    'timeRangeEnd': time_range_end.isoformat().replace('+00:00', 'Z'),
                    'numberOfMinutes': number_of_minutes,
                    'count': count,
                    'complete': complete,
                    'createdAt': now.isoformat().replace('+00:00', 'Z'),
                    'updatedAt': now.isoformat().replace('+00:00', 'Z')
                }
                
                # Add optional fields if provided
                if scorecard_id:
                    create_input['scorecardId'] = scorecard_id
                if score_id:
                    create_input['scoreId'] = score_id
                if cost is not None:
                    create_input['cost'] = cost
                if decision_count is not None:
                    create_input['decisionCount'] = decision_count
                if external_ai_api_count is not None:
                    create_input['externalAiApiCount'] = external_ai_api_count
                if cached_ai_api_count is not None:
                    create_input['cachedAiApiCount'] = cached_ai_api_count
                if error_count is not None:
                    create_input['errorCount'] = error_count
                if metadata is not None:
                    create_input['metadata'] = metadata
                
                result = client.execute(create_mutation, {'input': create_input})
                return cls.from_dict(result['createAggregatedMetrics'], client)
            else:
                raise
