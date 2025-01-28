"""
Optimizer node for generating improved prompts.
"""
import logging
from typing import Dict, Any, Callable

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import PromptChange, PromptImprovement, OptimizationStatus
from plexus.Registries import scorecard_registry
from plexus.Scorecard import Scorecard

logger = logging.getLogger('plexus.apos.nodes.optimizer')


class OptimizerOutput(BaseModel):
    """Schema for optimizer response."""
    system_message: str = Field(description="The improved system message")
    user_message: str = Field(description="The improved user message")
    rationale: str = Field(description="The rationale for the improvements made")


class OptimizerNode(APOSNode):
    """Node for generating optimized prompts."""
    
    def _setup_node(self) -> None:
        """Set up the optimizer components."""
        model_config = self.config.optimizer_model
        
        # Initialize LLM with structured output
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        ).with_structured_output(OptimizerOutput)
        
        # Set up prompt templates
        self.system_template = SystemMessagePromptTemplate.from_template(
            model_config.prompts['system_template']
        )
        self.human_template = HumanMessagePromptTemplate.from_template(
            model_config.prompts['human_template']
        )
        self.chat_prompt = ChatPromptTemplate.from_messages([
            self.system_template,
            self.human_template
        ])
        
        logger.info(f"Initialized optimizer node using {model_config.model_type}")
    
    def get_current_prompts(self, score_name: str) -> Dict[str, str]:
        """Get the current prompts for a given score from scorecard."""
        try:
            # Load scorecard
            logger.info(f"Loading scorecards for {score_name}")
            Scorecard.load_and_register_scorecards('scorecards/')
            
            # Get score configuration from the scorecard
            for scorecard_class in scorecard_registry._classes_by_key.values():
                scorecard_key = scorecard_class.properties.get('key') or scorecard_class.name
                logger.info(f"Checking scorecard: {scorecard_key}")
                
                scorecard = scorecard_class(scorecard=scorecard_key)
                score_config = next((score for score in scorecard.scores 
                                if score['name'] == score_name), None)
                
                if score_config:
                    logger.info(f"Found score config for {score_name}")
                    
                    # Look for Classifier node in graph
                    if 'graph' in score_config:
                        for node in score_config['graph']:
                            if node.get('class') == 'Classifier':
                                logger.info(f"Found Classifier node: {node}")
                                prompts = {
                                    'system_message': node.get('system_message', ''),
                                    'user_message': node.get('user_message', '')
                                }
                                if prompts['system_message'] and prompts['user_message']:
                                    logger.info("Found prompts in Classifier node")
                                    return prompts
                    
                    # Try top-level prompts
                    prompts = {
                        'system_message': score_config.get('system_message', ''),
                        'user_message': score_config.get('user_message', '')
                    }
                    
                    if prompts['system_message'] and prompts['user_message']:
                        logger.info("Using top-level prompts")
                        return prompts
                    else:
                        logger.error("No valid prompts found in score config")
                        raise ValueError(f"No prompts found for score: {score_name}")
            
            raise ValueError(f"No configuration found for score: {score_name}")
            
        except Exception as e:
            logger.error(f"Error getting current prompts for {score_name}: {e}")
            raise
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the handler function for this node."""
        
        async def optimize_prompts(state: APOSState) -> Dict[str, Any]:
            """Optimize prompts based on pattern analysis."""
            try:
                # First increment the iteration count since we're completing a cycle
                state.current_iteration += 1
                logger.info(f"Completed iteration {state.current_iteration - 1}, starting iteration {state.current_iteration}")
                
                # Check if we should continue
                if not state.should_continue():
                    logger.info("Optimization complete")
                    state.status = OptimizationStatus.COMPLETED
                    return {
                        "state": {
                            "current_iteration": state.current_iteration,
                            "status": state.status
                        }
                    }
                
                # Get pattern analysis results
                if not state.pattern_analysis:
                    logger.warning("No pattern analysis results available")
                    return {
                        "state": {
                            "current_iteration": state.current_iteration
                        }
                    }
                
                # Log pattern analysis for debugging
                logger.info(f"Pattern analysis: {state.pattern_analysis}")
                    
                # Run optimization using LLM
                prompt_vars = {
                    "current_system_message": state.system_message,
                    "current_user_message": state.user_message,
                    "common_issues": state.pattern_analysis.common_issues,
                    "summary": state.pattern_analysis.summary
                }
                
                # Get optimization suggestions from LLM
                prompt_improvement = await self.llm.ainvoke(
                    self.chat_prompt.format_messages(**prompt_vars)
                )
                
                # Create separate PromptChange objects for system and user messages
                prompt_changes = []
                
                # Add system message change
                if prompt_improvement.system_message != state.system_message:
                    prompt_changes.append(PromptChange(
                        component="system_message",
                        old_text=state.system_message,
                        new_text=prompt_improvement.system_message,
                        rationale=prompt_improvement.rationale
                    ))
                
                # Add user message change
                if prompt_improvement.user_message != state.user_message:
                    prompt_changes.append(PromptChange(
                        component="user_message",
                        old_text=state.user_message,
                        new_text=prompt_improvement.user_message,
                        rationale=prompt_improvement.rationale
                    ))
                
                # Update state with all optimization results
                state.optimization_result = prompt_changes if prompt_changes else None
                
                # Log the changes for debugging
                if prompt_changes:
                    logger.info(f"Generated {len(prompt_changes)} prompt changes:")
                    for change in prompt_changes:
                        logger.info(f"- {change.component} change:")
                        logger.info(f"  Old length: {len(change.old_text)}")
                        logger.info(f"  New length: {len(change.new_text)}")
                
                # Return state updates wrapped in state key
                return {
                    "state": {
                        "system_message": prompt_improvement.system_message,
                        "user_message": prompt_improvement.user_message,
                        "optimization_result": state.optimization_result,
                        "current_iteration": state.current_iteration
                    }
                }
                
            except Exception as e:
                logger.error(f"Error optimizing prompts: {e}")
                state.status = OptimizationStatus.FAILED
                state.metadata["error"] = str(e)
                return {
                    "state": {
                        "status": state.status,
                        "metadata": state.metadata,
                        "current_iteration": state.current_iteration
                    }
                }
                
        return optimize_prompts 