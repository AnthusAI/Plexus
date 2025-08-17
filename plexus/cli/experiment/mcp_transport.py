"""
In-Process MCP Transport for Experiments

This module provides an in-process implementation of the Model Context Protocol (MCP)
that allows experiments to provide MCP tools directly to AI models without requiring
a separate server process.

The implementation follows MCP architectural patterns but uses direct method calls
instead of stdio or HTTP transport, providing better performance and shared state
access for experiment contexts.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class MCPToolInfo:
    """Information about an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class MCPResourceInfo:
    """Information about an MCP resource."""
    uri: str
    name: str
    description: str
    mime_type: str
    handler: Callable[[str], str]


class InProcessMCPTransport:
    """
    In-process transport for MCP that uses direct method calls instead of 
    stdio or HTTP. Follows MCP JSON-RPC message format but executes synchronously.
    """
    
    def __init__(self):
        self.tools: Dict[str, MCPToolInfo] = {}
        self.resources: Dict[str, MCPResourceInfo] = {}
        self.connected = False
        self.client_info: Optional[Dict[str, Any]] = None
        self.server_info: Dict[str, Any] = {
            "name": "Plexus Experiment MCP Server",
            "version": "1.0.0"
        }
    
    def register_tool(self, tool_info: MCPToolInfo):
        """Register an MCP tool with the transport."""
        self.tools[tool_info.name] = tool_info
        logger.debug(f"Registered MCP tool: {tool_info.name}")
    
    def register_resource(self, resource_info: MCPResourceInfo):
        """Register an MCP resource with the transport."""
        self.resources[resource_info.uri] = resource_info
        logger.debug(f"Registered MCP resource: {resource_info.uri}")
    
    async def initialize(self, client_info: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize the MCP connection (equivalent to MCP initialize)."""
        self.client_info = client_info
        self.connected = True
        
        logger.info(f"MCP connection initialized with client: {client_info.get('name', 'Unknown')}")
        
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False}
            },
            "serverInfo": self.server_info
        }
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools (equivalent to MCP tools/list)."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            }
            for tool in self.tools.values()
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool (equivalent to MCP tools/call)."""
        if not self.connected:
            raise RuntimeError("MCP transport not initialized")
        
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found")
        
        tool = self.tools[name]
        
        try:
            logger.info(f"=== MCP TOOL CALL DEBUG ===")
            logger.info(f"Tool Name: '{name}'")
            logger.info(f"Arguments Received: {arguments}")
            logger.info(f"Arguments Type: {type(arguments)}")
            logger.info(f"Tool Handler: {tool.handler}")
            logger.info("=== CALLING TOOL HANDLER ===")
            result = tool.handler(arguments)
            logger.info(f"Tool Result: {result}")
            logger.info("=== END MCP TOOL CALL ===")
            
            # Handle async results (Tasks and coroutines)
            if hasattr(result, '__await__'):
                result = await result
            
            # Ensure result follows MCP tool call response format
            if not isinstance(result, dict):
                result = {"content": [{"type": "text", "text": str(result)}]}
            elif "content" not in result:
                # Wrap raw result in MCP content format
                result = {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
            
            logger.debug(f"MCP tool '{name}' completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error executing MCP tool '{name}': {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources (equivalent to MCP resources/list)."""
        return [
            {
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
                "mimeType": resource.mime_type
            }
            for resource in self.resources.values()
        ]
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource (equivalent to MCP resources/read)."""
        if not self.connected:
            raise RuntimeError("MCP transport not initialized")
        
        if uri not in self.resources:
            raise ValueError(f"Resource '{uri}' not found")
        
        resource = self.resources[uri]
        
        try:
            logger.debug(f"Reading MCP resource '{uri}'")
            content = resource.handler(uri)
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": resource.mime_type,
                        "text": content
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error reading MCP resource '{uri}': {e}")
            raise


class EmbeddedMCPServer:
    """
    An embedded MCP server that runs within an experiment process.
    Provides MCP tools and resources without requiring a separate server process.
    """
    
    def __init__(self, experiment_context: Optional[Dict[str, Any]] = None):
        self.transport = InProcessMCPTransport()
        self.experiment_context = experiment_context or {}
        self._setup_core_tools()
    
    def _setup_core_tools(self):
        """Setup core MCP tools that are useful for experiments."""
        
        # Tool: Get experiment context
        self.transport.register_tool(MCPToolInfo(
            name="get_experiment_context",
            description="Get the current experiment's context and state information",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            },
            handler=self._get_experiment_context
        ))
        
        # Tool: Log message
        self.transport.register_tool(MCPToolInfo(
            name="log_message",
            description="Log a message during experiment execution",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The message to log"},
                    "level": {"type": "string", "enum": ["debug", "info", "warning", "error"], "default": "info"}
                },
                "required": ["message"],
                "additionalProperties": False
            },
            handler=self._log_message
        ))
    
    def _get_experiment_context(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for get_experiment_context tool."""
        # Create a JSON-serializable copy of experiment context
        safe_context = {}
        if self.experiment_context:
            for key, value in self.experiment_context.items():
                # Skip non-serializable objects like PlexusDashboardClient
                if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    continue
                safe_context[key] = value
        
        return {
            "experiment_context": safe_context,
            "available_tools": list(self.transport.tools.keys()),
            "available_resources": list(self.transport.resources.keys())
        }
    
    def _log_message(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for log_message tool."""
        message = arguments.get("message", "")
        level = arguments.get("level", "info").lower()
        
        log_func = getattr(logger, level, logger.info)
        log_func(f"[Experiment MCP] {message}")
        
        return {"message": f"Logged message at {level} level: {message}"}
    
    def register_plexus_tools(self, tool_subset: Optional[List[str]] = None):
        """
        Register a subset of Plexus MCP tools for use in experiments.
        
        Args:
            tool_subset: List of tool names to register. If None, registers all available tools.
        """
        try:
            # Import the main MCP server tools from the MCP directory
            import sys
            import os
            
            # Add MCP directory to path temporarily
            # Get the project root (4 levels up from this file: mcp_transport.py -> experiment -> cli -> plexus -> project_root)
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            mcp_dir = os.path.join(project_root, 'MCP')
            
            if mcp_dir not in sys.path:
                sys.path.insert(0, mcp_dir)
                logger.debug(f"Added MCP directory to path: {mcp_dir}")
            
            from tools.util.think import register_think_tool
            from tools.scorecard.scorecards import register_scorecard_tools
            from tools.score.scores import register_score_tools
            from tools.item.items import register_item_tools
            from tools.feedback.feedback import register_feedback_tools
            from tools.prediction.predictions import register_prediction_tools
            from tools.experiment.experiment_nodes import register_experiment_node_tools
            
            # Create a mock MCP object that captures tool registrations
            class ToolCapture:
                def __init__(self, server):
                    self.server = server
                    self.registered_tools = []
                
                def tool(self):
                    def decorator(func):
                        # Extract tool info from the function
                        tool_name = func.__name__
                        tool_description = func.__doc__ or f"Tool: {tool_name}"
                        
                        # Create input schema - try to extract from function signature
                        input_schema = {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": True
                        }
                        
                        # Create a wrapper that handles both sync and async functions
                        async def async_handler(args):
                            try:
                                import asyncio
                                import inspect
                                
                                # Handle different argument patterns and function types
                                if args:
                                    if inspect.iscoroutinefunction(func):
                                        # Async function - need to run it
                                        try:
                                            loop = asyncio.get_running_loop()
                                            # We're in an event loop, create a task and await it
                                            return await func(**args)
                                        except RuntimeError:
                                            # No running loop, use asyncio.run
                                            return asyncio.run(func(**args))
                                    else:
                                        # Sync function
                                        return func(**args)
                                else:
                                    if inspect.iscoroutinefunction(func):
                                        try:
                                            loop = asyncio.get_running_loop()
                                            return await func()
                                        except RuntimeError:
                                            return asyncio.run(func())
                                    else:
                                        return func()
                                
                            except Exception as e:
                                logger.error(f"Error in MCP tool {tool_name}: {e}")
                                return {"error": str(e)}
                        
                        tool_info = MCPToolInfo(
                            name=tool_name,
                            description=tool_description,
                            input_schema=input_schema,
                            handler=async_handler
                        )
                        
                        self.server.transport.register_tool(tool_info)
                        self.registered_tools.append(tool_name)
                        
                        return func
                    return decorator
            
            tool_capture = ToolCapture(self)
            
            # Register selected tool sets
            available_tools = {
                "think": lambda: register_think_tool(tool_capture),
                "scorecard": lambda: register_scorecard_tools(tool_capture),
                "score": lambda: register_score_tools(tool_capture),
                "item": lambda: register_item_tools(tool_capture),
                "feedback": lambda: register_feedback_tools(tool_capture),
                "prediction": lambda: register_prediction_tools(tool_capture),
                "experiment_node": lambda: register_experiment_node_tools(tool_capture, self.experiment_context)
            }
            
            # If no specific tools requested, register all available tools
            if tool_subset is None:
                tool_subset = list(available_tools.keys())
            
            # Always register think tool as it's essential for AI planning
            if "think" not in tool_subset:
                tool_subset = ["think"] + list(tool_subset)
            
            for tool_category in tool_subset:
                if tool_category in available_tools:
                    try:
                        available_tools[tool_category]()
                        logger.info(f"Registered {tool_category} tools for experiment MCP")
                    except Exception as e:
                        logger.warning(f"Failed to register {tool_category} tools: {e}")
            
            logger.info(f"Total MCP tools registered: {len(self.transport.tools)}")
            
        except ImportError as e:
            logger.warning(f"Could not import Plexus MCP tools: {e}")
            logger.debug(f"MCP directory: {mcp_dir}")
            logger.debug(f"MCP directory exists: {os.path.exists(mcp_dir)}")
            logger.debug(f"sys.path contains MCP dir: {mcp_dir in sys.path}")
        except Exception as e:
            logger.error(f"Error registering Plexus tools: {e}")
    
    @asynccontextmanager
    async def connect(self, client_info: Optional[Dict[str, Any]] = None):
        """
        Context manager for MCP connection lifecycle.
        
        Usage:
            async with server.connect(client_info) as mcp_client:
                tools = await mcp_client.list_tools()
                result = await mcp_client.call_tool("tool_name", {"arg": "value"})
        """
        if client_info is None:
            client_info = {"name": "Experiment Client", "version": "1.0.0"}
        
        # Initialize connection
        init_result = await self.transport.initialize(client_info)
        logger.info(f"MCP connection established: {init_result}")
        
        try:
            # Create and yield client interface
            client = ExperimentMCPClient(self.transport)
            yield client
        finally:
            # Cleanup connection
            self.transport.connected = False
            logger.info("MCP connection closed")


class ExperimentMCPClient:
    """
    Client interface for interacting with the embedded MCP server.
    Provides async methods that match the MCP protocol.
    """
    
    def __init__(self, transport: InProcessMCPTransport):
        self.transport = transport
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools."""
        return await self.transport.list_tools()
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool with the given arguments."""
        return await self.transport.call_tool(name, arguments)
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available MCP resources."""
        return await self.transport.list_resources()
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read an MCP resource by URI."""
        return await self.transport.read_resource(uri)


# Convenience functions for experiment integration
async def create_experiment_mcp_server(
    experiment_context: Optional[Dict[str, Any]] = None,
    plexus_tools: Optional[List[str]] = None
) -> EmbeddedMCPServer:
    """
    Create and configure an embedded MCP server for experiment use.
    
    Args:
        experiment_context: Context information to make available to MCP tools
        plexus_tools: List of Plexus tool categories to register. 
                     If None, registers all available tools (default behavior).
    
    Returns:
        Configured EmbeddedMCPServer instance
    """
    server = EmbeddedMCPServer(experiment_context)
    
    # Always register Plexus tools (all tools if plexus_tools is None)
    server.register_plexus_tools(plexus_tools)
    
    return server