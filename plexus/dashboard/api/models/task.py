from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from .base import BaseModel
from .account import Account
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
    description: Optional[str] = None
    metadata: Optional[Dict] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
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
    scorecardId: Optional[str] = None
    scoreId: Optional[str] = None

    def __init__(
        self,
        id: str,
        accountId: str,
        type: str,
        status: str,
        target: str,
        command: str,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        createdAt: Optional[datetime] = None,
        updatedAt: Optional[datetime] = None,
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
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.type = type
        self.status = status
        self.target = target
        self.command = command
        self.description = description
        self.metadata = metadata
        self.createdAt = createdAt
        self.updatedAt = updatedAt
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
        self.scorecardId = scorecardId
        self.scoreId = scoreId

    @classmethod
    def fields(cls) -> str:
        return """
            id
            accountId
            type
            status
            target
            command
            description
            metadata
            createdAt
            updatedAt
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
            scorecardId
            scoreId
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
    def _get_account_id(cls, client) -> str:
        """Get the account ID for the call-criteria account."""
        account = Account.list_by_key(client, "call-criteria")
        if not account:
            raise ValueError("No account found with key: call-criteria")
        return account.id

    @classmethod
    def create(cls, client, type: str, target: str, command: str, **kwargs) -> 'Task':
        """Create a new task record.
        
        Args:
            client: The API client instance
            type: Task type
            target: Task target
            command: Command string
            **kwargs: Additional task fields
        
        Returns:
            Task: The created task instance
        """
        # Get the account ID if not provided
        if 'accountId' not in kwargs:
            kwargs['accountId'] = cls._get_account_id(client)

        # Prepare input data
        input_data = {
            "type": type,
            "target": target,
            "command": command,
            "status": "PENDING",  # Default status for new tasks
            **kwargs
        }

        # Create task with account ID
        response = client.execute(
            """
            mutation CreateTask($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    type
                    target
                    command
                    accountId
                    status
                    description
                    dispatchStatus
                    metadata
                    createdAt
                    updatedAt
                    startedAt
                    completedAt
                    estimatedCompletionAt
                    errorMessage
                    errorDetails
                    stdout
                    stderr
                    currentStageId
                }
            }
            """,
            {"input": input_data}
        )

        if 'errors' in response:
            raise ValueError(f"Failed to create task: {response['errors']}")

        task_data = response['createTask']
        return cls.from_dict(task_data, client)

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Safely parse a datetime value from various formats."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                # Try parsing ISO format with Z
                if value.endswith('Z'):
                    value = value[:-1] + '+00:00'
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                try:
                    # Fallback to parsing with dateutil
                    from dateutil import parser
                    return parser.parse(value)
                except:
                    logging.error(f"Failed to parse datetime value: {value}")
                    return None
        return None

    @staticmethod
    def _format_datetime(dt: Optional[datetime]) -> Optional[str]:
        """Safely format a datetime value to ISO format with Z."""
        if not dt:
            return None
        try:
            # Ensure the datetime is UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            elif dt.tzinfo != timezone.utc:
                dt = dt.astimezone(timezone.utc)
            return dt.isoformat().replace('+00:00', 'Z')
        except Exception as e:
            logging.error(f"Failed to format datetime: {e}")
            return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Task':
        # Convert datetime fields
        for date_field in ['createdAt', 'updatedAt', 'startedAt', 'completedAt', 'estimatedCompletionAt']:
            if date_field in data:
                data[date_field] = cls._parse_datetime(data[date_field])

        # Store stages data for later access if needed
        stages_data = data.pop('stages', None)
        
        # Create instance with remaining fields
        task = cls(client=client, **data)
        
        # Store stages data if present
        if stages_data and 'items' in stages_data:
            task._stages = stages_data['items']
        
        return task

    def update(self, **kwargs) -> 'Task':
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified")

        # Convert datetime fields to ISO format strings
        for field, value in list(kwargs.items()):
            if isinstance(value, datetime):
                kwargs[field] = self._format_datetime(value)
            elif value is None:
                kwargs[field] = None

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
            startedAt=self._format_datetime(datetime.now(timezone.utc))
        )

    def complete_processing(self) -> None:
        """Mark the task as completed."""
        self.update(
            status="COMPLETED",
            completedAt=self._format_datetime(datetime.now(timezone.utc))
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
            completedAt=self._format_datetime(datetime.now(timezone.utc))
        )

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
        
        # Always include the task's start time when creating a stage
        variables = {
            'input': {
                'taskId': self.id,
                'name': name,
                'order': order,
                'status': 'PENDING',
                'startedAt': self._format_datetime(self.startedAt) if self.startedAt else None
            }
        }
        
        result = self._client.execute(mutation, variables)
        stage_data = result.get('createTaskStage')
        if not stage_data:
            raise Exception("Failed to create TaskStage")
        
        stage = TaskStage.from_dict(stage_data, self._client)
        
        # Update task's currentStageId if this is the first stage
        if order == 1:
            self.update(currentStageId=stage.id)
        
        return stage

    def advance_stage(self, stage: 'TaskStage') -> None:
        """Update the task's current stage."""
        # First, ensure the stage has the task's original start time
        if self.startedAt:
            stage.update(startedAt=self.startedAt.isoformat().replace('+00:00', 'Z'))
        
        # Then update the current stage ID
        self.update(currentStageId=stage.id)

    def update_progress(
        self,
        current_items: int,
        total_items: int,
        stage_configs: Dict[str, Dict],
        estimated_completion_at: Optional[datetime] = None
    ) -> List['TaskStage']:
        """Update task progress and stage information."""
        now = datetime.now(timezone.utc)
        
        # Only update estimated completion time
        # Never modify startedAt - it should be set once when the task is created/started
        self.update(estimatedCompletionAt=estimated_completion_at)
        
        # Get existing stages
        stages = self.get_stages()
        existing_stages = {s.name: s for s in stages}
        created_stages = []
        
        # Create or update stages
        for name, config in stage_configs.items():
            if name in existing_stages:
                stage = existing_stages[name]
            else:
                stage = self.create_stage(
                    name=name,
                    order=config.get("order", 0)
                )
                created_stages.append(stage)
            
            # Update stage with all UI-required fields
            update_data = {
                "status": config.get("status", "PENDING"),
                "statusMessage": config.get("statusMessage"),
                "completedAt": config.get("completedAt"),
                "estimatedCompletionAt": config.get("estimatedCompletionAt")
            }
            
            # Only add progress tracking fields if they're explicitly set in config
            if "processedItems" in config:
                update_data["processedItems"] = config["processedItems"]
            if "totalItems" in config:
                update_data["totalItems"] = config["totalItems"]
                
            # ALWAYS use the task's original start time for all stages
            # This ensures consistent timing across the entire task
            if self.startedAt:
                update_data["startedAt"] = self.startedAt.isoformat().replace('+00:00', 'Z')
            
            # Remove None values to avoid overwriting existing data
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            # Update the stage
            stage.update(**update_data)
            
        # Return all stages including newly created ones
        return stages + created_stages

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