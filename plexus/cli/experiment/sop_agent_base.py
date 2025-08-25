"""
Base StandardOperatingProcedureAgent - General-purpose multi-agent orchestration.

This module provides the core StandardOperatingProcedureAgent that can be used
across different domains. It's decoupled from experiment-specific logic and can
orchestrate any procedure-driven multi-agent workflow.

Key Design Principles:
- Domain-agnostic: Works for experiments, reports, analysis, etc.
- Configurable: Procedures defined through pluggable components
- Reusable: Same agent can handle different types of structured workflows
- Extensible: Easy to add new domains without changing core logic
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
import yaml
from .logging_utils import (
    log_chat_history_for_agent, 
    log_agent_response, 
    log_tool_execution,
    truncate_log_message,
    reduce_debug_noise
)
try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
except ImportError:
    from langchain.schema import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)

# Import for testing purposes - normally imported locally where needed
try:
    from .mcp_adapter import LangChainMCPAdapter
except ImportError:
    # Allow tests to mock this import
    LangChainMCPAdapter = None


@runtime_checkable
class ProcedureDefinition(Protocol):
    """
    Protocol defining how a specific procedure (like experiments) configures the SOP Agent.
    
    This allows different domains to provide their own procedure definitions
    while using the same core SOP Agent orchestration logic.
    """
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        """Get the system prompt for the coding assistant in this procedure."""
        ...
    
    def get_sop_guidance_prompt(self, context: Dict[str, Any], state_data: Dict[str, Any]) -> str:
        """Get the SOP Agent guidance prompt for this procedure."""
        ...
    
    def get_user_prompt(self, context: Dict[str, Any]) -> str:
        """Get the initial user prompt for this procedure."""
        ...
    
    def get_allowed_tools(self, phase: str) -> List[str]:
        """Get the tools allowed in the given phase for this procedure."""
        ...
    
    def should_continue(self, state_data: Dict[str, Any]) -> bool:
        """Determine if the procedure should continue based on current state."""
        ...
    
    def get_completion_summary(self, state_data: Dict[str, Any]) -> str:
        """Get a summary when the procedure is complete."""
        ...


class FlowManager(ABC):
    """
    Abstract flow manager for procedure-specific conversation flow.
    
    Different procedures can implement their own flow logic
    (e.g., experiment phases, report generation steps, etc.)
    """
    
    @abstractmethod
    def update_state(self, tools_used: List[str], response_content: str, **kwargs) -> Dict[str, Any]:
        """Update the flow state based on coding assistant actions."""
        pass
    
    @abstractmethod
    def should_continue(self) -> bool:
        """Determine if the flow should continue."""
        pass
    
    @abstractmethod
    def get_next_guidance(self) -> Optional[str]:
        """Get template guidance for the next step."""
        pass
    
    @abstractmethod
    def get_completion_summary(self) -> str:
        """Get summary when flow is complete."""
        pass


class ChatRecorder(ABC):
    """
    Abstract chat recorder for procedure-specific conversation recording.
    
    Different procedures may record conversations differently
    (e.g., experiment sessions, report generation logs, etc.)
    """
    
    @abstractmethod
    async def start_session(self, context: Dict[str, Any]) -> Optional[str]:
        """Start a recording session for this procedure."""
        pass
    
    @abstractmethod
    async def record_message(self, role: str, content: str, message_type: str) -> Optional[str]:
        """Record a message in the current session."""
        pass
    
    @abstractmethod
    async def record_system_message(self, content: str) -> Optional[str]:
        """Record a system message."""
        pass
    
    @abstractmethod
    async def end_session(self, status: str, name: str = None) -> bool:
        """End the current recording session."""
        pass


class StandardOperatingProcedureAgent:
    """
    General-purpose Standard Operating Procedure Agent for multi-agent orchestration.
    
    This agent can orchestrate any procedure-driven multi-agent workflow by:
    1. Following configurable standard operating procedures
    2. Managing conversation flow through defined phases
    3. Providing contextual guidance to coding assistant agents
    4. Enforcing tool scoping and safety constraints
    5. Recording and reporting procedure execution results
    
    The agent is domain-agnostic and gets its procedure-specific behavior
    through injected ProcedureDefinition, FlowManager, and ChatRecorder components.
    """
    
    def __init__(self, 
                 procedure_id: str,
                 procedure_definition: ProcedureDefinition,
                 mcp_server,
                 flow_manager: Optional[FlowManager] = None,
                 chat_recorder: Optional[ChatRecorder] = None,
                 openai_api_key: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None,
                 model_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the StandardOperatingProcedureAgent.
        
        Args:
            procedure_id: Unique identifier for this procedure execution
            procedure_definition: Defines procedure-specific behavior (prompts, tools, etc.)
            mcp_server: MCP server providing tools to the coding assistant
            flow_manager: Optional flow manager for conversation state
            chat_recorder: Optional recorder for conversation logging
            openai_api_key: Optional OpenAI API key for SOP guidance LLM
            context: Optional procedure context with known information
            model_config: Optional model configuration dict for LLM parameters
        """
        self.procedure_id = procedure_id
        self.procedure_definition = procedure_definition
        self.mcp_server = mcp_server
        self.flow_manager = flow_manager
        self.chat_recorder = chat_recorder
        self.context = context or {}
        self.model_config = model_config or {}
        
        # Initialize model configuration system
        from .model_config import create_configured_llm, ModelConfig, ModelConfigs
        if self.model_config:
            self._model_config_instance = ModelConfig.from_dict(self.model_config)
        else:
            # Try environment configuration first, then fall back to GPT-4 default
            env_config = ModelConfigs.from_environment()
            if env_config.model != "gpt-4o":  # Environment config found
                self._model_config_instance = env_config
                logger.info(f"Using environment-based model configuration: {env_config.model}")
            else:
                self._model_config_instance = None  # Will use defaults
        
        # Reduce debug noise from verbose modules
        reduce_debug_noise()
        
        # Set up OpenAI API key
        self.openai_api_key = openai_api_key
        if not self.openai_api_key:
            from plexus.config.loader import load_config
            load_config()
            import os
            self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        logger.info(f"SOP Agent initialized for procedure {procedure_id}")
        
        # Internal state
        self.procedure_config = None
        self.mcp_adapter = None
    
    async def setup(self, procedure_yaml: str) -> bool:
        """
        Set up the SOP Agent with procedure configuration.
        
        Args:
            procedure_yaml: YAML configuration for this procedure
            
        Returns:
            True if setup successful, False otherwise
        """
        try:
            # Parse procedure YAML
            self.procedure_config = yaml.safe_load(procedure_yaml)
            logger.info(f"Loaded procedure config for {self.procedure_id}")
            
            # Initialize flow manager if provided
            if self.flow_manager:
                # Flow manager may need access to config and context
                if hasattr(self.flow_manager, 'initialize'):
                    self.flow_manager.initialize(self.procedure_config, self.context)
            
            # Set up MCP adapter for tool access
            from .mcp_adapter import LangChainMCPAdapter
            async with self.mcp_server.connect({'name': f'SOP Agent for {self.procedure_id}'}) as mcp_client:
                self.mcp_adapter = LangChainMCPAdapter(mcp_client)
                await self.mcp_adapter.load_tools()
                logger.info(f"Set up MCP adapter with {len(self.mcp_adapter.tools)} tools")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up SOP Agent: {e}")
            return False
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for the coding assistant."""
        return self.procedure_definition.get_system_prompt(self.context)
    
    def get_user_prompt(self) -> str:
        """Get the initial user prompt for the coding assistant."""
        return self.procedure_definition.get_user_prompt(self.context)
    
    async def _generate_sop_guidance(self, conversation_history: List, state_data: Dict[str, Any]) -> str:
        """
        Generate Standard Operating Procedure guidance for the coding assistant.
        
        This is the core SOP Agent responsibility: analyzing conversation state
        and providing structured guidance based on the procedure definition.
        """
        try:
            # Import model configuration system
            from .model_config import create_configured_llm, ModelConfigs
            
            # Create SOP guidance LLM with configuration
            if self._model_config_instance:
                # Use configured model
                manager_config = self._model_config_instance
                # Override API key and set manager-appropriate parameters
                manager_config.openai_api_key = self.openai_api_key
                sop_guidance_llm = manager_config.create_langchain_llm()
            else:
                # Fall back to default manager configuration
                sop_guidance_llm = create_configured_llm(
                    model_config=ModelConfigs.gpt_4o_precise(),
                    openai_api_key=self.openai_api_key
                )
            
            # Get procedure-specific guidance prompt for manager agent
            manager_system_prompt = self.procedure_definition.get_sop_guidance_prompt(self.context, state_data)
            
            # Build filtered conversation for manager agent using ManagerAgentConversationFilter
            filtered_messages = self._build_filtered_conversation_for_manager(conversation_history, manager_system_prompt)
            
            # Log what chat history is being sent to the SOP Agent (Manager)
            log_chat_history_for_agent(
                agent_name="SOP_AGENT (Manager)",
                chat_history=filtered_messages,
                context="for procedural guidance generation"
            )
            
            response = sop_guidance_llm.invoke(filtered_messages)
            
            # Log the manager's response with token usage
            self._log_sop_response_details(response)
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating SOP guidance: {e}")
            # Fallback to flow manager template if available
            if self.flow_manager:
                fallback = self.flow_manager.get_next_guidance()
                logger.info(f"SOP Agent falling back to template guidance")
                return fallback or "Continue with the next step in the procedure."
            return "Continue with the next step in the procedure."
    
    def _build_filtered_conversation_for_manager(self, conversation_history: List, manager_system_prompt: str) -> List:
        """Build a filtered conversation for the manager agent using ManagerAgentConversationFilter."""
        try:
            from .conversation_filter import ManagerAgentConversationFilter
            
            # Use Manager agent conversation filter for proper message list with manager-specific setup
            filter_model = self._model_config_instance.model if self._model_config_instance else "gpt-4o"
            manager_filter = ManagerAgentConversationFilter(model=filter_model)
            filtered_messages = manager_filter.filter_conversation(
                conversation_history, 
                max_tokens=8000,
                manager_system_prompt=manager_system_prompt
            )
            
            return filtered_messages
            
        except Exception as e:
            logger.warning(f"Error using ManagerAgentConversationFilter, falling back to simple message list: {e}")
            # Fallback to simplified message list if filter fails
            try:
                from langchain_core.messages import SystemMessage, HumanMessage
            except ImportError:
                try:
                    from langchain.schema.messages import SystemMessage, HumanMessage
                except ImportError:
                    from langchain.schema import SystemMessage, HumanMessage
            
            fallback_messages = []
            
            # Add manager system prompt
            if manager_system_prompt:
                fallback_messages.append(SystemMessage(content=manager_system_prompt))
            
            # Add simple conversation context
            if conversation_history:
                context_lines = []
                for i, msg in enumerate(conversation_history[-5:]):  # Last 5 messages
                    if hasattr(msg, 'content') and msg.content:
                        msg_type = "System" if isinstance(msg, SystemMessage) else \
                                  ("User" if isinstance(msg, HumanMessage) else "Assistant")
                        content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                        context_lines.append(f"[{i}] {msg_type}: {content_preview}")
                
                context_content = "CONVERSATION CONTEXT:\n" + "\n".join(context_lines)
                fallback_messages.append(SystemMessage(content=context_content))
            
            # Add manager instruction
            manager_instruction = SystemMessage(content="""
You are responding as the MANAGER/ORCHESTRATOR. Analyze the conversation and provide guidance for the next step in the procedure.
Your response will become the next user message to guide the coding assistant.
""")
            fallback_messages.append(manager_instruction)
            
            return fallback_messages
    
    def _log_assistant_response_details(self, ai_response, round_num: int) -> None:
        """
        Log the raw AI model response with complete details.
        
        Args:
            ai_response: The AI response object from LangChain
            round_num: Current round number
        """
        logger.info(f"🤖 CODING_ASSISTANT (Worker): Round {round_num} - RAW AI RESPONSE")
        
        try:
            # Show the complete raw response object structure
            logger.info(f"   Response Type: {type(ai_response)}")
            
            # Content (reasoning/thinking)
            response_content = getattr(ai_response, 'content', '') or ''
            if response_content.strip():
                logger.info(f"   Content: {response_content}")
            else:
                logger.info(f"   Content: [EMPTY]")
            
            # Tool calls
            if hasattr(ai_response, 'tool_calls') and ai_response.tool_calls:
                logger.info(f"   Tool Calls: {len(ai_response.tool_calls)} tools")
                for i, tool_call in enumerate(ai_response.tool_calls):
                    # Handle both dict and object formats
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get('name', 'UNKNOWN')
                        tool_args = tool_call.get('args', {})
                    else:
                        tool_name = getattr(tool_call, 'name', 'UNKNOWN')
                        tool_args = getattr(tool_call, 'args', {})
                    logger.info(f"     [{i+1}] {tool_name}: {tool_args}")
            else:
                logger.info(f"   Tool Calls: None")
            
            # Token usage (try multiple possible locations)
            usage_found = False
            if hasattr(ai_response, 'usage_metadata') and ai_response.usage_metadata:
                usage = ai_response.usage_metadata
                logger.info(f"   Usage Metadata: {usage}")
                usage_found = True
            
            if hasattr(ai_response, 'response_metadata') and ai_response.response_metadata:
                metadata = ai_response.response_metadata
                logger.info(f"   Response Metadata: {metadata}")
                usage_found = True
            
            if not usage_found:
                logger.info(f"   Token Usage: Not available")
            
            # Additional attributes that might contain useful info
            all_attrs = dir(ai_response)
            interesting_attrs = [attr for attr in all_attrs if not attr.startswith('_') and attr not in ['content', 'tool_calls', 'usage_metadata', 'response_metadata']]
            if interesting_attrs:
                logger.info(f"   Other Attributes: {interesting_attrs}")
                for attr in interesting_attrs[:5]:  # Show first 5 to avoid spam
                    try:
                        value = getattr(ai_response, attr)
                        if not callable(value):
                            logger.info(f"     {attr}: {value}")
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"   Error parsing raw response: {e}")
            logger.info(f"   Raw response object: {ai_response}")
    
    def _log_sop_response_details(self, sop_response) -> None:
        """
        Log the raw SOP agent response with complete details.
        
        Args:
            sop_response: The SOP agent response object from LangChain
        """
        logger.info(f"🤖 SOP_AGENT (Manager): RAW AI RESPONSE")
        
        try:
            # Show the complete raw response object structure
            logger.info(f"   Response Type: {type(sop_response)}")
            
            # Content (guidance)
            response_content = getattr(sop_response, 'content', '') or ''
            if response_content.strip():
                logger.info(f"   Content: {response_content}")
            else:
                logger.info(f"   Content: [EMPTY]")
            
            # Token usage (try multiple possible locations)
            usage_found = False
            if hasattr(sop_response, 'usage_metadata') and sop_response.usage_metadata:
                usage = sop_response.usage_metadata
                logger.info(f"   Usage Metadata: {usage}")
                usage_found = True
            
            if hasattr(sop_response, 'response_metadata') and sop_response.response_metadata:
                metadata = sop_response.response_metadata
                logger.info(f"   Response Metadata: {metadata}")
                usage_found = True
            
            if not usage_found:
                logger.info(f"   Token Usage: Not available")
            
            # Additional attributes that might contain useful info
            all_attrs = dir(sop_response)
            interesting_attrs = [attr for attr in all_attrs if not attr.startswith('_') and attr not in ['content', 'usage_metadata', 'response_metadata']]
            if interesting_attrs:
                logger.info(f"   Other Attributes: {interesting_attrs}")
                for attr in interesting_attrs[:5]:  # Show first 5 to avoid spam
                    try:
                        value = getattr(sop_response, attr)
                        if not callable(value):
                            logger.info(f"     {attr}: {value}")
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"   Error parsing raw response: {e}")
            logger.info(f"   Raw response object: {sop_response}")
    
    async def execute_procedure(self) -> Dict[str, Any]:
        """
        Execute the SOP-guided procedure with coding assistant.
        
        This is the main execution method that orchestrates the multi-agent ReAct loop:
        1. SOP Agent provides procedural guidance
        2. Coding Assistant executes tools based on guidance
        3. SOP Agent evaluates progress and provides next guidance
        4. Loop continues until procedure completion criteria met
        
        Returns:
            Dictionary with execution results
        """
        try:
            # Initialize chat recording
            session_id = None
            if self.chat_recorder:
                logger.info(f"Starting procedure recording session for {self.procedure_id}")
                session_id = await self.chat_recorder.start_session(self.context)
            
            # Check for API key
            if not self.openai_api_key:
                error_msg = "OpenAI API key not available"
                if self.chat_recorder:
                    await self.chat_recorder.record_system_message(f"Error: {error_msg}")
                    await self.chat_recorder.end_session('ERROR', name="Setup Error - Missing API Key")
                return {
                    "success": False, 
                    "error": error_msg,
                    "suggestion": "Please set OPENAI_API_KEY environment variable or pass openai_api_key parameter"
                }
            
            # Set up coding assistant with scoped tools using model configuration
            from .model_config import create_configured_llm, ModelConfigs
            
            if self._model_config_instance:
                # Use configured model for coding assistant
                worker_config = self._model_config_instance
                worker_config.openai_api_key = self.openai_api_key
                coding_assistant_llm = worker_config.create_langchain_llm()
            else:
                # Fall back to default worker configuration
                coding_assistant_llm = create_configured_llm(
                    model_config=ModelConfigs.gpt_4o_default(),
                    openai_api_key=self.openai_api_key
                )
            
            # Get procedure-specific tools
            async with self.mcp_server.connect({'name': f'Coding Assistant for {self.procedure_id}'}) as mcp_client:
                from .mcp_adapter import LangChainMCPAdapter
                adapter = LangChainMCPAdapter(mcp_client)
                all_tools = await adapter.load_tools()
                
                # Filter tools to only include allowed ones
                allowed_tool_names = self.procedure_definition.get_allowed_tools()
                filtered_tools = []
                for tool in all_tools:
                    if tool.name in allowed_tool_names:
                        filtered_tools.append(tool)
                
                logger.info(f"Worker agent has access to {len(filtered_tools)}/{len(all_tools)} tools: {[t.name for t in filtered_tools]}")
                
                # Convert to LangChain format and bind to LLM
                from .mcp_adapter import convert_mcp_tools_to_langchain
                langchain_tools = convert_mcp_tools_to_langchain(filtered_tools)
                
                # Add custom stop_procedure tool
                from langchain_core.tools import tool
                
                @tool
                def stop_procedure(reason: str, success: bool = True) -> str:
                    """Signal completion of the procedure with a reason.
                    
                    Args:
                        reason: Brief explanation of why you're stopping
                        success: True if task completed successfully, False if stopped due to issues
                    
                    Returns:
                        Acknowledgment message
                    """
                    return f"Stop request acknowledged: {reason} (success: {success})"
                
                langchain_tools.append(stop_procedure)
                llm_with_tools = coding_assistant_llm.bind_tools(langchain_tools)
                
                # Store filtered tools for later tool execution
                available_mcp_tools = filtered_tools
                
                # Get initial prompts
                system_prompt = self.get_system_prompt()
                user_prompt = self.get_user_prompt()
                
                # Record initial prompts
                if self.chat_recorder:
                    await self.chat_recorder.record_system_message(system_prompt)
                    await self.chat_recorder.record_message('USER', user_prompt, 'MESSAGE')
                
                # Initialize conversation
                conversation_history = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ]
                
                # Execute the ReAct loop
                round_num = 0
                safety_limit = 50
                results = {"tools_used": [], "phases_completed": [], "artifacts_created": 0}
                
                logger.info(f"🚀 Starting SOP-guided procedure execution: {self.procedure_id}")
                
                while round_num < safety_limit:
                    round_num += 1
                    
                    # Check if worker requested to stop
                    if results.get("stop_requested", False):
                        logger.info(f"🛑 Worker agent requested stop: {results.get('stop_reason', 'No reason provided')}")
                        break
                    
                    # Check if procedure should continue
                    state_data = self._get_current_state(results, round_num)
                    logger.info(f"🔍 CALLING should_continue on {type(self.procedure_definition).__name__}")
                    should_continue = self.procedure_definition.should_continue(state_data)
                    
                    if not should_continue:
                        logger.warning(f"🛑 STOPPING CONDITION TRIGGERED: Procedure definition returned should_continue=False")
                        logger.warning(f"🔍 STOP REASON: Round {round_num}, State data: {state_data}")
                        logger.info(f"🏁 Procedure complete - {self.procedure_definition.get_completion_summary(state_data)}")
                        break
                    
                    # Coding assistant response
                    try:
                        # Apply worker agent conversation filtering for the coding assistant
                        from .conversation_filter import WorkerAgentConversationFilter
                        # Using appropriate token limit based on configured model
                        filter_model = self._model_config_instance.model if self._model_config_instance else "gpt-4o"
                        conversation_filter = WorkerAgentConversationFilter(model=filter_model)
                        filtered_history = conversation_filter.filter_conversation(conversation_history, max_tokens=120000)
                        
                        # Worker agent has access to all tools at all times
                        
                        # Worker agent should NOT see any explanation messages about SOP agent role
                        # The worker just receives guidance messages directly
                        
                        # Log what chat history is being sent to the Coding Assistant (Worker)
                        log_chat_history_for_agent(
                            agent_name="CODING_ASSISTANT (Worker)",
                            chat_history=filtered_history,
                            context=f"round {round_num}"
                        )
                        
                        # Check if we need to force explanation (remove tools temporarily)
                        if results.get("force_explanation_next", False):
                            logger.info("🚨 FORCING EXPLANATION: Removing tools temporarily to require text response")
                            # Use LLM without tools to force explanation
                            ai_response = coding_assistant_llm.invoke(filtered_history)
                            # Clear the flag after use
                            results["force_explanation_next"] = False
                        else:
                            ai_response = llm_with_tools.invoke(filtered_history)
                        
                        # Log detailed assistant response information
                        self._log_assistant_response_details(ai_response, round_num)
                        
                        # Handle tool calls or regular responses
                        if hasattr(ai_response, 'tool_calls') and ai_response.tool_calls:
                            # Process tool calls
                            conversation_history.append(ai_response)
                            
                            # CRITICAL: Only process the FIRST tool call, then force model to explain before next tool
                            # This prevents tool call chaining without explanation
                            if len(ai_response.tool_calls) > 1:
                                logger.warning(f"🚨 MODEL ATTEMPTED {len(ai_response.tool_calls)} TOOL CALLS - Processing only the first one to enforce explanation requirement")
                            
                            tool_call = ai_response.tool_calls[0]  # Only process first tool call
                            
                            # Debug the tool_call structure
                            logger.info(f"🔧 RAW_TOOL_CALL: {tool_call}")
                            logger.info(f"🔧 TOOL_CALL_TYPE: {type(tool_call)}")
                            logger.info(f"🔧 TOOL_CALL_ATTRS: {dir(tool_call)}")
                            
                            # LangChain tool calls are objects, not dicts
                            tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                            tool_args = tool_call.get('args') if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
                            tool_call_id = tool_call.get('id') if isinstance(tool_call, dict) else getattr(tool_call, 'id', None)
                            
                            # Record tool call BEFORE execution
                            tool_call_message_id = None
                            if self.chat_recorder:
                                tool_call_message_id = await self.chat_recorder.record_message(
                                    role='ASSISTANT',
                                    content=f"Calling tool: {tool_name}",
                                    message_type='TOOL_CALL',
                                    tool_name=tool_name,
                                    tool_parameters=tool_args
                                )
                                
                                # Store in MCP adapter's pending_tool_calls for response linking
                                if hasattr(self.mcp_adapter, 'pending_tool_calls'):
                                    self.mcp_adapter.pending_tool_calls[tool_name] = tool_call_message_id
                            
                            # Execute tool
                            import time
                            start_time = time.time()
                            tool_result = None
                            
                            # Handle custom SOP agent tools first
                            if tool_name == "stop_procedure":
                                tool_result = self._handle_stop_procedure(tool_args)
                                results["tools_used"].append(tool_name)
                                results["stop_requested"] = True
                                results["stop_reason"] = tool_args.get("reason", "No reason provided")
                            else:
                                # Handle standard MCP tools
                                logger.info(f"🔍 Looking for tool '{tool_name}' in {len(available_mcp_tools)} available tools: {[t.name for t in available_mcp_tools]}")
                                
                                # Handle all MCP tools the same way (no special cases)
                                for tool in available_mcp_tools:
                                    if tool.name == tool_name:
                                        logger.info(f"🔍 Found matching tool '{tool_name}', calling tool.func with args: {tool_args}")
                                        try:
                                            tool_result = tool.func(tool_args)
                                            logger.info(f"🔍 Tool '{tool_name}' returned result type: {type(tool_result)}")
                                            if isinstance(tool_result, str) and len(tool_result) > 200:
                                                logger.info(f"🔍 Tool result preview: {tool_result[:200]}...")
                                            else:
                                                logger.info(f"🔍 Tool result: {tool_result}")
                                        except Exception as tool_error:
                                            logger.error(f"🔍 Tool '{tool_name}' execution failed: {tool_error}")
                                            import traceback
                                            logger.error(f"🔍 Tool error traceback: {traceback.format_exc()}")
                                            tool_result = f"Tool execution error: {tool_error}"
                                        results["tools_used"].append(tool_name)
                                        break
                            
                            if tool_result is None:
                                tool_result = f"Tool {tool_name} not found"
                            
                            execution_time = time.time() - start_time
                            
                            # Log tool execution with improved logging
                            log_tool_execution(tool_name, tool_args, tool_result, execution_time)
                            
                            # Additional debug logging for tool parameters
                            logger.info(f"🔍 TOOL_DEBUG: {tool_name} called with parameters: {tool_args}")
                            if "plexus_feedback_find" in tool_name and "limit" in tool_args:
                                logger.info(f"   📊 Limit parameter: {tool_args['limit']}")
                            if "plexus_feedback_find" in tool_name:
                                logger.info(f"   🎯 Search parameters: scorecard='{tool_args.get('scorecard_name', 'N/A')}', score='{tool_args.get('score_name', 'N/A')}', initial='{tool_args.get('initial_value', 'N/A')}', final='{tool_args.get('final_value', 'N/A')}'")
                            
                            # Record tool response (tool call was already recorded before execution)
                            if self.chat_recorder and tool_call_message_id:
                                await self.chat_recorder.record_message(
                                    role='TOOL',
                                    content=str(tool_result),
                                    message_type='TOOL_RESPONSE',
                                    tool_name=tool_name,
                                    tool_response=tool_result if isinstance(tool_result, dict) else {"result": tool_result},
                                    parent_message_id=tool_call_message_id
                                )
                            
                            # Add result to conversation
                            try:
                                from langchain_core.messages import ToolMessage
                            except ImportError:
                                from langchain.schema.messages import ToolMessage
                            
                            tool_message = ToolMessage(content=str(tool_result), tool_call_id=tool_call['id'])
                            conversation_history.append(tool_message)
                            
                            # Add system reminder about explaining tool results and running interpretation
                            reminder_message = SystemMessage(
                                content="🚨 REMINDER: You must provide two things in your next response before calling any other tools:\n\n1. **Summary of This Tool Result**: Start with '### Summary of Tool Result:' and describe what you learned from this specific tool call.\n\n2. **Running Interpretation**: Explain how this result changes or reinforces your overall understanding. What patterns are emerging? How does this fit with what you've seen before? What is your evolving interpretation of what's happening with the scoring problems?\n\n🚨 **OFFSET REMINDER**: If you need to examine more examples from the same segment, remember to INCREMENT your offset (if you just used offset=5, use offset=6 next). Never repeat the same offset or you'll get duplicate results."
                            )
                            conversation_history.append(reminder_message)
                            
                            # Set flag to remove tools in next iteration to force explanation
                            results["force_explanation_next"] = True
                        
                        else:
                            # Regular response - check if guidance needed
                            response_content = ai_response.content
                            
                            if self.chat_recorder:
                                await self.chat_recorder.record_message('ASSISTANT', response_content, 'MESSAGE')
                            
                            conversation_history.append(ai_response)
                            
                            # Generate SOP guidance for next steps
                            current_state = self._get_current_state(results, round_num)
                            if self.procedure_definition.should_continue(current_state):
                                guidance = await self._generate_sop_guidance(conversation_history, current_state)
                                
                                # Add the actual user guidance message to shared conversation history
                                user_guidance = HumanMessage(content=guidance)
                                conversation_history.append(user_guidance)
                                
                                if self.chat_recorder:
                                    await self.chat_recorder.record_message('USER', guidance, 'MESSAGE')
                    
                    except Exception as e:
                        logger.error(f"Error in procedure round {round_num}: {e}")
                        break
                
                # Generate final results
                final_state = self._get_current_state(results, round_num)
                completion_summary = self.procedure_definition.get_completion_summary(final_state)
                
                # Request final summarization from worker agent
                final_summary = await self._request_final_summarization(conversation_history, results)
                if final_summary:
                    conversation_history.append(HumanMessage(content=final_summary["request"]))
                    conversation_history.append(AIMessage(content=final_summary["response"]))
                    if self.chat_recorder:
                        await self.chat_recorder.record_message('USER', final_summary["request"], 'MESSAGE')
                        await self.chat_recorder.record_message('ASSISTANT', final_summary["response"], 'MESSAGE')
                
                # End chat session
                if self.chat_recorder:
                    await self.chat_recorder.end_session('COMPLETED', name=f"Procedure: {self.procedure_id}")
                
                return {
                    "success": True,
                    "procedure_id": self.procedure_id,
                    "rounds_completed": round_num,
                    "tools_used": list(set(results["tools_used"])),
                    "completion_summary": completion_summary,
                    "final_state": final_state
                }
                
        except Exception as e:
            logger.error(f"Error executing procedure {self.procedure_id}: {e}")
            if self.chat_recorder:
                await self.chat_recorder.end_session('ERROR', name=f"Procedure Error: {self.procedure_id}")
            return {"success": False, "error": str(e), "procedure_id": self.procedure_id}
    
    def _get_current_state(self, results: Dict[str, Any], round_num: int) -> Dict[str, Any]:
        """Get current procedure state for decision making."""
        state = {
            "procedure_id": self.procedure_id,
            "round": round_num,
            "tools_used": results.get("tools_used", []),
            "artifacts_created": results.get("artifacts_created", 0),
            "context": self.context
        }
        
        # Add flow manager state if available
        if self.flow_manager:
            try:
                flow_state = self.flow_manager.update_state(
                    tools_used=results.get("tools_used", []),
                    response_content="",  # Could be enhanced
                )
                state.update(flow_state)
            except Exception as e:
                logger.warning(f"Error getting flow manager state: {e}")
        
        return state
    
    def _handle_stop_procedure(self, tool_args: Dict[str, Any]) -> str:
        """
        Handle the stop_procedure tool call from the worker agent.
        
        Args:
            tool_args: Arguments including 'reason' for stopping
            
        Returns:
            Success message for the tool call
        """
        reason = tool_args.get("reason", "No reason provided")
        success = tool_args.get("success", True)
        
        logger.info(f"🛑 Worker agent requested to stop procedure: {reason}")
        
        return {
            "success": True,
            "message": "Procedure stop request acknowledged",
            "reason": reason,
            "worker_success": success
        }
    
    async def _request_final_summarization(self, conversation_history: List, results: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Request a final summarization from the worker agent.
        
        Args:
            conversation_history: Complete conversation history
            results: Execution results
            
        Returns:
            Dictionary with 'request' and 'response' or None if failed
        """
        try:
            from .experiment_prompts import ExperimentPrompts
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, AIMessage
            
            # Create summarization request
            summarization_request = ExperimentPrompts.get_summarization_request(self.context)
            
            logger.info("📝 Requesting final summarization from worker agent")
            
            # Set up LLM for final summarization (no tools needed) using model configuration
            from .model_config import create_configured_llm, ModelConfigs
            
            if self._model_config_instance:
                # Use configured model for summarization
                summary_config = self._model_config_instance
                summary_config.openai_api_key = self.openai_api_key
                summarization_llm = summary_config.create_langchain_llm()
            else:
                # Fall back to default summarization configuration
                summarization_llm = create_configured_llm(
                    model_config={
                        "model": "gpt-4o",
                        "temperature": 0.3,
                        "max_tokens": 2000
                    },
                    openai_api_key=self.openai_api_key
                )
            
            # Create final conversation for summarization
            summarization_history = conversation_history.copy()
            summarization_history.append(HumanMessage(content=summarization_request))
            
            # Get summarization response
            response = summarization_llm.invoke(summarization_history)
            
            logger.info("✅ Final summarization completed")
            logger.info(f"📄 Final Summary Content:\n{response.content}")
            
            return {
                "request": summarization_request,
                "response": response.content
            }
            
        except Exception as e:
            logger.error(f"Error requesting final summarization: {e}")
            return None



# Convenience function for procedure execution
async def execute_sop_procedure(procedure_id: str,
                               procedure_definition: ProcedureDefinition,
                               procedure_yaml: str,
                               mcp_server,
                               flow_manager: Optional[FlowManager] = None,
                               chat_recorder: Optional[ChatRecorder] = None,
                               openai_api_key: Optional[str] = None,
                               context: Optional[Dict[str, Any]] = None,
                               model_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute a Standard Operating Procedure with the SOP Agent.
    
    This is the main entry point for executing any procedure using the
    general-purpose StandardOperatingProcedureAgent.
    
    Args:
        procedure_id: Unique identifier for this procedure execution
        procedure_definition: Defines procedure-specific behavior
        procedure_yaml: YAML configuration for the procedure
        mcp_server: MCP server providing tools
        flow_manager: Optional flow manager for conversation state
        chat_recorder: Optional recorder for conversation logging
        openai_api_key: Optional OpenAI API key
        context: Optional procedure context
        model_config: Optional model configuration dict for LLM parameters
        
    Returns:
        Dictionary with execution results
    """
    logger.info(f"Starting SOP-guided procedure execution: {procedure_id}")
    
    try:
        # Create and set up the SOP Agent
        sop_agent = StandardOperatingProcedureAgent(
            procedure_id=procedure_id,
            procedure_definition=procedure_definition,
            mcp_server=mcp_server,
            flow_manager=flow_manager,
            chat_recorder=chat_recorder,
            openai_api_key=openai_api_key,
            context=context,
            model_config=model_config
        )
        
        setup_success = await sop_agent.setup(procedure_yaml)
        if not setup_success:
            return {
                "success": False,
                "error": "Failed to set up StandardOperatingProcedureAgent",
                "procedure_id": procedure_id
            }
        
        # Execute the procedure
        result = await sop_agent.execute_procedure()
        
        logger.info(f"SOP-guided procedure completed: {result.get('success', False)}")
        return result
        
    except Exception as e:
        logger.error(f"Error in SOP procedure execution: {e}")
        return {
            "success": False,
            "error": str(e),
            "procedure_id": procedure_id
        }
