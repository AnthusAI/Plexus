"""
SageMaker ML model trainer.

This trainer launches AWS SageMaker training jobs for ML models.
It packages the training code, uploads data to S3, launches the job,
and downloads the trained model artifacts.
"""

import os
import json
import time
import logging
import tarfile
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime

from plexus.training.trainer import Trainer

logger = logging.getLogger(__name__)


class MLTrainerSageMaker(Trainer):
    """
    Trainer for SageMaker ML model training.

    Launches training jobs on AWS SageMaker for traditional ML models
    (sklearn, TensorFlow, PyTorch, etc.). Handles packaging, S3 uploads,
    job monitoring, and artifact downloads.

    Compatible Score classes:
        - DeepLearningSemanticClassifier
        - OpenAIEmbeddingsClassifier
        - FastTextClassifier
        - BERTClassifier
        - SVMClassifier
        - And any Score with train_model() method

    Training workflow:
        1. Validate AWS credentials and SageMaker permissions
        2. Package training code and dependencies
        3. Upload data to S3
        4. Create and launch SageMaker training job
        5. Monitor job until completion
        6. Download trained model artifacts from S3
    """

    def get_training_type(self) -> str:
        """Return training type identifier."""
        return "ml"

    def get_platform(self) -> str:
        """Return training platform."""
        return "sagemaker"

    def validate(self):
        """
        Validate AWS credentials and SageMaker permissions.

        Raises:
            ValueError: If Score class doesn't support training
            RuntimeError: If AWS credentials or permissions are missing
        """
        import importlib
        import boto3

        # Get AWS region from environment or use default
        self.aws_region = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'us-east-1'))
        logger.info(f"Using AWS region: {self.aws_region}")

        # Check Score class has train_model method
        score_class_name = self.score_config['class']
        try:
            class_module = importlib.import_module(f'plexus.scores.{score_class_name}')
            score_class = getattr(class_module, score_class_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(
                f"Could not import Score class '{score_class_name}'. "
                f"Make sure the class exists in plexus/scores/{score_class_name}.py. Error: {e}"
            )

        if not hasattr(score_class, 'train_model'):
            raise ValueError(
                f"Score class '{score_class_name}' does not have a 'train_model' method. "
                f"SageMaker ML training requires Score classes with train_model() implementation."
            )

        # Validate AWS credentials
        try:
            sts = boto3.client('sts', region_name=self.aws_region)
            identity = sts.get_caller_identity()
            logger.info(f"AWS Account: {identity['Account']}")
            logger.info(f"AWS ARN: {identity['Arn']}")
        except Exception as e:
            raise RuntimeError(
                f"AWS credentials not configured or invalid. "
                f"Please configure AWS credentials using 'aws configure' or environment variables. "
                f"Error: {e}"
            )

        # Validate SageMaker permissions
        try:
            sagemaker = boto3.client('sagemaker', region_name=self.aws_region)
            # List training jobs to test permissions
            sagemaker.list_training_jobs(MaxResults=1)
            logger.info("SageMaker permissions validated")
        except Exception as e:
            raise RuntimeError(
                f"SageMaker permissions not available. "
                f"Ensure your AWS credentials have sagemaker:* permissions. "
                f"Error: {e}"
            )

    def prepare_data(self):
        """
        Load and prepare training data, then upload to S3.

        Calls:
            - Score.load_data(): Load data from data source
            - Score.process_data(): Apply processors and prepare for training
            - Upload processed data to S3
        """
        # Load data using Score's load_data method
        self.score_instance.load_data(
            data=self.score_config.get('data'),
            fresh=self.fresh
        )

        # Process data using Score's process_data method
        self.score_instance.process_data()

        logger.info(f"Data prepared: {len(self.score_instance.dataframe)} samples")

        # Upload data to S3
        self._upload_data_to_s3()

    def train(self):
        """
        Launch SageMaker training job and wait for completion.

        Creates a SageMaker training job with the packaged training code,
        monitors its progress, and handles errors.
        """
        # Package training code
        training_code_s3_path = self._package_and_upload_code()

        # Get training configuration
        training_config = self.score_config.get('training', {})
        instance_type = training_config.get('instance_type', 'ml.m5.xlarge')
        base_model_name = training_config.get('base_model_name', self.score_config.get('embeddings_model'))

        # Create unique job name
        score_name_safe = self.score_config.get('name', 'model').replace(' ', '-').replace('_', '-')
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        job_name = f"plexus-{score_name_safe}-{timestamp}"

        logger.info(f"Creating SageMaker training job: {job_name}")
        logger.info(f"Instance type: {instance_type}")
        logger.info(f"Base model: {base_model_name}")

        # Create training job
        self.training_job_name = self._create_training_job(
            job_name=job_name,
            training_code_s3_path=training_code_s3_path,
            instance_type=instance_type
        )

        # Wait for job completion
        self._wait_for_training_job()

    def save_artifacts(self) -> Dict[str, str]:
        """
        Download model artifacts from S3 and return their locations.

        Returns:
            Dictionary with model paths:
                - model_s3_path: S3 path to model artifacts
                - model_directory: Local directory with downloaded model
        """
        artifacts = {}

        # Get model S3 path from training job
        import boto3
        sagemaker = boto3.client('sagemaker', region_name=self.aws_region)

        job_description = sagemaker.describe_training_job(TrainingJobName=self.training_job_name)
        model_s3_path = job_description['ModelArtifacts']['S3ModelArtifacts']

        artifacts['model_s3_path'] = model_s3_path
        logger.info(f"Model artifacts in S3: {model_s3_path}")

        # Download model artifacts to local directory
        model_dir = self._download_model_artifacts(model_s3_path)
        artifacts['model_directory'] = model_dir
        logger.info(f"Model downloaded to: {model_dir}")

        return artifacts

    def get_metrics(self) -> Dict[str, Any]:
        """
        Collect training metrics from SageMaker CloudWatch logs.

        Returns:
            Dictionary of training metrics from CloudWatch
        """
        import boto3

        # Get metrics from training job
        sagemaker = boto3.client('sagemaker', region_name=self.aws_region)
        job_description = sagemaker.describe_training_job(TrainingJobName=self.training_job_name)

        metrics = {
            'training_time_seconds': job_description.get('TrainingTimeInSeconds', 0),
            'billable_time_seconds': job_description.get('BillableTimeInSeconds', 0),
            'training_job_name': self.training_job_name,
            'training_job_status': job_description['TrainingJobStatus']
        }

        # Get final metrics from CloudWatch if available
        final_metrics = job_description.get('FinalMetricDataList', [])
        for metric in final_metrics:
            metrics[metric['MetricName']] = metric['Value']

        logger.info(f"Training metrics: {metrics}")
        return metrics

    def _upload_data_to_s3(self):
        """Upload processed training data to S3."""
        import boto3

        # Save dataframe to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            self.score_instance.dataframe.to_csv(f.name, index=False)
            local_data_path = f.name

        # Upload to S3 using keys for paths
        s3_bucket = os.getenv('PLEXUS_S3_BUCKET', 'plexus-training')
        s3_key = f"training-data/{self.get_scorecard_key()}/{self.get_score_key()}/data.csv"

        s3 = boto3.client('s3', region_name=self.aws_region)
        s3.upload_file(local_data_path, s3_bucket, s3_key)

        self.data_s3_path = f"s3://{s3_bucket}/{s3_key}"
        logger.info(f"Data uploaded to S3: {self.data_s3_path}")

        # Clean up temporary file
        os.unlink(local_data_path)

    def _package_and_upload_code(self) -> str:
        """
        Package training code and upload to S3.

        Returns:
            S3 path to training code tarball
        """
        import boto3

        # Create temporary directory for training code
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create training script
            train_script = os.path.join(temp_dir, 'train.py')
            self._create_training_script(train_script)

            # Create requirements.txt
            requirements = os.path.join(temp_dir, 'requirements.txt')
            self._create_requirements_file(requirements)

            # Package as tarball
            tarball_path = os.path.join(temp_dir, 'sourcedir.tar.gz')
            with tarfile.open(tarball_path, 'w:gz') as tar:
                tar.add(train_script, arcname='train.py')
                tar.add(requirements, arcname='requirements.txt')

            # Upload to S3 using keys for paths
            s3_bucket = os.getenv('PLEXUS_S3_BUCKET', 'plexus-training')
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            s3_key = f"training-code/{self.get_scorecard_key()}/{self.get_score_key()}/{timestamp}/sourcedir.tar.gz"

            s3 = boto3.client('s3', region_name=self.aws_region)
            s3.upload_file(tarball_path, s3_bucket, s3_key)

            s3_path = f"s3://{s3_bucket}/{s3_key}"
            logger.info(f"Training code uploaded to S3: {s3_path}")
            return s3_path

    def _create_training_script(self, output_path: str):
        """Create SageMaker training script."""
        # This is a simplified training script
        # In a real implementation, this would be more comprehensive
        script_content = '''
import os
import json
import argparse

def train():
    """SageMaker training entry point."""
    parser = argparse.ArgumentParser()

    # SageMaker-specific arguments
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN'))
    parser.add_argument('--output-data-dir', type=str, default=os.environ.get('SM_OUTPUT_DATA_DIR'))

    args, _ = parser.parse_known_args()

    # TODO: Implement actual training logic here
    # This would load data, instantiate Score, and call train_model()

    print(f"Training data directory: {args.train}")
    print(f"Model output directory: {args.model_dir}")

if __name__ == '__main__':
    train()
'''

        with open(output_path, 'w') as f:
            f.write(script_content)

    def _create_requirements_file(self, output_path: str):
        """Create requirements.txt for SageMaker."""
        requirements = [
            'pandas',
            'numpy',
            'scikit-learn',
            'torch',
            'transformers',
        ]

        with open(output_path, 'w') as f:
            f.write('\n'.join(requirements))

    def _create_training_job(self, job_name: str, training_code_s3_path: str,
                            instance_type: str) -> str:
        """
        Create SageMaker training job.

        Returns:
            Training job name
        """
        import boto3

        sagemaker = boto3.client('sagemaker', region_name=self.aws_region)

        # Get SageMaker execution role
        role_arn = os.getenv('SAGEMAKER_ROLE_ARN')
        if not role_arn:
            raise ValueError(
                "SAGEMAKER_ROLE_ARN environment variable not set. "
                "This should be an IAM role with SageMaker permissions."
            )

        # Parse S3 paths
        s3_bucket = os.getenv('PLEXUS_S3_BUCKET', 'plexus-training')
        output_path = f"s3://{s3_bucket}/training-output/{job_name}"

        # Create training job
        sagemaker.create_training_job(
            TrainingJobName=job_name,
            RoleArn=role_arn,
            AlgorithmSpecification={
                'TrainingImage': 'pytorch-training:latest',  # Would use actual ECR image
                'TrainingInputMode': 'File'
            },
            InputDataConfig=[
                {
                    'ChannelName': 'train',
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
                'VolumeSizeInGB': 50
            },
            StoppingCondition={
                'MaxRuntimeInSeconds': 3600 * 6  # 6 hours max
            }
        )

        logger.info(f"Training job created: {job_name}")
        return job_name

    def _wait_for_training_job(self):
        """Wait for training job to complete, logging progress."""
        import boto3

        sagemaker = boto3.client('sagemaker', region_name=self.aws_region)

        logger.info(f"Waiting for training job {self.training_job_name} to complete...")

        while True:
            response = sagemaker.describe_training_job(TrainingJobName=self.training_job_name)
            status = response['TrainingJobStatus']

            if status in ['Completed', 'Stopped']:
                logger.info(f"Training job completed with status: {status}")
                break
            elif status == 'Failed':
                failure_reason = response.get('FailureReason', 'Unknown')
                raise RuntimeError(f"Training job failed: {failure_reason}")

            # Log progress
            if 'SecondaryStatusTransitions' in response:
                latest_status = response['SecondaryStatusTransitions'][-1]
                logger.info(f"Status: {latest_status['Status']} - {latest_status.get('StatusMessage', '')}")

            time.sleep(30)  # Poll every 30 seconds

    def _download_model_artifacts(self, s3_model_path: str) -> str:
        """
        Download model artifacts from S3.

        Args:
            s3_model_path: S3 URI to model.tar.gz

        Returns:
            Local directory path with extracted model
        """
        import boto3

        # Parse S3 path
        s3_parts = s3_model_path.replace('s3://', '').split('/', 1)
        s3_bucket = s3_parts[0]
        s3_key = s3_parts[1]

        # Create local model directory using keys
        model_dir = os.path.join(
            'models',
            self.get_scorecard_key(),
            self.get_score_key()
        )
        os.makedirs(model_dir, exist_ok=True)

        # Download tarball
        local_tarball = os.path.join(model_dir, 'model.tar.gz')
        s3 = boto3.client('s3', region_name=self.aws_region)
        s3.download_file(s3_bucket, s3_key, local_tarball)

        # Extract tarball
        with tarfile.open(local_tarball, 'r:gz') as tar:
            tar.extractall(model_dir)

        # Remove tarball
        os.unlink(local_tarball)

        logger.info(f"Model artifacts extracted to: {model_dir}")
        return model_dir
