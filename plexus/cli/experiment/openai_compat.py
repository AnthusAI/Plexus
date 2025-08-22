"""
OpenAI Model Compatibility Layer.

Provides compatibility wrappers for newer OpenAI models (like o3) that have
different parameter requirements than what LangChain expects.
"""

import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class O3CompatibleChatOpenAI(ChatOpenAI):
    """
    Custom ChatOpenAI wrapper for o3 model compatibility with LangChain.
    
    The o3 model has specific parameter requirements that differ from older models:
    - Requires temperature=1 (fixed)
    - Uses max_completion_tokens instead of max_tokens
    - Doesn't support stop, presence_penalty, frequency_penalty parameters
    """
    
    def __init__(self, **kwargs):
        # Force temperature to 1 for o3 models
        kwargs['temperature'] = 1
        
        # Replace max_tokens with max_completion_tokens if present
        if 'max_tokens' in kwargs:
            kwargs['max_completion_tokens'] = kwargs.pop('max_tokens')
        
        # Remove unsupported parameters
        unsupported_params = ["stop", "presence_penalty", "frequency_penalty"]
        for param in unsupported_params:
            kwargs.pop(param, None)
            
        super().__init__(**kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Override to remove stop parameter entirely for o3 models and ensure no streaming."""
        kwargs.pop('stop', None)  # Remove stop parameter entirely for o3 models
        kwargs['stream'] = False  # Force streaming to be disabled for o3 models
        return super()._generate(messages, stop=None, run_manager=run_manager, **kwargs)

    @property
    def _default_params(self) -> Dict[str, Any]:
        """Override default params to remove unsupported parameters."""
        params = super()._default_params
        
        # Ensure we have a dict to work with
        if isinstance(params, dict):
            params = params.copy()
        else:
            params = {}  # Handle cases where super()._default_params is not a dict
            
        # Remove unsupported parameters
        unsupported_params = ["stop", "presence_penalty", "frequency_penalty"]
        for param in unsupported_params:
            params.pop(param, None)
        
        # Force streaming to be disabled
        params['stream'] = False
            
        return params

    @property
    def _llm_type(self) -> str:
        return "o3-compatible-openai"

