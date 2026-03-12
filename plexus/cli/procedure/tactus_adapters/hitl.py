"""
Plexus HITL Adapter for Tactus.

Implements the Tactus HITLHandler protocol using Plexus's exit-and-resume pattern.
Creates HITL messages via GraphQL and raises ProcedureWaitingForHuman to pause execution.
"""

import logging
from typing import Optional

from tactus.protocols.models import HITLRequest, HITLResponse
from tactus.core.exceptions import ProcedureWaitingForHuman
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PlexusHITLAdapter:
    """
    Implements Tactus HITLHandler protocol using Plexus's exit-and-resume pattern.

    When a HITL interaction is requested:
    1. Creates a message in the chat session
    2. Updates procedure status to WAITING_FOR_HUMAN
    3. Raises ProcedureWaitingForHuman to exit runtime
    4. On resume, checks for response and returns it
    """

    def __init__(self, client, procedure_id: str, chat_recorder=None, storage_adapter=None):
        """
        Initialize Plexus HITL adapter.

        Args:
            client: PlexusDashboardClient instance
            procedure_id: ID of the procedure
            chat_recorder: Optional ProcedureChatRecorder for message creation
            storage_adapter: Optional PlexusStorageAdapter for status updates
        """
        self.client = client
        self.procedure_id = procedure_id
        self.chat_recorder = chat_recorder
        self.storage_adapter = storage_adapter
        logger.info(f"PlexusHITLAdapter initialized for procedure {procedure_id}")

    def request_interaction(
        self,
        procedure_id: str,
        request: HITLRequest
    ) -> HITLResponse:
        """
        Request human interaction using Plexus's exit-and-resume pattern.

        This creates a HITL message in the chat session, updates the procedure
        status, and raises ProcedureWaitingForHuman to pause execution.

        Args:
            procedure_id: Procedure ID
            request: HITLRequest with interaction details

        Returns:
            HITLResponse (only reached if response already exists on resume)

        Raises:
            ProcedureWaitingForHuman: To trigger exit-and-resume
        """
        if procedure_id != self.procedure_id:
            logger.warning(f"Requested procedure_id {procedure_id} doesn't match initialized {self.procedure_id}")
            procedure_id = self.procedure_id

        # Check if there's already a pending response (resume scenario)
        if self.storage_adapter:
            metadata = self.storage_adapter.load_procedure_metadata(procedure_id)
            waiting_on_message_id = metadata.waiting_on_message_id

            if waiting_on_message_id:
                # Check for response
                response = self.check_pending_response(procedure_id, waiting_on_message_id)
                if response:
                    logger.info(f"Found response for message {waiting_on_message_id}")
                    # Clear waiting status
                    self.storage_adapter.update_procedure_status(
                        procedure_id,
                        status='RUNNING',
                        waiting_on_message_id=None
                    )
                    return response

        # No existing response - create new HITL message
        logger.info(f"Creating HITL message for {request.request_type}: {request.message}")

        message_id = None
        if self.chat_recorder and self.chat_recorder.session_id:
            # Determine human interaction type
            interaction_type_map = {
                'approval': 'PENDING_APPROVAL',
                'input': 'PENDING_INPUT',
                'review': 'PENDING_REVIEW',
                'escalation': 'PENDING_ESCALATION'
            }
            interaction_type = interaction_type_map.get(request.request_type, 'PENDING_APPROVAL')

            # Build metadata
            metadata = request.metadata.copy() if request.metadata else {}
            if request.timeout_seconds:
                metadata['timeout_seconds'] = request.timeout_seconds
            if request.default_value is not None:
                metadata['default_value'] = request.default_value
            if request.options:
                metadata['options'] = request.options

            # Record message in chat session
            try:
                # Use chat recorder's record_message method
                import asyncio
                loop = asyncio.get_event_loop()
                message_id = loop.run_until_complete(
                    self.chat_recorder.record_message(
                        role='ASSISTANT',
                        content=request.message,
                        message_type='HITL_REQUEST',
                        human_interaction=interaction_type,
                        metadata=metadata
                    )
                )
                logger.info(f"Created HITL message: {message_id}")

            except Exception as e:
                logger.error(f"Error creating HITL message: {e}", exc_info=True)

        # Update procedure status to WAITING_FOR_HUMAN
        if self.storage_adapter and message_id:
            self.storage_adapter.update_procedure_status(
                procedure_id,
                status='WAITING_FOR_HUMAN',
                waiting_on_message_id=message_id
            )

        # Raise exception to trigger exit-and-resume
        raise ProcedureWaitingForHuman(
            f"Waiting for human {request.request_type}: {request.message}",
            pending_message_id=message_id
        )

    def check_pending_response(
        self,
        procedure_id: str,
        message_id: str
    ) -> Optional[HITLResponse]:
        """
        Check if there's a response to a pending HITL request.

        Args:
            procedure_id: Procedure ID
            message_id: Message ID to check

        Returns:
            HITLResponse if response exists, None otherwise
        """
        if not self.chat_recorder:
            return None

        # Query GraphQL for the message and check for response
        query = """
        query GetMessage($id: ID!) {
            message(id: $id) {
                id
                content
                humanInteraction
                responseContent
                responseMetadata
                respondedAt
            }
        }
        """

        try:
            response = self.client.execute(query, {'id': message_id})
            message_data = response.get('message')

            if not message_data:
                logger.warning(f"Message {message_id} not found")
                return None

            # Check if there's a response
            response_content = message_data.get('responseContent')
            if not response_content:
                logger.debug(f"No response yet for message {message_id}")
                return None

            # Parse response
            response_metadata = message_data.get('responseMetadata') or {}
            responded_at_str = message_data.get('respondedAt')
            responded_at = datetime.fromisoformat(responded_at_str) if responded_at_str else datetime.now(timezone.utc)

            # Determine value based on interaction type
            interaction_type = message_data.get('humanInteraction')

            if interaction_type == 'PENDING_APPROVAL':
                # Parse approval response (true/false)
                value = response_content.lower() in ['true', 'yes', 'approved', 'approve']
            elif interaction_type == 'PENDING_INPUT':
                # Return input as-is
                value = response_content
            elif interaction_type == 'PENDING_REVIEW':
                # Parse review response
                value = {
                    'decision': response_metadata.get('decision', 'approved'),
                    'edited_artifact': response_metadata.get('edited_artifact'),
                    'feedback': response_content
                }
            elif interaction_type == 'PENDING_ESCALATION':
                # Escalation resolved - return None (escalate just needs to resume)
                value = None
            else:
                # Default: return content
                value = response_content

            return HITLResponse(
                value=value,
                responded_at=responded_at,
                timed_out=False
            )

        except Exception as e:
            logger.error(f"Error checking pending response: {e}", exc_info=True)
            return None

    def cancel_pending_request(
        self,
        procedure_id: str,
        message_id: str
    ) -> None:
        """
        Cancel a pending HITL request.

        Args:
            procedure_id: Procedure ID
            message_id: Message ID to cancel
        """
        # Update message to cancelled status via GraphQL
        mutation = """
        mutation CancelMessage($id: ID!) {
            updateMessage(input: {
                id: $id
                humanInteraction: "CANCELLED"
            }) {
                message {
                    id
                    humanInteraction
                }
            }
        }
        """

        try:
            self.client.execute(mutation, {'id': message_id})
            logger.info(f"Cancelled HITL message: {message_id}")

            # Update procedure status if needed
            if self.storage_adapter:
                metadata = self.storage_adapter.load_procedure_metadata(procedure_id)
                if metadata.waiting_on_message_id == message_id:
                    self.storage_adapter.update_procedure_status(
                        procedure_id,
                        status='RUNNING',
                        waiting_on_message_id=None
                    )

        except Exception as e:
            logger.error(f"Error cancelling message: {e}", exc_info=True)
