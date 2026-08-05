from __future__ import annotations

import re

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_sns as sns,
    aws_sqs as sqs,
)
from constructs import Construct

_NAME_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_MIN_RETENTION_SECONDS = 60
_MAX_RETENTION_SECONDS = 14 * 24 * 60 * 60
_MAX_VISIBILITY_SECONDS = 12 * 60 * 60


class CommandServiceStateStack(Stack):
    """Durable state and delivery primitives for a command service.

    The command repository stores each canonical lifecycle record at
    ``pk=COMMAND#<command_id>, sk=META``. The record includes immutable command
    identity, the canonical request digest, lifecycle status, numeric fence,
    lease metadata, and ``expires_at_epoch`` for TTL cleanup.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        environment: str,
        visibility_timeout: Duration = Duration.minutes(5),
        receive_message_wait_time: Duration = Duration.seconds(20),
        command_retention_period: Duration = Duration.days(4),
        dead_letter_retention_period: Duration = Duration.days(14),
        max_receive_count: int = 5,
        dead_letter_alarm_threshold: int = 1,
        dead_letter_alarm_period: Duration = Duration.minutes(5),
        alarm_topic: sns.ITopic | None = None,
        table_deletion_protection: bool | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._validate_name_component("resource_prefix", resource_prefix)
        self._validate_name_component("environment", environment)

        resource_name = f"{resource_prefix}-{environment}-command"
        queue_name = f"{resource_name}-queue"
        dead_letter_queue_name = f"{resource_name}-dlq"
        table_name = f"{resource_name}-state"
        self._validate_resource_name("queue name", queue_name, maximum_length=80)
        self._validate_resource_name(
            "dead-letter queue name",
            dead_letter_queue_name,
            maximum_length=80,
        )
        self._validate_resource_name("table name", table_name, maximum_length=255)
        self._validate_duration(
            "visibility_timeout",
            visibility_timeout,
            minimum_seconds=1,
            maximum_seconds=_MAX_VISIBILITY_SECONDS,
        )
        self._validate_duration(
            "receive_message_wait_time",
            receive_message_wait_time,
            minimum_seconds=0,
            maximum_seconds=20,
        )
        self._validate_duration(
            "command_retention_period",
            command_retention_period,
            minimum_seconds=_MIN_RETENTION_SECONDS,
            maximum_seconds=_MAX_RETENTION_SECONDS,
        )
        self._validate_duration(
            "dead_letter_retention_period",
            dead_letter_retention_period,
            minimum_seconds=_MIN_RETENTION_SECONDS,
            maximum_seconds=_MAX_RETENTION_SECONDS,
        )
        if dead_letter_retention_period.to_seconds() < (
            command_retention_period.to_seconds()
        ):
            raise ValueError(
                "dead_letter_retention_period must be at least as long as "
                "command_retention_period"
            )
        if not isinstance(max_receive_count, int) or isinstance(
            max_receive_count, bool
        ):
            raise ValueError("max_receive_count must be an integer")
        if max_receive_count < 1 or max_receive_count > 1000:
            raise ValueError("max_receive_count must be between 1 and 1000")
        if not isinstance(dead_letter_alarm_threshold, int) or isinstance(
            dead_letter_alarm_threshold, bool
        ):
            raise ValueError("dead_letter_alarm_threshold must be an integer")
        if dead_letter_alarm_threshold < 1:
            raise ValueError("dead_letter_alarm_threshold must be at least 1")
        self._validate_alarm_period(dead_letter_alarm_period)
        if table_deletion_protection is not None and not isinstance(
            table_deletion_protection, bool
        ):
            raise ValueError("table_deletion_protection must be a boolean")

        if table_deletion_protection is None:
            table_deletion_protection = environment.casefold() == "production"

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", f"{resource_prefix}-command-service")
        Tags.of(self).add("Environment", environment)

        self.table = dynamodb.Table(
            self,
            "CommandStateTable",
            table_name=table_name,
            partition_key=dynamodb.Attribute(
                name="pk",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="sk",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery_specification=(
                dynamodb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=True
                )
            ),
            time_to_live_attribute="expires_at_epoch",
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            deletion_protection=table_deletion_protection,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.dead_letter_queue = sqs.Queue(
            self,
            "CommandDeadLetterQueue",
            queue_name=dead_letter_queue_name,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            retention_period=dead_letter_retention_period,
            removal_policy=RemovalPolicy.RETAIN,
        )
        self.queue = sqs.Queue(
            self,
            "CommandQueue",
            queue_name=queue_name,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            visibility_timeout=visibility_timeout,
            receive_message_wait_time=receive_message_wait_time,
            retention_period=command_retention_period,
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=self.dead_letter_queue,
                max_receive_count=max_receive_count,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.dead_letter_alarm = cloudwatch.Alarm(
            self,
            "CommandDeadLetterQueueMessagesAlarm",
            alarm_name=f"{resource_name}-dlq-messages-visible",
            alarm_description="Command dead-letter queue contains messages",
            metric=self.dead_letter_queue.metric_approximate_number_of_messages_visible(
                period=dead_letter_alarm_period,
                statistic="Maximum",
            ),
            threshold=dead_letter_alarm_threshold,
            evaluation_periods=1,
            comparison_operator=(
                cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        if alarm_topic is not None:
            self.dead_letter_alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(alarm_topic)
            )

        self._add_outputs(resource_prefix=resource_prefix, environment=environment)

    def grant_lifecycle_worker(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant only the metadata reads and fenced updates needed by a worker."""

        return iam.Grant.add_to_principal(
            grantee=grantee,
            actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
            resource_arns=[self.table.table_arn],
        )

    def grant_state_projection(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant read-only access to the canonical lifecycle change stream."""

        return self.table.grant_stream_read(grantee)

    def _add_outputs(self, *, resource_prefix: str, environment: str) -> None:
        export_prefix = f"{resource_prefix}-{environment}-command-service"
        outputs = (
            ("CommandStateTableName", self.table.table_name, "state-table-name"),
            ("CommandStateTableArn", self.table.table_arn, "state-table-arn"),
            (
                "CommandStateTableStreamArn",
                self.table.table_stream_arn,
                "state-table-stream-arn",
            ),
            ("CommandQueueUrl", self.queue.queue_url, "queue-url"),
            ("CommandQueueArn", self.queue.queue_arn, "queue-arn"),
            (
                "CommandDeadLetterQueueUrl",
                self.dead_letter_queue.queue_url,
                "dead-letter-queue-url",
            ),
            (
                "CommandDeadLetterQueueArn",
                self.dead_letter_queue.queue_arn,
                "dead-letter-queue-arn",
            ),
            (
                "CommandDeadLetterQueueAlarmName",
                self.dead_letter_alarm.alarm_name,
                "dead-letter-queue-alarm-name",
            ),
        )
        for construct_id, value, export_suffix in outputs:
            CfnOutput(
                self,
                construct_id,
                value=value,
                export_name=f"{export_prefix}-{export_suffix}",
            )

    @staticmethod
    def _validate_name_component(name: str, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must not be empty")
        if value != value.strip():
            raise ValueError(f"{name} must not have surrounding whitespace")
        if not _NAME_COMPONENT.fullmatch(value):
            raise ValueError(
                f"{name} must start with an alphanumeric character and contain "
                "only alphanumeric characters, hyphens, and underscores"
            )

    @staticmethod
    def _validate_resource_name(
        name: str,
        value: str,
        *,
        maximum_length: int,
    ) -> None:
        if len(value) > maximum_length:
            raise ValueError(f"{name} must not exceed {maximum_length} characters")

    @staticmethod
    def _validate_duration(
        name: str,
        value: Duration,
        *,
        minimum_seconds: int,
        maximum_seconds: int,
    ) -> None:
        if not isinstance(value, Duration):
            raise ValueError(f"{name} must be an aws_cdk.Duration")
        seconds = value.to_seconds()
        if seconds < minimum_seconds or seconds > maximum_seconds:
            raise ValueError(
                f"{name} must be between {minimum_seconds} and "
                f"{maximum_seconds} seconds"
            )

    @staticmethod
    def _validate_alarm_period(value: Duration) -> None:
        if not isinstance(value, Duration):
            raise ValueError("dead_letter_alarm_period must be an aws_cdk.Duration")
        seconds = value.to_seconds()
        if seconds < 60 or seconds % 60 != 0:
            raise ValueError(
                "dead_letter_alarm_period must be a positive whole number of minutes"
            )
