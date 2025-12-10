"""
Session Primitive - Conversation history management.

Provides:
- Session.append(role, content) - Add message to conversation
- Session.inject_system(text) - Inject system message
- Session.clear() - Clear conversation history
- Session.history() - Get all messages as Lua table
- Session.save() - Persist current session to database
"""

import logging
import time
from typing import Any, Dict, Optional, List
import asyncio

logger = logging.getLogger(__name__)


class SessionPrimitive:
    """
    Manages agent conversation history for procedures.

    Enables workflows to:
    - Manipulate conversation context
    - Inject system messages
    - Clear history for fresh contexts
    - Retrieve conversation for inspection
    """

    def __init__(self, chat_recorder, execution_context, lua_sandbox=None):
        """
        Initialize Session primitive.

        Args:
            chat_recorder: ProcedureChatRecorder for database operations
            execution_context: ExecutionContext for agent state access
            lua_sandbox: LuaSandbox for creating Lua tables (optional)
        """
        self.chat_recorder = chat_recorder
        self.execution_context = execution_context
        self.lua_sandbox = lua_sandbox
        self._messages: List[Dict[str, Any]] = []
        logger.debug("SessionPrimitive initialized")

    def append(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add message to conversation history (in-memory only until save()).

        Args:
            role: Message role (USER, ASSISTANT, SYSTEM)
            content: Message content
            metadata: Optional metadata dict

        Example (Lua):
            Session.append("USER", "What is the weather?")
            Session.append("ASSISTANT", "I need more information about location.")
        """
        # Normalize role to uppercase
        role = role.upper()

        # Validate role
        valid_roles = ['USER', 'ASSISTANT', 'SYSTEM']
        if role not in valid_roles:
            logger.warning(f"Invalid role '{role}', using 'USER'. Valid roles: {valid_roles}")
            role = 'USER'

        message = {
            'role': role,
            'content': content,
            'message_type': 'MESSAGE',
            'metadata': metadata or {}
        }

        self._messages.append(message)
        logger.info(f"Appended {role} message to session (in-memory): {content[:50]}...")

    def inject_system(self, text: str) -> None:
        """
        Inject system message into conversation.

        This is a convenience method for Session.append("SYSTEM", text)

        Args:
            text: System message content

        Example (Lua):
            Session.inject_system("Focus on security implications")
        """
        self.append("SYSTEM", text)
        logger.info(f"Injected system message: {text[:50]}...")

    def clear(self) -> None:
        """
        Clear conversation history (in-memory only until save()).

        Example (Lua):
            Session.clear()
            Session.inject_system("Fresh context")
        """
        count = len(self._messages)
        self._messages.clear()
        logger.info(f"Cleared {count} messages from session")

    def history(self):
        """
        Get all messages in conversation history.

        Returns:
            Lua table with messages (1-indexed for Lua)

        Example (Lua):
            local messages = Session.history()
            for i, msg in ipairs(messages) do
                Log.info("Message", {
                    role = msg.role,
                    content = msg.content
                })
            end
        """
        logger.debug(f"Retrieved {len(self._messages)} messages from session history")

        # If lua_sandbox available, create proper Lua table
        # (Required because unpack_returned_tuples=True causes tuples to be unpacked)
        if self.lua_sandbox:
            lua_table = self.lua_sandbox.lua.table()
            for i, msg in enumerate(self._messages, start=1):
                lua_table[i] = msg.copy()  # Lua uses 1-based indexing
            return lua_table
        else:
            # Fallback: return list (won't work with # operator, but better than nothing)
            return [msg.copy() for msg in self._messages]

    def count(self) -> int:
        """
        Get count of messages in session.

        Returns:
            Number of messages

        Example (Lua):
            local msg_count = Session.count()
            Log.info("Messages in session", {count = msg_count})
        """
        return len(self._messages)

    async def save(self) -> None:
        """
        Persist current in-memory messages to database.

        This records all queued messages via the chat recorder.
        Called automatically by runtime after workflow execution.

        Example (Lua):
            -- Not typically called from Lua - runtime handles this
        """
        if not self._messages:
            logger.debug("No session messages to save")
            return

        if not self.chat_recorder:
            logger.error("No chat_recorder available - cannot save session")
            return

        if not self.chat_recorder.session_id:
            logger.error("chat_recorder has no session_id - cannot save session")
            return

        logger.info(f"Saving {len(self._messages)} session messages (session: {self.chat_recorder.session_id})")

        for msg in self._messages:
            try:
                message_id = await self.chat_recorder.record_message(
                    role=msg['role'],
                    content=msg['content'],
                    message_type=msg['message_type'],
                    metadata=msg.get('metadata')
                )
                logger.info(f"Saved session message with ID: {message_id}")
            except Exception as e:
                logger.error(f"Error saving session message: {e}", exc_info=True)

        # Clear in-memory messages after save
        self._messages.clear()
        logger.debug("Session message queue cleared after save")

    def load_from_node(self, node: Any) -> int:
        """
        Load conversation history from a graph node's metadata.

        Args:
            node: Node dict with 'id' field (and optionally 'metadata')

        Returns:
            Number of messages loaded

        Example (Lua):
            local checkpoint = GraphNode.root()
            if checkpoint then
                local count = Session.load_from_node(checkpoint)
                Log.info("Resumed session", {messages = count})
            end
        """
        # Convert Lua table to Python dict
        from lupa import lua_type
        if lua_type(node) == 'table':
            node_dict = {}
            for k, v in node.items():
                node_dict[k] = v
        elif isinstance(node, dict):
            node_dict = node
        else:
            logger.warning("load_from_node: Invalid node type")
            return 0

        node_id = node_dict.get('id')
        if not node_id:
            logger.warning("load_from_node: Node has no 'id' field")
            return 0

        # Try to get metadata from passed dict first
        metadata = node_dict.get('metadata', {})

        # If no messages in metadata, try fetching from database
        if not metadata or 'messages' not in metadata:
            try:
                from plexus.dashboard.api.models.graph_node import GraphNode

                # Get client from chat_recorder (has client reference)
                if not self.chat_recorder or not hasattr(self.chat_recorder, 'client'):
                    logger.warning("No client available to fetch node")
                    return 0

                full_node = GraphNode.get_by_id(node_id, self.chat_recorder.client)
                metadata = full_node.metadata or {}
                logger.debug(f"Fetched node {node_id} from database")
            except Exception as e:
                logger.warning(f"Failed to fetch node {node_id}: {e}")
                return 0

        messages = metadata.get('messages', [])

        if not messages:
            logger.info(f"No messages found in node {node_id}")
            return 0

        # Clear current session
        self._messages.clear()

        # Restore messages
        loaded_count = 0
        for msg in messages:
            if not isinstance(msg, dict) or 'role' not in msg:
                logger.warning(f"Skipping invalid message: {msg}")
                continue

            self._messages.append({
                'role': msg.get('role', 'USER'),
                'content': msg.get('content', ''),
                'message_type': msg.get('message_type', 'MESSAGE'),
                'metadata': msg.get('metadata', {})
            })
            loaded_count += 1

        logger.info(f"Loaded {loaded_count} messages from node {node_id}")
        return loaded_count

    def save_to_node(self, node: Any) -> bool:
        """
        Save conversation history to a graph node's metadata.

        Args:
            node: Node dict with 'id' field

        Returns:
            True if saved successfully, False otherwise

        Example (Lua):
            Session.append("ASSISTANT", "Phase 1 complete")

            local checkpoint = GraphNode.create("checkpoint")
            Session.save_to_node(checkpoint)
            Log.info("Session saved", {node = checkpoint.id})
        """
        # Convert Lua table to Python dict
        from lupa import lua_type
        if lua_type(node) == 'table':
            node_dict = {}
            for k, v in node.items():
                node_dict[k] = v
        elif isinstance(node, dict):
            node_dict = node
        else:
            logger.error("save_to_node: Invalid node type")
            return False

        node_id = node_dict.get('id')
        if not node_id:
            logger.error("save_to_node: Node has no 'id' field")
            return False

        if not self._messages:
            logger.debug("save_to_node: No messages to save")
            return True  # Not an error

        try:
            from plexus.dashboard.api.models.graph_node import GraphNode

            # Get client from chat_recorder
            if not self.chat_recorder or not hasattr(self.chat_recorder, 'client'):
                logger.error("No client available to save to node")
                return False

            # Fetch full node
            graph_node = GraphNode.get_by_id(node_id, self.chat_recorder.client)

            # Get existing metadata (preserve other fields)
            metadata = graph_node.metadata or {}

            # Serialize messages
            messages_data = []
            for msg in self._messages:
                messages_data.append({
                    'role': msg['role'],
                    'content': msg['content'],
                    'message_type': msg.get('message_type', 'MESSAGE'),
                    'metadata': msg.get('metadata', {})
                })

            # Update metadata
            metadata['messages'] = messages_data
            metadata['message_count'] = len(messages_data)
            metadata['last_saved'] = time.time()

            # Persist to database
            graph_node.update_content(
                status=graph_node.status,
                metadata=metadata
            )

            logger.info(f"Saved {len(messages_data)} messages to node {node_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save to node {node_id}: {e}", exc_info=True)
            return False

    def __repr__(self) -> str:
        return f"SessionPrimitive(messages={len(self._messages)})"
