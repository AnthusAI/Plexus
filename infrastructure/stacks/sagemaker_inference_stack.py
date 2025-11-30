"""
Stack for SageMaker Serverless Inference endpoints.

This stack provisions SageMaker endpoints for ML model inference using
convention-over-configuration naming for endpoint discovery.
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    Tags,
    Fn,
    aws_sagemaker as sagemaker,
    aws_iam as iam,
)
from constructs import Construct
from .shared.naming import (
    get_sagemaker_endpoint_name,
    get_sagemaker_model_name,
    get_sagemaker_endpoint_config_name,
)


class SageMakerInferenceStack(Stack):
    """
    CDK Stack for SageMaker Serverless Inference endpoints.

    Provisions SageMaker Model, Endpoint Configuration, and Endpoint resources
    following Plexus naming conventions for automatic discovery.

    Key design principles:
    - Endpoint name is stable (doesn't change with model updates)
    - Model and EndpointConfig names are versioned (include hash of model S3 URI)
    - Idempotent deployments (CDK detects changes via hash)
    - No database required for endpoint discovery
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        scorecard_key: str,
        score_key: str,
        model_s3_uri: str,
        environment: str = 'development',
        deployment_type: str = 'serverless',
        memory_mb: int = 4096,
        max_concurrency: int = 10,
        pytorch_version: str = '2.3.0',
        **kwargs
    ) -> None:
        """
        Initialize the SageMaker inference stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            scorecard_key: Normalized scorecard key (filesystem-safe)
            score_key: Normalized score key (filesystem-safe)
            model_s3_uri: S3 URI to model.tar.gz (with inference code) in inference bucket
            environment: Environment name ('development', 'staging', 'production')
            deployment_type: 'serverless' or 'realtime'
            memory_mb: Memory allocation for serverless endpoint (1024-6144)
            max_concurrency: Max concurrent invocations (1-200)
            pytorch_version: PyTorch inference container version
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        # Validate inputs
        if deployment_type not in ['serverless', 'realtime']:
            raise ValueError(f"deployment_type must be 'serverless' or 'realtime', got: {deployment_type}")

        if not (1024 <= memory_mb <= 6144):
            raise ValueError(f"memory_mb must be between 1024 and 6144, got: {memory_mb}")

        if not (1 <= max_concurrency <= 200):
            raise ValueError(f"max_concurrency must be between 1 and 200, got: {max_concurrency}")

        # Generate resource names using naming conventions
        self.endpoint_name = get_sagemaker_endpoint_name(
            scorecard_key, score_key, deployment_type
        )
        self.model_name = get_sagemaker_model_name(
            scorecard_key, score_key, model_s3_uri
        )
        self.endpoint_config_name = get_sagemaker_endpoint_config_name(
            scorecard_key, score_key, model_s3_uri
        )

        # Add tags
        Tags.of(self).add("Service", "sagemaker-inference")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Scorecard", scorecard_key)
        Tags.of(self).add("Score", score_key)
        Tags.of(self).add("DeploymentType", deployment_type)
        Tags.of(self).add("Environment", environment)

        # Import shared SageMaker inference role from ML Training Stack
        inference_role_arn = Fn.import_value(
            f"plexus-{environment}-sagemaker-inference-role-arn"
        )
        self.sagemaker_role = iam.Role.from_role_arn(
            self, "SharedInferenceRole",
            role_arn=inference_role_arn
        )

        # Create SageMaker Model
        self.model = self._create_model(
            model_s3_uri=model_s3_uri,
            pytorch_version=pytorch_version
        )

        # Create Endpoint Configuration
        if deployment_type == 'serverless':
            self.endpoint_config = self._create_serverless_endpoint_config(
                memory_mb=memory_mb,
                max_concurrency=max_concurrency
            )
        else:
            # Realtime endpoints (future enhancement)
            raise NotImplementedError("Realtime endpoints not yet implemented")

        # Create Endpoint
        self.endpoint = self._create_endpoint()

        # Outputs
        CfnOutput(
            self, "EndpointName",
            value=self.endpoint_name,
            description="SageMaker endpoint name (stable, used for discovery)"
        )
        CfnOutput(
            self, "ModelName",
            value=self.model_name,
            description="SageMaker model name (versioned with hash)"
        )
        CfnOutput(
            self, "ModelDataURL",
            value=model_s3_uri,
            description="S3 URI to model.tar.gz"
        )
        CfnOutput(
            self, "EndpointArn",
            value=self.endpoint.ref,
            description="ARN of the SageMaker endpoint"
        )

    def _create_model(
        self,
        model_s3_uri: str,
        pytorch_version: str
    ) -> sagemaker.CfnModel:
        """
        Create SageMaker Model resource.

        Args:
            model_s3_uri: S3 URI to model.tar.gz
            pytorch_version: PyTorch container version

        Returns:
            SageMaker Model
        """
        # Use PyTorch inference container
        # The model package includes a code/ directory with inference.py and requirements.txt
        # SageMaker will automatically install dependencies from code/requirements.txt during startup
        pytorch_image = (
            f"763104351884.dkr.ecr.{self.region}.amazonaws.com/"
            f"pytorch-inference:{pytorch_version}-cpu-py311"
        )

        model = sagemaker.CfnModel(
            self, "Model",
            execution_role_arn=self.sagemaker_role.role_arn,
            primary_container=sagemaker.CfnModel.ContainerDefinitionProperty(
                image=pytorch_image,
                model_data_url=model_s3_uri,
                environment={
                    "SAGEMAKER_PROGRAM": "inference.py",
                    "SAGEMAKER_SUBMIT_DIRECTORY": model_s3_uri,
                    "SAGEMAKER_REGION": self.region,
                    # Allow more time for container startup and model loading
                    # Serverless containers can take time to download and load BERT models
                    "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",  # INFO level logging
                    "SAGEMAKER_MODEL_SERVER_TIMEOUT": "360",  # 6 minutes for model server startup
                }
            ),
            model_name=self.model_name
        )

        # Note: No explicit dependency needed on the shared role since it's
        # imported from the ML Training Stack which is already deployed.
        # The role has been created and fully propagated before we deploy
        # any inference endpoints.

        return model

    def _create_serverless_endpoint_config(
        self,
        memory_mb: int,
        max_concurrency: int
    ) -> sagemaker.CfnEndpointConfig:
        """
        Create serverless endpoint configuration.

        Args:
            memory_mb: Memory allocation (1024-6144 MB)
            max_concurrency: Max concurrent invocations (1-200)

        Returns:
            SageMaker Endpoint Configuration
        """
        endpoint_config = sagemaker.CfnEndpointConfig(
            self, "EndpointConfig",
            endpoint_config_name=self.endpoint_config_name,
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    model_name=self.model.model_name,
                    variant_name="AllTraffic",
                    serverless_config=sagemaker.CfnEndpointConfig.ServerlessConfigProperty(
                        max_concurrency=max_concurrency,
                        memory_size_in_mb=memory_mb
                    )
                )
            ]
        )

        # Ensure model is created before config
        endpoint_config.add_dependency(self.model)

        return endpoint_config

    def _create_endpoint(self) -> sagemaker.CfnEndpoint:
        """
        Create SageMaker Endpoint.

        Returns:
            SageMaker Endpoint
        """
        endpoint = sagemaker.CfnEndpoint(
            self, "Endpoint",
            endpoint_name=self.endpoint_name,
            endpoint_config_name=self.endpoint_config.endpoint_config_name
        )

        # Ensure config is created before endpoint
        endpoint.add_dependency(self.endpoint_config)

        return endpoint
