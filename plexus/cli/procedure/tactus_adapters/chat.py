"""
Plexus Chat Adapter for Tactus.

Thin wrapper around ProcedureChatRecorder that implements the Tactus
ChatRecorder protocol by converting Pydantic models to kwargs.
"""

import logging
from typing import Optional, Dict, Any

from tactus.protocols.models import ChatMessage

logger = logging.getLogger(__name__)


class PlexusChatAdapter:
    """
    Implements Tactus ChatRecorder protocol by wrapping ProcedureChatRecorder.

    This is a thin adapter that converts Pydantic ChatMessage models to
    the kwargs format expected by ProcedureChatRecorder.
    """

    def __init__(self, chat_recorder):
        """
        Initialize Plexus chat adapter.

        Args:
            chat_recorder: ProcedureChatRecorder instance
        """
        self.chat_recorder = chat_recorder
        self.session_id: Optional[str] = None
        logger.info("PlexusChatAdapter initialized")

    async def start_session(
        self,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new chat session.

        Note: This signature matches how TactusRuntime actually calls it (runtime.py:214),
        which only passes context. The Tactus ChatRecorder protocol definition incorrectly
        specifies procedure_id as the first parameter, but this is not how it's used.

        Args:
            context: Optional context data

        Returns:
            Session ID
        """
        self.session_id = await self.chat_recorder.start_session(context)
        logger.info(f"Started chat session: {self.session_id}")
        return self.session_id

    async def record_message(
        self,
        message: ChatMessage
    ) -> str:
        """
        Record a message in the chat session.

        Args:
            message: ChatMessage to record

        Returns:
            Message ID
        """
        if not self.session_id:
            logger.warning("No active session, starting one")
            self.session_id = await self.chat_recorder.start_session()

        # Convert Pydantic model to kwargs
        kwargs = {
            'role': message.role,
            'content': message.content,
            'message_type': message.message_type,
        }

        # Add optional fields if present
        if message.tool_name:
            kwargs['tool_name'] = message.tool_name
        if message.tool_parameters:
            kwargs['tool_parameters'] = message.tool_parameters
        if message.tool_response:
            kwargs['tool_response'] = message.tool_response
        if message.parent_message_id:
            kwargs['parent_message_id'] = message.parent_message_id
        if message.human_interaction:
            kwargs['human_interaction'] = message.human_interaction
        if message.metadata:
            kwargs['metadata'] = message.metadata

        # Call underlying chat recorder
        message_id = await self.chat_recorder.record_message(**kwargs)

        logger.debug(f"Recorded message: {message_id}")
        return message_id

    async def end_session(
        self,
        session_id: str,
        status: str = 'COMPLETED'
    ) -> None:
        """
        End the chat session.

        Args:
            session_id: Session ID to end
            status: Final status (COMPLETED, FAILED, CANCELLED)
        """
        await self.chat_recorder.end_session(status=status)
        logger.info(f"Ended chat session: {session_id} with status {status}")
        self.session_id = None

    async def get_session_history(
        self,
        session_id: str
    ) -> list[ChatMessage]:
        """
        Get the message history for a session.

        Args:
            session_id: Session ID

        Returns:
            List of ChatMessage objects
        """
        # This would query GraphQL to get messages
        # For now, not implemented as it's not in the core Tactus flow
        logger.warning("get_session_history not implemented in PlexusChatAdapter")
        return []
