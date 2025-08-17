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
from .conversation_flow import ConversationFlowManager, ConversationStage
from .mcp_tool import MCPTool
from .mcp_adapter import LangChainMCPAdapter
from .openai_compat import O3CompatibleChatOpenAI
from .tool_calling import extract_all_tool_calls, call_tool
from .chat_callbacks import ChatRecordingCallback

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
        # Use passed openai_api_key parameter first, then fallback to loading from config
        self.openai_api_key = openai_api_key if openai_api_key else self._get_openai_key()
        logger.info(f"AI Runner initialized with OpenAI key: {'Yes' if self.openai_api_key else 'No'}")
        self.experiment_config = None
        self.mcp_adapter = None
        self.experiment_context = experiment_context or {}
        self.chat_recorder = None
        self.conversation_flow = None
    
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
            
            # Initialize conversation flow manager with context
            self.conversation_flow = ConversationFlowManager(self.experiment_config, self.experiment_context)
            logger.info("Initialized intelligent conversation flow manager")
            
            # Set up MCP adapter
            async with self.mcp_server.connect({'name': f'AI Runner for {self.experiment_id}'}) as mcp_client:
                self.mcp_adapter = LangChainMCPAdapter(mcp_client)
                await self.mcp_adapter.load_tools()
                logger.info(f"Set up MCP adapter with {len(self.mcp_adapter.tools)} tools")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up AI runner: {e}")
            return False
    
    def get_system_prompt(self) -> str:
        """Get the system prompt with context about the hypothesis engine and documentation."""
        # Core system context about the hypothesis engine
        system_prompt = """You are part of a hypothesis engine that is part of an automated experiment running process aimed at optimizing scorecard score configurations for an industrial machine learning system. This system is organized around scorecards and scores, where each score represents a specific task like classification or extraction.

Our system has the ability to run evaluations to measure the performance of a given score configuration versus ground truth labels. The ground truth labels come from feedback edits provided by humans, creating a reinforcement learning feedback loop system.

Your specific role in this process is the hypothesis engine, which is responsible for coming up with valuable hypotheses for how to make changes to score configurations in order to better align with human feedback.

## Score YAML Format Documentation

"""
        
        # Add score YAML format documentation if available
        score_yaml_docs = self.experiment_context.get('score_yaml_format_docs') if self.experiment_context else None
        if score_yaml_docs:
            system_prompt += f"""{score_yaml_docs}

## Feedback Alignment Process Documentation

"""
        
        # Add feedback alignment documentation if available
        feedback_docs = self.experiment_context.get('feedback_alignment_docs') if self.experiment_context else None
        if feedback_docs:
            system_prompt += f"""{feedback_docs}

"""
        
        # Add the hypothesis engine task description
        system_prompt += """## Your Task: Hypothesis Generation

Your task is to analyze feedback patterns and generate hypotheses for improving score alignment. You should:

1. **CRITICAL: Use Provided Context**: The user prompt will provide specific scorecard_name and score_name values. You MUST use these exact values when calling feedback tools like plexus_feedback_summary and plexus_feedback_find. Do NOT use empty strings or try to discover these names yourself.

2. **Examine Feedback Details**: Use tools to look closely into feedback edits for different squares in the confusion matrix (e.g., cases where we predicted "yes" but the answer was "no" or vice versa).

3. **Analyze Individual Items**: Look at details of specific calls/items to understand how mistakes were made.

4. **Focus on Mistakes**: Specifically examine the mistakes identified in feedback analysis to understand root causes.

5. **Generate Varied Hypotheses**: Create distinct improvement ideas:
   - **Iterative**: Low-risk, incremental improvements (most valuable)
   - **Creative**: Moderate creativity, rethinking aspects of the approach
   - **Revolutionary**: High-risk, complete problem reframing (Hail Mary attempts)

6. **Prioritize Incremental**: Focus primarily on lower-risk, less creative, incremental improvements like adding policies inferred from human feedback patterns.

Your hypotheses should be:
- **Distinct**: Each idea should be genuinely different
- **Specific**: Include concrete configuration changes
- **Evidence-based**: Grounded in actual feedback patterns
- **Conceptual**: Focus on the idea, NOT the implementation details
- **Non-quantified**: Do NOT include percentage targets or specific numeric goals (e.g., "reduce by 30%") - focus on directional improvements

**IMPORTANT: When creating experiment nodes with create_experiment_node:**
- DO NOT include yaml_configuration parameter
- Focus on clear hypothesis_description and node_name
- YAML implementation will be handled in a separate future step
- Your job is to generate the concepts, not implement them

Use the available tools to examine feedback data and item details before generating hypotheses. Think carefully about what might actually be wrong and how to actually improve it."""

        return system_prompt

    def get_user_prompt(self) -> str:
        """Get the user prompt with current score configuration and feedback summary."""
        if not self.experiment_context:
            return "Please analyze the current score configuration and generate improvement hypotheses."
        
        user_prompt = f"""**Current Experiment Context:**
- Experiment ID: {self.experiment_context.get('experiment_id', 'Unknown')}
- Scorecard: {self.experiment_context.get('scorecard_name', 'Unknown')}
- Score: {self.experiment_context.get('score_name', 'Unknown')}

"""
        
        # Add current score configuration if available
        score_config = self.experiment_context.get('current_score_config')
        if score_config:
            user_prompt += f"""**Current Score Configuration (Champion Version):**

```yaml
{score_config}
```

"""
        
        # Add feedback summary if available
        feedback_summary = self.experiment_context.get('feedback_summary')
        if feedback_summary:
            user_prompt += f"""**Performance Analysis Summary:**

{feedback_summary}

"""
        
        user_prompt += f"""**Your Task:**

Please analyze the current score configuration and feedback patterns to generate 2-3 distinct hypotheses for improving alignment with human feedback.

**CRITICAL: When using feedback tools, you MUST use these exact names:**
- scorecard_name: "{self.experiment_context.get('scorecard_name', 'Unknown')}"
- score_name: "{self.experiment_context.get('score_name', 'Unknown')}"

**Required Analysis Steps:**
1. FIRST: Use plexus_feedback_summary with scorecard_name="{self.experiment_context.get('scorecard_name', 'Unknown')}" and score_name="{self.experiment_context.get('score_name', 'Unknown')}"
2. Use plexus_feedback_find to examine false positives and false negatives with the same scorecard_name and score_name
3. Use plexus_item_info to examine specific problematic items
4. Create experiment nodes with your hypotheses

**Example first tool call:**
plexus_feedback_summary(scorecard_name="{self.experiment_context.get('scorecard_name', 'Unknown')}", score_name="{self.experiment_context.get('score_name', 'Unknown')}", days=30)

For each hypothesis, use the `create_experiment_node` tool with:
- experiment_id: {self.experiment_context.get('experiment_id', 'EXPERIMENT_ID')}
- A clear hypothesis description following this format: "GOAL: [specific target - NO quantification] | METHOD: [exact changes]"
- A complete YAML configuration implementing your proposed changes
- A descriptive node name

Focus on evidence-based improvements that address the specific issues identified in the feedback analysis."""

        return user_prompt
    
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
                    await self.chat_recorder.end_session('ERROR')
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
                    await self.chat_recorder.end_session('ERROR')
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
            }
            
            # Only add completion tokens for newer models like o3
            if model_name in ["o3", "gpt-4.1", "gpt-5"]:
                model_config["max_completion_tokens"] = 4000
            else:
                model_config["max_tokens"] = 4000
            
            # Use the extracted O3-compatible model
            
            llm = O3CompatibleChatOpenAI(**model_config)
            
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
                        'plexus_feedback_find': {
                            'scorecard_name': 'Name of the scorecard containing the score',
                            'score_name': 'Name of the specific score to search feedback for',
                            'initial_value': 'Optional filter for the original AI prediction value',
                            'final_value': 'Optional filter for the corrected human value',
                            'limit': 'Maximum number of feedback items to return',
                            'days': 'Number of days back to search',
                            'output_format': 'Output format - json or yaml',
                            'prioritize_edit_comments': 'Whether to prioritize feedback items with edit comments'
                        },
                        'plexus_item_info': {
                            'item_id': 'The unique ID of the item OR an external identifier value'
                        },
                        'plexus_scorecard_info': {
                            'scorecard_identifier': 'The identifier for the scorecard (can be ID, name, key, or external ID)'
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
                            'experiment_id': 'The unique ID of the experiment',
                            'hypothesis_description': 'Clear description following format: GOAL: [target - no quantification] | METHOD: [changes]',
                            'node_name': 'Descriptive name for the hypothesis node (optional)',
                            'yaml_configuration': 'Optional YAML configuration - can be added later'
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
                
                # Get the system and user prompts first
                system_prompt = self.get_system_prompt()
                user_prompt = self.get_user_prompt()
                logger.info(f"Generated prompts: system={len(system_prompt)} chars, user={len(user_prompt)} chars")
                
                # Simple conversation history - just a list of messages
                from langchain.schema import SystemMessage, HumanMessage, AIMessage
                conversation_history = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ]
                
                # Tool calling logic is now in separate module
                
                logger.info(f"Running AI agent with {len(langchain_tools)} tools")
                
                # Record the system prompt and user prompt separately
                if self.chat_recorder:
                    await self.chat_recorder.record_system_message(system_prompt)
                    # Record user message with the current configuration and task
                    user_message_id = await self.chat_recorder.record_message(
                        role='USER',
                        content=user_prompt,
                        message_type='MESSAGE'
                    )
                
                # Log the conversation history that will be sent to the AI model
                logger.info("="*60)
                logger.info("CONVERSATION HISTORY BEING SENT TO AI MODEL:")
                logger.info("="*60)
                logger.info(f"SYSTEM: {system_prompt[:300]}{'...' if len(system_prompt) > 300 else ''}")
                logger.info("-" * 30)
                logger.info(f"USER: {user_prompt[:300]}{'...' if len(user_prompt) > 300 else ''}")
                logger.info("-"*60)
                logger.info(f"AVAILABLE TOOLS: {[tool.name for tool in langchain_tools]}")
                logger.info("="*60)
                
                # Track tool usage for safeguards
                tool_usage_tracker = {"create_experiment_node_count": 0}
                
                # Create enhanced callback that tracks create_experiment_node usage
                if callback:
                    original_on_agent_action = callback.on_agent_action
                    def enhanced_on_agent_action(action, **kwargs):
                        if action.tool == "create_experiment_node":
                            tool_usage_tracker["create_experiment_node_count"] += 1
                            logger.info(f"TOOL TRACKER: create_experiment_node called #{tool_usage_tracker['create_experiment_node_count']}")
                        return original_on_agent_action(action, **kwargs)
                    callback.on_agent_action = enhanced_on_agent_action
                
                # SIMPLE CONVERSATION LOOP: Just chat with the AI
                response = ""
                nodes_created = 0
                max_conversation_rounds = 10  # Safety limit
                
                # Start with initial prompt
                next_message = "Begin analyzing the current score configuration and feedback patterns to generate hypotheses. You have access to all the necessary context and tools."
                
                for conversation_round in range(max_conversation_rounds):
                    logger.info(f"CONVERSATION ROUND {conversation_round + 1}/{max_conversation_rounds}")
                    
                    # Use the message we have (either initial prompt or guidance from previous round)
                    if conversation_round == 0:
                        logger.info(f"FIRST ROUND: Prompting AI to start")
                    else:
                        logger.info(f"ROUND {conversation_round + 1}: Sending message ({len(next_message)} chars)")
                    
                    # Add the message to conversation (guidance messages are SystemMessages)
                    if conversation_round == 0:
                        # First message is the user prompt
                        conversation_history.append(HumanMessage(content=next_message))
                    else:
                        # Subsequent messages are system guidance
                        conversation_history.append(SystemMessage(content=next_message))
                    
                    # Note: guidance messages are recorded when they're generated (line 666), not when they're sent
                    
                    # Log conversation state
                    logger.info(f"CONVERSATION HISTORY: {len(conversation_history)} messages")
                    for i, msg in enumerate(conversation_history):
                        logger.info(f"  Message {i}: {type(msg).__name__} ({len(msg.content)} chars)")
                    
                    # Call the LLM directly with conversation history
                    logger.info(f"CALLING LLM directly with {len(conversation_history)} messages")
                    
                    try:
                        ai_response = llm.invoke(conversation_history)
                        logger.info(f"RAW AI RESPONSE CONTENT: {ai_response.content if hasattr(ai_response, 'content') else 'NO CONTENT ATTR'}")
                        
                        response = ai_response.content if hasattr(ai_response, 'content') else str(ai_response)
                        
                        if not response:
                            logger.error("AI RESPONSE IS EMPTY!")
                            logger.error(f"Full AI response object: {ai_response}")
                            response = "No response from AI"
                        
                        logger.info(f"PROCESSED AI RESPONSE ({len(response)} chars): {response}")
                        logger.info(f"FULL AI RESPONSE: {response}")
                        
                    except Exception as e:
                        logger.error(f"ERROR calling LLM: {e}")
                        logger.error(f"Exception type: {type(e)}")
                        response = f"Error calling LLM: {e}"
                    
                    # Add AI response to conversation
                    conversation_history.append(AIMessage(content=response))
                    
                    # Record AI response
                    if self.chat_recorder:
                        await self.chat_recorder.record_message(
                            role='ASSISTANT',
                            content=response,
                            message_type='MESSAGE'
                        )
                    
                    # Check if AI wants to call tools
                    logger.info(f"CHECKING FOR TOOL CALLS in response: {response[:500]}...")
                    tool_calls = extract_all_tool_calls(response, mcp_tools)
                    
                    if tool_calls:
                        logger.info(f"FOUND {len(tool_calls)} TOOL CALL(S)")
                        
                        # Process each tool call with error feedback
                        all_tool_results = []
                        for tool_name, tool_kwargs in tool_calls:
                            logger.info(f"PROCESSING TOOL CALL: {tool_name} with {tool_kwargs}")
                            
                            try:
                                tool_result = call_tool(tool_name, tool_kwargs, mcp_tools)
                                logger.info(f"TOOL RESULT: {tool_result[:500]}...")
                                
                                # Check if the result indicates an error and provide helpful feedback
                                if tool_result and isinstance(tool_result, str):
                                    if tool_result.startswith("Error calling") or (tool_result.startswith("Tool") and "not found" in tool_result):
                                        # Format error with helpful guidance
                                        error_feedback = f"⚠️ **Tool Error**: {tool_result}\n\n**Suggestion**: Please check your parameters and try again. Common issues:\n- Missing required parameters\n- Incorrect parameter names or values\n- Invalid tool name\n\nYou can retry this tool call in your next response."
                                        all_tool_results.append(f"Tool {tool_name} error: {error_feedback}")
                                        logger.warning(f"TOOL CALL FAILED: {tool_result}")
                                    else:
                                        # Success!
                                        all_tool_results.append(f"Tool {tool_name} result: {tool_result}")
                                else:
                                    # Non-string result, assume success
                                    all_tool_results.append(f"Tool {tool_name} result: {tool_result}")
                                    
                            except Exception as e:
                                # Handle exceptions with clear feedback
                                error_message = str(e)
                                logger.error(f"TOOL CALL EXCEPTION: {error_message}")
                                
                                error_feedback = f"⚠️ **Tool Exception**: {error_message}\n\n**Suggestion**: There was an unexpected error executing this tool. Please:\n- Verify all required parameters are provided\n- Check parameter types and formats\n- Try the tool call again with corrected parameters\n\nYou can retry this tool call in your next response."
                                all_tool_results.append(f"Tool {tool_name} error: {error_feedback}")
                                tool_result = error_feedback
                            
                            # Record tool call and response
                            if self.chat_recorder:
                                await self.chat_recorder.record_message(
                                    role='TOOL',
                                    content=f"{tool_name}({tool_kwargs})",
                                    message_type='TOOL_CALL'
                                )
                                await self.chat_recorder.record_message(
                                    role='TOOL',
                                    content=str(tool_result),
                                    message_type='TOOL_RESPONSE'
                                )
                            
                            # Track successful node creation only (exclude errors)
                            if tool_name == "create_experiment_node" and tool_result and not str(tool_result).startswith(("Error", "⚠️", "❌")):
                                tool_usage_tracker["create_experiment_node_count"] += 1
                                nodes_created = tool_usage_tracker["create_experiment_node_count"]
                                logger.info(f"TOOL TRACKER: create_experiment_node successfully called #{nodes_created}")
                            elif tool_name == "create_experiment_node":
                                logger.info(f"TOOL TRACKER: create_experiment_node failed, not counting towards nodes_created")
                        
                        # Add all tool results to conversation
                        combined_results = "\n\n".join(all_tool_results)
                        conversation_history.append(HumanMessage(content=combined_results))
                        
                    else:
                        logger.info("NO TOOL CALLS DETECTED in AI response")
                    
                    # Update conversation flow state
                    if self.conversation_flow:
                        # Use both local tool calls and MCP adapter tools for comprehensive tracking
                        tools_used = [tool_name for tool_name, _ in tool_calls] if tool_calls else []
                        if hasattr(self.mcp_adapter, 'tools_called'):
                            tools_used.extend(list(self.mcp_adapter.tools_called))
                        
                        self.conversation_flow.update_state(
                            tools_used=tools_used,
                            response_content=response,
                            nodes_created=nodes_created
                        )
                        
                        logger.info(f"CONVERSATION FLOW: Round {conversation_round + 1} complete, {nodes_created} nodes created")
                        
                        # Check if we should continue the conversation
                        if self.conversation_flow.should_continue():
                            guidance = self.conversation_flow.get_next_guidance()
                            
                            if guidance:
                                logger.info(f"CONVERSATION FLOW: Providing guidance for stage {self.conversation_flow.state.stage.value}")
                                
                                # Record the guidance prompt
                                if self.chat_recorder:
                                    await self.chat_recorder.record_system_message(guidance)
                                
                                # Set up next round with guidance
                                next_message = guidance
                                continue  # Continue the conversation loop
                            else:
                                logger.info("CONVERSATION FLOW: No guidance available, continuing conversation")
                                break
                        else:
                            logger.info(f"CONVERSATION FLOW: should_continue=False after round {conversation_round + 1}")
                            break
                    else:
                        # No conversation flow, just run once
                        break
                
                # CONVERSATION COMPLETE: Handle completion summary and emergency fallback
                if self.conversation_flow:
                    logger.info(f"CONVERSATION ENDING: nodes_created={nodes_created}")
                    
                    # EMERGENCY FALLBACK: Force node creation if none exist
                    if nodes_created == 0:
                        logger.warning("EMERGENCY FALLBACK: Forcing node creation since none were created")
                        emergency_prompt = f"""
🚨 **EMERGENCY: CREATE NODES NOW** 🚨

The conversation is about to end but you have not created any experiment nodes yet.

**CRITICAL CONTEXT:**
- scorecard_name: "{self.experiment_context.get('scorecard_name', 'Unknown')}"
- score_name: "{self.experiment_context.get('score_name', 'Unknown')}"
- experiment_id: {self.experiment_context.get('experiment_id', 'EXPERIMENT_ID')}

You MUST create at least 2 experiment nodes before this conversation can end.

**IMMEDIATE ACTION REQUIRED:**
Use create_experiment_node tool with these parameters:
1. A conservative hypothesis targeting the specific feedback patterns you found
2. An aggressive hypothesis with more significant changes

**Example call:**
create_experiment_node(
    experiment_id="{self.experiment_context.get('experiment_id', 'EXPERIMENT_ID')}",
    hypothesis_description="GOAL: Reduce false positives for medication verification | METHOD: Add stricter verification requirements",
    node_name="Stricter Verification Requirements"
)

This is MANDATORY - the conversation cannot complete without nodes.
"""
                        # Force one final attempt at node creation
                        if self.chat_recorder:
                            self.chat_recorder.record_message_sync(
                                role='SYSTEM', 
                                content=emergency_prompt,
                                message_type='MESSAGE'
                            )
                        
                        # Add emergency prompt to conversation and get response
                        conversation_history.append(HumanMessage(content=emergency_prompt))
                        emergency_ai_response = llm.invoke(conversation_history)
                        emergency_result = {"output": emergency_ai_response.content}
                        emergency_response = emergency_result.get("output", str(emergency_result))
                        emergency_nodes = tool_usage_tracker["create_experiment_node_count"]
                        
                        if emergency_nodes > nodes_created:
                            response = emergency_response
                            nodes_created = emergency_nodes
                            logger.info(f"EMERGENCY SUCCESS: Created {emergency_nodes} nodes in fallback")
                        else:
                            logger.error("EMERGENCY FAILURE: Still no nodes created even in fallback")
                    
                    # Generate completion summary (always run, regardless of emergency fallback)
                    completion_summary = self.conversation_flow.get_completion_summary()
                    
                    # Add a programmatic explanation of why the conversation ended
                    termination_reason = f"""

## Experiment Session Complete

**Termination Reason:** {'No experiment nodes created despite multiple attempts' if nodes_created == 0 else f'{nodes_created} experiment nodes created successfully'}

**Session Summary:**
- Stage reached: {self.conversation_flow.state.stage.value}
- Total rounds: {self.conversation_flow.state.total_rounds}
- Tools used: {len(self.conversation_flow.state.tools_used)}
- Nodes created: {nodes_created}

**Next Steps:** {'Manual intervention required - AI failed to generate hypotheses' if nodes_created == 0 else 'Review generated hypotheses in the experiment dashboard'}
"""
                    
                    # Record the termination explanation
                    if self.chat_recorder:
                        self.chat_recorder.record_message_sync(
                            role='SYSTEM', 
                            content=termination_reason,
                            message_type='MESSAGE'
                        )
                    
                    completion_summary_with_reason = completion_summary + termination_reason
                    response += f"\n\n{completion_summary_with_reason}"
                    logger.info(f"CONVERSATION FLOW: Conversation complete - {completion_summary}")
                    logger.info(f"TERMINATION REASON: {termination_reason.strip()}")
                
                else:
                    logger.warning("CONVERSATION FLOW: No conversation flow manager available, using basic check")
                    if nodes_created == 0:
                        logger.warning("BASIC CHECK: No experiment nodes created")
                    else:
                        logger.info(f"BASIC CHECK: {nodes_created} experiment nodes created")
                
                # End the chat session (all messages are recorded automatically via callbacks)
                if self.chat_recorder:
                    await self.chat_recorder.end_session('COMPLETED')
                
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