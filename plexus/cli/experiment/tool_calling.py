"""
Tool calling utilities for experiment AI execution.

Handles detection and execution of tool calls in AI responses.
"""

import logging
import re
import json
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


def _llm_repair_malformed_json(malformed_json: str, available_tools: List[str]) -> str:
    """Use an LLM to attempt repair of malformed JSON tool calls."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import SystemMessage, HumanMessage
        import os
        
        # Only attempt LLM repair if we have an API key available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.debug("No OpenAI API key available for LLM repair, skipping")
            return malformed_json
        
        # Create a lightweight model for JSON repair
        repair_llm = ChatOpenAI(
            model="gpt-4o-mini",  # Use smaller, faster model for JSON repair
            temperature=0,        # No creativity needed - just structure fixing
            openai_api_key=api_key,
            max_tokens=1000       # Limit tokens for efficiency
        )
        
        system_prompt = f"""You are a JSON repair specialist. Your job is to fix malformed JSON that represents tool calls.

AVAILABLE TOOLS: {', '.join(available_tools)}

COMMON ISSUES TO FIX:
1. Extra closing braces or brackets
2. Missing closing braces or brackets  
3. Escape sequence problems in strings (especially \\n, \\t, \\')
4. Trailing commas before closing brackets
5. Invalid JSON syntax

REQUIREMENTS:
- Output ONLY valid JSON, no explanations
- Preserve the original tool name and parameters as much as possible
- Use this exact structure: {{"tool": "tool_name", "arguments": {{"param": "value"}}}}
- If the original has "parameters" instead of "arguments", convert it
- If multiple tools are present, output only the first valid one

CRITICAL: Output only the repaired JSON, nothing else."""

        human_prompt = f"""Please repair this malformed JSON tool call:

{malformed_json}

Remember: Output ONLY the repaired JSON, no explanations or markdown."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        # Call the LLM with a timeout
        logger.info("Attempting LLM-based JSON repair...")
        response = repair_llm.invoke(messages)
        repaired_json = response.content.strip()
        
        # Clean up any markdown formatting the LLM might have added
        if repaired_json.startswith('```'):
            repaired_json = repaired_json.split('\n', 1)[1]
        if repaired_json.endswith('```'):
            repaired_json = repaired_json.rsplit('\n', 1)[0]
        
        logger.info(f"LLM repair result: {repaired_json[:100]}...")
        
        # Test if the repair worked by trying to parse it
        try:
            import json
            json.loads(repaired_json)
            logger.info("✅ LLM repair successful - JSON is now valid")
            return repaired_json
        except json.JSONDecodeError:
            logger.warning("❌ LLM repair failed - result is still invalid JSON")
            return malformed_json
            
    except Exception as e:
        logger.warning(f"LLM repair failed with error: {e}")
        return malformed_json


def extract_all_tool_calls(response_text: str, mcp_tools: List) -> List[Tuple[str, Dict[str, Any]]]:
    """Extract ALL tool calls from AI response - supports both JSON and function-style formats."""
    tool_calls = []
    available_tool_names = [tool.name for tool in mcp_tools]
    
    logger.debug(f"Looking for tool calls in response...")
    logger.debug(f"Available tools: {available_tool_names}")
    
    # METHOD 1: JSON-formatted tool calls (for OpenAI o3 and similar models)
    # Look for complete JSON objects with "tool" and "arguments" fields
    # Use a more robust approach to find complete JSON objects with proper nesting support
    
    def find_complete_json_objects(text: str) -> List[str]:
        """Find complete JSON objects in text, handling complex nested structures."""
        json_objects = []
        i = 0
        
        while i < len(text):
            # Look for opening brace
            if text[i] == '{':
                # Found potential JSON start, now find the matching closing brace
                brace_count = 1
                json_start = i
                i += 1
                in_string = False
                escape_next = False
                
                while i < len(text) and brace_count > 0:
                    char = text[i]
                    
                    if escape_next:
                        escape_next = False
                    elif char == '\\':
                        escape_next = True
                    elif char == '"' and not escape_next:
                        in_string = not in_string
                    elif not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                    
                    i += 1
                
                # If we found a complete JSON object (brace_count == 0)
                if brace_count == 0:
                    json_candidate = text[json_start:i]
                    json_objects.append(json_candidate)
                    logger.debug(f"Found potential JSON object: {json_candidate[:200]}...")
                else:
                    # Incomplete JSON, continue from next character
                    i = json_start + 1
            else:
                i += 1
        
        return json_objects
    
    # METHOD 1A: Extract JSON from markdown code blocks first
    # Many AI models wrap JSON in ```json ... ``` blocks
    markdown_json_pattern = r'```(?:json)?\s*(.*?)\s*```'
    markdown_matches = re.findall(markdown_json_pattern, response_text, re.DOTALL)
    
    # Find all complete JSON objects in the response (including from markdown blocks)
    json_blocks = find_complete_json_objects(response_text)
    
    # Add JSON from markdown blocks to our search
    for markdown_json in markdown_matches:
        # Only add if it looks like JSON (starts with {)
        if markdown_json.strip().startswith('{'):
            json_blocks.append(markdown_json.strip())
    
    # CRITICAL FIX: Deduplicate json_blocks to prevent duplicate tool call detection
    # This fixes the issue where markdown JSON blocks are found by both markdown extraction
    # and general JSON detection, causing the same tool call to be executed twice
    json_blocks = list(dict.fromkeys(json_blocks))  # Preserves order while removing duplicates
    logger.debug(f"After deduplication: {len(json_blocks)} unique JSON blocks to process")
    
    for json_block in json_blocks:
        try:
            logger.debug(f"Checking JSON block: {json_block[:100]}...")
            
            # Clean the JSON by removing JavaScript-style comments that AI models sometimes include
            # This handles cases where AI includes /* comment */ style comments in JSON
            cleaned_json = json_block
            
            # Remove /* ... */ style comments (multiline)
            cleaned_json = re.sub(r'/\*.*?\*/', '', cleaned_json, flags=re.DOTALL)
            
            # Remove // style comments (single line) - be careful not to break URLs
            # Only remove if // appears at start of line (with optional whitespace) or after comma/bracket
            cleaned_json = re.sub(r'(?:^|(?<=[,\[\{])\s*)//.*?$', '', cleaned_json, flags=re.MULTILINE)
            
            # Clean up any resulting empty lines or trailing commas before closing brackets
            cleaned_json = re.sub(r',\s*([}\]])', r'\1', cleaned_json)  # Remove trailing commas
            cleaned_json = re.sub(r'\n\s*\n', '\n', cleaned_json)  # Remove empty lines
            
            # Fix escape sequences in JSON strings - critical for complex code content
            # This handles cases where JSON contains Python code with single quotes that need proper JSON escaping
            def fix_string_escapes(match):
                string_content = match.group(1)
                # Handle common problematic escape sequences in the string content
                # Fix \' -> \\' (single quote escape) 
                string_content = string_content.replace("\\'", "\\\\'")
                # Fix \n that aren't already \\n
                string_content = re.sub(r'(?<!\\)\\n', '\\\\n', string_content)
                # Fix \t that aren't already \\t  
                string_content = re.sub(r'(?<!\\)\\t', '\\\\t', string_content)
                return f'"{string_content}"'
            
            # Apply escape fixes to string values
            # This pattern matches JSON string values (content between quotes, handling escaped quotes)
            string_pattern = r'"((?:[^"\\]|\\.)*)"'
            cleaned_json = re.sub(string_pattern, fix_string_escapes, cleaned_json)
            
            logger.debug(f"Cleaned JSON block: {cleaned_json[:100]}...")
            
            # Try to parse as JSON
            parsed_json = json.loads(cleaned_json)
            
            # Check if it has the expected tool call structure (support both formats)
            if isinstance(parsed_json, dict) and ("tool" in parsed_json or "name" in parsed_json):
                # Extract tool name from either "tool" or "name" field
                tool_name = parsed_json.get("tool") or parsed_json.get("name")
                # Support "arguments", "parameters", "args", and "params" field names for different AI models
                tool_arguments = parsed_json.get("arguments") or parsed_json.get("parameters") or parsed_json.get("args") or parsed_json.get("params", {})
                
                logger.info(f"Found JSON tool call: {tool_name}({tool_arguments})")
                
                # Check if this is a known tool
                if tool_name not in available_tool_names:
                    logger.debug(f"Skipping unknown tool: '{tool_name}' (not in tool list)")
                    continue
                
                # Validate arguments is a dict
                if not isinstance(tool_arguments, dict):
                    logger.error(f"Invalid arguments format - expected dict, got {type(tool_arguments)}")
                    continue
                
                # CRITICAL FIX: Filter out false positive tool calls that are likely examples or placeholders
                # This prevents the AI's explanatory content from being executed as actual tool calls
                def is_likely_false_positive(tool_name: str, args: dict) -> bool:
                    """Detect if this looks like an example/placeholder rather than a real tool call."""
                    
                    # Check for completely empty arguments (clear false positive)
                    if not args:
                        return False  # Empty args are actually valid for some tools
                    
                    # Check if all parameter values are empty strings (clear placeholder)
                    all_empty = all(value == '' for value in args.values() if isinstance(value, str))
                    if all_empty and len(args) > 0:
                        logger.debug(f"REJECTING: All parameters are empty strings - likely placeholder")
                        return True
                    
                    # Check for obvious placeholder values commonly used in examples
                    placeholder_patterns = {
                        'final_exp', 'doctor_mentions', 'dosage_mentions', 'original_val', 'original_value',
                        'example_text', 'placeholder', 'your_text_here', 'sample_text', 'demo_value',
                        'test_value', 'dummy_value', 'lorem_ipsum', 'foo', 'bar', 'baz',
                        'param1', 'param2', 'value1', 'value2', 'arg1', 'arg2'
                    }
                    
                    # Count how many parameters have placeholder-like values
                    placeholder_count = 0
                    total_string_params = 0
                    
                    for value in args.values():
                        if isinstance(value, str):
                            total_string_params += 1
                            if value.lower() in placeholder_patterns:
                                placeholder_count += 1
                    
                    # If more than half of string parameters are placeholders, likely false positive
                    if total_string_params > 0 and placeholder_count / total_string_params >= 0.5:
                        logger.debug(f"REJECTING: {placeholder_count}/{total_string_params} parameters are placeholders")
                        return True
                    
                    # Special case for 'think' tool - be extra strict since it's commonly used in examples
                    if tool_name == 'think':
                        # Reject if parameters look like variable names rather than actual thoughts
                        for key, value in args.items():
                            if isinstance(value, str):
                                # If value looks like a variable name (lowercase, underscores, no spaces)
                                if value and '_' in value and ' ' not in value and value.islower():
                                    logger.debug(f"REJECTING think: Parameter '{key}={value}' looks like a variable name")
                                    return True
                                # If value is very short and generic
                                if len(value.strip()) < 3:
                                    logger.debug(f"REJECTING think: Parameter '{key}={value}' is too short/generic")
                                    return True
                    
                    return False
                
                # Apply false positive detection
                if is_likely_false_positive(tool_name, tool_arguments):
                    logger.info(f"SKIPPING FALSE POSITIVE: {tool_name}({tool_arguments}) - likely example/placeholder content")
                    continue
                
                logger.info(f"PARSED JSON TOOL ARGS: {tool_arguments}")
                tool_calls.append((tool_name, tool_arguments))
                
        except json.JSONDecodeError as e:
            # JSON parsing failed - attempt LLM repair before giving up
            logger.info(f"JSON parsing failed for block: {e}")
            logger.info(f"Attempting LLM repair on malformed JSON: {json_block[:100]}...")
            
            # Try to repair the malformed JSON using LLM
            repaired_json = _llm_repair_malformed_json(json_block, available_tool_names)
            
            if repaired_json != json_block:
                # LLM made changes - try parsing the repaired version
                try:
                    logger.info(f"Testing LLM-repaired JSON: {repaired_json[:100]}...")
                    parsed_json = json.loads(repaired_json)
                    
                    # Check if it has the expected tool call structure (support both formats)
                    if isinstance(parsed_json, dict) and ("tool" in parsed_json or "name" in parsed_json):
                        # Extract tool name from either "tool" or "name" field
                        tool_name = parsed_json.get("tool") or parsed_json.get("name")
                        # Support "arguments", "parameters", "args", and "params" field names for different AI models
                        tool_arguments = parsed_json.get("arguments") or parsed_json.get("parameters") or parsed_json.get("args") or parsed_json.get("params", {})
                        
                        logger.info(f"✅ LLM repair successful! Found tool call: {tool_name}({tool_arguments})")
                        
                        # Check if this is a known tool
                        if tool_name not in available_tool_names:
                            logger.debug(f"Skipping unknown tool: '{tool_name}' (not in tool list)")
                            continue
                        
                        # Validate arguments is a dict
                        if not isinstance(tool_arguments, dict):
                            logger.error(f"Invalid arguments format - expected dict, got {type(tool_arguments)}")
                            continue
                        
                        logger.info(f"PARSED REPAIRED JSON TOOL ARGS: {tool_arguments}")
                        tool_calls.append((tool_name, tool_arguments))
                        continue  # Successfully processed this block, move to next
                        
                except json.JSONDecodeError as repair_error:
                    logger.warning(f"❌ LLM repair failed - result still invalid: {repair_error}")
                    # Fall through to original skip behavior
            else:
                logger.debug("LLM repair made no changes - original JSON was likely too malformed")
            
            # Original behavior: skip this block if repair didn't work
            continue
        except Exception as e:
            logger.error(f"Error processing JSON block: {e}")
            continue
    
    # METHOD 2: Function-style tool calls (traditional format)
    # Look for tool call patterns - handle multiline formatting
    # Pattern: function_name( ... ) with potential newlines and spaces
    # But be more restrictive to avoid false positives from conversational text
    
    # Only match function calls that:
    # 1. Start at beginning of line or after whitespace
    # 2. Have parentheses with content that looks like parameters (contains = or is empty)
    # 3. Are actually known tools
    
    # Enhanced pattern to handle multiline function calls better
    # This pattern looks for tool_name followed by opening paren, then captures everything until matching closing paren
    enhanced_function_pattern = r'(?:^|\n|\s)(\w+)\s*\(\s*((?:[^()]*|\([^)]*\))*)\s*\)'
    function_matches = re.finditer(enhanced_function_pattern, response_text, re.DOTALL | re.MULTILINE)
    
    logger.debug(f"Looking for function-style tool calls with enhanced pattern...")
    
    for match in function_matches:
        tool_name = match.group(1)
        tool_args_str = match.group(2)
        
        # Skip common English words that aren't tools
        if tool_name.upper() in ['YAML', 'JSON', 'HTML', 'XML', 'CSV', 'PDF', 'SQL']:
            logger.debug(f"SKIPPING ENGLISH WORD: '{tool_name}' (not a tool)")
            continue
            
        # Check if this is actually a known tool
        if tool_name not in available_tool_names:
            logger.debug(f"SKIPPING UNKNOWN FUNCTION TOOL: '{tool_name}' (not in tool list)")
            continue
        
        # Additional validation: Check if arguments look like actual function parameters
        # Skip if it looks like prose/documentation rather than a function call
        if tool_args_str.strip() and not ('=' in tool_args_str or tool_args_str.strip() == ''):
            # If args don't contain = and aren't empty, it's probably not a function call
            logger.debug(f"SKIPPING PROSE-LIKE PATTERN: '{tool_name}({tool_args_str})' (doesn't look like function call)")
            continue
        
        logger.info(f"FOUND FUNCTION TOOL PATTERN: name='{tool_name}', args='{tool_args_str}'")
        
        # Try to parse the arguments
        try:
            # Handle multiline, properly formatted arguments with better parsing
            tool_kwargs = {}
            if tool_args_str.strip():
                # Don't remove newlines yet - we need them for multiline strings
                args_text = tool_args_str.strip()
                logger.info(f"RAW ARGS TEXT: {repr(args_text)}")
                
                # Enhanced argument parsing to handle complex multiline strings and nested structures
                args = []
                current_arg = ""
                in_quotes = False
                quote_char = None
                paren_depth = 0
                bracket_depth = 0
                
                i = 0
                while i < len(args_text):
                    char = args_text[i]
                    
                    # Handle escape sequences
                    if char == '\\' and i + 1 < len(args_text) and in_quotes:
                        current_arg += char + args_text[i + 1]
                        i += 2
                        continue
                    
                    if char in ['"', "'"] and not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char and in_quotes:
                        in_quotes = False
                        quote_char = None
                    elif not in_quotes:
                        if char == '(':
                            paren_depth += 1
                        elif char == ')':
                            paren_depth -= 1
                        elif char == '[':
                            bracket_depth += 1
                        elif char == ']':
                            bracket_depth -= 1
                        elif char == ',' and paren_depth == 0 and bracket_depth == 0:
                            # Found a top-level comma - split here
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
                
                # Parse each argument with improved key-value extraction
                for arg in args:
                    if '=' in arg:
                        # Find the first equals sign that's not inside quotes
                        equals_pos = -1
                        in_arg_quotes = False
                        arg_quote_char = None
                        
                        for j, c in enumerate(arg):
                            if c in ['"', "'"] and (j == 0 or arg[j-1] != '\\'):
                                if not in_arg_quotes:
                                    in_arg_quotes = True
                                    arg_quote_char = c
                                elif c == arg_quote_char:
                                    in_arg_quotes = False
                                    arg_quote_char = None
                            elif c == '=' and not in_arg_quotes:
                                equals_pos = j
                                break
                        
                        if equals_pos > 0:
                            key = arg[:equals_pos].strip().strip('"\'')
                            value = arg[equals_pos + 1:].strip()
                            
                            # Remove outer quotes if present, but preserve inner content
                            if ((value.startswith('"') and value.endswith('"')) or 
                                (value.startswith("'") and value.endswith("'"))):
                                value = value[1:-1]
                            
                            tool_kwargs[key] = value
                        else:
                            logger.warning(f"Could not parse argument: {arg}")
                    else:
                        logger.debug(f"Skipping non-key-value argument: {arg}")
            
            logger.info(f"PARSED FUNCTION TOOL ARGS: {tool_kwargs}")
            if tool_kwargs or not tool_args_str.strip():  # Allow empty args for some tools
                tool_calls.append((tool_name, tool_kwargs))
        except Exception as e:
            logger.error(f"Failed to parse function tool args: {e}")
            logger.error(f"Args text was: {repr(tool_args_str)}")
            continue  # Try next match instead of skipping all
    
    # METHOD 3: YAML-like structured format detection and REJECTION
    # This method specifically identifies and REJECTS YAML-like patterns to prevent false positives
    # Pattern: tool_name followed by key: value pairs on new lines
    yaml_pattern = r'(\w+)\s*\n\s*(\w+)\s*:\s*(.+)'
    yaml_matches = re.finditer(yaml_pattern, response_text, re.MULTILINE)
    
    for match in yaml_matches:
        tool_name = match.group(1)
        # If this looks like a YAML-style tool call pattern, explicitly reject it
        if tool_name in available_tool_names:
            logger.info(f"REJECTING YAML-LIKE PATTERN: '{tool_name}' followed by key:value - this is conversational text, not a tool call")
            # Continue without adding to tool_calls - this is intentional rejection
    
    # METHOD 4: Simple tool names (fallback)
    # No valid tool calls found in JSON or function-style patterns
    # This fallback is very aggressive and causes false positives
    # Only use it if the response is VERY short and contains ONLY the tool name
    if not tool_calls:
        # Only trigger simple tool detection for very short responses (< 50 chars)
        # that contain essentially just the tool name
        if len(response_text.strip()) < 50:
            simple_pattern = r'^(\w+)$'
            match = re.search(simple_pattern, response_text.strip(), re.MULTILINE)
            if match:
                tool_name = match.group(1)
                # Check if this looks like a tool name
                if tool_name in available_tool_names:
                    logger.info(f"Found simple tool call: {tool_name}")
                    tool_calls.append((tool_name, {}))
    
    logger.info(f"Tool call detection complete: found {len(tool_calls)} tool calls")
    for tool_name, tool_kwargs in tool_calls:
        logger.debug(f"  - {tool_name}: {tool_kwargs}")
    
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

