"""
Stack for SageMaker Shared Real-Time Inference endpoints with LoRA adapters.

This stack provisions ONE SageMaker endpoint per base model with MULTIPLE adapter
components (one per score). All scores using the same base model share GPU resources.

Key differences from SageMakerInferenceStack:
- One stack per base model (not per score)
- Dynamically creates multiple adapter components from a list
- Uses base model naming (not scorecard/score naming)
- Discovery-driven: synthesized from all scores using the same base model class
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
from typing import List, Dict, Any, Optional
import hashlib
import os
from .shared.naming import (
    get_base_model_key,
    get_base_endpoint_name,
    get_adapter_component_name,
)


class SageMakerSharedInferenceStack(Stack):
    """
    CDK Stack for SageMaker Shared Real-Time Inference endpoints with multiple LoRA adapters.

    This stack provisions ONE endpoint per base model with MULTIPLE adapter components.
    All scores using the same base model share the same GPU instance, reducing costs by 67%.

    Architecture:
    - One endpoint per base model (e.g., one for all Llama-3.1-8B scores)
    - One base inference component (foundation model)
    - Multiple adapter inference components (one per score, all sharing the base)
    - Managed instance scaling with scale-to-zero (0-1 instances)
    - Application Auto Scaling (target tracking + step scaling)

    Key design principles:
    - Single-stack architecture: ONE stack per base model with ALL adapters
    - Discovery-driven: Stack synthesized from all scores using same base model class
    - Automatic deletion: When 0 active scores, stack is deleted (no cleanup command)
    - Convention over configuration: Infrastructure in Python class, not YAML
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        base_config: Dict[str, Any],
        adapter_configs: List[Dict[str, Any]],
        environment: str = 'development',
        **kwargs
    ) -> None:
        """
        Initialize the shared SageMaker inference stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            base_config: Base model configuration dict with keys:
                - base_model_hf_id: HuggingFace model ID (e.g., 'meta-llama/Llama-3.1-8B-Instruct')
                - instance_type: Instance type (e.g., 'ml.g6e.xlarge')
                - min_instances: Minimum instance count (0 for scale-to-zero)
                - max_instances: Maximum instance count (typically 1)
                - scale_in_cooldown: Scale-in cooldown in seconds (default: 300)
                - scale_out_cooldown: Scale-out cooldown in seconds (default: 60)
                - target_invocations_per_instance: Target tracking metric (default: 1.0)
                - container_image: Container image URI
                - hf_token: HuggingFace token (optional, for gated models)
                - environment: Dict of environment variables for vLLM/LoRA config
            adapter_configs: List of adapter configuration dicts, each with keys:
                - scorecard_key: Normalized scorecard key
                - score_key: Normalized score key
                - adapter_s3_uri: S3 URI to LoRA adapter (tar.gz)
            environment: Environment name ('development', 'staging', 'production')
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        # Validate inputs
        if not base_config.get('base_model_hf_id'):
            raise ValueError("base_config must include 'base_model_hf_id'")
        if not base_config.get('instance_type'):
            raise ValueError("base_config must include 'instance_type'")
        if not adapter_configs:
            raise ValueError("adapter_configs must contain at least one adapter configuration")

        # Store parameters
        self.base_model_hf_id = base_config['base_model_hf_id']
        self.instance_type = base_config['instance_type']
        self.min_instances = base_config.get('min_instances', 0)
        self.max_instances = base_config.get('max_instances', 1)
        self.scale_in_cooldown = base_config.get('scale_in_cooldown', 300)
        self.scale_out_cooldown = base_config.get('scale_out_cooldown', 60)
        self.target_invocations = base_config.get('target_invocations_per_instance', 1.0)
        self.container_image = base_config['container_image']
        self.hf_token = base_config.get('hf_token')  # Optional HuggingFace token for gated models
        self.environment_vars = base_config.get('environment', {})
        self.deployment_environment = environment
        self.adapter_configs = adapter_configs

        # Generate base model key and endpoint name
        self.base_model_key = get_base_model_key(self.base_model_hf_id)
        self.endpoint_name = get_base_endpoint_name(self.base_model_key, environment)

        # Add comprehensive tags for resource discovery
        Tags.of(self).add("Service", "sagemaker-shared-inference")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("DeploymentType", "realtime-shared")
        Tags.of(self).add("BaseModelHfId", self.base_model_hf_id)
        Tags.of(self).add("BaseModelKey", self.base_model_key)
        Tags.of(self).add("AdapterCount", str(len(adapter_configs)))

        # Import shared SageMaker inference role from ML Training Stack
        inference_role_arn = Fn.import_value(
            f"plexus-{environment}-sagemaker-inference-role-arn"
        )
        self.sagemaker_role = iam.Role.from_role_arn(
            self, "SharedInferenceRole",
            role_arn=inference_role_arn
        )

        # Create endpoint configuration with managed instance scaling
        self.endpoint_config = self._create_endpoint_config()

        # Create endpoint
        self.endpoint = self._create_endpoint()

        # Create base inference component
        self.base_component = self._create_base_component()

        # Create adapter inference components (one per score)
        self.adapter_components = self._create_adapter_components()

        # NOTE: Stack deletion may fail with "base inference component has associated components" error
        # if adapters aren't deleted first. The custom resource handler should handle this automatically,
        # but if manual cleanup is needed:
        #   aws sagemaker list-inference-components --endpoint-name-equals <endpoint> | jq -r '.InferenceComponents[] | select(.InferenceComponentName | contains("adapter")) | .InferenceComponentName' | xargs -I {} aws sagemaker delete-inference-component --inference-component-name {}

        # Setup auto-scaling for scale-to-zero
        self._setup_autoscaling()

        # Outputs
        CfnOutput(
            self, "EndpointName",
            value=self.endpoint_name,
            description="Shared SageMaker endpoint name"
        )
        CfnOutput(
            self, "BaseModelHfId",
            value=self.base_model_hf_id,
            description="HuggingFace base model ID"
        )
        CfnOutput(
            self, "BaseModelKey",
            value=self.base_model_key,
            description="Normalized base model key"
        )
        CfnOutput(
            self, "InstanceType",
            value=self.instance_type,
            description="Instance type for real-time endpoint"
        )
        CfnOutput(
            self, "ScalingConfig",
            value=f"min={self.min_instances}, max={self.max_instances}",
            description="Instance scaling configuration"
        )
        CfnOutput(
            self, "ScaleToZero",
            value="ENABLED" if self.min_instances == 0 else "DISABLED",
            description="Scale-to-zero capability"
        )
        CfnOutput(
            self, "AdapterCount",
            value=str(len(adapter_configs)),
            description="Number of adapter components in this stack"
        )
        CfnOutput(
            self, "EndpointArn",
            value=self.endpoint.ref,
            description="ARN of the SageMaker endpoint"
        )

    def _create_endpoint_config(self) -> sagemaker.CfnEndpointConfig:
        """
        Create endpoint configuration with managed instance scaling.

        This enables scale-to-zero for the shared endpoint.
        Inference components will be added separately after endpoint creation.

        Returns:
            SageMaker Endpoint Configuration
        """
        endpoint_config_name = f"{self.endpoint_name}-config"

        endpoint_config = sagemaker.CfnEndpointConfig(
            self, "EndpointConfig",
            endpoint_config_name=endpoint_config_name,
            execution_role_arn=self.sagemaker_role.role_arn,
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

        endpoint.add_dependency(self.endpoint_config)

        return endpoint

    def _create_base_component(self) -> sagemaker.CfnInferenceComponent:
        """
        Create base inference component for the foundation model.

        This component loads the base model (e.g., Llama-3.1-8B-Instruct) and
        configures vLLM with LoRA support.

        Returns:
            Base inference component
        """
        base_component_name = f"{self.endpoint_name}-base"

        # Build environment variables
        env = {
            "HF_MODEL_ID": self.base_model_hf_id,
        }

        # Add HuggingFace token if provided (needed for gated models like Llama)
        if self.hf_token:
            env["HUGGING_FACE_HUB_TOKEN"] = self.hf_token

        # Merge with additional environment variables from deployment config
        env.update(self.environment_vars)

        base_component = sagemaker.CfnInferenceComponent(
            self,
            "BaseComponent",
            inference_component_name=base_component_name,
            endpoint_name=self.endpoint_name,
            variant_name="AllTraffic",
            specification=sagemaker.CfnInferenceComponent.InferenceComponentSpecificationProperty(
                container=sagemaker.CfnInferenceComponent.InferenceComponentContainerSpecificationProperty(
                    image=self.container_image,
                    environment=env
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
        base_component.add_dependency(self.endpoint)

        return base_component

    def _create_adapter_components(self) -> List[CustomResource]:
        """
        Create adapter inference components (one per score).

        Uses custom resource Lambda to work around CloudFormation handler bug.
        Each adapter shares the base component and GPU resources.

        Returns:
            List of adapter custom resources
        """
        # Create Lambda role for custom resource (shared across all adapters)
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

        # Lambda function (shared across all adapters)
        adapter_lambda = lambda_.Function(
            self,
            "AdapterLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline(handler_code),
            role=adapter_lambda_role,
            timeout=Duration.minutes(10)
        )

        # Custom resource provider (shared across all adapters)
        adapter_provider = cr.Provider(
            self,
            "AdapterProvider",
            on_event_handler=adapter_lambda
        )

        # Create adapter components dynamically (stable ordering + stable logical IDs)
        adapter_components = []
        base_component_name = self.base_component.inference_component_name
        # Deterministic ordering prevents CloudFormation from remapping logical IDs
        sorted_adapters = sorted(
            self.adapter_configs,
            key=lambda c: (c.get('scorecard_key', ''), c.get('score_key', ''))
        )

        for adapter_config in sorted_adapters:
            scorecard_key = adapter_config['scorecard_key']
            score_key = adapter_config['score_key']
            adapter_s3_uri = adapter_config['adapter_s3_uri']
            adapter_s3_hash = hashlib.sha256(adapter_s3_uri.encode()).hexdigest()[:12]
            adapter_update_token = adapter_config.get('adapter_update_token')

            # Generate adapter component name
            adapter_component_name = get_adapter_component_name(
                scorecard_key,
                score_key,
                self.deployment_environment
            )

            # Stable logical ID based on deterministic name hash (prevents duplicate creation)
            adapter_id = f"AdapterComponent{hashlib.sha256(adapter_component_name.encode()).hexdigest()[:8]}"

            # Create custom resource for this adapter
            adapter_component = CustomResource(
                self,
                adapter_id,
                service_token=adapter_provider.service_token,
                properties={
                    "InferenceComponentName": adapter_component_name,
                    "EndpointName": self.endpoint_name,
                    "BaseInferenceComponentName": base_component_name,
                    "ArtifactUrl": adapter_s3_uri,
                    "ArtifactUrlHash": adapter_s3_hash,
                    **({"UpdateToken": adapter_update_token} if adapter_update_token else {})
                }
            )
            # Adapter depends on base for creation
            adapter_component.node.add_dependency(self.base_component)

            adapter_components.append(adapter_component)

            # Output for this adapter
            CfnOutput(
                self, f"{adapter_id}Name",
                value=adapter_component_name,
                description=f"Adapter component for {scorecard_key}/{score_key}"
            )
            CfnOutput(
                self, f"{adapter_id}S3URI",
                value=adapter_s3_uri,
                description=f"S3 URI for {scorecard_key}/{score_key} adapter"
            )

        return adapter_components

    def _setup_autoscaling(self):
        """
        Setup Application Auto Scaling for inference components with scale-to-zero.

        Creates:
        1. Scalable target for base component
        2. Target tracking policy (scales IN to 0 after idle period)
        3. Step scaling policy (scales OUT from 0 on demand)
        4. CloudWatch alarms (trigger scale-out on NoCapacityInvocationFailures)

        All adapter components automatically scale with the base (no separate auto-scaling needed).
        """
        base_component_name = self.base_component.inference_component_name
        sorted_adapters = sorted(
            self.adapter_configs,
            key=lambda c: (c.get('scorecard_key', ''), c.get('score_key', ''))
        )

        # 1. Register scalable target for inference component copies (scale-to-zero)
        scalable_target = appscaling.CfnScalableTarget(
            self, "BaseScalableTarget",
            service_namespace="sagemaker",
            resource_id=f"inference-component/{base_component_name}",
            scalable_dimension="sagemaker:inference-component:DesiredCopyCount",
            min_capacity=0,
            max_capacity=1,
            role_arn=(
                f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/aws-service-role/"
                f"sagemaker.application-autoscaling.amazonaws.com/"
                f"AWSServiceRoleForApplicationAutoScaling_SageMakerEndpoint"
            )
        )
        scalable_target.add_dependency(self.base_component)

        # 2. Target tracking policy (AWS-recommended scale-to-zero)
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

        # 4. CloudWatch alarm for base component (scale out on capacity failures)
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

        # 5. Adapter alarms (trigger component scale-out when adapter has no capacity)
        # These do NOT create per-adapter scaling policies; they only trigger
        # the component step-scaling policy from 0->1.
        for adapter_config in sorted_adapters:
            scorecard_key = adapter_config['scorecard_key']
            score_key = adapter_config['score_key']

            adapter_component_name = get_adapter_component_name(
                scorecard_key,
                score_key,
                self.deployment_environment
            )

            alarm_id = f"AdapterScaleOutAlarm{hashlib.sha256(adapter_component_name.encode()).hexdigest()[:8]}"
            adapter_alarm = cloudwatch.CfnAlarm(
                self, alarm_id,
                alarm_name=f"{adapter_component_name}-scale-out",
                alarm_description="Triggers base scale out from 0 when adapter requests fail due to no capacity",
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
