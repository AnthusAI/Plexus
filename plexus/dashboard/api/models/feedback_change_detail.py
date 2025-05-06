import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Literal
from dataclasses import dataclass, field

from plexus.dashboard.api.models.base import BaseModel

if TYPE_CHECKING:
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.feedback_item import FeedbackItem

logger = logging.getLogger(__name__)

FeedbackChangeType = Literal['Response', 'Score', 'Calibration']

@dataclass
class FeedbackChangeDetail(BaseModel):
    """
    Represents an individual change record contributing to a FeedbackItem.
    Corresponds to the FeedbackChangeDetail model in the GraphQL schema.
    """
    id: Optional[str] = None
    feedbackItemId: Optional[str] = None
    changeType: Optional[FeedbackChangeType] = None
    externalId: Optional[str] = None # Maps to original Call Criteria change record ID (fqrc.id, fqsc.id, cs.id)
    changedAt: Optional[datetime] = None
    changedBy: Optional[str] = None
    initialAnswerValue: Optional[str] = None
    finalAnswerValue: Optional[str] = None
    initialCommentValue: Optional[str] = None
    finalCommentValue: Optional[str] = None
    editCommentValue: Optional[str] = None # Specific to score changes
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None # Added in schema

    # Relationships - lazy loaded
    feedbackItem: Optional['FeedbackItem'] = field(default=None, repr=False)

    _client: Optional['PlexusDashboardClient'] = field(default=None, repr=False)
    _raw_data: Optional[Dict[str, Any]] = field(default=None, repr=False)

    GRAPHQL_BASE_FIELDS = [
        'id', 'feedbackItemId', 'changeType', 'externalId', 'changedAt',
        'changedBy', 'initialAnswerValue', 'finalAnswerValue', 
        'initialCommentValue', 'finalCommentValue', 'editCommentValue',
        'createdAt', 'updatedAt'
    ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: Optional['PlexusDashboardClient'] = None) -> 'FeedbackChangeDetail':
        """
        Create a FeedbackChangeDetail instance from a dictionary.
        
        Args:
            data: Dictionary containing the FeedbackChangeDetail data.
            client: Optional API client to associate with the instance.
            
        Returns:
            A new FeedbackChangeDetail instance.
        """
        # Handle datetime fields
        if 'changedAt' in data and data['changedAt'] and isinstance(data['changedAt'], str):
            data['changedAt'] = datetime.fromisoformat(data['changedAt'].replace('Z', '+00:00'))
        if 'createdAt' in data and data['createdAt'] and isinstance(data['createdAt'], str):
            data['createdAt'] = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00'))
        if 'updatedAt' in data and data['updatedAt'] and isinstance(data['updatedAt'], str):
            data['updatedAt'] = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00'))
            
        # Create instance with data
        instance = cls(
            id=data.get('id'),
            feedbackItemId=data.get('feedbackItemId'),
            changeType=data.get('changeType'),
            externalId=data.get('externalId'),
            changedAt=data.get('changedAt'),
            changedBy=data.get('changedBy'),
            initialAnswerValue=data.get('initialAnswerValue'),
            finalAnswerValue=data.get('finalAnswerValue'),
            initialCommentValue=data.get('initialCommentValue'),
            finalCommentValue=data.get('finalCommentValue'),
            editCommentValue=data.get('editCommentValue'),
            createdAt=data.get('createdAt'),
            updatedAt=data.get('updatedAt')
        )
        
        # Set client and raw data
        instance._client = client
        instance._raw_data = data
        
        return instance

    @classmethod
    def _build_query(cls, fields: Optional[List[str]] = None, relationship_fields: Optional[Dict[str, List[str]]] = None) -> str:
        """Builds the base GraphQL query string."""
        if fields is None:
            fields = cls.GRAPHQL_BASE_FIELDS
        
        query = f"""
            {{
                {' '.join(fields)}
            }}
        """
        # Basic implementation, doesn't handle nested relationship fields yet
        return query

    @classmethod
    def get(cls, id: str, client: 'PlexusDashboardClient', fields: Optional[List[str]] = None) -> Optional['FeedbackChangeDetail']:
        """Retrieve a specific FeedbackChangeDetail by its ID."""
        query_name = "getFeedbackChangeDetail"
        query_body = cls._build_query(fields)
        
        # Construct the full query string
        query_string = f"""
            query GetFeedbackChangeDetail($id: ID!) {{
                {query_name}(id: $id) {query_body}
            }}
        """
        variables = {"id": id}
        
        logger.debug(f"Executing GraphQL query: {query_string} with variables: {variables}")
        # Call client.execute directly
        response = client.execute(query=query_string, variables=variables)
        
        if response and query_name in response and response[query_name]:
            item_data = response[query_name]
            return cls.from_dict(item_data, client=client)
        elif response and 'errors' in response:
            logger.error(f"GraphQL errors fetching FeedbackChangeDetail {id}: {response['errors']}")
        return None
        
    @classmethod
    def list(
        cls, 
        client: 'PlexusDashboardClient', 
        feedback_item_id: Optional[str] = None, 
        limit: int = 100, 
        next_token: Optional[str] = None,
        fields: Optional[List[str]] = None
    ) -> (List['FeedbackChangeDetail'], Optional[str]):
        """List FeedbackChangeDetails, typically filtered by feedbackItemId."""
        query_name = "listFeedbackChangeDetails" # Check if this is the correct list query name
        query_body_items = cls._build_query(fields)
        query_body = f"""
            {{
                items {query_body_items}
                nextToken
            }}
        """
        
        filters = {}
        if feedback_item_id:
            # Assuming filtering by feedbackItemId is supported
            # The actual filter structure might depend on the index definition
            # Example: filters["feedbackItemId"] = {"eq": feedback_item_id}
            # Let's use the GSI defined: byFeedbackItemIdAndChangedAt
            # We need to check the exact filter capabilities exposed by AppSync / Amplify
            # For now, assume simple equality filter works
            filters["feedbackItemId"] = {"eq": feedback_item_id}
            
        arguments = {
            "filter": filters if filters else None,
            "limit": limit,
            "nextToken": next_token
        }
        
        arguments = {k: v for k, v in arguments.items() if v is not None}

        # Construct the full query string
        # Argument definition depends on exact schema
        query_string = f"""
            query ListFeedbackChangeDetails(
                $filter: ModelFeedbackChangeDetailFilterInput, 
                $limit: Int, 
                $nextToken: String
            ) {{
                {query_name}(filter: $filter, limit: $limit, nextToken: $nextToken) {query_body}
            }}
        """
        
        logger.debug(f"Executing GraphQL query: {query_string} with variables: {arguments}")
        # Call client.execute directly
        response = client.execute(query=query_string, variables=arguments)
        
        items = []
        new_next_token = None
        
        if response and query_name in response and response[query_name]:
            list_data = response[query_name]
            items = [cls.from_dict(item_data, client=client) for item_data in list_data.get('items', [])]
            new_next_token = list_data.get('nextToken')
        elif response and 'errors' in response:
             logger.error(f"GraphQL errors listing FeedbackChangeDetails: {response['errors']}")

        return items, new_next_token

    @classmethod
    def create(cls, client: 'PlexusDashboardClient', data: Dict[str, Any]) -> Optional['FeedbackChangeDetail']:
        """Create a new FeedbackChangeDetail."""
        mutation_name = "createFeedbackChangeDetail"
        input_variable_name = "input"
        input_type = "CreateFeedbackChangeDetailInput!" # Assuming standard Amplify input type
        input_data = data # Assume data is already formatted correctly 
        
        return_fields = cls.GRAPHQL_BASE_FIELDS
        mutation_body = cls._build_query(return_fields)

        # Construct the full mutation string
        mutation_string = f"""
            mutation CreateFeedbackChangeDetail($input: {input_type}) {{
                {mutation_name}(input: $input) {mutation_body}
            }}
        """
        variables = {input_variable_name: input_data}

        logger.debug(f"Executing GraphQL mutation: {mutation_string} with variables: {variables}")
        # Call client.execute directly
        response = client.execute(query=mutation_string, variables=variables)

        if response and mutation_name in response and response[mutation_name]:
            created_data = response[mutation_name]
            return cls.from_dict(created_data, client=client)
        elif response and 'errors' in response:
             error_message = f"GraphQL errors creating FeedbackChangeDetail: {response['errors']}"
             logger.error(error_message)
             # Optionally raise an exception or return None
             raise Exception(error_message) # Raising exception to make failure explicit

        return None

    # Update/Delete methods would follow a similar pattern if needed 
    
    @classmethod
    def count_by_account_id(cls, account_id: str, client: 'PlexusDashboardClient') -> int:
        """
        Count the number of FeedbackChangeDetail records associated with a specific account.
        
        Since FeedbackChangeDetail doesn't have a direct accountId field, we'll need to:
        1. Get all FeedbackItems for the account
        2. Count all associated FeedbackChangeDetails
        
        Args:
            account_id: The ID of the account to count records for.
            client: The API client to use.
            
        Returns:
            int: The number of FeedbackChangeDetail records for the account.
        """
        # This requires a separate query that joins FeedbackChangeDetail data with account filtering
        # Since there's no direct query for this, we'll use a custom GraphQL query
        query = """
        query ListFeedbackChangeDetailsByAccount($accountId: String!) {
            listFeedbackItemByAccountIdAndUpdatedAt(accountId: $accountId) {
                items {
                    id
                    changeDetails {
                        items {
                            id
                        }
                        nextToken
                    }
                }
                nextToken
            }
        }
        """
        
        try:
            result = client.execute(query, {'accountId': account_id})
            
            if not result or 'listFeedbackItemByAccountIdAndUpdatedAt' not in result:
                logger.error(f"Failed to query FeedbackChangeDetails by account. Response: {result}")
                return 0
                
            items_data = result['listFeedbackItemByAccountIdAndUpdatedAt'].get('items', [])
            
            # Count all change details across all items
            total_count = sum(
                len(item.get('changeDetails', {}).get('items', [])) 
                for item in items_data if item
            )
            
            # Note: This doesn't handle pagination within nested changeDetails
            # For a complete implementation, you would need to handle both the item pagination
            # and the nested changeDetails pagination
            
            return total_count
        except Exception as e:
            logger.error(f"Error counting FeedbackChangeDetails for account {account_id}: {e}")
            return 0
    
    @classmethod
    def delete_all_by_account_id(cls, account_id: str, client: 'PlexusDashboardClient') -> int:
        """
        Delete all FeedbackChangeDetail records associated with a specific account.
        
        Since FeedbackChangeDetail doesn't have a direct accountId field, we'll need to:
        1. Get all FeedbackItems for the account
        2. For each FeedbackItem, delete all its FeedbackChangeDetails
        
        Args:
            account_id: The ID of the account to delete records for.
            client: The API client to use.
            
        Returns:
            int: The number of records deleted.
        """
        from plexus.dashboard.api.models.feedback_item import FeedbackItem
        
        deleted_count = 0
        batch_size = 50  # Process feedback items in batches
        
        # Use FeedbackItem to get all items for the account
        # Process in batches to avoid memory issues with large accounts
        next_token = None
        
        while True:
            # Get a batch of FeedbackItems
            items, next_token = FeedbackItem.list(
                client=client,
                account_id=account_id,
                limit=batch_size,
                next_token=next_token,
                fields=['id']  # Only fetch ID to minimize data transfer
            )
            
            if not items:
                break
                
            # For each FeedbackItem, delete all associated FeedbackChangeDetails
            for item in items:
                try:
                    # Fetch all change details for this item
                    change_details, change_next_token = cls.list(
                        client=client,
                        feedback_item_id=item.id,
                        limit=1000,
                        fields=['id']
                    )
                    
                    # Delete each change detail
                    for change_detail in change_details:
                        try:
                            mutation = """
                            mutation DeleteFeedbackChangeDetail($input: DeleteFeedbackChangeDetailInput!) {
                                deleteFeedbackChangeDetail(input: $input) {
                                    id
                                }
                            }
                            """
                            result = client.execute(mutation, {'input': {'id': change_detail.id}})
                            
                            if result and 'deleteFeedbackChangeDetail' in result and result['deleteFeedbackChangeDetail']:
                                deleted_count += 1
                            else:
                                logger.warning(f"Failed to delete FeedbackChangeDetail {change_detail.id}. Response: {result}")
                        except Exception as e:
                            logger.error(f"Error deleting FeedbackChangeDetail {change_detail.id}: {e}")
                    
                    # Handle pagination for change details if needed
                    while change_next_token:
                        change_details, change_next_token = cls.list(
                            client=client,
                            feedback_item_id=item.id,
                            limit=1000,
                            next_token=change_next_token,
                            fields=['id']
                        )
                        
                        for change_detail in change_details:
                            try:
                                mutation = """
                                mutation DeleteFeedbackChangeDetail($input: DeleteFeedbackChangeDetailInput!) {
                                    deleteFeedbackChangeDetail(input: $input) {
                                        id
                                    }
                                }
                                """
                                result = client.execute(mutation, {'input': {'id': change_detail.id}})
                                
                                if result and 'deleteFeedbackChangeDetail' in result and result['deleteFeedbackChangeDetail']:
                                    deleted_count += 1
                                else:
                                    logger.warning(f"Failed to delete FeedbackChangeDetail {change_detail.id}. Response: {result}")
                            except Exception as e:
                                logger.error(f"Error deleting FeedbackChangeDetail {change_detail.id}: {e}")
                    
                except Exception as e:
                    logger.error(f"Error processing FeedbackChangeDetails for FeedbackItem {item.id}: {e}")
            
            # If no next token, we've reached the end of the FeedbackItems
            if not next_token:
                break
                
        return deleted_count 