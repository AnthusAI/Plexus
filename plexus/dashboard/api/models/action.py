from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient

if TYPE_CHECKING:
    from .action_stage import ActionStage

@dataclass
class Action(BaseModel):
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
    ) -> 'Action':
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
            'currentStageId'
        ]
        for field in optional_fields:
            if field in kwargs:
                input_data[field] = kwargs[field]

        mutation = """
        mutation CreateAction($input: CreateActionInput!) {
            createAction(input: $input) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createAction'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Action':
        for date_field in ['createdAt', 'startedAt', 'completedAt', 'estimatedCompletionAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )

        filtered_data = {k: v for k, v in data.items() if k != 'stages'}
        return cls(client=client, **filtered_data)

    def update(self, **kwargs) -> 'Action':
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified")

        # Convert datetime fields to ISO format strings
        for field, value in kwargs.items():
            if isinstance(value, datetime):
                kwargs[field] = value.isoformat().replace('+00:00', 'Z')

        mutation = """
        mutation UpdateAction($input: UpdateActionInput!) {
            updateAction(input: $input) {
                %s
            }
        }
        """ % self.fields()

        query = """
        query GetAction($id: ID!) {
            getAction(id: $id) {
                accountId
                type
                status
                target
                command
            }
        }
        """
        result = self._client.execute(query, {'id': self.id})
        current_data = result.get('getAction', {})

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
        return self.from_dict(result['updateAction'], self._client)

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'Action':
        query = """
        query GetAction($id: ID!) {
            getAction(id: $id) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'id': id})
        if not result or 'getAction' not in result:
            raise Exception(f"Failed to get Action {id}")

        return cls.from_dict(result['getAction'], client)

    def get_stages(self) -> List['ActionStage']:
        from .action_stage import ActionStage
        query = """
        query ListActionStages($actionId: String!) {
            listActionStages(filter: { actionId: { eq: $actionId } }) {
                items {
                    id
                    actionId
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
        result = self._client.execute(query, {'actionId': self.id})
        stages = result.get('listActionStages', {}).get('items', [])
        return [ActionStage.from_dict(stage, self._client) for stage in stages]

    def start_processing(self) -> None:
        """Mark the action as started and update its status."""
        self.update(
            status="RUNNING",
            startedAt=datetime.now(timezone.utc)
        )

    def complete_processing(self) -> None:
        """Mark the action as completed."""
        self.update(
            status="COMPLETED",
            completedAt=datetime.now(timezone.utc)
        )

    def fail_processing(
        self,
        error_message: str,
        error_details: Optional[Dict] = None
    ) -> None:
        """Mark the action as failed with error information."""
        self.update(
            status="FAILED",
            errorMessage=error_message,
            errorDetails=error_details,
            completedAt=datetime.now(timezone.utc)
        )

    def update_progress(
        self,
        processed_items: int,
        total_items: int,
        stage_configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List['ActionStage']:
        """
        Update progress for action stages.
        
        Args:
            processed_items: Number of items processed so far
            total_items: Total number of items to process
            stage_configs: Optional dict mapping stage names to their configs:
                {
                    "stage_name": {
                        "order": int,
                        "totalItems": int,
                        "processedItems": int
                    }
                }
                If not provided, stages won't be created/updated
        
        Returns:
            List of current stages in order
        """
        from .action_stage import ActionStage

        if not stage_configs:
            return []

        # Update action status based on progress
        if processed_items == 0:
            if self.status not in ["COMPLETED", "FAILED"]:
                self.update(status="PENDING")
        elif processed_items == total_items:
            if self.status != "COMPLETED":
                self.update(
                    status="COMPLETED",
                    completedAt=datetime.now(timezone.utc)
                )
        else:
            if self.status != "RUNNING":
                self.update(
                    status="RUNNING",
                    startedAt=datetime.now(timezone.utc)
                )

        # Get or create stages
        stages = self.get_stages()
        existing_stage_names = {stage.name for stage in stages}
        
        # Create any missing stages
        for name, config in stage_configs.items():
            if name not in existing_stage_names:
                stages.append(ActionStage.create(
                    client=self._client,
                    actionId=self.id,
                    name=name,
                    order=config["order"],
                    status="PENDING",
                    processedItems=0,
                    totalItems=config["totalItems"]
                ))

        # Sort stages by order
        stages.sort(key=lambda s: s.order)

        # Update stage progress
        for stage in stages:
            config = stage_configs.get(stage.name)
            if not config:
                continue

            processed = config.get("processedItems", 0)
            total = config.get("totalItems", 0)

            # Determine if this stage should be running
            if processed == 0:
                if stage.status not in ["COMPLETED", "FAILED"]:
                    stage.update(status="PENDING")
            elif processed == total:
                if stage.status != "COMPLETED":
                    stage.update(
                        status="COMPLETED",
                        completedAt=datetime.now(timezone.utc),
                        processedItems=total,
                        totalItems=total
                    )
            else:
                if stage.status != "RUNNING":
                    stage.update(
                        status="RUNNING",
                        startedAt=datetime.now(timezone.utc)
                    )
                stage.update(
                    processedItems=processed,
                    totalItems=total
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