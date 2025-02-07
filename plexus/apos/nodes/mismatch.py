"""
Mismatch analyzer node for analyzing individual mismatches.
"""
import os
import logging
import json
from typing import Dict, Any, Callable, List
import asyncio

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from jinja2 import Template

from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import MismatchAnalysis
from plexus.apos.utils import TokenCounterCallback

logger = logging.getLogger('plexus.apos.nodes.mismatch')

class MismatchAnalysisOutput(BaseModel):
    """Schema for mismatch analysis response."""
    error_category: str = Field(
        description="The category of the error",
        min_length=1
    )
    root_cause: str = Field(
        description="The root cause of the mismatch",
        min_length=1
    )
    detailed_analysis: str = Field(
        description="Detailed analysis of the mismatch",
        min_length=1
    )
    prompts_contribution: str = Field(
        description="Analysis of how the prompts may have contributed to the error",
        min_length=1
    )

    class Config:
        validate_assignment = True
        extra = "forbid"  # Prevent extra fields


class MismatchAnalyzerNode(APOSNode):
    """Node for analyzing individual mismatches."""
    
    def _setup_node(self) -> None:
        """Set up the mismatch analyzer components."""
        model_config = self.config.analyzer_model
        
        # Create cache directory if it doesn't exist
        os.makedirs(model_config.cache_dir, exist_ok=True)
        logger.info(f"Ensuring cache directory exists: {model_config.cache_dir}")
        
        # Initialize LLM and cache
        from langchain_community.cache import SQLiteCache
        from langchain_core.globals import set_llm_cache
        set_llm_cache(SQLiteCache(database_path=f"{model_config.cache_dir}/analyzer_cache.db"))
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        )
        
        # Set up output parser
        self.parser = JsonOutputParser(pydantic_object=MismatchAnalysisOutput)
        
        # Store raw templates for Jinja2
        self.system_template_str = (
            model_config.prompts['system_template'] + 
            "\n\nIMPORTANT: Your response MUST be in JSON format following this schema:\n" +
            "{{format_instructions}}"  # Use Jinja2 variable instead of direct substitution
        )
        self.human_template_str = model_config.prompts['human_template']
        
        logger.info(f"Initialized mismatch analyzer using {model_config.model_type}")
    
    async def analyze_mismatch(self, mismatch: MismatchAnalysis) -> MismatchAnalysis:
        """
        Analyze a single mismatch in detail.
        
        Args:
            mismatch: The mismatch case to analyze
            
        Returns:
            Updated MismatchAnalysis with detailed analysis
        """
        try:
            # Set current mismatch in state
            self.state.current_mismatch = mismatch
            
            # Debug logging
            state_dict = self.state.dict(exclude_unset=True, exclude_none=True)
            
            # Add format instructions directly to state_dict
            state_dict["format_instructions"] = self.parser.get_format_instructions()
            
            # Create token counter callback
            token_counter = TokenCounterCallback()
            
            # Render templates using Jinja2
            system_template = Template(self.system_template_str)
            human_template = Template(self.human_template_str)
            
            # Render the messages directly
            messages = [
                {"role": "system", "content": system_template.render(**state_dict)},
                {"role": "user", "content": human_template.render(**state_dict)}
            ]
            
            # Get analysis from LLM
            response = await self.llm.ainvoke(
                messages,
                config={"callbacks": [token_counter]}
            )
            
            # Debug log the raw response
            logger.debug(f"Mismatch Raw LLM response: {response.content}")
            
            # Clean and parse the response content
            content = response.content
            if content.startswith("```") and content.endswith("```"):
                lines = content.split("\n")
                if len(lines) >= 3:
                    content = "\n".join(lines[1:-1])
            
            # Parse the response
            parsed_dict = self.parser.parse(content)
            if not isinstance(parsed_dict, dict):
                raise ValueError(f"Expected dictionary from parser, got {type(parsed_dict)}")
            
            analysis_result = MismatchAnalysisOutput(**parsed_dict)
            
            # Track cost
            self.track_llm_cost(
                state=self.state,
                model_name=self.config.analyzer_model.model_type,
                input_tokens=token_counter.input_tokens,
                output_tokens=token_counter.output_tokens
            )
            
            # Update mismatch with analysis results
            mismatch.detailed_analysis = analysis_result.detailed_analysis
            mismatch.error_category = analysis_result.error_category
            mismatch.root_cause = analysis_result.root_cause
            mismatch.prompts_contribution = analysis_result.prompts_contribution
            
            logger.info(f"Completed analysis for mismatch {mismatch.form_id}")
            return mismatch
            
        except Exception as e:
            logger.error(f"Error analyzing mismatch {mismatch.form_id}: {e}")
            raise
    
    async def analyze_mismatches(self, mismatches: List[MismatchAnalysis]) -> List[MismatchAnalysis]:
        """
        Analyze a list of mismatches concurrently.
        
        Args:
            mismatches: List of mismatches to analyze
            
        Returns:
            List of analyzed mismatches
        """
        # Create tasks for all mismatches
        tasks = []
        for mismatch in mismatches:
            task = asyncio.create_task(self._analyze_mismatch_with_error_handling(mismatch))
            tasks.append(task)
            
        # Wait for all tasks to complete
        analyzed = await asyncio.gather(*tasks)
        return analyzed
    
    async def _analyze_mismatch_with_error_handling(self, mismatch: MismatchAnalysis) -> MismatchAnalysis:
        """
        Wrapper around analyze_mismatch that handles errors gracefully.
        
        Args:
            mismatch: The mismatch to analyze
            
        Returns:
            Analyzed mismatch or original mismatch if analysis fails
        """
        try:
            return await self.analyze_mismatch(mismatch)
        except Exception as e:
            logger.error(f"Failed to analyze mismatch {mismatch.form_id}: {e}")
            return mismatch
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the handler function for this node."""
        
        async def analyze_mismatches(state: APOSState) -> Dict[str, Any]:
            """Analyze mismatches from evaluation."""
            try:
                if not state.mismatches:
                    logger.warning("No mismatches available for analysis")
                    return state.dict()
                
                logger.info(f"Analyzing {len(state.mismatches)} mismatches individually")
                
                # Store state for access in analyze_mismatch
                self.state = state
                
                # Get scorecard and score names from metadata
                scorecard_name = state.metadata.get("scorecard_name")
                score_name = state.metadata.get("score_name")
                
                if not scorecard_name or not score_name:
                    logger.error("Missing scorecard_name or score_name in metadata")
                    return state.dict()
                
                # Create directory structure
                iteration_dir = os.path.join(
                    "optimization_history",
                    scorecard_name,
                    score_name,
                    f"iteration_{state.current_iteration}"
                )
                os.makedirs(iteration_dir, exist_ok=True)
                state.metadata["iteration_dir"] = iteration_dir
                
                # Convert raw mismatches to MismatchAnalysis objects
                mismatch_analyses = []
                for mismatch in state.mismatches:
                    # Handle both dict and MismatchAnalysis objects
                    if isinstance(mismatch, dict):
                        analysis = MismatchAnalysis(
                            form_id=mismatch.get('form_id'),
                            question_name=mismatch.get('question'),
                            transcript_text=mismatch.get('transcript', ''),
                            model_answer=mismatch.get('predicted', ''),
                            ground_truth=mismatch.get('ground_truth', ''),
                            original_explanation=mismatch.get('explanation', ''),
                            prompts_contribution=mismatch.get('prompts_contribution', '')
                        )
                    else:
                        # If it's already a MismatchAnalysis, use it as is
                        analysis = mismatch
                    mismatch_analyses.append(analysis)
                
                # Analyze mismatches
                analyzed_mismatches = await self.analyze_mismatches(mismatch_analyses)
                
                # Save analyses - convert back to dict format expected by evaluation
                output_path = os.path.join(iteration_dir, "mismatches.json")
                mismatch_dicts = []
                for m in analyzed_mismatches:
                    mismatch_dict = {
                        'form_id': m.form_id,
                        'question': m.question_name,
                        'predicted': m.model_answer,
                        'ground_truth': m.ground_truth,
                        'original_explanation': m.original_explanation,
                        'detailed_analysis': m.detailed_analysis,
                        'error_category': m.error_category,
                        'root_cause': m.root_cause,
                        'prompts_contribution': m.prompts_contribution
                    }
                    mismatch_dicts.append(mismatch_dict)
                
                with open(output_path, 'w') as f:
                    json.dump(mismatch_dicts, f, indent=4)
                logger.info(f"Saved {len(analyzed_mismatches)} mismatch analyses to {output_path}")
                
                # Update state with analyzed mismatches
                state.analyzed_mismatches = analyzed_mismatches
                
                # Log current iteration costs
                logger.info(
                    f"Iteration {state.current_iteration} costs - "
                    f"This iteration: ${float(state.current_iteration_cost):.4f}, "
                    f"Total so far: ${float(state.total_cost):.4f}"
                )
                
                return state.dict()
                
            except Exception as e:
                logger.error(f"Error analyzing mismatches: {e}")
                return self.handle_error(e, state)
                
        return analyze_mismatches 