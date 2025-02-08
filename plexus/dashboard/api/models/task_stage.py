from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient

@dataclass
class TaskStage(BaseModel):
    taskId: str
    name: str
    order: int
    status: str
    statusMessage: Optional[str] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    estimatedCompletionAt: Optional[datetime] = None
    processedItems: Optional[int] = None
    totalItems: Optional[int] = None

    def __init__(
        self,
        id: str,
        taskId: str,
        name: str,
        order: int,
        status: str,
        statusMessage: Optional[str] = None,
        startedAt: Optional[datetime] = None,
        completedAt: Optional[datetime] = None,
        estimatedCompletionAt: Optional[datetime] = None,
        processedItems: Optional[int] = None,
        totalItems: Optional[int] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.taskId = taskId
        self.name = name
        self.order = order
        self.status = status
        self.statusMessage = statusMessage
        self.startedAt = startedAt
        self.completedAt = completedAt
        self.estimatedCompletionAt = estimatedCompletionAt
        self.processedItems = processedItems
        self.totalItems = totalItems

    @classmethod
    def fields(cls) -> str:
        return """
            id
            taskId
            name
            order
            status
            statusMessage
            startedAt
            completedAt
            estimatedCompletionAt
            processedItems
            totalItems
        """

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        taskId: str,
        name: str,
        order: int,
        status: str,
        statusMessage: Optional[str] = None,
        **kwargs
    ) -> 'TaskStage':
        input_data = {
            'taskId': taskId,
            'name': name,
            'order': order,
            'status': status
        }

        if statusMessage:
            input_data['statusMessage'] = statusMessage

        optional_fields = [
            'startedAt', 'completedAt', 'estimatedCompletionAt',
            'processedItems', 'totalItems'
        ]
        for field in optional_fields:
            if field in kwargs:
                input_data[field] = kwargs[field]

        mutation = """
        mutation CreateTaskStage($input: CreateTaskStageInput!) {
            createTaskStage(input: $input) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createTaskStage'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'TaskStage':
        # Convert datetime fields
        for date_field in ['startedAt', 'completedAt', 'estimatedCompletionAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )

        # Extract required fields first
        id = data.pop('id')
        taskId = data.pop('taskId')
        name = data.pop('name')
        order = data.pop('order')
        status = data.pop('status')

        # Create instance with required fields
        return cls(
            id=id,
            taskId=taskId,
            name=name,
            order=order,
            status=status,
            client=client,
            **data  # Pass remaining fields as kwargs
        )

    def update(self, **kwargs) -> 'TaskStage':
        """Update the task stage."""
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified")

        # Convert datetime fields to ISO format strings
        for field, value in kwargs.items():
            if isinstance(value, datetime):
                kwargs[field] = value.isoformat().replace('+00:00', 'Z')

        mutation = """
        mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
            updateTaskStage(input: $input) {
                id
                taskId
                name
                order
                status
                statusMessage
                startedAt
                completedAt
                estimatedCompletionAt
                processedItems
                totalItems
            }
        }
        """

        # Get current data to preserve required fields
        query = """
        query GetTaskStage($id: ID!) {
            getTaskStage(id: $id) {
                taskId
                name
                order
                status
            }
        }
        """
        result = self._client.execute(query, {'id': self.id})
        current_data = result.get('getTaskStage', {})

        # Prepare input data with all required fields
        input_data = {
            'id': self.id,
            'taskId': current_data['taskId'],
            'name': current_data['name'],
            'order': current_data['order'],
            'status': current_data['status']
        }

        # Only add optional fields if they have non-None values
        for key, value in kwargs.items():
            if value is not None or key in ['processedItems', 'totalItems']:
                input_data[key] = value

        # Execute update mutation
        result = self._client.execute(mutation, {'input': input_data})
        if not result or 'updateTaskStage' not in result:
            raise Exception(f"Failed to update TaskStage {self.id}")

        # Update instance with new data
        updated = result['updateTaskStage']
        for key, value in updated.items():
            if hasattr(self, key):
                setattr(self, key, value)

        return self

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'TaskStage':
        query = """
        query GetTaskStage($id: ID!) {
            getTaskStage(id: $id) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'id': id})
        if not result or 'getTaskStage' not in result:
            raise Exception(f"Failed to get TaskStage {id}")

        return cls.from_dict(result['getTaskStage'], client)

    def start_processing(self) -> None:
        """Mark the stage as started and update its status."""
        update_fields = {
            "status": "RUNNING",
            "statusMessage": "Processing..."
        }
        self.update(**update_fields)

    def complete_processing(self) -> None:
        """Mark the stage as completed."""
        self.update(
            status="COMPLETED",
            statusMessage="Complete",
            completedAt=datetime.now(timezone.utc)
        )

    def fail_processing(self, error_message: str) -> None:
        """Mark the stage as failed with error information."""
        self.update(
            status="FAILED",
            statusMessage=error_message
        ) 