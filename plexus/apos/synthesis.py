"""
Pattern synthesis functionality for APOS.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser

from plexus.apos.models import MismatchAnalysis, SynthesisResult

logger = logging.getLogger('plexus.apos.synthesis')

class PatternSynthesizer:
    """
    Synthesizes patterns from individual mismatch analyses through recursive analysis.
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """Initialize the synthesizer with an optional LLM."""
        self.llm = llm or ChatOpenAI(
            model="gpt-4o-mini-2024-07-18",
            temperature=0.1,
            max_tokens=2000
        )
        self.output_parser = self._create_output_parser()
        self.synthesis_prompt = self._create_synthesis_prompt()
        self.merge_prompt = self._create_merge_prompt()
        
    def _create_output_parser(self):
        """Create a structured output parser for synthesis results."""
        schemas = [
            ResponseSchema(
                name="error_patterns",
                description="List of identified error patterns, each with pattern_name, description, frequency, and severity"
            ),
            ResponseSchema(
                name="improvement_suggestions",
                description="List of improvement suggestions, each with target_area, suggestion, and expected_impact"
            ),
            ResponseSchema(
                name="overall_assessment",
                description="High-level assessment of the model's performance and key areas for improvement"
            )
        ]
        return StructuredOutputParser.from_response_schemas(schemas)
        
    def _create_synthesis_prompt(self):
        """Create the prompt template for initial synthesis of a group of mismatches."""
        template = """Analyze this group of mismatch analyses to identify patterns and systematic issues.

Mismatch Analyses:
{mismatch_analyses}

Your task is to:
1. Identify common patterns in the types of errors being made
2. Assess which patterns are most impactful or concerning
3. Suggest systematic improvements that could address multiple issues
4. Provide an overall assessment of the model's performance

Provide your analysis in the following structured format:
{format_instructions}

Remember to:
- Focus on patterns that appear across multiple mismatches
- Consider both the frequency and severity of error patterns
- Prioritize actionable improvements that could address multiple issues
- Be specific about how each improvement would help"""

        return ChatPromptTemplate.from_template(template)
        
    def _create_merge_prompt(self):
        """Create the prompt template for merging multiple synthesis results."""
        template = """Merge and synthesize these analysis results to identify higher-level patterns and insights.

Previous Analyses:
{previous_analyses}

Your task is to:
1. Identify broader patterns that emerge across these analyses
2. Consolidate similar patterns and suggestions
3. Highlight the most significant findings
4. Provide a comprehensive assessment

Provide your synthesis in the following structured format:
{format_instructions}

Remember to:
- Look for connections between different patterns
- Consider how patterns might interact or compound
- Prioritize the most impactful improvements
- Maintain specific, actionable suggestions"""

        return ChatPromptTemplate.from_template(template)
        
    def _format_mismatch_analyses(self, analyses: List[MismatchAnalysis]) -> str:
        """Format mismatch analyses for the prompt."""
        formatted = []
        for i, analysis in enumerate(analyses, 1):
            formatted.append(f"""
Analysis {i}:
Error Category: {analysis.error_category}
Root Cause: {analysis.root_cause}
Impact Severity: {analysis.impact_severity}
Detailed Analysis: {analysis.detailed_analysis}
Suggested Improvements: {analysis.suggested_improvements}
""")
        return "\n".join(formatted)
        
    def _format_synthesis_results(self, results: List[SynthesisResult]) -> str:
        """Format synthesis results for the merge prompt."""
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"""
Synthesis {i}:
Error Patterns: {json.dumps(result.error_patterns, indent=2)}
Improvement Suggestions: {json.dumps(result.improvement_suggestions, indent=2)}
Overall Assessment: {result.overall_assessment}
""")
        return "\n".join(formatted)
        
    async def _synthesize_group(self, analyses: List[MismatchAnalysis]) -> SynthesisResult:
        """Synthesize patterns from a group of mismatch analyses."""
        try:
            format_instructions = self.output_parser.get_format_instructions()
            messages = self.synthesis_prompt.format_messages(
                mismatch_analyses=self._format_mismatch_analyses(analyses),
                format_instructions=format_instructions
            )
            
            response = await self.llm.ainvoke(messages)
            result = self.output_parser.parse(response.content)
            
            return SynthesisResult(
                error_patterns=result["error_patterns"],
                improvement_suggestions=result["improvement_suggestions"],
                overall_assessment=result["overall_assessment"]
            )
            
        except Exception as e:
            logger.error(f"Error synthesizing group of {len(analyses)} analyses: {e}")
            raise
            
    async def _merge_syntheses(self, results: List[SynthesisResult]) -> SynthesisResult:
        """Merge multiple synthesis results into a higher-level synthesis."""
        try:
            format_instructions = self.output_parser.get_format_instructions()
            messages = self.merge_prompt.format_messages(
                previous_analyses=self._format_synthesis_results(results),
                format_instructions=format_instructions
            )
            
            response = await self.llm.ainvoke(messages)
            result = self.output_parser.parse(response.content)
            
            return SynthesisResult(
                error_patterns=result["error_patterns"],
                improvement_suggestions=result["improvement_suggestions"],
                overall_assessment=result["overall_assessment"]
            )
            
        except Exception as e:
            logger.error(f"Error merging synthesis results: {e}")
            raise
            
    async def synthesize_patterns(self, analyses: List[MismatchAnalysis], group_size: int = 5) -> SynthesisResult:
        """
        Synthesize patterns from mismatch analyses through recursive analysis.
        
        Args:
            analyses: List of mismatch analyses to synthesize
            group_size: Number of analyses to process in each initial group
            
        Returns:
            Synthesized patterns and improvements
        """
        if not analyses:
            logger.warning("No analyses provided for pattern synthesis")
            return SynthesisResult([], [], "No analyses to synthesize")
            
        # Split analyses into groups
        groups = [analyses[i:i + group_size] for i in range(0, len(analyses), group_size)]
        logger.info(f"Split {len(analyses)} analyses into {len(groups)} groups of size {group_size}")
        
        # First level: Synthesize each group
        group_results = []
        for group in groups:
            try:
                result = await self._synthesize_group(group)
                group_results.append(result)
            except Exception as e:
                logger.error(f"Error processing group of {len(group)} analyses: {e}")
                continue
                
        if not group_results:
            logger.error("No successful group syntheses")
            return SynthesisResult([], [], "Failed to synthesize any groups")
            
        # If only one group, return its results
        if len(group_results) == 1:
            return group_results[0]
            
        # Second level: Merge group results
        try:
            final_synthesis = await self._merge_syntheses(group_results)
            logger.info("Successfully merged synthesis results")
            return final_synthesis
            
        except Exception as e:
            logger.error(f"Error in final synthesis merge: {e}")
            # Return the first group's results as fallback
            return group_results[0] 