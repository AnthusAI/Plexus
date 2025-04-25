"""
Report Model - Python representation of the GraphQL Report type.
"""

import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class Report(BaseModel):
    reportConfigurationId: str
    accountId: str
    name: str
    status: str
    createdAt: datetime
    updatedAt: datetime
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    parameters: Optional[Dict[str, Any]] = field(default_factory=dict)
    output: Optional[str] = None  # Changed from reportData to output
    errorMessage: Optional[str] = None
    errorDetails: Optional[str] = None # Store as string, potentially JSON

    def __init__(
        self,
        id: str,
        reportConfigurationId: str,
        accountId: str,
        name: str,
        status: str,
        createdAt: datetime,
        updatedAt: datetime,
        startedAt: Optional[datetime] = None,
        completedAt: Optional[datetime] = None,
        parameters: Optional[Dict[str, Any]] = None,
        output: Optional[str] = None,  # Changed from reportData to output
        errorMessage: Optional[str] = None,
        errorDetails: Optional[str] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.reportConfigurationId = reportConfigurationId
        self.accountId = accountId
        self.name = name
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.startedAt = startedAt
        self.completedAt = completedAt
        self.parameters = parameters or {}
        self.output = output  # Changed from reportData to output
        self.errorMessage = errorMessage
        self.errorDetails = errorDetails

    @classmethod
    def fields(cls) -> str:
        """Return the GraphQL fields to query for this model."""
        return """
            id
            reportConfigurationId
            accountId
            name
            status
            createdAt
            updatedAt
            startedAt
            completedAt
            parameters # Assuming JSON string
            output # Changed from reportData to output
            errorMessage
            errorDetails
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Report':
        """Create an instance from a dictionary of data."""
        # Parse datetime fields
        for date_field in ['createdAt', 'updatedAt', 'startedAt', 'completedAt']:
            if data.get(date_field):
                try:
                    # Handle potential ISO format strings from GraphQL
                    data[date_field] = datetime.fromisoformat(data[date_field].replace('Z', '+00:00'))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse date field '{date_field}': {data[date_field]}. Error: {e}")
                    data[date_field] = None # Or handle as appropriate

        # Parse JSON string fields
        for json_field in ['parameters']:  # Removed reportData from JSON parsing
            if data.get(json_field) and isinstance(data[json_field], str):
                try:
                    data[json_field] = json.loads(data[json_field])
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse JSON field '{json_field}': {e}. Data: {data[json_field]}")
                    data[json_field] = None # Or set to {} or handle error
            elif data.get(json_field) is None:
                 data[json_field] = {}
        
        # Handle output specifically - default to None if needed
        if 'output' not in data or data['output'] is None:
             data['output'] = None # Default to None if missing/null

        # Ensure required datetime fields have fallbacks if parsing failed or missing
        now = datetime.now(timezone.utc)
        data['createdAt'] = data.get('createdAt') or now
        data['updatedAt'] = data.get('updatedAt') or now

        return cls(
            id=data['id'],
            reportConfigurationId=data['reportConfigurationId'],
            accountId=data['accountId'],
            name=data['name'],
            status=data['status'],
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            startedAt=data.get('startedAt'),
            completedAt=data.get('completedAt'),
            parameters=data.get('parameters'),
            output=data.get('output'),  # Changed from reportData to output
            errorMessage=data.get('errorMessage'),
            errorDetails=data.get('errorDetails'),
            client=client
        )

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        reportConfigurationId: str,
        accountId: str,
        name: str,
        parameters: Optional[Dict[str, Any]] = None,
        status: str = 'PENDING' # Default status on creation
    ) -> 'Report':
        """Create a new Report record via GraphQL mutation."""
        mutation = f"""
        mutation CreateReport($input: CreateReportInput!) {{
            createReport(input: $input) {{
                {cls.fields()}
            }}
        }}
        """

        input_data = {
            'reportConfigurationId': reportConfigurationId,
            'accountId': accountId,
            'name': name,
            'status': status,
            'parameters': json.dumps(parameters or {})
            # createdAt/updatedAt are usually set by the backend
        }

        try:
            result = client.execute(mutation, {'input': input_data})
            if not result or 'createReport' not in result or not result['createReport']:
                 error_msg = f"Failed to create Report. Response: {result}"
                 logger.error(error_msg)
                 raise Exception(error_msg)
            return cls.from_dict(result['createReport'], client)
        except Exception as e:
            logger.exception(f"Error creating Report for config {reportConfigurationId}: {e}")
            raise

    def update(self, **kwargs) -> 'Report':
        """Update an existing Report record via GraphQL mutation."""
        if not self._client:
            raise ValueError("Cannot update report without an associated API client.")

        mutation = f"""
        mutation UpdateReport($input: UpdateReportInput!) {{
            updateReport(input: $input) {{
                {self.fields()}
            }}
        }}
        """

        input_data = {'id': self.id}

        # Prepare fields for update, serializing JSON and formatting dates
        for key, value in kwargs.items():
            if key in ['parameters']:
                input_data[key] = json.dumps(value or {}) # Only dump parameters
            elif key == 'output':
                 input_data[key] = value # Pass output string directly
            elif isinstance(value, datetime):
                input_data[key] = value.isoformat().replace('+00:00', 'Z')
            elif key == 'errorDetails': # Special handling for errorDetails
                if value is not None:
                    # Ensure errorDetails is always stored as a JSON-encoded string
                    # This handles newlines and special characters safely for GraphQL transport
                    try:
                        input_data[key] = json.dumps(str(value)) 
                    except TypeError as json_err:
                        logger.error(f"Could not JSON-encode errorDetails: {json_err}. Storing raw string representation.")
                        input_data[key] = repr(value) # Fallback to repr
                else:
                    input_data[key] = None # Pass None if value is None
            elif value is not None: # Include other non-None fields directly
                 input_data[key] = value

        try:
            result = self._client.execute(mutation, {'input': input_data})
            if not result or 'updateReport' not in result or not result['updateReport']:
                 error_msg = f"Failed to update Report {self.id}. Response: {result}"
                 logger.error(error_msg)
                 raise Exception(error_msg)

            # Update the current instance with the response data
            updated_data = result['updateReport']
            updated_instance = self.from_dict(updated_data, self._client)

            # Manually update fields of the current instance to reflect changes
            for field_name in self.__dataclass_fields__:
                if field_name != 'client': # Don't overwrite client
                    setattr(self, field_name, getattr(updated_instance, field_name))

            return self # Return the updated instance
        except Exception as e:
            logger.exception(f"Error updating Report {self.id} with data {input_data}: {e}")
            raise

    @classmethod
    def get_by_name(cls, name: str, account_id: str, client: _BaseAPIClient) -> Optional['Report']:
        """Get a Report by its name within a specific account.

        Uses the 'listReportByAccountIdAndUpdatedAt' index and filters results 
        client-side to find the matching name. Returns the first match found.
        NOTE: This can be inefficient if there are many reports for the account.
        """
        # Query using the available index
        query = f"""
        query ListReportByAccountIdAndUpdatedAt(
            $accountId: String!,
            $limit: Int,
            $sortDirection: ModelSortDirection,
            $nextToken: String
        ) {{
            listReportByAccountIdAndUpdatedAt(
                accountId: $accountId,
                limit: $limit, 
                sortDirection: $sortDirection,
                nextToken: $nextToken
                # Cannot filter by name directly in this query
            ) {{
                items {{
                    {cls.fields()} # Fetch all fields needed for filtering and construction
                }}
                nextToken
            }}
        }}
        """

        variables = {
            'accountId': account_id,
            'limit': 1000, # Fetch a large number to increase chance of finding the name
                       # TODO: Implement pagination if names aren't found in the first batch
            'sortDirection': 'DESC' # Get most recent first
        }
        # next_token logic could be added here for full pagination

        try:
            result = client.execute(query, variables)
            list_result = result.get('listReportByAccountIdAndUpdatedAt', {})
            items_data = list_result.get('items', [])
            
            # Filter client-side
            for item_data in items_data:
                if item_data.get('name') == name:
                    return cls.from_dict(item_data, client)
            
            # TODO: Handle pagination if item not found and nextToken exists
            # if list_result.get('nextToken'):
            #    # recursively call or loop with nextToken
            #    pass

            # If no match found after checking (potentially paginated) results
            return None 
        except Exception as e:
            logger.exception(f"Error listing reports for account {account_id} while searching for name '{name}': {e}")
            return None

    # get_by_id is inherited from BaseModel 