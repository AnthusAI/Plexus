"""
Pattern analyzer node for finding patterns across analyzed mismatches.
"""
import logging
import os
import json
from typing import Dict, Any, Callable

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from jinja2 import Template

from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import SynthesisResult
from plexus.apos.utils import TokenCounterCallback

logger = logging.getLogger('plexus.apos.nodes.pattern')

class PatternAnalysisOutput(BaseModel):
    """Schema for pattern analysis response."""
    common_issues: list[str] = Field(
        description="List of common issues identified across mismatches",
        min_length=1
    )
    summary: str = Field(
        description="Overall summary of how the current prompt is causing mismatches",
        min_length=1
    )

    class Config:
        validate_assignment = True
        extra = "forbid"

class PatternAnalyzerNode(APOSNode):
    """Node for analyzing patterns across mismatches."""
    
    def _setup_node(self) -> None:
        """Set up the pattern analyzer components."""
        model_config = self.config.pattern_analyzer_model
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        )
        
        # Set up output parser
        self.parser = JsonOutputParser(pydantic_object=PatternAnalysisOutput)
        
        # Set up prompt templates
        system_template = model_config.prompts['system_template']
        system_template += "\n\n{format_instructions}"
        
        self.system_template = SystemMessagePromptTemplate.from_template(
            system_template,
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        # Use Jinja2 template for human template
        self.human_template_str = model_config.prompts['human_template']
        
        logger.info(f"Initialized pattern analyzer node using {model_config.model_type}")
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the pattern analysis handler."""
        async def analyze_patterns(state: APOSState) -> Dict[str, Any]:
            try:
                if not state.mismatches:
                    logger.error("No analyzed mismatches available for pattern analysis")
                    raise ValueError("No analyzed mismatches available for pattern analysis")
                
                logger.info("Starting pattern analysis across mismatches")
                
                # Render the Jinja2 template with state data
                template = Template(self.human_template_str)
                human_message = template.render(**state.dict())
                
                # Create messages using rendered template
                messages = [
                    self.system_template.format(**state.dict()),
                    HumanMessagePromptTemplate.from_template(human_message).format(**state.dict())
                ]
                
                # Create token counter callback
                token_counter = TokenCounterCallback()
                
                # Get analysis from LLM
                response = await self.llm.ainvoke(
                    messages,
                    config={"callbacks": [token_counter]}
                )
                
                # Clean the response content by removing markdown code block if present
                content = response.content
                if content.startswith("```") and content.endswith("```"):
                    content = "\n".join(content.split("\n")[1:-1])
                
                # Parse the response
                parsed_dict = self.parser.parse(content)
                result = PatternAnalysisOutput(**parsed_dict)
                
                # Track cost
                self.track_llm_cost(
                    state=state,
                    model_name=self.config.pattern_analyzer_model.model_type,
                    input_tokens=token_counter.input_tokens,
                    output_tokens=token_counter.output_tokens
                )
                
                logger.info("Pattern analysis complete")
                logger.info(f"Found {len(result.common_issues)} common issues")
                
                # Create synthesis result
                synthesis = SynthesisResult(
                    common_issues=result.common_issues,
                    summary=result.summary
                )
                
                # Save pattern analysis results
                self._save_pattern_results(synthesis, state)
                
                # Log current iteration costs
                logger.info(
                    f"Pattern analysis costs - "
                    f"This iteration: ${float(state.current_iteration_cost):.4f}, "
                    f"Total so far: ${float(state.total_cost):.4f}"
                )
                
                # Update state with results
                return {
                    **state.dict(),
                    "pattern_analysis": synthesis,
                    "retry_count": 0
                }
                
            except Exception as e:
                logger.error(f"Error analyzing patterns: {e}")
                return self.handle_error(e, state)
                
        return analyze_patterns

    def _save_pattern_results(self, synthesis: SynthesisResult, state: APOSState) -> None:
        """Save pattern analysis results to disk."""
        try:
            # Get scorecard and score names from metadata
            scorecard_name = state.metadata.get("scorecard_name")
            score_name = state.metadata.get("score_name")
            
            if not scorecard_name or not score_name:
                logger.error("Missing scorecard_name or score_name in metadata")
                return
                
            # Create directory structure
            results_dir = os.path.join(
                "optimization_history",
                scorecard_name,
                score_name,
                f"iteration_{state.current_iteration}"
            )
            os.makedirs(results_dir, exist_ok=True)
                
            output_path = os.path.join(results_dir, "patterns.json")
            with open(output_path, 'w') as f:
                json.dump({
                    'common_issues': synthesis.common_issues,
                    'summary': synthesis.summary
                }, f, indent=4)
            logger.info(f"Saved pattern analysis results to {output_path}")
            
            # Update state metadata with new iteration directory
            state.metadata["iteration_dir"] = results_dir
            
        except Exception as e:
            logger.error(f"Error saving pattern analysis results: {e}") 