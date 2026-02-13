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
                 deployment_type: Optional[str] = None,
                 memory_mb: Optional[int] = None,
                 max_concurrency: Optional[int] = None,
                 instance_type: Optional[str] = None,
                 min_instances: Optional[int] = None,
                 max_instances: Optional[int] = None,
                 scale_in_cooldown: Optional[int] = None,
                 scale_out_cooldown: Optional[int] = None,
                 target_invocations: Optional[float] = None,
                 pytorch_version: str = '2.3.0',
                 region: Optional[str] = None,
                 force: bool = False):
        """
        Initialize dispatcher.

        Args:
            scorecard_name: Name of the scorecard
            score_name: Name of the score to provision
            yaml: Load from local YAML files instead of API (default: False)
            version: Specific score version ID to provision (optional)
            model_s3_uri: Explicit model S3 URI (optional)
            deployment_type: Deployment type override (None = use YAML config)
            memory_mb: Memory allocation override (None = use YAML config)
            max_concurrency: Max concurrent invocations override (None = use YAML config)
            instance_type: Instance type override (None = use YAML config)
            min_instances: Min instances override (None = use YAML config)
            max_instances: Max instances override (None = use YAML config)
            scale_in_cooldown: Scale-in cooldown override (None = use YAML config)
            scale_out_cooldown: Scale-out cooldown override (None = use YAML config)
            target_invocations: Target invocations override (None = use YAML config)
            pytorch_version: PyTorch version for container
            region: AWS region for infrastructure deployment (None = use default)
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
        self.instance_type = instance_type
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.scale_in_cooldown = scale_in_cooldown
        self.scale_out_cooldown = scale_out_cooldown
        self.target_invocations = target_invocations
        self.pytorch_version = pytorch_version
        self.region = region
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

            # Step 3: Call provision_endpoint_operation directly
            # This handles both LoRA classifiers (shared stack) and legacy classifiers (per-score stack)
            from plexus.cli.provisioning.operations import provision_endpoint_operation

            logger.info(f"Provisioning endpoint for {score_class.__name__}...")
            result = provision_endpoint_operation(
                scorecard_name=self.scorecard_name,
                score_name=self.score_name,
                use_yaml=self.yaml,
                score_version_id=self.version,
                model_s3_uri=self.model_s3_uri,
                deployment_type=self.deployment_type,
                memory_mb=self.memory_mb,
                max_concurrency=self.max_concurrency,
                instance_type=self.instance_type,
                min_instances=self.min_instances,
                max_instances=self.max_instances,
                scale_in_cooldown=self.scale_in_cooldown,
                scale_out_cooldown=self.scale_out_cooldown,
                target_invocations=self.target_invocations,
                pytorch_version=self.pytorch_version,
                region=self.region,
                force=self.force
            )

            if not result['success']:
                return ProvisioningResult(
                    success=False,
                    error=result.get('error', 'Unknown provisioning error')
                )

            endpoint_name = result.get('endpoint_name')
            if not endpoint_name:
                return ProvisioningResult(
                    success=True,
                    message=result.get('message', 'Provisioning completed with no endpoint changes')
                )

            # Step 5: Test the endpoint (only if score class supports test_endpoint)
            test_result = None
            if hasattr(score_class, 'test_endpoint'):
                try:
                    # Create a minimal score instance for testing
                    # We need the score config to determine endpoint names
                    score_instance = score_class()

                    # Inject the score config as a simple namespace object for endpoint naming
                    class SimpleNamespace:
                        def __init__(self, **kwargs):
                            self.__dict__.update(kwargs)

                    # CRITICAL: Inject scorecard_name for LoRA classifier endpoint naming
                    # LoRA classifiers need both scorecard_name and score name to compute adapter component names
                    # IMPORTANT: Use the ACTUAL names from the GraphQL API (returned by provisioning)
                    # NOT the CLI argument (which might be an identifier, not the canonical name)
                    actual_scorecard_name = result.get('actual_scorecard_name', self.scorecard_name)
                    actual_score_name = result.get('actual_score_name', self.score_name)

                    test_config = dict(self.score_config)
                    test_config['scorecard_name'] = actual_scorecard_name
                    test_config['name'] = actual_score_name

                    score_instance.parameters = SimpleNamespace(**test_config)

                    logger.info(f"Testing endpoint '{endpoint_name}'...")
                    test_result = score_instance.test_endpoint(endpoint_name=endpoint_name)
                except Exception as e:
                    logger.warning(f"Endpoint test failed (non-fatal): {e}")
                    test_result = {'warning': f'Test skipped: {str(e)}'}
            else:
                logger.info(f"Score class {score_class.__name__} does not implement test_endpoint(), skipping test")

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

        # Find score config by ANY identifier (name, key, id, externalId, originalExternalId)
        def matches_identifier(config: dict, identifier: str) -> bool:
            if not identifier:
                return False
            identifier_str = str(identifier)
            return (
                config.get('name') == identifier or
                config.get('key') == identifier or
                str(config.get('id', '')) == identifier_str or
                config.get('externalId') == identifier or
                config.get('originalExternalId') == identifier
            )

        for score_config in self.scorecard_class.scores:
            if isinstance(score_config, dict) and matches_identifier(score_config, self.score_name):
                self.score_config = score_config
                break

        if not self.score_config:
            raise ValueError(f"Score '{self.score_name}' not found in scorecard")

        # Normalize to canonical score name for registry lookups
        canonical_name = self.score_config.get('name')
        if canonical_name and canonical_name != self.score_name:
            logger.info(f"Resolved score identifier '{self.score_name}' to score name '{canonical_name}'")
            self.score_name = canonical_name

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
