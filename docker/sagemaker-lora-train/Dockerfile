FROM 763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.2.0-gpu-py310-cu121-ubuntu20.04-sagemaker

# Install compatible LoRA stack
RUN pip install --no-cache-dir \
    "torch>=2.1.0" \
    "transformers>=4.41.2" \
    "accelerate>=0.26.0" \
    "peft>=0.10.0" \
    datasets

# The training script is provided via Script Mode (sagemaker_program)
