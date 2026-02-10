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
    Aws,
    Duration,
    CustomResource,
    aws_sagemaker as sagemaker,
    aws_iam as iam,
    aws_applicationautoscaling as appscaling,
    aws_cloudwatch as cloudwatch,
    aws_lambda as lambda_,
    custom_resources as cr,
)
from constructs import Construct
from typing import Optional
import os
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
        # Serverless parameters
        memory_mb: int = 4096,
        max_concurrency: int = 10,
        # Real-time parameters
        instance_type: Optional[str] = None,
        min_instances: int = 0,
        max_instances: int = 1,
        scale_in_cooldown: int = 300,
        scale_out_cooldown: int = 60,
        target_invocations: float = 1.0,
        # Inference components parameters (for LoRA adapters)
        base_model_hf_id: Optional[str] = None,
        adapter_s3_uri: Optional[str] = None,
        container_image: Optional[str] = None,
        hf_token: Optional[str] = None,
        environment_vars: Optional[dict] = None,
        # Shared parameters
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
            instance_type: Instance type for real-time endpoints (e.g., 'ml.g5.xlarge')
            min_instances: Minimum instance count (0 for scale-to-zero)
            max_instances: Maximum instance count
            scale_in_cooldown: Scale-in cooldown period in seconds
            scale_out_cooldown: Scale-out cooldown period in seconds
            target_invocations: Target invocations per instance for target tracking
            base_model_hf_id: HuggingFace model ID for inference components (optional)
            adapter_s3_uri: S3 URI to LoRA adapter for inference components (optional)
            container_image: Custom container image URI (optional)
            hf_token: HuggingFace token (optional)
            environment_vars: Additional environment variables dict (optional)
            pytorch_version: PyTorch inference container version
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        # Validate inputs
        if deployment_type not in ['serverless', 'realtime']:
            raise ValueError(f"deployment_type must be 'serverless' or 'realtime', got: {deployment_type}")

        # Serverless validation
        if deployment_type == 'serverless':
            if not (1024 <= memory_mb <= 6144):
                raise ValueError(f"memory_mb must be between 1024 and 6144, got: {memory_mb}")
            if not (1 <= max_concurrency <= 200):
                raise ValueError(f"max_concurrency must be between 1 and 200, got: {max_concurrency}")

        # Real-time validation
        if deployment_type == 'realtime':
            if not instance_type:
                raise ValueError("instance_type is required for realtime deployments")
            if not (0 <= min_instances <= max_instances):
                raise ValueError(f"Invalid scaling: min_instances={min_instances}, max_instances={max_instances}")
            if min_instances < 0 or max_instances < 1:
                raise ValueError("min_instances >= 0 and max_instances >= 1 required")

        # Store parameters for later use
        self.deployment_type = deployment_type
        self.environment = environment
        self.instance_type = instance_type
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.scale_in_cooldown = scale_in_cooldown
        self.scale_out_cooldown = scale_out_cooldown
        self.target_invocations = target_invocations
        self.base_model_hf_id = base_model_hf_id
        self.adapter_s3_uri = adapter_s3_uri
        self.container_image = container_image
        self.hf_token = hf_token
        self.environment_vars = environment_vars or {}

        # Generate resource names using naming conventions (including environment)
        self.endpoint_name = get_sagemaker_endpoint_name(
            scorecard_key, score_key, deployment_type, environment
        )
        self.model_name = get_sagemaker_model_name(
            scorecard_key, score_key, model_s3_uri, environment
        )
        self.endpoint_config_name = get_sagemaker_endpoint_config_name(
            scorecard_key, score_key, model_s3_uri, environment
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

        # Create Endpoint Configuration
        if deployment_type == 'serverless':
            # Serverless endpoints need a Model resource
            self.model = self._create_model(
                model_s3_uri=model_s3_uri,
                pytorch_version=pytorch_version
            )
            self.endpoint_config = self._create_serverless_endpoint_config(
                memory_mb=memory_mb,
                max_concurrency=max_concurrency
            )
            # Create Endpoint
            self.endpoint = self._create_endpoint()
        else:
            # Real-time endpoints with inference components don't need a Model resource
            # (inference components load models directly from HuggingFace or S3)
            self.model = None
            self.endpoint_config = self._create_realtime_endpoint_config()
            self.endpoint = self._create_endpoint()

            # Create inference components (base + optional adapter)
            self._create_inference_components()

            # Setup auto-scaling for scale-to-zero
            self._setup_autoscaling()

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

        # Additional outputs for real-time endpoints
        if deployment_type == 'realtime':
            CfnOutput(
                self, "InstanceType",
                value=instance_type,
                description="Instance type for real-time endpoint"
            )
            CfnOutput(
                self, "ScalingConfig",
                value=f"min={min_instances}, max={max_instances}",
                description="Instance scaling configuration"
            )
            CfnOutput(
                self, "ScaleToZero",
                value="ENABLED" if min_instances == 0 else "DISABLED",
                description="Scale-to-zero capability"
            )
            if self.base_model_hf_id:
                CfnOutput(
                    self, "BaseModelHFID",
                    value=self.base_model_hf_id,
                    description="HuggingFace base model ID"
                )
            if self.adapter_s3_uri:
                CfnOutput(
                    self, "AdapterS3URI",
                    value=self.adapter_s3_uri,
                    description="S3 URI of LoRA adapter"
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

    def _create_realtime_endpoint_config(self) -> sagemaker.CfnEndpointConfig:
        """
        Create real-time endpoint configuration with managed instance scaling.

        This configuration enables scale-to-zero using managed_instance_scaling.
        Inference components will be added separately after endpoint creation.

        Returns:
            SageMaker Endpoint Configuration with managed instance scaling
        """
        endpoint_config = sagemaker.CfnEndpointConfig(
            self, "EndpointConfig",
            endpoint_config_name=self.endpoint_config_name,
            execution_role_arn=self.sagemaker_role.role_arn,  # Required for inference components
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    variant_name="AllTraffic",
                    instance_type=self.instance_type,
                    initial_instance_count=max(1, self.min_instances),  # Must start with at least 1
                    managed_instance_scaling=sagemaker.CfnEndpointConfig.ManagedInstanceScalingProperty(
                        status="ENABLED",
                        min_instance_count=self.min_instances,
                        max_instance_count=self.max_instances
                    ),
                    routing_config=sagemaker.CfnEndpointConfig.RoutingConfigProperty(
                        routing_strategy="LEAST_OUTSTANDING_REQUESTS"
                    )
                )
            ]
        )

        return endpoint_config

    def _create_inference_components(self):
        """
        Create inference components (base model + optional LoRA adapter).

        This implements the inference components architecture for LoRA fine-tuned models.
        - Base component: Foundation model (e.g., Llama 3.1-8B)
        - Adapter component: LoRA adapter (optional, created via custom resource)
        """
        if not self.base_model_hf_id:
            # No inference components needed (simple model deployment)
            return

        # Generate component names
        base_component_name = f"{self.endpoint_name}-base"

        # Base Inference Component
        self.base_component = sagemaker.CfnInferenceComponent(
            self,
            "BaseComponent",
            inference_component_name=base_component_name,
            endpoint_name=self.endpoint_name,  # Use string name, not CFN reference
            variant_name="AllTraffic",
            specification=sagemaker.CfnInferenceComponent.InferenceComponentSpecificationProperty(
                container=sagemaker.CfnInferenceComponent.InferenceComponentContainerSpecificationProperty(
                    image=self.container_image or self._get_default_container_image(),
                    environment=self._get_base_component_environment()
                ),
                compute_resource_requirements=sagemaker.CfnInferenceComponent.InferenceComponentComputeResourceRequirementsProperty(
                    number_of_cpu_cores_required=2,
                    number_of_accelerator_devices_required=1,
                    min_memory_required_in_mb=4096
                )
            ),
            runtime_config=sagemaker.CfnInferenceComponent.InferenceComponentRuntimeConfigProperty(
                copy_count=1
            )
        )
        self.base_component.add_dependency(self.endpoint)

        # Adapter Inference Component (if adapter S3 URI provided)
        if self.adapter_s3_uri:
            self._create_adapter_component(base_component_name)

    def _create_adapter_component(self, base_component_name: str):
        """
        Create adapter inference component using custom resource Lambda.

        Uses custom resource to work around CloudFormation handler bug that
        reports CREATE_FAILED even when adapter component is created successfully.

        Args:
            base_component_name: Name of the base inference component
        """
        adapter_component_name = f"{self.endpoint_name}-adapter"

        # Lambda role for custom resource
        adapter_lambda_role = iam.Role(
            self,
            "AdapterLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        adapter_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker:CreateInferenceComponent",
                    "sagemaker:DeleteInferenceComponent",
                    "sagemaker:DescribeInferenceComponent",
                    "sagemaker:UpdateInferenceComponent"
                ],
                resources=[f"arn:aws:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:inference-component/*"]
            )
        )

        # Read Lambda handler code
        handler_code_path = os.path.join(os.path.dirname(__file__), "custom_resource_handler.py")
        with open(handler_code_path, 'r') as f:
            handler_code = f.read()

        # Lambda function
        adapter_lambda = lambda_.Function(
            self,
            "AdapterLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline(handler_code),
            role=adapter_lambda_role,
            timeout=Duration.minutes(10)
        )

        # Custom resource provider
        adapter_provider = cr.Provider(
            self,
            "AdapterProvider",
            on_event_handler=adapter_lambda
        )

        # Custom resource to create adapter component
        self.adapter_component = CustomResource(
            self,
            "AdapterComponent",
            service_token=adapter_provider.service_token,
            properties={
                "InferenceComponentName": adapter_component_name,
                "EndpointName": self.endpoint_name,  # Use string name, not CFN reference
                "BaseInferenceComponentName": base_component_name,
                "ArtifactUrl": self.adapter_s3_uri
            }
        )
        self.adapter_component.node.add_dependency(self.base_component)

    def _get_default_container_image(self) -> str:
        """Get default container image for inference components."""
        # DJL LMI container with vLLM support
        return f"763104351884.dkr.ecr.{self.region}.amazonaws.com/djl-inference:0.31.0-lmi13.0.0-cu124"

    def _get_base_component_environment(self) -> dict:
        """Build environment variables for base inference component."""
        env = {
            "HF_MODEL_ID": self.base_model_hf_id,
            "OPTION_ROLLING_BATCH": "vllm",
            "OPTION_ENABLE_LORA": "true",
            "OPTION_MAX_LORAS": "10",
            "OPTION_MAX_LORA_RANK": "64",
            "OPTION_MAX_MODEL_LEN": "4096",
            "OPTION_GPU_MEMORY_UTILIZATION": "0.8"
        }

        # Add HuggingFace token if provided
        if self.hf_token:
            env["HUGGING_FACE_HUB_TOKEN"] = self.hf_token

        # Merge with additional environment variables
        env.update(self.environment_vars)

        return env

    def _setup_autoscaling(self):
        """
        Setup Application Auto Scaling for inference components with scale-to-zero.

        Creates:
        1. Scalable target for base component
        2. Target tracking policy (scales IN to 0 after idle period)
        3. Step scaling policy (scales OUT from 0 on demand)
        4. CloudWatch alarms (trigger scale-out on NoCapacityInvocationFailures)

        The adapter component automatically scales with the base (no separate auto-scaling needed).
        """
        if not self.base_component:
            # No inference components, no auto-scaling needed
            return

        base_component_name = self.base_component.inference_component_name

        # 1. Register scalable target
        scalable_target = appscaling.CfnScalableTarget(
            self, "BaseScalableTarget",
            service_namespace="sagemaker",
            resource_id=f"inference-component/{base_component_name}",
            scalable_dimension="sagemaker:inference-component:DesiredCopyCount",
            min_capacity=0,  # Can scale to 0
            max_capacity=1,  # Can scale to 1
            role_arn=(
                f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/aws-service-role/"
                f"sagemaker.application-autoscaling.amazonaws.com/"
                f"AWSServiceRoleForApplicationAutoScaling_SageMakerEndpoint"
            )
        )
        scalable_target.add_dependency(self.base_component)

        # 2. Target tracking policy (scales IN to 0 after idle period)
        target_tracking = appscaling.CfnScalingPolicy(
            self, "TargetTrackingPolicy",
            policy_name=f"{base_component_name}-target-tracking",
            policy_type="TargetTrackingScaling",
            service_namespace="sagemaker",
            resource_id=f"inference-component/{base_component_name}",
            scalable_dimension="sagemaker:inference-component:DesiredCopyCount",
            target_tracking_scaling_policy_configuration=(
                appscaling.CfnScalingPolicy.TargetTrackingScalingPolicyConfigurationProperty(
                    target_value=self.target_invocations,
                    predefined_metric_specification=(
                        appscaling.CfnScalingPolicy.PredefinedMetricSpecificationProperty(
                            predefined_metric_type="SageMakerInferenceComponentInvocationsPerCopy"
                        )
                    ),
                    scale_in_cooldown=self.scale_in_cooldown,
                    scale_out_cooldown=self.scale_out_cooldown
                )
            )
        )
        target_tracking.add_dependency(scalable_target)

        # 3. Step scaling policy (scales OUT from 0 when capacity failures occur)
        step_scaling = appscaling.CfnScalingPolicy(
            self, "StepScalingPolicy",
            policy_name=f"{base_component_name}-step-scaling",
            policy_type="StepScaling",
            service_namespace="sagemaker",
            resource_id=f"inference-component/{base_component_name}",
            scalable_dimension="sagemaker:inference-component:DesiredCopyCount",
            step_scaling_policy_configuration=(
                appscaling.CfnScalingPolicy.StepScalingPolicyConfigurationProperty(
                    adjustment_type="ExactCapacity",
                    metric_aggregation_type="Maximum",
                    step_adjustments=[
                        appscaling.CfnScalingPolicy.StepAdjustmentProperty(
                            scaling_adjustment=1,
                            metric_interval_lower_bound=0
                        )
                    ]
                )
            )
        )
        step_scaling.add_dependency(scalable_target)

        # 4. CloudWatch alarms for base component
        base_alarm = cloudwatch.CfnAlarm(
            self, "BaseScaleOutAlarm",
            alarm_name=f"{base_component_name}-scale-out",
            alarm_description="Triggers scale out from 0 when base component requests fail due to no capacity",
            comparison_operator="GreaterThanOrEqualToThreshold",
            evaluation_periods=1,
            metric_name="NoCapacityInvocationFailures",
            namespace="AWS/SageMaker",
            period=60,
            statistic="Sum",
            threshold=1,
            treat_missing_data="notBreaching",
            dimensions=[
                cloudwatch.CfnAlarm.DimensionProperty(
                    name="InferenceComponentName",
                    value=base_component_name
                )
            ],
            alarm_actions=[step_scaling.attr_arn]
        )
        base_alarm.add_dependency(step_scaling)

        # 5. CloudWatch alarm for adapter component (if exists)
        if hasattr(self, 'adapter_component'):
            adapter_component_name = f"{self.endpoint_name}-adapter"
            adapter_alarm = cloudwatch.CfnAlarm(
                self, "AdapterScaleOutAlarm",
                alarm_name=f"{adapter_component_name}-scale-out",
                alarm_description="Triggers scale out from 0 when adapter component requests fail due to no capacity",
                comparison_operator="GreaterThanOrEqualToThreshold",
                evaluation_periods=1,
                metric_name="NoCapacityInvocationFailures",
                namespace="AWS/SageMaker",
                period=60,
                statistic="Sum",
                threshold=1,
                treat_missing_data="notBreaching",
                dimensions=[
                    cloudwatch.CfnAlarm.DimensionProperty(
                        name="InferenceComponentName",
                        value=adapter_component_name
                    )
                ],
                alarm_actions=[step_scaling.attr_arn]
            )
            adapter_alarm.add_dependency(step_scaling)
