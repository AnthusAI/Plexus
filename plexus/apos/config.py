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
    max_consecutive_no_improvement: int = 3  # Maximum number of consecutive iterations without improvement before stopping
    max_mismatches_to_report: int = 100  # Maximum number of mismatches to analyze per iteration


@dataclass
class AnalysisConfig:
    """Configuration for the analysis process."""
    samples_per_iteration: int = 5
    max_prompt_length: int = 2000
    min_pattern_frequency: int = 2  # Minimum number of mismatches to consider a pattern significant


@dataclass
class ModelConfig:
    """Configuration for the LLM used in prompt optimization."""
    model_type: Literal["gpt-4o-mini-2024-07-18", "claude", "gpt-3.5-turbo"] = "gpt-4o-mini-2024-07-18"
    temperature: float = 0
    max_tokens: int = 2000
    top_p: float = 0.03
    # LangChain specific settings
    cache_dir: str = ".langchain_cache"
    max_retries: int = 3
    prompts: Dict[str, str] = None  # Dictionary containing system_template and human_template

    def __post_init__(self):
        """Initialize empty prompts dict if None."""
        if self.prompts is None:
            self.prompts = {}


@dataclass
class APOSConfig:
    """Main configuration class for APOS."""
    optimization: OptimizationConfig
    analysis: AnalysisConfig
    optimizer_model: ModelConfig  # For generating prompt improvements
    analyzer_model: ModelConfig  # For analyzing individual mismatches
    pattern_analyzer_model: ModelConfig  # For analyzing patterns across mismatches
    persistence_path: str = "./optimization_history"
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'APOSConfig':
        """Create a config instance from a dictionary."""
        opt_config = OptimizationConfig(**config_dict.get('optimization', {}))
        analysis_config = AnalysisConfig(**config_dict.get('analysis', {}))
        
        # Extract model configs, preserving the prompts
        optimizer_model_dict = config_dict.get('optimizer_model', {})
        analyzer_model_dict = config_dict.get('analyzer_model', {})
        pattern_analyzer_model_dict = config_dict.get('pattern_analyzer_model', {})
        
        optimizer_model_config = ModelConfig(**{k: v for k, v in optimizer_model_dict.items() if k != 'prompts'})
        analyzer_model_config = ModelConfig(**{k: v for k, v in analyzer_model_dict.items() if k != 'prompts'})
        pattern_analyzer_model_config = ModelConfig(**{k: v for k, v in pattern_analyzer_model_dict.items() if k != 'prompts'})
        
        # Set prompts separately
        optimizer_model_config.prompts = optimizer_model_dict.get('prompts', {})
        analyzer_model_config.prompts = analyzer_model_dict.get('prompts', {})
        pattern_analyzer_model_config.prompts = pattern_analyzer_model_dict.get('prompts', {})
        
        return cls(
            optimization=opt_config,
            analysis=analysis_config,
            optimizer_model=optimizer_model_config,
            analyzer_model=analyzer_model_config,
            pattern_analyzer_model=pattern_analyzer_model_config,
            persistence_path=config_dict.get('persistence_path', "./optimization_history"),
            log_level=config_dict.get('log_level', "INFO")
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
        optimizer_model=ModelConfig(),
        analyzer_model=ModelConfig(),
        pattern_analyzer_model=ModelConfig()
    )


def load_config(config_path: Optional[str] = None) -> APOSConfig:
    """
    Load APOS configuration from a file or return default config.
    
    Args:
        config_path: Path to the configuration file. If None, looks in default locations.
        
    Returns:
        APOSConfig instance
    """
    # If explicit path provided, try that first
    if config_path:
        config_path = Path(config_path)
        if config_path.exists():
            try:
                return APOSConfig.from_yaml(str(config_path))
            except Exception as e:
                logging.error(f"Error loading config from {config_path}: {e}")
    
    # Try default locations in order
    default_locations = [
        Path(__file__).parent / "apos_config.yaml",  # Same directory as this file
        Path("plexus/apos/apos_config.yaml"),  # Relative to current directory
    ]
    
    for path in default_locations:
        if path.exists():
            try:
                logging.info(f"Loading config from {path}")
                return APOSConfig.from_yaml(str(path))
            except Exception as e:
                logging.error(f"Error loading config from {path}: {e}")
                continue
    
    logging.warning("No valid configuration found. Using default configuration.")
    return get_default_config() 