"""
Logging utilities for experiment execution.

This module provides consistent logging patterns for the multi-agent system,
including truncation utilities and chat history logging.
"""

import logging
from typing import List, Any, Dict
try:
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
except ImportError:
    from langchain.schema import SystemMessage, HumanMessage, AIMessage, ToolMessage

logger = logging.getLogger(__name__)


def truncate_log_message(content: str, max_lines: int = 4) -> str:
    """
    Truncate log message content after specified number of lines.
    
    Args:
        content: The content to potentially truncate
        max_lines: Maximum number of lines to show (default: 4)
        
    Returns:
        Truncated content with truncation indication if needed
    """
    if not content:
        return ""
    
    lines = content.split('\n')
    
    if len(lines) <= max_lines:
        return content
    
    truncated_lines = lines[:max_lines]
    truncated_content = '\n'.join(truncated_lines)
    original_chars = len(content)
    truncated_chars = len(truncated_content)
    remaining_chars = original_chars - truncated_chars
    
    return f"{truncated_content}\n... [TRUNCATED: {remaining_chars} more characters, {len(lines) - max_lines} more lines]"


def log_chat_history_for_agent(agent_name: str, 
                              chat_history: List[Any], 
                              context: str = "") -> None:
    """
    Log the chat history that is being sent to a specific agent.
    
    This provides visibility into what each agent (manager/worker) actually sees
    in their conversation context.
    
    Args:
        agent_name: Name of the agent receiving this chat history
        chat_history: List of messages being sent to the agent
        context: Additional context about why this history is being sent
    """
    if not chat_history:
        logger.info(f"📨 {agent_name}: No chat history provided {context}")
        return
    
    logger.info(f"📨 {agent_name}: Sending {len(chat_history)} messages to model {context}")
    
    for i, message in enumerate(chat_history):
        message_type = _get_message_type(message)
        content = _get_message_content(message)
        
        # For AI messages with tool calls, show the tool calls instead of empty content
        if message_type == "ASSISTANT" and hasattr(message, 'tool_calls') and message.tool_calls:
            tool_calls_info = []
            for tool_call in message.tool_calls:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get('name', 'UNKNOWN')
                    tool_args = tool_call.get('args', {})
                else:
                    tool_name = getattr(tool_call, 'name', 'UNKNOWN')
                    tool_args = getattr(tool_call, 'args', {})
                tool_calls_info.append(f"{tool_name}({tool_args})")
            content = f"[TOOL_CALLS: {', '.join(tool_calls_info)}]"
        
        truncated_content = truncate_log_message(content, max_lines=4)
        logger.info(f"   [{i+1}] {message_type}: {truncated_content}")


def log_filtered_vs_full_history(agent_name: str,
                                full_history: List[Any],
                                filtered_history: List[Any],
                                filter_description: str = "") -> None:
    """
    Log comparison between full and filtered chat history.
    
    Args:
        agent_name: Name of the agent
        full_history: Complete conversation history
        filtered_history: Filtered conversation history  
        filter_description: Description of how filtering was applied
    """
    logger.info(f"🔄 {agent_name}: Chat filtering applied {filter_description}")
    logger.info(f"   Original: {len(full_history)} messages → Filtered: {len(filtered_history)} messages")
    
    if len(full_history) != len(filtered_history):
        # Show which messages were affected
        for i, (full_msg, filtered_msg) in enumerate(zip(full_history, filtered_history)):
            full_content = _get_message_content(full_msg)
            filtered_content = _get_message_content(filtered_msg)
            
            if len(full_content) != len(filtered_content):
                msg_type = _get_message_type(full_msg)
                logger.info(f"   [{i+1}] {msg_type}: {len(full_content)} → {len(filtered_content)} chars")


def _get_message_type(message: Any) -> str:
    """Get a readable message type string."""
    if isinstance(message, SystemMessage):
        return "SYSTEM"
    elif isinstance(message, HumanMessage):
        return "USER"
    elif isinstance(message, AIMessage):
        return "ASSISTANT"
    elif isinstance(message, ToolMessage):
        return "TOOL_RESULT"
    elif hasattr(message, '__class__'):
        return message.__class__.__name__.upper()
    else:
        return "UNKNOWN"


def _get_message_content(message: Any) -> str:
    """Get message content as string."""
    if hasattr(message, 'content'):
        return str(message.content)
    elif isinstance(message, dict) and 'content' in message:
        return str(message['content'])
    else:
        return str(message)


def log_tool_execution(tool_name: str, 
                      tool_args: Dict[str, Any], 
                      tool_result: Any,
                      execution_time: float = None) -> None:
    """
    Log tool execution with truncated results.
    
    Args:
        tool_name: Name of the tool being executed
        tool_args: Arguments passed to the tool
        tool_result: Result returned by the tool
        execution_time: Optional execution time in seconds
    """
    # Truncate arguments for logging
    args_str = str(tool_args)
    truncated_args = truncate_log_message(args_str, max_lines=2)
    
    # Truncate result for logging
    result_str = str(tool_result)
    truncated_result = truncate_log_message(result_str, max_lines=4)
    
    timing_info = f" ({execution_time:.2f}s)" if execution_time else ""
    
    logger.info(f"🔧 TOOL_CALL: {tool_name}{timing_info}")
    logger.info(f"   Args: {truncated_args}")
    logger.info(f"   Result: {truncated_result}")


def log_agent_response(agent_name: str, response_content: str, context: str = "") -> None:
    """
    Log agent response with truncation.
    
    Args:
        agent_name: Name of the responding agent
        response_content: The agent's response content
        context: Additional context about the response
    """
    truncated_content = truncate_log_message(response_content, max_lines=5)
    logger.info(f"🤖 {agent_name}: {context}")
    logger.info(f"   Response: {truncated_content}")


def reduce_debug_noise():
    """
    Configure logging to reduce debug noise while maintaining critical information.
    This should be called during initialization to clean up verbose logging.
    """
    # Reduce noise from specific modules that tend to be verbose
    verbose_modules = [
        'langchain.schema',
        'langchain_core',
        'langchain_openai',
        'openai',
        'httpx',
        'urllib3'
    ]
    
    for module_name in verbose_modules:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(logging.WARNING)
