"""
Mismatch analysis functionality for APOS.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict
import json
import asyncio

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.models import MismatchAnalysis

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
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize the analyzer with an optional LLM."""
        self.llm = llm or ChatOpenAI(
            model="gpt-4o-mini-2024-07-18",
            temperature=0.1,  # Low temperature for consistent analysis
            max_tokens=1000
        ).with_structured_output(MismatchAnalysisOutput)
        self.prompt = self._create_prompt()
        
    def _create_prompt(self):
        """Create the analysis prompt template."""
        template = """Analyze this specific case where the model's prediction did not match the ground truth.

Context:
The model was asked to evaluate a transcript and determine: {question_name}

Transcript:
{transcript_text}

Model's Prediction: {model_answer}
Ground Truth: {ground_truth}

Model's Original Explanation:
{original_explanation}

Your task is to:
1. Analyze exactly why the model made the wrong prediction in this specific case
2. Identify the root cause of the error
3. Provide a detailed analysis of what went wrong

Remember to:
- Be specific and reference exact details from the transcript
- Consider both what the model did wrong AND why it thought it was right"""

        return ChatPromptTemplate.from_template(template)
        
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