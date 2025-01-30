"""
Optimizer node for generating improved prompts.
"""
import logging
import os
import json
from typing import Dict, Any, Callable
from pydantic import ValidationError

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field, validator

from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import PromptChange, PromptImprovement, OptimizationStatus
from plexus.Registries import scorecard_registry
from plexus.Scorecard import Scorecard

logger = logging.getLogger('plexus.apos.nodes.optimizer')


class OptimizerOutput(BaseModel):
    """Schema for optimizer response."""
    system_message: str = Field(
        description="The improved system message",
        min_length=1,
        error_messages={
            "type": "System message must be a string",
            "required": "System message is required",
            "min_length": "System message cannot be empty"
        }
    )
    user_message: str = Field(
        description="The improved user message. IMPORTANT: Must contain the literal string '{{text}}' as a placeholder for the input text.",
        min_length=1,
        error_messages={
            "type": "User message must be a string",
            "required": "User message is required",
            "min_length": "User message cannot be empty"
        }
    )

    class Config:
        validate_assignment = True
        extra = "forbid"  # Prevent extra fields

    @validator('user_message', pre=True, always=True)
    def validate_placeholder(cls, v):
        if not isinstance(v, str):
            raise ValueError("User message must be a string")
        if '{{text}}' not in v:
            raise ValueError("User message MUST contain the literal string '{{text}}' as a placeholder. This is required for text substitution.")
        return v


class OptimizerNode(APOSNode):
    """Node for generating optimized prompts."""
    
    def _setup_node(self) -> None:
        """Set up the optimizer components."""
        model_config = self.config.optimizer_model
        
        # Create cache directory if it doesn't exist
        os.makedirs(model_config.cache_dir, exist_ok=True)
        logger.info(f"Ensuring cache directory exists: {model_config.cache_dir}")
        
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
                        "state": state.dict()
                    }
                
                # Get pattern analysis results
                if not state.pattern_analysis:
                    logger.warning("No pattern analysis results available")
                    return {
                        "state": state.dict()
                    }
                
                # Get scorecard and score names from metadata
                scorecard_name = state.metadata.get("scorecard_name")
                score_name = state.metadata.get("score_name")
                
                if not scorecard_name or not score_name:
                    logger.error("Missing scorecard_name or score_name in metadata")
                    return {
                        "state": state.dict()
                    }
                
                # Create directory structure
                iteration_dir = os.path.join(
                    "optimization_history",
                    scorecard_name,
                    score_name,
                    f"iteration_{state.current_iteration}"
                )
                os.makedirs(iteration_dir, exist_ok=True)
                state.metadata["iteration_dir"] = iteration_dir
                
                # Log pattern analysis for debugging
                logger.info(f"Pattern analysis: {state.pattern_analysis}")
                    
                # Run optimization using LLM with retries
                prompt_vars = {
                    **state.dict()
                }

                max_retries = 3
                retry_count = 0
                last_error = None

                while retry_count < max_retries:
                    try:
                        # If this is a retry, add error context to the prompt
                        if retry_count > 0 and last_error:
                            prompt_vars["error_context"] = (
                                f"Previous attempt failed with error: {str(last_error)}. "
                                "CRITICAL REQUIREMENT: The user_message MUST contain the exact string '{{text}}' (including the curly braces) "
                                "as a placeholder where the input text will be inserted. "
                                "Example format: 'Analyze the following text: {{text}}'"
                            )
                        
                        # Get optimization suggestions from LLM
                        prompt_improvement = await self.llm.ainvoke(
                            self.chat_prompt.format_messages(**prompt_vars)
                        )
                        break  # If successful, exit the retry loop
                        
                    except (ValidationError, ValueError) as e:
                        last_error = e
                        retry_count += 1
                        logger.warning(f"Validation error on attempt {retry_count}: {e}")
                        if retry_count >= max_retries:
                            raise  # Re-raise if we've exhausted retries
                        continue
                
                # Create prompt changes
                prompt_changes = []
                
                # Add system message change
                if prompt_improvement.system_message != state.system_message:
                    prompt_changes.append(PromptChange(
                        component="system_message",
                        old_text=state.system_message,
                        new_text=prompt_improvement.system_message
                    ))
                    # Update state's system message
                    state.system_message = prompt_improvement.system_message
                
                # Add user message change
                if prompt_improvement.user_message != state.user_message:
                    prompt_changes.append(PromptChange(
                        component="user_message",
                        old_text=state.user_message,
                        new_text=prompt_improvement.user_message
                    ))
                    # Update state's user message
                    state.user_message = prompt_improvement.user_message
                
                # Update state with all optimization results
                state.optimization_result = prompt_changes if prompt_changes else None
                
                # Log the changes for debugging
                if prompt_changes:
                    logger.info(f"Generated {len(prompt_changes)} prompt changes:")
                    for change in prompt_changes:
                        logger.info(f"- {change.component} change:")
                        logger.info(f"  Old length: {len(change.old_text)}")
                        logger.info(f"  New length: {len(change.new_text)}")
                    
                    # Save prompt changes to file
                    changes_path = os.path.join(iteration_dir, "prompt_changes.json")
                    changes_to_save = []
                    for change in prompt_changes:
                        changes_to_save.append({
                            "component": change.component,
                            "old_text": change.old_text,
                            "new_text": change.new_text,
                            "metadata": {
                                "iteration": state.current_iteration,
                                "score_name": state.score_name
                            }
                        })
                    
                    with open(changes_path, 'w') as f:
                        json.dump(changes_to_save, f, indent=4)
                    logger.info(f"Saved prompt changes to {changes_path}")
                
                # Return state updates wrapped in state key
                return {
                    "state": state.dict()
                }
                
            except Exception as e:
                logger.error(f"Error optimizing prompts: {e}")
                state.status = OptimizationStatus.FAILED
                state.metadata["error"] = str(e)
                return {
                    "state": state.dict()
                }
                
        return optimize_prompts 