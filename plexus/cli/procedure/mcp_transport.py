"""
In-Process MCP Transport for Procedures

This module provides an in-process implementation of the Model Context Protocol (MCP)
that allows experiments to provide MCP tools directly to AI models without requiring
a separate server process.

The implementation follows MCP architectural patterns but uses direct method calls
instead of stdio or HTTP transport, providing better performance and shared state
access for procedure contexts.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from plexus.dashboard.api.client import LONG_RUNNING_WRITE_RETRY_POLICY_NAME
from plexus.dashboard.api.models.task import Task

logger = logging.getLogger(__name__)


def _parse_task_metadata(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _touch_task_runtime_heartbeat(client: Any, task_id: str) -> None:
    task = Task.get_by_id(task_id, client)
    runtime = _parse_task_metadata(task.metadata).get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
    now_iso = datetime.now(timezone.utc).isoformat()
    runtime["lastHeartbeatAt"] = now_iso
    metadata = _parse_task_metadata(task.metadata)
    metadata["runtime"] = runtime
    task.update(
        metadata=json.dumps(metadata),
        updatedAt=now_iso,
    )


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
            "name": "Plexus Procedure MCP Server",
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
            # Call tool handler
            logger.debug(f"🔧 MCP TRANSPORT: Calling handler for tool '{name}' with args: {arguments}")
            logger.debug(f"🔧 MCP TRANSPORT: Tool handler type: {type(tool.handler)}")
            result = tool.handler(arguments)
            logger.debug(f"🔧 MCP TRANSPORT: Handler returned: {type(result)} - {str(result)[:200]}...")
            
            # Handle async results (Tasks and coroutines)
            if hasattr(result, '__await__'):
                logger.debug(f"🔧 MCP TRANSPORT: Awaiting coroutine for tool '{name}'")
                try:
                    result = await result
                    logger.debug(f"🔧 MCP TRANSPORT: Coroutine completed, result: {type(result)} - {str(result)[:200]}...")
                except Exception as e:
                    logger.error(f"🔧 MCP TRANSPORT: Coroutine failed with error: {e}")
                    import traceback
                    logger.error(f"🔧 MCP TRANSPORT: Traceback: {traceback.format_exc()}")
                    raise
            
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


def _advance_task_to_stage_by_name(client: Any, task_id: str, stage_name: str) -> None:
    """
    Update TaskStage records so the named stage is RUNNING and prior stages are COMPLETED.

    Args:
        client: PlexusDashboardClient
        task_id: Task whose stages to update
        stage_name: Name of the stage to mark as RUNNING (case-insensitive match)
    """
    stage_query = """
    query GetTask($id: ID!) {
        getTask(id: $id) {
            stages {
                items {
                    id
                    name
                    order
                    status
                }
            }
        }
    }
    """
    result = client.execute(stage_query, {"id": task_id})
    stages = result.get("getTask", {}).get("stages", {}).get("items", [])
    if not stages:
        logger.debug("No TaskStages found for task %s", task_id)
        return

    target = next(
        (s for s in stages if s.get("name", "").lower() == stage_name.lower()),
        None
    )
    if not target:
        logger.warning("Stage '%s' not found in task %s (available: %s)",
                       stage_name, task_id, [s.get("name") for s in stages])
        return

    target_order = target.get("order", 0)
    update_mutation = """
    mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
        updateTaskStage(input: $input) {
            id
            status
        }
    }
    """
    now = datetime.now(timezone.utc).isoformat()
    for stage in stages:
        order = stage.get("order", 0)
        if order < target_order and stage.get("status") != "COMPLETED":
            client.execute(
                update_mutation,
                {
                    "input": {"id": stage["id"], "status": "COMPLETED", "completedAt": now}
                },
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
        elif order == target_order and stage.get("status") != "RUNNING":
            client.execute(
                update_mutation,
                {
                    "input": {"id": stage["id"], "status": "RUNNING", "startedAt": now}
                },
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
        elif order > target_order and stage.get("status") != "PENDING":
            client.execute(
                update_mutation,
                {
                    "input": {"id": stage["id"], "status": "PENDING", "startedAt": None, "completedAt": None}
                },
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
    try:
        _touch_task_runtime_heartbeat(client, task_id)
    except Exception as exc:
        logger.warning("Could not refresh runtime heartbeat for task %s after stage update: %s", task_id, exc)


def _update_stage_status_message(client: Any, task_id: str, message: str) -> None:
    """Update statusMessage on the current RUNNING TaskStage."""
    stage_query = """
    query GetTask($id: ID!) {
        getTask(id: $id) {
            stages {
                items {
                    id
                    status
                }
            }
        }
    }
    """
    result = client.execute(stage_query, {"id": task_id})
    stages = result.get("getTask", {}).get("stages", {}).get("items", [])
    running = next((s for s in stages if s.get("status") == "RUNNING"), None)
    if not running:
        logger.debug("No RUNNING stage found for task %s", task_id)
        return

    update_mutation = """
    mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
        updateTaskStage(input: $input) {
            id
            statusMessage
        }
    }
    """
    client.execute(
        update_mutation,
        {"input": {"id": running["id"], "statusMessage": message[:500]}},
        retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
    )


def _update_stage_progress(client: Any, task_id: str, current: int, total: int) -> None:
    """
    Update processedItems and totalItems on the current RUNNING TaskStage.

    Args:
        client: PlexusDashboardClient
        task_id: Task whose running stage to update
        current: Current progress count
        total: Total expected count
    """
    stage_query = """
    query GetTask($id: ID!) {
        getTask(id: $id) {
            stages {
                items {
                    id
                    name
                    order
                    status
                }
            }
        }
    }
    """
    result = client.execute(stage_query, {"id": task_id})
    stages = result.get("getTask", {}).get("stages", {}).get("items", [])
    running = next((s for s in stages if s.get("status") == "RUNNING"), None)
    if not running:
        logger.debug("No RUNNING stage found for task %s", task_id)
        return

    update_mutation = """
    mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
        updateTaskStage(input: $input) {
            id
            processedItems
            totalItems
        }
    }
    """
    client.execute(
        update_mutation,
        {
            "input": {
                "id": running["id"],
                "processedItems": current,
                "totalItems": total
            }
        },
        retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
    )
    logger.info("Updated stage %s progress: %d/%d", running.get("name"), current, total)
    try:
        _touch_task_runtime_heartbeat(client, task_id)
    except Exception as exc:
        logger.warning("Could not refresh runtime heartbeat for task %s after progress update: %s", task_id, exc)


class EmbeddedMCPServer:
    """
    An embedded MCP server that runs within an procedure process.
    Provides MCP tools and resources without requiring a separate server process.
    """

    def __init__(self, experiment_context: Optional[Dict[str, Any]] = None):
        self.transport = InProcessMCPTransport()
        self.experiment_context = experiment_context or {}
        self._setup_core_tools()
        self._setup_stage_tool()
        self._setup_stage_progress_tool()
        self._setup_status_message_tool()
    
    def _setup_core_tools(self):
        """Setup core MCP tools that are useful for experiments."""
        
        # Tool: Get procedure context
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
            description="Log a message during procedure execution",
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
    
    def _setup_stage_tool(self):
        """Register the plexus_set_procedure_stage tool."""
        self.transport.register_tool(MCPToolInfo(
            name="plexus_set_procedure_stage",
            description="Update the current stage indicator for this procedure in the dashboard",
            input_schema={
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "Stage name to set as current (e.g. 'setup', 'baseline', 'optimize', 'finalize')"}
                },
                "required": ["stage"],
                "additionalProperties": False
            },
            handler=self._set_procedure_stage
        ))

    def _set_procedure_stage(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Update the TaskStage record in the DB when Stage.set() is called from Lua."""
        stage_name = arguments.get('stage', '')
        task_id = self.experiment_context.get('task_id')

        if not task_id:
            logger.warning("plexus_set_procedure_stage: no task_id in experiment_context, skipping")
            return {"success": False, "error": "No task_id in context"}

        try:
            from plexus.dashboard.api.client import PlexusDashboardClient
            client = PlexusDashboardClient()
            _advance_task_to_stage_by_name(client, task_id, stage_name)
            logger.info(f"Stage set to '{stage_name}' for task {task_id}")
            return {"success": True, "stage": stage_name}
        except Exception as e:
            logger.warning(f"plexus_set_procedure_stage failed: {e}")
            return {"success": False, "error": str(e)}

    def _setup_stage_progress_tool(self):
        """Register the plexus_set_stage_progress tool."""
        self.transport.register_tool(MCPToolInfo(
            name="plexus_set_stage_progress",
            description="Update progress (processedItems/totalItems) on the current RUNNING stage",
            input_schema={
                "type": "object",
                "properties": {
                    "current": {"type": "integer", "description": "Current progress count (e.g., cycle number)"},
                    "total": {"type": "integer", "description": "Total expected count (e.g., max cycles)"}
                },
                "required": ["current", "total"],
                "additionalProperties": False
            },
            handler=self._set_stage_progress
        ))

    def _set_stage_progress(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Update processedItems/totalItems on the current RUNNING TaskStage."""
        current = arguments.get('current', 0)
        total = arguments.get('total', 0)
        task_id = self.experiment_context.get('task_id')

        if not task_id:
            return {"success": False, "error": "No task_id in context"}

        try:
            from plexus.dashboard.api.client import PlexusDashboardClient
            client = PlexusDashboardClient()
            _update_stage_progress(client, task_id, current, total)
            return {"success": True, "current": current, "total": total}
        except Exception as e:
            logger.warning(f"plexus_set_stage_progress failed: {e}")
            return {"success": False, "error": str(e)}

    def _setup_status_message_tool(self):
        """Register the plexus_set_status_message tool."""
        self.transport.register_tool(MCPToolInfo(
            name="plexus_set_status_message",
            description="Update the status message on the current RUNNING stage (visible in the dashboard during long-running procedures)",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Short status message (max 500 chars) describing what the procedure is doing right now"}
                },
                "required": ["message"],
                "additionalProperties": False
            },
            handler=self._set_status_message
        ))

    def _set_status_message(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Update statusMessage on the current RUNNING TaskStage."""
        message = str(arguments.get('message', ''))
        task_id = self.experiment_context.get('task_id')

        if not task_id:
            return {"success": False, "error": "No task_id in context"}

        try:
            from plexus.dashboard.api.client import PlexusDashboardClient
            client = PlexusDashboardClient()
            _update_stage_status_message(client, task_id, message)
            return {"success": True, "message": message}
        except Exception as e:
            logger.warning(f"plexus_set_status_message failed: {e}")
            return {"success": False, "error": str(e)}

    def _get_experiment_context(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for get_experiment_context tool."""
        # Create a JSON-serializable copy of procedure context
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
        log_func(f"[Procedure MCP] {message}")
        
        return {"message": f"Logged message at {level} level: {message}"}
    
    def register_plexus_tools(self, tool_subset: Optional[List[str]] = None):
        """
        Register a subset of Plexus MCP tools for use in experiments.
        
        Args:
            tool_subset: List of tool names to register. If None, registers all available tools.
        """
        try:
            # The legacy MCP tool catalog (tools.scorecard, tools.score, etc.) has been
            # removed. All Plexus functionality is now exposed through execute_tactus in
            # MCP/tools/tactus_runtime/. Procedure-internal tool loading is a no-op here;
            # rubric_memory and other features are available to Tactus procedures via the
            # plexus.* runtime APIs.
            import sys
            import os
            
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

                        # Build JSON schema from the registered function signature.
                        # This keeps MCP tool argument contracts available to Tactus.
                        import inspect
                        from typing import Any, get_args, get_origin, Literal, Union
                        from pydantic import BaseModel

                        def annotation_to_schema(annotation: Any) -> Dict[str, Any]:
                            if annotation is inspect._empty:
                                return {"type": "string"}

                            origin = get_origin(annotation)
                            args = get_args(annotation)

                            if origin in (list, List):
                                item_annotation = args[0] if args else Any
                                return {"type": "array", "items": annotation_to_schema(item_annotation)}

                            if origin in (dict, Dict):
                                return {"type": "object", "additionalProperties": True}

                            if origin is Literal:
                                literal_values = [value for value in args if value is not None]
                                schema: Dict[str, Any] = {"enum": literal_values}
                                if literal_values:
                                    first = literal_values[0]
                                    if isinstance(first, bool):
                                        schema["type"] = "boolean"
                                    elif isinstance(first, int) and not isinstance(first, bool):
                                        schema["type"] = "integer"
                                    elif isinstance(first, float):
                                        schema["type"] = "number"
                                    else:
                                        schema["type"] = "string"
                                else:
                                    schema["type"] = "string"
                                return schema

                            if origin is Union:
                                non_none = [arg for arg in args if arg is not type(None)]
                                if len(non_none) == 1:
                                    return annotation_to_schema(non_none[0])
                                return {"type": "string"}

                            if isinstance(annotation, type):
                                if issubclass(annotation, BaseModel):
                                    return annotation.model_json_schema()
                                if annotation is bool:
                                    return {"type": "boolean"}
                                if annotation is int:
                                    return {"type": "integer"}
                                if annotation is float:
                                    return {"type": "number"}
                                if annotation is str:
                                    return {"type": "string"}
                                if annotation is dict:
                                    return {"type": "object", "additionalProperties": True}
                                if annotation is list:
                                    return {"type": "array", "items": {"type": "string"}}

                            return {"type": "string"}

                        signature = inspect.signature(func)
                        properties: Dict[str, Any] = {}
                        required: List[str] = []
                        for param_name, parameter in signature.parameters.items():
                            if param_name in {"self", "cls", "ctx", "context"}:
                                continue
                            if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                                continue
                            if parameter.default is inspect._empty:
                                required.append(param_name)
                            param_schema = annotation_to_schema(parameter.annotation)
                            properties[param_name] = param_schema

                        input_schema = {
                            "type": "object",
                            "properties": properties,
                            "additionalProperties": False,
                        }
                        if required:
                            input_schema["required"] = required
                        
                        # Create a wrapper that handles both sync and async functions
                        async def async_handler(args):
                            try:
                                import asyncio
                                import inspect
                                
                                logger.debug(f"🔧 WRAPPER: async_handler called for {tool_name} with args: {args}")
                                logger.debug(f"🔧 WRAPPER: func is coroutine function: {inspect.iscoroutinefunction(func)}")
                                
                                # Handle different argument patterns and function types
                                if args:
                                    if inspect.iscoroutinefunction(func):
                                        # Async function - need to run it
                                        try:
                                            loop = asyncio.get_running_loop()
                                            logger.debug(f"🔧 WRAPPER: Calling await func(**args) for {tool_name}")
                                            # We're in an event loop, create a task and await it
                                            result = await func(**args)
                                            logger.debug(f"🔧 WRAPPER: func returned: {type(result)} - {str(result)[:200]}...")
                                            return result
                                        except RuntimeError:
                                            logger.debug(f"🔧 WRAPPER: No running loop, using asyncio.run for {tool_name}")
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
                                logger.error(f"🔧 WRAPPER: Exception in MCP tool {tool_name}: {e}")
                                import traceback
                                logger.error(f"🔧 WRAPPER: Traceback: {traceback.format_exc()}")
                                return {"error": str(e)}
                        
                        tool_info = MCPToolInfo(
                            name=tool_name,
                            description=tool_description,
                            input_schema=input_schema,
                            handler=async_handler
                        )
                        
                        logger.info(f"🔧 REGISTRATION: Registering tool '{tool_name}' with handler {async_handler}")
                        self.server.transport.register_tool(tool_info)
                        self.registered_tools.append(tool_name)
                        logger.info(f"🔧 REGISTRATION: Successfully registered tool '{tool_name}'")
                        
                        return func
                    return decorator
            
            tool_capture = ToolCapture(self)

            # Register the built-in done tool used by all Tactus agents.
            @tool_capture.tool()
            async def done(reason: str = "", success: Optional[bool] = True, **kwargs):
                """Signal agent completion with an optional reason and any additional fields."""
                import json as _json
                # If extra fields were passed (e.g. hypothesis, new_code), encode them
                # as JSON in the reason field so Lua can decode them with Tool.last_call("done").args.reason
                if kwargs and not reason:
                    reason = _json.dumps(kwargs)
                elif kwargs:
                    # Merge reason and extra kwargs into a single JSON blob
                    try:
                        existing = _json.loads(reason)
                        if isinstance(existing, dict):
                            existing.update(kwargs)
                            reason = _json.dumps(existing)
                    except (ValueError, TypeError):
                        # reason is a plain string; wrap everything together
                        merged = {"reason": reason}
                        merged.update(kwargs)
                        reason = _json.dumps(merged)
                return {
                    "status": "completed",
                    "success": bool(True if success is None else success),
                    "reason": reason,
                    "tool": "done",
                }
            
            # Register execute_tactus so LLM agents (e.g. console chat) can query
            # Plexus data by writing short Lua snippets.
            import os as _os_et, sys as _sys_et
            _mcp_path_et = _os_et.path.normpath(
                _os_et.path.join(_os_et.path.dirname(__file__), "..", "..", "..", "MCP")
            )
            if _os_et.path.isdir(_mcp_path_et) and _mcp_path_et not in _sys_et.path:
                _sys_et.path.insert(0, _mcp_path_et)

            try:
                from tools.tactus_runtime.execute import (  # type: ignore[import]
                    _execute_tactus_tool as _et_run,
                    _default_trace_store as _et_traces,
                    _default_handle_store as _et_handles,
                    BudgetGate,
                    BudgetSpec,
                )

                _et_trace_store = _et_traces()
                _et_handle_store = _et_handles()
                # Permissive budget: async eval/procedure dispatch must be allowed
                _et_budget = BudgetGate(BudgetSpec(
                    usd=float("inf"),
                    wallclock_seconds=float("inf"),
                    depth=20,
                    tool_calls=500,
                ))

                @tool_capture.tool()
                async def execute_tactus(tactus: str) -> dict:
                    """Execute a Tactus (Lua) snippet against the Plexus runtime.
                    `plexus` is a global providing access to all Plexus functionality.
                    Examples:
                      return plexus.scorecards.list({})
                      return plexus.score.info({ id = "score-id" })
                      return plexus.evaluation.find_recent({ score_id = "id", count = 5 })
                      return plexus.item.last({ count = 1 })
                    """
                    return await _et_run(
                        tactus,
                        None,
                        ctx=None,
                        trace_store=_et_trace_store,
                        handle_store=_et_handle_store,
                        budget=_et_budget,
                    )

                logger.info("Registered execute_tactus in embedded MCP transport")
            except Exception as _et_exc:
                logger.warning(f"Could not register execute_tactus in embedded MCP: {_et_exc}")

            logger.info(f"Total MCP tools registered: {len(self.transport.tools)}")
            
        except Exception as e:
            logger.error(f"Error registering procedure tools: {e}")
    
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
            client_info = {"name": "Procedure Client", "version": "1.0.0"}
        
        # Initialize connection
        init_result = await self.transport.initialize(client_info)
        logger.info(f"MCP connection established: {init_result}")
        
        try:
            # Create and yield client interface
            client = ProcedureMCPClient(self.transport)
            yield client
        finally:
            # Cleanup connection
            self.transport.connected = False
            logger.info("MCP connection closed")


class ProcedureMCPClient:
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


# Convenience functions for procedure integration
async def create_procedure_mcp_server(
    experiment_context: Optional[Dict[str, Any]] = None,
    plexus_tools: Optional[List[str]] = None
) -> EmbeddedMCPServer:
    """
    Create and configure an embedded MCP server for procedure use.
    
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
