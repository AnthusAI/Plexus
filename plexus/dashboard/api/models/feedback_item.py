import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from plexus.dashboard.api.models.base import BaseModel
from plexus.dashboard.api.models.feedback_change_detail import FeedbackChangeDetail

if TYPE_CHECKING:
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.account import Account
    from plexus.dashboard.api.models.scorecard import Scorecard
    from plexus.dashboard.api.models.score import Score

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
    externalId: Optional[str] = None # Maps to Call Criteria form_id
    scoreId: Optional[str] = None # Maps to Call Criteria question_id
    initialAnswerValue: Optional[str] = None
    finalAnswerValue: Optional[str] = None
    initialCommentValue: Optional[str] = None
    finalCommentValue: Optional[str] = None
    isMismatch: Optional[bool] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    # Relationships - lazy loaded
    account: Optional['Account'] = field(default=None, repr=False)
    scorecard: Optional['Scorecard'] = field(default=None, repr=False)
    score: Optional['Score'] = field(default=None, repr=False)
    changeDetails: Optional[List['FeedbackChangeDetail']] = field(default=None, repr=False)

    _client: Optional['PlexusDashboardClient'] = field(default=None, repr=False)
    _raw_data: Optional[Dict[str, Any]] = field(default=None, repr=False)

    GRAPHQL_BASE_FIELDS = [
        'id', 'accountId', 'scorecardId', 'externalId', 'scoreId',
        'initialAnswerValue', 'finalAnswerValue', 'initialCommentValue',
        'finalCommentValue', 'isMismatch', 'createdAt', 'updatedAt'
    ]
    GRAPHQL_RELATIONSHIP_FIELDS = {
        'changeDetails': FeedbackChangeDetail.GRAPHQL_BASE_FIELDS
        # Add account, scorecard, score if needed later
    }

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
            # Default to including base fields for changeDetails if not specified
             relationship_fields = {'changeDetails': FeedbackChangeDetail.GRAPHQL_BASE_FIELDS}
             # relationship_fields = {}
            
        query_parts = list(fields)
        
        for rel_name, rel_fields in relationship_fields.items():
            if rel_name == 'changeDetails':
                # Special handling for lists: items { fields }
                sub_query = FeedbackChangeDetail._build_query(rel_fields)
                query_parts.append(f"{rel_name} {{ items {sub_query} nextToken }}")
            # Add handling for other relationships like account, scorecard, score if needed
            # Example: 
            # elif rel_name == 'account':
            #     sub_query = Account._build_query(rel_fields)
            #     query_parts.append(f"account {sub_query}")
            
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
        external_id: Optional[str] = None,
        limit: int = 100, 
        next_token: Optional[str] = None,
        fields: Optional[List[str]] = None,
        relationship_fields: Optional[Dict[str, List[str]]] = None
    ) -> (List['FeedbackItem'], Optional[str]):
        """List FeedbackItems with optional filtering."""
        query_name = "listFeedbackItems"
        query_body_items = cls._build_query(fields, relationship_fields)
        query_body = f"""
            {{
                items {query_body_items}
                nextToken
            }}
        """
        
        filters = {}
        if account_id:
            filters["accountId"] = {"eq": account_id}
        if scorecard_id:
            filters["scorecardId"] = {"eq": scorecard_id}
        if score_id:
            filters["scoreId"] = {"eq": score_id}
        if external_id:
            filters["externalId"] = {"eq": external_id}
            
        arguments = {
            "filter": filters if filters else None,
            "limit": limit,
            "nextToken": next_token
        }
        
        # Remove None values from arguments
        arguments = {k: v for k, v in arguments.items() if v is not None}

        # Construct the full query string with arguments
        # Argument definition depends on exact schema (e.g., $filter: ModelFeedbackItemFilterInput)
        # We'll construct a simple version assuming direct variable passing works
        # A more robust approach might involve generating argument definitions
        query_string = f"""
            query ListFeedbackItems(
                $filter: ModelFeedbackItemFilterInput, 
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