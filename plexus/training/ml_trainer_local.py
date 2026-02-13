"""
Local ML model trainer.

This trainer wraps the existing Score.train_model() workflow for local training
of traditional ML models (sklearn, TensorFlow, PyTorch, etc.).
"""

import os
import json
import logging
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from plexus.training.trainer import Trainer

logger = logging.getLogger(__name__)


class MLTrainerLocal(Trainer):
    """
    Trainer for local ML model training.

    Delegates to the Score's train_model() and evaluate_model() methods,
    which implement the actual training logic. This maintains backward
    compatibility with existing Score classes.

    Compatible Score classes:
        - DeepLearningSemanticClassifier
        - OpenAIEmbeddingsClassifier
        - FastTextClassifier
        - BERTClassifier
        - SVMClassifier
        - And any Score with train_model() method

    Training artifacts:
        - Models saved to: ./models/{scorecard_name}/{score_name}/
        - Metrics saved to: ./reports/{scorecard_name}/{score_name}/metrics.json
        - Visualizations: confusion_matrix.png, roc_curve.png, etc.
    """

    def get_training_type(self) -> str:
        """Return training type identifier."""
        return "ml"

    def get_platform(self) -> str:
        """Return training platform."""
        return "local"

    def validate(self):
        """
        Validate that Score class has train_model method.

        Raises:
            ValueError: If Score class doesn't support training
        """
        import importlib

        score_class_name = self.score_config['class']

        # Import the Score class to check if it has train_model method
        # Import directly from the class file
        try:
            class_module = importlib.import_module(f'plexus.scores.{score_class_name}')
            score_class = getattr(class_module, score_class_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(
                f"Could not import Score class '{score_class_name}'. "
                f"Make sure the class exists in plexus/scores/{score_class_name}.py. Error: {e}"
            )

        # Check that Score class has train_model method
        if not hasattr(score_class, 'train_model'):
            raise ValueError(
                f"Score class '{score_class_name}' does not have a 'train_model' method. "
                f"Local ML training requires Score classes with train_model() implementation."
            )

        # Optionally check for evaluate_model (not strictly required, but expected)
        if not hasattr(score_class, 'evaluate_model'):
            logger.warning(
                f"Score class '{score_class_name}' does not have 'evaluate_model' method. "
                f"Evaluation will be skipped."
            )

    def prepare_data(self):
        """
        Load and process training data using Score methods.

        Calls:
            - Score.load_data(): Load data from data source
            - Score.process_data(): Apply processors and prepare for training
        """
        # Load data using Score's load_data method
        # The score_config['data'] contains the data source configuration
        self.score_instance.load_data(
            data=self.score_config.get('data'),
            fresh=self.fresh
        )

        # Process data using Score's process_data method
        # This applies processors, handles train/val split, etc.
        self.score_instance.process_data()

        logger.info(f"Data prepared: {len(self.score_instance.dataframe)} samples")

    def train(self):
        """
        Train the model by delegating to Score.train_model().

        The Score's train_model() method handles the actual training logic,
        which varies by Score type (TensorFlow, sklearn, etc.).
        """
        # Record configuration to file (matches existing behavior)
        if hasattr(self.score_instance, 'record_configuration'):
            self.score_instance.record_configuration(self.score_config)

        # Delegate to Score's train_model method
        self.score_instance.train_model()

        logger.info("Model training completed")

    def save_artifacts(self) -> Dict[str, str]:
        """
        Save model artifacts and return their locations.

        The Score's train_model() typically saves models automatically,
        but we can optionally call save_model() if available.

        For YAML-based training, this also:
        1. Creates a new ScoreVersion in the API
        2. Uses the version ID in the S3 path for proper versioning

        Returns:
            Dictionary with model directory path and S3 URI
        """
        artifacts = {}

        # Get model directory path
        if hasattr(self.score_instance, 'model_directory_path'):
            model_dir = self.score_instance.model_directory_path()
            artifacts['model_directory'] = model_dir
            logger.info(f"Model saved to: {model_dir}")
        else:
            # Fallback: construct expected path using keys
            model_dir = os.path.join(
                'models',
                self.get_scorecard_key(),
                self.get_score_key()
            )
            artifacts['model_directory'] = model_dir

        # Optionally call save_model if Score supports it
        if hasattr(self.score_instance, 'save_model'):
            try:
                self.score_instance.save_model()
                logger.info("Explicitly saved model using Score.save_model()")
            except Exception as e:
                logger.warning(f"Score.save_model() failed: {e}")

        # Push new score version if in YAML mode
        version_id = self._push_score_version_if_yaml_mode()
        if version_id:
            artifacts['version_id'] = version_id
            # Update local YAML with new version ID so provisioning can find the model
            self._update_local_yaml_version(version_id)

        # Upload model to S3 for later provisioning
        s3_uri = self._upload_model_to_s3(model_dir, version_id)
        if s3_uri:
            artifacts['model_s3_uri'] = s3_uri

        return artifacts

    def _upload_model_to_s3(self, model_dir: str, version_id: Optional[str] = None) -> Optional[str]:
        """
        Upload trained model to S3 for provisioning.

        Creates a model.tar.gz archive and uploads to:
        - With version: s3://{bucket}/models/{scorecard_key}/{score_key}/{version_id}/model.tar.gz
        - Without version: s3://{bucket}/models/{scorecard_key}/{score_key}/model.tar.gz

        Args:
            model_dir: Local directory containing the trained model
            version_id: Optional score version ID (from API) for versioned storage

        Returns:
            S3 URI to the uploaded model.tar.gz, or None if upload failed
        """
        # If no version ID was pushed (non-YAML mode), try to get it from score config
        if not version_id:
            version_id = self.score_config.get('version')
            if version_id:
                logger.info(f"Using version ID from score config: {version_id}")

        try:
            import boto3
            from botocore.exceptions import ClientError
            from botocore.config import Config
            from boto3.s3.transfer import TransferConfig

            # Get S3 bucket from environment
            bucket_name = os.getenv('PLEXUS_S3_BUCKET')
            if not bucket_name:
                logger.warning(
                    "PLEXUS_S3_BUCKET not set. Model saved locally but not uploaded to S3. "
                    "Set PLEXUS_S3_BUCKET to enable automatic upload for easier provisioning."
                )
                return None

            # Create requirements.txt for SageMaker inference
            requirements_path = os.path.join(model_dir, 'requirements.txt')
            if not os.path.exists(requirements_path):
                logger.info("Creating requirements.txt for SageMaker inference...")
                with open(requirements_path, 'w') as f:
                    # Add required dependencies for BERT models
                    f.write("transformers==4.30.0\n")
                    f.write("torch==2.3.0\n")
                    f.write("numpy\n")
                    f.write("scikit-learn\n")
                logger.info("✓ Created requirements.txt")
            else:
                logger.info("requirements.txt already exists in model directory")

            # Create tarball of model directory
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
                tmp_tarball_path = tmp_file.name

            logger.info(f"Creating model tarball from {model_dir}...")
            with tarfile.open(tmp_tarball_path, 'w:gz') as tar:
                tar.add(model_dir, arcname='.')

            # Build S3 key with version ID if available
            scorecard_key = self.get_scorecard_key()
            score_key = self.get_score_key()

            if version_id:
                # Versioned path: models/{scorecard}/{score}/{version}/model.tar.gz
                s3_key = f"models/{scorecard_key}/{score_key}/{version_id}/model.tar.gz"
                logger.info(f"Using versioned S3 path with version {version_id}")
            else:
                # Legacy path: models/{scorecard}/{score}/model.tar.gz
                s3_key = f"models/{scorecard_key}/{score_key}/model.tar.gz"
                logger.warning("No version ID available - using legacy S3 path without version")

            s3_uri = f"s3://{bucket_name}/{s3_key}"

            # Configure S3 client for reliable large file uploads
            # - Increase timeouts for large files
            # - Enable retries with exponential backoff
            # - Let boto3 auto-discover region from bucket
            boto_config = Config(
                connect_timeout=60,
                read_timeout=60,
                retries={
                    'max_attempts': 10,
                    'mode': 'adaptive'
                }
            )

            # Configure transfer for large files
            # - 100MB multipart threshold
            # - 100MB chunk size
            # - 10 concurrent uploads
            transfer_config = TransferConfig(
                multipart_threshold=100 * 1024 * 1024,
                multipart_chunksize=100 * 1024 * 1024,
                max_concurrency=10,
                use_threads=True
            )

            logger.info(f"Uploading model to {s3_uri}...")
            s3_client = boto3.client('s3', config=boto_config)
            s3_client.upload_file(
                tmp_tarball_path,
                bucket_name,
                s3_key,
                Config=transfer_config
            )

            logger.info(f"✓ Model uploaded to S3: {s3_uri}")

            # Clean up temporary tarball
            os.unlink(tmp_tarball_path)

            return s3_uri

        except ImportError as e:
            logger.warning(f"boto3 not available: {e}. Model saved locally but not uploaded to S3.")
            return None
        except ClientError as e:
            logger.error(f"Failed to upload model to S3: {e}")
            logger.info("Model is still available locally and can be manually uploaded later.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading model to S3: {e}")
            return None

    def get_metrics(self) -> Dict[str, Any]:
        """
        Collect training metrics.

        Note: Post-training evaluation is skipped here since Plexus has a dedicated
        'plexus evaluate accuracy' command for comprehensive model evaluation.
        Users should run proper evaluations after training completes.

        Returns:
            Dictionary of training metrics (from training_history.json if available)
        """
        metrics = {}

        # Skip evaluate_model() - use 'plexus evaluate accuracy' instead for proper evaluation
        logger.info("Skipping post-training evaluation - use 'plexus evaluate accuracy' for comprehensive evaluation")

        # Try to read training_history.json from model directory (BERTClassifier, etc.)
        if hasattr(self.score_instance, 'model_directory_path'):
            model_dir = self.score_instance.model_directory_path()
            training_history_file = os.path.join(model_dir, 'training_history.json')
            if os.path.exists(training_history_file):
                try:
                    with open(training_history_file, 'r') as f:
                        history = json.load(f)
                    # Extract final metrics from history (last epoch)
                    if history:
                        metrics = history[-1] if isinstance(history, list) else history
                    logger.info(f"Loaded training metrics from: {training_history_file}")
                    return metrics
                except Exception as e:
                    logger.debug(f"Could not read training_history.json: {e}")

        # Try to read metrics from metrics.json file in reports directory
        if hasattr(self.score_instance, 'report_file_name'):
            metrics_file = self.score_instance.report_file_name("metrics.json")
            if os.path.exists(metrics_file):
                try:
                    with open(metrics_file, 'r') as f:
                        metrics = json.load(f)
                    logger.info(f"Loaded metrics from: {metrics_file}")
                    return metrics
                except Exception as e:
                    logger.debug(f"Could not read metrics file: {e}")

        # No metrics found - this is fine, training completed successfully
        logger.debug("No metrics file found, but training completed successfully")
        return metrics
