"""
Local ML model trainer.

This trainer wraps the existing Score.train_model() workflow for local training
of traditional ML models (sklearn, TensorFlow, PyTorch, etc.).
"""

import os
import json
import logging
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

    def get_target(self) -> str:
        """Return target platform."""
        return "local"

    def validate(self):
        """
        Validate that Score class has train_model method.

        Raises:
            ValueError: If Score class doesn't support training
        """
        score_class_name = self.score_config['class']

        # Check that Score class has train_model method
        if not hasattr(self.score_instance.__class__, 'train_model'):
            raise ValueError(
                f"Score class '{score_class_name}' does not have a 'train_model' method. "
                f"Local ML training requires Score classes with train_model() implementation."
            )

        # Optionally check for evaluate_model (not strictly required, but expected)
        if not hasattr(self.score_instance.__class__, 'evaluate_model'):
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

        Returns:
            Dictionary with model directory path
        """
        artifacts = {}

        # Get model directory path
        if hasattr(self.score_instance, 'model_directory_path'):
            model_dir = self.score_instance.model_directory_path()
            artifacts['model_directory'] = model_dir
            logger.info(f"Model saved to: {model_dir}")
        else:
            # Fallback: construct expected path
            model_dir = os.path.join(
                'models',
                self.scorecard_class.name,
                self.score_config.get('name', 'Unknown')
            )
            artifacts['model_directory'] = model_dir

        # Optionally call save_model if Score supports it
        if hasattr(self.score_instance, 'save_model'):
            try:
                self.score_instance.save_model()
                logger.info("Explicitly saved model using Score.save_model()")
            except Exception as e:
                logger.warning(f"Score.save_model() failed: {e}")

        return artifacts

    def get_metrics(self) -> Dict[str, Any]:
        """
        Collect training metrics by running evaluation.

        Calls Score.evaluate_model() which generates metrics and visualizations,
        then reads the metrics from the metrics.json file.

        Returns:
            Dictionary of training/validation metrics
        """
        metrics = {}

        # Run evaluation if Score supports it
        if hasattr(self.score_instance, 'evaluate_model'):
            try:
                self.score_instance.evaluate_model()
                logger.info("Model evaluation completed")
            except Exception as e:
                logger.error(f"Evaluation failed: {e}")
                return {'error': str(e)}

        # Try to read metrics from metrics.json file
        if hasattr(self.score_instance, 'report_file_name'):
            metrics_file = self.score_instance.report_file_name("metrics.json")
            if os.path.exists(metrics_file):
                try:
                    with open(metrics_file, 'r') as f:
                        metrics = json.load(f)
                    logger.info(f"Loaded metrics from: {metrics_file}")
                except Exception as e:
                    logger.warning(f"Could not read metrics file: {e}")
            else:
                logger.warning(f"Metrics file not found: {metrics_file}")
        else:
            # Fallback: try to construct metrics file path
            metrics_file = os.path.join(
                os.getenv('PLEXUS_REPORTS_DIR', './tmp/reports'),
                self.scorecard_class.name,
                self.score_config.get('name', 'Unknown'),
                'metrics.json'
            )
            if os.path.exists(metrics_file):
                try:
                    with open(metrics_file, 'r') as f:
                        metrics = json.load(f)
                    logger.info(f"Loaded metrics from: {metrics_file}")
                except Exception as e:
                    logger.warning(f"Could not read metrics file: {e}")

        return metrics
