"""
LoRA fine-tuning trainer for adapter-based real-time inference.

This trainer generates chat-style training data (via LLMFineTuneTrainer),
fine-tunes a base LLM with LoRA, packages adapter artifacts, and uploads
an adapter tarball to the convention-based S3 location.
"""

import os
import logging
from typing import Dict, Any, Optional

from plexus.training.trainer import Trainer
from plexus.training.llm_finetune_trainer import LLMFineTuneTrainer
from plexus.training.utils import (
    get_output_dir,
    get_adapter_s3_uri,
)
from plexus.training.lora_finetune_core import train_lora_adapter

logger = logging.getLogger(__name__)


class LoraFineTuneTrainer(Trainer):
    """
    Trainer for LoRA fine-tuning of LLMs used by LoRAClassifier scores.

    Workflow:
      1) Generate chat-style JSONL training/validation data
      2) Fine-tune base model with LoRA
      3) Package adapter artifacts
      4) Upload to convention-based S3 URI
    """

    def __init__(self, scorecard_class, scorecard_name: str, score_config: dict,
                 fresh: bool = False, use_yaml: bool = False, **kwargs):
        super().__init__(scorecard_class, scorecard_name, score_config, fresh, use_yaml, **kwargs)
        self.training_files: Dict[str, str] = {}
        self.adapter_output_dir: Optional[str] = None
        self._training_metrics: Dict[str, Any] = {}

    def get_training_type(self) -> str:
        return "lora"

    def get_platform(self) -> Optional[str]:
        return "local"

    def validate(self):
        try:
            import torch  # noqa: F401
        except Exception as e:
            raise RuntimeError("torch is required for LoRA training") from e

        try:
            import peft  # noqa: F401
        except Exception as e:
            raise RuntimeError("peft is required for LoRA training") from e

        # Ensure the score class is a LoRAClassifier (or subclass)
        score_class = self.scorecard_class.score_registry.get(self.score_config.get('name'))
        if score_class is None:
            raise ValueError(f"Score class not found for {self.score_config.get('name')}")

        from plexus.scores.LoRAClassifier import LoRAClassifier
        if not issubclass(score_class, LoRAClassifier):
            raise ValueError(
                f"Score '{self.score_config.get('name')}' uses class '{score_class.__name__}' which is not a LoRAClassifier."
            )

    def prepare_data(self):
        """
        Generate JSONL training/validation data using existing LLM fine-tune workflow.
        """
        logger.info("Generating training data via LLMFineTuneTrainer...")
        data_generator = LLMFineTuneTrainer(
            scorecard_class=self.scorecard_class,
            scorecard_name=self.scorecard_name,
            score_config=self.score_config,
            fresh=self.fresh,
            use_yaml=self.use_yaml,
            **self.extra_params,
        )

        result = data_generator.execute()
        if not result.success:
            raise RuntimeError(f"Training data generation failed: {result.error}")

        self.training_files = result.artifacts or {}
        if not self.training_files.get('training_file'):
            raise RuntimeError("Training data generation did not produce training_file")

    def train(self):
        """
        Run LoRA fine-tuning using generated chat-style JSONL data.
        """
        score_class = self.scorecard_class.score_registry.get(self.score_config.get('name'))
        base_model_hf_id = score_class.get_deployment_config().get('base_model_hf_id')
        if not base_model_hf_id:
            raise ValueError("base_model_hf_id is required in deployment config for LoRA training")

        lora_cfg = self.score_config.get('training', {}).get('lora', {})

        output_dir = lora_cfg.get('output_dir')
        if not output_dir:
            output_dir = os.path.join(
                get_output_dir(scorecard_name=self.scorecard_name, score_config=self.score_config),
                "lora_adapter"
            )
        os.makedirs(output_dir, exist_ok=True)
        self.adapter_output_dir = output_dir

        # Resolve hyperparameters (CLI overrides take precedence)
        epochs = self.extra_params.get('epochs', lora_cfg.get('epochs', 3))
        batch_size = self.extra_params.get('batch_size', lora_cfg.get('batch_size', 1))
        learning_rate = self.extra_params.get('learning_rate', lora_cfg.get('learning_rate', 2e-4))
        grad_accum = lora_cfg.get('gradient_accumulation_steps', 4)
        max_seq_length = lora_cfg.get('max_seq_length', 2048)

        metrics = train_lora_adapter(
            base_model_hf_id=base_model_hf_id,
            training_file=self.training_files['training_file'],
            validation_file=self.training_files.get('validation_file'),
            output_dir=output_dir,
            lora_config=lora_cfg,
            training_config={
                'epochs': epochs,
                'batch_size': batch_size,
                'learning_rate': learning_rate,
                'gradient_accumulation_steps': grad_accum,
                'max_seq_length': max_seq_length,
                'logging_steps': lora_cfg.get('logging_steps', 10),
                'save_steps': lora_cfg.get('save_steps', 200),
                'save_total_limit': lora_cfg.get('save_total_limit', 2),
                'eval_steps': lora_cfg.get('eval_steps', 200),
            }
        )
        self._training_metrics.update(metrics)

    def save_artifacts(self) -> Dict[str, str]:
        """
        Package adapter artifacts and upload to S3.
        """
        if not self.adapter_output_dir:
            raise RuntimeError("Adapter output directory not set; training may have failed")

        artifacts: Dict[str, str] = {
            "adapter_output_dir": self.adapter_output_dir,
        }

        # Push version if in YAML mode
        version_id = self._push_score_version_if_yaml_mode()
        if version_id:
            artifacts["version_id"] = version_id
            self._update_local_yaml_version(version_id)

        # Build adapter tarball
        tarball_path = os.path.join(self.adapter_output_dir, "adapter.tar.gz")
        self._create_adapter_tarball(self.adapter_output_dir, tarball_path)
        artifacts["adapter_tarball"] = tarball_path

        # Upload to S3
        s3_uri = self._upload_adapter_to_s3(tarball_path, version_id)
        if s3_uri:
            artifacts["adapter_s3_uri"] = s3_uri

        return artifacts

    def get_metrics(self) -> Dict[str, Any]:
        return self._training_metrics

    def _create_adapter_tarball(self, adapter_dir: str, tarball_path: str) -> None:
        import tarfile

        required_files = [
            "adapter_config.json",
            "adapter_model.safetensors",
            "adapter_model.bin",
        ]
        present = [f for f in required_files if os.path.exists(os.path.join(adapter_dir, f))]
        if not present:
            raise RuntimeError(
                "Adapter output missing adapter_config.json and adapter_model.* files. "
                "Training did not produce LoRA adapter artifacts."
            )

        with tarfile.open(tarball_path, "w:gz") as tar:
            for filename in present:
                tar.add(os.path.join(adapter_dir, filename), arcname=filename)

        logger.info(f"Created adapter tarball: {tarball_path}")

    def _upload_adapter_to_s3(self, tarball_path: str, version_id: Optional[str]) -> Optional[str]:
        try:
            import boto3
            from botocore.config import Config
            from boto3.s3.transfer import TransferConfig

            score_class = self.scorecard_class.score_registry.get(self.score_config.get('name'))
            base_model_hf_id = score_class.get_deployment_config().get('base_model_hf_id')

            s3_uri = get_adapter_s3_uri(
                scorecard_name=self.scorecard_name,
                score_config=self.score_config,
                base_model_hf_id=base_model_hf_id,
                version=version_id,
            )

            bucket_and_key = s3_uri.replace("s3://", "", 1)
            bucket_name, s3_key = bucket_and_key.split("/", 1)

            logger.info(f"Uploading adapter to {s3_uri}...")
            boto_config = Config(retries={"max_attempts": 5, "mode": "standard"})
            s3_client = boto3.client("s3", config=boto_config)
            transfer_config = TransferConfig(multipart_threshold=1024 * 25, max_concurrency=4)
            s3_client.upload_file(
                tarball_path,
                bucket_name,
                s3_key,
                Config=transfer_config,
            )
            logger.info(f"✓ Adapter uploaded to S3: {s3_uri}")
            return s3_uri

        except Exception as e:
            logger.warning(f"Failed to upload adapter to S3: {e}")
            logger.warning("Provisioning will need a manual adapter upload to S3")
            return None
