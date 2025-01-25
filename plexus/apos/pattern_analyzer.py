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
from langchain.output_parsers import ResponseSchema, StructuredOutputParser

from plexus.apos.models import MismatchAnalysis, SynthesisResult

logger = logging.getLogger('plexus.apos.pattern_analyzer')

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
        )
        self.output_parser = self._create_output_parser()
        self.prompt = self._create_prompt()
        
    def _create_output_parser(self):
        """Create a structured output parser for pattern analysis results."""
        schemas = [
            ResponseSchema(
                name="error_patterns",
                description="""List of identified error patterns. Each pattern should have:
                - pattern_name: A descriptive name for the pattern
                - description: Detailed description of the pattern
                - frequency: How many mismatches show this pattern
                - examples: List of transcript IDs that exemplify this pattern
                - severity: How critical this pattern is to address (HIGH/MEDIUM/LOW)"""
            ),
            ResponseSchema(
                name="improvement_suggestions",
                description="""List of suggested improvements. Each suggestion should have:
                - target: What aspect of the system to improve (e.g., 'prompt structure', 'context handling')
                - suggestion: Detailed description of the proposed improvement
                - rationale: Why this improvement would help
                - affected_patterns: List of pattern names this would address"""
            ),
            ResponseSchema(
                name="overall_assessment",
                description="A high-level assessment of the systematic issues found and their impact on model performance"
            )
        ]
        return StructuredOutputParser.from_response_schemas(schemas)
        
    def _create_prompt(self):
        """Create the pattern analysis prompt template."""
        template = """Analyze the following set of mismatches to identify patterns and suggest improvements.

Mismatches:
{mismatch_summaries}

Your task is to:
1. Identify patterns in how and why the model is making mistakes
2. Suggest specific improvements that would address these patterns
3. Provide an overall assessment of the systematic issues

Focus on finding actionable patterns that can lead to concrete improvements.
Look for commonalities in:
- Error categories
- Root causes
- Types of misunderstandings
- Specific aspects of the transcripts that cause issues

Provide your analysis in the following structured format:
{format_instructions}

Remember to:
- Focus on systematic patterns rather than individual cases
- Prioritize patterns that appear multiple times
- Make specific, actionable improvement suggestions
- Connect improvements to the patterns they would address"""

        return ChatPromptTemplate.from_template(template)
        
    def _format_mismatch_summary(self, mismatch: MismatchAnalysis) -> str:
        """Format a single mismatch for inclusion in the prompt."""
        return f"""
Transcript ID: {mismatch.transcript_id}
Question: {mismatch.question_name}
Error Category: {mismatch.error_category}
Root Cause: {mismatch.root_cause}
Detailed Analysis: {mismatch.detailed_analysis}
---"""

    async def analyze_patterns(self, mismatches: List[MismatchAnalysis]) -> SynthesisResult:
        """
        Analyze patterns across a set of mismatches.
        
        Args:
            mismatches: List of analyzed mismatches to find patterns in
            
        Returns:
            SynthesisResult containing identified patterns and improvement suggestions
        """
        try:
            # Format mismatches for the prompt
            mismatch_summaries = "\n".join(
                self._format_mismatch_summary(m) for m in mismatches
            )
            
            # Prepare the prompt
            format_instructions = self.output_parser.get_format_instructions()
            messages = self.prompt.format_messages(
                mismatch_summaries=mismatch_summaries,
                format_instructions=format_instructions
            )
            
            # Get analysis from LLM
            response = await self.llm.ainvoke(messages)
            analysis_result = self.output_parser.parse(response.content)
            
            # Create synthesis result
            result = SynthesisResult(
                error_patterns=analysis_result["error_patterns"],
                improvement_suggestions=analysis_result["improvement_suggestions"],
                overall_assessment=analysis_result["overall_assessment"]
            )
            
            logger.info(f"Completed pattern analysis for {len(mismatches)} mismatches")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")
            raise 