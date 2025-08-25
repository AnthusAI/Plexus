"""
Experiment-specific StandardOperatingProcedureAgent implementation.

This module provides the ExperimentSOPAgent, which uses the general-purpose
StandardOperatingProcedureAgent to execute experiment hypothesis generation
procedures. It implements the experiment-specific behavior while delegating
the core SOP orchestration to the reusable base agent.

Architecture:
- ExperimentProcedureDefinition: Defines experiment-specific prompts, tools, and logic
- ExperimentFlowManager: Manages experiment conversation flow (exploration → synthesis → hypothesis)
- ExperimentChatRecorder: Records experiment conversations
- ExperimentSOPAgent: Convenience wrapper for experiment procedures
"""

import logging
from typing import Dict, Any, List, Optional
from .sop_agent_base import StandardOperatingProcedureAgent, ProcedureDefinition, FlowManager, ChatRecorder
from .experiment_prompts import ExperimentPrompts
from .conversation_flow import ConversationFlowManager
from .chat_recorder import ExperimentChatRecorder
from .mcp_adapter import LangChainMCPAdapter

logger = logging.getLogger(__name__)


class ExperimentProcedureDefinition:
    """
    Experiment-specific procedure definition for the StandardOperatingProcedureAgent.
    
    This class encapsulates all experiment-specific knowledge:
    - Experiment hypothesis generation prompts
    - Experiment tool scoping by phase
    - Experiment completion criteria
    - Experiment-specific guidance logic
    """
    
    def __init__(self):
        # Worker agent gets access to a curated subset of tools
        self.available_tools = [
            "plexus_feedback_find", 
            "create_experiment_node", 
            "stop_procedure"
        ]
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        """Get the experiment hypothesis generation system prompt."""
        return ExperimentPrompts.get_system_prompt(context)
    
    def get_sop_guidance_prompt(self, context: Dict[str, Any], state_data: Dict[str, Any]) -> str:
        """Get the SOP Agent guidance prompt for experiment procedures."""
        return ExperimentPrompts.get_sop_agent_system_prompt(context, state_data)
    
    def get_user_prompt(self, context: Dict[str, Any]) -> str:
        """Get the initial experiment user prompt."""
        return ExperimentPrompts.get_user_prompt(context)
    
    def get_allowed_tools(self) -> List[str]:
        """Get all available tools for the worker agent."""
        return self.available_tools
    
    def should_continue(self, state_data: Dict[str, Any]) -> bool:
        """
        Determine if the experiment procedure should continue.
        
        With the new stop tool approach, the worker agent decides when to stop.
        This method only enforces safety limits and respects explicit stop requests.
        """
        round_num = state_data.get("round", 0)
        tools_used = state_data.get("tools_used", [])
        
        logger.info(f"🔍 SHOULD_CONTINUE CHECK: Round {round_num}/100, Tools used: {len(tools_used)}")
        
        # Safety limit to prevent infinite loops - increased for comprehensive data gathering
        if round_num >= 100:
            logger.warning(f"🛑 SAFETY LIMIT REACHED: Hit maximum rounds ({round_num}/100)")
            logger.warning(f"🔍 FINAL STATE: Tools used: {tools_used}")
            return False
        
        # Let worker agent control stopping via stop_procedure tool
        # The stop tool will set stop_requested=True in results
        logger.debug(f"✅ CONTINUING: Round {round_num} < 100, no stop requested")
        return True
    
    def get_completion_summary(self, state_data: Dict[str, Any]) -> str:
        """Get experiment completion summary."""
        tools_used = state_data.get("tools_used", [])
        round_num = state_data.get("round", 0)
        
        # Count experiment node creation tools used (more accurate than nodes_created)
        create_node_calls = sum(1 for tool in tools_used if tool == "create_experiment_node")
        
        if create_node_calls == 0:
            return "Experiment analysis completed but no hypothesis nodes were created."
        elif create_node_calls == 1:
            return f"Experiment completed with 1 hypothesis node created in {round_num} rounds."
        else:
            return f"Experiment completed successfully with {create_node_calls} hypothesis nodes created in {round_num} rounds."


class ExperimentFlowManagerAdapter(FlowManager):
    """
    Adapter that wraps ConversationFlowManager to implement the FlowManager interface.
    
    This allows the existing experiment flow logic to work with the general-purpose
    StandardOperatingProcedureAgent while maintaining backward compatibility.
    """
    
    def __init__(self, experiment_config: Dict[str, Any], experiment_context: Dict[str, Any]):
        self.conversation_flow_manager = ConversationFlowManager(experiment_config, experiment_context)
    
    def initialize(self, config: Dict[str, Any], context: Dict[str, Any]):
        """Initialize with config and context (called by SOP Agent setup)."""
        # ConversationFlowManager is already initialized in __init__
        pass
    
    def update_state(self, tools_used: List[str], response_content: str, **kwargs) -> Dict[str, Any]:
        """Update the experiment conversation flow state."""
        nodes_created = kwargs.get("nodes_created", 0)
        
        # Update the conversation flow manager
        state_data = self.conversation_flow_manager.update_state(
            tools_used=tools_used,
            response_content=response_content,
            nodes_created=nodes_created
        )
        
        # Add flow manager continuation decision
        state_data["flow_manager_should_continue"] = self.conversation_flow_manager.should_continue()
        
        return state_data
    
    def should_continue(self) -> bool:
        """Determine if the experiment flow should continue."""
        return self.conversation_flow_manager.should_continue()
    
    def get_next_guidance(self) -> Optional[str]:
        """Get template guidance for the next experiment step."""
        return self.conversation_flow_manager.get_next_guidance()
    
    def get_completion_summary(self) -> str:
        """Get experiment completion summary."""
        return self.conversation_flow_manager.get_completion_summary()


class ExperimentChatRecorderAdapter(ChatRecorder):
    """
    Adapter that wraps ExperimentChatRecorder to implement the ChatRecorder interface.
    
    This allows experiment chat recording to work with the general-purpose
    StandardOperatingProcedureAgent while maintaining experiment-specific recording logic.
    """
    
    def __init__(self, client, experiment_id: str, node_id: Optional[str] = None):
        self.experiment_chat_recorder = ExperimentChatRecorder(client, experiment_id, node_id)
    
    async def start_session(self, context: Dict[str, Any]) -> Optional[str]:
        """Start an experiment recording session."""
        return await self.experiment_chat_recorder.start_session(context)
    
    async def record_message(self, role: str, content: str, message_type: str, 
                           tool_name: Optional[str] = None,
                           tool_parameters: Optional[Dict[str, Any]] = None,
                           tool_response: Optional[Dict[str, Any]] = None,
                           parent_message_id: Optional[str] = None) -> Optional[str]:
        """Record a message in the experiment session."""
        return await self.experiment_chat_recorder.record_message(
            role, content, message_type, tool_name, tool_parameters, tool_response, parent_message_id
        )
    
    async def record_system_message(self, content: str) -> Optional[str]:
        """Record a system message in the experiment session."""
        return await self.experiment_chat_recorder.record_system_message(content)
    
    async def end_session(self, status: str, name: str = None) -> bool:
        """End the experiment recording session."""
        return await self.experiment_chat_recorder.end_session(status, name)


class ExperimentSOPAgent:
    """
    Experiment-specific wrapper for StandardOperatingProcedureAgent.
    
    This class provides a convenient interface for running experiment procedures
    while hiding the general-purpose SOP Agent complexity from experiment-specific code.
    
    It maintains the same interface as the original ExperimentAIRunner for backward
    compatibility while using the new architecture under the hood.
    """
    
    def __init__(self, experiment_id: str, mcp_server, client=None, openai_api_key: Optional[str] = None, experiment_context: Optional[Dict[str, Any]] = None, model_config: Optional[Dict[str, Any]] = None):
        """Initialize the ExperimentSOPAgent with experiment-specific configuration."""
        self.experiment_id = experiment_id
        self.mcp_server = mcp_server
        self.client = client
        self.openai_api_key = openai_api_key
        self.experiment_context = experiment_context or {}
        self.model_config = model_config
        
        # Experiment-specific components
        self.procedure_definition = ExperimentProcedureDefinition()
        self.flow_manager = None
        self.chat_recorder = None
        self.sop_agent = None
        
        # Backward compatibility attributes
        self.experiment_config = None
        
        logger.info(f"ExperimentSOPAgent initialized for experiment {experiment_id}")
    
    async def setup(self, experiment_yaml: str) -> bool:
        """Set up the experiment procedure with the given YAML configuration."""
        try:
            # Parse experiment configuration
            import yaml
            experiment_config = yaml.safe_load(experiment_yaml)
            self.experiment_config = experiment_config  # Store for backward compatibility
            
            # Create experiment-specific components
            self.flow_manager = ExperimentFlowManagerAdapter(experiment_config, self.experiment_context)
            
            if self.client:
                self.chat_recorder = ExperimentChatRecorderAdapter(self.client, self.experiment_id, None)
            
            # Create the general-purpose SOP Agent with experiment-specific components
            self.sop_agent = StandardOperatingProcedureAgent(
                procedure_id=self.experiment_id,
                procedure_definition=self.procedure_definition,
                mcp_server=self.mcp_server,
                flow_manager=self.flow_manager,
                chat_recorder=self.chat_recorder,
                openai_api_key=self.openai_api_key,
                context=self.experiment_context,
                model_config=self.model_config
            )
            
            # Set up the SOP Agent
            setup_success = await self.sop_agent.setup(experiment_yaml)
            if setup_success:
                logger.info(f"ExperimentSOPAgent setup completed for {self.experiment_id}")
            return setup_success
            
        except Exception as e:
            logger.error(f"Error setting up ExperimentSOPAgent: {e}")
            return False
    
    async def execute_sop_guided_experiment(self) -> Dict[str, Any]:
        """
        Execute the SOP-guided experiment procedure.
        
        This method delegates to the general-purpose SOP Agent while maintaining
        the experiment-specific interface for backward compatibility.
        """
        if not self.sop_agent:
            return {
                "success": False,
                "error": "ExperimentSOPAgent not properly set up",
                "experiment_id": self.experiment_id
            }
        
        try:
            # Execute using the general-purpose SOP Agent
            result = await self.sop_agent.execute_procedure()
            
            # Transform result to match experiment expectations
            if result.get("success"):
                # Count nodes created from tools used
                nodes_created = len([tool for tool in result.get("tools_used", []) if tool == "create_experiment_node"])
                
                experiment_result = {
                    "success": True,
                    "experiment_id": self.experiment_id,
                    "system_prompt": self.procedure_definition.get_system_prompt(self.experiment_context),
                    "user_prompt": self.procedure_definition.get_user_prompt(self.experiment_context),
                    "response": result.get("completion_summary", "Experiment completed"),
                    "tools_available": len(self.procedure_definition.get_allowed_tools()),
                    "tool_names": result.get("tools_used", []),
                    "nodes_created": nodes_created,
                    "rounds_completed": result.get("rounds_completed", 0)
                }
                
                logger.info(f"ExperimentSOPAgent completed successfully: {nodes_created} nodes created")
                return experiment_result
            else:
                error_result = {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "experiment_id": self.experiment_id
                }
                # Pass through suggestion if available
                if "suggestion" in result:
                    error_result["suggestion"] = result["suggestion"]
                return error_result
                
        except Exception as e:
            logger.error(f"Error executing experiment procedure: {e}")
            return {
                "success": False,
                "error": str(e),
                "experiment_id": self.experiment_id,
                "suggestion": "Check logs for detailed error information"
            }
    
    # Backward compatibility methods
    def get_exploration_prompt(self) -> str:
        """Get the exploration prompt (backward compatibility)."""
        if self.experiment_config and 'exploration' in self.experiment_config:
            return self.experiment_config['exploration']
        return self.procedure_definition.get_user_prompt(self.experiment_context)
    
    def get_system_prompt(self) -> str:
        """Get the system prompt (backward compatibility)."""
        return self.procedure_definition.get_system_prompt(self.experiment_context)
    
    def get_user_prompt(self) -> str:
        """Get the user prompt (backward compatibility)."""
        return self.procedure_definition.get_user_prompt(self.experiment_context)


# Convenience function for experiment execution
async def run_sop_guided_experiment(experiment_id: str, experiment_yaml: str, 
                                   mcp_server, openai_api_key: Optional[str] = None, 
                                   experiment_context: Optional[Dict[str, Any]] = None,
                                   client=None, 
                                   model_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run SOP-guided experiment using the ExperimentSOPAgent.
    
    This function maintains backward compatibility with the original experiment
    execution interface while using the new general-purpose SOP Agent architecture.
    
    Args:
        experiment_id: The experiment ID
        experiment_yaml: The experiment YAML configuration
        mcp_server: The MCP server instance providing tools
        openai_api_key: Optional OpenAI API key for SOP Agent
        experiment_context: Optional experiment context with known information
        client: Optional GraphQL client for recording conversations
        model_config: Optional model configuration dict (e.g., {"model": "gpt-5", "reasoning_effort": "medium"})
        
    Returns:
        Dictionary with execution results including nodes created, tools used, etc.
    """
    logger.info(f"Starting SOP-guided experiment execution: {experiment_id}")
    
    try:
        # Ensure client is included in experiment context for MCP tools
        if experiment_context is None:
            experiment_context = {}
        if client and 'client' not in experiment_context:
            experiment_context['client'] = client
        
        # Create and set up the ExperimentSOPAgent
        experiment_agent = ExperimentSOPAgent(experiment_id, mcp_server, client, openai_api_key, experiment_context, model_config)
        
        setup_success = await experiment_agent.setup(experiment_yaml)
        if not setup_success:
            return {
                "success": False,
                "error": "Failed to set up ExperimentSOPAgent",
                "experiment_id": experiment_id
            }
        
        # Execute the experiment procedure
        result = await experiment_agent.execute_sop_guided_experiment()
        
        logger.info(f"SOP-guided experiment completed: {result.get('success', False)}")
        return result
        
    except Exception as e:
        logger.error(f"Error in experiment execution: {e}")
        return {
            "success": False,
            "error": str(e),
            "experiment_id": experiment_id,
            "suggestion": "Check logs for detailed error information and ensure proper setup"
        }
