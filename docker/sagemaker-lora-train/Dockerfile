FROM 763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.2.0-gpu-py310-cu121-ubuntu20.04-sagemaker

# Install compatible LoRA stack
RUN pip install --no-cache-dir \
    "torch==2.2.0" \
    "transformers==4.46.3" \
    "accelerate==0.34.2" \
    "peft==0.12.0" \
    "datasets==2.19.1" \
    "tokenizers==0.20.1" \
    "bitsandbytes==0.43.1"

# The training script is provided via Script Mode (sagemaker_program)
