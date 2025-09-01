"""
Procedure-specific StandardOperatingProcedureAgent implementation.

This module provides the ProcedureSOPAgent, which uses the general-purpose
StandardOperatingProcedureAgent to execute procedure hypothesis generation
procedures. It implements the experiment-specific behavior while delegating
the core SOP orchestration to the reusable base agent.

Architecture:
- ProcedureProcedureDefinition: Defines experiment-specific prompts, tools, and logic
- ProcedureFlowManager: Manages procedure conversation flow (exploration → synthesis → hypothesis)
- ProcedureChatRecorder: Records procedure conversations
- ProcedureSOPAgent: Convenience wrapper for procedure procedures
"""

import logging
from typing import Dict, Any, List, Optional
from .sop_agent_base import StandardOperatingProcedureAgent, ProcedureDefinition, FlowManager, ChatRecorder
# ProcedurePrompts no longer used - all prompts come from YAML configuration
# Removed ConversationFlowManager import - using simplified multi-agent ReAct loop
from .chat_recorder import ProcedureChatRecorder
from .mcp_adapter import LangChainMCPAdapter

logger = logging.getLogger(__name__)


class ProcedureProcedureDefinition:
    """
    Procedure-specific procedure definition for the StandardOperatingProcedureAgent.
    
    This class encapsulates all experiment-specific knowledge:
    - Procedure hypothesis generation prompts (configurable via YAML)
    - Procedure tool scoping by phase
    - Procedure completion criteria
    - Procedure-specific guidance logic
    """
    
    def __init__(self):
        # Worker agent gets access to a curated subset of tools
        self.available_tools = [
            "plexus_feedback_find", 
            "create_procedure_node", 
            "stop_procedure"
        ]
        # Will be set by ProcedureSOPAgent.setup() when YAML is parsed
        self.experiment_config = None
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        """Get the procedure hypothesis generation system prompt from YAML configuration."""
        if not self.experiment_config or 'prompts' not in self.experiment_config:
            raise ValueError("Procedure configuration must include 'prompts' section with 'worker_system_prompt'")
        
        prompts = self.experiment_config['prompts']
        if 'worker_system_prompt' not in prompts:
            raise ValueError("Procedure configuration missing 'worker_system_prompt' in prompts section")
        
        # Load prompt from YAML and process template variables
        yaml_prompt = prompts['worker_system_prompt']
        return self._process_prompt_template(yaml_prompt, context)
    
    def get_sop_guidance_prompt(self, context: Dict[str, Any], state_data: Dict[str, Any]) -> str:
        """Get the SOP Agent guidance prompt from YAML configuration."""
        if not self.experiment_config or 'prompts' not in self.experiment_config:
            raise ValueError("Procedure configuration must include 'prompts' section with 'manager_system_prompt'")
        
        prompts = self.experiment_config['prompts']
        if 'manager_system_prompt' not in prompts:
            raise ValueError("Procedure configuration missing 'manager_system_prompt' in prompts section")
        
        # Load prompt from YAML and process template variables
        yaml_prompt = prompts['manager_system_prompt']
        return self._process_prompt_template(yaml_prompt, context, state_data)
    
    def get_user_prompt(self, context: Dict[str, Any]) -> str:
        """Get the initial procedure user prompt from YAML configuration."""
        if not self.experiment_config or 'prompts' not in self.experiment_config:
            raise ValueError("Procedure configuration must include 'prompts' section with 'worker_user_prompt'")
        
        prompts = self.experiment_config['prompts']
        if 'worker_user_prompt' not in prompts:
            raise ValueError("Procedure configuration missing 'worker_user_prompt' in prompts section")
        
        # Load prompt from YAML and process template variables
        yaml_prompt = prompts['worker_user_prompt']
        return self._process_prompt_template(yaml_prompt, context)
    
    def get_manager_user_prompt(self, context: Dict[str, Any], state_data: Optional[Dict[str, Any]] = None) -> str:
        """Get the initial manager user prompt from YAML configuration."""
        if not self.experiment_config or 'prompts' not in self.experiment_config:
            raise ValueError("Procedure configuration must include 'prompts' section with 'manager_user_prompt'")
        
        prompts = self.experiment_config['prompts']
        if 'manager_user_prompt' not in prompts:
            raise ValueError("Procedure configuration missing 'manager_user_prompt' in prompts section")
        
        # Load prompt from YAML and process template variables
        yaml_prompt = prompts['manager_user_prompt']
        return self._process_prompt_template(yaml_prompt, context, state_data)
    
    def _process_prompt_template(self, prompt_template: str, context: Dict[str, Any], state_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Process a prompt template with variable substitution.
        
        Supports template variables from context and state_data:
        - {procedure_id}
        - {scorecard_name}
        - {score_name}
        - {current_score_config}
        - {feedback_summary}
        - etc.
        
        Args:
            prompt_template: The YAML prompt template string
            context: Procedure context with variables
            state_data: Optional state data for additional variables
            
        Returns:
            Processed prompt with variables substituted
        """
        try:
            # Combine all available variables
            template_vars = {}
            
            # Add context variables
            if context:
                template_vars.update(context)
            
            # Add state data variables
            if state_data:
                template_vars.update(state_data)
            
            # Use simple string formatting for now (could upgrade to Jinja2 later)
            return prompt_template.format(**template_vars)
            
        except KeyError as e:
            # If template variable is missing, log warning and return template as-is
            logger.warning(f"Template variable {e} not found in context, using template as-is")
            return prompt_template
        except Exception as e:
            # If any other formatting error occurs, log and return template as-is
            logger.error(f"Error processing prompt template: {e}")
            return prompt_template
    
    def get_allowed_tools(self) -> List[str]:
        """Get all available tools for the worker agent."""
        return self.available_tools
    
    def should_continue(self, state_data: Dict[str, Any]) -> bool:
        """
        Determine if the procedure procedure should continue.
        
        With the new stop tool approach, the worker agent decides when to stop.
        This method only enforces safety limits and respects explicit stop requests.
        """
        round_num = state_data.get("round", 0)
        tools_used = state_data.get("tools_used", [])
        
        # Get max rounds from procedure configuration (simplified - no state machine)
        max_rounds = 500  # High default fallback to respect template settings
        if hasattr(self, 'experiment_config') and self.experiment_config:
            # Look for max_total_rounds in the top level or under escalation
            max_rounds = self.experiment_config.get('max_total_rounds', 
                        self.experiment_config.get('escalation', {}).get('max_total_rounds', 500))
        
        logger.info(f"🔍 SHOULD_CONTINUE CHECK: Round {round_num}/{max_rounds}, Tools used: {len(tools_used)}")
        
        # Safety limit to prevent infinite loops - uses dynamic limit from template
        if round_num >= max_rounds:
            logger.warning(f"🛑 SAFETY LIMIT REACHED: Hit maximum rounds ({round_num}/{max_rounds})")
            logger.warning(f"🛑 STOP REASON: SOP Agent safety limit reached after {max_rounds} rounds (from template config)")
            logger.warning(f"🔍 FINAL STATE: Tools used: {tools_used}")
            return False
        
        # Let worker agent control stopping via stop_procedure tool
        # The stop tool will set stop_requested=True in results
        logger.debug(f"✅ CONTINUING: Round {round_num} < {max_rounds}, no stop requested")
        return True
    
    def get_completion_summary(self, state_data: Dict[str, Any]) -> str:
        """Get procedure completion summary."""
        tools_used = state_data.get("tools_used", [])
        round_num = state_data.get("round", 0)
        
        # Count procedure node creation tools used (more accurate than nodes_created)
        create_node_calls = sum(1 for tool in tools_used if tool == "create_procedure_node")
        
        if create_node_calls == 0:
            return "Procedure analysis completed but no hypothesis nodes were created."
        elif create_node_calls == 1:
            return f"Procedure completed with 1 hypothesis node created in {round_num} rounds."
        else:
            return f"Procedure completed successfully with {create_node_calls} hypothesis nodes created in {round_num} rounds."


# Removed ProcedureFlowManagerAdapter - using simplified multi-agent ReAct loop without state machine


class ProcedureChatRecorderAdapter(ChatRecorder):
    """
    Adapter that wraps ProcedureChatRecorder to implement the ChatRecorder interface.
    
    This allows procedure chat recording to work with the general-purpose
    StandardOperatingProcedureAgent while maintaining experiment-specific recording logic.
    """
    
    def __init__(self, client, procedure_id: str, node_id: Optional[str] = None):
        self.experiment_chat_recorder = ProcedureChatRecorder(client, procedure_id, node_id)
    
    async def start_session(self, context: Dict[str, Any]) -> Optional[str]:
        """Start an procedure recording session."""
        return await self.experiment_chat_recorder.start_session(context)
    
    async def record_message(self, role: str, content: str, message_type: str, 
                           tool_name: Optional[str] = None,
                           tool_parameters: Optional[Dict[str, Any]] = None,
                           tool_response: Optional[Dict[str, Any]] = None,
                           parent_message_id: Optional[str] = None) -> Optional[str]:
        """Record a message in the procedure session."""
        return await self.experiment_chat_recorder.record_message(
            role, content, message_type, tool_name, tool_parameters, tool_response, parent_message_id
        )
    
    async def record_system_message(self, content: str) -> Optional[str]:
        """Record a system message in the procedure session."""
        return await self.experiment_chat_recorder.record_system_message(content)
    
    async def end_session(self, status: str, name: str = None) -> bool:
        """End the procedure recording session."""
        return await self.experiment_chat_recorder.end_session(status, name)


class ProcedureSOPAgent:
    """
    Procedure-specific wrapper for StandardOperatingProcedureAgent.
    
    This class provides a convenient interface for running procedure procedures
    while hiding the general-purpose SOP Agent complexity from experiment-specific code.
    
    It maintains the same interface as the original ProcedureAIRunner for backward
    compatibility while using the new architecture under the hood.
    """
    
    def __init__(self, procedure_id: str, mcp_server, client=None, openai_api_key: Optional[str] = None, experiment_context: Optional[Dict[str, Any]] = None, model_config: Optional[Dict[str, Any]] = None):
        """Initialize the ProcedureSOPAgent with experiment-specific configuration."""
        self.procedure_id = procedure_id
        self.mcp_server = mcp_server
        self.client = client
        self.openai_api_key = openai_api_key
        self.experiment_context = experiment_context or {}
        self.model_config = model_config
        
        # Procedure-specific components
        self.procedure_definition = ProcedureProcedureDefinition()
        self.chat_recorder = None
        self.sop_agent = None
        
        # Backward compatibility attributes
        self.experiment_config = None
        
        logger.info(f"ProcedureSOPAgent initialized for procedure {procedure_id}")
    
    async def setup(self, experiment_yaml: str) -> bool:
        """Set up the procedure procedure with the given YAML configuration."""
        try:
            # Parse procedure configuration
            import yaml
            experiment_config = yaml.safe_load(experiment_yaml)
            self.experiment_config = experiment_config  # Store for backward compatibility
            
            # Create experiment-specific components (simplified - no flow manager)
            if self.client:
                self.chat_recorder = ProcedureChatRecorderAdapter(self.client, self.procedure_id, None)
            
            # Pass procedure config to procedure definition
            self.procedure_definition.experiment_config = experiment_config
            
            # Create the general-purpose SOP Agent with experiment-specific components (no flow manager)
            self.sop_agent = StandardOperatingProcedureAgent(
                procedure_id=self.procedure_id,
                procedure_definition=self.procedure_definition,
                mcp_server=self.mcp_server,
                flow_manager=None,  # Simplified - no state machine
                chat_recorder=self.chat_recorder,
                openai_api_key=self.openai_api_key,
                context=self.experiment_context,
                model_config=self.model_config
            )
            
            # Set up the SOP Agent
            setup_success = await self.sop_agent.setup(experiment_yaml)
            if setup_success:
                logger.info(f"ProcedureSOPAgent setup completed for {self.procedure_id}")
            return setup_success
            
        except Exception as e:
            logger.error(f"Error setting up ProcedureSOPAgent: {e}")
            return False
    
    async def execute_sop_guided_procedure(self) -> Dict[str, Any]:
        """
        Execute the SOP-guided procedure procedure.
        
        This method delegates to the general-purpose SOP Agent while maintaining
        the experiment-specific interface for backward compatibility.
        """
        if not self.sop_agent:
            return {
                "success": False,
                "error": "ProcedureSOPAgent not properly set up",
                "procedure_id": self.procedure_id
            }
        
        try:
            # Execute using the general-purpose SOP Agent
            result = await self.sop_agent.execute_procedure()
            
            # Transform result to match procedure expectations
            if result.get("success"):
                # Count nodes created from tools used
                nodes_created = len([tool for tool in result.get("tools_used", []) if tool == "create_procedure_node"])
                
                experiment_result = {
                    "success": True,
                    "procedure_id": self.procedure_id,
                    "system_prompt": self.procedure_definition.get_system_prompt(self.experiment_context),
                    "user_prompt": self.procedure_definition.get_user_prompt(self.experiment_context),
                    "response": result.get("completion_summary", "Procedure completed"),
                    "tools_available": len(self.procedure_definition.get_allowed_tools()),
                    "tool_names": result.get("tools_used", []),
                    "nodes_created": nodes_created,
                    "rounds_completed": result.get("rounds_completed", 0)
                }
                
                logger.info(f"ProcedureSOPAgent completed successfully: {nodes_created} nodes created")
                return experiment_result
            else:
                error_result = {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "procedure_id": self.procedure_id
                }
                # Pass through suggestion if available
                if "suggestion" in result:
                    error_result["suggestion"] = result["suggestion"]
                return error_result
                
        except Exception as e:
            logger.error(f"Error executing procedure procedure: {e}")
            return {
                "success": False,
                "error": str(e),
                "procedure_id": self.procedure_id,
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


# Convenience function for procedure execution
async def run_sop_guided_procedure(procedure_id: str, experiment_yaml: str, 
                                   mcp_server, openai_api_key: Optional[str] = None, 
                                   experiment_context: Optional[Dict[str, Any]] = None,
                                   client=None, 
                                   model_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run SOP-guided procedure using the ProcedureSOPAgent.
    
    This function maintains backward compatibility with the original experiment
    execution interface while using the new general-purpose SOP Agent architecture.
    
    Args:
        procedure_id: The procedure ID
        experiment_yaml: The procedure YAML configuration
        mcp_server: The MCP server instance providing tools
        openai_api_key: Optional OpenAI API key for SOP Agent
        experiment_context: Optional procedure context with known information
        client: Optional GraphQL client for recording conversations
        model_config: Optional model configuration dict (e.g., {"model": "gpt-5", "reasoning_effort": "medium"})
        
    Returns:
        Dictionary with execution results including nodes created, tools used, etc.
    """
    logger.info(f"Starting SOP-guided procedure execution: {procedure_id}")
    
    try:
        # Ensure client is included in procedure context for MCP tools
        if experiment_context is None:
            experiment_context = {}
        if client and 'client' not in experiment_context:
            experiment_context['client'] = client
        
        # Create and set up the ProcedureSOPAgent
        experiment_agent = ProcedureSOPAgent(procedure_id, mcp_server, client, openai_api_key, experiment_context, model_config)
        
        setup_success = await experiment_agent.setup(experiment_yaml)
        if not setup_success:
            return {
                "success": False,
                "error": "Failed to set up ProcedureSOPAgent",
                "procedure_id": procedure_id
            }
        
        # Execute the procedure procedure
        result = await experiment_agent.execute_sop_guided_procedure()
        
        logger.info(f"SOP-guided procedure completed: {result.get('success', False)}")
        return result
        
    except Exception as e:
        logger.error(f"Error in procedure execution: {e}")
        return {
            "success": False,
            "error": str(e),
            "procedure_id": procedure_id,
            "suggestion": "Check logs for detailed error information and ensure proper setup"
        }
