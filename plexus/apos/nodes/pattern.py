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

from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import PatternAnalysisOutput, SynthesisResult
from plexus.apos.utils import TokenCounterCallback

logger = logging.getLogger('plexus.apos.nodes.pattern')

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
        ).with_structured_output(PatternAnalysisOutput)
        
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
        
        logger.info(f"Initialized pattern analyzer node using {model_config.model_type}")
    
    def _format_mismatch_summary(self, mismatch) -> str:
        """Format a single mismatch for inclusion in the prompt."""
        return f"""
Question: {mismatch.question_name}
Model's Answer: {mismatch.model_answer}
Correct Answer: {mismatch.ground_truth}
Analysis: {mismatch.detailed_analysis}
---"""
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the pattern analysis handler."""
        async def analyze_patterns(state: APOSState) -> Dict[str, Any]:
            try:
                if not state.mismatches:
                    logger.error("No analyzed mismatches available for pattern analysis")
                    raise ValueError("No analyzed mismatches available for pattern analysis")
                
                logger.info("Starting pattern analysis across mismatches")
                
                # Format mismatches and store in state
                state.mismatch_summaries = "\n".join(
                    self._format_mismatch_summary(m) for m in state.mismatches
                )
                
                # Create token counter callback
                token_counter = TokenCounterCallback()
                
                # Get analysis from LLM using state dict with token counting
                messages = self.chat_prompt.format_messages(**state.dict())
                result = await self.llm.ainvoke(
                    messages,
                    config={"callbacks": [token_counter]}
                )
                
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