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
    output: Optional[Dict[str, Any]] = field(default_factory=dict) # Store parsed JSON
    name: Optional[str] = None
    log: Optional[str] = None
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
            output # Expecting JSON string from API
            log
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

        return cls(
            id=data['id'],
            reportId=data['reportId'],
            position=position,
            output=output_data, # Store the parsed dict/None
            name=name,
            log=log,
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            client=client
        )

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        reportId: str,
        position: int,
        output: Optional[str] = None, # Expecting JSON string as input here
        name: Optional[str] = None,
        log: Optional[str] = None,
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
            # Pass output as a string, ensure None is handled
            'output': output, 
            'name': name,
            'log': log,
            # createdAt/updatedAt are usually set by the backend automatically
        }
        # Remove keys with None values if the mutation expects them to be absent
        input_data = {k: v for k, v in input_data.items() if v is not None}

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