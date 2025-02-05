from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from .base import BaseModel
from ..client import _BaseAPIClient
import logging
import uuid

if TYPE_CHECKING:
    from .task_stage import TaskStage

@dataclass
class Task(BaseModel):
    accountId: str
    type: str
    status: str
    target: str
    command: str
    metadata: Optional[Dict] = None
    createdAt: Optional[datetime] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    estimatedCompletionAt: Optional[datetime] = None
    errorMessage: Optional[str] = None
    errorDetails: Optional[Dict] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    currentStageId: Optional[str] = None
    workerNodeId: Optional[str] = None
    dispatchStatus: Optional[str] = None
    lock_token: Optional[str] = None
    lock_expires: Optional[datetime] = None

    def __init__(
        self,
        id: str,
        accountId: str,
        type: str,
        status: str,
        target: str,
        command: str,
        metadata: Optional[Dict] = None,
        createdAt: Optional[datetime] = None,
        startedAt: Optional[datetime] = None,
        completedAt: Optional[datetime] = None,
        estimatedCompletionAt: Optional[datetime] = None,
        errorMessage: Optional[str] = None,
        errorDetails: Optional[Dict] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        currentStageId: Optional[str] = None,
        workerNodeId: Optional[str] = None,
        dispatchStatus: Optional[str] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.type = type
        self.status = status
        self.target = target
        self.command = command
        self.metadata = metadata
        self.createdAt = createdAt
        self.startedAt = startedAt
        self.completedAt = completedAt
        self.estimatedCompletionAt = estimatedCompletionAt
        self.errorMessage = errorMessage
        self.errorDetails = errorDetails
        self.stdout = stdout
        self.stderr = stderr
        self.currentStageId = currentStageId
        self.workerNodeId = workerNodeId
        self.dispatchStatus = dispatchStatus

    @classmethod
    def fields(cls) -> str:
        return """
            id
            accountId
            type
            status
            target
            command
            metadata
            createdAt
            startedAt
            completedAt
            estimatedCompletionAt
            errorMessage
            errorDetails
            stdout
            stderr
            currentStageId
            workerNodeId
            dispatchStatus
            stages {
                items {
                    id
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

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        accountId: str,
        type: str,
        target: str,
        command: str,
        metadata: Optional[Dict] = None,
        **kwargs
    ) -> 'Task':
        input_data = {
            'accountId': accountId,
            'type': type,
            'target': target,
            'command': command,
            'status': kwargs.pop('status', 'PENDING'),
            'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }

        if metadata:
            input_data['metadata'] = metadata

        optional_fields = [
            'startedAt', 'completedAt', 'estimatedCompletionAt',
            'errorMessage', 'errorDetails', 'stdout', 'stderr',
            'currentStageId', 'workerNodeId', 'dispatchStatus'
        ]
        for field in optional_fields:
            if field in kwargs:
                input_data[field] = kwargs[field]

        mutation = """
        mutation CreateTask($input: CreateTaskInput!) {
            createTask(input: $input) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createTask'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Task':
        for date_field in ['createdAt', 'startedAt', 'completedAt', 'estimatedCompletionAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )

        filtered_data = {k: v for k, v in data.items() if k != 'stages'}
        return cls(client=client, **filtered_data)

    def update(self, **kwargs) -> 'Task':
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified")

        # Convert datetime fields to ISO format strings
        for field, value in kwargs.items():
            if isinstance(value, datetime):
                kwargs[field] = value.isoformat().replace('+00:00', 'Z')

        mutation = """
        mutation UpdateTask($input: UpdateTaskInput!) {
            updateTask(input: $input) {
                %s
            }
        }
        """ % self.fields()

        query = """
        query GetTask($id: ID!) {
            getTask(id: $id) {
                accountId
                type
                status
                target
                command
            }
        }
        """
        result = self._client.execute(query, {'id': self.id})
        current_data = result.get('getTask', {})

        input_data = {
            'id': self.id,
            'accountId': current_data['accountId'],
            'type': current_data['type'],
            'status': current_data['status'],
            'target': current_data['target'],
            'command': current_data['command'],
            **kwargs
        }

        result = self._client.execute(mutation, {'input': input_data})
        return self.from_dict(result['updateTask'], self._client)

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'Task':
        query = """
        query GetTask($id: ID!) {
            getTask(id: $id) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'id': id})
        if not result or 'getTask' not in result:
            raise Exception(f"Failed to get Task {id}")

        return cls.from_dict(result['getTask'], client)

    def get_stages(self) -> List['TaskStage']:
        from .task_stage import TaskStage
        query = """
        query ListTaskStages($taskId: String!) {
            listTaskStages(filter: { taskId: { eq: $taskId } }) {
                items {
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
        }
        """
        result = self._client.execute(query, {'taskId': self.id})
        stages = result.get('listTaskStages', {}).get('items', [])
        return [TaskStage.from_dict(stage, self._client) for stage in stages]

    def start_processing(self) -> None:
        """Mark the task as started."""
        self.update(
            status='RUNNING',
            startedAt=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        )

    def complete_processing(self) -> None:
        """Mark the task as completed."""
        self.update(
            status="COMPLETED",
            completedAt=datetime.now(timezone.utc)
        )

    def fail_processing(
        self,
        error_message: str,
        error_details: Optional[Dict] = None
    ) -> None:
        """Mark the task as failed with error information."""
        self.update(
            status="FAILED",
            errorMessage=error_message,
            errorDetails=error_details,
            completedAt=datetime.now(timezone.utc)
        )

    def update_progress(
        self,
        current_items: int,
        total_items: int,
        stage_configs: Dict[str, Dict],
        estimated_completion_at: Optional[datetime] = None
    ) -> List['TaskStage']:
        """Update task progress and stage information."""
        now = datetime.now(timezone.utc)
        
        # Update task progress
        self.update(
            estimatedCompletionAt=estimated_completion_at
        )
        
        # Get existing stages
        stages = self.get_stages()
        existing_stage_names = {s.name for s in stages}
        
        # Only create new stages for configs that don't have matching existing stages
        for name, config in stage_configs.items():
            if name not in existing_stage_names:
                stage = self.create_stage(
                    name=name,
                    order=config.get("order", 0)
                )
                stages.append(stage)
        
        # Update all stages
        for stage in stages:
            if stage.name in stage_configs:
                config = stage_configs[stage.name]
                processed = config.get("processedItems", 0)
                total = config.get("totalItems", 0)
                
                # Update stage
                stage.update(
                    processedItems=processed,
                    totalItems=total,
                    statusMessage=config.get("statusMessage"),
                    status="RUNNING" if processed < total else "COMPLETED",
                    startedAt=now if processed > 0 else None,
                    completedAt=now if processed == total else None
                )
        
        return stages

    def fail_current_stage(
        self,
        error_message: str,
        error_details: Optional[Dict] = None
    ) -> None:
        """Mark the current running stage as failed."""
        stages = self.get_stages()
        for stage in stages:
            if stage.status == "RUNNING":
                stage.update(
                    status="FAILED",
                    statusMessage=error_message,
                    completedAt=datetime.now(timezone.utc)
                )

    def acquire_lock(self, timeout=1800):
        if self.lock_token and self.lock_expires > datetime.now(timezone.utc):
            raise Exception("Task already locked")
        self.lock_token = str(uuid.uuid4())
        self.lock_expires = datetime.now(timezone.utc) + timedelta(seconds=timeout)
        self.update(lock_token=self.lock_token, lock_expires=self.lock_expires)

    def release_lock(self):
        self.update(lock_token=None, lock_expires=None)

    def create_stage(self, name: str, order: int) -> 'TaskStage':
        """Create a new TaskStage for this Task."""
        from .task_stage import TaskStage
        
        mutation = """
        mutation CreateTaskStage($input: CreateTaskStageInput!) {
            createTaskStage(input: $input) {
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
        
        variables = {
            'input': {
                'taskId': self.id,
                'name': name,
                'order': order,
                'status': 'PENDING'
            }
        }
        
        result = self._client.execute(mutation, variables)
        stage_data = result.get('createTaskStage')
        if not stage_data:
            raise Exception("Failed to create TaskStage")
        
        return TaskStage.from_dict(stage_data, self._client) 