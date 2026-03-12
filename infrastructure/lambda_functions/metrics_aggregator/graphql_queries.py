"""
GraphQL queries for fetching records to count.

This module handles querying DynamoDB via GraphQL with pagination
to get all records in a time window for counting.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


def query_items_in_window(graphql_client, 
                          account_id: str, 
                          start_time: datetime, 
                          end_time: datetime) -> List[Dict[str, Any]]:
    """
    Query all Items in a time window with pagination.
    
    Args:
        graphql_client: GraphQL client instance
        account_id: Account ID to filter by
        start_time: Start of time window
        end_time: End of time window
        
    Returns:
        List of all items (id, createdAt, and createdByType for filtering)
    """
    query = """
    query ListItemsByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listItemByAccountIdAndCreatedAt(
            accountId: $accountId,
            createdAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                createdAt
                createdByType
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listItemByAccountIdAndCreatedAt'
    )


def query_score_results_in_window(graphql_client,
                                  account_id: str,
                                  start_time: datetime,
                                  end_time: datetime) -> List[Dict[str, Any]]:
    """
    Query all ScoreResults in a time window with pagination.
    
    Note: Uses updatedAt due to GSI limit (20 max per table).
    This may cause some double-counting if records are updated frequently.
    
    Args:
        graphql_client: GraphQL client instance
        account_id: Account ID to filter by
        start_time: Start of time window
        end_time: End of time window
        
    Returns:
        List of all score results (id, updatedAt, and type for filtering)
    """
    query = """
    query ListScoreResultsByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listScoreResultByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                updatedAt
                type
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listScoreResultByAccountIdAndUpdatedAt'
    )


def query_tasks_in_window(graphql_client,
                          account_id: str,
                          start_time: datetime,
                          end_time: datetime) -> List[Dict[str, Any]]:
    """
    Query all Tasks in a time window with pagination.
    
    Args:
        graphql_client: GraphQL client instance
        account_id: Account ID to filter by
        start_time: Start of time window
        end_time: End of time window
        
    Returns:
        List of all tasks (id and updatedAt only for efficiency)
    """
    query = """
    query ListTasksByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listTaskByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                updatedAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listTaskByAccountIdAndUpdatedAt'
    )


def query_evaluations_in_window(graphql_client,
                                account_id: str,
                                start_time: datetime,
                                end_time: datetime) -> List[Dict[str, Any]]:
    """
    Query all Evaluations in a time window with pagination.
    
    Args:
        graphql_client: GraphQL client instance
        account_id: Account ID to filter by
        start_time: Start of time window
        end_time: End of time window
        
    Returns:
        List of all evaluations (id and updatedAt only for efficiency)
    """
    query = """
    query ListEvaluationsByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listEvaluationByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                updatedAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listEvaluationByAccountIdAndUpdatedAt'
    )


def query_feedback_items_in_window(graphql_client,
                                   account_id: str,
                                   start_time: datetime,
                                   end_time: datetime) -> List[Dict[str, Any]]:
    """Query all FeedbackItems in a time window with pagination."""
    query = """
    query ListFeedbackItemsByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listFeedbackItemByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                updatedAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listFeedbackItemByAccountIdAndUpdatedAt'
    )


def query_procedures_in_window(graphql_client,
                               account_id: str,
                               start_time: datetime,
                               end_time: datetime) -> List[Dict[str, Any]]:
    """Query all Procedures in a time window with pagination."""
    query = """
    query ListProceduresByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listProcedureByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                updatedAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listProcedureByAccountIdAndUpdatedAt'
    )


def query_graph_nodes_in_window(graphql_client,
                                account_id: str,
                                start_time: datetime,
                                end_time: datetime) -> List[Dict[str, Any]]:
    """Query all GraphNodes in a time window with pagination."""
    query = """
    query ListGraphNodesByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listGraphNodeByAccountIdAndCreatedAt(
            accountId: $accountId,
            createdAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                createdAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listGraphNodeByAccountIdAndCreatedAt'
    )


def query_chat_sessions_in_window(graphql_client,
                                  account_id: str,
                                  start_time: datetime,
                                  end_time: datetime) -> List[Dict[str, Any]]:
    """Query all ChatSessions in a time window with pagination."""
    query = """
    query ListChatSessionsByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listChatSessionByAccountIdAndUpdatedAt(
            accountId: $accountId,
            updatedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                updatedAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listChatSessionByAccountIdAndUpdatedAt'
    )


def query_chat_messages_in_window(graphql_client,
                                  account_id: str,
                                  start_time: datetime,
                                  end_time: datetime) -> List[Dict[str, Any]]:
    """Query all ChatMessages in a time window with pagination."""
    query = """
    query ListChatMessagesByTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listChatMessageByAccountIdAndCreatedAt(
            accountId: $accountId,
            createdAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                createdAt
            }
            nextToken
        }
    }
    """
    
    return _paginated_query(
        graphql_client,
        query,
        {
            'accountId': account_id,
            'startTime': start_time.isoformat().replace('+00:00', 'Z'),
            'endTime': end_time.isoformat().replace('+00:00', 'Z')
        },
        'listChatMessageByAccountIdAndCreatedAt'
    )


def _paginated_query(graphql_client,
                    query: str,
                    variables: Dict[str, Any],
                    response_key: str) -> List[Dict[str, Any]]:
    """
    Execute a paginated GraphQL query and collect all results.
    
    Args:
        graphql_client: GraphQL client instance
        query: GraphQL query string
        variables: Query variables (without nextToken)
        response_key: Key in response data containing items and nextToken
        
    Returns:
        List of all items from all pages
    """
    all_items = []
    next_token = None
    page_count = 0
    
    while True:
        page_count += 1
        
        # Add nextToken to variables if we have one
        query_variables = {**variables}
        if next_token:
            query_variables['nextToken'] = next_token
        
        # Execute query
        try:
            data = graphql_client.execute_query(query, query_variables)
            response = data.get(response_key, {})
            
            # Get items from this page
            items = response.get('items', [])
            all_items.extend(items)
            
            # Only log if multiple pages (single page is common and not interesting)
            if page_count > 1 or next_token:
                print(f"  Page {page_count}: +{len(items)} records (total: {len(all_items)})")
            
            # Check if there are more pages
            next_token = response.get('nextToken')
            if not next_token:
                break
                
        except Exception as e:
            print(f"  ✗ Error on page {page_count}: {e}")
            # Return what we have so far rather than failing completely
            break
    
    if page_count > 1:
        print(f"  Fetched {len(all_items)} records across {page_count} pages")
    
    return all_items


# Map record types to query functions
# Note: chatMessages excluded - no accountId field, belongs to sessions
QUERY_FUNCTIONS = {
    'items': query_items_in_window,
    'scoreResults': query_score_results_in_window,
    'tasks': query_tasks_in_window,
    'evaluations': query_evaluations_in_window,
    'feedbackItems': query_feedback_items_in_window,
    'procedures': query_procedures_in_window,
    'graphNodes': query_graph_nodes_in_window,
    'chatSessions': query_chat_sessions_in_window
}


def query_records_for_counting(graphql_client,
                               record_type: str,
                               account_id: str,
                               start_time: datetime,
                               end_time: datetime) -> List[Dict[str, Any]]:
    """
    Query records of a specific type in a time window.
    
    Args:
        graphql_client: GraphQL client instance
        record_type: Type of records to query
        account_id: Account ID
        start_time: Start of time window
        end_time: End of time window
        
    Returns:
        List of records with timestamps
        
    Raises:
        ValueError: If record_type is not supported
    """
    query_func = QUERY_FUNCTIONS.get(record_type)
    if not query_func:
        raise ValueError(f"Unsupported record type: {record_type}")
    
    return query_func(graphql_client, account_id, start_time, end_time)

