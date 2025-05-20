"""
ReportBlock Model - Python representation of the GraphQL ReportBlock type.
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
class ReportBlock(BaseModel):
    reportId: str
    position: int
    type: str  # Add required type field
    output: Optional[Dict[str, Any]] = field(default_factory=dict) # Store parsed JSON
    name: Optional[str] = None
    log: Optional[str] = None
    detailsFiles: Optional[str] = None  # JSON string of files attached to this block
    createdAt: Optional[datetime] = None # Assuming these are set by backend
    updatedAt: Optional[datetime] = None # Assuming these are set by backend

    # Use __post_init__ or a custom __init__ if complex initialization is needed
    # For now, relying on dataclass defaults

    @classmethod
    def fields(cls) -> str:
        """Return the GraphQL fields to query for this model."""
        # Ensure these match the actual GraphQL schema names
        return """
            id
            reportId
            name
            position
            type
            output # Expecting JSON string from API
            log
            detailsFiles # JSON string containing attached file details
            createdAt
            updatedAt
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'ReportBlock':
        """Create an instance from a dictionary of data (typically from API response)."""
        # Parse datetime fields if they exist and are strings
        for date_field in ['createdAt', 'updatedAt']:
            if data.get(date_field) and isinstance(data[date_field], str):
                try:
                    data[date_field] = datetime.fromisoformat(data[date_field].replace('Z', '+00:00'))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse date field '{date_field}': {data[date_field]}. Error: {e}")
                    data[date_field] = None
            elif data.get(date_field):
                 # Assume it might already be a datetime object if not a string
                 pass 
            else:
                 data[date_field] = None # Ensure field exists as None if missing

        # Parse the 'output' JSON string field
        output_data = None
        if data.get('output') and isinstance(data['output'], str):
            try:
                output_data = json.loads(data['output'])
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse JSON field 'output': {e}. Data: {data['output']}")
                output_data = {"error": "Failed to parse output JSON", "raw_output": data['output']}
        elif data.get('output') is not None: # If it's not a string but not None (e.g., already dict?)
             logger.warning(f"'output' field was not a string: {type(data['output'])}. Using as is.")
             output_data = data['output']
        # If output field is missing or null, output_data remains None

        # Handle potential missing optional fields gracefully
        name = data.get('name')
        log = data.get('log')
        details_files = data.get('detailsFiles')  # Get detailsFiles field
        position = data.get('position')
        if position is None:
            # Position is required in our plan, raise error or default?
            logger.error(f"Missing required field 'position' in ReportBlock data: {data.get('id')}")
            # Fallback or raise error depending on strictness
            position = -1 # Or raise ValueError("Missing required field 'position'")
        else:
             try:
                 position = int(position) # Ensure it's an integer
             except (ValueError, TypeError):
                 logger.error(f"Invalid type for 'position' field in ReportBlock data: {data.get('id')}")
                 position = -1 # Or raise

        # Instantiate using fields defined in ReportBlock dataclass
        # Client is likely handled by BaseModel internally or not needed here.
        instance = cls(
            reportId=data['reportId'],
            position=position,
            type=data['type'],
            output=output_data, # Store the parsed dict/None
            name=name,
            log=log,
            detailsFiles=details_files,  # Add detailsFiles to instance
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt']
            # Removed: client=client
        )
        # Set the ID after initialization
        instance.id = data.get('id') # Use .get() for safety
        # TODO: Verify if client needs to be attached to the instance, e.g., instance._client = client
        instance._client = client # Assume BaseModel stores client like this
        return instance

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        reportId: str,
        position: int,
        type: str,  # Add required type parameter
        output: Optional[str] = None, # Expecting JSON string as input here
        name: Optional[str] = None,
        log: Optional[str] = None,
        detailsFiles: Optional[str] = None,  # JSON string of file details
    ) -> 'ReportBlock':
        """Create a new ReportBlock record via GraphQL mutation."""
        mutation = f"""
        mutation CreateReportBlock($input: CreateReportBlockInput!) {{
            createReportBlock(input: $input) {{
                {cls.fields()}
            }}
        }}
        """

        input_data = {
            'reportId': reportId,
            'position': position,
            'type': type,  # Add type to input data
            # Pass output as a string, ensure None is handled
            'output': output, 
            'name': name,
            'log': log,
            'detailsFiles': detailsFiles,  # Add detailsFiles to input data
            # createdAt/updatedAt are usually set by the backend automatically
        }
        # Remove keys with None values if the mutation expects them to be absent
        input_data = {k: v for k, v in input_data.items() if v is not None}

        # Add detailed logging about sizes
        if 'output' in input_data:
            input_data_size = len(json.dumps(input_data))
            output_size = len(input_data['output']) if isinstance(input_data['output'], str) else 0
            other_fields_size = input_data_size - output_size
            
            logger.info(f"ReportBlock create sizes - Total input: {input_data_size} bytes")
            logger.info(f"ReportBlock create sizes - Output field: {output_size} bytes")
            logger.info(f"ReportBlock create sizes - Other fields: {other_fields_size} bytes")
            
            # Log detailsFiles size if present
            if 'detailsFiles' in input_data:
                details_size = len(input_data['detailsFiles']) if isinstance(input_data['detailsFiles'], str) else 0
                logger.info(f"ReportBlock create sizes - detailsFiles field: {details_size} bytes")
            
            if output_size > 350000:
                logger.warning(f"ReportBlock output field size ({output_size} bytes) approaching DynamoDB limit!")
            
            if input_data_size > 380000:
                logger.error(f"TOTAL input data size ({input_data_size} bytes) exceeds DynamoDB limit!")

        try:
            logger.debug(f"Creating ReportBlock with input: {input_data}")
            result = client.execute(mutation, {'input': input_data})
            if not result or 'createReportBlock' not in result or not result['createReportBlock']:
                error_msg = f"Failed to create ReportBlock for report {reportId}. Response: {result}"
                logger.error(error_msg)
                raise Exception(error_msg)
            # Convert the response dict back using from_dict
            return cls.from_dict(result['createReportBlock'], client)
        except Exception as e:
            logger.exception(f"Error creating ReportBlock for report {reportId}: {e}")
            raise

    # get_by_id is inherited from BaseModel
    # TODO: Implement list methods using GSI (byReportAndName, byReportAndPosition) if needed

    @classmethod
    def list_by_report_id(
        cls,
        report_id: str,
        client: _BaseAPIClient,
        limit: int = 100,
        max_items: Optional[int] = None
    ) -> list['ReportBlock']:
        """List ReportBlocks for a specific report using pagination.

        Assumes a GraphQL query 'listReportBlocksByReportIdAndPosition' exists, 
        using an index like 'byReportIdAndPosition'.

        Args:
            report_id: The ID of the Report to list blocks for.
            client: The API client instance.
            limit: The number of items to fetch per page.
            max_items: Optional limit on the total number of items to return.

        Returns:
            A list of ReportBlock instances, sorted by position ascending.
        """
        # TODO: Verify the actual GraphQL query name and index name from schema
        query = f"""
        query ListReportBlocksByReportIdAndPosition(
            $reportId: String!,
            $limit: Int,
            $sortDirection: ModelSortDirection,
            $nextToken: String
        ) {{
            listReportBlockByReportIdAndPosition(
                reportId: $reportId,
                limit: $limit,
                sortDirection: $sortDirection, # ASC to sort by position
                nextToken: $nextToken
            ) {{
                items {{
                    {cls.fields()}
                }}
                nextToken
            }}
        }}
        """

        blocks = []
        next_token = None
        items_fetched = 0

        while True:
            variables = {
                'reportId': report_id,
                'limit': limit,
                'sortDirection': 'ASC', # Sort by position ascending
                'nextToken': next_token
            }

            try:
                result = client.execute(query, variables)
                # TODO: Verify the actual response structure matches the assumed query name
                list_result = result.get('listReportBlockByReportIdAndPosition', {})
                items_data = list_result.get('items', [])

                for item_data in items_data:
                    blocks.append(cls.from_dict(item_data, client))
                    items_fetched += 1
                    if max_items is not None and items_fetched >= max_items:
                        return blocks # Reached max items limit

                next_token = list_result.get('nextToken')
                if not next_token:
                    break # No more pages

            except Exception as e:
                logger.exception(f"Error listing report blocks for report {report_id} on page with nextToken {next_token}: {e}")
                # Depending on desired behavior, we might break, continue, or raise
                break # Stop fetching on error

        return blocks 

    def update(self, client: Optional[_BaseAPIClient] = None, **kwargs) -> 'ReportBlock':
        """Update an existing ReportBlock record via GraphQL mutation."""
        if not self.id:
            raise ValueError("Cannot update ReportBlock without an ID.")

        # Use the instance's client if one isn't provided
        api_client = client if client else self._client
        if not api_client:
            raise ValueError("API client not available for update operation.")

        mutation = f"""
        mutation UpdateReportBlock($input: UpdateReportBlockInput!) {{
            updateReportBlock(input: $input) {{
                {self.fields()}
            }}
        }}
        """
        
        input_data = {'id': self.id}
        
        # Prepare allowed fields for update from kwargs
        # Only include fields that are part of the model and were actually passed
        allowed_update_fields = {
            'reportId', 'name', 'position', 'type', 
            'output', 'log', 'detailsFiles' # Add other mutable fields as needed
        }
        
        # Special handling for specific fields
        for key, value in kwargs.items():
            if key in allowed_update_fields:
                # Special handling for 'output' if it's a dict, needs to be JSON string for GQL
                if key == 'output' and isinstance(value, dict):
                    input_data[key] = json.dumps(value)
                    logger.info(f"ReportBlock update: Converted 'output' dict to JSON string ({len(input_data[key])} bytes)")
                elif key == 'detailsFiles':
                    # Log original value
                    logger.info(f"ReportBlock update: detailsFiles before processing - Type: {type(value)}, Value: {value}")
                    
                    # Ensure detailsFiles is stringified JSON
                    if not isinstance(value, str):
                        input_data[key] = json.dumps(value)
                        logger.info(f"ReportBlock update: Converted 'detailsFiles' to JSON string ({len(input_data[key])} bytes)")
                    else:
                        input_data[key] = value
                        # Validate it's proper JSON
                        try:
                            json.loads(value)
                            logger.info(f"ReportBlock update: 'detailsFiles' is valid JSON string ({len(value)} bytes)")
                        except json.JSONDecodeError as e:
                            logger.warning(f"ReportBlock update: 'detailsFiles' is not valid JSON: {e}")
                else:
                    input_data[key] = value
            else:
                logger.warning(f"Field '{key}' not allowed for ReportBlock update or not recognized.")

        if len(input_data) == 1 and 'id' in input_data:
            logger.warning("Update called with no fields to update other than ID.")
            return self

        try:
            logger.debug(f"Updating ReportBlock {self.id} with input: {input_data}")
            result = api_client.execute(mutation, {'input': input_data})
            if not result or 'updateReportBlock' not in result or not result['updateReportBlock']:
                error_msg = f"Failed to update ReportBlock {self.id}. Response: {result}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            updated_data = result['updateReportBlock']
            logger.info(f"Update result for ReportBlock {self.id}: {updated_data}")
            
            # Specifically log detailsFiles to track if it was properly updated
            if 'detailsFiles' in kwargs:
                if 'detailsFiles' in updated_data:
                    logger.info(f"detailsFiles after update: {updated_data['detailsFiles']}")
                    
                    # Try to parse it to validate
                    try:
                        if updated_data['detailsFiles']:
                            details_files_parsed = json.loads(updated_data['detailsFiles'])
                            logger.info(f"detailsFiles parsed successfully: {details_files_parsed}")
                        else:
                            logger.info("detailsFiles is empty in response")
                    except json.JSONDecodeError as e:
                        logger.warning(f"detailsFiles in response is not valid JSON: {e}")
                else:
                    logger.warning("detailsFiles missing from update response")
            
            for field_name, value in updated_data.items():
                if hasattr(self, field_name):
                    if field_name == 'output' and isinstance(value, str):
                        try:
                            setattr(self, field_name, json.loads(value))
                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse output from update response: {value}")
                            setattr(self, field_name, {"error": "Failed to parse output JSON", "raw_output": value})
                    elif field_name == 'detailsFiles':
                        # Just store the raw detailsFiles string on the instance
                        setattr(self, field_name, value)
                        logger.info(f"Set detailsFiles attribute on instance: {value}")
                    elif field_name in ['createdAt', 'updatedAt'] and isinstance(value, str):
                        try:
                            setattr(self, field_name, datetime.fromisoformat(value.replace('Z', '+00:00')))
                        except (ValueError, TypeError):
                            setattr(self, field_name, None)
                    else:
                        setattr(self, field_name, value)
            
            self.id = updated_data.get('id', self.id)
            logger.info(f"Successfully updated ReportBlock {self.id}")
            return self
        except Exception as e:
            logger.exception(f"Error updating ReportBlock {self.id}: {e}")
            raise

# TODO: If list_by_report_id is used, ensure it's correctly implemented or remove if unused.
# Consider if this file is the single source of truth for ReportBlock or if there's another.
# BaseModel might provide some of these methods, verify to avoid duplication or conflicts.
# Example: if BaseModel has _client or generic get_by_id, update, delete methods. 