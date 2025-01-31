"""
Mismatch analyzer node for analyzing individual mismatches.
"""
import os
import logging
import json
from typing import Dict, Any, Callable, List
from dataclasses import asdict
import asyncio

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import MismatchAnalysis

logger = logging.getLogger('plexus.apos.nodes.mismatch')


class MismatchAnalysisOutput(BaseModel):
    """Schema for mismatch analysis response."""
    error_category: str
    root_cause: str
    detailed_analysis: str


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
        
        # Initialize LLM with only valid OpenAI parameters
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        ).with_structured_output(MismatchAnalysisOutput)
        
        logger.info(f"Initialized mismatch analyzer using {model_config.model_type}")
        self.prompt = self._create_prompt()
        
    def _create_prompt(self):
        """Create the analysis prompt template."""
        system_template = SystemMessagePromptTemplate.from_template(
            self.config.analyzer_model.prompts['system_template']
        )
        
        human_template = HumanMessagePromptTemplate.from_template(
            self.config.analyzer_model.prompts['human_template']
        )
        
        return ChatPromptTemplate.from_messages([
            system_template,
            human_template
        ])
    
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
            
            # Convert any non-serializable objects to their string representation for logging
            state_dict_serializable = {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v 
                                     for k, v in state_dict.items()}
            
            # Prepare the prompt with all variables
            messages = self.prompt.format_messages(**state_dict)
            
            # Get analysis from LLM
            analysis_result = await self.llm.ainvoke(messages)
            
            # Update mismatch with analysis results
            mismatch.detailed_analysis = analysis_result.detailed_analysis
            mismatch.error_category = analysis_result.error_category
            mismatch.root_cause = analysis_result.root_cause
            
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
                            original_explanation=mismatch.get('explanation', '')
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
                        'root_cause': m.root_cause
                    }
                    mismatch_dicts.append(mismatch_dict)
                
                with open(output_path, 'w') as f:
                    json.dump(mismatch_dicts, f, indent=4)
                logger.info(f"Saved {len(analyzed_mismatches)} mismatch analyses to {output_path}")
                
                # Update state with analyzed mismatches
                state.analyzed_mismatches = analyzed_mismatches
                
                return state.dict()
                
            except Exception as e:
                logger.error(f"Error analyzing mismatches: {e}")
                return self.handle_error(e, state)
                
        return analyze_mismatches 