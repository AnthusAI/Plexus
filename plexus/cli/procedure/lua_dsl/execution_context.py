"""
Execution context abstraction for Procedure DSL.

Provides dual execution backend support:
- LocalExecutionContext: Database checkpoints with exit-and-resume
- LambdaDurableExecutionContext: AWS Lambda Durable Functions (future)

Same procedure code works in both contexts.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Callable, Dict, List
from dataclasses import dataclass
from datetime import datetime, timezone
import json


class GraphQLServiceAdapter:
    """
    Adapter that provides query() and mutate() interface for PlexusDashboardClient.

    ExecutionContext expects a GraphQL service with query() and mutate() methods,
    but PlexusDashboardClient has a unified execute() method for both operations.
    This adapter bridges the gap.
    """
    def __init__(self, client):
        """
        Args:
            client: PlexusDashboardClient instance with synchronous execute() method
        """
        self.client = client

    def query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        return self.client.execute(query, variables)

    def mutate(self, mutation: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL mutation."""
        return self.client.execute(mutation, variables)


@dataclass
class HumanResponse:
    """Response from a human interaction."""
    value: Any
    responded_at: str


class ProcedureWaitingForHuman(Exception):
    """
    Raised to exit workflow when waiting for human response.

    In LocalExecutionContext, this signals the runtime to:
    1. Update Procedure.status to 'WAITING_FOR_HUMAN'
    2. Save the pending message ID
    3. Exit cleanly
    4. Wait for resume trigger
    """
    def __init__(self, procedure_id: str, pending_message_id: str):
        self.procedure_id = procedure_id
        self.pending_message_id = pending_message_id
        super().__init__(f"Procedure {procedure_id} waiting for human response to message {pending_message_id}")


class ExecutionContext(ABC):
    """
    Protocol for execution backends.

    Abstracts over local execution (DB checkpoints) and Lambda Durable
    Functions (native suspend/resume).
    """

    @abstractmethod
    def step_run(self, name: str, fn: Callable[[], Any]) -> Any:
        """
        Execute fn with checkpointing. On replay, return stored result.

        Args:
            name: Unique checkpoint name
            fn: Function to execute (must be deterministic)

        Returns:
            Result of fn() on first execution, cached result on replay
        """
        pass

    @abstractmethod
    def wait_for_human(
        self,
        request_type: str,
        message: str,
        timeout_seconds: Optional[int],
        default_value: Any,
        options: Optional[List[dict]],
        metadata: dict
    ) -> HumanResponse:
        """
        Suspend until human responds.

        Args:
            request_type: 'approval', 'input', or 'review'
            message: Message to display to human
            timeout_seconds: Timeout in seconds, None = wait forever
            default_value: Value to return on timeout
            options: For review requests: [{label, type}, ...]
            metadata: Additional context data

        Returns:
            HumanResponse with value and timestamp

        Raises:
            ProcedureWaitingForHuman: (Local context) Exits to wait for resume
        """
        pass

    @abstractmethod
    def sleep(self, seconds: int) -> None:
        """
        Sleep without consuming resources.

        Local context: Creates checkpoint and exits
        Lambda context: Uses Lambda wait (zero cost)
        """
        pass

    @abstractmethod
    def checkpoint_clear_all(self) -> None:
        """Clear all checkpoints. Used for testing."""
        pass

    @abstractmethod
    def checkpoint_clear_after(self, name: str) -> None:
        """Clear checkpoint and all subsequent ones. Used for testing."""
        pass

    @abstractmethod
    def checkpoint_exists(self, name: str) -> bool:
        """Check if checkpoint exists."""
        pass

    @abstractmethod
    def checkpoint_get(self, name: str) -> Optional[Any]:
        """Get cached checkpoint value, or None if not found."""
        pass


class LocalExecutionContext(ExecutionContext):
    """
    Local execution context using database checkpoints.

    Checkpoints stored in Procedure.metadata JSON field:
    {
        "checkpoints": {
            "step_name": {
                "result": <value>,
                "completed_at": "2024-12-04T10:00:00Z"
            }
        },
        "state": {...},
        "lua_state": {...}
    }
    """

    def __init__(
        self,
        procedure_id: str,
        session_id: str,
        graphql_service: Any,
        chat_recorder: Any
    ):
        """
        Initialize local execution context.

        Args:
            procedure_id: ID of the running procedure
            session_id: Associated chat session ID
            graphql_service: Service for GraphQL queries/mutations
            chat_recorder: ChatRecorder for message operations
        """
        self.procedure_id = procedure_id
        self.session_id = session_id
        self.graphql_service = graphql_service
        self.chat_recorder = chat_recorder

        # Load procedure and metadata
        self.procedure = self._load_procedure()

        # Parse metadata JSON string
        metadata_str = self.procedure.get('metadata')
        if metadata_str:
            try:
                self.metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            except json.JSONDecodeError:
                self.metadata = {}
        else:
            self.metadata = {}

        self.checkpoints: Dict[str, dict] = self.metadata.get('checkpoints', {})

    def _load_procedure(self) -> dict:
        """Load procedure record from database."""
        query = """
            query GetProcedure($id: ID!) {
                getProcedure(id: $id) {
                    id
                    status
                    metadata
                    waitingOnMessageId
                }
            }
        """
        result = self.graphql_service.query(query, {'id': self.procedure_id})
        return result['getProcedure']

    def _save_metadata(self) -> None:
        """Save metadata back to database."""
        self.metadata['checkpoints'] = self.checkpoints

        mutation = """
            mutation UpdateProcedureMetadata($id: ID!, $metadata: AWSJSON!) {
                updateProcedure(input: {id: $id, metadata: $metadata}) {
                    id
                }
            }
        """
        self.graphql_service.mutate(mutation, {
            'id': self.procedure_id,
            'metadata': json.dumps(self.metadata)
        })

    def _update_procedure_status(
        self,
        status: str,
        waiting_on_message_id: Optional[str] = None
    ) -> None:
        """Update procedure status."""
        mutation = """
            mutation UpdateProcedureStatus(
                $id: ID!
                $status: String!
                $waitingOnMessageId: String
            ) {
                updateProcedure(input: {
                    id: $id
                    status: $status
                    waitingOnMessageId: $waitingOnMessageId
                }) {
                    id
                }
            }
        """
        self.graphql_service.mutate(mutation, {
            'id': self.procedure_id,
            'status': status,
            'waitingOnMessageId': waiting_on_message_id
        })

    def step_run(self, name: str, fn: Callable[[], Any]) -> Any:
        """Execute with checkpoint replay."""
        if name in self.checkpoints:
            # Replay: return cached result
            return self.checkpoints[name]['result']

        # Execute and cache
        result = fn()
        self.checkpoints[name] = {
            'result': result,
            'completed_at': datetime.now(timezone.utc).isoformat()
        }
        self._save_metadata()
        return result

    def wait_for_human(
        self,
        request_type: str,
        message: str,
        timeout_seconds: Optional[int],
        default_value: Any,
        options: Optional[List[dict]],
        metadata: dict
    ) -> HumanResponse:
        """
        Wait for human response with exit-and-resume pattern.

        Flow:
        1. Check if procedure already has waitingOnMessageId (resuming)
        2. If yes, check for response to that specific message
        3. If response found, return it and continue
        4. If no response, check timeout
        5. If timed out, return default
        6. If still waiting, raise ProcedureWaitingForHuman to exit
        7. If no waitingOnMessageId, create new pending message (first time)
        """
        # Check if we're resuming from a previous HITL wait
        pending_message_id = self.procedure.get('waitingOnMessageId')

        if pending_message_id:
            # Resuming - we already have a pending message
            # Check for response to the specific message we're waiting for
            response = self._find_response_to(pending_message_id)

            if response:
                # Human responded! Clear the waiting state and return
                self._update_procedure_status('RUNNING', None)
                return HumanResponse(
                    value=self._parse_response(response, request_type),
                    responded_at=response['createdAt']
                )
            else:
                # Still waiting - need to get the pending message to check timeout
                pending = self._get_message_by_id(pending_message_id)

                if pending and self._is_timed_out(pending, timeout_seconds):
                    self._mark_timed_out(pending_message_id)
                    self._update_procedure_status('RUNNING', None)
                    return HumanResponse(
                        value=default_value,
                        responded_at=datetime.now(timezone.utc).isoformat()
                    )

                # Exit and wait for resume
                raise ProcedureWaitingForHuman(
                    procedure_id=self.procedure_id,
                    pending_message_id=pending_message_id
                )
        else:
            # First time - create the pending message
            pending_message = self._create_pending_message(
                request_type=request_type,
                message=message,
                timeout_seconds=timeout_seconds,
                default_value=default_value,
                options=options,
                metadata=metadata
            )

            # Update procedure status
            self._update_procedure_status('WAITING_FOR_HUMAN', pending_message['id'])

            # Exit and wait for resume
            raise ProcedureWaitingForHuman(
                procedure_id=self.procedure_id,
                pending_message_id=pending_message['id']
            )

    def _find_pending_request(self, request_type: str) -> Optional[dict]:
        """Find existing pending request of given type using GSI."""
        human_interaction_map = {
            'approval': 'PENDING_APPROVAL',
            'input': 'PENDING_INPUT',
            'review': 'PENDING_REVIEW',
            'escalation': 'PENDING_ESCALATION'
        }

        query = """
            query FindPendingMessage($sessionId: String!, $interaction: ChatMessageHumanInteraction!) {
                listChatMessageBySessionIdAndCreatedAt(
                    sessionId: $sessionId
                    filter: {
                        humanInteraction: {eq: $interaction}
                    }
                    sortDirection: DESC
                    limit: 1
                ) {
                    items {
                        id
                        content
                        metadata
                        createdAt
                    }
                }
            }
        """

        result = self.graphql_service.query(query, {
            'sessionId': self.session_id,
            'interaction': human_interaction_map[request_type]
        })

        items = result.get('listChatMessageBySessionIdAndCreatedAt', {}).get('items', [])
        return items[0] if items else None

    def _find_response_to(self, pending_message_id: str) -> Optional[dict]:
        """Find response message to a pending request using GSI."""
        query = """
            query FindResponse($parentId: String!) {
                listChatMessageByParentMessageId(
                    parentMessageId: $parentId
                    filter: {
                        humanInteraction: {eq: RESPONSE}
                    }
                    limit: 1
                ) {
                    items {
                        id
                        content
                        metadata
                        createdAt
                    }
                }
            }
        """

        result = self.graphql_service.query(query, {'parentId': pending_message_id})
        items = result.get('listChatMessageByParentMessageId', {}).get('items', [])
        return items[0] if items else None

    def _get_message_by_id(self, message_id: str) -> Optional[dict]:
        """Get a specific message by ID."""
        query = """
            query GetMessage($id: ID!) {
                getChatMessage(id: $id) {
                    id
                    content
                    metadata
                    createdAt
                    humanInteraction
                }
            }
        """

        result = self.graphql_service.query(query, {'id': message_id})
        return result.get('getChatMessage')

    def _create_pending_message(
        self,
        request_type: str,
        message: str,
        timeout_seconds: Optional[int],
        default_value: Any,
        options: Optional[List[dict]],
        metadata: dict
    ) -> dict:
        """Create a pending HITL message."""
        import asyncio
        import nest_asyncio

        # Allow nested event loops
        nest_asyncio.apply()

        human_interaction_map = {
            'approval': 'PENDING_APPROVAL',
            'input': 'PENDING_INPUT',
            'review': 'PENDING_REVIEW',
            'escalation': 'PENDING_ESCALATION'
        }

        message_metadata = {
            'timeout_seconds': timeout_seconds,
            'default_value': default_value,
            'request_metadata': metadata,
            'created_at': datetime.now(timezone.utc).isoformat()
        }

        # Add interactive UI elements based on request type
        if request_type == 'approval':
            message_metadata['buttons'] = [
                {'label': 'Approve', 'value': 'approve', 'variant': 'default'},
                {'label': 'Reject', 'value': 'reject', 'variant': 'destructive'}
            ]
        elif request_type == 'input':
            message_metadata['inputs'] = [{
                'name': 'input',
                'label': 'Your Response',
                'placeholder': 'Enter your response...',
                'type': 'text',
                'required': True
            }]
            message_metadata['buttons'] = [
                {'label': 'Submit', 'value': 'submit', 'variant': 'default'}
            ]
        elif request_type == 'review':
            # Add artifact if provided
            if 'artifact' in metadata:
                message_metadata['artifact'] = metadata['artifact']
            if 'artifact_type' in metadata:
                message_metadata['artifact_type'] = metadata['artifact_type']

            # Convert options to buttons
            if options:
                buttons = []
                for opt in options:
                    if isinstance(opt, dict) and 'label' in opt:
                        # Map button type to variant
                        variant = 'default'
                        if opt.get('type') == 'action':
                            variant = 'default'
                        elif opt.get('type') == 'cancel':
                            variant = 'destructive'

                        buttons.append({
                            'label': opt['label'],
                            'value': opt['label'].lower().replace(' ', '_'),
                            'variant': variant
                        })
                message_metadata['buttons'] = buttons
            else:
                # Default review buttons
                message_metadata['buttons'] = [
                    {'label': 'Approve', 'value': 'approve', 'variant': 'default'},
                    {'label': 'Request Changes', 'value': 'request_changes', 'variant': 'secondary'},
                    {'label': 'Reject', 'value': 'reject', 'variant': 'destructive'}
                ]

            # Add optional feedback textarea
            message_metadata['inputs'] = [{
                'name': 'feedback',
                'label': 'Feedback (Optional)',
                'placeholder': 'Add any comments or feedback...',
                'type': 'textarea',
                'required': False
            }]

        # Run the async record_message in a sync context
        loop = asyncio.get_event_loop()
        message_id = loop.run_until_complete(
            self.chat_recorder.record_message(
                role='ASSISTANT',
                content=message,
                message_type='MESSAGE',
                human_interaction=human_interaction_map[request_type],
                metadata=message_metadata
            )
        )

        # Return a dict with the message ID
        return {'id': message_id}

    def _parse_response(self, response: dict, request_type: str) -> Any:
        """Parse response message content based on request type."""
        try:
            content = json.loads(response['content'])
        except json.JSONDecodeError:
            content = response['content']

        if request_type == 'approval':
            return content.get('approved', False)
        elif request_type == 'input':
            return content.get('input', '')
        elif request_type == 'review':
            return {
                'decision': content.get('decision'),
                'feedback': content.get('feedback'),
                'edited_artifact': content.get('edited_artifact'),
                'responded_at': response['createdAt']
            }

        return content

    def _is_timed_out(self, pending_message: dict, timeout_seconds: Optional[int]) -> bool:
        """Check if pending message has timed out."""
        if timeout_seconds is None:
            return False

        created_at = datetime.fromisoformat(pending_message['createdAt'].replace('Z', '+00:00'))
        elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()
        return elapsed > timeout_seconds

    def _mark_timed_out(self, message_id: str) -> None:
        """Mark message as timed out."""
        mutation = """
            mutation MarkTimedOut($id: ID!) {
                updateChatMessage(input: {
                    id: $id
                    humanInteraction: "TIMED_OUT"
                }) {
                    id
                }
            }
        """
        self.graphql_service.mutate(mutation, {'id': message_id})

    def sleep(self, seconds: int) -> None:
        """
        Sleep by creating a checkpoint and exiting.

        Note: Not fully implemented - would need a scheduled resume mechanism.
        For now, just checkpoint the sleep and continue.
        """
        checkpoint_name = f"sleep_{datetime.now(timezone.utc).isoformat()}"
        self.step_run(checkpoint_name, lambda: None)

    def checkpoint_clear_all(self) -> None:
        """Clear all checkpoints."""
        self.checkpoints = {}
        self.metadata['state'] = {}
        self.metadata['lua_state'] = {}
        self._save_metadata()

    def checkpoint_clear_after(self, name: str) -> None:
        """Clear checkpoint and all subsequent ones."""
        if name not in self.checkpoints:
            return

        target_time = self.checkpoints[name]['completed_at']
        self.checkpoints = {
            k: v for k, v in self.checkpoints.items()
            if v['completed_at'] < target_time
        }
        self._save_metadata()

    def checkpoint_exists(self, name: str) -> bool:
        """Check if checkpoint exists."""
        return name in self.checkpoints

    def checkpoint_get(self, name: str) -> Optional[Any]:
        """Get cached checkpoint value."""
        entry = self.checkpoints.get(name)
        return entry['result'] if entry else None
