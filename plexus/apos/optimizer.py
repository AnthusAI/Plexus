"""
Prompt optimization using LLMs via LangChain.
"""
import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.config import APOSConfig, ModelConfig
from plexus.apos.models import (
    PromptChange, 
    Mismatch,
    MismatchAnalysis,
    SynthesisResult
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


class PromptImprovement(BaseModel):
    """Schema for prompt improvement response."""
    system_message: str = Field(description="The improved system message with meaningful changes to fix issues")
    user_message: str = Field(description="The improved user message (must contain {{text}} placeholder)")
    rationale: str = Field(description="Explanation of the specific changes made and why they will help")


class PromptOptimizer:
    """
    Optimizes prompts using LLM-based analysis and improvement suggestions.
    """
    
    def __init__(self, config: APOSConfig):
        """Initialize the optimizer with configuration."""
        self.config = config
        
        # Initialize LLM with optimizer-specific model config
        model_config = config.optimizer_model
        
        # Setup LangChain caching if specified
        if hasattr(model_config, 'cache_dir'):
            from langchain_community.cache import SQLiteCache
            from langchain_core.globals import set_llm_cache
            set_llm_cache(SQLiteCache(database_path=f"{model_config.cache_dir}/optimizer_cache.db"))
        
        # Initialize LLM with only valid OpenAI parameters
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        ).with_structured_output(PromptImprovement)
        
        logger.info(f"Initialized prompt optimizer using {model_config.model_type}")
        
        # Setup prompt templates
        self.system_template = SystemMessagePromptTemplate.from_template(
            self.config.optimizer_model.prompts['system_template']
        )
        
        self.human_template = HumanMessagePromptTemplate.from_template(
            self.config.optimizer_model.prompts['human_template']
        )
        
        self.chat_prompt = ChatPromptTemplate.from_messages([
            self.system_template,
            self.human_template
        ])

    def optimize_prompt(self, score_name: str, synthesis_result: SynthesisResult, evaluation_instance) -> Dict[str, PromptChange]:
        """Generate optimized prompts based on analysis of issues."""
        try:
            # Log the pattern analysis results
            logger.info("\n=== Pattern Analysis Results ===")
            logger.info("Common Issues:")
            for issue in synthesis_result.common_issues:
                logger.info(f"- {issue}")
            logger.info("\nSummary:")
            logger.info(synthesis_result.summary)
            logger.info("===============================\n")
            
            # Get current prompts from evaluation instance
            current_prompts = evaluation_instance.get_current_prompts().get(score_name, {})
            if not current_prompts:
                logger.warning(f"No current prompts found for {score_name}, falling back to scorecard")
                current_prompts = self.get_current_prompts(score_name)
            
            # Prepare context for the LLM
            context = {
                'current_system_message': current_prompts.get('system_message', ''),
                'current_user_message': current_prompts.get('user_message', ''),
                'common_issues': "\n".join(f"- {issue}" for issue in synthesis_result.common_issues),
                'summary': synthesis_result.summary
            }
            
            # Generate improvements using the chat prompt and LLM
            messages = self.chat_prompt.format_messages(**context)
            prompt_data = self.llm.invoke(messages)
            
            # Validate {{text}} variable is only in user_message
            if '{{text}}' in prompt_data.system_message:
                logger.error("system_message should not contain {{text}} variable")
                raise ValueError("system_message should not contain {{text}} variable")
            if '{{text}}' not in prompt_data.user_message:
                logger.error("user_message must contain {{text}} variable")
                raise ValueError("user_message must contain {{text}} variable")
            
            # Create PromptChange objects for each component
            changes = {}
            metadata = {
                'score_name': score_name,
                'analysis_summary': synthesis_result.summary,
                'iteration': evaluation_instance.current_iteration
            }
            logger.info(f"DEBUG: Creating changes with metadata: {metadata}")
            
            # Only create changes if the prompts are actually different
            if prompt_data.system_message.strip() != current_prompts.get('system_message', '').strip():
                changes['system_message'] = PromptChange(
                    component='system_message',
                    old_text=current_prompts.get('system_message', ''),
                    new_text=prompt_data.system_message,
                    rationale=prompt_data.rationale,
                    metadata=metadata.copy()
                )
                logger.info("Generated new system message")
                logger.info(f"DEBUG: Created system message change: {changes['system_message']}")
            
            if prompt_data.user_message.strip() != current_prompts.get('user_message', '').strip():
                changes['user_message'] = PromptChange(
                    component='user_message',
                    old_text=current_prompts.get('user_message', ''),
                    new_text=prompt_data.user_message,
                    rationale=prompt_data.rationale,
                    metadata=metadata.copy()
                )
                logger.info("Generated new user message")
                logger.info(f"DEBUG: Created user message change: {changes['user_message']}")
            
            if not changes:
                logger.warning("No meaningful changes to prompts were needed")
            else:
                logger.info(f"DEBUG: Final changes to return: {changes}")
            
            return changes
            
        except Exception as e:
            logger.error(f"Error generating prompt improvements: {e}")
            raise

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