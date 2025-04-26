"""
ReportConfiguration Model - Python representation of the GraphQL ReportConfiguration type.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from .base import BaseModel
from ..client import _BaseAPIClient
import traceback
import logging

logger = logging.getLogger(__name__)

@dataclass
class ReportConfiguration(BaseModel):
    name: str
    accountId: str
    configuration: str  # Stored as Markdown text
    description: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    # Add createdAt, updatedAt if needed, assuming they are handled by base or not directly used often

    def __init__(
        self,
        id: str,
        name: str,
        accountId: str,
        configuration: str,
        description: Optional[str] = None,
        createdAt: Optional[datetime] = None,
        updatedAt: Optional[datetime] = None,
        client: Optional[_BaseAPIClient] = None,
    ):
        super().__init__(id, client)
        self.name = name
        self.accountId = accountId
        self.configuration = configuration
        self.description = description
        self.createdAt = createdAt
        self.updatedAt = updatedAt

    @classmethod
    def fields(cls) -> str:
        """Return the GraphQL fields to query for this model."""
        return """
            id
            name
            description
            accountId
            configuration
            createdAt
            updatedAt
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'ReportConfiguration':
        """Create an instance from a dictionary of data."""
        # Handle potential date parsing if needed, though often stored as strings from GraphQL
        # Example:
        # created_at = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00')) if data.get('createdAt') else None
        # updated_at = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00')) if data.get('updatedAt') else None
        # Parse createdAt and updatedAt from ISO 8601 format
        created_at = None
        if data.get('createdAt'):
            try:
                # Handle potential timezone 'Z' (UTC)
                ts_str = data['createdAt'].replace('Z', '+00:00')
                created_at = datetime.fromisoformat(ts_str)
            except ValueError:
                logger.warning(f"Could not parse createdAt timestamp: {data.get('createdAt')}")

        updated_at = None
        if data.get('updatedAt'):
            try:
                # Handle potential timezone 'Z' (UTC)
                ts_str = data['updatedAt'].replace('Z', '+00:00')
                updated_at = datetime.fromisoformat(ts_str)
            except ValueError:
                logger.warning(f"Could not parse updatedAt timestamp: {data.get('updatedAt')}")

        return cls(
            id=data['id'],
            name=data['name'],
            accountId=data['accountId'],
            configuration=data['configuration'],
            description=data.get('description'),
            createdAt=created_at,
            updatedAt=updated_at,
            client=client
        )

    # get_by_id is inherited from BaseModel

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        name: str,
        accountId: str,
        configuration: str,
        description: Optional[str] = None
    ) -> 'ReportConfiguration':
        """Create a new ReportConfiguration record via GraphQL mutation."""
        mutation = f"""
        mutation CreateReportConfiguration($input: CreateReportConfigurationInput!) {{
            createReportConfiguration(input: $input) {{
                {cls.fields()}
            }}
        }}
        """

        input_data = {
            'name': name,
            'accountId': accountId,
            'configuration': configuration,
            'description': description
            # createdAt/updatedAt are set by the backend automatically
        }
        # Remove optional fields if None
        input_data = {k: v for k, v in input_data.items() if v is not None}

        try:
            logger.debug(f"Creating ReportConfiguration with input: {input_data}")
            result = client.execute(mutation, {'input': input_data})
            if not result or 'createReportConfiguration' not in result or not result['createReportConfiguration']:
                error_msg = f"Failed to create ReportConfiguration. Response: {result}"
                logger.error(error_msg)
                raise Exception(error_msg)
            # Convert the response dict back using from_dict
            return cls.from_dict(result['createReportConfiguration'], client)
        except Exception as e:
            logger.exception(f"Error creating ReportConfiguration '{name}' for account {accountId}: {e}")
            raise

    @classmethod
    def get_by_name(cls, name: str, account_id: str, client: _BaseAPIClient) -> Optional['ReportConfiguration']:
        """Get a ReportConfiguration by its name within a specific account.

        Uses the GSI 'byAccountIdAndName' (implicitly queried by listReportConfigurationByAccountIdAndUpdatedAt
        with an eq filter on name, assuming the backend supports it, or filters client-side).
        Returns the first match found.
        """
        # Try using the index optimized for accountId and name sorting first
        # The actual query name might differ based on Amplify generation, but this is common pattern
        query = f"""
        query ListReportConfigByName(
            $accountId: String!,
            $name: ModelStringKeyConditionInput,
            $limit: Int
        ) {{
            listReportConfigurationByAccountIdAndName(
                accountId: $accountId,
                name: $name,
                limit: $limit
            ) {{
                items {{
                    {cls.fields()}
                }}
                nextToken # Include for potential future pagination
            }}
        }}
        """
        variables = {
            'accountId': account_id,
            'name': { 'eq': name }, # Filter for exact name match
            'limit': 1 # We only need one match
        }
        
        try:
            logger.debug(f"Querying ReportConfiguration by name '{name}' for account {account_id}")
            result = client.execute(query, variables)
            list_result = result.get('listReportConfigurationByAccountIdAndName', {})
            items_data = list_result.get('items', [])
            
            if items_data:
                logger.debug(f"Found ReportConfiguration by name via specific index.")
                # Found using the specific index
                return cls.from_dict(items_data[0], client)
            else:
                # If the specific index query fails or returns empty, try the broader list + filter
                # This is a fallback in case the 'byAccountIdAndName' GSI isn't queryable this way
                logger.warning(f"Query by name GSI failed or returned empty. Falling back to list + filter.")
                list_result = cls.list_by_account_id(account_id=account_id, client=client, limit=1000) # Fetch many
                items = list_result.get('items', [])
                for item in items:
                    if item.name == name:
                         logger.debug(f"Found ReportConfiguration by name via list+filter fallback.")
                         return item # Already an instance due to list_by_account_id
                # If not found even in fallback
                logger.debug(f"ReportConfiguration '{name}' not found in account {account_id} even after fallback.")
                return None

        except Exception as e:
            # Log the specific error, but attempt fallback if appropriate
            logger.error(f"Error querying ReportConfiguration by name '{name}' (GSI: byAccountIdAndName): {e}")
            logger.info("Attempting fallback: Listing all for account and filtering...")
            try:
                 list_result = cls.list_by_account_id(account_id=account_id, client=client, limit=1000) # Fetch many
                 items = list_result.get('items', [])
                 for item in items:
                    if item.name == name:
                        logger.debug(f"Found ReportConfiguration by name via list+filter fallback after error.")
                        return item # Already an instance
                 logger.debug(f"ReportConfiguration '{name}' not found in account {account_id} even after fallback from error.")
                 return None
            except Exception as fallback_e:
                logger.exception(f"Error during fallback list+filter for ReportConfiguration '{name}': {fallback_e}")
                return None # Both primary and fallback failed

    @classmethod
    def list_by_account_id(
        cls,
        account_id: str,
        client: _BaseAPIClient,
        limit: int = 50,
        next_token: Optional[str] = None # Added for potential pagination
    ) -> Dict[str, Any]: # Returns a dict like {'items': [...], 'nextToken': ...}
        """List Report Configurations for a specific account using the GSI."""
        query = f"""
        query ListReportConfigurationByAccountIdAndUpdatedAt(
            $accountId: String!,
            $limit: Int,
            $sortDirection: ModelSortDirection,
            $nextToken: String
        ) {{
            listReportConfigurationByAccountIdAndUpdatedAt(
                accountId: $accountId,
                limit: $limit,
                sortDirection: $sortDirection,
                nextToken: $nextToken
            ) {{
                items {{
                    {cls.fields()}
                }}
                nextToken
            }}
        }}
        """
        variables = {
            'accountId': account_id,
            'limit': limit,
            'sortDirection': 'DESC', # Default to newest first
            'nextToken': next_token
        }

        try:
            result = client.execute(query, variables)
            list_result = result.get('listReportConfigurationByAccountIdAndUpdatedAt', {})

            # Convert raw item dicts to ReportConfiguration instances if items exist
            items_data = list_result.get('items', [])
            if items_data:
                list_result['items'] = [cls.from_dict(item, client) for item in items_data]
            else:
                 list_result['items'] = [] # Ensure items is always a list

            return list_result # Return the whole structure including nextToken
        except Exception as e:
            logger.error(f"Error listing Report Configurations for account {account_id}: {e}\\\n{traceback.format_exc()}")
            # Re-raise or return an empty structure based on desired error handling
            raise # Re-raise for now to let caller handle 