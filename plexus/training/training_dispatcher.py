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

from plexus.training.trainer import TrainingResult
from plexus.training.ml_trainer_local import MLTrainerLocal
from plexus.training.ml_trainer_sagemaker import MLTrainerSageMaker
from plexus.training.llm_finetune_trainer import LLMFineTuneTrainer
from plexus.training.lora_finetune_trainer import LoraFineTuneTrainer
from plexus.training.lora_trainer_sagemaker import LoraFineTuneTrainerSageMaker

logger = logging.getLogger(__name__)


class TrainingDispatcher:
    """
    Orchestrates the training workflow by determining training type and
    delegating to the appropriate Trainer implementation.
    """

    # Map of training types to Trainer classes
    TRAINER_MAP = {
        ('ml', 'local'): MLTrainerLocal,
        ('ml', 'sagemaker'): MLTrainerSageMaker,
        ('llm-finetune', None): LLMFineTuneTrainer,
        ('lora', 'local'): LoraFineTuneTrainer,
        ('lora', 'sagemaker'): LoraFineTuneTrainerSageMaker,
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

    # Score classes that support LoRA fine-tuning
    LORA_SCORE_CLASSES = [
        'LoRAClassifier',
        'Llama318BInstructClassifier',
    ]

    def __init__(self,
                 scorecard_name: str,
                 score_name: str,
                 yaml: bool = False,
                 specific_version: Optional[str] = None,
                 training_type_override: Optional[str] = None,
                 platform_override: Optional[str] = None,
                 fresh: bool = False,
                 **kwargs):
        """
        Initialize dispatcher.

        Args:
            scorecard_name: Name of the scorecard
            score_name: Name of the score to train
            yaml: Load from local YAML files instead of API (default: False)
            specific_version: Train a specific version (by version ID) instead of champion
            training_type_override: Override training type ('ml' | 'llm-finetune')
            platform_override: Override platform ('local' | 'sagemaker')
            fresh: Pull fresh data from data lake
            **kwargs: Additional parameters for specific trainers
        """
        self.scorecard_name = scorecard_name
        self.score_name = score_name
        self.yaml = yaml
        self.specific_version = specific_version
        self.training_type_override = training_type_override
        self.platform_override = platform_override
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

            # Step 1.5: Override data configuration if data source provided via CLI
            if 'data_source_identifier' in self.extra_params:
                self._override_data_config(self.extra_params['data_source_identifier'])

            # Step 2: Check if Score supports training using supports_training() classmethod
            score_class = self.scorecard_class.score_registry.get(self.score_name)
            if score_class and hasattr(score_class, 'supports_training'):
                if not score_class.supports_training():
                    logger.info(f"Score '{self.score_name}' does not support training (class: {self.score_config['class']})")
                    return TrainingResult(
                        success=True,
                        training_type='none',
                        metadata={
                            'message': f"Score '{self.score_name}' does not support training",
                            'score_class': self.score_config['class'],
                            'reason': 'train_model() not overridden - would raise TrainingNotSupportedException'
                        }
                    )

            # Step 3: Determine training type
            training_type = self._determine_training_type()
            logger.info(f"Training type: {training_type}")

            # Step 4: Determine platform (for ML training)
            platform = self._determine_platform(training_type)
            if platform:
                logger.info(f"Training platform: {platform}")

            # Step 5: Validate flag compatibility
            self._validate_flags(training_type)

            # Step 6: Instantiate appropriate trainer
            trainer = self._create_trainer(training_type, platform)

            # Step 7: Execute training
            logger.info(f"Starting training for score '{self.score_name}'...")
            result = trainer.execute()

            return result

        except Exception as e:
            logger.error(f"Training dispatch failed: {e}", exc_info=True)
            return TrainingResult(
                success=False,
                training_type=self.training_type_override or 'unknown',
                platform=self.platform_override,
                error=str(e)
            )

    def _load_config(self):
        """
        Load scorecard and score configuration from API or YAML files.

        Raises:
            ValueError: If scorecard or score not found
        """
        if self.yaml:
            # Load from local YAML files
            if self.specific_version:
                logger.warning("--version parameter ignored when using --yaml (YAML files represent champion versions)")
            logger.info(f"Loading scorecard '{self.scorecard_name}' from local YAML files")
            self._load_from_yaml()
        else:
            # Load from API (default)
            logger.info(f"Loading scorecard '{self.scorecard_name}' from API")
            self._load_from_api()

    def _load_from_yaml(self):
        """
        Load scorecard and score configuration from local YAML files.

        Uses the same loading mechanism as evaluate accuracy for consistency.

        Raises:
            ValueError: If scorecard or score not found
        """
        from plexus.cli.evaluation.evaluations import load_scorecard_from_yaml_files

        try:
            # Load scorecard from YAML files (loads specific score by name)
            self.scorecard_class = load_scorecard_from_yaml_files(
                scorecard_identifier=self.scorecard_name,
                score_names=[self.score_name] if self.score_name else None
            )

            logger.info(f"Found scorecard: {self.scorecard_name}")

            # Get score configuration from the loaded scorecard
            # The scorecard.scores should be a list of score configs
            if not hasattr(self.scorecard_class, 'scores') or not self.scorecard_class.scores:
                raise ValueError(f"No scores found in scorecard '{self.scorecard_name}'")

            # Find the requested score in the loaded configs
            self.score_config = None
            for score in self.scorecard_class.scores:
                if isinstance(score, dict):
                    score_name = score.get('name')
                    if score_name == self.score_name:
                        self.score_config = score
                        break

            if not self.score_config:
                available = ', '.join([s.get('name', 'Unknown') for s in self.scorecard_class.scores if isinstance(s, dict)])
                raise ValueError(
                    f"Score '{self.score_name}' not found in scorecard loaded from YAML. "
                    f"Available scores: {available}"
                )

            # Add name to config if not present (some Score classes expect it)
            if 'name' not in self.score_config:
                self.score_config['name'] = self.score_name

            logger.info(f"Found score: {self.score_name} (class: {self.score_config.get('class')})")

        except Exception as e:
            error_msg = f"Failed to load scorecard from YAML files: {str(e)}"
            logger.error(error_msg)
            hint = "\nMake sure individual score YAML files exist in scorecards/{scorecard_name}/ directory."
            hint += "\nYou may need to run fetch_score_configurations first."
            raise ValueError(f"{error_msg}{hint}") from e

    def _override_data_config(self, data_source_identifier: str):
        """
        Override the score's data configuration with a DatasetCache using the provided data source.

        Args:
            data_source_identifier: Data source ID, key, or name (DatasetResolver will try all)
        """
        logger.info(f"Overriding data configuration with data source: {data_source_identifier}")

        # Replace the data config with DatasetCache pointing to the data source
        # DatasetResolver will try the identifier as ID, key, then name
        self.score_config['data'] = {
            'class': 'DatasetCache',
            'source': data_source_identifier
        }

        logger.info(f"Data configuration overridden: {self.score_config['data']}")

    def _load_from_api(self):
        """
        Load scorecard and score configuration from API.

        Uses the same loading mechanism as evaluate accuracy for consistency.

        Raises:
            ValueError: If scorecard or score not found in API
        """
        from plexus.cli.evaluation.evaluations import load_scorecard_from_api

        try:
            # Load scorecard from API (loads specific score by name)
            if self.specific_version:
                logger.info(f"Loading specific version: {self.specific_version}")

            self.scorecard_class = load_scorecard_from_api(
                scorecard_identifier=self.scorecard_name,
                score_names=[self.score_name] if self.score_name else None,
                specific_version=self.specific_version  # Use specific version if provided, else champion
            )

            logger.info(f"Loaded scorecard '{self.scorecard_name}' from API with {len(self.scorecard_class.scores)} score(s)")

            # Find the score configuration
            if isinstance(self.scorecard_class.scores, dict):
                if self.score_name not in self.scorecard_class.scores:
                    available = ', '.join(self.scorecard_class.scores.keys())
                    raise ValueError(
                        f"Score '{self.score_name}' not found in scorecard loaded from API. "
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
                        f"Score '{self.score_name}' not found in scorecard loaded from API. "
                        f"Available scores: {available}"
                    )

            # Add name to config if not present (some Score classes expect it)
            if 'name' not in self.score_config:
                self.score_config['name'] = self.score_name

            logger.info(f"Found score: {self.score_name} (class: {self.score_config.get('class')})")

        except Exception as e:
            error_msg = f"Failed to load scorecard from API: {str(e)}"
            logger.error(error_msg)
            hint = "\nTry using the --yaml flag to load from local YAML files instead."
            raise ValueError(f"{error_msg}{hint}") from e

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

        if score_class_name in self.LORA_SCORE_CLASSES:
            logger.info(f"Inferred training type 'lora' from Score class '{score_class_name}'")
            return 'lora'

        # Fallback: detect LoRAClassifier subclass
        try:
            score_class = self.scorecard_class.score_registry.get(self.score_name)
            if score_class:
                from plexus.scores.LoRAClassifier import LoRAClassifier
                if issubclass(score_class, LoRAClassifier):
                    logger.info(f"Inferred training type 'lora' from LoRAClassifier subclass '{score_class.__name__}'")
                    return 'lora'
        except Exception:
            pass

        # Cannot infer
        raise ValueError(
            f"Cannot infer training type for Score class '{score_class_name}'. "
            f"Please specify --training-type flag or add 'training.type' to Score YAML. "
            f"Supported types: ml, llm-finetune, lora"
        )

    def _determine_platform(self, training_type: str) -> Optional[str]:
        """
        Determine training platform for ML training.

        For ML training, determines whether to train locally or on SageMaker.
        For LLM fine-tuning, returns None (not applicable).

        Args:
            training_type: The determined training type

        Returns:
            Platform: 'local', 'sagemaker', or None

        Raises:
            ValueError: If platform cannot be determined for ML training
        """
        if training_type != 'ml':
            if training_type == 'lora':
                if self.platform_override:
                    return self.platform_override
                platform = self.score_config.get('training', {}).get('platform')
                if platform in ['local', 'sagemaker']:
                    return platform
                return 'sagemaker'
            return None  # Platform not applicable for non-ML training

        # Priority 1: CLI flag override
        if self.platform_override:
            logger.info(f"Using platform from CLI flag: {self.platform_override}")
            return self.platform_override

        # Priority 2: Explicit training.platform in YAML configuration
        training_config = self.score_config.get('training', {})
        platform = training_config.get('platform')

        if platform:
            if platform in ['local', 'sagemaker']:
                logger.info(f"Using platform from YAML config: {platform}")
                return platform
            else:
                logger.warning(f"Unknown training.platform '{platform}', defaulting to local")
                return 'local'

        # Default to local training
        # Note: deployment_target is for inference deployment, not training platform
        logger.info("No training platform specified, defaulting to local training")
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

        if training_type in ['ml', 'lora'] and llm_flags_provided:
            raise ValueError(
                f"LLM fine-tuning flags {llm_flags_provided} cannot be used with ML/LoRA training. "
                f"These flags only apply to --training-type llm-finetune"
            )

        if training_type == 'llm-finetune' and ml_flags_provided:
            raise ValueError(
                f"ML training flags {ml_flags_provided} cannot be used with LLM fine-tuning. "
                f"These flags only apply to --training-type ml"
            )

    def _create_trainer(self, training_type: str, platform: Optional[str]):
        """
        Instantiate the appropriate Trainer based on type and platform.

        Args:
            training_type: Training type ('ml' or 'llm-finetune')
            platform: Training platform ('local', 'sagemaker', or None)

        Returns:
            Instantiated Trainer object

        Raises:
            ValueError: If no trainer available for type/platform combination
        """
        # Normalize platform for SageMaker
        if platform and platform.startswith('sagemaker'):
            platform = 'sagemaker'

        # Look up trainer class
        trainer_key = (training_type, platform)

        if trainer_key not in self.TRAINER_MAP:
            raise ValueError(
                f"No trainer available for training_type='{training_type}', platform='{platform}'"
            )

        trainer_class = self.TRAINER_MAP[trainer_key]

        # Instantiate trainer
        trainer = trainer_class(
            scorecard_class=self.scorecard_class,
            scorecard_name=self.scorecard_name,
            score_config=self.score_config,
            fresh=self.fresh,
            use_yaml=self.yaml,  # Pass yaml flag so trainer knows to push versions
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
