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