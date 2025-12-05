"""
Lua DSL Runtime - Main execution engine for Lua-based procedures.

Orchestrates:
1. YAML parsing and validation
2. Lua sandbox setup
3. Primitive injection
4. Agent configuration with LLMs and tools
5. Workflow execution
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List

from .yaml_parser import ProcedureYAMLParser, ProcedureConfigError
from .lua_sandbox import LuaSandbox, LuaSandboxError
from .output_validator import OutputValidator, OutputValidationError
from .primitives import (
    StatePrimitive,
    IterationsPrimitive,
    StopPrimitive,
    ToolPrimitive,
    AgentPrimitive,
    GraphNodePrimitive,
    HumanPrimitive,
    SystemPrimitive
)

logger = logging.getLogger(__name__)


class LuaDSLRuntimeError(Exception):
    """Raised when Lua DSL runtime encounters an error."""
    pass


class LuaDSLRuntime:
    """
    Main execution engine for Lua-based procedure workflows.

    Responsibilities:
    - Parse and validate YAML configuration
    - Setup sandboxed Lua environment
    - Create and inject primitives
    - Configure agents with LLMs and tools
    - Execute Lua workflow code
    - Return results
    """

    def __init__(self, procedure_id: str, client, mcp_server, openai_api_key: Optional[str] = None):
        """
        Initialize the Lua DSL runtime.

        Args:
            procedure_id: Unique procedure identifier
            client: PlexusDashboardClient instance
            mcp_server: MCP server providing tools
            openai_api_key: Optional OpenAI API key for LLMs
        """
        self.procedure_id = procedure_id
        self.client = client
        self.mcp_server = mcp_server
        self.openai_api_key = openai_api_key
        self.account_id: Optional[str] = None

        # Will be initialized during setup
        self.config: Optional[Dict[str, Any]] = None
        self.lua_sandbox: Optional[LuaSandbox] = None
        self.output_validator: Optional[OutputValidator] = None

        # Primitives (shared across all agents)
        self.state_primitive: Optional[StatePrimitive] = None
        self.iterations_primitive: Optional[IterationsPrimitive] = None
        self.stop_primitive: Optional[StopPrimitive] = None
        self.tool_primitive: Optional[ToolPrimitive] = None
        self.graph_primitive: Optional[GraphNodePrimitive] = None
        self.human_primitive: Optional[HumanPrimitive] = None
        self.system_primitive: Optional[SystemPrimitive] = None

        # Agent primitives (one per agent)
        self.agents: Dict[str, AgentPrimitive] = {}

        logger.info(f"LuaDSLRuntime initialized for procedure {procedure_id}")

    async def execute(self, yaml_config: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a Lua-based procedure workflow.

        Args:
            yaml_config: YAML configuration string
            context: Optional context dict with pre-loaded data

        Returns:
            Execution results dict with:
                - success: bool
                - result: Any (return value from Lua workflow)
                - state: Final state
                - iterations: Number of iterations
                - tools_used: List of tool names called
                - error: Error message if failed

        Raises:
            LuaDSLRuntimeError: If execution fails
        """
        chat_recorder = None

        try:
            # 1. Parse YAML configuration
            logger.info("Step 1: Parsing YAML configuration")
            self.config = ProcedureYAMLParser.parse(yaml_config)
            logger.info(f"Loaded procedure: {self.config['name']} v{self.config['version']}")

            # 2. Get procedure to extract account_id
            logger.info("Step 2: Fetching procedure for account_id")
            from plexus.dashboard.api.models.procedure import Procedure
            procedure = Procedure.get_by_id(self.procedure_id, self.client)
            self.account_id = procedure.accountId
            logger.info(f"Account ID: {self.account_id}")

            # 3. Setup output validator
            logger.info("Step 3: Setting up output validator")
            output_schema = self.config.get('outputs', {})
            self.output_validator = OutputValidator(output_schema)
            if output_schema:
                logger.info(f"Output schema has {len(output_schema)} fields: {list(output_schema.keys())}")

            # 4. Setup Lua sandbox
            logger.info("Step 4: Setting up Lua sandbox")
            self.lua_sandbox = LuaSandbox()

            # 5. Initialize primitives
            logger.info("Step 5: Initializing primitives")
            await self._initialize_primitives()

            # 6. Start chat session for recording
            logger.info("Step 6: Starting chat session")
            from plexus.cli.procedure.chat_recorder import ProcedureChatRecorder
            chat_recorder = ProcedureChatRecorder(self.client, self.procedure_id)
            session_id = await chat_recorder.start_session(context)

            if session_id:
                logger.info(f"Chat session started: {session_id}")
            else:
                logger.warning("Failed to create chat session - continuing without recording")

            # 7. Initialize HITL primitives (require chat_recorder)
            logger.info("Step 7: Initializing HITL primitives")
            hitl_config = self.config.get('hitl', {})
            self.human_primitive = HumanPrimitive(chat_recorder, hitl_config)
            self.system_primitive = SystemPrimitive(chat_recorder)
            logger.debug("HITL primitives initialized")

            # 8. Setup agents with LLMs and tools
            logger.info("Step 8: Setting up agents")
            await self._setup_agents(context or {}, chat_recorder)

            # 9. Inject primitives into Lua
            logger.info("Step 9: Injecting primitives into Lua environment")
            self._inject_primitives()

            # 10. Execute workflow
            logger.info("Step 10: Executing Lua workflow")
            workflow_result = self._execute_workflow()

            # 11. Validate workflow output
            logger.info("Step 11: Validating workflow output")
            try:
                validated_result = self.output_validator.validate(workflow_result)
                logger.info("✓ Output validation passed")
            except OutputValidationError as e:
                logger.error(f"Output validation failed: {e}")
                # Still continue but mark as validation failure
                validated_result = workflow_result

            # 12. Flush all queued chat recordings
            logger.info("Step 12: Flushing chat recordings")

            # Flush agent messages
            for agent_name, agent_primitive in self.agents.items():
                await agent_primitive.flush_recordings()

            # Flush HITL primitive messages
            if self.human_primitive:
                await self.human_primitive.flush_recordings()
            if self.system_primitive:
                await self.system_primitive.flush_recordings()

            # 13. End chat session
            if chat_recorder and chat_recorder.session_id:
                await chat_recorder.end_session(status='COMPLETED')

            # 14. Build final results
            final_state = self.state_primitive.all()
            tools_used = [call.name for call in self.tool_primitive.get_all_calls()]

            logger.info(
                f"Workflow execution complete: "
                f"{self.iterations_primitive.current()} iterations, "
                f"{len(tools_used)} tool calls"
            )

            return {
                'success': True,
                'procedure_id': self.procedure_id,
                'result': validated_result,
                'state': final_state,
                'iterations': self.iterations_primitive.current(),
                'tools_used': tools_used,
                'stop_requested': self.stop_primitive.requested(),
                'stop_reason': self.stop_primitive.reason(),
                'session_id': session_id if chat_recorder else None
            }

        except ProcedureConfigError as e:
            logger.error(f"Configuration error: {e}")
            # Flush recordings even on error
            if self.agents:
                for agent_primitive in self.agents.values():
                    try:
                        await agent_primitive.flush_recordings()
                    except:
                        pass
            if self.human_primitive:
                try:
                    await self.human_primitive.flush_recordings()
                except:
                    pass
            if self.system_primitive:
                try:
                    await self.system_primitive.flush_recordings()
                except:
                    pass
            if chat_recorder and chat_recorder.session_id:
                try:
                    await chat_recorder.end_session(status='COMPLETED')
                except Exception as e:
                    logger.warning(f"Failed to end chat session: {e}")

            return {
                'success': False,
                'procedure_id': self.procedure_id,
                'error': f"Configuration error: {e}"
            }

        except LuaSandboxError as e:
            logger.error(f"Lua execution error: {e}")
            # Flush recordings even on error
            if self.agents:
                for agent_primitive in self.agents.values():
                    try:
                        await agent_primitive.flush_recordings()
                    except:
                        pass
            if self.human_primitive:
                try:
                    await self.human_primitive.flush_recordings()
                except:
                    pass
            if self.system_primitive:
                try:
                    await self.system_primitive.flush_recordings()
                except:
                    pass
            if chat_recorder and chat_recorder.session_id:
                try:
                    await chat_recorder.end_session(status='COMPLETED')
                except Exception as e:
                    logger.warning(f"Failed to end chat session: {e}")

            return {
                'success': False,
                'procedure_id': self.procedure_id,
                'error': f"Lua execution error: {e}"
            }

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            # Flush recordings even on error
            if self.agents:
                for agent_primitive in self.agents.values():
                    try:
                        await agent_primitive.flush_recordings()
                    except:
                        pass
            if self.human_primitive:
                try:
                    await self.human_primitive.flush_recordings()
                except:
                    pass
            if self.system_primitive:
                try:
                    await self.system_primitive.flush_recordings()
                except:
                    pass
            if chat_recorder and chat_recorder.session_id:
                try:
                    await chat_recorder.end_session(status='COMPLETED')
                except Exception as e:
                    logger.warning(f"Failed to end chat session: {e}")

            return {
                'success': False,
                'procedure_id': self.procedure_id,
                'error': f"Unexpected error: {e}"
            }

    async def _initialize_primitives(self):
        """Initialize all primitive objects."""
        self.state_primitive = StatePrimitive()
        self.iterations_primitive = IterationsPrimitive()
        self.stop_primitive = StopPrimitive()
        self.tool_primitive = ToolPrimitive()
        self.graph_primitive = GraphNodePrimitive(
            client=self.client,
            procedure_id=self.procedure_id,
            account_id=self.account_id
        )

        logger.debug("All primitives initialized")

    async def _setup_agents(self, context: Dict[str, Any], chat_recorder=None):
        """
        Setup agent primitives with LLMs and tools.

        Args:
            context: Procedure context with pre-loaded data
            chat_recorder: Optional ProcedureChatRecorder for logging conversations
        """
        # Get OpenAI API key
        if not self.openai_api_key:
            from plexus.config.loader import load_config
            load_config()
            import os
            self.openai_api_key = os.getenv('OPENAI_API_KEY')

        if not self.openai_api_key:
            raise LuaDSLRuntimeError("OpenAI API key not available")

        # Get agent configurations
        agents_config = self.config.get('agents', {})

        if not agents_config:
            raise LuaDSLRuntimeError("No agents defined in configuration")

        # Connect to MCP server and get tools
        async with self.mcp_server.connect({'name': f'LuaDSL Runtime for {self.procedure_id}'}) as mcp_client:
            from plexus.cli.procedure.mcp_adapter import LangChainMCPAdapter, convert_mcp_tools_to_langchain

            adapter = LangChainMCPAdapter(mcp_client)
            all_mcp_tools = await adapter.load_tools()

            logger.info(f"Loaded {len(all_mcp_tools)} MCP tools")

            # Setup each agent
            for agent_name, agent_config in agents_config.items():
                logger.info(f"Setting up agent: {agent_name}")

                # Get agent prompts (with template substitution)
                system_prompt = self._process_template(agent_config['system_prompt'], context)
                initial_message = self._process_template(agent_config['initial_message'], context)

                # Inject output schema into system prompt if defined
                if self.config.get('outputs'):
                    output_guidance = self._format_output_schema_for_prompt()
                    system_prompt = f"{system_prompt}\n\n{output_guidance}"
                    logger.info(f"Injected output schema guidance into agent '{agent_name}' prompt")

                # Filter tools for this agent
                allowed_tool_names = agent_config.get('tools', [])
                filtered_tools = [tool for tool in all_mcp_tools if tool.name in allowed_tool_names]

                logger.info(f"Agent '{agent_name}' has {len(filtered_tools)} tools: {allowed_tool_names}")

                # Convert to LangChain format
                langchain_tools = convert_mcp_tools_to_langchain(filtered_tools)

                # Add "done" tool for stopping
                from langchain_core.tools import tool

                @tool
                def done(reason: str, success: bool = True) -> str:
                    """Signal completion of the task.

                    Args:
                        reason: Brief explanation of completion
                        success: True if completed successfully

                    Returns:
                        Acknowledgment message
                    """
                    return f"Done: {reason} (success: {success})"

                langchain_tools.append(done)

                # Create LLM with tools
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="gpt-4o",
                    temperature=0.7,
                    openai_api_key=self.openai_api_key
                )

                llm_with_tools = llm.bind_tools(langchain_tools)

                # Create AgentPrimitive
                agent_primitive = AgentPrimitive(
                    name=agent_name,
                    system_prompt=system_prompt,
                    initial_message=initial_message,
                    llm=llm_with_tools,
                    available_tools=filtered_tools + [done],  # Include MCP tools + done tool
                    tool_primitive=self.tool_primitive,
                    stop_primitive=self.stop_primitive,
                    iterations_primitive=self.iterations_primitive,
                    chat_recorder=chat_recorder
                )

                self.agents[agent_name] = agent_primitive

                logger.info(f"Agent '{agent_name}' configured successfully")

    def _inject_primitives(self):
        """Inject all primitives into Lua global scope."""
        # Inject shared primitives
        self.lua_sandbox.inject_primitive("State", self.state_primitive)
        self.lua_sandbox.inject_primitive("Iterations", self.iterations_primitive)
        self.lua_sandbox.inject_primitive("Stop", self.stop_primitive)
        self.lua_sandbox.inject_primitive("Tool", self.tool_primitive)
        self.lua_sandbox.inject_primitive("GraphNode", self.graph_primitive)

        # Debug HITL primitives
        logger.info(f"Injecting Human primitive: {self.human_primitive}")
        logger.info(f"  Human.approve: {self.human_primitive.approve if self.human_primitive else 'None'}")
        self.lua_sandbox.inject_primitive("Human", self.human_primitive)

        logger.info(f"Injecting System primitive: {self.system_primitive}")
        self.lua_sandbox.inject_primitive("System", self.system_primitive)

        # Inject agent primitives (capitalized names)
        for agent_name, agent_primitive in self.agents.items():
            # Capitalize first letter for Lua convention (Worker, Assistant, etc.)
            lua_name = agent_name.capitalize()
            self.lua_sandbox.inject_primitive(lua_name, agent_primitive)
            logger.info(f"Injected agent primitive: {lua_name}")

        logger.debug("All primitives injected into Lua sandbox")

    def _execute_workflow(self) -> Any:
        """
        Execute the Lua workflow code.

        Returns:
            Result from Lua workflow execution
        """
        workflow_code = self.config['workflow']

        logger.debug(f"Executing workflow code ({len(workflow_code)} bytes)")

        try:
            result = self.lua_sandbox.execute(workflow_code)
            logger.info("Workflow execution completed successfully")
            return result

        except LuaSandboxError as e:
            logger.error(f"Workflow execution failed: {e}")
            raise

    def _process_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        Process a template string with variable substitution.

        Args:
            template: Template string with {variable} placeholders
            context: Context dict with variable values

        Returns:
            Processed string with variables substituted
        """
        try:
            # Build template variables from context (supports dot notation)
            from string import Formatter

            class DotFormatter(Formatter):
                def get_field(self, field_name, args, kwargs):
                    # Support dot notation like {params.topic}
                    parts = field_name.split('.')
                    obj = kwargs
                    for part in parts:
                        if isinstance(obj, dict):
                            obj = obj.get(part, '')
                        else:
                            obj = getattr(obj, part, '')
                    return obj, field_name

            template_vars = {}

            # Add context variables
            if context:
                template_vars.update(context)

            # Add params from config with default values (Plexus standard)
            if 'params' in self.config:
                params = self.config['params']
                param_values = {}
                for param_name, param_def in params.items():
                    if 'default' in param_def:
                        param_values[param_name] = param_def['default']
                template_vars['params'] = param_values

            # Add state (for dynamic templates)
            if self.state_primitive:
                template_vars['state'] = self.state_primitive.all()

            # Use dot-notation formatter
            formatter = DotFormatter()
            result = formatter.format(template, **template_vars)
            return result

        except KeyError as e:
            logger.warning(f"Template variable {e} not found, using template as-is")
            return template

        except Exception as e:
            logger.error(f"Error processing template: {e}")
            return template

    def _format_output_schema_for_prompt(self) -> str:
        """
        Format the output schema as guidance for LLM prompts.

        Returns:
            Formatted string describing expected outputs
        """
        outputs = self.config.get('outputs', {})
        if not outputs:
            return ""

        lines = ["## Expected Output Format", ""]
        lines.append("This workflow must return a structured result with the following fields:")
        lines.append("")

        # Format each output field
        for field_name, field_def in outputs.items():
            field_type = field_def.get('type', 'any')
            is_required = field_def.get('required', False)
            description = field_def.get('description', '')

            req_marker = "**REQUIRED**" if is_required else "*optional*"
            lines.append(f"- **{field_name}** ({field_type}) - {req_marker}")
            if description:
                lines.append(f"  {description}")
            lines.append("")

        lines.append("Note: The workflow orchestration code will extract and format these values from your tool calls and actions.")

        return "\n".join(lines)

    def get_state(self) -> Dict[str, Any]:
        """Get current procedure state."""
        if self.state_primitive:
            return self.state_primitive.all()
        return {}

    def get_iteration_count(self) -> int:
        """Get current iteration count."""
        if self.iterations_primitive:
            return self.iterations_primitive.current()
        return 0

    def is_stopped(self) -> bool:
        """Check if procedure was stopped."""
        if self.stop_primitive:
            return self.stop_primitive.requested()
        return False
