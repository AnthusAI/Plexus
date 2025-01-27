"""
Pattern analysis functionality for APOS.

This module handles the analysis of patterns across multiple mismatches,
identifying common issues and suggesting improvements.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.models import MismatchAnalysis, SynthesisResult
from plexus.apos.config import APOSConfig

logger = logging.getLogger('plexus.apos.pattern_analyzer')

class PatternAnalysisError(Exception):
    """Raised when pattern analysis fails."""
    pass

class PatternAnalysisOutput(BaseModel):
    """Schema for pattern analysis response."""
    common_issues: List[str] = Field(description="List of common issues found across the mismatches that explain why the prompt misguided the model")
    summary: str = Field(description="A clear summary of how the current prompt is causing these mismatches")

class PatternAnalyzer:
    """
    Analyzes patterns across multiple mismatches to identify systematic issues
    and suggest improvements.
    """
    
    def __init__(self, config: APOSConfig):
        """Initialize the analyzer with configuration."""
        self.config = config
        
        # Initialize LLM with pattern analyzer-specific model config
        model_config = config.pattern_analyzer_model
        
        # Setup LangChain caching if specified
        if hasattr(model_config, 'cache_dir'):
            from langchain_community.cache import SQLiteCache
            from langchain_core.globals import set_llm_cache
            set_llm_cache(SQLiteCache(database_path=f"{model_config.cache_dir}/pattern_analyzer_cache.db"))
        
        # Initialize LLM with only valid OpenAI parameters
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        ).with_structured_output(PatternAnalysisOutput)
        
        logger.info(f"Initialized pattern analyzer using {model_config.model_type}")
        self.prompt = self._create_prompt()
        
    def _create_prompt(self):
        """Create the pattern analysis prompt template."""
        system_template = SystemMessagePromptTemplate.from_template(
            self.config.pattern_analyzer_model.prompts['system_template']
        )
        
        human_template = HumanMessagePromptTemplate.from_template(
            self.config.pattern_analyzer_model.prompts['human_template']
        )
        
        return ChatPromptTemplate.from_messages([
            system_template,
            human_template
        ])
        
    def _format_mismatch_summary(self, mismatch: MismatchAnalysis) -> str:
        """Format a single mismatch for inclusion in the prompt."""
        return f"""
Question: {mismatch.question_name}
Model's Answer: {mismatch.model_answer}
Correct Answer: {mismatch.ground_truth}
Analysis: {mismatch.detailed_analysis}
---"""

    async def analyze_patterns(self, mismatches: List[MismatchAnalysis]) -> SynthesisResult:
        """
        Analyze patterns across a set of mismatches.
        
        Args:
            mismatches: List of analyzed mismatches to find patterns in
            
        Returns:
            SynthesisResult containing common issues and a summary
            
        Raises:
            PatternAnalysisError: If pattern analysis fails
        """
        if not mismatches:
            raise PatternAnalysisError("No mismatches provided for pattern analysis")
            
        try:
            # Format mismatches for the prompt
            mismatch_summaries = "\n".join(
                self._format_mismatch_summary(m) for m in mismatches
            )
            
            # Prepare the prompt
            messages = self.prompt.format_messages(
                mismatch_summaries=mismatch_summaries
            )
            
            # Get analysis from LLM
            analysis_result = await self.llm.ainvoke(messages)
            
            # Create synthesis result
            result = SynthesisResult(
                common_issues=analysis_result.common_issues,
                summary=analysis_result.summary
            )
            
            logger.info("Completed pattern analysis")
            return result
            
        except Exception as e:
            error_msg = f"Error analyzing patterns: {str(e)}"
            logger.error(error_msg)
            raise PatternAnalysisError(error_msg) from e 