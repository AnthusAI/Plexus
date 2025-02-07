"""
Optimizer node for generating improved prompts.
"""
import logging
import os
import json
from typing import Dict, Any, Callable
from decimal import Decimal

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field, field_validator, ValidationError
from jinja2 import Template

from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import PromptChange, OptimizationStatus
from plexus.apos.utils import TokenCounterCallback

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

    @field_validator('user_message', mode='before')
    @classmethod
    def validate_placeholder(cls, v: str) -> str:
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
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        )
        
        # Set up output parser
        self.parser = JsonOutputParser(pydantic_object=OptimizerOutput)
        
        # Store raw templates for Jinja2
        self.system_template_str = (
            model_config.prompts['system_template'] + 
            "\n\nIMPORTANT: Your response MUST be in JSON format following this schema:\n" +
            "{{format_instructions}}"  # Use Jinja2 variable instead of direct substitution
        )
        self.human_template_str = model_config.prompts['human_template']
        
        logger.info(f"Initialized optimizer node using {model_config.model_type}")
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the handler function for this node."""
        
        async def optimize_prompts(state: APOSState) -> Dict[str, Any]:
            """Optimize prompts based on pattern analysis."""
            try:
                # First increment the iteration count since we're completing a cycle
                completed_iteration = state.current_iteration  # Store the iteration we just completed
                state.current_iteration += 1
                logger.info(f"Completed iteration {completed_iteration}, starting iteration {state.current_iteration}")
                
                # Log full iteration cost summary before checking if we should continue
                if completed_iteration >= 0:  # Only log if we completed an iteration
                    # Get evaluation costs from the latest iteration result
                    evaluation_cost = Decimal('0.0')
                    if state.history and len(state.history) > completed_iteration:
                        latest_result = state.history[completed_iteration]
                        # Debug log the iteration result
                        logger.info(f"Latest iteration result metrics: {latest_result.metrics}")
                        logger.info(f"Latest iteration result metadata: {latest_result.metadata}")
                        
                        # Try to get cost from different possible locations
                        if 'total_cost' in latest_result.metrics:
                            evaluation_cost = Decimal(str(latest_result.metrics['total_cost']))
                        elif 'cost_per_call' in latest_result.metrics:
                            # If we have cost per call, multiply by number of calls
                            cost_per_call = Decimal(str(latest_result.metrics['cost_per_call']))
                            total_calls = latest_result.metrics.get('total_calls', 1)
                            evaluation_cost = cost_per_call * Decimal(str(total_calls))
                        elif 'total_cost' in latest_result.metadata:
                            evaluation_cost = Decimal(str(latest_result.metadata['total_cost']))
                        
                        logger.info(f"Found evaluation cost: ${float(evaluation_cost):.4f}")
                        
                        # Add evaluation cost to the iteration and total costs
                        state.current_iteration_cost += evaluation_cost
                        state.total_cost += evaluation_cost
                    
                    # Calculate optimization costs (convert to Decimal for consistency)
                    optimization_cost = state.current_iteration_cost - evaluation_cost
                    
                    logger.info(
                        f"\n=== Iteration {completed_iteration} Cost Summary ===\n"
                        f"Optimization costs this iteration: ${float(optimization_cost):.4f}\n"
                        f"Evaluation costs this iteration: ${float(evaluation_cost):.4f}\n"
                        f"Total cost this iteration: ${float(state.current_iteration_cost):.4f}\n"
                        f"Cumulative cost so far: ${float(state.total_cost):.4f}\n"
                        f"Average cost per iteration: ${float(state.total_cost / (completed_iteration + 1)):.4f}\n"
                        f"========================================="
                    )
                
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
                    **state.dict(),
                    "format_instructions": self.parser.get_format_instructions()
                }

                max_retries = 3
                retry_count = 0
                last_error = None
                token_counter = TokenCounterCallback()

                while retry_count < max_retries:
                    try:
                        # If this is a retry, add error context
                        if retry_count > 0 and last_error:
                            prompt_vars["error_context"] = f"Previous attempt failed with error: {str(last_error)}..."
                        
                        # Render templates using Jinja2
                        system_template = Template(self.system_template_str)
                        human_template = Template(self.human_template_str)
                        
                        # Render the messages directly
                        messages = [
                            {"role": "system", "content": system_template.render(**prompt_vars)},
                            {"role": "user", "content": human_template.render(**prompt_vars)}
                        ]
                        
                        # Get optimization suggestions from LLM
                        response = await self.llm.ainvoke(
                            messages,
                            config={"callbacks": [token_counter]}
                        )
                        
                        # Parse the response and convert to OptimizerOutput
                        parsed_dict = self.parser.parse(response.content)
                        prompt_improvement = OptimizerOutput(**parsed_dict)
                        
                        # Track cost (only on successful attempt)
                        self.track_llm_cost(
                            state=state,
                            model_name=self.config.optimizer_model.model_type,
                            input_tokens=token_counter.input_tokens,
                            output_tokens=token_counter.output_tokens
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
                
                # Log optimizer node costs
                logger.info(
                    f"Optimizer costs - "
                    f"This iteration: ${float(state.current_iteration_cost):.4f}, "
                    f"Total so far: ${float(state.total_cost):.4f}"
                )
                
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