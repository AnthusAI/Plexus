"""
Plexus Configuration Loader

Loads configuration from YAML files with environment variable fallback.
Supports precedence order: current directory -> user home directory -> environment variables.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfigSource:
    """Represents a configuration source with its path and priority."""
    path: Path
    priority: int
    exists: bool = False


class ConfigLoader:
    """Loads and processes Plexus configuration from YAML files."""
    
    CONFIG_FILENAMES = ["config.yaml", "config.yml"]
    HOME_CONFIG_DIR = ".plexus"
    
    # Environment variable mapping from YAML keys to env var names
    ENV_VAR_MAPPING = {
        # Core Plexus
        'plexus.api_url': 'PLEXUS_API_URL',
        'plexus.api_key': 'PLEXUS_API_KEY',
        'plexus.app_url': 'PLEXUS_APP_URL',
        'plexus.account_key': 'PLEXUS_ACCOUNT_KEY',
        'plexus.default_account_id': 'PLEXUS_DEFAULT_ACCOUNT_ID',
        'plexus.enable_batching': 'PLEXUS_ENABLE_BATCHING',
        'plexus.langgraph_checkpointer_postgres_uri': 'PLEXUS_LANGGRAPH_CHECKPOINTER_POSTGRES_URI',
        
        # Working directory (special case)
        'plexus.working_directory': '_PLEXUS_WORKING_DIRECTORY',
        
        # Environment
        'environment': 'environment',
        'debug': 'DEBUG',
        
        # AWS Core
        'aws.access_key_id': 'AWS_ACCESS_KEY_ID',
        'aws.secret_access_key': 'AWS_SECRET_ACCESS_KEY',
        'aws.region_name': 'AWS_REGION_NAME',
        
        # AWS Storage Buckets
        'aws.storage.report_block_details_bucket': 'AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME',
        'aws.storage.datasets_bucket': 'AMPLIFY_STORAGE_DATASETS_BUCKET_NAME',
        'aws.storage.task_attachments_bucket': 'AMPLIFY_STORAGE_TASKATTACHMENTS_BUCKET_NAME',
        'aws.storage.score_result_attachments_bucket': 'AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME',
        
        # Data Lake
        'aws.data_lake.database_name': 'PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME',
        'aws.data_lake.athena_results_bucket': 'PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME',
        'aws.data_lake.bucket_name': 'PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME',
        
        # Celery
        'celery.queue_name': 'CELERY_QUEUE_NAME',
        'celery.result_backend_template': 'CELERY_RESULT_BACKEND_TEMPLATE',
        'celery.broker_url': 'CELERY_BROKER_URL',
        'celery.result_backend': 'CELERY_RESULT_BACKEND',
        'celery.aws_access_key_id': 'CELERY_AWS_ACCESS_KEY_ID',
        'celery.aws_secret_access_key': 'CELERY_AWS_SECRET_ACCESS_KEY',
        'celery.aws_region_name': 'CELERY_AWS_REGION_NAME',
        
        # AI/ML APIs
        'openai.api_key': 'OPENAI_API_KEY',
        'anthropic.api_key': 'ANTHROPIC_API_KEY',
        
        # Azure
        'azure.api_key': 'AZURE_API_KEY',
        'azure.api_base': 'AZURE_API_BASE',
        'azure.api_version': 'AZURE_API_VERSION',
        'azure.tenant_id': 'AZURE_TENANT_ID',
        'azure.client_id': 'AZURE_CLIENT_ID',
        'azure.client_secret': 'AZURE_CLIENT_SECRET',
        'azure.openai_api_key': 'AZURE_OPENAI_API_KEY',
        'azure.openai_endpoint': 'AZURE_OPENAI_ENDPOINT',
        'azure.openai_deployment': 'AZURE_OPENAI_DEPLOYMENT',
        
        # LangChain/LangSmith
        'langchain.api_key': 'LANGCHAIN_API_KEY',
        'langchain.endpoint': 'LANGCHAIN_ENDPOINT',
        'langchain.project': 'LANGCHAIN_PROJECT',
        'langchain.debug': 'LANGCHAIN_DEBUG',
        'langchain.tracing_v2': 'LANGCHAIN_TRACING_V2',
        'langgraph.timeout': 'LANGGRAPH_TIMEOUT',
        
        # MLflow
        'mlflow.tracking_uri': 'MLFLOW_TRACKING_URI',
        'mlflow.experiment_name': 'MLFLOW_EXPERIMENT_NAME',
        
        
        # Performance/Threading
        'performance.omp_num_threads': 'OMP_NUM_THREADS',
        'performance.openblas_num_threads': 'OPENBLAS_NUM_THREADS',
        'performance.mkl_num_threads': 'MKL_NUM_THREADS',
        'performance.numexpr_num_threads': 'NUMEXPR_NUM_THREADS',
        
        # TensorFlow
        'tensorflow.force_gpu_allow_growth': 'TF_FORCE_GPU_ALLOW_GROWTH',
        'tensorflow.gpu_allocator': 'TF_GPU_ALLOCATOR',
        
        # Third-party
        'airtable.api_key': 'AIRTABLE_API_KEY',
        
        # Dashboard
        'dashboard.minimal_branding': 'NEXT_PUBLIC_MINIMAL_BRANDING',
    }
    
    def __init__(self):
        self.config_sources = self._discover_config_sources()
        self.loaded_config = {}
        self.env_vars_set = 0
        
    def _discover_config_sources(self) -> List[ConfigSource]:
        """Discover available configuration sources in precedence order."""
        sources = []
        
        # 1. Current working directory .plexus subdirectory (highest priority)
        # Order: config.yaml, config.yml
        for i, filename in enumerate(self.CONFIG_FILENAMES):
            cwd_plexus_config = Path.cwd() / self.HOME_CONFIG_DIR / filename
            sources.append(ConfigSource(cwd_plexus_config, i + 1, cwd_plexus_config.exists()))
        
        # 2. User home directory .plexus (lowest priority)
        # Order: config.yaml, config.yml
        for i, filename in enumerate(self.CONFIG_FILENAMES):
            home_config = Path.home() / self.HOME_CONFIG_DIR / filename
            sources.append(ConfigSource(home_config, i + 3, home_config.exists()))
        
        return sources
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = key_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def _set_nested_value(self, data: Dict[str, Any], key_path: str, value: Any) -> None:
        """Set value in nested dictionary using dot notation."""
        keys = key_path.split('.')
        current = data
        
        # Navigate to the parent of the final key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[keys[-1]] = value
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML configuration from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                logger.debug(f"Loaded config from {file_path}")
                return config
        except Exception as e:
            logger.warning(f"Failed to load config from {file_path}: {e}")
            return {}
    
    def _merge_configs(self, base_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries recursively."""
        result = base_config.copy()
        
        for key, value in new_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _change_working_directory(self, working_dir: str) -> bool:
        """Change the current working directory."""
        try:
            expanded_path = os.path.expanduser(working_dir)
            if os.path.isdir(expanded_path):
                os.chdir(expanded_path)
                logger.debug(f"Changed working directory to: {expanded_path}")
                return True
            else:
                logger.warning(f"Working directory does not exist: {expanded_path}")
                return False
        except Exception as e:
            logger.warning(f"Failed to change working directory to {working_dir}: {e}")
            return False
    
    def _set_environment_variables(self, config: Dict[str, Any]) -> int:
        """Set environment variables from configuration.
        
        Only sets environment variables that are not already set, preserving
        the precedence order: env vars > YAML config > defaults.
        """
        env_vars_set = 0
        
        for yaml_key, env_var in self.ENV_VAR_MAPPING.items():
            value = self._get_nested_value(config, yaml_key)
            
            if value is not None:
                # Handle special case for working directory
                if env_var == '_PLEXUS_WORKING_DIRECTORY':
                    if self._change_working_directory(str(value)):
                        env_vars_set += 1
                else:
                    # Only set environment variable if it's not already set
                    # This preserves precedence: env vars > YAML config
                    if env_var not in os.environ:
                        os.environ[env_var] = str(value)
                        env_vars_set += 1
                        logger.debug(f"Set {env_var} from config")
                    else:
                        logger.debug(f"Skipped {env_var} - already set in environment")
        
        return env_vars_set
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from all sources and set environment variables."""
        merged_config = {}
        config_files_loaded = []
        
        # Load configs in priority order (lowest priority first, highest priority last to override)
        for source in sorted(self.config_sources, key=lambda x: x.priority, reverse=True):
            if source.exists:
                file_config = self._load_yaml_file(source.path)
                merged_config = self._merge_configs(merged_config, file_config)
                config_files_loaded.append(str(source.path))
        
        self.loaded_config = merged_config
        self.env_vars_set = self._set_environment_variables(merged_config)
        
        # Log configuration loading summary
        if config_files_loaded:
            logger.info(
                f"Loaded Plexus configuration from {len(config_files_loaded)} file(s): "
                f"{', '.join(config_files_loaded)} - Set {self.env_vars_set} environment variables"
            )
        else:
            logger.info("No Plexus configuration files found - using environment variables only")
        
        return self.loaded_config
    
    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """Get a configuration value by key path."""
        return self._get_nested_value(self.loaded_config, key_path) or default
    
    def get_available_sources(self) -> List[str]:
        """Get list of available configuration sources."""
        return [str(source.path) for source in self.config_sources if source.exists]


def load_config() -> Dict[str, Any]:
    """Convenience function to load Plexus configuration."""
    loader = ConfigLoader()
    return loader.load_config()