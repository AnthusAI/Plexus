"""
Prompt optimization using LLMs via LangChain.
"""
import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from pathlib import Path

from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.messages import SystemMessage, HumanMessage

from plexus.apos.config import APOSConfig, ModelConfig
from plexus.apos.models import (
    PromptChange, 
    PatternInfo, 
    Recommendation, 
    Mismatch,
    MismatchAnalysis
)
from plexus.Registries import scorecard_registry
from plexus.Scorecard import Scorecard


logger = logging.getLogger('plexus.apos.optimizer')


class StreamingCallbackHandler(BaseCallbackHandler):
    """Custom streaming callback handler."""
    
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Print the token as it's generated."""
        print(token, end="", flush=True)
        
    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Print a newline when generation is complete."""
        print()


class PromptOptimizer:
    """
    Optimizes prompts using LLMs based on identified patterns and recommendations.
    
    This class is responsible for:
    1. Taking pattern analysis results
    2. Generating specific prompt improvements using LLMs
    3. Applying improvements to existing prompts
    4. Validating the changes
    """
    
    def __init__(self, config: APOSConfig):
        """Initialize the optimizer with configuration."""
        self.config = config
        self._setup_model()
        logger.info(f"Initialized prompt optimizer using {config.model.model_type}")
        
    def _setup_model(self):
        """Set up the LangChain LLM client based on configuration."""
        model_config = self.config.model
        
        # Setup LangChain caching
        cache_dir = Path(model_config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        set_llm_cache(SQLiteCache(database_path=str(cache_dir / "langchain.db")))
        
        # Setup callbacks
        callbacks = []
        if model_config.streaming:
            callbacks.append(StreamingCallbackHandler())
        
        # Initialize the LLM
        self.llm = ChatOpenAI(
            model_name=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            frequency_penalty=model_config.frequency_penalty,
            presence_penalty=model_config.presence_penalty,
            openai_api_key=model_config.api_key,
            openai_api_base=model_config.api_base,
            openai_organization=model_config.organization,
            request_timeout=model_config.request_timeout,
            max_retries=model_config.max_retries,
            callbacks=callbacks if callbacks else None
        )
        
        # Setup prompt templates
        self.system_template = SystemMessagePromptTemplate.from_template(
            """You are an expert at optimizing prompts for classification tasks.
            Your goal is to improve accuracy by making targeted improvements to the existing prompts.
            
            You will be shown:
            1. The current prompts being used
            2. Examples where the model gave wrong answers
            
            IMPORTANT:
            - DO NOT rewrite the prompts from scratch
            - Keep the existing structure and rules
            - Make minimal, targeted changes to fix the issues shown in the examples
            - Preserve all the detailed criteria and steps
            
            Return ONLY a raw JSON object with these fields:
            {{"system_message": "the improved system message (with same structure but targeted fixes)", 
              "user_message": "the improved user message (must contain {{text}} placeholder)",
              "rationale": "explanation of the specific changes made and why"}}"""
        )
        
        self.human_template = HumanMessagePromptTemplate.from_template(
            """Here are the current prompts and examples of misclassified cases:

            Current Prompts (these should be used as a foundation):
            system_message: "{current_system_message}"
            user_message: "{current_user_message}"

            Misclassified Examples:
            {patterns}
            
            Your task:
            1. Start with the current prompts and make targeted improvements
            2. Ensure the {{text}} variable is ONLY in the user_message
            3. Focus on fixing the misclassified cases while maintaining existing functionality
            4. Return ONLY a raw JSON object (no markdown, no code blocks)"""
        )
        
        self.chat_prompt = ChatPromptTemplate.from_messages([
            self.system_template,
            self.human_template
        ])
            
    def optimize_prompt(self, score_name: str, mismatches: List[MismatchAnalysis]) -> Dict[str, PromptChange]:
        """Generate optimized prompts based on the mismatches."""
        try:
            # Get current prompts
            current_prompts = self.get_current_prompts(score_name)
            logger.info(f"Optimizing prompts for score: {score_name}")
            logger.info("Current prompts loaded:")
            logger.info(f"System message: {current_prompts.get('system_message')}")
            logger.info(f"User message: {current_prompts.get('user_message')}")
            
            # Prepare context for the LLM
            context = {
                'current_system_message': current_prompts.get('system_message', ''),
                'current_user_message': current_prompts.get('user_message', ''),
                'patterns': self._format_mismatches(mismatches),
                'recommendation': "Improve the prompts to correctly handle the misclassified cases while maintaining accuracy on other cases."
            }
            
            # Log what we're sending to the LLM
            logger.info("Sending to LLM:")
            logger.info(f"System message template: {self.system_template.prompt.template}")
            logger.info(f"Human message template: {self.human_template.prompt.template}")
            logger.info("Context:")
            logger.info(f"- Current system message length: {len(context['current_system_message'])}")
            logger.info(f"- Current user message length: {len(context['current_user_message'])}")
            logger.info(f"- Number of mismatches: {len(mismatches)}")
            
            # Generate improvements using the chat prompt and LLM
            messages = self.chat_prompt.format_messages(**context)
            response = self.llm.invoke(messages).content
            logger.debug(f"LLM response: {response}")
            
            # Parse the response
            try:
                content = response.strip()
                # Remove markdown code blocks if present
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()
                
                if not content.startswith('{'): 
                    logger.error(f"Invalid JSON response: {content}")
                    raise ValueError("LLM response is not valid JSON")
                    
                prompt_data = json.loads(content)
                
                # Validate required fields in response
                required_fields = ['system_message', 'user_message', 'rationale']
                missing_fields = [f for f in required_fields if f not in prompt_data]
                if missing_fields:
                    logger.error(f"Missing required fields in LLM response: {missing_fields}")
                    raise ValueError(f"LLM response missing required fields: {missing_fields}")
                
                # Validate {text} variable is only in user_message
                if '{text}' in prompt_data['system_message']:
                    logger.error("system_message should not contain {text} variable")
                    raise ValueError("system_message should not contain {text} variable")
                if '{text}' not in prompt_data['user_message']:
                    logger.error("user_message must contain {text} variable")
                    raise ValueError("user_message must contain {text} variable")
                
                # Create PromptChange objects for each component
                changes = {}
                metadata = {
                    'score_name': score_name,
                    'num_mismatches': len(mismatches),
                    'mismatch_ids': [m.transcript_id for m in mismatches]
                }
                
                # Create changes for both components
                changes['system_message'] = PromptChange(
                    component='system_message',
                    old_text=current_prompts.get('system_message', ''),
                    new_text=prompt_data['system_message'],
                    rationale=prompt_data['rationale'],
                    metadata=metadata.copy()
                )
                
                changes['user_message'] = PromptChange(
                    component='user_message',
                    old_text=current_prompts.get('user_message', ''),
                    new_text=prompt_data['user_message'],
                    rationale=prompt_data['rationale'],
                    metadata=metadata.copy()
                )
                
                return changes
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}\nResponse: {content}")
                raise
            
        except Exception as e:
            logger.error(f"Error generating prompt improvements: {e}")
            raise
            
    def _format_mismatches(self, mismatches: List[MismatchAnalysis]) -> str:
        """Format mismatches to show concrete examples."""
        formatted = []
        for mismatch in mismatches:
            formatted.append(f"""
Predicted:    {mismatch.model_answer}
Ground Truth: {mismatch.ground_truth}

Explanation:
{mismatch.analysis}

Transcript:
{mismatch.transcript_text}

---""")
        return "\n".join(formatted)

    def _prepare_optimization_context(
        self,
        prompt_change: PromptChange,
        patterns: List[PatternInfo]
    ) -> Dict[str, Any]:
        """Prepare context for the LLM."""
        return {
            "component": prompt_change.component,
            "current_text": prompt_change.old_text,
            "improvement_rationale": prompt_change.rationale,
            "patterns": [
                {
                    "category": p.category,
                    "frequency": p.frequency,
                    "examples": [
                        {
                            "transcript_id": m.transcript_id,
                            "ground_truth": m.ground_truth,
                            "model_answer": m.model_answer,
                            "analysis": m.analysis
                        }
                        for m in p.example_mismatches[:2]  # Include up to 2 examples
                    ]
                }
                for p in patterns
            ]
        }
        
    def validate_change(self, prompt_change: PromptChange) -> bool:
        """
        Validate that the proposed change maintains the prompt's core functionality.
        
        Args:
            prompt_change: The proposed prompt change
            
        Returns:
            bool indicating if the change is valid
        """
        # TODO: Implement validation logic
        # This could include:
        # 1. Length checks
        # 2. Core concept preservation
        # 3. Readability metrics
        # 4. Test against sample inputs
        return True 

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the LLM."""
        return """You are an expert at optimizing prompts for classification tasks.
        Your goal is to improve prompt accuracy while maintaining clarity and conciseness.
        Analyze the provided patterns and recommendation to generate optimized prompts.
        Focus on addressing the identified issues while preserving the essential evaluation criteria.
        
        You will generate complete optimized prompts for both components:
        - system_message: Contains the core evaluation criteria and rules
        - user_message: Contains the specific question and context for evaluation"""

    def _get_human_prompt(self, recommendation: Recommendation, patterns: List[PatternInfo]) -> str:
        """Get the human prompt template with context."""
        return f"""Based on the following error patterns and recommendation, generate optimized prompts:

        Error Patterns:
        {self._format_patterns(patterns)}
        
        Recommendation:
        {recommendation.description}
        
        Generate optimized prompts that address these issues. Your response should be valid JSON with this structure:
        {{
            "system_message": "string - complete optimized system message with evaluation criteria and rules",
            "user_message": "string - complete optimized human message with question and context",
            "rationale": "string - detailed explanation of the improvements made and how they address the patterns"
        }}
        
        Important:
        1. Both system_message and user_message must be complete, standalone prompts
        2. Preserve all essential evaluation criteria while improving clarity and robustness
        3. Focus on addressing the identified error patterns
        4. Ensure your response contains ONLY the JSON object, no additional text"""

    def _format_patterns(self, patterns: List[PatternInfo]) -> str:
        """Format patterns to show concrete examples."""
        formatted = []
        for pattern in patterns:
            for example in pattern.example_mismatches:
                formatted.append(f"""
                Example {example.transcript_id}:
                Transcript: {example.metadata.get('transcript_text', 'Not available')}
                Expected Answer: {example.ground_truth}
                Model's Answer: {example.model_answer}
                Analysis: {example.analysis}
                """)
        return "\n".join(formatted)

    def get_current_prompts(self, score_name: str) -> Dict[str, str]:
        """Get the current prompts for a given score."""
        try:
            # Load scorecard
            logger.info(f"Loading scorecards for {score_name}")
            Scorecard.load_and_register_scorecards('scorecards/')
            
            # Get score configuration from the scorecard
            for scorecard_class in scorecard_registry._classes_by_key.values():
                scorecard_key = scorecard_class.properties.get('key') or scorecard_class.name
                logger.info(f"Checking scorecard: {scorecard_key}")
                
                scorecard = scorecard_class(scorecard=scorecard_key)
                score_config = next((score for score in scorecard.scores 
                                if score['name'] == score_name), None)
                
                if score_config:
                    logger.info(f"Found score config for {score_name}")
                    logger.info(f"Score config: {score_config}")
                    
                    # Look for Classifier node in graph
                    if 'graph' in score_config:
                        for node in score_config['graph']:
                            if node.get('class') == 'Classifier':
                                logger.info(f"Found Classifier node: {node}")
                                # Get prompts from the node configuration
                                prompts = {
                                    'system_message': node.get('system_message', ''),
                                    'user_message': node.get('user_message', '')
                                }
                                if prompts['system_message'] and prompts['user_message']:
                                    logger.info("Found prompts in Classifier node")
                                    return prompts
                    
                    # If no Classifier node found or no prompts in it, try top-level prompts
                    prompts = {
                        'system_message': score_config.get('system_message', ''),
                        'user_message': score_config.get('user_message', '')
                    }
                    
                    if prompts['system_message'] and prompts['user_message']:
                        logger.info("Using top-level prompts")
                        return prompts
                    else:
                        logger.error("No valid prompts found in score config")
                        raise ValueError(f"No prompts found for score: {score_name}")
            
            raise ValueError(f"No configuration found for score: {score_name}")
            
        except Exception as e:
            logger.error(f"Error getting current prompts for {score_name}: {e}")
            raise 