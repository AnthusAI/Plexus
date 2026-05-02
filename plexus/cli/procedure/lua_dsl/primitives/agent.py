"""
Agent Primitive - LLM agent operations.

Provides:
- Agent.turn() - Execute one agent turn (reasoning + tool calls)
- Agent.turn({inject = "message"}) - Inject additional context
"""

import json
import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


def _coerce_lua_mapping(value: Any) -> Any:
    """Convert a Lua table proxy into a plain Python mapping when possible."""
    try:
        from lupa import lua_type
    except Exception:  # pragma: no cover - lupa import failure is environment-specific
        lua_type = None

    if lua_type is not None:
        try:
            if lua_type(value) == 'table':
                return {k: v for k, v in value.items()}
        except Exception as exc:  # Defensive: keep original value when Lua proxy coercion fails
            logger.debug("Failed to coerce Lua table proxy to dict: %s", exc)

    return value


class AgentHistoryAccessor:
    """Lua-facing conversation history helper for AgentPrimitive."""

    def __init__(self, agent: "AgentPrimitive"):
        self._agent = agent

    def add(self, message: Any) -> None:
        normalized = self._agent._normalize_history_message(message)
        self._agent._conversation.append(normalized)
        self._agent._initialized = True
        logger.debug(
            "Agent '%s' history add: %s",
            self._agent.name,
            type(normalized).__name__,
        )

    def get(self) -> List[Any]:
        return LuaHistoryView(self._agent.get_conversation())

    def count_tokens(self) -> int:
        from plexus.cli.procedure.conversation_utils import ConversationUtils

        try:
            return ConversationUtils._count_tokens_in_conversation(self._agent._conversation)
        except Exception as exc:  # pragma: no cover - defensive only
            logger.warning(
                "Token counting failed for agent '%s' history: %s",
                self._agent.name,
                exc,
            )
            return 0


class AgentResponse:
    """Represents the response from an agent turn."""

    def __init__(
        self,
        content: str,
        tool_calls: List[Dict[str, Any]],
        token_usage: Optional[Dict[str, int]] = None
    ):
        self.content = content
        self.tool_calls = tool_calls
        self.token_usage = token_usage or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Lua access."""
        return {
            'content': self.content,
            'tool_calls': self.tool_calls,
            'token_usage': self.token_usage
        }

    def __repr__(self) -> str:
        return f"AgentResponse(content_len={len(self.content)}, tools={len(self.tool_calls)})"


class LuaHistoryView:
    """1-indexed, nil-on-miss view for Lua iteration over Python message history."""

    def __init__(self, messages: List[Any]):
        self._messages = list(messages)

    def __getitem__(self, index: Any) -> Any:
        if not isinstance(index, int):
            return None
        if index < 1 or index > len(self._messages):
            return None
        return self._messages[index - 1]


class AgentPrimitive:
    """
    Executes LLM agent turns with tool calling.

    Each agent has:
    - System prompt (instructions)
    - Initial message (kickoff)
    - Conversation history
    - Available tools
    - LLM instance
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        initial_message: str,
        llm,
        available_tools: List[Any],
        tool_primitive,
        stop_primitive,
        iterations_primitive,
        chat_recorder=None,
        state_primitive=None
    ):
        """
        Initialize an agent primitive.

        Args:
            name: Agent name (e.g., "worker", "assistant")
            system_prompt: System prompt for the agent
            initial_message: Initial user message to kickoff
            llm: LangChain LLM instance with tools bound
            available_tools: List of available tool objects
            tool_primitive: ToolPrimitive instance for recording calls
            stop_primitive: StopPrimitive instance for stop detection
            iterations_primitive: IterationsPrimitive for tracking turns
            chat_recorder: Optional ProcedureChatRecorder for logging conversations
            state_primitive: Optional StatePrimitive for shared procedure state
        """
        self.name = name
        self.system_prompt = system_prompt
        self.initial_message = initial_message
        self.llm = llm
        self.available_tools = available_tools
        self.tool_primitive = tool_primitive
        self.stop_primitive = stop_primitive
        self.iterations_primitive = iterations_primitive
        self.chat_recorder = chat_recorder
        self.state_primitive = state_primitive

        # Conversation history
        self._conversation: List[Any] = []
        self._initialized = False

        # Last turn's text content (accessible from Lua as agent.output)
        self.output = None

        # Lua-facing history helper expected by optimizer procedures.
        self.history = AgentHistoryAccessor(self)

        # Recording queue (for async chat recording)
        self._recording_queue: List[Dict[str, Any]] = []

        logger.info(f"AgentPrimitive '{name}' initialized with {len(available_tools)} tools")

    def _normalize_tool_args_value(
        self,
        tool_name: str,
        raw_args: Any,
        *,
        source: str = "args",
        allow_callable: bool = True,
    ) -> tuple[Dict[str, Any], Optional[str]]:
        """Normalize tool-call args into a plain dict for execution and recording."""
        if raw_args is None:
            return {}, None

        if isinstance(raw_args, dict):
            return raw_args, None

        if isinstance(raw_args, str):
            if not raw_args.strip():
                return {}, None
            try:
                parsed = json.loads(raw_args)
            except Exception as exc:
                return {}, (
                    f"{source} for tool '{tool_name}' must be a JSON object string; "
                    f"decode failed with {type(exc).__name__}: {exc}"
                )
            if isinstance(parsed, dict):
                return parsed, None
            return {}, (
                f"{source} for tool '{tool_name}' must decode to a dict, "
                f"got {type(parsed).__name__}"
            )

        if callable(raw_args) and allow_callable:
            try:
                called_args = raw_args()
            except Exception as exc:
                return {}, (
                    f"{source} callable for tool '{tool_name}' raised "
                    f"{type(exc).__name__}: {exc}"
                )
            return self._normalize_tool_args_value(
                tool_name,
                called_args,
                source=f"{source}()",
                allow_callable=False,
            )

        return {}, (
            f"{source} for tool '{tool_name}' must normalize to a dict; "
            f"got {type(raw_args).__name__}"
        )

    def _extract_tool_call_info(
        self,
        tool_call: Any,
    ) -> tuple[str, Dict[str, Any], Optional[str], Optional[str]]:
        """Extract a tool name, normalized args dict, tool call id, and optional args error."""
        if isinstance(tool_call, dict):
            tool_name = tool_call.get('name', 'UNKNOWN')
            tool_call_id = tool_call.get('id')
            tool_args, args_error = self._normalize_tool_args_value(
                tool_name,
                tool_call.get('args'),
                source="args",
            )
            return tool_name, tool_args, tool_call_id, args_error

        tool_name = getattr(tool_call, 'name', 'UNKNOWN')
        tool_call_id = getattr(tool_call, 'id', None)

        args_as_dict = getattr(tool_call, 'args_as_dict', None) if hasattr(type(tool_call), 'args_as_dict') else None
        if callable(args_as_dict):
            try:
                raw_args = args_as_dict()
            except Exception as exc:
                return tool_name, {}, tool_call_id, (
                    f"args_as_dict() for tool '{tool_name}' raised "
                    f"{type(exc).__name__}: {exc}"
                )
            tool_args, args_error = self._normalize_tool_args_value(
                tool_name,
                raw_args,
                source="args_as_dict()",
            )
            return tool_name, tool_args, tool_call_id, args_error

        tool_args, args_error = self._normalize_tool_args_value(
            tool_name,
            getattr(tool_call, 'args', None),
            source="args",
        )
        return tool_name, tool_args, tool_call_id, args_error

    def turn(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute one agent turn.

        Args:
            options: Optional dict with:
                - inject: Additional context message to inject for this turn

        Returns:
            Dictionary with response information (for Lua access)

        Example (Lua):
            local response = Worker.turn()
            Log.info("Agent said: " .. response.content)

            for i, call in ipairs(response.tool_calls) do
                Log.info("Called tool: " .. call.name)
            end
        """
        try:
            # Initialize conversation on first turn
            if not self._initialized:
                self._initialize_conversation()

            # Inject additional context if provided
            if options and 'inject' in options:
                self._inject_message(options['inject'])

            self._inject_pending_steering()

            # Increment iteration counter
            self.iterations_primitive.increment()

            # Call LLM
            logger.debug(f"Calling LLM for agent '{self.name}' (turn {self.iterations_primitive.current()})")
            from plexus.cli.procedure.logging_utils import capture_llm_context_for_agent

            capture_llm_context_for_agent(
                agent_name=f"Tactus AgentPrimitive: {self.name}",
                chat_history=self._conversation,
                context=f"turn {self.iterations_primitive.current()}",
                call_site="tactus_agent_turn",
                tools=self.available_tools,
            )
            ai_response = self.llm.invoke(self._conversation)

            # Log response
            logger.debug(f"Agent '{self.name}' response: {ai_response}")

            # Process response
            response_content = getattr(ai_response, 'content', '') or ''
            self.output = response_content  # Store for Lua access
            tool_calls = getattr(ai_response, 'tool_calls', [])

            # Add AI response to conversation
            self._conversation.append(ai_response)

            # Queue AI response for recording (agent messages are INTERNAL)
            self._queue_recording({
                'role': 'ASSISTANT',
                'content': response_content,
                'message_type': 'MESSAGE',
                'human_interaction': 'INTERNAL'
            })

            # Execute tool calls if present
            executed_tools = []
            if tool_calls:
                logger.info(f"Agent '{self.name}' called {len(tool_calls)} tools")
                executed_tools = self._execute_tool_calls(tool_calls)

            # Extract token usage if available
            token_usage = self._extract_token_usage(ai_response)

            # Build response dict for Lua
            response_dict = {
                'content': response_content,
                'tool_calls': executed_tools,
                'token_usage': token_usage
            }

            logger.debug(f"Agent '{self.name}' turn complete")
            return response_dict

        except Exception as e:
            logger.error(f"Error in agent '{self.name}' turn: {e}", exc_info=True)
            # Return error response
            return {
                'content': '',
                'tool_calls': [],
                'token_usage': {},
                'error': str(e)
            }

    def _initialize_conversation(self):
        """Initialize conversation with system prompt and initial message."""
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
        except ImportError:
            from langchain.schema import SystemMessage, HumanMessage

        self._conversation = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=self.initial_message)
        ]

        # Queue initial messages for recording (all agent messages are INTERNAL)
        self._queue_recording({
            'role': 'SYSTEM',
            'content': self.system_prompt,
            'message_type': 'MESSAGE',
            'human_interaction': 'INTERNAL'
        })
        self._queue_recording({
            'role': 'USER',
            'content': self.initial_message,
            'message_type': 'MESSAGE',
            'human_interaction': 'INTERNAL'
        })

        self._initialized = True
        logger.debug(f"Agent '{self.name}' conversation initialized")

    def _normalize_history_message(self, message: Any) -> Any:
        """Normalize Lua/Python history entries into LangChain-compatible messages."""
        message = _coerce_lua_mapping(message)
        if not isinstance(message, dict):
            return message

        role = str(message.get('role', 'user') or 'user').lower()
        content = message.get('content', '')
        if content is None:
            content = ''
        content = str(content)

        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
        except ImportError:  # pragma: no cover - compatibility only
            from langchain.schema import SystemMessage, HumanMessage, AIMessage, ToolMessage

        if role == 'system':
            return SystemMessage(content=content)
        if role in ('assistant', 'ai'):
            return AIMessage(content=content)
        if role == 'tool':
            tool_call_id = message.get('tool_call_id') or "manual-tool-call"
            return ToolMessage(content=content, tool_call_id=str(tool_call_id))
        return HumanMessage(content=content)

    def _queue_recording(self, message_data: Dict[str, Any]):
        """Queue a message for async recording later."""
        if self.chat_recorder:
            self._recording_queue.append(message_data)

    def reset(self) -> None:
        """
        Reset the agent's conversation state.

        Clears the in-memory conversation history and forces re-initialization
        on the next turn, without altering the recording queue.
        """
        self._conversation = []
        self._initialized = False
        logger.debug(f"Agent '{self.name}' reset conversation state")

    def clear_history(self) -> None:
        """Lua-facing alias for reset()."""
        self.reset()

    def __call__(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Lua-facing call syntax: agent({message=...}) or agent()."""
        opts = _coerce_lua_mapping(options)
        if isinstance(opts, dict) and 'message' in opts and 'inject' not in opts:
            opts = dict(opts)
            opts['inject'] = opts.pop('message')
        return self.turn(opts if isinstance(opts, dict) else None)

    async def flush_recordings(self):
        """Flush queued recordings to chat session (called by runtime after workflow)."""
        if not self.chat_recorder or not self.chat_recorder.session_id:
            return

        logger.info(f"Flushing {len(self._recording_queue)} queued messages for agent '{self.name}'")

        for msg_data in self._recording_queue:
            try:
                await self.chat_recorder.record_message(**msg_data)
            except Exception as e:
                logger.error(f"Error recording message: {e}")

        self._recording_queue.clear()

    def _inject_message(self, message: str):
        """Inject an additional message into the conversation."""
        try:
            from langchain_core.messages import HumanMessage
        except ImportError:
            from langchain.schema import HumanMessage

        self._conversation.append(HumanMessage(content=message))
        logger.debug(f"Injected message into agent '{self.name}' conversation")

    def _inject_pending_steering(self) -> None:
        """Inject new procedure steering notes once for this agent before the next LLM call."""
        if not self.chat_recorder or not self.state_primitive:
            return
        get_messages = getattr(self.chat_recorder, 'get_steering_messages', None)
        if not callable(get_messages):
            return

        watermark_key = f"procedure_steering_watermark:{self.name}"
        try:
            after = self.state_primitive.get(watermark_key) or ""
            result = get_messages(
                after=after,
                agent_name=self.name,
                limit=20,
            )
            messages = result.get('messages', []) if isinstance(result, dict) else []
            watermark = result.get('watermark') if isinstance(result, dict) else None
            if not messages:
                if watermark and watermark != after:
                    self.state_primitive.set(watermark_key, watermark)
                return

            try:
                from langchain_core.messages import SystemMessage
            except ImportError:  # pragma: no cover - compatibility only
                from langchain.schema import SystemMessage

            lines = ["=== USER STEERING RECEIVED MID-RUN ==="]
            for index, message in enumerate(messages, start=1):
                created_at = message.get('created_at') or 'unknown time'
                content = str(message.get('content') or '').strip()
                lines.append(f"{index}. [{created_at}] {content}")
            lines.append(
                "Treat this as advisory operator guidance for this and future procedure work."
            )
            lines.append("=== END USER STEERING ===")
            self._conversation.append(SystemMessage(content="\n".join(lines)))
            self.state_primitive.set(watermark_key, watermark or messages[-1].get('created_at') or after)
            logger.info(
                "Injected %d steering message(s) into agent '%s'",
                len(messages),
                self.name,
            )
        except Exception as exc:
            logger.warning(
                "Failed to inject procedure steering into agent '%s': %s",
                self.name,
                exc,
            )

    def _execute_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """
        Execute tool calls and add results to conversation.

        Args:
            tool_calls: List of tool call objects from LLM

        Returns:
            List of executed tool dicts for Lua access
        """
        try:
            from langchain_core.messages import ToolMessage
        except ImportError:
            from langchain.schema import ToolMessage

        executed = []

        for tool_call in tool_calls:
            tool_name, tool_args, tool_call_id, args_error = self._extract_tool_call_info(tool_call)

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            if args_error:
                logger.error(f"Malformed tool call args for '{tool_name}': {args_error}")
                tool_result = f"Tool argument error: {args_error}"
            else:
                # Execute tool
                tool_result = self._execute_single_tool(tool_name, tool_args)

            # Record tool call in ToolPrimitive
            self.tool_primitive.record_call(tool_name, tool_args, tool_result)

            # Queue tool call for recording (tool calls are INTERNAL)
            self._queue_recording({
                'role': 'TOOL',
                'content': str(tool_result),
                'message_type': 'TOOL_RESPONSE',
                'tool_name': tool_name,
                'tool_parameters': tool_args,
                'tool_response': {'result': tool_result},
                'human_interaction': 'INTERNAL'
            })

            # Check if this is a stop request
            if not args_error and (tool_name == "done" or tool_name == "stop"):
                reason = tool_args.get('reason', 'Agent requested stop')
                success = tool_args.get('success', True)
                self.stop_primitive.request(reason, success)

            # Add tool result to conversation. Some model providers omit tool_call_id,
            # so we still inject a deterministic result message into history.
            if tool_call_id:
                tool_message = ToolMessage(content=str(tool_result), tool_call_id=str(tool_call_id))
                self._conversation.append(tool_message)
            else:
                try:
                    from langchain_core.messages import HumanMessage
                except ImportError:  # pragma: no cover - compatibility only
                    from langchain.schema import HumanMessage
                self._conversation.append(
                    HumanMessage(content=f"Tool '{tool_name}' result: {tool_result}")
                )

            # Build executed tool dict for Lua
            executed.append({
                'name': tool_name,
                'args': tool_args,
                'result': tool_result
            })

        return executed

    def _execute_single_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """
        Execute a single tool by name.

        Args:
            tool_name: Name of the tool
            tool_args: Arguments to pass

        Returns:
            Tool execution result
        """
        # Find tool in available tools
        for tool in self.available_tools:
            if tool.name == tool_name:
                try:
                    # Execute tool
                    result = tool.func(tool_args)
                    logger.debug(f"Tool '{tool_name}' executed successfully")
                    return result

                except Exception as e:
                    logger.error(f"Tool '{tool_name}' execution failed: {e}")
                    return f"Tool execution error: {e}"

        # Tool not found
        logger.warning(f"Tool '{tool_name}' not found in available tools")
        return f"Tool '{tool_name}' not found"

    def _extract_token_usage(self, ai_response: Any) -> Dict[str, int]:
        """
        Extract token usage from LLM response.

        Args:
            ai_response: LangChain AI message object

        Returns:
            Dict with token usage info
        """
        usage = {}

        # Try usage_metadata (newer LangChain)
        if hasattr(ai_response, 'usage_metadata') and ai_response.usage_metadata:
            usage_metadata = ai_response.usage_metadata
            if hasattr(usage_metadata, 'input_tokens'):
                usage['input'] = usage_metadata.input_tokens
            if hasattr(usage_metadata, 'output_tokens'):
                usage['output'] = usage_metadata.output_tokens
            if hasattr(usage_metadata, 'total_tokens'):
                usage['total'] = usage_metadata.total_tokens

        # Try response_metadata (older LangChain)
        elif hasattr(ai_response, 'response_metadata') and ai_response.response_metadata:
            resp_metadata = ai_response.response_metadata
            if 'token_usage' in resp_metadata:
                token_usage = resp_metadata['token_usage']
                usage['input'] = token_usage.get('prompt_tokens', 0)
                usage['output'] = token_usage.get('completion_tokens', 0)
                usage['total'] = token_usage.get('total_tokens', 0)

        return usage

    def get_conversation(self) -> List[Any]:
        """Get the current conversation history."""
        return self._conversation.copy()

    def __repr__(self) -> str:
        return f"AgentPrimitive(name='{self.name}', turns={len(self._conversation)})"
