"""
SageMaker LoRA fine-tuning trainer.

Generates JSONL training data locally, uploads it to S3, launches a
SageMaker training job to produce LoRA adapter artifacts, then uploads
adapter.tar.gz to the convention-based S3 path for provisioning.
"""

import os
import time
import json
import tarfile
import tempfile
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from plexus.training.trainer import Trainer
from plexus.training.llm_finetune_trainer import LLMFineTuneTrainer
from plexus.training.utils import get_adapter_s3_uri

logger = logging.getLogger(__name__)


class LoraFineTuneTrainerSageMaker(Trainer):
    def get_training_type(self) -> str:
        return "lora"

    def get_platform(self) -> str:
        return "sagemaker"

    def validate(self):
        import boto3

        self.aws_region = os.getenv(
            'AWS_DEFAULT_REGION',
            os.getenv('AWS_REGION', os.getenv('AWS_REGION_NAME', 'us-east-1'))
        )
        logger.info(f"Using AWS region: {self.aws_region}")

        role_arn = os.getenv('SAGEMAKER_ROLE_ARN')
        if not role_arn:
            raise ValueError(
                "SAGEMAKER_ROLE_ARN environment variable not set. "
                "This should be an IAM role with SageMaker permissions."
            )

        training_cfg = self.score_config.get('training', {}) if isinstance(self.score_config, dict) else {}
        image_uri = training_cfg.get('image_uri') if isinstance(training_cfg, dict) else None
        image_uri = image_uri or getattr(self, "training_image_uri", None) or os.getenv('SAGEMAKER_TRAINING_IMAGE')
        if not image_uri:
            image_uri = (
                f"763104351884.dkr.ecr.{self.aws_region}.amazonaws.com/"
                "pytorch-training:2.2.0-gpu-py310-cu121-ubuntu20.04-sagemaker"
            )
            logger.info(f"SAGEMAKER_TRAINING_IMAGE not set; defaulting to {image_uri}")

        # Validate image region suffix matches
        if f".ecr.{self.aws_region}.amazonaws.com" not in image_uri:
            raise ValueError(
                f"SAGEMAKER_TRAINING_IMAGE region mismatch for {self.aws_region}. "
                f"Expected '.ecr.{self.aws_region}.amazonaws.com' in image URI, got: {image_uri}"
            )

        self.training_image_uri = image_uri

        try:
            sts = boto3.client('sts', region_name=self.aws_region)
            identity = sts.get_caller_identity()
            logger.info(f"AWS Account: {identity['Account']}")
            logger.info(f"AWS ARN: {identity['Arn']}")
        except Exception as e:
            raise RuntimeError(
                f"AWS credentials not configured or invalid. Error: {e}"
            )

        try:
            sagemaker = boto3.client('sagemaker', region_name=self.aws_region)
            sagemaker.list_training_jobs(MaxResults=1)
            logger.info("SageMaker permissions validated")
        except Exception as e:
            raise RuntimeError(
                f"SageMaker permissions not available. Error: {e}"
            )

    def prepare_data(self):
        """
        Generate JSONL training data and upload to S3 for SageMaker.
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

        self._upload_training_data_to_s3()

    def train(self):
        """
        Launch SageMaker training job and wait for completion.
        """
        training_code_s3_path = self._package_and_upload_code()

        training_config = self.score_config.get('training', {})
        lora_cfg = training_config.get('lora', {})

        instance_type = training_config.get('instance_type', 'ml.g6e.xlarge')
        volume_size = training_config.get('volume_size', 100)
        max_runtime = training_config.get('max_runtime', 3600 * 8)

        score_name_safe = self.score_config.get('name', 'model').replace(' ', '-').replace('_', '-')
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        job_name = f"plexus-lora-{score_name_safe}-{timestamp}"

        logger.info(f"Creating SageMaker training job: {job_name}")
        logger.info(f"Instance type: {instance_type}")

        self.training_job_name = self._create_training_job(
            job_name=job_name,
            training_code_s3_path=training_code_s3_path,
            instance_type=instance_type,
            volume_size=volume_size,
            max_runtime=max_runtime,
            lora_cfg=lora_cfg
        )

        self._wait_for_training_job()

    def save_artifacts(self) -> Dict[str, str]:
        """
        Download model artifacts, package adapter, upload to convention S3 path.
        """
        artifacts: Dict[str, str] = {}

        import boto3
        sagemaker = boto3.client('sagemaker', region_name=self.aws_region)
        job_description = sagemaker.describe_training_job(TrainingJobName=self.training_job_name)
        model_s3_path = job_description['ModelArtifacts']['S3ModelArtifacts']

        artifacts['model_s3_path'] = model_s3_path
        logger.info(f"Model artifacts in S3: {model_s3_path}")

        model_dir = self._download_model_artifacts(model_s3_path)
        artifacts['model_directory'] = model_dir

        version_id = self._push_score_version_if_yaml_mode()
        if version_id:
            artifacts['version_id'] = version_id
            self._update_local_yaml_version(version_id)

        tarball_path = os.path.join(model_dir, "adapter.tar.gz")
        self._create_adapter_tarball(model_dir, tarball_path)
        artifacts['adapter_tarball'] = tarball_path

        s3_uri = self._upload_adapter_to_s3(tarball_path, version_id)
        if s3_uri:
            artifacts['adapter_s3_uri'] = s3_uri

        return artifacts

    def get_metrics(self) -> Dict[str, Any]:
        import boto3

        sagemaker = boto3.client('sagemaker', region_name=self.aws_region)
        job_description = sagemaker.describe_training_job(TrainingJobName=self.training_job_name)

        metrics = {
            'training_time_seconds': job_description.get('TrainingTimeInSeconds', 0),
            'billable_time_seconds': job_description.get('BillableTimeInSeconds', 0),
            'training_job_name': self.training_job_name,
            'training_job_status': job_description['TrainingJobStatus']
        }

        final_metrics = job_description.get('FinalMetricDataList', [])
        for metric in final_metrics:
            metrics[metric['MetricName']] = metric['Value']

        logger.info(f"Training metrics: {metrics}")
        return metrics

    def _upload_training_data_to_s3(self):
        import boto3

        s3_bucket = os.getenv('PLEXUS_S3_BUCKET', 'plexus-training')
        s3_prefix = f"training-data/{self.get_scorecard_key()}/{self.get_score_key()}/{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        s3 = boto3.client('s3', region_name=self.aws_region)

        training_file = self.training_files['training_file']
        train_key = f"{s3_prefix}/training.jsonl"
        s3.upload_file(training_file, s3_bucket, train_key)

        val_key = None
        if self.training_files.get('validation_file'):
            val_key = f"{s3_prefix}/validation.jsonl"
            s3.upload_file(self.training_files['validation_file'], s3_bucket, val_key)

        self.data_s3_path = f"s3://{s3_bucket}/{s3_prefix}"
        self.training_data_keys = {
            'training': train_key,
            'validation': val_key
        }
        logger.info(f"Training data uploaded to {self.data_s3_path}")

    def _package_and_upload_code(self) -> str:
        import boto3

        with tempfile.TemporaryDirectory() as temp_dir:
            train_script = os.path.join(temp_dir, 'train.py')
            core_script = os.path.join(temp_dir, 'lora_finetune_core.py')
            requirements = os.path.join(temp_dir, 'requirements.txt')

            self._create_training_script(train_script)
            self._write_core_module(core_script)
            self._create_requirements_file(requirements)

            tarball_path = os.path.join(temp_dir, 'sourcedir.tar.gz')
            with tarfile.open(tarball_path, 'w:gz') as tar:
                tar.add(train_script, arcname='train.py')
                tar.add(core_script, arcname='lora_finetune_core.py')
                tar.add(requirements, arcname='requirements.txt')

            s3_bucket = os.getenv('PLEXUS_S3_BUCKET', 'plexus-training')
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            s3_key = f"training-code/{self.get_scorecard_key()}/{self.get_score_key()}/{timestamp}/sourcedir.tar.gz"

            s3 = boto3.client('s3', region_name=self.aws_region)
            s3.upload_file(tarball_path, s3_bucket, s3_key)

            s3_path = f"s3://{s3_bucket}/{s3_key}"
            logger.info(f"Training code uploaded to S3: {s3_path}")
            return s3_path

    def _write_core_module(self, output_path: str):
        from pathlib import Path
        core_path = Path(__file__).with_name('lora_finetune_core.py')
        with open(core_path, 'r') as src:
            content = src.read()
        with open(output_path, 'w') as dst:
            dst.write(content)

    def _create_training_script(self, output_path: str):
        script_content = '''
import os
import json
import argparse
import torch

# Patch for older torch versions missing LRScheduler
if not hasattr(torch.optim.lr_scheduler, "LRScheduler") and hasattr(torch.optim.lr_scheduler, "_LRScheduler"):
    torch.optim.lr_scheduler.LRScheduler = torch.optim.lr_scheduler._LRScheduler

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAINING'))
    parser.add_argument('--output-data-dir', type=str, default=os.environ.get('SM_OUTPUT_DATA_DIR'))

    parser.add_argument('--base_model_hf_id', type=str, required=True)
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--batch_size', type=int, default=1)
    parser.add_argument('--learning_rate', type=float, default=2e-4)
    parser.add_argument('--gradient_accumulation_steps', type=int, default=4)
    parser.add_argument('--max_seq_length', type=int, default=2048)
    parser.add_argument('--quantization', type=str, default='')

    parser.add_argument('--lora_r', type=int, default=64)
    parser.add_argument('--lora_alpha', type=int, default=16)
    parser.add_argument('--lora_dropout', type=float, default=0.1)

    args, _ = parser.parse_known_args()

    # Log versions for debugging
    try:
        import transformers
        print(f"torch={torch.__version__} transformers={transformers.__version__}")
    except Exception as e:
        print(f"Version check failed: {e}")

    from lora_finetune_core import train_lora_adapter

    train_file = os.path.join(args.train, 'training.jsonl')
    val_file = os.path.join(args.train, 'validation.jsonl')
    if not os.path.exists(val_file):
        val_file = None

    lora_cfg = {
        'r': args.lora_r,
        'lora_alpha': args.lora_alpha,
        'lora_dropout': args.lora_dropout,
    }
    training_cfg = {
        'epochs': args.epochs,
        'batch_size': args.batch_size,
        'learning_rate': args.learning_rate,
        'gradient_accumulation_steps': args.gradient_accumulation_steps,
        'max_seq_length': args.max_seq_length,
        'quantization': args.quantization or None,
    }

    metrics = train_lora_adapter(
        base_model_hf_id=args.base_model_hf_id,
        training_file=train_file,
        validation_file=val_file,
        output_dir=args.model_dir,
        lora_config=lora_cfg,
        training_config=training_cfg,
    )

    metrics_path = os.path.join(args.model_dir, 'sagemaker_metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)


if __name__ == '__main__':
    main()
'''
        with open(output_path, 'w') as f:
            f.write(script_content)

    def _create_requirements_file(self, output_path: str):
        requirements = [
            'torch==2.2.0',
            'transformers==4.46.3',
            'accelerate==0.34.2',
            'peft==0.12.0',
            'datasets==2.19.1',
            'tokenizers==0.20.1',
            'bitsandbytes==0.43.1'
        ]
        with open(output_path, 'w') as f:
            f.write('\n'.join(requirements))

    def _create_training_job(self, job_name: str, training_code_s3_path: str,
                            instance_type: str, volume_size: int, max_runtime: int,
                            lora_cfg: Dict[str, Any]) -> str:
        import boto3

        sagemaker = boto3.client('sagemaker', region_name=self.aws_region)

        role_arn = os.getenv('SAGEMAKER_ROLE_ARN')
        training_cfg = self.score_config.get('training', {}) if isinstance(self.score_config, dict) else {}
        image_uri = training_cfg.get('image_uri') if isinstance(training_cfg, dict) else None
        image_uri = image_uri or os.getenv('SAGEMAKER_TRAINING_IMAGE') or self.training_image_uri

        s3_bucket = os.getenv('PLEXUS_S3_BUCKET', 'plexus-training')
        output_path = f"s3://{s3_bucket}/training-output/{job_name}"

        score_class = self.scorecard_class.score_registry.get(self.score_config.get('name'))
        base_model_hf_id = score_class.get_deployment_config().get('base_model_hf_id')

        hyperparameters = {
            'base_model_hf_id': base_model_hf_id,
            'epochs': str(self.extra_params.get('epochs', lora_cfg.get('epochs', 3))),
            'batch_size': str(self.extra_params.get('batch_size', lora_cfg.get('batch_size', 1))),
            'learning_rate': str(self.extra_params.get('learning_rate', lora_cfg.get('learning_rate', 2e-4))),
            'gradient_accumulation_steps': str(lora_cfg.get('gradient_accumulation_steps', 4)),
            'max_seq_length': str(lora_cfg.get('max_seq_length', 2048)),
            'lora_r': str(lora_cfg.get('r', 64)),
            'lora_alpha': str(lora_cfg.get('lora_alpha', 16)),
            'lora_dropout': str(lora_cfg.get('lora_dropout', 0.1)),
            'quantization': str(lora_cfg.get('quantization', '') or ''),
            # Script mode entry point configuration
            'sagemaker_program': 'train.py',
            'sagemaker_submit_directory': training_code_s3_path,
        }

        env = {
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"
        }
        hf_token = os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACE_HUB_TOKEN')
        if hf_token:
            env['HF_TOKEN'] = hf_token
            env['HUGGINGFACE_HUB_TOKEN'] = hf_token

        sagemaker.create_training_job(
            TrainingJobName=job_name,
            RoleArn=role_arn,
            AlgorithmSpecification={
                'TrainingImage': image_uri,
                'TrainingInputMode': 'File'
            },
            HyperParameters=hyperparameters,
            Environment=env,
            InputDataConfig=[
                {
                    'ChannelName': 'training',
                    'DataSource': {
                        'S3DataSource': {
                            'S3DataType': 'S3Prefix',
                            'S3Uri': self.data_s3_path,
                            'S3DataDistributionType': 'FullyReplicated'
                        }
                    }
                }
            ],
            OutputDataConfig={
                'S3OutputPath': output_path
            },
            ResourceConfig={
                'InstanceType': instance_type,
                'InstanceCount': 1,
                'VolumeSizeInGB': volume_size
            },
            StoppingCondition={
                'MaxRuntimeInSeconds': max_runtime
            },
        )

        logger.info(f"Training job created: {job_name}")
        return job_name

    def _wait_for_training_job(self):
        import boto3

        sagemaker = boto3.client('sagemaker', region_name=self.aws_region)
        logger.info(f"Waiting for training job {self.training_job_name} to complete...")

        while True:
            response = sagemaker.describe_training_job(TrainingJobName=self.training_job_name)
            status = response['TrainingJobStatus']

            if status in ['Completed', 'Stopped']:
                logger.info(f"Training job completed with status: {status}")
                break
            if status == 'Failed':
                failure_reason = response.get('FailureReason', 'Unknown')
                raise RuntimeError(f"Training job failed: {failure_reason}")

            if 'SecondaryStatusTransitions' in response:
                latest_status = response['SecondaryStatusTransitions'][-1]
                logger.info(f"Status: {latest_status['Status']} - {latest_status.get('StatusMessage', '')}")

            time.sleep(30)

    def _download_model_artifacts(self, s3_model_path: str) -> str:
        import boto3

        s3_parts = s3_model_path.replace('s3://', '').split('/', 1)
        s3_bucket = s3_parts[0]
        s3_key = s3_parts[1]

        model_dir = os.path.join(
            'models',
            self.get_scorecard_key(),
            self.get_score_key()
        )
        os.makedirs(model_dir, exist_ok=True)

        local_tarball = os.path.join(model_dir, 'model.tar.gz')
        s3 = boto3.client('s3', region_name=self.aws_region)
        s3.download_file(s3_bucket, s3_key, local_tarball)

        with tarfile.open(local_tarball, 'r:gz') as tar:
            tar.extractall(model_dir)

        os.unlink(local_tarball)
        logger.info(f"Model artifacts extracted to: {model_dir}")
        return model_dir

    def _create_adapter_tarball(self, adapter_dir: str, tarball_path: str) -> None:
        required_files = [
            'adapter_config.json',
            'adapter_model.safetensors',
            'adapter_model.bin',
        ]
        present = [f for f in required_files if os.path.exists(os.path.join(adapter_dir, f))]
        if not present:
            raise RuntimeError(
                "Adapter output missing adapter_config.json and adapter_model.* files."
            )

        with tarfile.open(tarball_path, 'w:gz') as tar:
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

            bucket_and_key = s3_uri.replace('s3://', '', 1)
            bucket_name, s3_key = bucket_and_key.split('/', 1)

            logger.info(f"Uploading adapter to {s3_uri}...")
            boto_config = Config(retries={'max_attempts': 5, 'mode': 'standard'})
            s3_client = boto3.client('s3', config=boto_config)
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
