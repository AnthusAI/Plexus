"""
Configuration management for the Automated Prompt Optimization System.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal
import yaml
import logging
import logging.config
import os
from pathlib import Path


@dataclass
class OptimizationConfig:
    """Configuration for the optimization process."""
    max_iterations: int = 2
    target_accuracy: float = 0.95
    min_improvement: float = 0.01
    max_regression: float = 0.02


@dataclass
class AnalysisConfig:
    """Configuration for the analysis process."""
    samples_per_iteration: int = 5
    min_mismatch_confidence: float = 0.8
    max_prompt_length: int = 2000
    min_pattern_frequency: int = 2  # Minimum number of mismatches to consider a pattern significant


@dataclass
class ModelConfig:
    """Configuration for the LLM used in prompt optimization."""
    model_type: Literal["gpt-4o-mini-2024-07-18", "claude", "gpt-3.5-turbo"] = "gpt-4o-mini-2024-07-18"
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    organization: Optional[str] = None
    # LangChain specific settings
    cache_dir: str = ".langchain_cache"
    request_timeout: int = 60
    max_retries: int = 3
    streaming: bool = False


@dataclass
class APOSConfig:
    """Main configuration class for APOS."""
    optimization: OptimizationConfig
    analysis: AnalysisConfig
    model: ModelConfig
    persistence_path: str = "./optimization_history"
    log_level: str = "INFO"
    backup_frequency: int = 1

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'APOSConfig':
        """Create a config instance from a dictionary."""
        opt_config = OptimizationConfig(**config_dict.get('optimization', {}))
        analysis_config = AnalysisConfig(**config_dict.get('analysis', {}))
        model_config = ModelConfig(**config_dict.get('model', {}))
        
        return cls(
            optimization=opt_config,
            analysis=analysis_config,
            model=model_config,
            persistence_path=config_dict.get('persistence_path', "./optimization_history"),
            log_level=config_dict.get('log_level', "INFO"),
            backup_frequency=config_dict.get('backup_frequency', 1)
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'APOSConfig':
        """Load configuration from a YAML file."""
        with open(yaml_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        return cls.from_dict(config_dict)

    def setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Remove any existing CloudWatch handlers to prevent timeouts
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            if 'watchtower' in str(type(handler)).lower():
                logger.removeHandler(handler)
                logger.info("Removed CloudWatch handler for optimization process")
        
        # Ensure log directory exists
        os.makedirs(self.persistence_path, exist_ok=True)


def get_default_config() -> APOSConfig:
    """Get the default APOS configuration."""
    return APOSConfig(
        optimization=OptimizationConfig(),
        analysis=AnalysisConfig(),
        model=ModelConfig()
    )


def load_config(config_path: Optional[str] = None) -> APOSConfig:
    """
    Load APOS configuration from a file or return default config.
    
    Args:
        config_path: Path to the configuration file. If None, uses default config.
        
    Returns:
        APOSConfig instance
    """
    if not config_path:
        return get_default_config()
        
    config_path = Path(config_path)
    if not config_path.exists():
        logging.warning(f"Config file {config_path} not found. Using default configuration.")
        return get_default_config()
        
    try:
        return APOSConfig.from_yaml(str(config_path))
    except Exception as e:
        logging.error(f"Error loading config from {config_path}: {e}")
        logging.warning("Using default configuration.")
        return get_default_config() 