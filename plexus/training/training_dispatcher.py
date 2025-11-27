"""
Training Dispatcher - orchestrates the unified training workflow.

The TrainingDispatcher is responsible for:
1. Loading Score configuration
2. Determining training type (from YAML, CLI flags, or class inference)
3. Selecting appropriate Trainer implementation
4. Validating flag compatibility
5. Executing training with error handling
"""

import logging
import importlib
from typing import Optional, Dict, Any

import plexus
import plexus.Scorecard
from plexus.Registries import scorecard_registry
from plexus.training.trainer import TrainingResult
from plexus.training.ml_trainer_local import MLTrainerLocal
from plexus.training.llm_finetune_trainer import LLMFineTuneTrainer

logger = logging.getLogger(__name__)


class TrainingDispatcher:
    """
    Orchestrates the training workflow by determining training type and
    delegating to the appropriate Trainer implementation.
    """

    # Map of training types to Trainer classes
    TRAINER_MAP = {
        ('ml', 'local'): MLTrainerLocal,
        ('llm-finetune', None): LLMFineTuneTrainer,
    }

    # Score classes that support ML training
    ML_SCORE_CLASSES = [
        'BERTClassifier',
        'DeepLearningSemanticClassifier',
        'DeepLearningOneStepSemanticClassifier',
        'DeepLearningSlidingWindowSemanticClassifier',
        'OpenAIEmbeddingsClassifier',
        'FastTextClassifier',
        'SVMClassifier',
        'ExplainableClassifier',
    ]

    # Score classes that support LLM fine-tuning
    LLM_FINETUNE_SCORE_CLASSES = [
        'LangGraphScore',
    ]

    def __init__(self,
                 scorecard_name: str,
                 score_name: str,
                 training_type_override: Optional[str] = None,
                 target_override: Optional[str] = None,
                 fresh: bool = False,
                 **kwargs):
        """
        Initialize dispatcher.

        Args:
            scorecard_name: Name of the scorecard
            score_name: Name of the score to train
            training_type_override: Override training type ('ml' | 'llm-finetune')
            target_override: Override target ('local' | 'sagemaker')
            fresh: Pull fresh data from data lake
            **kwargs: Additional parameters for specific trainers
        """
        self.scorecard_name = scorecard_name
        self.score_name = score_name
        self.training_type_override = training_type_override
        self.target_override = target_override
        self.fresh = fresh
        self.extra_params = kwargs

        self.scorecard_class = None
        self.score_config = None

    def dispatch(self) -> TrainingResult:
        """
        Execute the complete training dispatch workflow.

        Returns:
            TrainingResult with success status, metrics, and artifacts
        """
        try:
            # Step 1: Load scorecard and score configuration
            logger.info(f"Loading scorecard '{self.scorecard_name}'...")
            self._load_config()

            # Step 2: Check if Score supports training using supports_training() classmethod
            score_class = self.scorecard_class.score_registry.get(self.score_name)
            if score_class and hasattr(score_class, 'supports_training'):
                if not score_class.supports_training():
                    logger.info(f"Score '{self.score_name}' does not support training (class: {self.score_config['class']})")
                    return TrainingResult(
                        success=True,
                        training_type='none',
                        target=None,
                        metadata={
                            'message': f"Score '{self.score_name}' does not support training",
                            'score_class': self.score_config['class'],
                            'reason': 'train_model() not overridden - would raise TrainingNotSupportedException'
                        }
                    )

            # Step 3: Determine training type
            training_type = self._determine_training_type()
            logger.info(f"Training type: {training_type}")

            # Step 4: Determine target (for ML training)
            target = self._determine_target(training_type)
            if target:
                logger.info(f"Training target: {target}")

            # Step 5: Validate flag compatibility
            self._validate_flags(training_type)

            # Step 6: Instantiate appropriate trainer
            trainer = self._create_trainer(training_type, target)

            # Step 7: Execute training
            logger.info(f"Starting training for score '{self.score_name}'...")
            result = trainer.execute()

            return result

        except Exception as e:
            logger.error(f"Training dispatch failed: {e}", exc_info=True)
            return TrainingResult(
                success=False,
                training_type=self.training_type_override or 'unknown',
                target=self.target_override,
                error=str(e)
            )

    def _load_config(self):
        """
        Load scorecard and score configuration from YAML files.

        Raises:
            ValueError: If scorecard or score not found
        """
        # Load scorecards from directory
        plexus.Scorecard.Scorecard.load_and_register_scorecards('scorecards/')

        # Get scorecard class
        self.scorecard_class = scorecard_registry.get(self.scorecard_name)
        if not self.scorecard_class:
            raise ValueError(f"Scorecard '{self.scorecard_name}' not found")

        logger.info(f"Found scorecard: {self.scorecard_class.name}")

        # Get score configuration
        # Handle both dict and list formats
        if isinstance(self.scorecard_class.scores, dict):
            if self.score_name not in self.scorecard_class.scores:
                available = ', '.join(self.scorecard_class.scores.keys())
                raise ValueError(
                    f"Score '{self.score_name}' not found in scorecard. "
                    f"Available scores: {available}"
                )
            self.score_config = self.scorecard_class.scores[self.score_name]
        else:
            # List format
            self.score_config = None
            for score in self.scorecard_class.scores:
                if isinstance(score, dict) and score.get('name') == self.score_name:
                    self.score_config = score
                    break

            if not self.score_config:
                available = ', '.join([s.get('name', 'Unknown') for s in self.scorecard_class.scores if isinstance(s, dict)])
                raise ValueError(
                    f"Score '{self.score_name}' not found in scorecard. "
                    f"Available scores: {available}"
                )

        # Add name to config if not present (some Score classes expect it)
        if 'name' not in self.score_config:
            self.score_config['name'] = self.score_name

        logger.info(f"Found score: {self.score_name} (class: {self.score_config.get('class')})")

    def _determine_training_type(self) -> str:
        """
        Determine training type using priority hierarchy:
        1. CLI flag (--training-type)
        2. Explicit YAML config (training.type)
        3. Inferred from Score class name

        Returns:
            Training type: 'ml' or 'llm-finetune'

        Raises:
            ValueError: If training type cannot be determined
        """
        # Priority 1: CLI flag override
        if self.training_type_override:
            logger.info(f"Using training type from CLI flag: {self.training_type_override}")
            return self.training_type_override

        # Priority 2: Explicit YAML configuration
        training_config = self.score_config.get('training', {})
        if 'type' in training_config:
            training_type = training_config['type']
            logger.info(f"Using training type from YAML config: {training_type}")
            return training_type

        # Priority 3: Infer from Score class name
        score_class_name = self.score_config['class']

        if score_class_name in self.ML_SCORE_CLASSES:
            logger.info(f"Inferred training type 'ml' from Score class '{score_class_name}'")
            return 'ml'

        if score_class_name in self.LLM_FINETUNE_SCORE_CLASSES:
            # Check if graph has completion_template
            if self._has_completion_template():
                logger.info(f"Inferred training type 'llm-finetune' from LangGraphScore with completion_template")
                return 'llm-finetune'

        # Cannot infer
        raise ValueError(
            f"Cannot infer training type for Score class '{score_class_name}'. "
            f"Please specify --training-type flag or add 'training.type' to Score YAML. "
            f"Supported types: ml, llm-finetune"
        )

    def _determine_target(self, training_type: str) -> Optional[str]:
        """
        Determine training target for ML training.

        For ML training, determines whether to train locally or on SageMaker.
        For LLM fine-tuning, returns None (not applicable).

        Args:
            training_type: The determined training type

        Returns:
            Target: 'local', 'sagemaker', or None

        Raises:
            ValueError: If target cannot be determined for ML training
        """
        if training_type != 'ml':
            return None  # Target not applicable for non-ML training

        # Priority 1: CLI flag override
        if self.target_override:
            logger.info(f"Using target from CLI flag: {self.target_override}")
            return self.target_override

        # Priority 2: YAML configuration
        training_config = self.score_config.get('training', {})
        deployment_target = training_config.get('deployment_target')

        if deployment_target:
            # Map deployment_target to training target
            if deployment_target == 'local':
                return 'local'
            elif deployment_target in ['sagemaker_serverless', 'sagemaker_realtime', 'sagemaker']:
                return 'sagemaker'
            else:
                logger.warning(f"Unknown deployment_target '{deployment_target}', defaulting to local")
                return 'local'

        # Default to local training
        logger.info("No target specified, defaulting to local training")
        return 'local'

    def _validate_flags(self, training_type: str):
        """
        Validate that CLI flags are compatible with training type.

        Args:
            training_type: The determined training type

        Raises:
            ValueError: If incompatible flags are provided
        """
        # ML-specific flags
        ml_flags = ['epochs', 'batch_size', 'learning_rate']
        ml_flags_provided = [flag for flag in ml_flags if flag in self.extra_params]

        # LLM fine-tuning flags
        llm_flags = ['maximum_number', 'train_ratio', 'threads', 'clean_existing']
        llm_flags_provided = [flag for flag in llm_flags if flag in self.extra_params]

        if training_type == 'ml' and llm_flags_provided:
            raise ValueError(
                f"LLM fine-tuning flags {llm_flags_provided} cannot be used with ML training. "
                f"These flags only apply to --training-type llm-finetune"
            )

        if training_type == 'llm-finetune' and ml_flags_provided:
            raise ValueError(
                f"ML training flags {ml_flags_provided} cannot be used with LLM fine-tuning. "
                f"These flags only apply to --training-type ml"
            )

    def _create_trainer(self, training_type: str, target: Optional[str]):
        """
        Instantiate the appropriate Trainer based on type and target.

        Args:
            training_type: Training type ('ml' or 'llm-finetune')
            target: Training target ('local', 'sagemaker', or None)

        Returns:
            Instantiated Trainer object

        Raises:
            ValueError: If no trainer available for type/target combination
        """
        # Normalize target for SageMaker
        if target and target.startswith('sagemaker'):
            target = 'sagemaker'

        # Look up trainer class
        trainer_key = (training_type, target)

        if trainer_key not in self.TRAINER_MAP:
            if training_type == 'ml' and target == 'sagemaker':
                # SageMaker trainer not implemented yet
                raise ValueError(
                    f"SageMaker training not yet implemented. "
                    f"Please use --target local or implement MLTrainerSageMaker."
                )
            else:
                raise ValueError(
                    f"No trainer available for training_type='{training_type}', target='{target}'"
                )

        trainer_class = self.TRAINER_MAP[trainer_key]

        # Instantiate trainer
        trainer = trainer_class(
            scorecard_class=self.scorecard_class,
            score_config=self.score_config,
            fresh=self.fresh,
            **self.extra_params
        )

        logger.info(f"Created trainer: {trainer_class.__name__}")
        return trainer

    def _has_completion_template(self) -> bool:
        """
        Check if Score configuration has completion_template in graph.

        Returns:
            True if completion_template found in any graph node
        """
        if 'graph' not in self.score_config:
            return False

        for node in self.score_config['graph']:
            if isinstance(node, dict) and 'completion_template' in node:
                return True

        return False
