"""
Provisioning Dispatcher - orchestrates the unified provisioning workflow.

The ProvisioningDispatcher is responsible for:
1. Loading Score configuration
2. Checking if Score supports provisioning (via supports_provisioning())
3. Instantiating the Score
4. Calling score.provision_endpoint()
5. Testing the endpoint via score.test_endpoint()
"""

import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProvisioningResult(BaseModel):
    """Result of a provisioning operation."""
    success: bool
    endpoint_name: Optional[str] = None
    status: Optional[str] = None
    model_s3_uri: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    test_result: Optional[Dict[str, Any]] = None


class ProvisioningDispatcher:
    """
    Orchestrates the provisioning workflow by checking Score support and
    delegating to the Score's provision_endpoint() method.
    """

    def __init__(self,
                 scorecard_name: str,
                 score_name: str,
                 yaml: bool = False,
                 version: Optional[str] = None,
                 model_s3_uri: Optional[str] = None,
                 deployment_type: str = 'serverless',
                 memory_mb: int = 4096,
                 max_concurrency: int = 10,
                 pytorch_version: str = '2.3.0',
                 force: bool = False):
        """
        Initialize dispatcher.

        Args:
            scorecard_name: Name of the scorecard
            score_name: Name of the score to provision
            yaml: Load from local YAML files instead of API (default: False)
            version: Specific score version ID to provision (optional)
            model_s3_uri: Explicit model S3 URI (optional)
            deployment_type: Deployment type ('serverless' or 'realtime')
            memory_mb: Memory allocation in MB
            max_concurrency: Max concurrent invocations
            pytorch_version: PyTorch version for container
            force: Force re-provisioning
        """
        self.scorecard_name = scorecard_name
        self.score_name = score_name
        self.yaml = yaml
        self.version = version
        self.model_s3_uri = model_s3_uri
        self.deployment_type = deployment_type
        self.memory_mb = memory_mb
        self.max_concurrency = max_concurrency
        self.pytorch_version = pytorch_version
        self.force = force

        self.scorecard_class = None
        self.score_config = None

    def dispatch(self) -> ProvisioningResult:
        """
        Execute the complete provisioning dispatch workflow.

        Returns:
            ProvisioningResult with success status and endpoint details
        """
        try:
            # Step 1: Load scorecard and score configuration
            logger.info(f"Loading scorecard '{self.scorecard_name}'...")
            self._load_config()

            # Step 2: Check if Score supports provisioning using supports_provisioning() classmethod
            score_class = self.scorecard_class.score_registry.get(self.score_name)
            if not score_class:
                return ProvisioningResult(
                    success=False,
                    error=f"Score class not found in registry for '{self.score_name}'"
                )

            if hasattr(score_class, 'supports_provisioning'):
                if not score_class.supports_provisioning():
                    logger.info(f"Score '{self.score_name}' does not support provisioning (class: {self.score_config['class']})")
                    return ProvisioningResult(
                        success=True,
                        message=f"Score '{self.score_name}' does not support provisioning",
                    )

            # Step 3: Instantiate the Score
            score_instance = self._instantiate_score(score_class)

            # Step 4: Call score.provision_endpoint()
            logger.info(f"Calling {score_class.__name__}.provision_endpoint()...")
            result = score_instance.provision_endpoint(
                scorecard=self.scorecard_class,
                model_s3_uri=self.model_s3_uri,
                deployment_type=self.deployment_type,
                memory_mb=self.memory_mb,
                max_concurrency=self.max_concurrency,
                pytorch_version=self.pytorch_version,
                force=self.force
            )

            if not result['success']:
                return ProvisioningResult(
                    success=False,
                    error=result.get('error', 'Unknown provisioning error')
                )

            endpoint_name = result['endpoint_name']

            # Step 5: Test the endpoint via score.test_endpoint()
            logger.info(f"Testing endpoint '{endpoint_name}'...")
            test_result = score_instance.test_endpoint(endpoint_name=endpoint_name)

            return ProvisioningResult(
                success=True,
                endpoint_name=endpoint_name,
                status=result.get('status'),
                model_s3_uri=result.get('model_s3_uri'),
                message=result.get('message'),
                test_result=test_result
            )

        except Exception as e:
            logger.error(f"Provisioning dispatch failed: {e}", exc_info=True)
            return ProvisioningResult(
                success=False,
                error=str(e)
            )

    def _load_config(self):
        """Load scorecard and score configuration."""
        if self.yaml:
            from plexus.cli.evaluation.evaluations import load_scorecard_from_yaml_files
            self.scorecard_class = load_scorecard_from_yaml_files(
                scorecard_identifier=self.scorecard_name,
                score_names=[self.score_name]
            )
        else:
            from plexus.cli.evaluation.evaluations import load_scorecard_from_api
            self.scorecard_class = load_scorecard_from_api(
                scorecard_identifier=self.scorecard_name,
                score_names=[self.score_name]
            )

        # Find score config (should be a dict in scorecard_class.scores)
        for score_config in self.scorecard_class.scores:
            if isinstance(score_config, dict):
                score_name_in_config = score_config.get('name')
                if score_name_in_config == self.score_name:
                    self.score_config = score_config
                    break

        if not self.score_config:
            raise ValueError(f"Score '{self.score_name}' not found in scorecard")

    def _instantiate_score(self, score_class):
        """
        Instantiate a Score from its class and configuration.

        Args:
            score_class: The Score class (e.g., BERTClassifier)

        Returns:
            Initialized Score instance
        """
        # Add scorecard and score names to configuration
        # (following the same pattern as Trainer)
        config_with_names = self.score_config.copy()
        config_with_names['scorecard_name'] = self.scorecard_name
        config_with_names['score_name'] = self.score_config.get('name', self.score_name)

        # Instantiate the Score by passing the entire config as kwargs
        score_instance = score_class(**config_with_names)

        return score_instance
