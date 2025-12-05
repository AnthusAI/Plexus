"""
Human Primitive - Human-in-the-Loop (HITL) operations.

Provides:
- Human.approve(opts) - Request yes/no approval (blocking)
- Human.input(opts) - Request free-form input (blocking)
- Human.review(opts) - Request review with options (blocking)
- Human.notify(opts) - Send notification (non-blocking)
- Human.escalate(opts) - Escalate to human (blocking)
"""

import logging
import asyncio
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HumanPrimitive:
    """
    Manages human-in-the-loop operations for procedures.

    Enables procedures to:
    - Request approval from humans
    - Get input from humans
    - Send notifications
    - Escalate issues

    All blocking methods support timeouts and defaults.
    """

    def __init__(self, chat_recorder, hitl_config: Optional[Dict[str, Any]] = None):
        """
        Initialize Human primitive.

        Args:
            chat_recorder: ProcedureChatRecorder for recording messages
            hitl_config: Optional HITL declarations from YAML
        """
        self.chat_recorder = chat_recorder
        self.hitl_config = hitl_config or {}
        self._pending_requests: Dict[str, Dict[str, Any]] = {}
        self._message_queue: List[Dict[str, Any]] = []
        logger.debug("HumanPrimitive initialized")

    def approve(self, options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Request yes/no approval from human (BLOCKING).

        Args:
            options: Dict with:
                - message: str - Message to show human
                - context: Dict - Additional context
                - timeout: int - Timeout in seconds (None = no timeout)
                - default: bool - Default if timeout (default: False)
                - config_key: str - Reference to hitl: declaration

        Returns:
            bool - True if approved, False if rejected/timeout

        Example (Lua):
            local approved = Human.approve({
                message = "Deploy to production?",
                context = {environment = "prod"},
                timeout = 3600,
                default = false
            })

            if approved then
                deploy()
            end
        """
        # Convert Lua table to dict if needed
        if options and hasattr(options, 'items') and not isinstance(options, dict):
            options = dict(options.items())

        opts = options or {}

        # Check for config reference
        config_key = opts.get('config_key')
        if config_key and config_key in self.hitl_config:
            # Merge config with runtime options (runtime wins)
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get('message', 'Approval requested')
        context = opts.get('context', {})
        timeout = opts.get('timeout')
        default = opts.get('default', False)

        logger.info(f"Human approval requested: {message[:50]}...")

        # NOTE: This is a SYNCHRONOUS placeholder implementation
        # Full implementation requires:
        # 1. Create PENDING_APPROVAL message via chat_recorder
        # 2. Suspend Lua coroutine
        # 3. Wait for RESPONSE message (async)
        # 4. Resume coroutine with response value
        #
        # For now, we'll return the default to allow testing
        logger.warning("HITL blocking not yet implemented - returning default value")
        return default

    def input(self, options: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Request free-form input from human (BLOCKING).

        Args:
            options: Dict with:
                - message: str - Prompt for human
                - placeholder: str - Input placeholder
                - timeout: int - Timeout in seconds
                - default: str - Default if timeout
                - config_key: str - Reference to hitl: declaration

        Returns:
            str or None - Human's input, or None if timeout with no default

        Example (Lua):
            local topic = Human.input({
                message = "What topic?",
                placeholder = "Enter topic...",
                timeout = 600
            })

            if topic then
                State.set("topic", topic)
            end
        """
        # Convert Lua table to dict if needed
        if options and hasattr(options, 'items') and not isinstance(options, dict):
            options = dict(options.items())

        opts = options or {}

        # Check for config reference
        config_key = opts.get('config_key')
        if config_key and config_key in self.hitl_config:
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get('message', 'Input requested')
        placeholder = opts.get('placeholder', '')
        timeout = opts.get('timeout')
        default = opts.get('default')

        logger.info(f"Human input requested: {message[:50]}...")

        # Placeholder implementation
        logger.warning("HITL blocking not yet implemented - returning default value")
        return default

    def review(self, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Request human review (BLOCKING).

        Args:
            options: Dict with:
                - message: str - Review prompt
                - artifact: Any - Thing to review
                - artifact_type: str - Type of artifact
                - options: List[str] - Available actions
                - timeout: int - Timeout in seconds
                - config_key: str - Reference to hitl: declaration

        Returns:
            Dict with:
                - decision: str - Selected option
                - edited_artifact: Any - Modified artifact (if edited)
                - feedback: str - Human feedback

        Example (Lua):
            local review = Human.review({
                message = "Review this document",
                artifact = document,
                artifact_type = "document",
                options = {"approve", "edit", "reject"}
            })

            if review.decision == "approve" then
                publish(review.artifact)
            end
        """
        # Convert Lua table to dict if needed
        if options and hasattr(options, 'items') and not isinstance(options, dict):
            options = dict(options.items())

        opts = options or {}

        # Check for config reference
        config_key = opts.get('config_key')
        if config_key and config_key in self.hitl_config:
            config_opts = self.hitl_config[config_key].copy()
            config_opts.update(opts)
            opts = config_opts

        message = opts.get('message', 'Review requested')
        artifact = opts.get('artifact')
        options_list = opts.get('options', ['approve', 'reject'])

        logger.info(f"Human review requested: {message[:50]}...")

        # Placeholder implementation
        logger.warning("HITL blocking not yet implemented - returning default")
        return {'decision': 'approve', 'edited_artifact': artifact, 'feedback': ''}

    def notify(self, options: Optional[Dict[str, Any]] = None) -> None:
        """
        Send notification to human (NON-BLOCKING).

        Args:
            options: Dict with:
                - message: str - Notification message
                - level: str - info, warning, error (default: info)
                - context: Dict - Additional context

        Example (Lua):
            Human.notify({
                message = "Processing complete",
                level = "info",
                context = {items_processed = 100}
            })
        """
        # Convert Lua table to dict if needed
        if options and hasattr(options, 'items') and not isinstance(options, dict):
            options = dict(options.items())

        opts = options or {}
        message = opts.get('message', 'Notification')
        level = opts.get('level', 'info')
        context = opts.get('context', {})

        logger.info(f"Human notification: [{level}] {message}")

        # Queue message for async recording
        self._message_queue.append({
            'role': 'SYSTEM',
            'content': message,
            'message_type': 'MESSAGE',
            'human_interaction': 'NOTIFICATION'
        })

    def escalate(self, options: Optional[Dict[str, Any]] = None) -> None:
        """
        Escalate to human (BLOCKING).

        Stops workflow execution until human resolves the issue.

        Args:
            options: Dict with:
                - message: str - Escalation message
                - context: Dict - Error context

        Example (Lua):
            if attempts > 3 then
                Human.escalate({
                    message = "Cannot resolve automatically",
                    context = {attempts = attempts, error = last_error}
                })
            end
        """
        # Convert Lua table to dict if needed
        if options and hasattr(options, 'items') and not isinstance(options, dict):
            options = dict(options.items())

        opts = options or {}
        message = opts.get('message', 'Escalation required')
        context = opts.get('context', {})

        logger.warning(f"Human escalation: {message}")

        # Placeholder - this should block like approve/input/review
        logger.warning("HITL escalate not yet fully implemented")

    async def flush_recordings(self) -> None:
        """
        Flush all queued messages to chat recorder.

        This is called by the runtime after workflow execution to
        record all Human.notify() messages to the chat session.
        """
        if not self._message_queue:
            logger.debug("No Human primitive messages to flush")
            return

        if not self.chat_recorder:
            logger.error("No chat_recorder available - cannot flush Human primitive messages")
            return

        if not self.chat_recorder.session_id:
            logger.error(f"chat_recorder has no session_id - cannot flush Human primitive messages")
            return

        logger.info(f"Flushing {len(self._message_queue)} Human primitive messages (session: {self.chat_recorder.session_id})")

        for msg in self._message_queue:
            try:
                logger.info(f"Recording Human message: role={msg['role']}, human_interaction={msg['human_interaction']}, content={msg['content'][:50]}...")
                message_id = await self.chat_recorder.record_message(
                    role=msg['role'],
                    content=msg['content'],
                    message_type=msg['message_type'],
                    human_interaction=msg['human_interaction']
                )
                logger.info(f"Human message recorded with ID: {message_id}")
            except Exception as e:
                logger.error(f"Error recording Human primitive message: {e}", exc_info=True)

        self._message_queue.clear()
        logger.debug("Human primitive message queue cleared")

    def __repr__(self) -> str:
        return f"HumanPrimitive(config_keys={list(self.hitl_config.keys())})"
