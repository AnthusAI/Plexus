"""
System Primitive - System monitoring and alerting.

Provides:
- System.alert(opts) - Send system alert (non-blocking)
"""

import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


class SystemPrimitive:
    """
    Manages system-level operations and monitoring.

    Enables procedures and external systems to send alerts
    through the unified message infrastructure.
    """

    def __init__(self, chat_recorder):
        """
        Initialize System primitive.

        Args:
            chat_recorder: ProcedureChatRecorder for recording alerts
        """
        self.chat_recorder = chat_recorder
        self._message_queue: List[Dict[str, Any]] = []
        logger.debug("SystemPrimitive initialized")

    def alert(self, options: Optional[Dict[str, Any]] = None) -> None:
        """
        Send system alert (NON-BLOCKING).

        Args:
            options: Dict with:
                - message: str - Alert message
                - level: str - info, warning, error, critical (default: info)
                - source: str - Alert source identifier
                - context: Dict - Additional context

        Example (Lua):
            System.alert({
                message = "Memory threshold exceeded",
                level = "warning",
                source = "resource_monitor",
                context = {memory_mb = 3500, threshold_mb = 3000}
            })
        """
        # Convert Lua table to dict if needed
        if options and hasattr(options, 'items') and not isinstance(options, dict):
            options = dict(options.items())

        opts = options or {}
        message = opts.get('message', 'System alert')
        level = opts.get('level', 'info')
        source = opts.get('source', 'system')
        context = opts.get('context', {})

        # Map level to humanInteraction enum
        level_to_interaction = {
            'info': 'ALERT_INFO',
            'warning': 'ALERT_WARNING',
            'error': 'ALERT_ERROR',
            'critical': 'ALERT_CRITICAL'
        }

        human_interaction = level_to_interaction.get(level, 'ALERT_INFO')

        logger.info(f"System alert [{level}]: {message}")

        # Queue message for async recording
        self._message_queue.append({
            'role': 'SYSTEM',
            'content': message,
            'message_type': 'MESSAGE',
            'human_interaction': human_interaction
        })

    async def flush_recordings(self) -> None:
        """
        Flush all queued messages to chat recorder.

        This is called by the runtime after workflow execution to
        record all System.alert() messages to the chat session.
        """
        if not self._message_queue:
            logger.debug("No System primitive messages to flush")
            return

        logger.info(f"Flushing {len(self._message_queue)} System primitive messages")

        for msg in self._message_queue:
            try:
                await self.chat_recorder.record_message(
                    role=msg['role'],
                    content=msg['content'],
                    message_type=msg['message_type'],
                    human_interaction=msg['human_interaction']
                )
            except Exception as e:
                logger.error(f"Error recording System primitive message: {e}")

        self._message_queue.clear()
        logger.debug("System primitive message queue cleared")

    def __repr__(self) -> str:
        return "SystemPrimitive()"
