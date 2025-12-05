"""
Agent Primitive - LLM agent operations.

Provides:
- Agent.turn() - Execute one agent turn (reasoning + tool calls)
- Agent.turn({inject = "message"}) - Inject additional context
"""

import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


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
        chat_recorder=None
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

        # Conversation history
        self._conversation: List[Any] = []
        self._initialized = False

        # Recording queue (for async chat recording)
        self._recording_queue: List[Dict[str, Any]] = []

        logger.info(f"AgentPrimitive '{name}' initialized with {len(available_tools)} tools")

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

            # Increment iteration counter
            self.iterations_primitive.increment()

            # Call LLM
            logger.debug(f"Calling LLM for agent '{self.name}' (turn {self.iterations_primitive.current()})")
            ai_response = self.llm.invoke(self._conversation)

            # Log response
            logger.debug(f"Agent '{self.name}' response: {ai_response}")

            # Process response
            response_content = getattr(ai_response, 'content', '') or ''
            tool_calls = getattr(ai_response, 'tool_calls', [])

            # Add AI response to conversation
            self._conversation.append(ai_response)

            # Queue AI response for recording
            self._queue_recording({
                'role': 'ASSISTANT',
                'content': response_content,
                'message_type': 'MESSAGE'
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

        # Queue initial messages for recording
        self._queue_recording({
            'role': 'SYSTEM',
            'content': self.system_prompt,
            'message_type': 'MESSAGE'
        })
        self._queue_recording({
            'role': 'USER',
            'content': self.initial_message,
            'message_type': 'MESSAGE'
        })

        self._initialized = True
        logger.debug(f"Agent '{self.name}' conversation initialized")

    def _queue_recording(self, message_data: Dict[str, Any]):
        """Queue a message for async recording later."""
        if self.chat_recorder:
            self._recording_queue.append(message_data)

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
            # Extract tool call info (handle both dict and object formats)
            if isinstance(tool_call, dict):
                tool_name = tool_call.get('name', 'UNKNOWN')
                tool_args = tool_call.get('args', {})
                tool_call_id = tool_call.get('id')
            else:
                tool_name = getattr(tool_call, 'name', 'UNKNOWN')
                tool_args = getattr(tool_call, 'args', {})
                tool_call_id = getattr(tool_call, 'id', None)

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            # Execute tool
            tool_result = self._execute_single_tool(tool_name, tool_args)

            # Record tool call in ToolPrimitive
            self.tool_primitive.record_call(tool_name, tool_args, tool_result)

            # Queue tool call for recording
            self._queue_recording({
                'role': 'TOOL',
                'content': str(tool_result),
                'message_type': 'TOOL_RESPONSE',
                'tool_name': tool_name,
                'tool_parameters': tool_args,
                'tool_response': {'result': tool_result}
            })

            # Check if this is a stop request
            if tool_name == "done" or tool_name == "stop":
                reason = tool_args.get('reason', 'Agent requested stop')
                success = tool_args.get('success', True)
                self.stop_primitive.request(reason, success)

            # Add tool result to conversation
            if tool_call_id:
                tool_message = ToolMessage(content=str(tool_result), tool_call_id=tool_call_id)
                self._conversation.append(tool_message)

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

    def reset(self):
        """Reset the agent (mainly for testing)."""
        self._conversation.clear()
        self._initialized = False
        logger.debug(f"Agent '{self.name}' reset")

    def __repr__(self) -> str:
        return f"AgentPrimitive(name='{self.name}', turns={len(self._conversation)})"
