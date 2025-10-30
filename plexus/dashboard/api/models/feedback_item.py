import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Tuple
from dataclasses import dataclass, field

from plexus.dashboard.api.models.base import BaseModel
from plexus.dashboard.api.models.feedback_change_detail import FeedbackChangeDetail

if TYPE_CHECKING:
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.account import Account
    from plexus.dashboard.api.models.scorecard import Scorecard
    from plexus.dashboard.api.models.score import Score
    from plexus.dashboard.api.models.item import Item

logger = logging.getLogger(__name__)

@dataclass
class FeedbackItem(BaseModel):
    """
    Represents aggregated feedback results for a specific form/question combination.
    Corresponds to the FeedbackItem model in the GraphQL schema.
    """
    id: Optional[str] = None
    accountId: Optional[str] = None
    scorecardId: Optional[str] = None
    cacheKey: Optional[str] = None # Maps to Call Criteria form_id
    scoreId: Optional[str] = None # Maps to Call Criteria question_id
    itemId: Optional[str] = None # Add the itemId field
    initialAnswerValue: Optional[str] = None
    finalAnswerValue: Optional[str] = None
    initialCommentValue: Optional[str] = None
    finalCommentValue: Optional[str] = None
    editCommentValue: Optional[str] = None
    editedAt: Optional[datetime] = None  # Add the missing editedAt field
    editorName: Optional[str] = None
    isAgreement: Optional[bool] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    # Relationships - lazy loaded
    account: Optional['Account'] = field(default=None, repr=False)
    scorecard: Optional['Scorecard'] = field(default=None, repr=False)
    score: Optional['Score'] = field(default=None, repr=False)
    item: Optional['Item'] = field(default=None, repr=False)  # Add the item relationship
    scoreResults: Optional[Any] = field(default=None, repr=False)  # Add scoreResults relationship (can be dict or list)

    _client: Optional['PlexusDashboardClient'] = field(default=None, repr=False)
    _raw_data: Optional[Dict[str, Any]] = field(default=None, repr=False)

    GRAPHQL_BASE_FIELDS = [
        'id', 'accountId', 'scorecardId', 'cacheKey', 'scoreId', 'itemId',
        'initialAnswerValue', 'finalAnswerValue', 'initialCommentValue',
        'finalCommentValue', 'editCommentValue', 'editedAt', 'editorName', 'isAgreement', 'createdAt', 'updatedAt'
    ]
    GRAPHQL_RELATIONSHIP_FIELDS = {
        # Relationship fields can be added here if needed
    }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: Optional['PlexusDashboardClient'] = None) -> 'FeedbackItem':
        """
        Create a FeedbackItem instance from a dictionary.
        
        Args:
            data: Dictionary containing the FeedbackItem data.
            client: Optional API client to associate with the instance.
            
        Returns:
            A new FeedbackItem instance.
        """
        # Handle datetime fields
        if 'createdAt' in data and data['createdAt'] and isinstance(data['createdAt'], str):
            data['createdAt'] = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00'))
        if 'updatedAt' in data and data['updatedAt'] and isinstance(data['updatedAt'], str):
            data['updatedAt'] = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00'))
        if 'editedAt' in data and data['editedAt'] and isinstance(data['editedAt'], str):
            data['editedAt'] = datetime.fromisoformat(data['editedAt'].replace('Z', '+00:00'))
            
        # Create instance with data
        instance = cls(
            id=data.get('id'),
            accountId=data.get('accountId'),
            scorecardId=data.get('scorecardId'),
            cacheKey=data.get('cacheKey'),
            scoreId=data.get('scoreId'),
            itemId=data.get('itemId'),
            initialAnswerValue=data.get('initialAnswerValue'),
            finalAnswerValue=data.get('finalAnswerValue'),
            initialCommentValue=data.get('initialCommentValue'),
            finalCommentValue=data.get('finalCommentValue'),
            editCommentValue=data.get('editCommentValue'),
            editedAt=data.get('editedAt'),
            editorName=data.get('editorName'),
            isAgreement=data.get('isAgreement'),
            createdAt=data.get('createdAt'),
            updatedAt=data.get('updatedAt')
        )
        
        # Set client and raw data
        instance._client = client
        instance._raw_data = data
        
        # Handle nested relationships if present in the data
        if 'item' in data and data['item']:
            # Import here to avoid circular imports
            from plexus.dashboard.api.models.item import Item
            instance.item = Item.from_dict(data['item'], client=client)
        
        # Handle scoreResults relationship if present (keep as raw dict/list for flexibility)
        if 'scoreResults' in data and data['scoreResults']:
            instance.scoreResults = data['scoreResults']
        
        return instance

    @classmethod
    def _build_query(
        cls, 
        fields: Optional[List[str]] = None, 
        relationship_fields: Optional[Dict[str, List[str]]] = None
    ) -> str:
        """Builds the GraphQL query string including specified relationships."""
        if fields is None:
            fields = cls.GRAPHQL_BASE_FIELDS
        if relationship_fields is None:
            relationship_fields = {}
            
        query_parts = list(fields)
        
        for rel_name, rel_fields in relationship_fields.items():
            # Add handling for relationships like item, account, scorecard, score
            if rel_fields:
                rel_query = f"{rel_name} {{ {' '.join(rel_fields)} }}"
                query_parts.append(rel_query)
            
        return f"{{ {' '.join(query_parts)} }}"

    @classmethod
    def get(cls, id: str, client: 'PlexusDashboardClient', fields: Optional[List[str]] = None, relationship_fields: Optional[Dict[str, List[str]]] = None) -> Optional['FeedbackItem']:
        """Retrieve a specific FeedbackItem by its ID."""
        query_name = "getFeedbackItem"
        query_body = cls._build_query(fields, relationship_fields)
        
        # Construct the full query string
        query_string = f"""
            query GetFeedbackItem($id: ID!) {{
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
             logger.error(f"GraphQL errors fetching FeedbackItem {id}: {response['errors']}")
        return None

    @classmethod
    def list(
        cls, 
        client: 'PlexusDashboardClient', 
        account_id: Optional[str] = None, 
        scorecard_id: Optional[str] = None,
        score_id: Optional[str] = None,
        cache_key: Optional[str] = None,
        limit: int = 100, 
        next_token: Optional[str] = None,
        fields: Optional[List[str]] = None,
        relationship_fields: Optional[Dict[str, List[str]]] = None,
        filter: Optional[Dict[str, Any]] = None,
        index_name: Optional[str] = None,
        sort_condition: Optional[Dict[str, Any]] = None
    ) -> (List['FeedbackItem'], Optional[str]):
        """
        List FeedbackItems with optional filtering.
        
        Args:
            client: The API client to use
            account_id: Optional account ID to filter by
            scorecard_id: Optional scorecard ID to filter by
            score_id: Optional score ID to filter by
            cache_key: Optional cache key to filter by
            limit: Maximum number of items to return
            next_token: Pagination token from a previous request
            fields: Optional list of fields to include in the response
            relationship_fields: Optional relationship fields to include
            filter: Optional additional filter parameters
            index_name: Optional GSI name to use (e.g., "byAccountScorecardScoreUpdatedAt")
            sort_condition: Optional sort condition for the GSI query, particularly for date range filtering
            
        Returns:
            Tuple of (list of FeedbackItem objects, next pagination token)
        """
        query_name = "listFeedbackItems"
        
        # Handle specific indexes
        if index_name:
            if index_name == "byAccountScorecardScoreUpdatedAt":
                if not account_id:
                    raise ValueError("account_id is required when using byAccountScorecardScoreUpdatedAt index")
                query_name = "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt"
            else:
                # Add support for other indexes as needed
                logger.warning(f"Unknown index name: {index_name}, falling back to standard query")
        # Fixed for accounts with just account_id - corrected the field name to match schema
        elif account_id and not (scorecard_id or score_id or cache_key):
            query_name = "listFeedbackItemByAccountIdAndUpdatedAt"
            
        query_body_items = cls._build_query(fields, relationship_fields)
        query_body = f"""
            {{
                items {query_body_items}
                nextToken
            }}
        """
        
        # Prepare variables based on query type
        variables = {}
        
        if query_name == "listFeedbackItemByAccountIdAndUpdatedAt":
            variables = {
                "accountId": account_id,
                "limit": limit,
                "nextToken": next_token
            }
            # Construct query string for account-based list
            query_string = f"""
                query ListFeedbackItemsByAccount($accountId: String!, $limit: Int, $nextToken: String) {{
                    {query_name}(accountId: $accountId, limit: $limit, nextToken: $nextToken) {query_body}
                }}
            """
        elif query_name == "listFeedbackItemByAccountScorecardScoreUpdatedAt":
            variables = {
                "accountId": account_id,
                "limit": limit,
                "nextToken": next_token
            }
            
            # If sort_condition is not provided, build it from parameters
            if not sort_condition and scorecard_id:
                local_sort_condition = {
                    "scorecardId": {"eq": scorecard_id}
                }
                if score_id:
                    local_sort_condition["scoreId"] = {"eq": score_id}
                    
                    # Add updatedAt filter from the filter parameter if provided
                    if filter and 'updatedAt' in filter:
                        local_sort_condition["updatedAt"] = filter['updatedAt']
                
                # Use our locally built sort condition
                sort_condition = local_sort_condition
            
            # Add sort condition to variables if we have any
            if sort_condition:
                variables["sortCondition"] = sort_condition
                
            # Construct query string for the GSI - making sure accountId is passed directly
            query_string = f"""
                query ListFeedbackItemsByGSI(
                    $accountId: String!, 
                    $sortCondition: ModelFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAtCompositeKeyConditionInput,
                    $limit: Int, 
                    $nextToken: String
                ) {{
                    {query_name}(
                        accountId: $accountId, 
                        sortCondition: $sortCondition,
                        limit: $limit, 
                        nextToken: $nextToken
                    ) {query_body}
                }}
            """
        else:
            # Standard filtering logic for regular list
            filters = filter or {}
            if account_id and 'accountId' not in filters:
                filters["accountId"] = {"eq": account_id}
            if scorecard_id and 'scorecardId' not in filters:
                filters["scorecardId"] = {"eq": scorecard_id}
            if score_id and 'scoreId' not in filters:
                filters["scoreId"] = {"eq": score_id}
            if cache_key and 'cacheKey' not in filters:
                filters["cacheKey"] = {"eq": cache_key}
                
            variables = {
                "filter": filters if filters else None,
                "limit": limit,
                "nextToken": next_token
            }
            
            # Construct the full query string with arguments for standard list
            query_string = f"""
                query ListFeedbackItems(
                    $filter: ModelFeedbackItemFilterInput, 
                    $limit: Int, 
                    $nextToken: String
                ) {{
                    {query_name}(filter: $filter, limit: $limit, nextToken: $nextToken) {query_body}
                }}
            """
        
        # Remove None values from variables
        variables = {k: v for k, v in variables.items() if v is not None}
        
        logger.debug(f"Executing GraphQL query: {query_string} with variables: {variables}")
        # Call client.execute directly
        response = client.execute(query=query_string, variables=variables)
        
        items = []
        new_next_token = None
        
        if response and query_name in response and response[query_name]:
            list_data = response[query_name]
            items = [cls.from_dict(item_data, client=client) for item_data in list_data.get('items', [])]
            new_next_token = list_data.get('nextToken')
        elif response and 'errors' in response:
             logger.error(f"GraphQL errors listing FeedbackItems: {response['errors']}")

        return items, new_next_token

    @classmethod
    def create(cls, client: 'PlexusDashboardClient', data: Dict[str, Any]) -> Optional['FeedbackItem']:
        """Create a new FeedbackItem."""
        mutation_name = "createFeedbackItem"
        input_variable_name = "input"
        input_type = "CreateFeedbackItemInput!" # Assuming standard Amplify input type
        input_data = data # Assume data is already formatted correctly
        
        return_fields = cls.GRAPHQL_BASE_FIELDS 
        mutation_body = cls._build_query(return_fields) # Just get base fields back for now

        # Construct the full mutation string
        mutation_string = f"""
            mutation CreateFeedbackItem($input: {input_type}) {{
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
             error_message = f"GraphQL errors creating FeedbackItem: {response['errors']}"
             logger.error(error_message)
             # Optionally raise an exception or return None
             raise Exception(error_message) # Raising exception to make failure explicit

        return None
        
    # --- Relationship Loading Methods ---
    
    def load_change_details(self, force_reload: bool = False):
        """Loads the related FeedbackChangeDetail records."""
        if not self._client or not self.id:
            logger.warning("Cannot load change details without a client and FeedbackItem ID.")
            return
            
        if self.changeDetails is None or force_reload:
            logger.debug(f"Loading change details for FeedbackItem {self.id}")
            # Paginate if necessary
            details = []
            next_token = None
            while True:
                results, next_token = FeedbackChangeDetail.list(
                    client=self._client, 
                    feedback_item_id=self.id, 
                    limit=1000, # Adjust limit as needed
                    next_token=next_token
                )
                details.extend(results)
                if not next_token:
                    break
            self.changeDetails = details
            logger.debug(f"Loaded {len(self.changeDetails)} change details for FeedbackItem {self.id}")

    # Add similar load methods for account, scorecard, score if needed

    # Update/Delete methods would follow a similar pattern if needed 
    
    @classmethod
    def count_by_account_id(cls, account_id: str, client: 'PlexusDashboardClient') -> int:
        """
        Count the number of FeedbackItem records for a specific account.
        
        Args:
            account_id: The ID of the account to count records for.
            client: The API client to use.
            
        Returns:
            int: The number of FeedbackItem records for the account.
        """
        # Use the list method with a limit but only count items
        items, next_token = cls.list(
            client=client,
            account_id=account_id,
            limit=1000,  # Use a large limit to minimize pagination
            fields=['id']  # Only fetch ID to minimize data transfer
        )
        
        total_count = len(items)
        
        # Handle pagination
        while next_token:
            items, next_token = cls.list(
                client=client,
                account_id=account_id,
                limit=1000,
                next_token=next_token,
                fields=['id']
            )
            total_count += len(items)
            
        return total_count
    
    @classmethod
    def delete_all_by_account_id(cls, account_id: str, client: 'PlexusDashboardClient', 
                               progress=None, task_id=None) -> int:
        """
        Delete all FeedbackItem records for a specific account.
        
        Args:
            account_id: The ID of the account to delete records for.
            client: The API client to use.
            progress: Optional progress bar instance to use for tracking progress.
            task_id: Optional task ID within the progress bar to update.
            
        Returns:
            int: The number of records deleted.
        """
        import time
        # Only import if we need to create our own progress bar
        if progress is None:
            from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn

        deleted_count = 0
        batch_size = 50  # Delete in batches to avoid overwhelming the API
        
        # First, get the total count for progress reporting
        total_items = cls.count_by_account_id(account_id, client)
        
        if total_items == 0:
            logger.info("No FeedbackItem records found to delete.")
            return 0
            
        # Determine if we need to create our own progress bar
        use_external_progress = progress is not None and task_id is not None
        internal_progress = None
        task = task_id
        
        try:
            # Create our own progress bar if not provided
            if not use_external_progress:
                internal_progress = Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(bar_width=50),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TextColumn("[cyan]{task.completed}/{task.total}"),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    expand=True
                )
                internal_progress.start()
                task = internal_progress.add_task(f"[cyan]Deleting FeedbackItem records", total=total_items)
                # Use the internal progress from now on
                progress = internal_progress
            
            # First, fetch all IDs (this is more efficient than fetching in batches)
            all_ids = []
            next_token = None
            
            logger.info(f"Collecting all FeedbackItem IDs for account {account_id}...")
            while True:
                # Fetch a batch of IDs
                items, next_token = cls.list(
                    client=client,
                    account_id=account_id,
                    limit=1000,  # Use a large limit to minimize pagination API calls
                    next_token=next_token,
                    fields=['id']  # Only fetch ID to minimize data transfer
                )
                
                if not items:
                    break
                    
                # Extract IDs from items
                all_ids.extend([item.id for item in items])
                
                # Update progress bar for collection phase
                progress.update(task, description=f"[cyan]Collecting IDs ({len(all_ids)}/{total_items})")
                
                # If no next token, we've reached the end
                if not next_token:
                    break
            
            # Reset progress bar for deletion phase
            progress.update(task, description="[cyan]Deleting FeedbackItem records", completed=0)
            
            # Process deletions in batches
            for i in range(0, len(all_ids), batch_size):
                batch = all_ids[i:i+batch_size]
                
                # Construct batch mutation
                batch_operations = []
                for item_id in batch:
                    # Clean ID for alias to avoid GraphQL errors
                    clean_id = ''.join(c for c in item_id if c.isalnum())
                    batch_operations.append(
                        f"""
                        delete{clean_id}: deleteFeedbackItem(input: {{id: "{item_id}"}}) {{
                            id
                        }}
                        """
                    )
                
                # Execute batch mutation
                if batch_operations:
                    try:
                        mutation = f"""
                        mutation BatchDeleteFeedbackItems {{
                            {" ".join(batch_operations)}
                        }}
                        """
                        
                        result = client.execute(query=mutation)
                        
                        # Check results and count successful deletions
                        if result:
                            for item_id in batch:
                                clean_id = ''.join(c for c in item_id if c.isalnum())
                                field_name = f"delete{clean_id}"
                                if field_name in result and result[field_name] and result[field_name].get('id'):
                                    deleted_count += 1
                    except Exception as e:
                        # If batch deletion fails, fall back to individual deletions
                        logger.warning(f"Batch deletion failed, falling back to individual deletions: {e}")
                        for item_id in batch:
                            try:
                                mutation = """
                                mutation DeleteFeedbackItem($input: DeleteFeedbackItemInput!) {
                                    deleteFeedbackItem(input: $input) {
                                        id
                                    }
                                }
                                """
                                result = client.execute(query=mutation, variables={'input': {'id': item_id}})
                                
                                if result and 'deleteFeedbackItem' in result and result['deleteFeedbackItem']:
                                    deleted_count += 1
                                else:
                                    logger.warning(f"Failed to delete FeedbackItem {item_id}. Response: {result}")
                            except Exception as e:
                                logger.error(f"Error deleting FeedbackItem {item_id}: {e}")
                
                # Update progress after each batch
                progress.update(task, advance=len(batch))
                
                # Small delay to prevent API rate limiting
                time.sleep(0.1)
        
        finally:
            # Clean up if we created our own progress bar
            if internal_progress is not None:
                internal_progress.stop()
            
        logger.info(f"Deleted {deleted_count} FeedbackItem records for account {account_id}")
        return deleted_count

    @classmethod
    def get_by_composite_key(cls, client: 'PlexusDashboardClient', account_id: str, scorecard_id: str, 
                            score_id: str, cache_key: str) -> Optional['FeedbackItem']:
        """
        Efficiently retrieve a FeedbackItem using the combination of account, scorecard, score, and cache key.
        
        Args:
            client: The API client
            account_id: Account ID
            scorecard_id: Scorecard ID
            score_id: Score ID
            cache_key: Cache key for this feedback item
            
        Returns:
            FeedbackItem or None if not found
        """
        # Use standard query with filters and pagination to ensure we check all potential records
        query = """
        query GetFeedbackItemByCompositeKey(
            $filter: ModelFeedbackItemFilterInput!,
            $limit: Int,
            $nextToken: String
        ) {
            listFeedbackItems(
                filter: $filter,
                limit: $limit,
                nextToken: $nextToken
            ) {
                items {
                    id
                    accountId
                    scorecardId
                    cacheKey
                    scoreId
                    initialAnswerValue
                    finalAnswerValue
                    initialCommentValue
                    finalCommentValue
                    editCommentValue
                    isAgreement
                    createdAt
                    updatedAt
                }
                nextToken
            }
        }
        """
        
        # Use AND filter combination to match all 4 key components
        filter_condition = {
            "and": [
                {"accountId": {"eq": account_id}},
                {"scorecardId": {"eq": scorecard_id}},
                {"scoreId": {"eq": score_id}}, 
                {"cacheKey": {"eq": cache_key}}
            ]
        }
        
        variables = {
            "filter": filter_condition,
            "limit": 25  # Increased from 1 to handle potential duplicates
        }
        
        logger.debug(f"Executing get_by_composite_key query with variables: {variables}")
        
        try:
            # Handle pagination to ensure we get ALL matching records
            all_items = []
            next_token = None
            
            while True:
                # Add the next token if we have one
                if next_token:
                    variables["nextToken"] = next_token
                
                # Execute the query
                response = client.execute(query=query, variables=variables)
                
                if response and 'listFeedbackItems' in response:
                    items = response['listFeedbackItems'].get('items', [])
                    if items:
                        all_items.extend(items)
                    
                    # Get the next token for pagination
                    next_token = response['listFeedbackItems'].get('nextToken')
                    
                    # If no next token, we've reached the end
                    if not next_token:
                        break
                else:
                    logger.warning(f"Unexpected response structure from query: {response}")
                    break
            
            # Process the results
            if all_items:
                # If we found multiple items, log a warning - this shouldn't happen with proper indexing
                if len(all_items) > 1:
                    logger.warning(f"Found {len(all_items)} FeedbackItems with the same composite key: "
                                  f"account={account_id}, scorecard={scorecard_id}, score={score_id}, "
                                  f"cache_key={cache_key}. Using the first one.")
                    
                    # Use the most recently updated item if there are multiple
                    all_items.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
                
                # Return the first (or most recently updated) item
                return cls.from_dict(all_items[0], client=client)
            else:
                logger.debug(f"No FeedbackItem found with filter: account={account_id}, scorecard={scorecard_id}, "
                            f"score={score_id}, cache_key={cache_key}")
                
        except Exception as e:
            logger.error(f"Error querying FeedbackItem by composite key: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        return None

    @classmethod
    def generate_cache_key(cls, score_id: str, form_id: str) -> str:
        """
        Generate a cache key for a feedback item based on score ID and form ID.
        
        Args:
            score_id: The score ID
            form_id: The form ID
            
        Returns:
            A string that can be used as a cache key
        """
        # Simple concatenation with a separator
        return f"{score_id}:{form_id}"

    @classmethod
    def upsert_by_cache_key(
        cls,
        client: 'PlexusDashboardClient',
        account_id: str,
        scorecard_id: str,
        score_id: str,
        cache_key: str,
        initial_answer_value: Optional[str] = None,
        final_answer_value: Optional[str] = None,
        initial_comment_value: Optional[str] = None,
        final_comment_value: Optional[str] = None,
        edit_comment_value: Optional[str] = None,
        is_agreement: Optional[bool] = None,
        edited_at: Optional[str] = None,
        editor_name: Optional[str] = None,
        item_id: Optional[str] = None,
        debug: bool = False
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Create or update a FeedbackItem using cache key lookup for deduplication.
        
        Uses the byCacheKey GSI for efficient lookup to prevent duplicates.
        
        Args:
            client: The PlexusDashboardClient instance
            account_id: Account ID
            scorecard_id: Scorecard ID  
            score_id: Score ID
            cache_key: Cache key for lookup (typically "{score_id}:{form_id}")
            initial_answer_value: Initial answer value
            final_answer_value: Final answer value
            initial_comment_value: Initial comment value
            final_comment_value: Final comment value
            edit_comment_value: Edit comment value
            is_agreement: Whether initial and final answers agree
            edited_at: ISO timestamp when edited
            editor_name: Name of editor
            item_id: Associated Item ID
            debug: Enable debug logging
            
        Returns:
            Tuple of (feedback_item_id, was_created, error_message)
            - feedback_item_id: ID of the FeedbackItem (None if error)
            - was_created: True if created, False if updated
            - error_message: Error description (None if successful)
        """
        try:
            if debug:
                logger.debug(f"FeedbackItem upsert_by_cache_key: cache_key={cache_key}, account_id={account_id}")
            
            # First, look up existing FeedbackItem by cache key using the GSI
            existing_item = cls._lookup_feedback_item_by_cache_key(client, cache_key, debug)
            
            # Prepare the data payload
            feedback_data = {
                "accountId": account_id,
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "cacheKey": cache_key
            }
            
            # Add optional fields if provided
            if initial_answer_value is not None:
                feedback_data["initialAnswerValue"] = initial_answer_value
            if final_answer_value is not None:
                feedback_data["finalAnswerValue"] = final_answer_value
            if initial_comment_value is not None:
                feedback_data["initialCommentValue"] = initial_comment_value
            if final_comment_value is not None:
                feedback_data["finalCommentValue"] = final_comment_value
            if edit_comment_value is not None:
                feedback_data["editCommentValue"] = edit_comment_value
            if is_agreement is not None:
                feedback_data["isAgreement"] = is_agreement
            if edited_at is not None:
                feedback_data["editedAt"] = edited_at
            if editor_name is not None:
                feedback_data["editorName"] = editor_name
            if item_id is not None:
                feedback_data["itemId"] = item_id
            
            if existing_item:
                # Update existing FeedbackItem
                if debug:
                    logger.debug(f"Updating existing FeedbackItem {existing_item.id} with cache_key {cache_key}")
                
                updated_item = cls._update_feedback_item(client, existing_item.id, feedback_data, debug)
                if updated_item:
                    return updated_item.id, False, None
                else:
                    return None, False, "Failed to update existing FeedbackItem"
            else:
                # Create new FeedbackItem
                if debug:
                    logger.debug(f"Creating new FeedbackItem with cache_key {cache_key}")
                
                created_item = cls._create_feedback_item(client, feedback_data, debug)
                if created_item:
                    return created_item.id, True, None
                else:
                    return None, False, "Failed to create new FeedbackItem"
                    
        except Exception as e:
            error_msg = f"Exception during FeedbackItem upsert: {str(e)}"
            if debug:
                logger.error(error_msg)
                import traceback
                logger.error(traceback.format_exc())
            return None, False, error_msg

    @classmethod
    def _lookup_feedback_item_by_cache_key(
        cls,
        client: 'PlexusDashboardClient',
        cache_key: str,
        debug: bool = False
    ) -> Optional['FeedbackItem']:
        """
        Look up a FeedbackItem by cache key using the byCacheKey GSI.
        
        Args:
            client: The PlexusDashboardClient instance
            cache_key: Cache key to search for
            debug: Enable debug logging
            
        Returns:
            FeedbackItem instance if found, None otherwise
        """
        try:
            if debug:
                logger.debug(f"Looking up FeedbackItem by cache_key: {cache_key}")
            
            # Use the byCacheKey GSI query
            query = """
            query GetFeedbackItemByCacheKey($cacheKey: String!, $limit: Int) {
                listFeedbackItemByCacheKey(cacheKey: $cacheKey, limit: $limit) {
                    items {
                        id
                        accountId
                        scorecardId
                        scoreId
                        cacheKey
                        initialAnswerValue
                        finalAnswerValue
                        initialCommentValue
                        finalCommentValue
                        editCommentValue
                        isAgreement
                        editedAt
                        editorName
                        itemId
                        createdAt
                        updatedAt
                    }
                }
            }
            """
            
            variables = {
                "cacheKey": cache_key,
                "limit": 1
            }
            
            result = client.execute(query=query, variables=variables)
            
            if debug:
                logger.debug(f"Cache key lookup result: {result}")
            
            if result and "listFeedbackItemByCacheKey" in result:
                items = result["listFeedbackItemByCacheKey"].get("items", [])
                if items:
                    if debug:
                        logger.debug(f"Found existing FeedbackItem with ID: {items[0]['id']}")
                    return cls.from_dict(items[0], client=client)
            
            if debug:
                logger.debug(f"No existing FeedbackItem found for cache_key: {cache_key}")
            return None
            
        except Exception as e:
            if debug:
                logger.error(f"Error looking up FeedbackItem by cache_key {cache_key}: {e}")
            return None

    @classmethod
    def _create_feedback_item(
        cls,
        client: 'PlexusDashboardClient',
        feedback_data: Dict[str, Any],
        debug: bool = False
    ) -> Optional['FeedbackItem']:
        """
        Create a new FeedbackItem.
        
        Args:
            client: The PlexusDashboardClient instance
            feedback_data: Data for creating the item
            debug: Enable debug logging
            
        Returns:
            Created FeedbackItem instance or None if failed
        """
        try:
            if debug:
                logger.debug(f"Creating FeedbackItem with data: {feedback_data}")
            
            # Use the existing create method
            created_item = cls.create(client, feedback_data)
            
            if debug and created_item:
                logger.debug(f"Successfully created FeedbackItem with ID: {created_item.id}")
            
            return created_item
            
        except Exception as e:
            if debug:
                logger.error(f"Error creating FeedbackItem: {e}")
            return None

    @classmethod
    def _update_feedback_item(
        cls,
        client: 'PlexusDashboardClient',
        feedback_item_id: str,
        feedback_data: Dict[str, Any],
        debug: bool = False
    ) -> Optional['FeedbackItem']:
        """
        Update an existing FeedbackItem.
        
        Args:
            client: The PlexusDashboardClient instance
            feedback_item_id: ID of the FeedbackItem to update
            feedback_data: Data for updating the item
            debug: Enable debug logging
            
        Returns:
            Updated FeedbackItem instance or None if failed
        """
        try:
            if debug:
                logger.debug(f"Updating FeedbackItem {feedback_item_id} with data: {feedback_data}")
            
            # Add the ID to the data for update
            update_data = feedback_data.copy()
            update_data["id"] = feedback_item_id
            
            # Construct update mutation
            mutation = """
            mutation UpdateFeedbackItem($input: UpdateFeedbackItemInput!) {
                updateFeedbackItem(input: $input) {
                    id
                    accountId
                    scorecardId
                    scoreId
                    cacheKey
                    initialAnswerValue
                    finalAnswerValue
                    initialCommentValue
                    finalCommentValue
                    editCommentValue
                    isAgreement
                    editedAt
                    editorName
                    itemId
                    createdAt
                    updatedAt
                }
            }
            """
            
            variables = {"input": update_data}
            
            result = client.execute(query=mutation, variables=variables)
            
            if debug:
                logger.debug(f"Update result: {result}")
            
            if result and "updateFeedbackItem" in result and result["updateFeedbackItem"]:
                updated_data = result["updateFeedbackItem"]
                updated_item = cls.from_dict(updated_data, client=client)
                
                if debug:
                    logger.debug(f"Successfully updated FeedbackItem with ID: {updated_item.id}")
                
                return updated_item
            else:
                if debug:
                    logger.error(f"Update mutation failed: {result}")
                return None
                
        except Exception as e:
            if debug:
                logger.error(f"Error updating FeedbackItem {feedback_item_id}: {e}")
            return None 