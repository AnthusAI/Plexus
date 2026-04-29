"""
Logging utilities for procedure execution.

This module provides consistent logging patterns for the multi-agent system,
including truncation utilities and chat history logging.
"""

import json
import logging
import os
import re
from typing import List, Any, Dict
from datetime import datetime, timezone
from pathlib import Path
try:
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
except ImportError:
    from langchain.schema import SystemMessage, HumanMessage, AIMessage, ToolMessage

logger = logging.getLogger(__name__)

_CONTEXT_CAPTURE_COUNTER = 0


def _context_capture_filter_matches(
    *,
    agent_name: str,
    call_site: str,
    context: str,
) -> bool:
    """Return whether this LLM call should be captured under the optional filter."""
    raw_filter = os.getenv("PLEXUS_CAPTURE_LLM_CONTEXT_FILTER", "")
    if not raw_filter.strip():
        return True

    haystack = " ".join(
        part.lower()
        for part in (agent_name or "", call_site or "", context or "")
        if part
    )
    filters = [
        item.strip().lower()
        for item in re.split(r"[,;\n]+", raw_filter)
        if item.strip()
    ]
    return any(item in haystack for item in filters)


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
        
        # Don't truncate initial messages (SYSTEM and first USER message) - they contain critical context
        # Only truncate subsequent conversation messages
        if i <= 1:
            # First two messages (system prompt and initial user prompt) - don't truncate
            logger.info(f"   [{i + 1}] {message_type}: {content}")
        else:
            # Later messages - truncate for readability
            truncated_content = truncate_log_message(content, max_lines=4)
            logger.info(f"   [{i + 1}] {message_type}: {truncated_content}")


def capture_llm_context_for_agent(
    agent_name: str,
    chat_history: List[Any],
    *,
    context: str = "",
    call_site: str = "",
    tools: List[Any] | None = None,
) -> Dict[str, str] | None:
    """
    Persist the exact message list about to be sent to an LLM.

    Capture is opt-in via PLEXUS_CAPTURE_LLM_CONTEXT_DIR. Files are local
    diagnostics intended for inspecting real agent context and must not be
    committed.
    """
    capture_dir = os.getenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR")
    if not capture_dir:
        return None
    if not _context_capture_filter_matches(
        agent_name=agent_name,
        call_site=call_site,
        context=context,
    ):
        return None

    global _CONTEXT_CAPTURE_COUNTER
    _CONTEXT_CAPTURE_COUNTER += 1

    output_dir = Path(capture_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc)
    timestamp_slug = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    slug = _slugify_context_filename(
        f"{_CONTEXT_CAPTURE_COUNTER:04d}-{agent_name}-{call_site or context or 'llm-call'}"
    )
    base_path = output_dir / f"{timestamp_slug}-{slug}"

    serialized_messages = [
        _serialize_context_message(index, message)
        for index, message in enumerate(chat_history, start=1)
    ]
    payload = {
        "agent_name": agent_name,
        "call_site": call_site,
        "context": context,
        "captured_at": timestamp.isoformat(),
        "message_count": len(serialized_messages),
        "total_character_count": sum(
            message["character_count"] for message in serialized_messages
        ),
        "tools": [_serialize_tool_name(tool) for tool in tools or []],
        "messages": serialized_messages,
    }

    json_path = base_path.with_suffix(".json")
    markdown_path = base_path.with_suffix(".md")
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_format_context_capture_markdown(payload), encoding="utf-8")

    logger.info(
        "Captured LLM context for %s at %s and %s",
        agent_name,
        markdown_path,
        json_path,
    )
    return {"markdown_path": str(markdown_path), "json_path": str(json_path)}


def capture_tactus_dspy_context_for_agent(
    agent_name: str,
    prompt_context: Dict[str, Any],
    *,
    turn_count: int | None = None,
    call_site: str = "tactus_dspy_agent_turn",
) -> Dict[str, str] | None:
    """Persist a Tactus/DSPy prompt_context using the standard capture format."""
    messages: List[Any] = []

    system_prompt = prompt_context.get("system_prompt")
    if system_prompt:
        messages.append({"role": "system", "content": str(system_prompt)})

    history = prompt_context.get("history", [])
    if hasattr(history, "messages"):
        history = history.messages
    if isinstance(history, list):
        messages.extend(history)

    user_message = prompt_context.get("user_message")
    if user_message:
        messages.append({"role": "user", "content": str(user_message)})

    context_parts = []
    if turn_count is not None:
        context_parts.append(f"turn {turn_count}")
    if user_message:
        context_parts.append(str(user_message)[:300])
    context = " | ".join(context_parts)
    return capture_llm_context_for_agent(
        agent_name=agent_name,
        chat_history=messages,
        context=context,
        call_site=call_site,
        tools=prompt_context.get("tools") or [],
    )


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
                logger.info(f"   [{i + 1}] {msg_type}: {len(full_content)} → {len(filtered_content)} chars")


def _get_message_type(message: Any) -> str:
    """Get a readable message type string."""
    if isinstance(message, dict):
        role = str(message.get("role") or "").lower()
        if role in {"system", "user", "assistant", "tool", "tool_result"}:
            return {
                "system": "SYSTEM",
                "user": "USER",
                "assistant": "ASSISTANT",
                "tool": "TOOL_RESULT",
                "tool_result": "TOOL_RESULT",
            }[role]
        return "DICT"
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


def _serialize_context_message(index: int, message: Any) -> Dict[str, Any]:
    content = _get_message_content(message)
    serialized = {
        "index": index,
        "role": _get_message_type(message),
        "class_name": message.__class__.__name__ if hasattr(message, "__class__") else "",
        "content": content,
        "character_count": len(content),
    }
    tool_calls = _extract_message_tool_calls(message)
    if tool_calls:
        serialized["tool_calls"] = tool_calls
    if hasattr(message, "tool_call_id"):
        serialized["tool_call_id"] = str(getattr(message, "tool_call_id"))
    return serialized


def _extract_message_tool_calls(message: Any) -> List[Dict[str, Any]]:
    raw_tool_calls = getattr(message, "tool_calls", None)
    if not raw_tool_calls and isinstance(message, dict):
        raw_tool_calls = message.get("tool_calls")
    tool_calls = []
    for raw_call in raw_tool_calls or []:
        if isinstance(raw_call, dict):
            tool_calls.append(
                {
                    "name": str(raw_call.get("name") or raw_call.get("tool_name") or ""),
                    "args": raw_call.get("args") or raw_call.get("arguments") or {},
                    "id": str(raw_call.get("id") or ""),
                }
            )
        else:
            tool_calls.append(
                {
                    "name": str(getattr(raw_call, "name", "")),
                    "args": getattr(raw_call, "args", {}),
                    "id": str(getattr(raw_call, "id", "")),
                }
            )
    return tool_calls


def _serialize_tool_name(tool: Any) -> str:
    if isinstance(tool, str):
        return tool
    return str(getattr(tool, "name", None) or getattr(tool, "__name__", None) or tool)


def _format_context_capture_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        f"# LLM Context Capture: {payload['agent_name']}",
        "",
        f"- Captured at: `{payload['captured_at']}`",
        f"- Call site: `{payload['call_site']}`",
        f"- Context: `{payload['context']}`",
        f"- Messages: `{payload['message_count']}`",
        f"- Total characters: `{payload['total_character_count']}`",
        "",
    ]
    tools = payload.get("tools") or []
    if tools:
        lines.extend(["## Tools", ""])
        for tool_name in tools:
            lines.append(f"- `{tool_name}`")
        lines.append("")

    lines.extend(["## Messages", ""])
    for message in payload["messages"]:
        lines.extend(
            [
                f"### {message['index']}. {message['role']}",
                "",
                f"- Class: `{message['class_name']}`",
                f"- Characters: `{message['character_count']}`",
                "",
            ]
        )
        if message.get("tool_calls"):
            lines.extend(["Tool calls:", ""])
            for tool_call in message["tool_calls"]:
                lines.append(
                    f"- `{tool_call['name']}` id=`{tool_call['id']}` args="
                    f"`{json.dumps(tool_call['args'], ensure_ascii=False, default=str)}`"
                )
            lines.append("")
        markdown_content = str(message["content"]).replace("\x00", "\\0")
        lines.extend(["```text", markdown_content, "```", ""])
    return "\n".join(lines)


def _slugify_context_filename(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return slug[:140] or "llm-context"


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
