from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from aws_cdk import Duration, aws_cloudwatch as cloudwatch
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_events
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sqs as sqs
from constructs import Construct


DEFAULT_SECRET_ENVIRONMENT = {
    "PLEXUS_ACCOUNT_KEY": "account-key",
    "PLEXUS_API_KEY": "api-key",
    "PLEXUS_API_URL": "api-url",
    "OPENAI_API_KEY": "openai-api-key",
    "AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME": (
        "score-result-attachments-bucket"
    ),
    "AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME": (
        "report-block-details-bucket"
    ),
}

DEFAULT_STATIC_ENVIRONMENT = {
    "FETCH_SCHEMA_FROM_TRANSPORT": "false",
    "PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT": "0",
    "GQL_FETCH_SCHEMA_FROM_TRANSPORT": "0",
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "MPLBACKEND": "Agg",
    "MPLCONFIGDIR": "/tmp/mpl",
}


@dataclass(frozen=True)
class AsyncScoreProcessingQueues:
    request_queue: sqs.IQueue
    response_queue: sqs.IQueue
    request_dead_letter_queue: sqs.IQueue | None = None
    response_dead_letter_queue: sqs.IQueue | None = None


@dataclass(frozen=True)
class AsyncScoreProcessingProps:
    resource_prefix: str
    environment_name: str
    image_repository: ecr.IRepository
    image_tag_or_digest: str
    runtime_config_secret: secretsmanager.ISecret
    request_queue: sqs.IQueue | None = None
    response_queue: sqs.IQueue | None = None
    secret_environment: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_SECRET_ENVIRONMENT)
    )
    environment_variables: Mapping[str, str] = field(default_factory=dict)
    additional_policy_statements: Sequence[iam.PolicyStatement] = field(
        default_factory=list
    )
    bedrock_model_resources: Sequence[str] = field(default_factory=list)
    visibility_timeout: Duration = Duration.seconds(300)
    retention_period: Duration = Duration.days(14)
    dead_letter_max_receive_count: int = 3
    lambda_timeout: Duration = Duration.seconds(300)
    lambda_memory_size: int = 3008
    reserved_concurrency: int | None = None
    max_event_source_concurrency: int | None = None
    batch_size: int = 1
    enable_dead_letter_queue_alarms: bool = True


class AsyncScoreProcessing(Construct):
    """Reusable async score processing resources for a deployment-owned runtime."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        props: AsyncScoreProcessingProps,
    ) -> None:
        super().__init__(scope, construct_id)

        self.props = props
        self.queues = self._resolve_queues(props)
        self.role = self._create_execution_role(props)
        props.image_repository.grant_pull(self.role)
        props.runtime_config_secret.grant_read(self.role)

        self.function = lambda_.DockerImageFunction(
            self,
            "ScoreProcessorFunction",
            function_name=f"{props.resource_prefix}-score-processor",
            code=lambda_.DockerImageCode.from_ecr(
                repository=props.image_repository,
                tag_or_digest=props.image_tag_or_digest,
            ),
            role=self.role,
            timeout=props.lambda_timeout,
            memory_size=props.lambda_memory_size,
            reserved_concurrent_executions=props.reserved_concurrency,
            environment=self._lambda_environment(props, self.queues),
            description=(
                "Processes async scoring jobs from the standard request queue"
            ),
        )

        self.function.add_event_source(
            lambda_events.SqsEventSource(
                queue=self.queues.request_queue,
                batch_size=props.batch_size,
                max_concurrency=props.max_event_source_concurrency,
            )
        )

        self.dead_letter_queue_alarms = []
        if props.enable_dead_letter_queue_alarms:
            self.dead_letter_queue_alarms = self._create_dead_letter_queue_alarms(
                props, self.queues
            )

    def _resolve_queues(
        self, props: AsyncScoreProcessingProps
    ) -> AsyncScoreProcessingQueues:
        request_dlq = None
        response_dlq = None

        if props.request_queue is None:
            request_dlq = sqs.Queue(
                self,
                "StandardRequestDeadLetterQueue",
                queue_name=f"{props.resource_prefix}-standard-request-dlq",
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                retention_period=props.retention_period,
            )
            request_queue = sqs.Queue(
                self,
                "StandardRequestQueue",
                queue_name=f"{props.resource_prefix}-standard-request-queue",
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                visibility_timeout=props.visibility_timeout,
                retention_period=props.retention_period,
                dead_letter_queue=sqs.DeadLetterQueue(
                    max_receive_count=props.dead_letter_max_receive_count,
                    queue=request_dlq,
                ),
            )
        else:
            request_queue = props.request_queue

        if props.response_queue is None:
            response_dlq = sqs.Queue(
                self,
                "ResponseDeadLetterQueue",
                queue_name=f"{props.resource_prefix}-response-dlq",
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                retention_period=props.retention_period,
            )
            response_queue = sqs.Queue(
                self,
                "ResponseQueue",
                queue_name=f"{props.resource_prefix}-response-queue",
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                visibility_timeout=props.visibility_timeout,
                retention_period=props.retention_period,
                dead_letter_queue=sqs.DeadLetterQueue(
                    max_receive_count=props.dead_letter_max_receive_count,
                    queue=response_dlq,
                ),
            )
        else:
            response_queue = props.response_queue

        return AsyncScoreProcessingQueues(
            request_queue=request_queue,
            response_queue=response_queue,
            request_dead_letter_queue=request_dlq,
            response_dead_letter_queue=response_dlq,
        )

    def _create_execution_role(
        self, props: AsyncScoreProcessingProps
    ) -> iam.Role:
        role = iam.Role(
            self,
            "ScoreProcessorExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "LambdaLogging": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["logs:CreateLogGroup"],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            resources=[
                                (
                                    f"arn:aws:logs:*:*:log-group:/aws/lambda/"
                                    f"{props.resource_prefix}-score-processor:*"
                                )
                            ],
                        ),
                    ]
                )
            },
        )
        self.queues.request_queue.grant_consume_messages(role)
        self.queues.response_queue.grant_send_messages(role)

        if props.bedrock_model_resources:
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    resources=list(props.bedrock_model_resources),
                )
            )

        for statement in props.additional_policy_statements:
            role.add_to_policy(statement)

        return role

    def _lambda_environment(
        self,
        props: AsyncScoreProcessingProps,
        queues: AsyncScoreProcessingQueues,
    ) -> dict[str, str]:
        environment = {
            "environment": props.environment_name,
            "PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL": (
                queues.request_queue.queue_url
            ),
            "PLEXUS_RESPONSE_WORKER_QUEUE_URL": queues.response_queue.queue_url,
            **DEFAULT_STATIC_ENVIRONMENT,
        }
        for env_name, secret_key in props.secret_environment.items():
            environment[env_name] = (
                props.runtime_config_secret.secret_value_from_json(
                    secret_key
                ).unsafe_unwrap()
            )
        environment.update(props.environment_variables)
        return environment

    def _create_dead_letter_queue_alarms(
        self,
        props: AsyncScoreProcessingProps,
        queues: AsyncScoreProcessingQueues,
    ) -> list[cloudwatch.Alarm]:
        alarms = []
        for construct_id, queue in [
            ("StandardRequestDeadLetterQueueAlarm", queues.request_dead_letter_queue),
            ("ResponseDeadLetterQueueAlarm", queues.response_dead_letter_queue),
        ]:
            if queue is None:
                continue
            alarms.append(
                cloudwatch.Alarm(
                    self,
                    construct_id,
                    alarm_name=f"{props.resource_prefix}-{construct_id}",
                    metric=queue.metric_approximate_number_of_messages_visible(),
                    threshold=1,
                    evaluation_periods=1,
                    datapoints_to_alarm=1,
                    comparison_operator=(
                        cloudwatch.ComparisonOperator
                        .GREATER_THAN_OR_EQUAL_TO_THRESHOLD
                    ),
                    treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                )
            )
        return alarms
