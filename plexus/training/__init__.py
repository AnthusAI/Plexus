"""
Plexus Training Infrastructure

This module provides a unified training framework supporting multiple training workflows:
- ML model training (local and SageMaker)
- LLM fine-tuning data generation
- Future training methods through extensible Trainer abstraction
"""

from plexus.training.trainer import Trainer, TrainingResult
from plexus.training.ml_trainer_local import MLTrainerLocal
from plexus.training.llm_finetune_trainer import LLMFineTuneTrainer
from plexus.training.lora_finetune_trainer import LoraFineTuneTrainer
from plexus.training.lora_trainer_sagemaker import LoraFineTuneTrainerSageMaker
from plexus.training.training_dispatcher import TrainingDispatcher
from plexus.training import utils

__all__ = [
    'Trainer',
    'TrainingResult',
    'MLTrainerLocal',
    'LLMFineTuneTrainer',
    'TrainingDispatcher',
    'utils'
]
