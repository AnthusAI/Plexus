"""
Tool calling utilities for experiment AI execution.

Handles detection and execution of tool calls in AI responses.
"""

import logging
import re
import json
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


def extract_all_tool_calls(response_text: str, mcp_tools: List) -> List[Tuple[str, Dict[str, Any]]]:
    """Extract ALL tool calls from AI response."""
    # Look for tool call patterns - handle multiline formatting
    # Pattern: function_name( ... ) with potential newlines and spaces
    # But exclude common English words that aren't tools
    tool_call_pattern = r'(\w+)\s*\(\s*(.*?)\s*\)'
    matches = re.finditer(tool_call_pattern, response_text, re.DOTALL)
    
    tool_calls = []
    
    for match in matches:
        tool_name = match.group(1)
        tool_args_str = match.group(2)
        
        # Skip common English words that aren't tools
        if tool_name.upper() in ['YAML', 'JSON', 'HTML', 'XML', 'CSV', 'PDF', 'SQL']:
            logger.info(f"SKIPPING ENGLISH WORD: '{tool_name}' (not a tool)")
            continue
            
        # Check if this is actually a known tool
        if tool_name not in [tool.name for tool in mcp_tools]:
            logger.info(f"SKIPPING UNKNOWN TOOL: '{tool_name}' (not in tool list)")
            continue
        
        logger.info(f"FOUND TOOL PATTERN: name='{tool_name}', args='{tool_args_str}'")
        
        # Try to parse the arguments
        try:
            # Handle multiline, properly formatted arguments with better parsing
            tool_kwargs = {}
            if tool_args_str.strip():
                # Don't remove newlines yet - we need them for multiline strings
                args_text = tool_args_str.strip()
                logger.info(f"RAW ARGS TEXT: {repr(args_text)}")
                
                # Split by comma, but be smart about quoted strings and multiline content
                args = []
                current_arg = ""
                in_quotes = False
                quote_char = None
                paren_depth = 0
                
                i = 0
                while i < len(args_text):
                    char = args_text[i]
                    
                    if char in ['"', "'"] and (i == 0 or args_text[i-1] != '\\'):
                        if not in_quotes:
                            in_quotes = True
                            quote_char = char
                        elif char == quote_char:
                            in_quotes = False
                            quote_char = None
                    elif char == '(' and not in_quotes:
                        paren_depth += 1
                    elif char == ')' and not in_quotes:
                        paren_depth -= 1
                    elif char == ',' and not in_quotes and paren_depth == 0:
                        args.append(current_arg.strip())
                        current_arg = ""
                        i += 1
                        continue
                    
                    current_arg += char
                    i += 1
                
                # Add the last argument
                if current_arg.strip():
                    args.append(current_arg.strip())
                
                logger.info(f"SPLIT ARGS: {args}")
                
                # Parse each argument
                for arg in args:
                    if '=' in arg:
                        key, value = arg.split('=', 1)
                        key = key.strip().strip('"\'')
                        value = value.strip()
                        
                        # Remove outer quotes if present
                        if (value.startswith('"') and value.endswith('"')) or \
                           (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        
                        tool_kwargs[key] = value
            
            logger.info(f"PARSED TOOL ARGS: {tool_kwargs}")
            tool_calls.append((tool_name, tool_kwargs))
        except Exception as e:
            logger.error(f"Failed to parse tool args: {e}")
            logger.error(f"Args text was: {repr(tool_args_str)}")
            continue  # Try next match instead of skipping all
    
    # No valid tool calls found in function-style patterns
    # Fallback: look for simpler patterns like just "tool_name" at start of line
    if not tool_calls:
        simple_pattern = r'^(\w+)$'
        match = re.search(simple_pattern, response_text.strip(), re.MULTILINE)
        if match:
            tool_name = match.group(1)
            # Check if this looks like a tool name
            if tool_name in [tool.name for tool in mcp_tools]:
                logger.info(f"FOUND SIMPLE TOOL CALL: {tool_name}")
                tool_calls.append((tool_name, {}))
    
    return tool_calls


def call_tool(tool_name: str, tool_kwargs: Dict[str, Any], mcp_tools: List) -> str:
    """Call an MCP tool by name."""
    for mcp_tool in mcp_tools:
        if mcp_tool.name == tool_name:
            try:
                logger.info(f"Calling tool {tool_name} with {tool_kwargs}")
                result = mcp_tool.func(tool_kwargs)
                return str(result)
            except Exception as e:
                logger.error(f"Tool call failed: {e}")
                return f"Error calling {tool_name}: {e}"
    
    return f"Tool {tool_name} not found"
