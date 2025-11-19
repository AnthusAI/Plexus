"""
GraphQL client for updating AggregatedMetrics table.
"""

import json
import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime


class GraphQLClient:
    """Client for interacting with the Plexus GraphQL API."""
    
    def __init__(self, endpoint: str, api_key: str):
        """
        Initialize GraphQL client.
        
        Args:
            endpoint: GraphQL API endpoint URL
            api_key: API key for authentication
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key
        }
    
    def execute_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a GraphQL query.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            
        Returns:
            Response data
            
        Raises:
            Exception: If the query fails
        """
        payload = {
            'query': query,
            'variables': variables
        }
        
        response = requests.post(
            self.endpoint,
            headers=self.headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"GraphQL request failed: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if 'errors' in result:
            raise Exception(f"GraphQL errors: {json.dumps(result['errors'])}")
        
        return result.get('data', {})
    
    def get_aggregated_metrics(self, 
                               account_id: str,
                               record_type: str,
                               time_range_start: str,
                               number_of_minutes: int,
                               scorecard_id: Optional[str] = None,
                               score_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Query for existing AggregatedMetrics record.
        
        Args:
            account_id: Account ID
            record_type: Type of record ('items', 'scoreResults', 'tasks', 'evaluations')
            time_range_start: ISO datetime string for bucket start
            number_of_minutes: Bucket duration in minutes
            scorecard_id: Optional scorecard filter
            score_id: Optional score filter
            
        Returns:
            Existing record if found, None otherwise
        """
        query = """
        query ListAggregatedMetrics(
            $accountId: String!,
            $recordType: String!,
            $timeRangeStart: String!
        ) {
            listAggregatedMetricsByRecordTypeAndTimeRangeStart(
                recordType: $recordType,
                timeRangeStart: { eq: $timeRangeStart },
                filter: {
                    accountId: { eq: $accountId }
                }
            ) {
                items {
                    id
                    accountId
                    scorecardId
                    scoreId
                    recordType
                    timeRangeStart
                    timeRangeEnd
                    numberOfMinutes
                    count
                    complete
                }
            }
        }
        """
        
        variables = {
            'accountId': account_id,
            'recordType': record_type,
            'timeRangeStart': time_range_start
        }
        
        try:
            data = self.execute_query(query, variables)
            items = data.get('listAggregatedMetricsByRecordTypeAndTimeRangeStart', {}).get('items', [])
            
            # Filter by numberOfMinutes, scorecardId, scoreId
            for item in items:
                if item['numberOfMinutes'] != number_of_minutes:
                    continue
                if scorecard_id and item.get('scorecardId') != scorecard_id:
                    continue
                if score_id and item.get('scoreId') != score_id:
                    continue
                return item
            
            return None
        except Exception as e:
            print(f"Error querying AggregatedMetrics: {e}")
            return None
    
    def create_aggregated_metrics(self,
                                  account_id: str,
                                  record_type: str,
                                  time_range_start: str,
                                  time_range_end: str,
                                  number_of_minutes: int,
                                  count: int,
                                  complete: bool = False,
                                  scorecard_id: Optional[str] = None,
                                  score_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new AggregatedMetrics record.
        
        Args:
            account_id: Account ID
            record_type: Type of record
            time_range_start: ISO datetime string
            time_range_end: ISO datetime string
            number_of_minutes: Bucket duration
            count: Aggregated count
            complete: Whether the bucket is complete
            scorecard_id: Optional scorecard filter
            score_id: Optional score filter
            
        Returns:
            Created record
        """
        mutation = """
        mutation CreateAggregatedMetrics($input: CreateAggregatedMetricsInput!) {
            createAggregatedMetrics(input: $input) {
                id
                accountId
                recordType
                timeRangeStart
                timeRangeEnd
                numberOfMinutes
                count
                complete
            }
        }
        """
        
        now = datetime.utcnow().isoformat() + 'Z'
        
        input_data = {
            'accountId': account_id,
            'recordType': record_type,
            'timeRangeStart': time_range_start,
            'timeRangeEnd': time_range_end,
            'numberOfMinutes': number_of_minutes,
            'count': count,
            'complete': complete,
            'createdAt': now,
            'updatedAt': now
        }
        
        if scorecard_id:
            input_data['scorecardId'] = scorecard_id
        if score_id:
            input_data['scoreId'] = score_id
        
        variables = {'input': input_data}
        
        data = self.execute_query(mutation, variables)
        return data.get('createAggregatedMetrics', {})
    
    def update_aggregated_metrics(self,
                                  record_id: str,
                                  count: int,
                                  complete: bool = False) -> Dict[str, Any]:
        """
        Update an existing AggregatedMetrics record.
        
        Args:
            record_id: Record ID to update
            count: New count value
            complete: Whether the bucket is complete
            
        Returns:
            Updated record
        """
        mutation = """
        mutation UpdateAggregatedMetrics($input: UpdateAggregatedMetricsInput!) {
            updateAggregatedMetrics(input: $input) {
                id
                count
                complete
                updatedAt
            }
        }
        """
        
        now = datetime.utcnow().isoformat() + 'Z'
        
        variables = {
            'input': {
                'id': record_id,
                'count': count,
                'complete': complete,
                'updatedAt': now
            }
        }
        
        data = self.execute_query(mutation, variables)
        return data.get('updateAggregatedMetrics', {})
    
    def upsert_aggregated_metrics(self,
                                  account_id: str,
                                  record_type: str,
                                  time_range_start: str,
                                  time_range_end: str,
                                  number_of_minutes: int,
                                  count: int,
                                  complete: bool = False,
                                  scorecard_id: Optional[str] = None,
                                  score_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create or update an AggregatedMetrics record.
        
        Args:
            account_id: Account ID
            record_type: Type of record
            time_range_start: ISO datetime string
            time_range_end: ISO datetime string
            number_of_minutes: Bucket duration
            count: Aggregated count
            complete: Whether the bucket is complete
            scorecard_id: Optional scorecard filter
            score_id: Optional score filter
            
        Returns:
            Created or updated record
        """
        # Try to find existing record
        existing = self.get_aggregated_metrics(
            account_id=account_id,
            record_type=record_type,
            time_range_start=time_range_start,
            number_of_minutes=number_of_minutes,
            scorecard_id=scorecard_id,
            score_id=score_id
        )
        
        if existing:
            # Update existing record
            return self.update_aggregated_metrics(
                record_id=existing['id'],
                count=count,
                complete=complete
            )
        else:
            # Create new record
            return self.create_aggregated_metrics(
                account_id=account_id,
                record_type=record_type,
                time_range_start=time_range_start,
                time_range_end=time_range_end,
                number_of_minutes=number_of_minutes,
                count=count,
                complete=complete,
                scorecard_id=scorecard_id,
                score_id=score_id
            )


def get_client_from_env() -> GraphQLClient:
    """
    Create a GraphQL client from environment variables.
    
    Looks for PLEXUS_API_URL and PLEXUS_API_KEY (developer .env format)
    or GRAPHQL_ENDPOINT and GRAPHQL_API_KEY (Lambda environment format).
    
    Returns:
        Configured GraphQL client
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Try developer .env format first
    endpoint = os.environ.get('PLEXUS_API_URL') or os.environ.get('GRAPHQL_ENDPOINT')
    api_key = os.environ.get('PLEXUS_API_KEY') or os.environ.get('GRAPHQL_API_KEY')
    
    if not endpoint:
        raise ValueError(
            "GraphQL endpoint not found. Set PLEXUS_API_URL or GRAPHQL_ENDPOINT environment variable."
        )
    if not api_key:
        raise ValueError(
            "GraphQL API key not found. Set PLEXUS_API_KEY or GRAPHQL_API_KEY environment variable."
        )
    
    return GraphQLClient(endpoint, api_key)

