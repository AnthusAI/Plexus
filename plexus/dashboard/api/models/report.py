"""
Report Model - Python representation of the GraphQL Report type.
"""

import json
import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime, timezone
from .base import BaseModel

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class Report(BaseModel):
    reportConfigurationId: str
    accountId: str
    name: str
    taskId: str
    createdAt: datetime
    updatedAt: datetime
    parameters: Optional[Dict[str, Any]] = field(default_factory=dict)
    output: Optional[str] = None

    def __init__(
        self,
        id: str,
        reportConfigurationId: str,
        accountId: str,
        name: str,
        taskId: str,
        createdAt: datetime,
        updatedAt: datetime,
        parameters: Optional[Dict[str, Any]] = None,
        output: Optional[str] = None,
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.reportConfigurationId = reportConfigurationId
        self.accountId = accountId
        self.name = name
        self.taskId = taskId
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.parameters = parameters or {}
        self.output = output

    @classmethod
    def fields(cls) -> str:
        """Return the GraphQL fields to query for this model."""
        return """
            id
            reportConfigurationId
            accountId
            name
            taskId
            createdAt
            updatedAt
            parameters # Assuming JSON string
            output
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'Report':
        """Create an instance from a dictionary of data."""
        # Parse datetime fields
        for date_field in ['createdAt', 'updatedAt']:
            if data.get(date_field):
                try:
                    data[date_field] = datetime.fromisoformat(data[date_field].replace('Z', '+00:00'))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse date field '{date_field}': {data[date_field]}. Error: {e}")
                    data[date_field] = None

        # Parse JSON string fields
        for json_field in ['parameters']:
            if data.get(json_field) and isinstance(data[json_field], str):
                try:
                    data[json_field] = json.loads(data[json_field])
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse JSON field '{json_field}': {e}. Data: {data[json_field]}")
                    data[json_field] = None
            elif data.get(json_field) is None:
                 data[json_field] = {}

        if 'output' not in data or data['output'] is None:
             data['output'] = None

        now = datetime.now(timezone.utc)
        data['createdAt'] = data.get('createdAt') or now
        data['updatedAt'] = data.get('updatedAt') or now

        # Ensure taskId is present
        if 'taskId' not in data:
            raise ValueError("Missing required field 'taskId' in Report data")

        return cls(
            id=data['id'],
            reportConfigurationId=data['reportConfigurationId'],
            accountId=data['accountId'],
            name=data['name'],
            taskId=data['taskId'],
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            parameters=data.get('parameters'),
            output=data.get('output'),
            client=client
        )

    @classmethod
    def create(
        cls,
        client: '_BaseAPIClient',
        reportConfigurationId: str,
        accountId: str,
        taskId: str,
        name: str,
        parameters: Optional[Dict[str, Any]] = None,
        output: Optional[str] = None
    ) -> 'Report':
        """Create a new Report record via GraphQL mutation, linked to a Task."""
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
            'taskId': taskId,
            'name': name,
            'parameters': json.dumps(parameters or {})
        }
        if output is not None:
            input_data['output'] = output

        try:
            result = client.execute(mutation, {'input': input_data})
            if not result or 'createReport' not in result or not result['createReport']:
                 error_msg = f"Failed to create Report. Response: {result}"
                 logger.error(error_msg)
                 raise Exception(error_msg)
            return cls.from_dict(result['createReport'], client)
        except Exception as e:
            logger.exception(f"Error creating Report for config {reportConfigurationId}, task {taskId}: {e}")
            raise

    def update(self, **kwargs) -> 'Report':
        """Update an existing Report record via GraphQL mutation."""
        if not self._client:
            raise ValueError("Cannot update report without an associated API client.")

        # Prevent updating fields managed by Task or immutable fields
        forbidden_fields = ['status', 'startedAt', 'completedAt', 'errorMessage', 'errorDetails', 'taskId', 'accountId', 'reportConfigurationId', 'createdAt']
        for field in forbidden_fields:
             if field in kwargs:
                 raise ValueError(f"Cannot update field '{field}' directly on Report model. It is either immutable or managed by the associated Task.")

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
                input_data[key] = json.dumps(value or {})
            elif key == 'output':
                 input_data[key] = value
            # No datetime fields are updatable anymore except updatedAt (handled automatically)
            elif value is not None:
                 input_data[key] = value

        if not input_data:
            logger.warning(f"Update called for Report {self.id} with no updatable fields.")
            return self # No changes needed

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
                if field_name != 'client' and hasattr(updated_instance, field_name):
                    setattr(self, field_name, getattr(updated_instance, field_name))

            return self
        except Exception as e:
            logger.exception(f"Error updating Report {self.id} with data {input_data}: {e}")
            raise

    @classmethod
    def get_by_name(cls, name: str, account_id: str, client: '_BaseAPIClient') -> Optional['Report']:
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
            ) {{
                items {{
                    {cls.fields()} # Fetch fields including taskId now
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

    @classmethod
    def list_by_account_id(
        cls,
        account_id: str,
        client: '_BaseAPIClient',
        limit: int = 100, # Default limit per request
        max_items: Optional[int] = None # Optional total max items to fetch
    ) -> list['Report']:
        """List Reports for a specific account using pagination.

        Uses the 'listReportByAccountIdAndUpdatedAt' index.

        Args:
            account_id: The ID of the account to list reports for.
            client: The API client instance.
            limit: The number of items to fetch per page.
            max_items: Optional limit on the total number of items to return.

        Returns:
            A list of Report instances.
        """
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
            ) {{
                items {{
                    {cls.fields()}
                }}
                nextToken
            }}
        }}
        """

        reports = []
        next_token = None
        items_fetched = 0

        while True:
            variables = {
                'accountId': account_id,
                'limit': limit,
                'sortDirection': 'DESC', # Get most recent first
                'nextToken': next_token
            }

            try:
                result = client.execute(query, variables)
                list_result = result.get('listReportByAccountIdAndUpdatedAt', {})
                items_data = list_result.get('items', [])

                for item_data in items_data:
                    reports.append(cls.from_dict(item_data, client))
                    items_fetched += 1
                    if max_items is not None and items_fetched >= max_items:
                        return reports # Reached max items limit

                next_token = list_result.get('nextToken')
                if not next_token:
                    break # No more pages

            except Exception as e:
                logger.exception(f"Error listing reports for account {account_id} on page with nextToken {next_token}: {e}")
                # Depending on desired behavior, we might break, continue, or raise
                break # Stop fetching on error

        return reports

    def delete(self) -> bool:
        """Delete this Report record and its associated ReportBlock records.
        
        Performs a GraphQL mutation to delete the report. The API is expected to
        cascade delete all associated ReportBlock records.
        
        Returns:
            bool: True if deletion was successful, False otherwise.
            
        Raises:
            ValueError: If no client is associated with this instance.
            Exception: If the GraphQL mutation returns an error.
        """
        if not self._client:
            raise ValueError("Cannot delete report without an associated API client.")
            
        mutation = """
        mutation DeleteReport($input: DeleteReportInput!) {
            deleteReport(input: $input) {
                id
            }
        }
        """
        
        try:
            logger.debug(f"Deleting Report {self.id}")
            result = self._client.execute(mutation, {'input': {'id': self.id}})
            
            if not result or 'deleteReport' not in result or not result['deleteReport']:
                error_msg = f"Failed to delete Report {self.id}. Response: {result}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            deleted_id = result['deleteReport'].get('id')
            if deleted_id != self.id:
                logger.warning(f"Deleted report ID mismatch. Expected {self.id}, got {deleted_id}")
                
            logger.info(f"Successfully deleted Report {self.id}")
            return True
            
        except Exception as e:
            logger.exception(f"Error deleting Report {self.id}: {e}")
            raise
    
    @classmethod
    def delete_by_id(cls, report_id: str, client: '_BaseAPIClient') -> bool:
        """Delete a Report by ID without first retrieving it.
        
        Args:
            report_id: The ID of the report to delete.
            client: The API client to use for the deletion.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
            
        Raises:
            Exception: If the GraphQL mutation returns an error.
        """
        mutation = """
        mutation DeleteReport($input: DeleteReportInput!) {
            deleteReport(input: $input) {
                id
            }
        }
        """
        
        try:
            logger.debug(f"Deleting Report {report_id} by ID")
            result = client.execute(mutation, {'input': {'id': report_id}})
            
            if not result or 'deleteReport' not in result or not result['deleteReport']:
                error_msg = f"Failed to delete Report {report_id}. Response: {result}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            deleted_id = result['deleteReport'].get('id')
            if deleted_id != report_id:
                logger.warning(f"Deleted report ID mismatch. Expected {report_id}, got {deleted_id}")
                
            logger.info(f"Successfully deleted Report {report_id}")
            return True
            
        except Exception as e:
            logger.exception(f"Error deleting Report {report_id}: {e}")
            raise
            
    @classmethod
    def delete_multiple(cls, report_ids: List[str], client: '_BaseAPIClient') -> Dict[str, bool]:
        """Delete multiple Reports by IDs.
        
        Args:
            report_ids: A list of report IDs to delete.
            client: The API client to use for the deletion.
            
        Returns:
            Dict[str, bool]: A dictionary mapping report IDs to deletion success status.
        """
        results = {}
        
        for report_id in report_ids:
            try:
                success = cls.delete_by_id(report_id, client)
                results[report_id] = success
            except Exception as e:
                logger.error(f"Failed to delete Report {report_id}: {e}")
                results[report_id] = False
                
        return results

    # get_by_id is inherited from BaseModel 