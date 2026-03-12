"""
Module for testing Ollama LLM integration.
"""

import logging
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

def test_ollama_chat(
    model: str = 'gemma3:27b',
    prompt: str = 'Why is the sky blue?',
    additional_params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Test Ollama LLM chat functionality.
    
    Args:
        model: The model to use, defaults to 'gemma3:27b'
        prompt: The prompt to send to the model, defaults to 'Why is the sky blue?'
        additional_params: Additional parameters to pass to the Ollama API
        
    Returns:
        The response content from the model
    """
    # Try to import ollama first, before doing anything else
    try:
        import ollama
        from ollama import chat, ChatResponse
    except ImportError as e:
        error_msg = (
            "The 'ollama' package is not installed. Install it with: pip install ollama\n"
            "Make sure you're using the correct Python environment (e.g., py311)"
        )
        logger.error(error_msg)
        return f"ERROR: {error_msg}"
    
    try:
        # Prepare parameters
        params = {}
        if additional_params:
            params.update(additional_params)
            
        logger.info(f"Sending request to Ollama model: {model}")
        logger.debug(f"Prompt: {prompt}")
        
        # Make the API call
        response: ChatResponse = chat(
            model=model,
            messages=[
                {
                    'role': 'user',
                    'content': prompt,
                }
            ],
            **params
        )
        
        # Extract and return the response content
        content = response.message.content
        logger.debug(f"Received response: {content[:100]}...")
        return content
        
    except Exception as e:
        logger.error(f"Error calling Ollama API: {e}", exc_info=True)
        
        # Provide more specific error messages for common issues
        error_msg = str(e)
        if "connection refused" in error_msg.lower():
            return (
                "ERROR: Connection to Ollama server refused. Make sure Ollama is running locally.\n"
                "Run 'ollama serve' in a separate terminal or check if the service is running."
            )
        elif "not found" in error_msg.lower() and model in error_msg:
            return (
                f"ERROR: Model '{model}' not found in Ollama.\n"
                f"Try installing it with: ollama pull {model}"
            )
        else:
            return f"ERROR: Failed to call Ollama API: {error_msg}" 