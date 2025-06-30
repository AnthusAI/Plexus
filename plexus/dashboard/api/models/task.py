from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from .base import BaseModel
from .account import Account
from ..client import _BaseAPIClient
import logging
import uuid
import json

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

        # Get current timestamp for createdAt and updatedAt
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Prepare input data
        input_data = {
            "type": type,
            "target": target,
            "command": command,
            "status": "PENDING",  # Default status for new tasks
            "createdAt": now,
            "updatedAt": now,  # Set initial updatedAt
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

    @classmethod
    def create_with_stages(cls, client, type: str, target: str, command: str, stages: list, **kwargs) -> 'Task':
        """Create a new task record with stages in a single GraphQL request.
        
        Args:
            client: The API client instance
            type: Task type
            target: Task target
            command: Command string
            stages: List of stage configurations in the format 
                   [{"name": str, "order": int, "status": str, "statusMessage": str, 
                     "totalItems": int, "estimatedCompletionAt": str}]
            **kwargs: Additional task fields
        
        Returns:
            Task: The created task instance with stages initialized
        """
        # Get the account ID if not provided
        if 'accountId' not in kwargs:
            kwargs['accountId'] = cls._get_account_id(client)

        # Get current timestamp for createdAt and updatedAt
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Prepare input data
        input_data = {
            "type": type,
            "target": target,
            "command": command,
            "status": "PENDING",  # Default status for new tasks
            "createdAt": now,
            "updatedAt": now,  # Set initial updatedAt
            **kwargs
        }

        # Execute a multi-operation request that creates the task and all stages in one HTTP call
        # Each operation needs a unique name in the multi-operation request
        operations = """
        mutation CreateTaskAndStages(
            $taskInput: CreateTaskInput!
            $stage1: CreateTaskStageInput
            $stage2: CreateTaskStageInput
            $stage3: CreateTaskStageInput
            $stage4: CreateTaskStageInput
            $stage5: CreateTaskStageInput
        ) {
            # First create the task
            createTask(input: $taskInput) {
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
                scorecardId
                scoreId
            }
            
            # Then create each stage if variables are provided
            stage1: createTaskStage(input: $stage1) @include(if: $hasStage1) {
                id
                taskId
                name
                order
                status
                statusMessage
                totalItems
            }
            
            stage2: createTaskStage(input: $stage2) @include(if: $hasStage2) {
                id
                taskId
                name
                order
                status
                statusMessage
                totalItems
            }
            
            stage3: createTaskStage(input: $stage3) @include(if: $hasStage3) {
                id
                taskId
                name
                order
                status
                statusMessage
                totalItems
            }
            
            stage4: createTaskStage(input: $stage4) @include(if: $hasStage4) {
                id
                taskId
                name
                order
                status
                statusMessage
                totalItems
            }
            
            stage5: createTaskStage(input: $stage5) @include(if: $hasStage5) {
                id
                taskId
                name
                order
                status
                statusMessage
                totalItems
            }
        }
        """
        
        # Prepare variables with conditional flags for stage inclusion
        variables = {
            "taskInput": input_data,
            "hasStage1": False,
            "hasStage2": False,
            "hasStage3": False,
            "hasStage4": False,
            "hasStage5": False,
        }
        
        # Maximum of 5 stages in a single request
        if len(stages) > 5:
            raise ValueError("Cannot create more than 5 stages in a single request")
        
        # Add stage variables
        for i, stage in enumerate(stages, 1):
            stage_key = f"stage{i}"
            has_stage_key = f"hasStage{i}"
            
            variables[has_stage_key] = True
            variables[stage_key] = {
                "name": stage["name"],
                "order": stage["order"],
                "status": stage.get("status", "PENDING"),
                # Dummy taskId will be replaced after task creation
                "taskId": "PLACEHOLDER"
            }
            
            # Add optional fields
            if "statusMessage" in stage:
                variables[stage_key]["statusMessage"] = stage["statusMessage"]
            if "totalItems" in stage:
                variables[stage_key]["totalItems"] = stage["totalItems"]
            if "estimatedCompletionAt" in stage:
                variables[stage_key]["estimatedCompletionAt"] = stage["estimatedCompletionAt"]
        
        try:
            # Create the task first
            create_response = client.execute(
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
                        scorecardId
                        scoreId
                    }
                }
                """,
                {"input": input_data}
            )
            
            task_data = create_response['createTask']
            task_id = task_data['id']
            
            # Now create all stages with the actual task ID
            stage_data_list = []
            for i, stage in enumerate(stages):
                stage_input = {
                    "taskId": task_id,
                    "name": stage["name"],
                    "order": stage["order"],
                    "status": stage.get("status", "PENDING"),
                }
                
                # Add optional fields
                if "statusMessage" in stage:
                    stage_input["statusMessage"] = stage["statusMessage"]
                if "totalItems" in stage:
                    stage_input["totalItems"] = stage["totalItems"]
                if "estimatedCompletionAt" in stage:
                    stage_input["estimatedCompletionAt"] = stage["estimatedCompletionAt"]
                
                # Create the stage
                stage_response = client.execute(
                    """
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
                    """,
                    {"input": stage_input}
                )
                
                stage_data = stage_response['createTaskStage']
                stage_data_list.append(stage_data)
                
                # If this is the first stage, set it as the current stage
                if i == 0:
                    client.execute(
                        """
                        mutation UpdateTask($input: UpdateTaskInput!) {
                            updateTask(input: $input) {
                                id
                                currentStageId
                            }
                        }
                        """,
                        {
                            "input": {
                                "id": task_id,
                                "accountId": input_data["accountId"],
                                "type": input_data["type"],
                                "status": input_data["status"],
                                "target": input_data["target"],
                                "command": input_data["command"],
                                "currentStageId": stage_data["id"]
                            }
                        }
                    )
            
            # Create the task instance
            task = cls.from_dict(task_data, client)
            
            # Attach the stages data for later access
            task._stages = stage_data_list
            
            return task
            
        except Exception as e:
            logging.error(f"Failed to create task with stages: {str(e)}")
            raise ValueError(f"Failed to create task with stages: {str(e)}")

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
        """Get all stages for this task, handling pagination properly."""
        from .task_stage import TaskStage
        query = """
        query ListTaskStageByTaskId($taskId: String!, $limit: Int, $nextToken: String) {
            listTaskStageByTaskId(taskId: $taskId, limit: $limit, nextToken: $nextToken) {
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
                nextToken
            }
        }
        """
        all_stages = []
        next_token = None
        
        while True:
            variables = {
                'taskId': self.id,
                'limit': 100  # Fetch 100 stages at a time
            }
            if next_token:
                variables['nextToken'] = next_token
                
            result = self._client.execute(query, variables)
            response = result.get('listTaskStageByTaskId', {})
            stages = response.get('items', [])
            all_stages.extend(stages)
            
            next_token = response.get('nextToken')
            if not next_token:  # No more pages
                break
        
        return [TaskStage.from_dict(stage, self._client) for stage in all_stages]

    def start_processing(self) -> None:
        """Mark the task as started."""
        self.update(
            status='RUNNING',
            startedAt=self._format_datetime(datetime.now(timezone.utc))
        )

    def complete_processing(self):
        """Complete processing of the task."""
        # First update all stages to completed state
        stages = self.get_stages()
        for stage in stages:
            if stage.status != 'FAILED':  # Don't override failed stages
                stage.update(
                    status='COMPLETED',
                    completedAt=self._format_datetime(datetime.now(timezone.utc)),
                    startedAt=self._format_datetime(self.startedAt) if not stage.startedAt else stage.startedAt
                )

        # Then complete the task
        self.update(
            status="COMPLETED",
            completedAt=self._format_datetime(datetime.now(timezone.utc))
        )

    def fail_processing(
        self,
        error_message: str,
        error_details: Optional[Dict] = None,
        current_items: Optional[int] = None
    ) -> None:
        """Mark the task as failed with error information.
        
        Args:
            error_message: The error message to display
            error_details: Optional dictionary of additional error details
            current_items: The number of items processed when the failure occurred
        """
        # First fail the current stage with the error message and progress count
        self.fail_current_stage(error_message, error_details, current_items)
        
        # Then update the task level status and error info with all required fields
        update_data = {
            'accountId': self.accountId,
            'type': self.type,
            'status': 'FAILED',
            'target': self.target,
            'command': self.command,
            'errorMessage': error_message,
            'completedAt': self._format_datetime(datetime.now(timezone.utc)),
            'updatedAt': self._format_datetime(datetime.now(timezone.utc))
        }
        if error_details:
            update_data['errorDetails'] = json.dumps(error_details)
            
        self.update(**update_data)

    def fail_current_stage(
        self,
        error_message: str,
        error_details: Optional[Dict] = None,
        current_items: Optional[int] = None
    ) -> None:
        """Mark the current running stage as failed with error message and progress.
        
        Args:
            error_message: The error message to display
            error_details: Optional dictionary of additional error details
            current_items: The number of items processed when the failure occurred
        """
        stages = self.get_stages()
        logging.info(f"Looking for stage to fail among {len(stages)} stages")
        
        # First try to find the stage by currentStageId
        current_stage = None
        if self.currentStageId:
            current_stage = next((s for s in stages if s.id == self.currentStageId), None)
            if current_stage:
                logging.info(f"Found current stage by ID: {current_stage.name} (status: {current_stage.status})")
            else:
                logging.warning(f"Could not find stage with ID {self.currentStageId}")
        
        # Fallback to finding a RUNNING stage if we couldn't find by ID
        if not current_stage:
            running_stages = [s for s in stages if s.status == "RUNNING"]
            if running_stages:
                current_stage = running_stages[0]
                logging.info(f"Found running stage: {current_stage.name}")
            else:
                logging.error("No RUNNING stage found to fail! Current stages:")
                for stage in stages:
                    logging.error(f"  - {stage.name}: {stage.status}")
                return
        
        # Update the stage status
        logging.info(f"Failing stage '{current_stage.name}' with error: {error_message}")
        update_data = {
            "status": "FAILED",
            "statusMessage": f"Error: {error_message}",  # Prefix with "Error:" to make it clear this is an error
            "completedAt": self._format_datetime(datetime.now(timezone.utc))
        }
        
        # Include the final progress count if available
        if current_items is not None:
            update_data["processedItems"] = current_items
            logging.info(f"Including final progress count: {current_items} items")
        
        # Update the stage with all the failure information
        try:
            current_stage.update(**update_data)
            logging.info(f"Successfully updated stage '{current_stage.name}' to FAILED status")
            
            # Verify the update was successful
            updated_stage = next((s for s in self.get_stages() if s.id == current_stage.id), None)
            if updated_stage:
                logging.info(f"Verified stage status is now: {updated_stage.status}")
                if updated_stage.status != "FAILED":
                    logging.error(f"Stage status update failed! Expected FAILED but got {updated_stage.status}")
            else:
                logging.error("Could not verify stage status after update")
                
        except Exception as e:
            logging.error(f"Failed to update stage '{current_stage.name}' status: {str(e)}", exc_info=True)
            raise  # Re-raise to prevent silent failures

    def create_stage(
        self,
        name: str,
        order: int,
        status: str = 'PENDING',
        status_message: Optional[str] = None,
        total_items: Optional[int] = None,
        estimated_completion_at: Optional[str] = None,
        **kwargs
    ) -> 'TaskStage':
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
        
        # Build input data with all fields
        variables = {
            'input': {
                'taskId': self.id,
                'name': name,
                'order': order,
                'status': status
            }
        }

        # Add optional fields if provided
        if status_message:
            variables['input']['statusMessage'] = status_message
        if total_items is not None:
            variables['input']['totalItems'] = total_items
        if estimated_completion_at:
            variables['input']['estimatedCompletionAt'] = estimated_completion_at
        if self.startedAt:
            variables['input']['startedAt'] = self._format_datetime(self.startedAt)
        
        # Add any additional fields from kwargs
        for key, value in kwargs.items():
            # Explicitly skip the 'client' argument if passed via kwargs
            if key == 'client':
                continue
            if value is not None:
                variables['input'][key] = value
        
        logging.info(f"Executing CreateTaskStage mutation with variables: {variables}")
        result = self._client.execute(mutation, variables)
        
        # Check for GraphQL errors
        if 'errors' in result:
            error_messages = [error.get('message', 'Unknown error') for error in result['errors']]
            error_str = '; '.join(error_messages)
            logging.error(f"GraphQL errors creating stage: {error_str}")
            logging.error(f"Full error response: {result['errors']}")
            raise Exception(f"Failed to create TaskStage: {error_str}")
            
        stage_data = result.get('createTaskStage')
        if not stage_data:
            logging.error(f"No data returned from createTaskStage mutation. Full response: {result}")
            raise Exception("Failed to create TaskStage - no data returned")
        
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

    def acquire_lock(self, timeout=1800):
        if self.lock_token and self.lock_expires > datetime.now(timezone.utc):
            raise Exception("Task already locked")
        self.lock_token = str(uuid.uuid4())
        self.lock_expires = datetime.now(timezone.utc) + timedelta(seconds=timeout)
        self.update(lock_token=self.lock_token, lock_expires=self.lock_expires)

    def release_lock(self):
        self.update(lock_token=None, lock_expires=None)

    @classmethod
    def list_tasks(cls, client: _BaseAPIClient, updated_at: str = "", limit: int = 100) -> List['Task']:
        """List tasks using the listTaskByUpdatedAt query for proper pagination.
        
        Args:
            client: The API client instance
            updated_at: The updatedAt timestamp to start from (empty string for most recent)
            limit: Maximum number of tasks to return per page
            
        Returns:
            List[Task]: List of Task instances
        """
        query = """
        query ListTaskByUpdatedAt($updatedAt: String!, $limit: Int, $nextToken: String) {
            listTaskByUpdatedAt(updatedAt: $updatedAt, limit: $limit, nextToken: $nextToken) {
                items {
                    %s
                }
                nextToken
            }
        }
        """ % cls.fields()
        
        all_tasks = []
        next_token = None
        
        while True:
            variables = {
                'updatedAt': updated_at,
                'limit': limit
            }
            if next_token:
                variables['nextToken'] = next_token
                
            result = client.execute(query, variables)
            response = result.get('listTaskByUpdatedAt', {})
            tasks = response.get('items', [])
            all_tasks.extend(tasks)
            
            next_token = response.get('nextToken')
            if not next_token:  # No more pages
                break
        
        return [cls.from_dict(task, client) for task in all_tasks] 