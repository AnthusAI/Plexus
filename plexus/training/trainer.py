"""
Base Trainer abstraction for unified training workflows.

This module defines the abstract Trainer interface that all training implementations
must follow. The Trainer uses the Template Method pattern - the execute() method
defines the workflow, and subclasses implement specific steps.
"""

import logging
import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    """
    Result of a training operation.

    Attributes:
        success: Whether training completed successfully
        training_type: Type of training performed ('ml', 'llm-finetune', etc.)
        target: Target platform ('local', 'sagemaker', etc.) or None
        metrics: Dictionary of training metrics (accuracy, loss, etc.)
        artifacts: Dictionary mapping artifact types to their locations
        error: Error message if training failed
        metadata: Additional metadata about the training run
    """
    success: bool
    training_type: str
    target: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Trainer(ABC):
    """
    Abstract base class for all trainers.

    Defines the common workflow for training operations using the Template Method
    pattern. The execute() method orchestrates the training workflow by calling
    abstract methods that subclasses must implement.

    Workflow:
        1. Validate prerequisites and configuration
        2. Create Score instance
        3. Prepare training data
        4. Execute training
        5. Save artifacts (models, files, etc.)
        6. Collect metrics
        7. Return TrainingResult

    Subclasses must implement:
        - validate(): Check prerequisites (credentials, dependencies, etc.)
        - prepare_data(): Load and prepare training data
        - train(): Execute the actual training
        - save_artifacts(): Save outputs and return their locations
        - get_metrics(): Return training metrics
        - get_training_type(): Return training type identifier
        - get_target(): Return target platform or None
    """

    def __init__(self, scorecard_class, score_config: dict,
                 fresh: bool = False, **kwargs):
        """
        Initialize trainer.

        Args:
            scorecard_class: The scorecard class containing the score
            score_config: Score configuration dictionary from YAML
            fresh: Whether to pull fresh data (bypass cache)
            **kwargs: Additional parameters specific to trainer type
        """
        self.scorecard_class = scorecard_class
        self.score_config = score_config
        self.fresh = fresh
        self.extra_params = kwargs
        self.score_instance = None

    def execute(self) -> TrainingResult:
        """
        Execute the complete training workflow.

        This is the Template Method that defines the training workflow.
        It calls abstract methods in sequence and handles errors.

        Returns:
            TrainingResult with success status, metrics, and artifacts
        """
        try:
            logger.info(f"Starting training for score '{self.score_config.get('name', 'Unknown')}'")
            logger.info(f"Training type: {self.get_training_type()}")
            if self.get_target():
                logger.info(f"Target: {self.get_target()}")

            # Step 1: Validate prerequisites
            logger.info("Validating prerequisites...")
            self.validate()

            # Step 2: Instantiate Score
            logger.info("Creating Score instance...")
            self.score_instance = self._create_score_instance()

            # Step 3: Prepare data
            logger.info("Preparing training data...")
            self.prepare_data()

            # Step 4: Train
            logger.info("Training...")
            self.train()

            # Step 5: Save artifacts
            logger.info("Saving artifacts...")
            artifacts = self.save_artifacts()

            # Step 6: Collect metrics
            logger.info("Collecting metrics...")
            metrics = self.get_metrics()

            logger.info(f"Training completed successfully for '{self.score_config.get('name')}'")

            return TrainingResult(
                success=True,
                training_type=self.get_training_type(),
                target=self.get_target(),
                metrics=metrics,
                artifacts=artifacts,
                metadata={
                    'scorecard_name': self.scorecard_class.name,
                    'score_name': self.score_config.get('name'),
                    'fresh': self.fresh
                }
            )

        except Exception as e:
            logger.error(f"Training failed for '{self.score_config.get('name')}': {str(e)}", exc_info=True)
            return TrainingResult(
                success=False,
                training_type=self.get_training_type(),
                target=self.get_target(),
                metrics={},
                artifacts={},
                error=str(e),
                metadata={
                    'scorecard_name': self.scorecard_class.name,
                    'score_name': self.score_config.get('name'),
                    'fresh': self.fresh
                }
            )

    def _create_score_instance(self):
        """
        Create an instance of the Score class from configuration.

        This mirrors the logic in plexus/cli/training/operations.py:train_score()
        to maintain compatibility with existing Score classes.

        Returns:
            Instantiated Score object
        """
        score_class_name = self.score_config['class']
        score_module_path = f'plexus.scores.{score_class_name}'

        try:
            score_module = importlib.import_module(score_module_path)
            score_class = getattr(score_module, score_class_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(
                f"Could not import Score class '{score_class_name}' from '{score_module_path}': {e}"
            )

        if not isinstance(score_class, type):
            raise ValueError(f"{score_class_name} is not a class")

        # Add scorecard and score names to configuration
        # (required by many Score classes)
        config_with_names = self.score_config.copy()
        config_with_names['scorecard_name'] = self.scorecard_class.name
        config_with_names['score_name'] = self.score_config.get('name', score_class_name)

        # Instantiate the Score
        score_instance = score_class(**config_with_names)

        return score_instance

    @abstractmethod
    def validate(self):
        """
        Validate prerequisites and configuration.

        Should raise an exception if prerequisites are not met
        (e.g., missing credentials, unavailable dependencies, invalid config).

        Raises:
            ValueError: If configuration is invalid
            RuntimeError: If prerequisites are not met
        """
        pass

    @abstractmethod
    def prepare_data(self):
        """
        Load and prepare training data.

        Typically calls Score.load_data() and Score.process_data() or equivalent.
        Should store prepared data in instance variables for use by train().
        """
        pass

    @abstractmethod
    def train(self):
        """
        Execute the actual training.

        This is where the core training logic happens - calling Score.train_model(),
        generating JSON-L files, launching SageMaker jobs, etc.
        """
        pass

    @abstractmethod
    def save_artifacts(self) -> Dict[str, str]:
        """
        Save training artifacts and return their locations.

        Returns:
            Dictionary mapping artifact types to their locations:
            - 'model_directory': Local model directory path
            - 'model_s3_path': S3 path to model artifacts
            - 'training_file': Path to training.jsonl
            - 'validation_file': Path to validation.jsonl
            - etc.
        """
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """
        Return training metrics.

        Returns:
            Dictionary of metrics:
            - 'accuracy': Training accuracy
            - 'loss': Training loss
            - 'validation_accuracy': Validation accuracy
            - 'training_examples': Number of training examples
            - etc.
        """
        pass

    @abstractmethod
    def get_training_type(self) -> str:
        """
        Return the training type identifier.

        Returns:
            Training type: 'ml', 'llm-finetune', etc.
        """
        pass

    @abstractmethod
    def get_target(self) -> Optional[str]:
        """
        Return the target platform.

        Returns:
            Target: 'local', 'sagemaker', etc., or None if not applicable
        """
        pass
