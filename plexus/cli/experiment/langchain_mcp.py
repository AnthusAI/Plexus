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
from .chat_recorder import ExperimentChatRecorder, LangChainChatRecorderHook

logger = logging.getLogger(__name__)


class MCPTool(BaseModel):
    """LangChain-compatible tool that wraps an MCP tool."""
    name: str
    description: str
    args_schema: Optional[type] = None
    func: Callable[[Dict[str, Any]], str]
    
    def run(self, **kwargs) -> str:
        """Run the tool with the given arguments."""
        return self.func(kwargs)
    
    async def arun(self, **kwargs) -> str:
        """Async version of run."""
        return self.run(**kwargs)


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
                        import json
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
                    import concurrent.futures
                    import threading
                    
                    # Run the async call in a separate thread with its own event loop
                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(
                                self.mcp_client.call_tool(tool_name, args)
                            )
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
                        result = loop.run_until_complete(
                            self.mcp_client.call_tool(tool_name, args)
                        )
                    finally:
                        loop.close()
                
                # Record tool response FIRST - before any early returns
                if self.chat_recorder:
                    try:
                        # Look up the corresponding tool call ID
                        tool_call_id = self.pending_tool_calls.get(tool_name)
                        if tool_call_id:
                            logger.info(f"MCP WRAPPER: Recording response for {tool_name} (call_id: {tool_call_id})")
                            
                            # Record tool response asynchronously 
                            import threading
                            def record_response():
                                try:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    response_id = loop.run_until_complete(
                                        self.chat_recorder.record_tool_response(
                                            tool_name=tool_name,
                                            response=result if isinstance(result, dict) else {'result': str(result)},
                                            parent_message_id=tool_call_id,
                                            description=f"Response from {tool_name}"
                                        )
                                    )
                                    loop.close()
                                    logger.info(f"MCP WRAPPER: Successfully recorded tool response {response_id}")
                                    
                                    # Clean up the pending call
                                    if tool_name in self.pending_tool_calls:
                                        del self.pending_tool_calls[tool_name]
                                        
                                except Exception as e:
                                    logger.error(f"MCP WRAPPER: Error recording tool response: {e}")
                            
                            threading.Thread(target=record_response, daemon=True).start()
                        else:
                            logger.warning(f"MCP WRAPPER: No tool call ID found for {tool_name} response")
                    except Exception as e:
                        logger.error(f"MCP WRAPPER: Error in response recording setup: {e}")
                
                # Format the result for LangChain - preserve full response for accurate analysis
                def format_response(result_data):
                    """Format the result without truncation for accurate AI analysis."""
                    # The AI context management should be done at the LLM level, not by truncating tool results
                    # This allows the AI to see the full data and make informed decisions
                    if isinstance(result_data, dict):
                        # Return the JSON string representation for consistent parsing
                        import json
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
        # Use passed openai_api_key parameter first, then fallback to loading from config
        self.openai_api_key = openai_api_key if openai_api_key else self._get_openai_key()
        logger.info(f"AI Runner initialized with OpenAI key: {'Yes' if self.openai_api_key else 'No'}")
        self.experiment_config = None
        self.mcp_adapter = None
        self.experiment_context = experiment_context or {}
        self.chat_recorder = None
    
    def _get_openai_key(self) -> Optional[str]:
        """Get OpenAI API key using Plexus configuration system."""
        try:
            from plexus.config.loader import load_config
            load_config()  # This loads config and sets environment variables
            
            import os
            key = os.getenv('OPENAI_API_KEY')
            logger.info(f"OpenAI key check: {'Found' if key else 'Not found'}")
            return key
        except Exception as e:
            logger.warning(f"Failed to load configuration: {e}")
            import os
            key = os.getenv('OPENAI_API_KEY')
            logger.info(f"OpenAI key fallback: {'Found' if key else 'Not found'}")
            return key
    
    async def setup(self, experiment_yaml: str):
        """Set up the AI runner with experiment configuration."""
        try:
            # Parse experiment YAML
            self.experiment_config = yaml.safe_load(experiment_yaml)
            logger.info(f"Loaded experiment config for {self.experiment_id}")
            
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
        """Get the exploration prompt from the experiment config."""
        if not self.experiment_config:
            base_prompt = "Explore and analyze the available tools and data."
        else:
            base_prompt = self.experiment_config.get('exploration', 
                "Explore and analyze the available tools and data.")
        
        # Create context section with known experiment information
        context_section = ""
        if self.experiment_context:
            context_section = f"""
=== EXPERIMENT CONTEXT ===
You are working with the following experiment:
- Experiment ID: {self.experiment_context.get('experiment_id', 'Unknown')}
- Scorecard: {self.experiment_context.get('scorecard_name', 'Unknown')}
- Score: {self.experiment_context.get('score_name', 'Unknown')}
- Nodes: {self.experiment_context.get('node_count', 0)}
- Versions: {self.experiment_context.get('version_count', 0)}

You already know this information, so you don't need to look it up. Focus on analyzing and improving this specific experiment.
==========================

"""
        
        # Enhanced prompt with context and tool guidance
        enhanced_prompt = f"""{context_section}{base_prompt}

CRITICAL: You MUST use the Plexus MCP tools to analyze the experiment and CREATE new experiment nodes. DO NOT provide a text-only response.

REQUIRED ACTIONS (you must complete ALL of these):
1. **First**: Call `plexus_feedback_summary` with scorecard_name="{self.experiment_context.get('scorecard_name', 'Unknown')}" and score_name="{self.experiment_context.get('score_name', 'Unknown')}" to get performance data
2. **Second**: Call `plexus_score_info` with the same scorecard and score names to get configuration details
3. **Third**: Call `get_experiment_tree` with experiment_id="{self.experiment_context.get('experiment_id', 'Unknown')}" to understand current experiment structure
4. **Fourth**: Based on the analysis, create NEW experiment nodes for different hypotheses using `create_experiment_node` tool
5. **Fifth**: Each new node should test a specific hypothesis to improve the identified weaknesses

EXPERIMENT NODE CREATION GUIDELINES:
- Create 2-3 experiment nodes with DISTINCT hypotheses that address different performance issues
- For each node, provide a clear hypothesis description that explains both the goal and the method
- Optionally provide a short, distinctive node name (will be auto-generated if not provided)

**Recommended hypothesis format:**
"GOAL: [What specific performance issue you're trying to fix]
METHOD: [Exact implementation approach and configuration changes]"

Example:
"GOAL: Reduce false positives in medical query classification by 15%
METHOD: Add medical domain-specific keywords to the classification prompt in the first LLM node and increase confidence threshold from 0.7 to 0.85"

- The YAML configuration should implement the specific method described in the hypothesis
- Focus on different improvement strategies: prompt engineering, threshold tuning, model parameters, architectural changes, etc.
- Don't worry about perfect formatting - the system will handle auto-generation of names and validation

You cannot complete this task without using these tools. The goal is to generate actionable experiment variations, not just recommendations.
"""
        return enhanced_prompt
    
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
                
                # Create chat recorder with node association (or None if no root node)
                self.chat_recorder = ExperimentChatRecorder(self.client, self.experiment_id, root_node_id)
                
                # Always try to start a session, even without node association
                logger.info(f"Starting chat session for experiment {self.experiment_id} with node {root_node_id}")
                session_id = await self.chat_recorder.start_session(self.experiment_context)
                if session_id:
                    logger.info(f"Successfully started chat recording session: {session_id}")
                else:
                    logger.error("Failed to start chat recording session - chat will not be recorded")
            
            if not self.openai_api_key:
                error_msg = "OpenAI API key not available"
                if self.chat_recorder:
                    await self.chat_recorder.record_system_message(f"Error: {error_msg}")
                    await self.chat_recorder.end_session('ERROR')
                return {
                    "success": False,
                    "error": error_msg,
                    "suggestion": "Set OPENAI_API_KEY environment variable or pass it to the runner"
                }
            
            # Import LangChain components
            try:
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
                    await self.chat_recorder.end_session('ERROR')
                return {
                    "success": False,
                    "error": error_msg,
                    "suggestion": "Install langchain: pip install langchain openai"
                }
            
            # Create custom callback for chat recording
            class ChatRecordingCallback(BaseCallbackHandler):
                """Custom callback to record LLM messages and tool calls."""
                
                def __init__(self, recorder, mcp_adapter=None):
                    super().__init__()
                    self.recorder = recorder
                    self.tool_call_messages = {}
                    self.current_run_messages = {}
                    self.mcp_adapter = mcp_adapter  # Reference to adapter for storing tool call IDs
                    logger.info("CALLBACK INIT: ChatRecordingCallback initialized")
                
                def on_chain_start(self, serialized, inputs, **kwargs):
                    """Called when chain starts - test if callback is working."""
                    logger.info(f"CALLBACK TEST: Chain starting - callback is working!")
                
                def on_agent_action(self, action, **kwargs):
                    """Called when agent takes an action - this should capture tool calls."""
                    run_id = kwargs.get('run_id')
                    logger.info(f"CALLBACK TEST: Agent action detected - tool: {action.tool}, run_id: {run_id}")
                    logger.info(f"CALLBACK TEST: Tool input: {action.tool_input}")
                    
                    if self.recorder:
                        try:
                            import threading
                            tool_call_id = None
                            
                            def record_action():
                                nonlocal tool_call_id
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                tool_call_id = loop.run_until_complete(
                                    self.recorder.record_tool_call(
                                        tool_name=action.tool,
                                        parameters=action.tool_input if isinstance(action.tool_input, dict) else {'input': str(action.tool_input)},
                                        description=f"Agent calling tool: {action.tool}"
                                    )
                                )
                                loop.close()
                            
                            thread = threading.Thread(target=record_action)
                            thread.start()
                            thread.join()
                            
                            # Store the tool call ID for later use in on_tool_end and MCP wrapper
                            if tool_call_id and run_id:
                                self.tool_call_messages[run_id] = (tool_call_id, action.tool)
                                logger.info(f"CALLBACK TEST: Stored tool call {tool_call_id} for run {run_id}")
                                
                                # Also store in MCP adapter for direct tool response recording
                                if self.mcp_adapter:
                                    self.mcp_adapter.pending_tool_calls[action.tool] = tool_call_id
                                    logger.info(f"MCP ADAPTER: Stored tool call {tool_call_id} for {action.tool}")
                            
                        except Exception as e:
                            logger.error(f"CALLBACK ERROR: Failed to record agent action: {e}")
                
                def on_chain_end(self, outputs, **kwargs):
                    """Called when a chain ends - this might capture tool responses."""
                    run_id = kwargs.get('run_id')
                    logger.info(f"CALLBACK TEST: Chain end - run_id: {run_id}, outputs: {str(outputs)[:200]}...")
                    
                    # Check if this is a tool response by looking for matching tool call
                    if self.recorder and run_id in self.tool_call_messages:
                        tool_call_id, tool_name = self.tool_call_messages[run_id]
                        logger.info(f"CALLBACK TEST: Found tool response for {tool_name} (call_id: {tool_call_id})")
                        
                        try:
                            import threading
                            response_id = None
                            
                            def record_response_sync():
                                nonlocal response_id
                                try:
                                    new_loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(new_loop)
                                    
                                    response_id = new_loop.run_until_complete(
                                        self.recorder.record_tool_response(
                                            tool_name=tool_name,
                                            response=outputs if isinstance(outputs, dict) else {'result': str(outputs)},
                                            parent_message_id=tool_call_id,
                                            description=f"Tool {tool_name} response"
                                        )
                                    )
                                    new_loop.close()
                                    logger.info(f"CALLBACK TEST: Successfully recorded tool response {response_id}")
                                    
                                except Exception as e:
                                    logger.error(f"CALLBACK ERROR: Failed to record tool response in thread: {e}")
                            
                            thread = threading.Thread(target=record_response_sync)
                            thread.start()
                            thread.join()
                            
                            # Clean up the stored tool call info
                            del self.tool_call_messages[run_id]
                            
                        except Exception as e:
                            logger.error(f"CALLBACK ERROR: Failed to record tool response: {e}")

                def on_agent_finish(self, finish, **kwargs):
                    """Called when agent finishes - this should capture tool responses.""" 
                    logger.info(f"CALLBACK TEST: Agent finished - output: {finish.return_values}")
                    # For agents, the finish contains the final result but not individual tool responses
                    # Tool responses are handled in on_chain_end now
                
                def on_llm_start(self, serialized, prompts, **kwargs):
                    """Record when LLM starts - capture the input prompts."""
                    logger.info(f"CALLBACK TEST: LLM starting with {len(prompts) if prompts else 0} prompts")

                def on_llm_end(self, response, **kwargs):
                    """Record when LLM ends - might capture tool results."""
                    run_id = kwargs.get('run_id')
                    logger.info(f"CALLBACK TEST: LLM end - run_id: {run_id}, response: {str(response)[:200]}...")
                    
                    # Check if this LLM response contains tool results we can capture
                    if hasattr(response, 'generations') and response.generations:
                        for gen_list in response.generations:
                            for gen in gen_list:
                                if hasattr(gen, 'text') and gen.text:
                                    logger.info(f"CALLBACK TEST: LLM generated text: {gen.text[:100]}...")
                                    # Look for tool output patterns in the generated text
                            try:
                                # Run async code synchronously in callback
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                result = loop.run_until_complete(
                                    self.recorder.record_user_message(f"Prompt {i+1}: {prompt}")
                                )
                                loop.close()
                                logger.info(f"CHAT CALLBACK: Successfully recorded prompt as message {result}")
                            except Exception as e:
                                logger.error(f"CHAT CALLBACK: Error recording LLM prompt: {e}")
                    else:
                        logger.warning(f"CHAT CALLBACK: No recorder or prompts (recorder: {bool(self.recorder)}, prompts: {bool(prompts)})")
                
                def on_llm_end(self, response, **kwargs):
                    """Record when LLM ends - capture the response."""
                    logger.info(f"CHAT CALLBACK: LLM ended with response type: {type(response)}")
                    if self.recorder and response:
                        try:
                            # Extract the actual text response
                            if hasattr(response, 'generations') and response.generations:
                                logger.info(f"CHAT CALLBACK: Found {len(response.generations)} generation groups")
                                for i, generation_list in enumerate(response.generations):
                                    logger.info(f"CHAT CALLBACK: Generation group {i} has {len(generation_list)} generations")
                                    for j, generation in enumerate(generation_list):
                                        if hasattr(generation, 'text'):
                                            logger.info(f"CHAT CALLBACK: Recording assistant response: {generation.text[:100]}...")
                                            # Record as assistant message
                                            loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(loop)
                                            result = loop.run_until_complete(
                                                self.recorder.record_assistant_message(generation.text)
                                            )
                                            loop.close()
                                            logger.info(f"CHAT CALLBACK: Successfully recorded assistant message {result}")
                            else:
                                logger.warning(f"CHAT CALLBACK: Response has no generations attribute or empty generations")
                        except Exception as e:
                            logger.error(f"CHAT CALLBACK: Error recording LLM response: {e}")
                    else:
                        logger.warning(f"CHAT CALLBACK: No recorder or response (recorder: {bool(self.recorder)}, response: {bool(response)})")
                
                def on_tool_start(self, serialized, input_str, **kwargs):
                    """Record when a tool starts executing."""
                    if self.recorder:
                        tool_name = serialized.get('name', 'unknown_tool')
                        run_id = kwargs.get('run_id')
                        logger.info(f"CHAT RECORDER: Tool starting - {tool_name} with run_id {run_id}")
                        logger.info(f"CHAT RECORDER: Tool input: {input_str}")
                        
                        try:
                            # Use the existing event loop instead of creating a new one
                            import threading
                            
                            def record_sync():
                                try:
                                    # Create a new event loop for this thread
                                    new_loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(new_loop)
                                    
                                    tool_call_id = new_loop.run_until_complete(
                                        self.recorder.record_tool_call(
                                            tool_name=tool_name,
                                            parameters=input_str if isinstance(input_str, dict) else {'input': str(input_str)},
                                            description=f"AI is calling tool: {tool_name}"
                                        )
                                    )
                                    new_loop.close()
                                    
                                    if run_id and tool_call_id:
                                        self.current_run_messages[run_id] = (tool_call_id, tool_name)
                                        logger.info(f"CHAT RECORDER: Recorded tool call {tool_call_id} for run {run_id}")
                                    
                                except Exception as e:
                                    logger.error(f"CHAT RECORDER: Error in record_sync: {e}")
                            
                            # Run in a separate thread to avoid event loop conflicts
                            thread = threading.Thread(target=record_sync)
                            thread.start()
                            thread.join()  # Wait for completion
                            
                        except Exception as e:
                            logger.error(f"CHAT RECORDER: Error recording tool call: {e}")
                
                def on_tool_end(self, output, **kwargs):
                    """Record when a tool finishes executing."""
                    run_id = kwargs.get('run_id')
                    logger.info(f"CALLBACK TEST: on_tool_end called - run_id: {run_id}")
                    logger.info(f"CALLBACK TEST: Tool output type: {type(output)}, content: {str(output)[:200]}...")
                    
                    if self.recorder:
                        # Check both possible storage locations for tool call info
                        tool_info = self.tool_call_messages.get(run_id) or self.current_run_messages.get(run_id)
                        
                        if tool_info:
                            tool_call_id, tool_name = tool_info
                            logger.info(f"CALLBACK TEST: Found matching tool call {tool_call_id} for tool {tool_name}")
                            
                            try:
                                import threading
                                response_id = None
                                
                                def record_response_sync():
                                    nonlocal response_id
                                    try:
                                        new_loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(new_loop)
                                        
                                        response_id = new_loop.run_until_complete(
                                            self.recorder.record_tool_response(
                                                tool_name=tool_name,
                                                response=output if isinstance(output, dict) else {'result': str(output)},
                                                parent_message_id=tool_call_id,
                                                description=f"Tool {tool_name} response"
                                            )
                                        )
                                        new_loop.close()
                                        logger.info(f"CALLBACK TEST: Successfully recorded tool response {response_id}")
                                        
                                    except Exception as e:
                                        logger.error(f"CALLBACK ERROR: Failed to record tool response in thread: {e}")
                                
                                thread = threading.Thread(target=record_response_sync)
                                thread.start()
                                thread.join()
                                
                                # Clean up the stored tool call info
                                if run_id in self.tool_call_messages:
                                    del self.tool_call_messages[run_id]
                                if run_id in self.current_run_messages:
                                    del self.current_run_messages[run_id]
                                
                            except Exception as e:
                                logger.error(f"CALLBACK ERROR: Failed to record tool response: {e}")
                        else:
                            logger.warning(f"CALLBACK WARNING: No tool call info found for run_id {run_id}")
                            logger.warning(f"CALLBACK WARNING: Available tool calls: {list(self.tool_call_messages.keys())}")
                            logger.warning(f"CALLBACK WARNING: Available current runs: {list(self.current_run_messages.keys())}")
                    else:
                        logger.warning("CALLBACK WARNING: No recorder available for tool response")
            
            # Create callback if recorder is available
            callback = None
            
            # Set up the AI model - use gpt-4o which has larger context window
            llm = ChatOpenAI(
                model="gpt-4o",  # 128k context window
                temperature=0.7,
                openai_api_key=self.openai_api_key,
                max_tokens=4000  # Limit response length to preserve context
            )
            
            # Convert MCP tools to LangChain tools
            async with self.mcp_server.connect({'name': f'AI Agent for {self.experiment_id}'}) as mcp_client:
                adapter = LangChainMCPAdapter(mcp_client)
                mcp_tools = await adapter.load_tools()
                
                # Set up chat recording in the adapter
                adapter.chat_recorder = self.chat_recorder
                
                # Create callback with adapter reference
                callback = ChatRecordingCallback(self.chat_recorder, adapter) if self.chat_recorder else None
                
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
                    known_tool_schemas = {
                        'plexus_score_info': {
                            'score_identifier': 'Score identifier (ID, name, key, or external ID)',
                            'scorecard_identifier': 'Optional scorecard identifier to narrow search',
                            'version_id': 'Optional specific version ID',
                            'include_versions': 'Include detailed version information'
                        },
                        'plexus_feedback_summary': {
                            'scorecard_name': 'Name of the scorecard',
                            'score_name': 'Name of the score',
                            'days': 'Number of days back to analyze',
                            'output_format': 'Output format - json or yaml'
                        },
                        'plexus_predict': {
                            'scorecard_name': 'Name of the scorecard containing the score',
                            'score_name': 'Name of the specific score to run predictions with',
                            'item_id': 'ID of a single item to predict on',
                            'item_ids': 'Comma-separated list of item IDs to predict on',
                            'include_input': 'Whether to include the original input text',
                            'include_trace': 'Whether to include detailed execution trace',
                            'output_format': 'Output format - json or yaml',
                            'no_cache': 'If True, disable local caching entirely',
                            'yaml_only': 'If True, load only from local YAML files'
                        },
                        'create_experiment_node': {
                            'experiment_id': 'ID of the experiment to add the node to',
                            'yaml_configuration': 'YAML configuration for the new hypothesis',
                            'hypothesis_description': 'Structured description: "GOAL: [what to improve]\\nMETHOD: [specific implementation]"',
                            'node_name': 'Optional: Short, distinctive name (auto-generated if not provided)',
                            'parent_node_id': 'Optional parent node ID (if None, creates child of root node)',
                            'initial_value': 'Optional initial computed value (defaults to hypothesis info)'
                        },
                        'get_experiment_tree': {
                            'experiment_id': 'ID of the experiment to analyze'
                        },
                        'update_node_version': {
                            'node_id': 'ID of the node to update',
                            'yaml_configuration': 'Updated YAML configuration',
                            'update_description': 'Description of what changed in this update',
                            'computed_value': 'Optional computed results (defaults to update info)'
                        }
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
                            else:
                                # Use kwargs as provided
                                result = func(kwargs)
                            
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
                
                # Set up memory
                memory = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
                
                # Create the agent - use STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION for multi-input tool support
                agent_kwargs = {
                    'tools': langchain_tools,
                    'llm': llm,
                    'agent': AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,  # Supports structured tools
                    'memory': memory,
                    'verbose': True,
                    'handle_parsing_errors': True,
                    'max_iterations': 15,  # Allow more iterations for tool usage
                    'early_stopping_method': "generate",  # Don't stop early
                    'return_intermediate_steps': True  # Get detailed execution info
                }
                
                # Add callback if available
                if callback:
                    agent_kwargs['callbacks'] = [callback]
                
                agent = initialize_agent(**agent_kwargs)
                
                # Get the exploration prompt
                prompt = self.get_exploration_prompt()
                logger.info(f"Running AI agent with {len(langchain_tools)} tools")
                
                # Record the initial system prompt
                if self.chat_recorder:
                    await self.chat_recorder.record_system_message(prompt)
                
                # Log the conversation history that will be sent to the AI model
                logger.info("="*60)
                logger.info("CONVERSATION HISTORY BEING SENT TO AI MODEL:")
                logger.info("="*60)
                logger.info(f"PROMPT:\n{prompt}")
                logger.info("-"*60)
                logger.info(f"AVAILABLE TOOLS: {[tool.name for tool in langchain_tools]}")
                logger.info("="*60)
                
                # Run the agent using invoke method (run is deprecated)
                result = agent.invoke({"input": prompt})
                
                # Extract the output from the result
                response = result.get("output", str(result))
                
                # Record the final AI response
                if self.chat_recorder:
                    await self.chat_recorder.record_assistant_message(response)
                    await self.chat_recorder.end_session('COMPLETED')
                
                return {
                    "success": True,
                    "experiment_id": self.experiment_id,
                    "prompt": prompt,
                    "response": response,
                    "tools_available": len(langchain_tools),
                    "tool_names": [tool.name for tool in langchain_tools]
                }
            
        except Exception as e:
            logger.error(f"Error running AI with tools: {e}")
            
            # Record error and end session if recorder is available
            if self.chat_recorder:
                await self.chat_recorder.record_system_message(f"Error occurred: {str(e)}")
                await self.chat_recorder.end_session('ERROR')
            
            return {
                "success": False,
                "error": str(e),
                "experiment_id": self.experiment_id
            }


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