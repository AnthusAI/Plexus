"""
Common utilities for APOS nodes.
"""
import logging
from langchain_core.callbacks import AsyncCallbackHandler

logger = logging.getLogger('plexus.apos.utils')

class TokenCounterCallback(AsyncCallbackHandler):
    """Callback to count tokens used in LLM calls."""
    
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        
    async def on_llm_start(self, *args, **kwargs):
        self.input_tokens = 0
        self.output_tokens = 0
        
    async def on_llm_end(self, response, *args, **kwargs):
        try:
            # Handle both direct token_usage and nested llm_output formats
            if hasattr(response, 'llm_output') and response.llm_output:
                usage = response.llm_output.get('token_usage', {})
            else:
                # Try to get token usage directly from response
                usage = getattr(response, 'token_usage', {}) or {}
            
            # Safely get token counts with defaults
            self.input_tokens = usage.get('prompt_tokens', 0)
            self.output_tokens = usage.get('completion_tokens', 0)
            
            # If we still don't have tokens, try other common field names
            if not self.input_tokens and not self.output_tokens:
                self.input_tokens = usage.get('input_tokens', 0)
                self.output_tokens = usage.get('output_tokens', 0)
                
        except Exception as e:
            logger.warning(f"Failed to get token usage from LLM response: {e}")
            # Keep the last known token counts in case of error 