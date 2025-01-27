"""
Mismatch analysis functionality for APOS.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict
import json
import asyncio

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.models import MismatchAnalysis
from plexus.apos.config import APOSConfig

logger = logging.getLogger('plexus.apos.analyzer')

class MismatchAnalysisOutput(BaseModel):
    """Schema for mismatch analysis response."""
    error_category: str = Field(description="The type of error that occurred (e.g., 'Misinterpretation of Context', 'Overlooked Detail', 'Script Adherence Issue')")
    root_cause: str = Field(description="The fundamental reason why the model made this specific mistake")
    detailed_analysis: str = Field(description="A thorough analysis of why this mismatch occurred, including specific details from the transcript and model's reasoning")

class MismatchAnalyzer:
    """
    Analyzes individual mismatches to understand why they occurred and how to fix them.
    """
    
    def __init__(self, config: APOSConfig):
        """Initialize the analyzer with configuration."""
        self.config = config
        
        # Initialize LLM with analyzer-specific model config
        model_config = config.analyzer_model
        
        # Setup LangChain caching if specified
        if hasattr(model_config, 'cache_dir'):
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
            # Prepare the prompt
            messages = self.prompt.format_messages(
                question_name=mismatch.question_name,
                transcript_text=mismatch.transcript_text,
                model_answer=mismatch.model_answer,
                ground_truth=mismatch.ground_truth,
                original_explanation=mismatch.original_explanation
            )
            
            # Get analysis from LLM
            analysis_result = await self.llm.ainvoke(messages)
            
            # Update mismatch with analysis results
            mismatch.detailed_analysis = analysis_result.detailed_analysis
            mismatch.error_category = analysis_result.error_category
            mismatch.root_cause = analysis_result.root_cause
            
            logger.info(f"Completed analysis for mismatch {mismatch.transcript_id}")
            return mismatch
            
        except Exception as e:
            logger.error(f"Error analyzing mismatch {mismatch.transcript_id}: {e}")
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
            logger.error(f"Failed to analyze mismatch {mismatch.transcript_id}: {e}")
            return mismatch 