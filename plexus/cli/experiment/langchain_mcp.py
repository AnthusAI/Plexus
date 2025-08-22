"""
LangChain integration for MCP tools in experiments.

This module provides LangChain tools that can interact with the in-process MCP
server, allowing AI models to use Plexus MCP tools during experiment execution.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field
import yaml
from langchain.schema import HumanMessage, AIMessage
from .chat_recorder import ExperimentChatRecorder, LangChainChatRecorderHook
from .mcp_tool import MCPTool
from .mcp_adapter import LangChainMCPAdapter
from .openai_compat import O3CompatibleChatOpenAI
from .conversation_flow import ConversationFlowManager
from .experiment_prompts import ExperimentPrompts
from .conversation_utils import ConversationUtils

logger = logging.getLogger(__name__)

class ExperimentAIRunner:
    """
    Runs AI models with access to MCP tools in experiment context.
    
    This class handles:
    1. Loading experiment YAML configuration
    2. Setting up MCP tools for AI access
    3. Running AI with the exploration prompt
    4. Capturing and reporting results
    """
    
    def __init__(self, experiment_id: str, mcp_server, client=None, openai_api_key: Optional[str] = None, experiment_context: Optional[Dict[str, Any]] = None):
        self.experiment_id = experiment_id
        self.mcp_server = mcp_server
        self.client = client
        # Use passed openai_api_key parameter first, then get from environment after config load
        self.openai_api_key = openai_api_key
        if not self.openai_api_key:
            # Use Plexus configuration system to properly load environment variables
            from plexus.config.loader import load_config
            load_config()  # This loads .plexus/config.yaml and sets environment variables
            import os
            self.openai_api_key = os.getenv('OPENAI_API_KEY')
        logger.info(f"AI Runner initialized with OpenAI key: {'Yes' if self.openai_api_key else 'No'}")
        self.experiment_config = None
        self.mcp_adapter = None
        self.experiment_context = experiment_context or {}
        self.chat_recorder = None
        self.flow_manager = None
    
    async def setup(self, experiment_yaml: str):
        """Set up the AI runner with experiment configuration."""
        try:
            # Parse experiment YAML
            self.experiment_config = yaml.safe_load(experiment_yaml)
            logger.info(f"Loaded experiment config for {self.experiment_id}")
            
            # Initialize conversation flow manager for conversation management
            self.flow_manager = ConversationFlowManager(
                experiment_config=self.experiment_config,
                experiment_context=self.experiment_context
            )
            logger.info("Initialized conversation flow manager")
            
            # Set up MCP adapter
            async with self.mcp_server.connect({'name': f'AI Runner for {self.experiment_id}'}) as mcp_client:
                self.mcp_adapter = LangChainMCPAdapter(mcp_client)
                await self.mcp_adapter.load_tools()
                logger.info(f"Set up MCP adapter with {len(self.mcp_adapter.tools)} tools")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up AI runner: {e}")
            return False

    def get_exploration_prompt(self) -> str:
        """Return the exploration prompt from the experiment YAML or a sensible fallback.

        Tests and demos expect an explicit exploration prompt that may mention
        tools like 'plexus_scorecards_list'. If the loaded experiment YAML
        contains an 'exploration' field, prefer returning it directly. If not,
        fall back to the user prompt used in our hypothesis engine flow.
        """
        try:
            if self.experiment_config and 'exploration' in self.experiment_config:
                prompt = self.experiment_config.get('exploration') or ""
                if isinstance(prompt, str) and prompt.strip():
                    return prompt
        except Exception:
            # Fallback below
            pass
        # Fallback to existing user prompt builder
        return self.get_user_prompt()
    
    def get_system_prompt(self) -> str:
        """Get the system prompt with context about the hypothesis engine and documentation."""
        return ExperimentPrompts.get_system_prompt(self.experiment_context)

    def get_user_prompt(self) -> str:
        """Get the user prompt with current score configuration and feedback summary."""
        return ExperimentPrompts.get_user_prompt(self.experiment_context)
    
    async def _generate_orchestration_message(self, conversation_history: List, state_data: Dict[str, Any]) -> str:
        """Generate a contextual user message using orchestration LLM."""
        try:
            # Import LangChain for orchestration LLM
            from langchain_openai import ChatOpenAI
            from langchain.schema import SystemMessage, HumanMessage
            
            # Create orchestration LLM
            orchestration_llm = ChatOpenAI(
                model="gpt-4o",  # Use a capable model for orchestration
                temperature=0.1,  # Low temperature for consistent guidance
                openai_api_key=self.openai_api_key,
                stream=False  # Disable streaming responses
            )
            
            # Get current state info - handle None state_data
            if not state_data:
                state_data = {}
            
            current_state = state_data.get('current_state', 'exploration')  # Use flow manager stage
            round_in_state = state_data.get('round_in_stage', 0)
            total_rounds = state_data.get('total_rounds', 0)
            tools_used = state_data.get('tools_used', [])  # Use flow manager tools
            nodes_created = state_data.get('nodes_created', 0)  # Use flow manager node count
            analysis_completed = state_data.get('analysis_completed', {})
            
            # Build orchestration system prompt using the prompts class
            system_prompt = ExperimentPrompts.get_orchestration_system_prompt(
                self.experiment_context, 
                state_data
            )

            # Build comprehensive conversation summary for orchestration
            conversation_summary = ""
            last_message_content = ""
            
            if conversation_history:
                # Create truncated summary of all messages
                summary_lines = []
                for i, msg in enumerate(conversation_history):
                    if hasattr(msg, 'content'):
                        msg_type = "System" if hasattr(msg, '__class__') and 'System' in msg.__class__.__name__ else \
                                  ("User" if isinstance(msg, HumanMessage) else "AI")
                        
                        # Truncate content but show message structure
                        content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                        summary_lines.append(f"[{i}] {msg_type}: {content_preview}")
                
                conversation_summary = f"\n\nCONVERSATION HISTORY ({len(conversation_history)} messages):\n" + "\n".join(summary_lines)
                
                # Get full content of the last message
                last_msg = conversation_history[-1]
                if hasattr(last_msg, 'content'):
                    last_msg_type = "System" if hasattr(last_msg, '__class__') and 'System' in last_msg.__class__.__name__ else \
                                   ("User" if isinstance(last_msg, HumanMessage) else "AI") 
                    last_message_content = f"\n\nLAST MESSAGE FULL CONTENT:\n[{len(conversation_history)-1}] {last_msg_type}: {last_msg.content}"

            human_prompt = ExperimentPrompts.get_orchestration_human_prompt(conversation_summary, last_message_content)
            
            # Call orchestration LLM
            orchestration_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = orchestration_llm.invoke(orchestration_messages)
            logger.info(f"ORCHESTRATION LLM: Generated dynamic message ({len(response.content)} chars)")
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating orchestration message: {e}")
            logger.error(f"OpenAI API key available: {'Yes' if self.openai_api_key else 'No'}")
            import traceback
            logger.error(f"Orchestration LLM traceback: {traceback.format_exc()}")
            # Fallback to flow manager template
            fallback = self.flow_manager.get_next_guidance() 
            logger.info(f"ORCHESTRATION: Falling back to template ({len(fallback)} chars)")
            return fallback or "Continue your analysis and hypothesis generation."
    
    async def run_ai_with_tools(self) -> Dict[str, Any]:
        """Run the AI model with access to MCP tools."""
        try:
            # Initialize chat recording if client is available
            if self.client:
                # Get the root node ID for this experiment to associate the chat session
                root_node_id = self.experiment_context.get('root_node_id')
                
                # Try multiple ways to get the root node ID
                if not root_node_id and self.experiment_context.get('experiment_id'):
                    try:
                        from plexus.dashboard.api.models.experiment import Experiment
                        experiment = Experiment.get_by_id(self.experiment_context.get('experiment_id'), self.client)
                        if experiment and experiment.rootNodeId:
                            # Use the rootNodeId directly from the experiment record
                            root_node_id = experiment.rootNodeId
                            logger.info(f"Using root node ID from experiment: {root_node_id}")
                        else:
                            logger.warning("Experiment has no rootNodeId - will record chat without node association")
                    except Exception as e:
                        logger.warning(f"Could not get experiment for chat session: {e}")
                
                # FIXED: For the main experiment conversation, record at experiment level (node_id = None)
                # Individual node conversations would use specific node IDs, but this is the main
                # conversation that should appear at the experiment level in the UI
                self.chat_recorder = ExperimentChatRecorder(self.client, self.experiment_id, None)
                
                # Always try to start a session, even without node association
                logger.info(f"Starting chat session for experiment {self.experiment_id} at experiment level (no node association)")
                session_id = await self.chat_recorder.start_session(self.experiment_context)
                if session_id:
                    logger.info(f"Successfully started chat recording session: {session_id}")
                else:
                    logger.error("Failed to start chat recording session - chat will not be recorded")
            
            if not self.openai_api_key:
                error_msg = "OpenAI API key not available"
                if self.chat_recorder:
                    await self.chat_recorder.record_system_message(f"Error: {error_msg}")
                    await self.chat_recorder.end_session('ERROR', name="Setup Error - Missing API Key")
                return {
                    "success": False,
                    "error": error_msg,
                    "suggestion": "Set OPENAI_API_KEY environment variable or pass it to the runner"
                }
            
            # Import LangChain components
            try:
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError:
                    from langchain.chat_models import ChatOpenAI
                from langchain.agents import initialize_agent, AgentType
                from langchain.memory import ConversationBufferMemory
                from langchain.tools import Tool, StructuredTool
                from langchain.tools.base import BaseTool
                from langchain.callbacks.base import BaseCallbackHandler
                from pydantic import BaseModel, Field
            except ImportError:
                error_msg = "LangChain not available"
                if self.chat_recorder:
                    await self.chat_recorder.record_system_message(f"Error: {error_msg}")
                    await self.chat_recorder.end_session('ERROR', name="Setup Error - Missing Dependencies")
                return {
                    "success": False,
                    "error": error_msg,
                    "suggestion": "Install langchain: pip install langchain openai"
                }
            
            # Create custom callback for chat recording
                        # Create callback if recorder is available
            callback = None
            
            # Set up the AI model - create o3-compatible configuration
            model_name = "o3"
            
            # Create model kwargs that exclude unsupported parameters for o3
            model_config = {
                "model": model_name,
                "temperature": 1,
                "openai_api_key": self.openai_api_key,
                "stream": False,  # Disable streaming responses
            }
            
            # Only add completion tokens for newer models like o3
            if model_name in ["o3", "gpt-4.1", "gpt-5"]:
                model_config["max_completion_tokens"] = 4000
            else:
                model_config["max_tokens"] = 4000
            
            # Use the extracted O3-compatible model with tools bound
            base_llm = O3CompatibleChatOpenAI(**model_config)
            
            # Debug log to confirm streaming is disabled
            logger.info(f"LLM Configuration: model={model_config.get('model')}, stream={model_config.get('stream')}, temperature={model_config.get('temperature')}")
            logger.info(f"LLM streaming setting: {getattr(base_llm, 'stream', 'not set')}")
            
            # Convert MCP tools to LangChain tools
            async with self.mcp_server.connect({'name': f'AI Agent for {self.experiment_id}'}) as mcp_client:
                adapter = LangChainMCPAdapter(mcp_client)
                all_mcp_tools = await adapter.load_tools()
                
                # CRITICAL FIX: Implement tool scoping for hypothesis generation
                # Only allow tools appropriate for analysis and hypothesis creation
                allowed_tools_for_hypothesis_generation = {
                    # Analysis tools - for examining feedback and understanding problems
                    'plexus_feedback_analysis',
                    'plexus_feedback_find', 
                    'plexus_item_info',
                    'plexus_score_info',
                    'plexus_scorecard_info',
                    
                    # Hypothesis creation tools - for creating experiment nodes
                    'create_experiment_node',
                    'get_experiment_tree',
                    'update_node_content',
                    
                    # Utility tools
                    'think'
                }
                
                # UNAUTHORIZED TOOLS that should NOT be available during hypothesis generation:
                # - plexus_predict: AI should NOT run predictions during hypothesis generation
                # - Other execution/testing tools that go beyond analysis and hypothesis creation
                
                # Filter tools to only include those appropriate for hypothesis generation
                mcp_tools = []
                unauthorized_tools = []
                
                for tool in all_mcp_tools:
                    if tool.name in allowed_tools_for_hypothesis_generation:
                        mcp_tools.append(tool)
                        logger.info(f"TOOL SCOPING: Allowing tool '{tool.name}' for hypothesis generation")
                    else:
                        unauthorized_tools.append(tool.name)
                        logger.warning(f"TOOL SCOPING: Blocking unauthorized tool '{tool.name}' from hypothesis generation")
                
                logger.info(f"TOOL SCOPING: {len(mcp_tools)} tools allowed, {len(unauthorized_tools)} tools blocked")
                logger.info(f"TOOL SCOPING: Allowed tools: {[tool.name for tool in mcp_tools]}")
                logger.info(f"TOOL SCOPING: Blocked tools: {unauthorized_tools}")
                
                # Set up chat recording in the adapter
                adapter.chat_recorder = self.chat_recorder
                
                # Convert to LangChain Tool format
                langchain_tools = []
                for mcp_tool in mcp_tools:
                    # Create a structured tool to handle multiple parameters properly
                    tool_name = mcp_tool.name
                    tool_description = mcp_tool.description
                    tool_func = mcp_tool.func
                    
                    # Create a proper StructuredTool using the from_function method
                    # Fix closure issue by capturing variables by value
                    def create_tool_func(func, name):
                        def wrapper(**kwargs):
                            logger.info(f"=== LANGCHAIN TOOL WRAPPER DEBUG ===")
                            logger.info(f"Tool: {name}")
                            logger.info(f"Kwargs Received: {kwargs}")
                            logger.info(f"Kwargs Type: {type(kwargs)}")
                            logger.info("=== CALLING MCP TOOL FUNC ===")
                            # Pass the kwargs dictionary directly to the MCP tool function
                            result = func(kwargs)
                            logger.info(f"MCP Tool Result: {result}")
                            logger.info("=== END LANGCHAIN WRAPPER ===")
                            return result
                        wrapper.__name__ = name.replace('-', '_').replace(' ', '_')
                        return wrapper
                    
                    # Create a proper StructuredTool by defining the input schema manually
                    # Extract schema from the MCP tool definition - mcp_tool is already parsed from MCP
                    # Get the actual input schema from the MCP tool list
                    
                    # Instead of using complex schema extraction, let's use the actual function signature
                    # Get the expected parameters from the plexus tool if it's a well-known one
                    # ONLY include schemas for tools that are allowed during hypothesis generation
                    known_tool_schemas = {
                        # Analysis tools - allowed for examining feedback and understanding problems
                        'plexus_score_info': {
                            'score_identifier': 'Score identifier (ID, name, key, or external ID)',
                            'scorecard_identifier': 'Optional scorecard identifier to narrow search',
                            'version_id': 'Optional specific version ID',
                            'include_versions': 'Include detailed version information'
                        },
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
                            'offset': 'Simple numeric offset for pagination - start at result #N (e.g., 0, 5, 10). Use offset=0 for first page, offset=5 for second page, etc.'
                        },
                        'plexus_item_info': {
                            'item_id': 'The unique ID of the item OR an external identifier value'
                        },
                        'plexus_scorecard_info': {
                            'scorecard_identifier': 'The identifier for the scorecard (can be ID, name, key, or external ID)'
                        },
                        
                        # Hypothesis creation tools - allowed for creating experiment nodes
                        'create_experiment_node': {
                            'experiment_id': 'The unique ID of the experiment',
                            'hypothesis_description': 'Clear description following format: GOAL: [target - no quantification] | METHOD: [changes]',
                            'node_name': 'Descriptive name for the hypothesis node (optional)',
                            'yaml_configuration': 'Optional YAML configuration - can be added later'
                        },
                        'get_experiment_tree': {
                            'experiment_id': 'ID of the experiment to analyze'
                        },
                        'update_node_content': {
                            'node_id': 'ID of the node to update',
                            'yaml_configuration': 'Updated YAML configuration',
                            'update_description': 'Description of what changed in this update',
                            'computed_value': 'Optional computed results (defaults to update info)'
                        },
                        
                        # Utility tools
                        'think': {
                            'thought': 'Your internal reasoning or analysis'
                        }
                        
                        # REMOVED UNAUTHORIZED TOOLS:
                        # - 'plexus_predict': BLOCKED - AI should NOT run predictions during hypothesis generation
                        # - Other execution/testing tools are also blocked by the scoping filter above
                    }
                    
                    schema_props = known_tool_schemas.get(tool_name, {})
                    
                    logger.info(f"Creating StructuredTool for {tool_name} with known schema: {list(schema_props.keys())}")
                    
                    # Create a wrapper function that accepts both positional and keyword arguments
                    def make_structured_func(func, name):
                        def wrapper(*args, **kwargs):
                            logger.info(f"=== LANGCHAIN STRUCTURED TOOL DEBUG ===")
                            logger.info(f"Tool: {name}")
                            logger.info(f"Args: {args}")
                            logger.info(f"Kwargs: {kwargs}")
                            logger.info("=== CALLING MCP TOOL FUNC ===")
                            
                            # Handle different argument patterns from LangChain
                            if args and not kwargs:
                                # LangChain passed positional arguments (likely a single dict)
                                if len(args) == 1 and isinstance(args[0], dict):
                                    result = func(args[0])
                                else:
                                    # Convert positional args to dict based on known schema
                                    arg_dict = {}
                                    prop_names = list(schema_props.keys()) if schema_props else ['input']
                                    for i, arg in enumerate(args):
                                        if i < len(prop_names):
                                            arg_dict[prop_names[i]] = arg
                                    result = func(arg_dict)
                            elif kwargs:
                                # LangChain passed keyword arguments - pass them to MCP tool
                                result = func(kwargs)
                            else:
                                # No arguments provided
                                result = func({})
                            
                            logger.info(f"MCP Tool Result: {result}")
                            logger.info("=== END LANGCHAIN STRUCTURED WRAPPER ===")
                            return result
                        return wrapper
                    
                    # Create the StructuredTool manually with explicit args_schema
                    from pydantic import Field
                    from typing import Union, Optional
                    
                    # Build the Pydantic model dynamically using modern Pydantic BaseModel approach
                    # This avoids deprecation warnings from create_model with tuple field definitions
                    if schema_props:
                        # Create annotations dictionary for the model
                        annotations = {}
                        field_defaults = {}
                        
                        for prop_name, prop_description in schema_props.items():
                            # Use Optional Union type for flexibility - MCP tools handle type coercion
                            annotations[prop_name] = Optional[Union[str, int, float, bool]]
                            field_defaults[prop_name] = Field(default="", description=prop_description)
                        
                        # Create class dynamically without deprecated patterns
                        class_name = f"{tool_name.replace('-', '_')}_Args"
                        ArgsSchema = type(class_name, (BaseModel,), {
                            '__annotations__': annotations,
                            **field_defaults
                        })
                    else:
                        # Fallback schema for tools without known schema
                        class ArgsSchema(BaseModel):
                            input: Optional[Union[str, int, float, bool]] = Field(default="", description="Tool input")
                    
                    langchain_tool = StructuredTool(
                        name=tool_name,
                        description=tool_description,
                        func=make_structured_func(tool_func, tool_name),
                        args_schema=ArgsSchema
                    )
                    
                    langchain_tools.append(langchain_tool)
                
                logger.info(f"Created {len(langchain_tools)} LangChain tools from MCP")
                
                # BEST OF BOTH WORLDS: Bind tools to LLM for native tool calling
                # while maintaining our own conversation loop control
                llm_with_tools = base_llm.bind_tools(langchain_tools)
                logger.info(f"Bound {len(langchain_tools)} tools to LLM for native tool calling")
                
                # Get the system and user prompts first
                system_prompt = self.get_system_prompt()
                user_prompt = self.get_user_prompt()
                logger.info(f"Generated prompts: system={len(system_prompt)} chars, user={len(user_prompt)} chars")
                
                logger.info(f"Using LangChain native tool calling with our conversation loop")
                
                # Use LangChain's native message types
                from langchain.schema import SystemMessage, HumanMessage
                try:
                    from langchain_core.messages import ToolMessage
                except ImportError:
                    try:
                        from langchain.schema.messages import ToolMessage
                    except ImportError:
                        # Fallback for older versions - create a simple message with tool info
                        from langchain.schema import AIMessage
                        ToolMessage = lambda content, tool_call_id: AIMessage(content=f"Tool result: {content}")
                
                logger.info("Using LangChain native tool calling with our conversation loop")
                
                # Record the system prompt and user prompt separately  
                if self.chat_recorder:
                    await self.chat_recorder.record_system_message(system_prompt)
                    # Record user message with the current configuration and task
                    user_message_id = await self.chat_recorder.record_message(
                        role='USER',
                        content=user_prompt,
                        message_type='MESSAGE'
                    )
                
                # Log the configuration
                logger.info("="*60)
                logger.info("LANGCHAIN NATIVE TOOL CALLING CONFIGURATION:")
                logger.info("="*60)
                logger.info(f"SYSTEM PROMPT: {system_prompt[:300]}{'...' if len(system_prompt) > 300 else ''}")
                logger.info("-" * 30)
                logger.info(f"USER PROMPT: {user_prompt[:300]}{'...' if len(user_prompt) > 300 else ''}")
                logger.info("-"*30)
                logger.info(f"AVAILABLE TOOLS: {[tool.name for tool in langchain_tools]}")
                logger.info(f"APPROACH: Native LangChain tool calling with manual conversation loop")
                logger.info(f"MAX ITERATIONS: 20")
                logger.info(f"TOOL BINDING: {len(langchain_tools)} tools bound to LLM")
                logger.info("="*60)
                
                # Track tool usage for safeguards
                tool_usage_tracker = {
                    "create_experiment_node_count": 0,
                    "create_experiment_node_attempts": 0  # Track attempts vs successes
                }
                
                # BEST OF BOTH WORLDS: LangChain native tool calling with our conversation loop
                conversation_history = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ]
                
                response = ""
                nodes_created = 0
                round_num = 0
                safety_limit = 50  # Ultimate safety limit to prevent infinite loops
                
                logger.info("🚀 Starting LangChain native tool calling with flow manager guidance...")
                
                # Use flow manager's should_continue logic instead of arbitrary round limit
                # Fallback to reasonable limit if no flow manager available
                while ((self.flow_manager and self.flow_manager.should_continue()) or 
                       (not self.flow_manager and round_num < 15)) and round_num < safety_limit:
                    round_num += 1
                    stage_info = self.flow_manager.state.stage.value if self.flow_manager else "no-flow-manager"
                    logger.info(f"📝 CONVERSATION ROUND {round_num} (Flow Manager: {stage_info})")
                    
                    try:
                        # Get AI response using LLM with bound tools - LangChain handles tool calling
                        ai_response = llm_with_tools.invoke(conversation_history)
                        
                        # Log the raw AI response FIRST before processing
                        logger.info(f"🤖 RAW AI RESPONSE: {ai_response}")
                        logger.info(f"🤖 RAW AI RESPONSE TYPE: {type(ai_response)}")
                        logger.info(f"🤖 RAW AI RESPONSE CONTENT: {getattr(ai_response, 'content', 'No content attr')}")
                        logger.info(f"🤖 RAW AI RESPONSE TOOL_CALLS: {getattr(ai_response, 'tool_calls', 'No tool_calls attr')}")
                        
                        # Check if this is a regular message or contains tool calls
                        if hasattr(ai_response, 'tool_calls') and ai_response.tool_calls:
                            # LangChain detected tool calls - handle them
                            tool_call_count = len(ai_response.tool_calls)
                            tool_call_text = "tool call" if tool_call_count == 1 else "tool calls"
                            logger.info(f"🔧 LangChain detected {tool_call_count} {tool_call_text}")
                            
                            # Record the AI response with tool calls
                            if self.chat_recorder:
                                tool_call_summary = f"AI requested {tool_call_count} {tool_call_text}: {[call['name'] for call in ai_response.tool_calls]}"
                                await self.chat_recorder.record_message(
                                    role='ASSISTANT',
                                    content=tool_call_summary,
                                    message_type='MESSAGE'
                                )
                            
                            # Add AI message to conversation history
                            conversation_history.append(ai_response)
                            
                            # Execute each tool call using LangChain's parsed data
                            for tool_call in ai_response.tool_calls:
                                tool_name = tool_call['name']
                                tool_args = tool_call['args']
                                
                                logger.info(f"🔧 EXECUTING TOOL: {tool_name}({tool_args})")
                                
                                # Record tool call
                                if self.chat_recorder:
                                    await self.chat_recorder.record_message(
                                        role='TOOL',
                                        content=f"{tool_name}({tool_args})",
                                        message_type='TOOL_CALL'
                                    )
                                
                                # Execute the tool using our MCP backend
                                tool_result = None
                                for mcp_tool in mcp_tools:
                                    if mcp_tool.name == tool_name:
                                        try:
                                            tool_result = mcp_tool.func(tool_args)
                                            break
                                        except Exception as e:
                                            tool_result = f"Error calling {tool_name}: {e}"
                                            break
                                
                                if tool_result is None:
                                    tool_result = f"Tool {tool_name} not found"
                                
                                logger.info(f"✅ TOOL RESULT: {str(tool_result)[:200]}{'...' if len(str(tool_result)) > 200 else ''}")
                                
                                # Record tool result
                                if self.chat_recorder:
                                    await self.chat_recorder.record_message(
                                        role='TOOL', 
                                        content=str(tool_result),
                                        message_type='TOOL_RESPONSE'
                                    )
                                
                                # Create a ToolMessage for LangChain conversation history
                                tool_message = ToolMessage(
                                    content=str(tool_result),
                                    tool_call_id=tool_call['id']
                                )
                                conversation_history.append(tool_message)
                                
                                # Track node creation for safeguards
                                if tool_name == "create_experiment_node":
                                    # Check if the tool call was successful (no error indicators)
                                    tool_result_str = str(tool_result).lower()
                                    error_indicators = [
                                        "error", "failed", "exception", "⚠️", "❌", "invalid", 
                                        "missing", "required", "unexpected", "not found", "bad request"
                                    ]
                                    success_indicators = [
                                        "successfully created", "node created", "experiment node", 
                                        "created node", "hypothesis added", "node id", "created successfully"
                                    ]
                                    
                                    has_errors = any(indicator in tool_result_str for indicator in error_indicators)
                                    has_success = any(indicator in tool_result_str for indicator in success_indicators)
                                    
                                    if has_success and not has_errors:
                                        tool_usage_tracker["create_experiment_node_count"] += 1
                                        nodes_created = tool_usage_tracker["create_experiment_node_count"]
                                        logger.info(f"✅ NODES CREATED: {nodes_created}")
                            
                            # Update flow manager state after tool calls are processed
                            if self.flow_manager:
                                tools_used_this_round = [tool_call['name'] for tool_call in ai_response.tool_calls]
                                state_data = self.flow_manager.update_state(
                                    tools_used=tools_used_this_round,
                                    response_content="", # No response content for tool calls
                                    nodes_created=tool_usage_tracker["create_experiment_node_count"]
                                )
                                logger.info(f"🔄 Flow Manager updated after tools: stage={state_data.get('current_state')}, nodes_created={state_data.get('nodes_created')}")
                            
                            # Continue the loop for the next round
                            continue
                            
                        else:
                            # Regular AI response without tool calls
                            response_content = ai_response.content
                            logger.info(f"🤖 AI Response: {response_content[:300]}{'...' if len(response_content) > 300 else ''}")
                            
                            # Record the AI response
                            if self.chat_recorder:
                                await self.chat_recorder.record_message(
                                    role='ASSISTANT',
                                    content=response_content,
                                    message_type='MESSAGE'
                                )
                            
                            # Add AI response to conversation history
                            conversation_history.append(ai_response)
                            
                            # FLOW MANAGER INTEGRATION: Instead of immediately terminating,
                            # use the flow manager to determine if conversation should continue
                            logger.info("🤖 AI response without tool calls - checking flow manager for continuation")
                            
                            # Update flow manager state with current progress
                            if self.flow_manager:
                                tools_used_this_round = []  # No tools used in this round
                                state_data = self.flow_manager.update_state(
                                    tools_used=tools_used_this_round,
                                    response_content=response_content,
                                    nodes_created=tool_usage_tracker["create_experiment_node_count"]
                                )
                                
                                # Check if conversation should continue
                                should_continue = self.flow_manager.should_continue()
                                logger.info(f"🔄 Flow Manager: should_continue={should_continue}, stage={state_data.get('current_state')}, nodes_created={state_data.get('nodes_created')}")
                                
                                if should_continue:
                                    # Generate orchestration message to guide the AI forward
                                    logger.info("🎯 Flow Manager: Generating orchestration message to continue conversation")
                                    orchestration_message = await self._generate_orchestration_message(conversation_history, state_data)
                                    
                                    # Add orchestration message as user guidance
                                    user_guidance = HumanMessage(content=orchestration_message)
                                    conversation_history.append(user_guidance)
                                    
                                    # Record the orchestration guidance
                                    if self.chat_recorder:
                                        await self.chat_recorder.record_message(
                                            role='USER',
                                            content=orchestration_message,
                                            message_type='MESSAGE'
                                        )
                                    
                                    logger.info(f"📝 Added orchestration guidance: {orchestration_message[:200]}...")
                                    continue  # Continue the conversation loop
                                else:
                                    # Flow manager says conversation is complete
                                    completion_summary = self.flow_manager.get_completion_summary()
                                    logger.info(f"🏁 Flow Manager: Conversation complete - {completion_summary[:100]}...")
                                    response = response_content + f"\n\n{completion_summary}"
                                    break
                            else:
                                # Fallback: No flow manager available, terminate as before
                                logger.info("🏁 No flow manager available - conversation complete")
                                response = response_content
                                break
                        
                    except Exception as e:
                        logger.error(f"❌ CONVERSATION ROUND {round_num + 1} FAILED: {e}")
                        response = f"Conversation round {round_num + 1} failed: {e}"
                        
                        # Record the error
                        if self.chat_recorder:
                            await self.chat_recorder.record_message(
                                role='SYSTEM',
                                content=f"Round {round_num + 1} error: {str(e)}",
                                message_type='MESSAGE'
                            )
                        break
                
                # CONVERSATION COMPLETE: Log why conversation ended
                if self.flow_manager:
                    flow_should_continue = self.flow_manager.should_continue()
                    logger.info(f"🏁 CONVERSATION ENDED: Flow Manager should_continue={flow_should_continue}, "
                              f"stage={self.flow_manager.state.stage.value}, "
                              f"round_in_stage={self.flow_manager.state.round_in_stage}, "
                              f"total_rounds={self.flow_manager.state.total_rounds}, "
                              f"nodes_created={self.flow_manager.state.nodes_created}")
                else:
                    logger.info(f"🏁 CONVERSATION ENDED: No flow manager (fallback limit reached)")
                
                if round_num >= safety_limit:
                    logger.warning(f"⚠️ SAFETY LIMIT REACHED: Conversation terminated at safety limit of {safety_limit} rounds")
                
                # CONVERSATION COMPLETE: Generate completion summary
                logger.info(f"AGENT EXECUTION ENDING: nodes_created={nodes_created}")
                
                # Generate completion summary
                completion_summary = "Agent execution completed"
                
                # Add a programmatic explanation of why the execution ended
                termination_reason = f"""

## Experiment Session Complete

**Execution Result:** {'No experiment nodes created' if nodes_created == 0 else f'{nodes_created} experiment nodes created successfully'}

**Session Summary:**
- Agent execution: {'Failed' if 'failed' in response.lower() else 'Completed'}
- Nodes created: {nodes_created}

**Next Steps:** {'Manual intervention may be required' if nodes_created == 0 else 'Review generated hypotheses in the experiment dashboard'}
"""
                
                # Record the termination explanation
                if self.chat_recorder:
                    await self.chat_recorder.record_message(
                        role='SYSTEM', 
                        content=termination_reason,
                        message_type='MESSAGE'
                    )
                
                completion_summary_with_reason = completion_summary + termination_reason
                response += f"\n\n{completion_summary_with_reason}"
                logger.info(f"AGENT EXECUTION: Complete - {completion_summary}")
                logger.info(f"TERMINATION REASON: {termination_reason.strip()}")
                
                # =====================================================================
                # FINALLY CLAUSE: Automatic conversation summarization (always runs)
                # =====================================================================
                logger.info("FINALLY CLAUSE: Starting automatic conversation summarization...")
                
                try:
                    # STEP 1: Add User message requesting summarization
                    summarization_request = ExperimentPrompts.get_summarization_request(self.experiment_context)
                    
                    # Record the user's summarization request
                    if self.chat_recorder:
                        await self.chat_recorder.record_message(
                            role='USER',
                            content=summarization_request.strip(),
                            message_type='MESSAGE'
                        )
                    
                    logger.info("FINALLY CLAUSE: User summarization request added")
                    
                    # STEP 2: Get AI's comprehensive summary response
                    # Since we're using LangChain agent, create a simple conversation for summarization
                    logger.info("FINALLY CLAUSE: Requesting AI summary response...")
                    
                    # Create a minimal conversation context for summarization
                    summary_conversation = [
                        HumanMessage(content=f"Based on our conversation about experiment {self.experiment_id}, please provide a comprehensive summary."),
                        HumanMessage(content=summarization_request.strip())
                    ]
                    
                    summary_ai_response = base_llm.invoke(summary_conversation)
                    summary_response_content = summary_ai_response.content
                    
                    # Record the AI's summary response
                    if self.chat_recorder:
                        await self.chat_recorder.record_message(
                            role='ASSISTANT',
                            content=summary_response_content,
                            message_type='MESSAGE'
                        )
                    
                    logger.info(f"FINALLY CLAUSE: AI summary generated ({len(summary_response_content)} characters)")
                    
                    # Append the summary to the main response for visibility
                    response += f"\n\n## Conversation Summary\n\n{summary_response_content}"
                    
                except Exception as summary_error:
                    logger.error(f"FINALLY CLAUSE ERROR: Failed to generate summary - {summary_error}")
                    # Don't let summarization errors break the main conversation
                    summary_fallback = f"""
## Conversation Summary (Error Recovery)

Unable to generate detailed summary due to error: {str(summary_error)}

**Session Overview:**
- Agent execution: Using LangChain agent framework
- Nodes created: {tool_usage_tracker["create_experiment_node_count"]}
- Target scorecard: {self.experiment_context.get('scorecard_name', 'Unknown')}
- Target score: {self.experiment_context.get('score_name', 'Unknown')}
"""
                    response += summary_fallback
                    
                    if self.chat_recorder:
                        await self.chat_recorder.record_system_message(
                            f"Summarization error occurred: {str(summary_error)}"
                        )
                
                logger.info("FINALLY CLAUSE: Automatic conversation summarization complete")
                
                # End the chat session with meaningful name based on outcome
                if self.chat_recorder:
                    nodes_created = tool_usage_tracker["create_experiment_node_count"]
                    if nodes_created == 0:
                        session_name = "No Hypotheses Generated"
                    elif nodes_created == 1:
                        session_name = "1 Hypothesis Generated"
                    else:
                        session_name = f"{nodes_created} Hypotheses Generated"
                    
                    await self.chat_recorder.end_session('COMPLETED', name=session_name)
                
                return {
                    "success": True,
                    "experiment_id": self.experiment_id,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "response": response,
                    "tools_available": len(langchain_tools),
                    "tool_names": [tool.name for tool in langchain_tools],
                    "nodes_created": tool_usage_tracker["create_experiment_node_count"],
                    "safeguard_triggered": nodes_created == 0
                }
            
        finally:
            # Always end chat session if it was started
            if self.chat_recorder:
                await self.chat_recorder.end_session('COMPLETED', name="Experiment Session")


async def run_experiment_with_ai(experiment_id: str, experiment_yaml: str, 
                                mcp_server, openai_api_key: Optional[str] = None, 
                                experiment_context: Optional[Dict[str, Any]] = None,
                                client=None) -> Dict[str, Any]:
    """
    Run an experiment with AI that has access to MCP tools.
    
    This is the main entry point for running AI-powered experiments with full
    access to Plexus MCP tools.
    
    Args:
        experiment_id: The experiment ID
        experiment_yaml: The experiment YAML configuration
        mcp_server: The MCP server instance
        openai_api_key: Optional OpenAI API key
        experiment_context: Optional experiment context with known information
        
    Returns:
        Dictionary with execution results
    """
    logger.info(f"Starting AI-powered experiment run: {experiment_id}")
    
    try:
        # Ensure client is included in experiment context for MCP tools
        if experiment_context is None:
            experiment_context = {}
        if client and 'client' not in experiment_context:
            experiment_context['client'] = client
        
        # Create and set up the AI runner
        runner = ExperimentAIRunner(experiment_id, mcp_server, client, openai_api_key, experiment_context)
        
        setup_success = await runner.setup(experiment_yaml)
        if not setup_success:
            return {
                "success": False,
                "error": "Failed to set up AI runner",
                "experiment_id": experiment_id
            }
        
        # Run the AI with tools
        result = await runner.run_ai_with_tools()
        
        logger.info(f"AI experiment run completed: {result.get('success', False)}")
        return result
        
    except Exception as e:
        logger.error(f"Error in AI experiment run: {e}")
        return {
            "success": False,
            "error": str(e),
            "experiment_id": experiment_id
        }
