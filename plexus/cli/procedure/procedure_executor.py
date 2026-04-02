"""
Procedure Executor - Routes procedure execution based on class field.

Supports multiple procedure execution engines:
- Tactus: Lua-based DSL runtime
- SOPAgent: Existing SOP agent system (default)
"""

import logging
import json
import inspect
import asyncio
import queue
import threading
import yaml
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class _PlexusTraceLogBridge:
    """
    Bridges synchronous Tactus log events to async Plexus trace persistence.

    - Exposes supports_streaming=True so Tactus enables agent chunk streaming.
    - Captures CostEvent entries for execution summary accounting.
    - Forwards all non-cost events to PlexusTraceSink on a background worker.
    """

    supports_streaming = True

    def __init__(self, trace_sink: Any):
        self.trace_sink = trace_sink
        self.cost_events = []
        self._events: "queue.Queue[Any]" = queue.Queue()
        self._closed = threading.Event()
        self._worker = threading.Thread(
            target=self._worker_main,
            name="plexus-trace-log-bridge",
            daemon=True,
        )
        self._worker.start()

    def log(self, event: Any) -> None:
        try:
            from tactus.protocols.models import CostEvent
        except Exception:
            CostEvent = None  # type: ignore

        if CostEvent is not None and isinstance(event, CostEvent):
            self.cost_events.append(event)
            return

        try:
            self._events.put_nowait(event)
        except Exception as exc:
            logger.warning("Failed queueing trace event for persistence: %s", exc)

    def _worker_main(self) -> None:
        while not self._closed.is_set() or not self._events.empty():
            try:
                event = self._events.get(timeout=0.05)
            except queue.Empty:
                continue

            try:
                record_fn = getattr(self.trace_sink, "record", None)
                if callable(record_fn):
                    asyncio.run(record_fn(event))
            except Exception as exc:
                logger.warning("Failed recording streamed trace event: %s", exc)
            finally:
                self._events.task_done()

    async def flush(self) -> None:
        await asyncio.to_thread(self._events.join)
        flush_fn = getattr(self.trace_sink, "flush", None)
        if callable(flush_fn):
            await flush_fn()

    async def close(self) -> None:
        self._closed.set()
        await asyncio.to_thread(self._worker.join, 1.0)


async def execute_procedure(
    procedure_id: str,
    procedure_code: str,
    client,
    mcp_server,
    context: Optional[Dict[str, Any]] = None,
    **options
) -> Dict[str, Any]:
    """
    Execute a procedure using the appropriate engine.

    Args:
        procedure_id: Procedure ID
        procedure_code: Procedure YAML (Tactus or SOPAgent)
        client: PlexusDashboardClient instance
        mcp_server: MCP server for tool access
        context: Optional context dict with pre-loaded data
        **options: Additional execution options (openai_api_key, etc.)

    Returns:
        Execution results dict
    """
    try:
        # Parse YAML procedure wrapper
        config = yaml.safe_load(procedure_code)

        if not isinstance(config, dict):
            raise ValueError("Invalid YAML: root must be a dictionary")

        # Check class field to determine executor
        procedure_class = config.get('class', '')

        logger.info(f"Routing procedure {procedure_id} to executor: {procedure_class}")

        if procedure_class == 'Tactus':
            code = config.get('code')
            if not isinstance(code, str) or not code.strip():
                raise ValueError("Tactus procedure requires non-empty 'code' field")
            return await _execute_tactus(
                procedure_id,
                procedure_code,
                client,
                mcp_server,
                context,
                **options
            )

        elif procedure_class == 'SOPAgent' or not procedure_class:
            # Route to existing SOP agent system
            return await _execute_sop_agent(
                procedure_id,
                procedure_code,
                client,
                mcp_server,
                context,
                **options
            )

        else:
            # Unknown class
            error_msg = f"Unknown procedure class: {procedure_class}. Supported: Tactus, SOPAgent"
            logger.error(error_msg)
            return {
                'success': False,
                'procedure_id': procedure_id,
                'error': error_msg
            }

    except yaml.YAMLError as e:
        error_msg = f"Failed to parse procedure configuration: {e}"
        logger.error(error_msg)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': error_msg
        }

    except Exception as e:
        error_msg = f"Procedure execution failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': error_msg
        }


async def _execute_tactus(
    procedure_id: str,
    procedure_source: str,
    client,
    mcp_server,
    context: Optional[Dict[str, Any]],
    **options
) -> Dict[str, Any]:
    """
    Execute procedure using Tactus runtime with Plexus adapters.

    Args:
        procedure_id: Procedure ID
        procedure_source: Full Tactus YAML procedure source
        client: PlexusDashboardClient
        mcp_server: MCP server
        context: Optional context
        **options: Additional options (openai_api_key, etc.)

    Returns:
        Execution results
    """
    logger.info(f"Executing procedure {procedure_id} with Tactus runtime")
    log_bridge: Optional[_PlexusTraceLogBridge] = None

    try:
        from tactus.core import TactusRuntime
        from .tactus_adapters import PlexusStorageAdapter, PlexusHITLAdapter, PlexusTraceSink
        from .chat_recorder import ProcedureChatRecorder
        
        def _extract_legacy_input_from_params(source_config: Dict[str, Any]) -> Dict[str, Any]:
            """Resolve legacy runtime input from params.<name>.value/default declarations."""
            params_config = source_config.get("params")
            if not isinstance(params_config, dict):
                return {}

            resolved: Dict[str, Any] = {}
            for name, definition in params_config.items():
                if not isinstance(name, str) or not name:
                    continue
                if not isinstance(definition, dict):
                    continue
                if "value" in definition:
                    resolved[name] = definition.get("value")
                elif "default" in definition:
                    resolved[name] = definition.get("default")
            return resolved

        def _lua_string(value: str) -> str:
            escaped = (
                value.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
            )
            return f'"{escaped}"'

        def _lua_literal(value: Any) -> str:
            if value is None:
                return "nil"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return repr(value)
            if isinstance(value, str):
                return _lua_string(value)
            try:
                payload = json.dumps(value)
                payload = payload.replace("]]", "] ]")
                return f"Json.decode([[{payload}]])"
            except Exception:
                return _lua_string(str(value))

        def _lua_table_literal(values: Dict[str, Any]) -> str:
            entries = []
            for key, value in values.items():
                if not isinstance(key, str) or not key:
                    continue
                entries.append(f"[{_lua_string(key)}] = {_lua_literal(value)}")
            return "{ " + ", ".join(entries) + " }" if entries else "{}"

        def _extract_assistant_text(payload: Any) -> Optional[str]:
            if not isinstance(payload, dict):
                return None
            response_value = payload.get("response")
            if isinstance(response_value, str) and response_value.strip():
                return response_value.strip()
            nested_result = payload.get("result")
            if isinstance(nested_result, dict):
                nested_response = nested_result.get("response")
                if isinstance(nested_response, str) and nested_response.strip():
                    return nested_response.strip()
            return None

        # Backward compatibility: older Plexus templates use `code:` for Lua source.
        # Current Tactus parser expects `procedure:` as the required field.
        try:
            parsed_source = yaml.safe_load(procedure_source)
            if isinstance(parsed_source, dict):
                changed = False

                if 'procedure' not in parsed_source:
                    legacy_code = parsed_source.get('code')
                    if isinstance(legacy_code, str) and legacy_code.strip():
                        parsed_source = dict(parsed_source)
                        parsed_source['procedure'] = legacy_code
                        parsed_source.pop('code', None)
                        changed = True
                        logger.info("Adapted legacy Tactus config: mapped 'code' to 'procedure'")

                if not parsed_source.get('default_provider'):
                    parsed_source = dict(parsed_source)
                    parsed_source['default_provider'] = 'openai'
                    changed = True
                    logger.info("Adapted Tactus config: set default_provider to 'openai'")

                agents = parsed_source.get('agents')
                if isinstance(agents, dict):
                    normalized_agents = dict(agents)
                    agents_changed = False
                    for agent_name, agent_config in agents.items():
                        if not isinstance(agent_config, dict):
                            continue
                        tools = agent_config.get('tools')
                        if (
                            isinstance(tools, list)
                            and tools
                            and all(isinstance(tool, str) for tool in tools)
                            and all(tool.startswith('plexus_') for tool in tools)
                        ):
                            updated_agent_config = dict(agent_config)
                            # Use direct named toolset binding for compatibility with DSPy tool conversion.
                            # Filtered toolset wrappers currently lose visible tool definitions, resulting in
                            # zero callable tools at runtime.
                            updated_agent_config['tools'] = ['plexus']
                            normalized_agents[agent_name] = updated_agent_config
                            agents_changed = True
                    if agents_changed:
                        parsed_source = dict(parsed_source)
                        parsed_source['agents'] = normalized_agents
                        changed = True
                        logger.info("Adapted Tactus config: normalized legacy tool lists to plexus toolset expressions")

                if changed:
                    procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)

            # Backward compatibility shims for older Lua procedures.
            if isinstance(parsed_source, dict):
                lua_source = parsed_source.get('procedure')
                if isinstance(lua_source, str):
                    shim_parts = []

                    if 'Specification(' in lua_source and 'function Specification' not in lua_source:
                        shim_parts.append(
                            "if Specification == nil then\n"
                            "  function Specification(spec)\n"
                            "    return spec\n"
                            "  end\n"
                            "end\n"
                        )
                        shim_parts.append(
                            "if field == nil then\n"
                            "  field = setmetatable({}, {\n"
                            "    __index = function(_, _)\n"
                            "      return function(value)\n"
                            "        return value\n"
                            "      end\n"
                            "    end\n"
                            "  })\n"
                            "end\n"
                        )

                    if 'State.' in lua_source and 'State = ' not in lua_source:
                        shim_parts.append(
                            "if State == nil then\n"
                            "  local __legacy_state = {}\n"
                            "  State = {\n"
                            "    get = function(key, default)\n"
                            "      local value = __legacy_state[key]\n"
                            "      if value == nil then\n"
                            "        return default\n"
                            "      end\n"
                            "      return value\n"
                            "    end,\n"
                            "    set = function(key, value)\n"
                            "      __legacy_state[key] = value\n"
                            "      return value\n"
                            "    end,\n"
                            "    increment = function(key, amount)\n"
                            "      local current = __legacy_state[key]\n"
                            "      if type(current) ~= 'number' then\n"
                            "        current = 0\n"
                            "      end\n"
                            "      local delta = amount or 1\n"
                            "      __legacy_state[key] = current + delta\n"
                            "      return __legacy_state[key]\n"
                            "    end,\n"
                            "    append = function(key, value)\n"
                            "      local current = __legacy_state[key]\n"
                            "      if type(current) ~= 'table' then\n"
                            "        current = {}\n"
                            "      end\n"
                            "      table.insert(current, value)\n"
                            "      __legacy_state[key] = current\n"
                            "      return current\n"
                            "    end,\n"
                            "    all = function()\n"
                            "      return __legacy_state\n"
                            "    end\n"
                            "  }\n"
                            "end\n"
                        )

                    if 'Stage.' in lua_source and 'Stage = ' not in lua_source:
                        shim_parts.append(
                            "if Stage == nil then\n"
                            "  local __stage_value = nil\n"
                            "  Stage = {\n"
                            "    set = function(value)\n"
                            "      __stage_value = value\n"
                            "      if State ~= nil and State.set ~= nil then\n"
                            "        State.set(\"stage\", value)\n"
                            "      end\n"
                            "      return value\n"
                            "    end,\n"
                            "    get = function()\n"
                            "      return __stage_value\n"
                            "    end\n"
                            "  }\n"
                            "end\n"
                        )

                    agents = parsed_source.get('agents')
                    if isinstance(agents, dict):
                        alias_lines = []
                        for agent_name in agents.keys():
                            if not isinstance(agent_name, str) or not agent_name:
                                continue
                            alias = ''.join(part.capitalize() for part in agent_name.split('_'))
                            if not alias:
                                continue
                            alias_lines.append(
                                f"if {alias} == nil then "
                                f"if {agent_name} ~= nil then {alias} = {agent_name} "
                                f"elseif Agent ~= nil then {alias} = Agent('{agent_name}') end end"
                            )
                        if alias_lines:
                            shim_parts.append('\n'.join(alias_lines) + '\n')

                    if shim_parts:
                        parsed_source = dict(parsed_source)
                        parsed_source['procedure'] = '\n'.join(shim_parts) + '\n' + lua_source
                        procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)
                        logger.info("Adapted Tactus config: added legacy Lua compatibility shims")

                if (
                    isinstance(lua_source, str)
                    and 'Specification(' in lua_source
                    and 'function Specification' not in lua_source
                ):
                    # No-op: condition retained for compatibility with previous log messages.
                    procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)
                    logger.info("Adapted Tactus config: added legacy Specification/field compatibility shims")

            # Backward compatibility: older procedures ended with:
            #   Procedure { ..., function(input) return run(input) end }
            # In current Tactus runtime, `Procedure(...)` is a lookup primitive, not a declarative
            # wrapper, so executing this block raises "Named procedure '<Lua table ...>' not found".
            # Rewrite to direct legacy execution entrypoint.
            if isinstance(parsed_source, dict):
                legacy_input = _extract_legacy_input_from_params(parsed_source)
                if legacy_input:
                    if isinstance(context, dict):
                        context = {**legacy_input, **context}
                    elif context is None:
                        context = legacy_input

                lua_source = parsed_source.get('procedure')
                if (
                    isinstance(lua_source, str)
                    and 'Procedure {' in lua_source
                    and 'return run(' in lua_source
                ):
                    block_start = lua_source.rfind('Procedure {')
                    if block_start > -1:
                        legacy_defaults_lua = _lua_table_literal(legacy_input)
                        normalized_lua = (
                            lua_source[:block_start].rstrip()
                            + "\n\nlocal __legacy_defaults = "
                            + legacy_defaults_lua
                            + "\nlocal __legacy_input = {}\n"
                            + "for k, v in pairs(__legacy_defaults) do\n"
                            + "  __legacy_input[k] = v\n"
                            + "end\n"
                            + "if type(input) == 'table' then\n"
                            + "  for k, v in pairs(input) do\n"
                            + "    __legacy_input[k] = v\n"
                            + "  end\n"
                            + "end\n"
                            + "return run(__legacy_input)\n"
                        )
                        parsed_source = dict(parsed_source)
                        parsed_source['procedure'] = normalized_lua
                        procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)
                        logger.info(
                            "Adapted Tactus config: replaced legacy Procedure block with direct run(input)"
                        )
        except Exception:  # noqa: BLE001
            # Let runtime report parse errors with full context if adaptation fails.
            pass

        # Get OpenAI API key from options or environment (not logged — passed to API client only)
        _api_key = options.get('openai_api_key')

        if not _api_key:
            from plexus.config.loader import load_config
            load_config()
            import os
            _api_key = os.getenv('OPENAI_API_KEY')

        # Create Plexus adapters
        storage = PlexusStorageAdapter(client, procedure_id)
        chat_recorder = ProcedureChatRecorder(client, procedure_id)
        hitl = PlexusHITLAdapter(client, procedure_id, chat_recorder, storage)
        trace_sink = PlexusTraceSink(chat_recorder)
        log_bridge = _PlexusTraceLogBridge(trace_sink)

        # Create Tactus runtime with Plexus adapters.
        # Support both newer and older runtime signatures.
        _runtime_param_names: list = [
            "procedure_id", "storage_backend", "hitl_handler", "chat_recorder",
            "trace_sink", "log_handler", "mcp_server", "openai_api_key",
        ]
        runtime_kwargs: Dict[str, Any] = {
            "procedure_id": procedure_id,
            "storage_backend": storage,
            "hitl_handler": hitl,
            "chat_recorder": chat_recorder,
            "trace_sink": trace_sink,
            "log_handler": log_bridge,
            "mcp_server": mcp_server,
            "openai_api_key": _api_key,
        }
        supports_chat_recorder = True
        try:
            runtime_sig = inspect.signature(TactusRuntime.__init__)
            accepts_var_kwargs = any(
                param.kind == inspect.Parameter.VAR_KEYWORD
                for param in runtime_sig.parameters.values()
            )
            if not accepts_var_kwargs:
                supported_params = {
                    name
                    for name in runtime_sig.parameters.keys()
                    if name != "self"
                }
                supports_chat_recorder = "chat_recorder" in supported_params
                # Use the static param names list (not runtime_kwargs) to avoid
                # taint-analysis false positives on logged key names.
                dropped = sorted(k for k in _runtime_param_names if k not in supported_params)
                if dropped:
                    logger.info(
                        "TactusRuntime.__init__ does not accept %s; continuing without them",
                        ", ".join(dropped),
                    )
                runtime_kwargs = {
                    key: value
                    for key, value in runtime_kwargs.items()
                    if key in supported_params
                }
        except Exception as sig_error:
            logger.debug(
                "Could not inspect TactusRuntime signature (%s); using default runtime kwargs",
                sig_error,
            )

        runtime = TactusRuntime(**runtime_kwargs)

        # Ensure DSPy agents can stream even when runtime constructor does not expose log_handler.
        if getattr(runtime, "log_handler", None) is None:
            runtime.log_handler = log_bridge

        # Bridge legacy in-process MCP server to Tactus toolset registry.
        # Newer Tactus versions resolve agent tools through named toolsets.
        mcp_client_for_bridge = None
        if mcp_server and hasattr(mcp_server, "list_tools") and hasattr(mcp_server, "call_tool"):
            mcp_client_for_bridge = mcp_server
        elif mcp_server and hasattr(mcp_server, "transport"):
            try:
                from .mcp_transport import ProcedureMCPClient
                # Embedded transport must be initialized before any tool calls.
                transport = mcp_server.transport
                if hasattr(transport, "initialize") and not getattr(transport, "connected", False):
                    await transport.initialize({"name": "Tactus Procedure Runtime", "version": "1.0.0"})
                mcp_client_for_bridge = ProcedureMCPClient(mcp_server.transport)
            except Exception:
                mcp_client_for_bridge = None

        if mcp_client_for_bridge:
            try:
                from tactus.adapters.mcp import PydanticAIMCPAdapter
                from pydantic_ai.toolsets import FunctionToolset

                mcp_adapter = PydanticAIMCPAdapter(
                    mcp_client_for_bridge, tool_primitive=runtime.tool_primitive
                )
                mcp_tools = await mcp_adapter.load_tools()
                if mcp_tools and "plexus" not in runtime.toolset_registry:
                    runtime.toolset_registry["plexus"] = FunctionToolset(tools=mcp_tools)
                    logger.info(
                        "Registered bridged MCP toolset 'plexus' with %d tool(s)",
                        len(mcp_tools),
                    )
            except Exception as exc:
                logger.warning("Could not bridge MCP tools into Tactus toolset registry: %s", exc)

        # Compatibility patch: newer DSPy ToolCall objects are attribute-based,
        # while current Tactus agent code indexes them like dictionaries.
        try:
            from dspy.adapters.types.tool import ToolCalls

            dspy_tool_call_cls = getattr(ToolCalls, "ToolCall", None)
            if dspy_tool_call_cls and not hasattr(dspy_tool_call_cls, "__getitem__"):
                def _tool_call_getitem(self, key):
                    if key == "name":
                        return getattr(self, "name", None)
                    if key == "args":
                        return getattr(self, "args", None)
                    if hasattr(self, key):
                        return getattr(self, key)
                    raise KeyError(key)

                dspy_tool_call_cls.__getitem__ = _tool_call_getitem
                logger.info("Patched DSPy ToolCalls.ToolCall for dict-style compatibility")
        except Exception as exc:
            logger.warning("Could not patch DSPy ToolCall compatibility: %s", exc)

        # Hydrate console-trigger text into runtime context so procedures can access
        # the exact user prompt even when runtime message history is empty.
        runtime_context: Any = context
        if isinstance(context, dict):
            runtime_context = dict(context)
        elif context is None:
            runtime_context = {}

        if isinstance(runtime_context, dict):
            runtime_account_id = runtime_context.get("account_id") or runtime_context.get("accountId")
            if runtime_account_id:
                try:
                    chat_recorder.account_id = str(runtime_account_id)
                except Exception:  # noqa: BLE001
                    pass  # account_id is best-effort; proceed without it

            get_console_trigger_message = getattr(chat_recorder, "get_latest_console_trigger_message", None)
            console_trigger_message = (
                get_console_trigger_message()
                if callable(get_console_trigger_message)
                else None
            )
            if (
                isinstance(console_trigger_message, str)
                and console_trigger_message.strip()
                and not runtime_context.get("console_user_message")
            ):
                runtime_context["console_user_message"] = console_trigger_message.strip()

            get_console_session_history = getattr(chat_recorder, "get_console_session_history", None)
            console_session_history = (
                get_console_session_history()
                if callable(get_console_session_history)
                else None
            )
            if (
                isinstance(console_session_history, list)
                and console_session_history
                and not runtime_context.get("console_session_history")
            ):
                runtime_context["console_session_history"] = console_session_history

        mark_runtime_execute_started = getattr(trace_sink, "mark_runtime_execute_started", None)
        if callable(mark_runtime_execute_started):
            mark_runtime_execute_started()

        # Execute the full Tactus YAML source so params/agents/stages are preserved.
        result = await runtime.execute(procedure_source, runtime_context, format="yaml")
        if log_bridge:
            await log_bridge.flush()

        # Ensure Console receives a meaningful assistant message from procedure output.
        # Some runtime/trace combinations emit only placeholder completion events.
        if supports_chat_recorder and isinstance(result, dict):
            assistant_text = _extract_assistant_text(result)
            if assistant_text:
                trace_messages = getattr(trace_sink, "assistant_message_texts", [])
                has_meaningful_trace_assistant = any(
                    isinstance(message, str) and message.strip()
                    for message in trace_messages
                )
                if not has_meaningful_trace_assistant:
                    await chat_recorder.record_assistant_message(assistant_text)

        if log_bridge:
            try:
                await log_bridge.close()
            except Exception as close_error:
                logger.warning("Failed closing trace log bridge after success: %s", close_error)

        logger.info(f"Tactus execution complete: {result.get('success')}")
        return result

    except Exception as e:
        if log_bridge:
            try:
                await log_bridge.flush()
            except Exception as flush_error:
                logger.warning("Failed flushing trace log bridge after error: %s", flush_error)
            try:
                await log_bridge.close()
            except Exception as close_error:
                logger.warning("Failed closing trace log bridge after error: %s", close_error)
        logger.error(f"Tactus execution error: {e}", exc_info=True)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': f"Tactus execution error: {e}"
        }


async def _execute_sop_agent(
    procedure_id: str,
    procedure_code: str,
    client,
    mcp_server,
    context: Optional[Dict[str, Any]],
    **options
) -> Dict[str, Any]:
    """
    Execute procedure using existing SOP agent system (legacy).

    Args:
        procedure_id: Procedure ID
        procedure_code: YAML configuration (legacy format)
        client: PlexusDashboardClient
        mcp_server: MCP server
        context: Optional context
        **options: Additional options

    Returns:
        Execution results
    """
    logger.info(f"Executing procedure {procedure_id} with SOP Agent system")

    try:
        from .procedure_sop_agent import run_sop_guided_procedure

        # Get OpenAI API key (not logged — passed directly to API client only)
        _sop_api_key = options.get('openai_api_key')

        # Execute with SOP agent
        result = await run_sop_guided_procedure(
            procedure_id=procedure_id,
            experiment_yaml=procedure_code,
            mcp_server=mcp_server,
            openai_api_key=_sop_api_key,
            experiment_context=context,
            client=client,
            model_config=options.get('model_config')
        )

        logger.info(f"SOP Agent execution complete: {result.get('success')}")
        return result

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"SOP Agent execution error ({error_type})", exc_info=False)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': f"SOP Agent execution error: {error_type}"
        }
