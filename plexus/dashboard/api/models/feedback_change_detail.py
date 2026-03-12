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
    def delete_all_by_account_id(cls, account_id: str, client: 'PlexusDashboardClient', 
                               progress=None, task_id=None) -> int:
        """
        Delete all FeedbackChangeDetail records associated with a specific account.
        
        Since FeedbackChangeDetail doesn't have a direct accountId field, we'll need to:
        1. Get all FeedbackItems for the account
        2. For each FeedbackItem, delete all its FeedbackChangeDetails
        
        Args:
            account_id: The ID of the account to delete records for.
            client: The API client to use.
            progress: Optional progress bar instance to use for tracking progress.
            task_id: Optional task ID within the progress bar to update.
            
        Returns:
            int: The number of records deleted.
        """
        from plexus.dashboard.api.models.feedback_item import FeedbackItem
        import time
        # Only import if we need to create our own progress bar
        if progress is None:
            from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn
        
        deleted_count = 0
        
        # First, get the total count for progress reporting
        total_details = cls.count_by_account_id(account_id, client)
        
        if total_details == 0:
            logger.info("No FeedbackChangeDetail records found to delete.")
            return 0
        
        # Determine if we need to create our own progress bar
        use_external_progress = progress is not None and task_id is not None
        internal_progress = None
        detail_task = task_id
        
        try:
            # Create our own progress bar if not provided
            if not use_external_progress:
                internal_progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(bar_width=50),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TextColumn("[cyan]{task.completed}/{task.total}"),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    expand=True
                )
                internal_progress.start()
                detail_task = internal_progress.add_task(f"[cyan]Deleting FeedbackChangeDetail records", total=total_details)
                # Use the internal progress from now on
                progress = internal_progress
            
            # Get all feedback item IDs for this account
            all_item_ids = []
            item_next_token = None
            
            # Fetch batch size can be larger since we're just getting IDs
            item_batch_size = 100
            
            progress.update(detail_task, description="[cyan]Collecting FeedbackItem IDs")
            # Collect all FeedbackItem IDs first
            while True:
                # Get a batch of FeedbackItems
                items, item_next_token = FeedbackItem.list(
                    client=client,
                    account_id=account_id,
                    limit=item_batch_size,
                    next_token=item_next_token,
                    fields=['id']
                )
                
                if not items:
                    break
                
                all_item_ids.extend([item.id for item in items])
                
                # If no next token, we've reached the end of the FeedbackItems
                if not item_next_token:
                    break
            
            # Collect all detail IDs first - this is much more efficient
            all_detail_ids = []
            progress.update(detail_task, description=f"[cyan]Collecting detail IDs from {len(all_item_ids)} items")
            
            for idx, item_id in enumerate(all_item_ids):
                try:
                    # Fetch all change details for this item (with pagination)
                    detail_next_token = None
                    
                    while True:
                        change_details, detail_next_token = cls.list(
                            client=client,
                            feedback_item_id=item_id,
                            limit=1000,  # Use larger limit to reduce API calls
                            next_token=detail_next_token,
                            fields=['id']
                        )
                        
                        all_detail_ids.extend([detail.id for detail in change_details])
                        
                        # Update progress description to show collection progress
                        progress.update(
                            detail_task, 
                            description=f"[cyan]Collecting detail IDs ({len(all_detail_ids)}/{total_details}, item {idx+1}/{len(all_item_ids)})"
                        )
                        
                        if not detail_next_token:
                            break
                        
                except Exception as e:
                    logger.error(f"Error fetching FeedbackChangeDetails for FeedbackItem {item_id}: {e}")
            
            # Reset progress for deletion phase
            progress.update(detail_task, completed=0, description="[cyan]Deleting FeedbackChangeDetail records")
            
            # Now delete all details in batches
            batch_size = 25  # GraphQL has limits on mutation complexity
            
            for i in range(0, len(all_detail_ids), batch_size):
                batch = all_detail_ids[i:i+batch_size]
                
                # Construct batch mutation with alias for each deletion
                try:
                    batch_operations = []
                    for detail_id in batch:
                        # Use clean ID (alphanumeric only) for the alias to avoid GraphQL errors
                        clean_id = ''.join(c for c in detail_id if c.isalnum())
                        batch_operations.append(
                            f"""
                            delete{clean_id}: deleteFeedbackChangeDetail(input: {{id: "{detail_id}"}}) {{
                                id
                            }}
                            """
                        )
                    
                    # Execute batch mutation if we have operations
                    if batch_operations:
                        mutation = f"""
                        mutation BatchDeleteFeedbackChangeDetails {{
                            {" ".join(batch_operations)}
                        }}
                        """
                        
                        result = client.execute(query=mutation)
                        
                        # Count successful deletions
                        if result:
                            for detail_id in batch:
                                clean_id = ''.join(c for c in detail_id if c.isalnum())
                                field_name = f"delete{clean_id}"
                                if field_name in result and result[field_name] and result[field_name].get('id'):
                                    deleted_count += 1
                        
                except Exception as e:
                    # If batch deletion fails, fall back to individual deletions
                    logger.warning(f"Batch deletion failed, falling back to individual deletions: {e}")
                    
                    for detail_id in batch:
                        try:
                            mutation = """
                            mutation DeleteFeedbackChangeDetail($input: DeleteFeedbackChangeDetailInput!) {
                                deleteFeedbackChangeDetail(input: $input) {
                                    id
                                }
                            }
                            """
                            result = client.execute(query=mutation, variables={'input': {'id': detail_id}})
                            
                            if result and 'deleteFeedbackChangeDetail' in result and result['deleteFeedbackChangeDetail']:
                                deleted_count += 1
                            else:
                                logger.warning(f"Failed to delete FeedbackChangeDetail {detail_id}. Response: {result}")
                        except Exception as individual_e:
                            logger.error(f"Error deleting FeedbackChangeDetail {detail_id}: {individual_e}")
                
                # Update progress after each batch
                progress.update(detail_task, advance=len(batch))
                
                # Small delay to prevent API rate limiting
                time.sleep(0.1)
        
        finally:
            # Clean up if we created our own progress bar
            if internal_progress is not None:
                internal_progress.stop()
        
        logger.info(f"Deleted {deleted_count} FeedbackChangeDetail records for account {account_id}")
        return deleted_count 