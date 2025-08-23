"""
LangChain MCP Adapter for tool conversion.

Converts MCP tools into LangChain-compatible tools, handling async execution,
argument formatting, and chat recording integration.
"""

import asyncio
import concurrent.futures
import json
import logging
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from .mcp_tool import MCPTool

logger = logging.getLogger(__name__)


class LangChainMCPAdapter:
    """
    Adapter that converts MCP tools into LangChain-compatible tools.
    
    This allows AI models using LangChain to seamlessly access all Plexus MCP tools
    through the in-process MCP transport.
    """
    
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.tools = []
        self._tools_loaded = False
        self.chat_recorder = None  # Will be set by the AI runner
        self.pending_tool_calls = {}  # Maps tool_name to most recent call_id
        self.tools_called = set()  # Track which tools have been used
    
    async def load_tools(self) -> List[MCPTool]:
        """Load and convert all MCP tools to LangChain format."""
        if self._tools_loaded:
            return self.tools
        
        try:
            # Get tools from MCP client
            mcp_tools = await self.mcp_client.list_tools()
            logger.info(f"Loading {len(mcp_tools)} MCP tools for LangChain")
            
            self.tools = []
            for mcp_tool in mcp_tools:
                # Create LangChain-compatible tool
                langchain_tool = self._create_langchain_tool(mcp_tool)
                self.tools.append(langchain_tool)
                logger.debug(f"Converted MCP tool '{mcp_tool['name']}' to LangChain tool")
            
            self._tools_loaded = True
            logger.info(f"Successfully loaded {len(self.tools)} tools for LangChain")
            return self.tools
            
        except Exception as e:
            logger.error(f"Error loading MCP tools for LangChain: {e}")
            return []
    
    def _create_langchain_tool(self, mcp_tool: Dict[str, Any]) -> MCPTool:
        """Convert an MCP tool to a LangChain-compatible tool."""
        tool_name = mcp_tool['name']
        tool_description = mcp_tool['description']
        
        # Create the function that will be called by LangChain
        def tool_func(args) -> str:
            try:
                # Handle different argument formats from LangChain
                if isinstance(args, str):
                    # LangChain sometimes passes string arguments
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, ValueError):
                        # If it's not valid JSON, treat as a simple string parameter
                        # Try to guess the parameter name from the tool schema
                        input_schema = mcp_tool.get('inputSchema', {})
                        properties = input_schema.get('properties', {})
                        if properties:
                            # Use the first property name as the parameter
                            first_param = list(properties.keys())[0]
                            args = {first_param: args}
                        else:
                            # Default to common parameter names
                            args = {'query': args}
                elif not isinstance(args, dict):
                    # Convert other types to dict
                    args = {'input': str(args)}
                
                # Ensure args is a dictionary
                if not isinstance(args, dict):
                    args = {}
                
                # Handle the async call properly - check for existing event loop
                try:
                    # Try to get the current event loop
                    current_loop = asyncio.get_running_loop()
                    # We're in an async context, so we need to create a task
                    # But since LangChain expects sync execution, we'll use a workaround
                    
                    # Run the async call in a separate thread with its own event loop
                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            logger.debug(f"🔧 MCP ADAPTER: Calling tool '{tool_name}' with args: {args}")
                            result = new_loop.run_until_complete(
                                self.mcp_client.call_tool(tool_name, args)
                            )
                            logger.debug(f"🔧 MCP ADAPTER: Tool '{tool_name}' returned: {type(result)} - {str(result)[:200]}...")
                            # Track tool usage for conversation flow
                            self.tools_called.add(tool_name)
                            return result
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_in_thread)
                        result = future.result(timeout=30)  # 30 second timeout
                        
                except RuntimeError:
                    # No event loop running, safe to create one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        logger.debug(f"🔧 MCP ADAPTER: Calling tool '{tool_name}' with args: {args}")
                        result = loop.run_until_complete(
                            self.mcp_client.call_tool(tool_name, args)
                        )
                        logger.debug(f"🔧 MCP ADAPTER: Tool '{tool_name}' returned: {type(result)} - {str(result)[:200]}...")
                        # Track tool usage for conversation flow
                        self.tools_called.add(tool_name)
                    finally:
                        loop.close()
                
                # TOOL RESPONSE RECORDING: Since on_tool_end callback isn't being called,
                # we need to record tool responses here in the MCP wrapper
                if self.chat_recorder and tool_name in self.pending_tool_calls:
                    tool_call_id = self.pending_tool_calls[tool_name]
                    logger.info(f"MCP WRAPPER: Recording tool response for {tool_name}, call_id: {tool_call_id}")
                    
                    try:
                        # Format the tool response
                        if isinstance(result, dict):
                            response_str = json.dumps(result, indent=2)
                        else:
                            response_str = str(result)
                        
                        # Truncate very long tool responses to prevent context overflow
                        max_response_length = 10000  # ~2500 tokens
                        if len(response_str) > max_response_length:
                            response_str = response_str[:max_response_length] + f"\n\n[Response truncated - was {len(response_str)} chars, showing first {max_response_length}]"
                        
                        content = f"Response from tool: {tool_name}\n\nResponse:\n{response_str}"
                        
                        response_id = self.chat_recorder.record_message_sync(
                            role='TOOL',
                            content=content,
                            message_type='TOOL_RESPONSE',
                            tool_name=tool_name,
                            parent_message_id=tool_call_id
                        )
                        
                        if response_id:
                            logger.info(f"MCP WRAPPER: ✅ Recorded tool response {response_id}")
                        else:
                            logger.error(f"MCP WRAPPER: ❌ Failed to record tool response")
                        
                        # Clean up the pending tool call
                        del self.pending_tool_calls[tool_name]
                        
                    except Exception as e:
                        logger.error(f"MCP WRAPPER: ❌ Error recording tool response: {e}")
                        import traceback
                        logger.error(f"MCP WRAPPER: Full traceback: {traceback.format_exc()}")
                
                # Format the result for LangChain - preserve full response for accurate analysis
                def format_response(result_data):
                    """Format the result without truncation for accurate AI analysis."""
                    # The AI context management should be done at the LLM level, not by truncating tool results
                    # This allows the AI to see the full data and make informed decisions
                    if isinstance(result_data, dict):
                        # Return the JSON string representation for consistent parsing
                        return json.dumps(result_data, indent=2)
                    else:
                        return str(result_data)
                
                if isinstance(result, dict):
                    if 'content' in result:
                        # MCP standard format
                        content = result['content']
                        if isinstance(content, list) and len(content) > 0:
                            raw_text = content[0].get('text', str(result))
                            return format_response(raw_text)
                        return format_response(content)
                    elif 'error' in result:
                        return f"Error: {result['error']}"
                    else:
                        return format_response(result)
                else:
                    return format_response(result)
                    
            except Exception as e:
                error_msg = f"Error calling MCP tool {tool_name}: {str(e)}"
                logger.error(error_msg)
                return error_msg
        
        # Create schema for the tool arguments (simplified)
        try:
            input_schema = mcp_tool.get('inputSchema', {})
            properties = input_schema.get('properties', {})
            
            # Create a simple args schema
            class ToolArgs(BaseModel):
                pass
            
            # Dynamically add fields based on the schema
            for prop_name, prop_info in properties.items():
                prop_type = str  # Default to string for simplicity
                prop_description = prop_info.get('description', f'{prop_name} parameter')
                
                # Add field to the model
                setattr(ToolArgs, prop_name, Field(default="", description=prop_description))
            
            args_schema = ToolArgs
            
        except Exception as e:
            logger.warning(f"Could not create args schema for {tool_name}: {e}")
            args_schema = None
        
        return MCPTool(
            name=tool_name,
            description=tool_description,
            args_schema=args_schema,
            func=tool_func
        )


def convert_mcp_tools_to_langchain(mcp_tools):
    """
    Convert MCP tools to LangChain StructuredTool format.
    
    This function takes a list of MCPTool objects and converts them to
    LangChain StructuredTool objects for use with LangChain agents.
    
    Args:
        mcp_tools: List of MCPTool objects
        
    Returns:
        List of LangChain StructuredTool objects
    """
    from langchain.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Union, Optional
    
    langchain_tools = []
    
    # Known tool schemas for proper argument handling
    known_tool_schemas = {
        'plexus_feedback_analysis': {
            'scorecard_name': 'Name of the scorecard',
            'score_name': 'Name of the score',
            'days': 'Number of days back to analyze',
            'output_format': 'Output format - json or yaml'
        },
        'plexus_feedback_find': {
            'scorecard_name': 'Name of the scorecard containing the score',
            'score_name': 'Name of the specific score to search feedback for',
            'initial_value': 'Optional filter for the original AI prediction value',
            'final_value': 'Optional filter for the corrected human value',
            'limit': 'Maximum number of feedback items to return (default 5, max 50)',
            'days': 'Number of days back to search',
            'output_format': 'Output format - json or yaml',
            'prioritize_edit_comments': 'Whether to prioritize feedback items with edit comments',
            'offset': 'Simple numeric offset for pagination'
        },
        'plexus_item_info': {
            'item_id': 'The unique ID of the item OR an external identifier value'
        },
        'create_experiment_node': {
            'experiment_id': 'The unique ID of the experiment',
            'hypothesis_description': 'Clear description following format: GOAL: [target] | METHOD: [changes]',
            'node_name': 'Descriptive name for the hypothesis node (optional)',
            'yaml_configuration': 'Optional YAML configuration'
        },
        'update_node_content': {
            'node_id': 'ID of the node to update',
            'yaml_configuration': 'Updated YAML configuration',
            'update_description': 'Description of what changed in this update',
            'computed_value': 'Optional computed results'
        },
        'think': {
            'thought': 'Your internal reasoning or analysis'
        }
    }
    
    for mcp_tool in mcp_tools:
        tool_name = mcp_tool.name
        tool_description = mcp_tool.description
        tool_func = mcp_tool.func
        
        # Get schema for this tool
        schema_props = known_tool_schemas.get(tool_name, {})
        
        # Create wrapper function
        def make_structured_func(func, name):
            def wrapper(*args, **kwargs):
                # Handle different argument patterns from LangChain
                if args and not kwargs:
                    if len(args) == 1 and isinstance(args[0], dict):
                        result = func(args[0])
                    else:
                        # Convert positional args to dict
                        arg_dict = {}
                        prop_names = list(schema_props.keys()) if schema_props else ['input']
                        for i, arg in enumerate(args):
                            if i < len(prop_names):
                                arg_dict[prop_names[i]] = arg
                        result = func(arg_dict)
                elif kwargs:
                    result = func(kwargs)
                else:
                    result = func({})
                
                return result
            return wrapper
        
        # Build Pydantic model for arguments
        if schema_props:
            annotations = {}
            field_defaults = {}
            
            for prop_name, prop_description in schema_props.items():
                annotations[prop_name] = Optional[Union[str, int, float, bool]]
                field_defaults[prop_name] = Field(default="", description=prop_description)
            
            class_name = f"{tool_name.replace('-', '_')}_Args"
            ArgsSchema = type(class_name, (BaseModel,), {
                '__annotations__': annotations,
                **field_defaults
            })
        else:
            class ArgsSchema(BaseModel):
                input: Optional[Union[str, int, float, bool]] = Field(default="", description="Tool input")
        
        # Create LangChain StructuredTool
        langchain_tool = StructuredTool(
            name=tool_name,
            description=tool_description,
            func=make_structured_func(tool_func, tool_name),
            args_schema=ArgsSchema
        )
        
        langchain_tools.append(langchain_tool)
    
    return langchain_tools

