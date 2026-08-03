from __future__ import annotations

from collections.abc import Mapping, Sequence

from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Duration,
    SecretValue,
    Stack,
    Tags,
    aws_ecr as ecr,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_s3 as s3,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
    aws_ssm as ssm,
)
from constructs import Construct
from plexus.infrastructure.constructs import AsyncScoreProcessing
from plexus.infrastructure.constructs.async_score_processing import (
    AsyncScoreProcessingProps,
)


class ScoringServiceAsyncScoringStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        environment: str,
        score_processor_repository_name: str,
        score_processor_image_uri: str | None,
        image_source_reference: str,
        runtime_config_secret_name: str,
        alert_topic: sns.ITopic,
        read_bucket_parameters: Mapping[str, str],
        read_write_bucket_parameters: Mapping[str, str],
        bucket_environment_variables: Mapping[str, Sequence[str]],
        secret_environment: Mapping[str, str],
        bedrock_model_resources: Sequence[str],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not resource_prefix.strip():
            raise ValueError("resource_prefix must not be empty")
        if score_processor_image_uri is not None and "@sha256:" not in str(
            score_processor_image_uri
        ):
            raise ValueError(
                "score_processor_image_uri must use an immutable sha256 digest"
            )

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", f"{resource_prefix}-async-scoring")
        Tags.of(self).add("Environment", environment)

        repository = ecr.Repository.from_repository_name(
            self,
            "ScoreProcessorRepository",
            repository_name=score_processor_repository_name,
        )
        image_uri = score_processor_image_uri or CfnParameter(
            self,
            "ScoreProcessorImageUri",
            type="String",
            description="Immutable score processor ECR image URI by sha256 digest",
            allowed_pattern=r"^.+@sha256:[0-9a-f]{64}$",
        ).value_as_string
        runtime_config_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "RuntimeConfigSecret",
            secret_name=runtime_config_secret_name,
        )
        read_buckets = self._resolve_bucket_parameters(read_bucket_parameters)
        read_write_buckets = self._resolve_bucket_parameters(
            read_write_bucket_parameters
        )

        scoring_resource_prefix = f"{resource_prefix}-scoring-{environment}"
        async_score_processing = AsyncScoreProcessing(
            self,
            "AsyncScoreProcessing",
            props=AsyncScoreProcessingProps(
                resource_prefix=scoring_resource_prefix,
                environment_name=environment,
                image_repository=repository,
                image_tag_or_digest="latest",
                runtime_config_secret=runtime_config_secret,
                secret_environment={},
                lambda_timeout=Duration.seconds(300),
                visibility_timeout=Duration.seconds(1800),
                bedrock_model_resources=list(bedrock_model_resources),
            ),
        )

        self.async_score_processing = async_score_processing
        self.function = async_score_processing.function
        self.queues = async_score_processing.queues
        self.log_group = async_score_processing.log_group

        self._grant_s3_access(
            read_buckets=read_buckets,
            read_write_buckets=read_write_buckets,
        )

        alarm_action = cloudwatch_actions.SnsAction(alert_topic)
        for alarm in async_score_processing.dead_letter_queue_alarms:
            alarm.add_alarm_action(alarm_action)

        self._override_lambda_image_uri(image_uri=image_uri)
        self._add_runtime_environment(
            runtime_config_secret_name=runtime_config_secret_name,
            secret_environment=secret_environment,
            buckets=read_buckets | read_write_buckets,
            bucket_environment_variables=bucket_environment_variables,
        )
        self._create_queue_outputs(
            resource_prefix=resource_prefix,
            environment=environment,
        )
        self._create_queue_parameters(
            resource_prefix=resource_prefix,
            environment=environment,
        )
        CfnOutput(
            self,
            "ScoreProcessorFunctionName",
            value=self.function.function_name,
            export_name=f"{resource_prefix}-scoring-{environment}-function-name",
        )
        CfnOutput(
            self,
            "ScoreProcessorImageUriParameterName",
            value=image_source_reference,
        )

    def _override_lambda_image_uri(self, *, image_uri: str) -> None:
        function_resource = self.function.node.default_child
        function_resource.add_property_override("Code.ImageUri", image_uri)

    def _grant_s3_access(
        self,
        *,
        read_buckets: dict[str, str],
        read_write_buckets: dict[str, str],
    ) -> None:
        buckets = read_buckets | read_write_buckets
        for bucket_id, bucket_name in buckets.items():
            bucket = s3.Bucket.from_bucket_name(
                self,
                f"{bucket_id}Bucket",
                bucket_name,
            )
            self.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "s3:GetBucketLocation",
                        "s3:ListBucket",
                        "s3:ListBucketMultipartUploads",
                    ],
                    resources=[bucket.bucket_arn],
                )
            )
            object_actions = ["s3:GetObject", "s3:GetObjectVersion"]
            if bucket_id in read_write_buckets:
                object_actions.extend(
                    [
                        "s3:AbortMultipartUpload",
                        "s3:ListMultipartUploadParts",
                        "s3:PutObject",
                    ]
                )
            self.function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=object_actions,
                    resources=[bucket.arn_for_objects("*")],
                )
            )

    def _resolve_bucket_parameters(
        self,
        bucket_parameters: Mapping[str, str],
    ) -> dict[str, str]:
        return {
            bucket_id: ssm.StringParameter.value_for_string_parameter(
                self,
                parameter_name,
            )
            for bucket_id, parameter_name in bucket_parameters.items()
        }

    def _add_runtime_environment(
        self,
        *,
        runtime_config_secret_name: str,
        secret_environment: Mapping[str, str],
        buckets: Mapping[str, str],
        bucket_environment_variables: Mapping[str, Sequence[str]],
    ) -> None:
        for environment_key, secret_field in secret_environment.items():
            self.function.add_environment(
                environment_key,
                SecretValue.secrets_manager(
                    secret_id=runtime_config_secret_name,
                    json_field=secret_field,
                ).unsafe_unwrap(),
            )
        for bucket_id, environment_keys in bucket_environment_variables.items():
            if bucket_id not in buckets:
                raise ValueError(
                    f"bucket environment binding references unknown bucket: {bucket_id}"
                )
            for environment_key in environment_keys:
                self.function.add_environment(environment_key, buckets[bucket_id])

    def _create_queue_outputs(
        self,
        *,
        resource_prefix: str,
        environment: str,
    ) -> None:
        CfnOutput(
            self,
            "StandardRequestQueueUrl",
            value=self.queues.request_queue.queue_url,
            export_name=(
                f"{resource_prefix}-scoring-{environment}-"
                "standard-request-queue-url"
            ),
        )
        CfnOutput(
            self,
            "ResponseQueueUrl",
            value=self.queues.response_queue.queue_url,
            export_name=(
                f"{resource_prefix}-scoring-{environment}-response-queue-url"
            ),
        )

    def _create_queue_parameters(
        self,
        *,
        resource_prefix: str,
        environment: str,
    ) -> None:
        ssm.StringParameter(
            self,
            "StandardRequestQueueUrlParameter",
            parameter_name=(
                f"/{resource_prefix}/{environment}/async-scoring/"
                "standard-request-queue-url"
            ),
            string_value=self.queues.request_queue.queue_url,
        )
        ssm.StringParameter(
            self,
            "ResponseQueueUrlParameter",
            parameter_name=(
                f"/{resource_prefix}/{environment}/async-scoring/"
                "response-queue-url"
            ),
            string_value=self.queues.response_queue.queue_url,
        )
