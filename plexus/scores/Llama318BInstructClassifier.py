"""
Llama 3.1 8B Instruct Classifier - Concrete LoRA classifier for Llama 3.1 8B Instruct.

This classifier uses Meta's Llama 3.1 8B Instruct model with LoRA adapters for efficient
fine-tuning and inference. It defines all infrastructure settings needed for deployment
to SageMaker real-time endpoints with scale-to-zero capability.
"""

from typing import Dict, Any
from plexus.scores.LoRAClassifier import LoRAClassifier
from plexus.CustomLogging import logging


class Llama318BInstructClassifier(LoRAClassifier):
    """
    Llama 3.1 8B Instruct with LoRA adapter classifier.

    This classifier is optimized for Llama 3.1 8B Instruct, a 8-billion parameter
    instruction-tuned model from Meta. It uses:
    - ml.g6e.xlarge GPU instance (cost-effective for 8B models, ~$1.15/hour)
    - vLLM for efficient inference
    - Scale-to-zero capability (0-1 instances)
    - Support for up to 10 LoRA adapters on shared base model

    Score YAML configuration:
        name: My Sentiment Classifier
        class: Llama318BInstructClassifier
        provisioning:
          adapter_s3_uri: s3://my-bucket/adapters/sentiment-classifier.tar.gz

    The class defines all infrastructure settings, so the YAML only needs to specify
    the adapter location. Multiple scores using this class will share the same endpoint
    and GPU instance, reducing costs by 67%.

    Cost comparison:
    - 3 separate endpoints: $1.15/hour × 3 = $3.45/hour
    - 1 shared endpoint: $1.15/hour (67% savings)
    """

    @classmethod
    def get_deployment_config(cls) -> Dict[str, Any]:
        """
        Return deployment configuration for Llama 3.1 8B Instruct.

        This configuration is optimized for the 8B parameter model:
        - Uses ml.g6e.xlarge (24GB GPU, cheapest option for 8B models)
        - Configures vLLM for efficient inference
        - Enables LoRA support for multiple adapters
        - Sets scale-to-zero for cost efficiency

        Returns:
            Dict[str, Any]: Complete deployment configuration

        Example:
            config = Llama318BInstructClassifier.get_deployment_config()
            print(config['instance_type'])  # 'ml.g6e.xlarge'
            print(config['base_model_hf_id'])  # 'meta-llama/Llama-3.1-8B-Instruct'
        """
        return {
            # Deployment type (must be 'realtime' for LoRA classifiers)
            'deployment_type': 'realtime',

            # Base model from HuggingFace
            'base_model_hf_id': 'meta-llama/Llama-3.1-8B-Instruct',

            # Instance configuration
            # ml.g6e.xlarge: 1 NVIDIA L4 GPU (24GB), 4 vCPUs, 32 GiB RAM
            # Cost: ~$1.15/hour (cheapest GPU option suitable for 8B models)
            'instance_type': 'ml.g6e.xlarge',

            # Scaling configuration (scale-to-zero)
            'min_instances': 0,  # Scale down to 0 when idle (no cost)
            'max_instances': 1,  # Single instance (suitable for most use cases)

            # Auto-scaling timing
            'scale_in_cooldown': 300,  # Wait 5 minutes before scaling down to 0
            'scale_out_cooldown': 60,  # Wait 1 minute before scaling up from 0

            # Target invocations per instance for auto-scaling
            'target_invocations_per_instance': 1.0,

            # DJL LMI container optimized for large language models
            # Version: 0.31.0-lmi13.0.0-cu124 (includes vLLM, LoRA support, CUDA 12.4)
            'container_image': '763104351884.dkr.ecr.us-east-1.amazonaws.com/djl-inference:0.31.0-lmi13.0.0-cu124',

            # Environment variables for vLLM and LoRA configuration
            'environment': {
                # vLLM configuration
                'OPTION_ROLLING_BATCH': 'vllm',  # Use vLLM for continuous batching

                # LoRA configuration
                'OPTION_ENABLE_LORA': 'true',  # Enable LoRA adapter support
                'OPTION_MAX_LORAS': '10',  # Support up to 10 adapters on shared base
                'OPTION_MAX_LORA_RANK': '64',  # Max rank for LoRA weight matrices

                # Model configuration
                'OPTION_MAX_MODEL_LEN': '4096',  # Max sequence length (tokens)
                'OPTION_GPU_MEMORY_UTILIZATION': '0.8',  # Use 80% of GPU memory

                # Performance tuning
                # These are vLLM defaults but can be customized if needed:
                # 'OPTION_MAX_NUM_SEQS': '256',  # Max sequences in batch
                # 'OPTION_DTYPE': 'auto',  # Data type (auto, float16, bfloat16)
            }
        }

    # predict() is inherited from LoRAClassifier base class
    # Subclasses can override to customize prompt formatting or response parsing


# Validation: Test that the deployment config is complete
if __name__ == "__main__":
    # Test deployment config
    config = Llama318BInstructClassifier.get_deployment_config()
    print("Deployment configuration for Llama318BInstructClassifier:")
    print(f"  Base model: {config['base_model_hf_id']}")
    print(f"  Instance type: {config['instance_type']}")
    print(f"  Scaling: {config['min_instances']}-{config['max_instances']} instances")
    print(f"  Container: {config['container_image']}")
    print(f"  Environment variables: {len(config['environment'])} variables")

    # Test validation
    try:
        Llama318BInstructClassifier.validate_deployment_config()
        print("\n✅ Deployment configuration is valid")
    except ValueError as e:
        print(f"\n❌ Validation failed: {e}")
