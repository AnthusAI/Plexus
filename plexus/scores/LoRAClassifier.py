"""
LoRAClassifier - Base class for LoRA adapter-based classifiers.

This base class provides common functionality for classifiers that use
Low-Rank Adaptation (LoRA) fine-tuning on large language models.
"""

from abc import abstractmethod
from typing import Dict, Any, Optional
from plexus.scores.Score import Score
from plexus.CustomLogging import logging


class LoRAClassifier(Score):
    """
    Base class for LoRA adapter-based classifiers.

    LoRAClassifier is designed for classification tasks that use large language
    models fine-tuned with LoRA (Low-Rank Adaptation) adapters. This approach
    allows efficient fine-tuning of large models by only training a small number
    of additional parameters (the adapter).

    Subclasses must implement:
    - get_deployment_config(): Returns infrastructure configuration for the model
    - predict(): Classification logic using the LoRA-tuned model

    Key features:
    - Convention over configuration: Infrastructure details defined at class level
    - Shared base model support: Multiple scores can share the same base model
    - Scale-to-zero capable: Real-time endpoints with managed instance scaling
    - SageMaker Inference Components: Base component + adapter component architecture

    Example usage:
        class Llama318BInstructClassifier(LoRAClassifier):
            @classmethod
            def get_deployment_config(cls) -> Dict[str, Any]:
                return {
                    'deployment_type': 'realtime',
                    'base_model_hf_id': 'meta-llama/Llama-3.1-8B-Instruct',
                    'instance_type': 'ml.g6e.xlarge',
                    # ... additional configuration
                }

            def predict(self, context, model_input: Score.Input) -> Score.Result:
                # LoRA-specific prediction logic
                pass

    Score YAML configuration:
        name: My Classifier
        class: Llama318BInstructClassifier
        provisioning:
          adapter_s3_uri: s3://bucket/adapters/my-adapter.tar.gz
    """

    @classmethod
    @abstractmethod
    def get_deployment_config(cls) -> Dict[str, Any]:
        """
        Return deployment configuration for this model.

        This method defines all infrastructure settings needed to deploy the model
        to SageMaker, including instance types, container images, and environment
        variables. By defining these at the class level, we follow convention over
        configuration - users don't need to specify infrastructure details in YAML.

        Returns:
            Dict[str, Any]: Deployment configuration dictionary with the following required keys:

            Required keys:
            - deployment_type (str): Must be 'realtime' for LoRA classifiers
            - base_model_hf_id (str): HuggingFace model ID (e.g., 'meta-llama/Llama-3.1-8B-Instruct')
            - instance_type (str): SageMaker instance type (e.g., 'ml.g6e.xlarge')
            - min_instances (int): Minimum instances (usually 0 for scale-to-zero)
            - max_instances (int): Maximum instances (usually 1)
            - scale_in_cooldown (int): Seconds before scaling in (default 300)
            - scale_out_cooldown (int): Seconds before scaling out (default 60)
            - target_invocations_per_instance (float): Target for auto-scaling (default 1.0)
            - container_image (str): DJL inference container image URI
            - environment (Dict[str, str]): Environment variables for vLLM/LoRA configuration

            Environment variables should typically include:
            - OPTION_ROLLING_BATCH: 'vllm' (enables vLLM for efficient inference)
            - OPTION_ENABLE_LORA: 'true' (enables LoRA adapter support)
            - OPTION_MAX_LORAS: '10' (max number of adapters on shared base)
            - OPTION_MAX_LORA_RANK: '64' (max rank for LoRA matrices)
            - OPTION_MAX_MODEL_LEN: '4096' (max sequence length)
            - OPTION_GPU_MEMORY_UTILIZATION: '0.8' (GPU memory utilization)

        Example:
            @classmethod
            def get_deployment_config(cls) -> Dict[str, Any]:
                return {
                    'deployment_type': 'realtime',
                    'base_model_hf_id': 'meta-llama/Llama-3.1-8B-Instruct',
                    'instance_type': 'ml.g6e.xlarge',
                    'min_instances': 0,
                    'max_instances': 1,
                    'scale_in_cooldown': 300,
                    'scale_out_cooldown': 60,
                    'target_invocations_per_instance': 1.0,
                    'container_image': '763104351884.dkr.ecr.us-east-1.amazonaws.com/djl-inference:0.31.0-lmi13.0.0-cu124',
                    'environment': {
                        'OPTION_ROLLING_BATCH': 'vllm',
                        'OPTION_ENABLE_LORA': 'true',
                        'OPTION_MAX_LORAS': '10',
                        'OPTION_MAX_LORA_RANK': '64',
                        'OPTION_MAX_MODEL_LEN': '4096',
                        'OPTION_GPU_MEMORY_UTILIZATION': '0.8'
                    }
                }

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError(
            f"{cls.__name__} must implement get_deployment_config() class method. "
            "This method should return a dictionary with deployment configuration "
            "including base_model_hf_id, instance_type, container_image, and environment variables."
        )

    @classmethod
    def supports_provisioning(cls) -> bool:
        """
        Check if this classifier supports SageMaker endpoint provisioning.

        LoRA classifiers support provisioning via SageMaker real-time endpoints
        with inference components (base component + adapter component).

        Returns:
            bool: Always True for LoRA classifiers
        """
        return True

    @classmethod
    def validate_deployment_config(cls) -> None:
        """
        Validate that the deployment configuration is complete and correct.

        This method checks that get_deployment_config() returns all required
        fields with appropriate types and values. Called during provisioning
        to catch configuration errors early.

        Raises:
            ValueError: If configuration is missing required fields or has invalid values
        """
        try:
            config = cls.get_deployment_config()
        except NotImplementedError:
            raise ValueError(f"{cls.__name__} must implement get_deployment_config()")

        # Required fields
        required_fields = [
            'deployment_type',
            'base_model_hf_id',
            'instance_type',
            'min_instances',
            'max_instances',
            'scale_in_cooldown',
            'scale_out_cooldown',
            'target_invocations_per_instance',
            'container_image',
            'environment'
        ]

        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise ValueError(
                f"{cls.__name__}.get_deployment_config() is missing required fields: {missing_fields}"
            )

        # Validate deployment_type
        if config['deployment_type'] != 'realtime':
            raise ValueError(
                f"{cls.__name__}: LoRA classifiers must use deployment_type='realtime', "
                f"got '{config['deployment_type']}'"
            )

        # Validate instance_type
        if not config['instance_type'].startswith('ml.'):
            raise ValueError(
                f"{cls.__name__}: instance_type must be a valid SageMaker instance type "
                f"(e.g., 'ml.g6e.xlarge'), got '{config['instance_type']}'"
            )

        # Validate scaling parameters
        if not isinstance(config['min_instances'], int) or config['min_instances'] < 0:
            raise ValueError(
                f"{cls.__name__}: min_instances must be a non-negative integer, "
                f"got {config['min_instances']}"
            )

        if not isinstance(config['max_instances'], int) or config['max_instances'] < 1:
            raise ValueError(
                f"{cls.__name__}: max_instances must be a positive integer, "
                f"got {config['max_instances']}"
            )

        if config['min_instances'] > config['max_instances']:
            raise ValueError(
                f"{cls.__name__}: min_instances ({config['min_instances']}) cannot be "
                f"greater than max_instances ({config['max_instances']})"
            )

        # Validate environment is a dictionary
        if not isinstance(config['environment'], dict):
            raise ValueError(
                f"{cls.__name__}: environment must be a dictionary, got {type(config['environment'])}"
            )

        logging.debug(f"{cls.__name__}: Deployment configuration validated successfully")

    def __init__(self, *args, **kwargs):
        """
        Initialize the LoRA classifier.

        Validates deployment configuration on initialization to catch
        configuration errors early.
        """
        super().__init__(*args, **kwargs)

        # Validate deployment config on initialization
        try:
            self.__class__.validate_deployment_config()
        except ValueError as e:
            logging.warning(f"Deployment configuration validation failed: {e}")

    @abstractmethod
    def predict(self, context, model_input: Score.Input) -> Score.Result:
        """
        Make a prediction using the LoRA-tuned model.

        Subclasses must implement this method with their specific prediction logic.
        The implementation should handle:
        - Preparing input for the model (formatting, tokenization, etc.)
        - Making the prediction (via SageMaker endpoint or local inference)
        - Parsing and formatting the result

        Args:
            context: Execution context (may contain shared state, configuration, etc.)
            model_input (Score.Input): Input data with text and optional metadata

        Returns:
            Score.Result: Prediction result with value, confidence, explanation, etc.

        Example:
            def predict(self, context, model_input: Score.Input) -> Score.Result:
                text = model_input.text

                # Prepare input for model
                prompt = self._format_prompt(text)

                # Make prediction via SageMaker endpoint
                response = self._invoke_endpoint(prompt)

                # Parse result
                value = self._parse_response(response)

                return Score.Result(
                    parameters=self.parameters,
                    value=value,
                    confidence=response.get('confidence'),
                    explanation=response.get('explanation')
                )
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement predict()")
