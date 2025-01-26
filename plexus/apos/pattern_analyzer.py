"""
Pattern analysis functionality for APOS.

This module handles the analysis of patterns across multiple mismatches,
identifying common issues and suggesting improvements.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.models import MismatchAnalysis, SynthesisResult

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
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize the analyzer with an optional LLM."""
        self.llm = llm or ChatOpenAI(
            model="gpt-4o-mini-2024-07-18",
            temperature=0.1,  # Low temperature for consistent analysis
            max_tokens=2000  # Higher token limit for analyzing multiple mismatches
        ).with_structured_output(PatternAnalysisOutput)
        self.prompt = self._create_prompt()
        
    def _create_prompt(self):
        """Create the pattern analysis prompt template."""
        template = """Review these mismatches where the model gave incorrect answers. For each mismatch, we've analyzed why the prompt misguided the model.

Your task is to:
1. Look at all the mismatch analyses
2. Identify the common issues in how the prompt is misguiding the model
3. Create a clear summary explaining how the prompt is causing these problems

Mismatches and their analyses:
{mismatch_summaries}

Focus on being clear and specific about how the prompt is causing these issues."""

        return ChatPromptTemplate.from_template(template)
        
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