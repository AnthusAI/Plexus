"""
Model Configuration System for SOP Agent

This module provides a model-agnostic configuration system that allows
different LLM models (GPT-4, GPT-5, O3, etc.) to be configured with
their specific parameters without hardcoding model-specific logic.

The configuration system:
1. Allows dynamic parameter passing through model_kwargs
2. Supports different parameter sets for different models
3. Maintains backward compatibility with existing GPT-4 configurations
4. Provides clean separation between model configuration and business logic
"""

import os
import logging
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """
    Model configuration that supports any LLM model with dynamic parameters.
    
    This approach lets configuration determine what parameters are valid
    rather than hardcoding model-specific parameter validation in code.
    """
    
    model: str = "gpt-5"  # Default to GPT-5
    temperature: Optional[float] = None  # GPT-5 only supports default temperature=1
    max_tokens: Optional[int] = None
    
    # GPT-5 specific parameters (currently not supported by API)
    reasoning_effort: Optional[str] = None  # Future: "low", "medium", "high" for GPT-5
    verbosity: Optional[str] = None  # Future: "low", "medium", "high" for GPT-5
    
    # Generic model_kwargs for any other parameters
    model_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # OpenAI API configuration
    openai_api_key: Optional[str] = None
    stream: bool = False
    
    def __post_init__(self):
        """Set default API key from environment if not provided."""
        if self.openai_api_key is None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
    
    def to_langchain_kwargs(self) -> Dict[str, Any]:
        """
        Convert this config to kwargs suitable for LangChain ChatOpenAI.
        
        This method builds the parameter dict dynamically, only including
        parameters that are actually set. This allows:
        - GPT-4 configs to include temperature
        - GPT-5 configs to include reasoning_effort and verbosity
        - Any model to include custom parameters via model_kwargs
        - Invalid parameters to cause errors at the OpenAI API level
        """
        kwargs = {
            "model": self.model,
            "openai_api_key": self.openai_api_key
        }
        
        # Only add stream if it's not the default value
        if self.stream is not False:
            kwargs["stream"] = self.stream
        
        # Build model_kwargs dynamically from set parameters
        combined_model_kwargs = {}
        
        # Add standard parameters only if they're set
        if self.temperature is not None:
            combined_model_kwargs["temperature"] = self.temperature
        elif self.model.startswith("gpt-5"):
            # gpt-5 requires temperature=1 (its only supported value)
            # If we don't pass it, LangChain/OpenAI SDK adds 0.7 as default
            combined_model_kwargs["temperature"] = 1
        
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens  # max_tokens is a direct ChatOpenAI parameter
        
        # Add GPT-5 specific parameters only if they're set
        if self.reasoning_effort is not None:
            combined_model_kwargs["reasoning_effort"] = self.reasoning_effort
            
        if self.verbosity is not None:
            combined_model_kwargs["verbosity"] = self.verbosity
        
        # Add any additional model_kwargs from configuration
        combined_model_kwargs.update(self.model_kwargs)
        
        # Only include model_kwargs if there are actually parameters to pass
        if combined_model_kwargs:
            kwargs["model_kwargs"] = combined_model_kwargs
        
        return kwargs
    
    def create_langchain_llm(self) -> ChatOpenAI:
        """
        Create a LangChain ChatOpenAI instance with this configuration.
        
        This method handles all the parameter passing complexity so that
        the calling code doesn't need to know about model differences.
        """
        kwargs = self.to_langchain_kwargs()
        
        logger.info(f"Creating LLM with model='{self.model}' and parameters: {list(kwargs.get('model_kwargs', {}).keys())}")
        logger.info(f"DEBUG: FULL kwargs being passed to ChatOpenAI: {kwargs}")
        
        try:
            return ChatOpenAI(**kwargs)
        except Exception as e:
            logger.error(f"Failed to create LLM with config {kwargs}: {e}")
            # Log specific parameter info for debugging
            if "model_kwargs" in kwargs:
                logger.error(f"Model-specific parameters that failed: {kwargs['model_kwargs']}")
            raise
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ModelConfig":
        """
        Create ModelConfig from a dictionary (e.g., loaded from YAML/JSON).
        
        This allows configuration to be externalized to config files.
        """
        # Extract known fields
        known_fields = {
            "model", "temperature", "max_tokens", "reasoning_effort", 
            "verbosity", "openai_api_key", "stream"
        }
        
        # Separate known fields from model_kwargs
        direct_params = {}
        model_kwargs = {}
        
        for key, value in config_dict.items():
            if key in known_fields:
                direct_params[key] = value
            else:
                # Any unknown parameters go into model_kwargs
                model_kwargs[key] = value
        
        if model_kwargs:
            direct_params["model_kwargs"] = model_kwargs
        
        return cls(**direct_params)


# Predefined configurations for common use cases
class ModelConfigs:
    """
    Predefined model configurations for common scenarios.
    
    These serve as examples and can be customized or extended.
    """
    
    @staticmethod
    def gpt_4o_default() -> ModelConfig:
        """Standard GPT-4o configuration."""
        return ModelConfig(
            model="gpt-4o",
            temperature=0.7,
            max_tokens=4000
        )
    
    @staticmethod
    def gpt_4o_precise() -> ModelConfig:
        """GPT-4o with low temperature for precise tasks."""
        return ModelConfig(
            model="gpt-4o",
            temperature=0.1,
            max_tokens=4000
        )
    
    @staticmethod
    def gpt_5_default() -> ModelConfig:
        """Standard GPT-5 configuration with supported parameters."""
        return ModelConfig(
            model="gpt-5",
            # No temperature - GPT-5 only supports default (1.0)
            max_tokens=4000
        )
    
    @staticmethod
    def gpt_5_high_reasoning() -> ModelConfig:
        """GPT-5 configured for complex reasoning tasks."""
        return ModelConfig(
            model="gpt-5",
            # No temperature - GPT-5 uses default reasoning behavior
            max_tokens=6000
        )
    
    @staticmethod
    def gpt_5_mini_fast() -> ModelConfig:
        """GPT-5 mini for fast responses."""
        return ModelConfig(
            model="gpt-5-mini",
            # No temperature - GPT-5 mini uses default behavior
            max_tokens=2000
        )
    
    @staticmethod
    def from_environment() -> ModelConfig:
        """
        Create configuration from environment variables.
        
        This allows runtime configuration without code changes:
        - MODEL_NAME=gpt-5
        - MODEL_TEMPERATURE=0.3
        - MODEL_REASONING_EFFORT=high
        - MODEL_VERBOSITY=medium
        - etc.
        """
        config_dict = {}
        
        # Map environment variables to config parameters
        env_mappings = {
            "MODEL_NAME": "model",
            "MODEL_TEMPERATURE": "temperature",
            "MODEL_MAX_TOKENS": "max_tokens",
            "MODEL_STREAM": "stream"
            # Note: MODEL_REASONING_EFFORT and MODEL_VERBOSITY removed as they're not supported by GPT-5 API yet
        }
        
        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                if config_key in ("temperature",):
                    config_dict[config_key] = float(value)
                elif config_key in ("max_tokens",):
                    config_dict[config_key] = int(value)
                elif config_key in ("stream",):
                    config_dict[config_key] = value.lower() in ("true", "1", "yes")
                else:
                    config_dict[config_key] = value
        
        # Also check for any other MODEL_* environment variables
        # and add them to model_kwargs
        model_kwargs = {}
        for env_var in os.environ:
            if env_var.startswith("MODEL_") and env_var not in env_mappings:
                # Convert MODEL_CUSTOM_PARAM to custom_param
                param_name = env_var[6:].lower()  # Remove "MODEL_" prefix
                model_kwargs[param_name] = os.getenv(env_var)
        
        if model_kwargs:
            config_dict["model_kwargs"] = model_kwargs
        
        return ModelConfig.from_dict(config_dict) if config_dict else ModelConfig()


def create_configured_llm(
    model_config: Optional[Union[ModelConfig, Dict[str, Any], str]] = None,
    **override_kwargs
) -> ChatOpenAI:
    """
    Convenience function to create a configured LLM.
    
    Args:
        model_config: Can be:
            - ModelConfig instance
            - Dict to create ModelConfig from
            - String model name (uses defaults)
            - None (uses environment or defaults)
        **override_kwargs: Override any parameters
    
    Returns:
        Configured ChatOpenAI instance
    """
    if model_config is None:
        # Try environment first, then fall back to default
        config = ModelConfigs.from_environment()
        if config.model == "gpt-4o":  # No environment config found
            # Default to gpt-5 which works out of the box
            config = ModelConfigs.gpt_5_default()
    elif isinstance(model_config, str):
        # Just a model name, use appropriate defaults
        if model_config.startswith("gpt-5"):
            config = ModelConfig(model=model_config, reasoning_effort="medium", verbosity="medium")
        else:
            config = ModelConfig(model=model_config, temperature=0.7)
    elif isinstance(model_config, dict):
        config = ModelConfig.from_dict(model_config)
    else:
        config = model_config
    
    # Apply any overrides
    if override_kwargs:
        # Create a copy of the config and apply overrides directly
        # to avoid double-processing of model_kwargs
        import copy
        config = copy.deepcopy(config)
        
        # Apply direct field overrides
        for key, value in override_kwargs.items():
            if key == "model_kwargs":
                # Merge with existing model_kwargs
                config.model_kwargs.update(value)
            elif hasattr(config, key):
                setattr(config, key, value)
            else:
                # Unknown parameter goes to model_kwargs
                config.model_kwargs[key] = value
    
    return config.create_langchain_llm()


# Example usage patterns for documentation:
if __name__ == "__main__":
    # Example 1: Use predefined configurations
    gpt4_llm = ModelConfigs.gpt_4o_default().create_langchain_llm()
    gpt5_llm = ModelConfigs.gpt_5_default().create_langchain_llm()
    
    # Example 2: Create from dictionary (e.g., loaded from YAML)
    config_dict = {
        "model": "gpt-5",
        "reasoning_effort": "high",
        "verbosity": "medium",
        "max_tokens": 6000,
        "custom_parameter": "some_value"  # Goes to model_kwargs
    }
    custom_llm = ModelConfig.from_dict(config_dict).create_langchain_llm()
    
    # Example 3: Environment-based configuration
    env_llm = ModelConfigs.from_environment().create_langchain_llm()
    
    # Example 4: Convenience function with overrides
    override_llm = create_configured_llm(
        "gpt-5",
        model_kwargs={"reasoning_effort": "high"}
    )
