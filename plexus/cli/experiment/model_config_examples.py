"""
Model Configuration Examples for SOP Agent

This file provides examples of how to configure the SOP agent for different
models (GPT-4, GPT-5, etc.) and demonstrates the flexibility of the new
model-agnostic configuration system.

Usage patterns:
1. Use predefined configurations for common scenarios
2. Create custom configurations from dictionaries/YAML
3. Set environment variables for runtime configuration
4. Mix and match parameters for different use cases
"""

import os
from typing import Dict, Any
from .model_config import ModelConfig, ModelConfigs, create_configured_llm


# =============================================================================
# GPT-4 CONFIGURATIONS
# =============================================================================

def get_gpt4_experimentation_config() -> Dict[str, Any]:
    """Configuration for GPT-4 with standard experimentation parameters."""
    return {
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 4000,
        "stream": False
    }

def get_gpt4_precise_analysis_config() -> Dict[str, Any]:
    """Configuration for GPT-4 with precise analysis parameters."""
    return {
        "model": "gpt-4o",
        "temperature": 0.1,
        "max_tokens": 6000,
        "stream": False
    }


# =============================================================================
# GPT-5 CONFIGURATIONS
# =============================================================================

def get_gpt5_default_config() -> Dict[str, Any]:
    """Configuration for GPT-5 with new reasoning parameters."""
    return {
        "model": "gpt-5",
        "reasoning_effort": "medium",
        "verbosity": "medium",
        "max_tokens": 4000,
        "stream": False
    }

def get_gpt5_high_reasoning_config() -> Dict[str, Any]:
    """Configuration for GPT-5 with high reasoning effort."""
    return {
        "model": "gpt-5",
        "reasoning_effort": "high",
        "verbosity": "high",
        "max_tokens": 6000,
        "stream": False
    }

def get_gpt5_fast_config() -> Dict[str, Any]:
    """Configuration for GPT-5 optimized for speed."""
    return {
        "model": "gpt-5-mini",
        "reasoning_effort": "low",
        "verbosity": "low",
        "max_tokens": 2000,
        "stream": False
    }


# =============================================================================
# O3 CONFIGURATIONS (Future)
# =============================================================================

def get_o3_default_config() -> Dict[str, Any]:
    """Configuration for O3 model (example of future model support)."""
    return {
        "model": "o3",
        # O3 might have different parameters - this demonstrates flexibility
        "inference_mode": "balanced",
        "context_length": "extended",
        "max_tokens": 8000,
        "stream": False
    }


# =============================================================================
# CONFIGURATION EXAMPLES BY USE CASE
# =============================================================================

def get_manager_agent_config(base_model: str = "gpt-4o") -> Dict[str, Any]:
    """Configuration optimized for SOP manager agent (precise guidance)."""
    if base_model.startswith("gpt-5"):
        return {
            "model": base_model,
            "reasoning_effort": "high",
            "verbosity": "low",  # Concise guidance
            "max_tokens": 2000
        }
    else:
        return {
            "model": base_model,
            "temperature": 0.1,  # Precise, consistent guidance
            "max_tokens": 2000
        }

def get_worker_agent_config(base_model: str = "gpt-4o") -> Dict[str, Any]:
    """Configuration optimized for worker agent (creative problem solving)."""
    if base_model.startswith("gpt-5"):
        return {
            "model": base_model,
            "reasoning_effort": "medium",
            "verbosity": "high",  # Detailed explanations
            "max_tokens": 4000
        }
    else:
        return {
            "model": base_model,
            "temperature": 0.7,  # Creative problem solving
            "max_tokens": 4000
        }

def get_summarization_config(base_model: str = "gpt-4o") -> Dict[str, Any]:
    """Configuration optimized for summarization tasks."""
    if base_model.startswith("gpt-5"):
        return {
            "model": base_model,
            "reasoning_effort": "low",  # Fast summarization
            "verbosity": "medium",
            "max_tokens": 2000
        }
    else:
        return {
            "model": base_model,
            "temperature": 0.3,  # Balanced summarization
            "max_tokens": 2000
        }


# =============================================================================
# YAML CONFIGURATION EXAMPLES
# =============================================================================

EXAMPLE_YAML_CONFIGS = {
    "gpt4_standard": """
model: gpt-4o
temperature: 0.7
max_tokens: 4000
stream: false
""",
    
    "gpt5_reasoning": """
model: gpt-5
reasoning_effort: high
verbosity: medium
max_tokens: 6000
stream: false
""",
    
    "mixed_parameters": """
model: gpt-5
reasoning_effort: medium
verbosity: high
max_tokens: 4000
# Custom parameters go to model_kwargs
custom_parameter: some_value
experimental_feature: enabled
""",
    
    "environment_based": """
# This config uses environment variables for runtime flexibility
model: ${MODEL_NAME:-gpt-4o}
temperature: ${MODEL_TEMPERATURE:-0.7}
max_tokens: ${MODEL_MAX_TOKENS:-4000}
"""
}


# =============================================================================
# ENVIRONMENT VARIABLE PATTERNS
# =============================================================================

def setup_gpt4_environment():
    """Set environment variables for GPT-4 configuration."""
    os.environ.update({
        "MODEL_NAME": "gpt-4o",
        "MODEL_TEMPERATURE": "0.7",
        "MODEL_MAX_TOKENS": "4000"
    })

def setup_gpt5_environment():
    """Set environment variables for GPT-5 configuration."""
    os.environ.update({
        "MODEL_NAME": "gpt-5",
        "MODEL_TEMPERATURE": "0.7",
        "MODEL_MAX_TOKENS": "4000"
    })

def setup_custom_environment(model_name: str, **params):
    """Set up environment variables for any model with custom parameters."""
    os.environ["MODEL_NAME"] = model_name
    
    for param_name, param_value in params.items():
        env_var = f"MODEL_{param_name.upper()}"
        os.environ[env_var] = str(param_value)


# =============================================================================
# USAGE DEMONSTRATIONS
# =============================================================================

def demonstrate_usage():
    """Demonstrate different ways to use the model configuration system."""
    
    print("=== Model Configuration Examples ===\n")
    
    # 1. Using predefined configurations
    print("1. Predefined configurations:")
    gpt4_llm = ModelConfigs.gpt_4o_default().create_langchain_llm()
    gpt5_llm = ModelConfigs.gpt_5_default().create_langchain_llm()
    print(f"   GPT-4: {gpt4_llm}")
    print(f"   GPT-5: {gpt5_llm}")
    
    # 2. Using configuration dictionaries
    print("\n2. Configuration from dictionary:")
    config_dict = get_gpt5_high_reasoning_config()
    custom_llm = ModelConfig.from_dict(config_dict).create_langchain_llm()
    print(f"   Custom: {custom_llm}")
    
    # 3. Using convenience function
    print("\n3. Convenience function with overrides:")
    override_llm = create_configured_llm(
        "gpt-5",
        model_kwargs={"reasoning_effort": "high", "verbosity": "low"}
    )
    print(f"   Override: {override_llm}")
    
    # 4. Environment-based configuration
    print("\n4. Environment-based configuration:")
    setup_gpt5_environment()
    env_llm = ModelConfigs.from_environment().create_langchain_llm()
    print(f"   Environment: {env_llm}")


# =============================================================================
# SOP AGENT INTEGRATION EXAMPLES
# =============================================================================

async def run_experiment_with_gpt4():
    """Example: Run experiment with GPT-4 configuration."""
    from .experiment_sop_agent import ExperimentProcedureDefinition
    from .sop_agent_base import StandardOperatingProcedureAgent
    
    # Configure for GPT-4
    model_config = get_gpt4_experimentation_config()
    
    procedure_definition = ExperimentProcedureDefinition()
    
    # Mock MCP server (in real usage, use actual MCP server)
    mock_mcp_server = None
    
    agent = StandardOperatingProcedureAgent(
        procedure_id="gpt4_experiment_001",
        procedure_definition=procedure_definition,
        mcp_server=mock_mcp_server,
        model_config=model_config
    )
    
    print(f"Created SOP agent with GPT-4 configuration: {model_config}")
    # In real usage: result = await agent.execute_procedure()

async def run_experiment_with_gpt5():
    """Example: Run experiment with GPT-5 configuration."""
    from .experiment_sop_agent import ExperimentProcedureDefinition
    from .sop_agent_base import StandardOperatingProcedureAgent
    
    # Configure for GPT-5 with high reasoning
    model_config = get_gpt5_high_reasoning_config()
    
    procedure_definition = ExperimentProcedureDefinition()
    
    # Mock MCP server (in real usage, use actual MCP server)
    mock_mcp_server = None
    
    agent = StandardOperatingProcedureAgent(
        procedure_id="gpt5_experiment_001",
        procedure_definition=procedure_definition,
        mcp_server=mock_mcp_server,
        model_config=model_config
    )
    
    print(f"Created SOP agent with GPT-5 configuration: {model_config}")
    # In real usage: result = await agent.execute_procedure()

def switch_models_dynamically():
    """Example: Switch between models dynamically based on task complexity."""
    
    def get_model_for_task(task_complexity: str) -> Dict[str, Any]:
        """Choose model configuration based on task complexity."""
        if task_complexity == "simple":
            return get_gpt5_fast_config()  # Use fast GPT-5 mini
        elif task_complexity == "complex":
            return get_gpt5_high_reasoning_config()  # Use high reasoning GPT-5
        else:
            return get_gpt4_experimentation_config()  # Default to GPT-4
    
    # Example task routing
    tasks = [
        ("simple", "Quick data logging"),
        ("complex", "Multi-step reasoning analysis"),
        ("standard", "Regular experimentation")
    ]
    
    for complexity, description in tasks:
        config = get_model_for_task(complexity)
        print(f"Task: {description}")
        print(f"  Complexity: {complexity}")
        print(f"  Model Config: {config}")
        print()


# =============================================================================
# MIGRATION HELPERS
# =============================================================================

def migrate_from_hardcoded_gpt4():
    """Helper to migrate from hardcoded GPT-4 usage to configurable system."""
    
    # Old way (hardcoded in SOP agent):
    # sop_guidance_llm = ChatOpenAI(
    #     model="gpt-4o",
    #     temperature=0.1,
    #     openai_api_key=self.openai_api_key,
    #     stream=False
    # )
    
    # New way (configurable):
    config = {
        "model": "gpt-4o",
        "temperature": 0.1,
        "stream": False
    }
    
    # The SOP agent now handles this automatically when model_config is provided
    print("Migration example:")
    print(f"  Old: Hardcoded ChatOpenAI(...)")
    print(f"  New: model_config = {config}")
    print(f"       SOP agent handles LLM creation automatically")

def validate_model_compatibility(model_name: str, parameters: Dict[str, Any]) -> bool:
    """
    Example function to validate model/parameter compatibility.
    
    Note: The actual implementation leaves this validation to the OpenAI API
    to avoid hardcoding model-specific logic, but this shows how you could
    add validation if needed.
    """
    
    # This is intentionally simple - let OpenAI API handle validation
    try:
        config = ModelConfig.from_dict({"model": model_name, **parameters})
        llm = config.create_langchain_llm()
        return True
    except Exception as e:
        print(f"Model compatibility issue: {e}")
        return False


if __name__ == "__main__":
    demonstrate_usage()
    print("\n" + "="*50 + "\n")
    switch_models_dynamically()
