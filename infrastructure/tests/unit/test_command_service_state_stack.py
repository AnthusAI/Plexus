from pathlib import Path

import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest
from aws_cdk import Duration, aws_iam

from plexus.infrastructure.command_service import CommandServiceStateStack

ENV = cdk.Environment(account="123456789012", region="us-east-1")


def _stack(
    app: cdk.App | None = None,
    **kwargs,
) -> CommandServiceStateStack:
    app = app or cdk.App()
    return CommandServiceStateStack(
        app,
        "CommandState",
        resource_prefix="example-service",
        environment="test",
        env=ENV,
        **kwargs,
    )


def test_command_service_package_exports_state_stack() -> None:
    assert CommandServiceStateStack


def test_state_stack_synthesizes_durable_table_and_encrypted_queues() -> None:
    stack = _stack()
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "example-service-test-command-state",
            "AttributeDefinitions": [
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            "KeySchema": [
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
            "SSESpecification": {"SSEEnabled": True},
            "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
            "TimeToLiveSpecification": {
                "AttributeName": "expires_at_epoch",
                "Enabled": True,
            },
            "DeletionProtectionEnabled": False,
        },
    )
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "example-service-test-command-dlq",
            "SqsManagedSseEnabled": True,
            "MessageRetentionPeriod": 1209600,
        },
    )
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "example-service-test-command-queue",
            "SqsManagedSseEnabled": True,
            "VisibilityTimeout": 300,
            "ReceiveMessageWaitTimeSeconds": 20,
            "MessageRetentionPeriod": 345600,
            "RedrivePolicy": assertions.Match.object_like({"maxReceiveCount": 5}),
        },
    )
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "example-service-test-command-dlq-messages-visible",
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "EvaluationPeriods": 1,
            "Threshold": 1,
            "TreatMissingData": "notBreaching",
            "MetricName": "ApproximateNumberOfMessagesVisible",
            "Namespace": "AWS/SQS",
            "Statistic": "Maximum",
        },
    )
    assert stack.table
    assert stack.queue
    assert stack.dead_letter_queue
    assert stack.dead_letter_alarm


def test_state_stack_retains_stateful_resources() -> None:
    template = assertions.Template.from_stack(_stack())

    table = next(iter(template.find_resources("AWS::DynamoDB::Table").values()))
    assert table["DeletionPolicy"] == "Retain"
    assert table["UpdateReplacePolicy"] == "Retain"
    for queue in template.find_resources("AWS::SQS::Queue").values():
        assert queue["DeletionPolicy"] == "Retain"
        assert queue["UpdateReplacePolicy"] == "Retain"


def test_state_stack_denies_non_tls_access_to_both_queues() -> None:
    template = assertions.Template.from_stack(_stack())
    policies = template.find_resources("AWS::SQS::QueuePolicy")

    assert len(policies) == 2
    for policy in policies.values():
        statements = policy["Properties"]["PolicyDocument"]["Statement"]
        assert any(
            statement.get("Effect") == "Deny"
            and statement.get("Action") == "sqs:*"
            and statement.get("Principal") == {"AWS": "*"}
            and statement.get("Condition") == {"Bool": {"aws:SecureTransport": "false"}}
            for statement in statements
        )


def test_production_enables_table_deletion_protection_by_default() -> None:
    app = cdk.App()
    stack = CommandServiceStateStack(
        app,
        "ProductionCommandState",
        resource_prefix="example-service",
        environment="production",
        env=ENV,
    )

    assertions.Template.from_stack(stack).has_resource_properties(
        "AWS::DynamoDB::Table",
        {"DeletionProtectionEnabled": True},
    )


def test_table_deletion_protection_can_be_explicitly_configured() -> None:
    assertions.Template.from_stack(
        _stack(table_deletion_protection=True)
    ).has_resource_properties(
        "AWS::DynamoDB::Table",
        {"DeletionProtectionEnabled": True},
    )


def test_state_stack_applies_optional_alarm_topic_action() -> None:
    app = cdk.App()
    topic_stack = cdk.Stack(app, "Alerting", env=ENV)
    topic = cdk.aws_sns.Topic(topic_stack, "Alerts")
    stack = _stack(app, alarm_topic=topic)

    alarms = assertions.Template.from_stack(stack).find_resources(
        "AWS::CloudWatch::Alarm"
    )
    alarm = next(iter(alarms.values()))
    assert len(alarm["Properties"]["AlarmActions"]) == 1


def test_lifecycle_worker_grant_is_limited_to_metadata_reads_and_updates() -> None:
    app = cdk.App()
    stack = _stack(app)
    worker = aws_iam.Role(
        stack,
        "WorkerRole",
        assumed_by=aws_iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    )
    stack.grant_lifecycle_worker(worker)

    policies = assertions.Template.from_stack(stack).find_resources("AWS::IAM::Policy")
    statements = [
        statement
        for policy in policies.values()
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    ]
    assert any(
        statement["Action"] == ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        and statement["Resource"]
        == {"Fn::GetAtt": ["CommandStateTable92D4D8AD", "Arn"]}
        for statement in statements
    )


def test_state_stack_uses_stable_logical_ids() -> None:
    resources = assertions.Template.from_stack(_stack()).to_json()["Resources"]

    assert "CommandStateTable92D4D8AD" in resources
    assert "CommandDeadLetterQueue4E581A99" in resources
    assert "CommandQueue811FAE69" in resources
    assert "CommandDeadLetterQueueMessagesAlarm6AB29208" in resources


def test_state_stack_accepts_valid_queue_and_alarm_configuration() -> None:
    template = assertions.Template.from_stack(
        _stack(
            visibility_timeout=Duration.hours(1),
            receive_message_wait_time=Duration.seconds(0),
            command_retention_period=Duration.days(7),
            dead_letter_retention_period=Duration.days(10),
            max_receive_count=9,
            dead_letter_alarm_threshold=3,
            dead_letter_alarm_period=Duration.minutes(1),
        )
    )

    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "example-service-test-command-queue",
            "VisibilityTimeout": 3600,
            "ReceiveMessageWaitTimeSeconds": 0,
            "MessageRetentionPeriod": 604800,
            "RedrivePolicy": {"maxReceiveCount": 9},
        },
    )
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {"Period": 60, "Threshold": 3},
    )


def test_state_stack_publishes_stable_useful_outputs() -> None:
    template = assertions.Template.from_stack(_stack())

    for output_id, export_suffix in (
        ("CommandStateTableName", "state-table-name"),
        ("CommandStateTableArn", "state-table-arn"),
        ("CommandQueueUrl", "queue-url"),
        ("CommandQueueArn", "queue-arn"),
        ("CommandDeadLetterQueueUrl", "dead-letter-queue-url"),
        ("CommandDeadLetterQueueArn", "dead-letter-queue-arn"),
        ("CommandDeadLetterQueueAlarmName", "dead-letter-queue-alarm-name"),
    ):
        template.has_output(
            output_id,
            {
                "Export": {
                    "Name": ("example-service-test-command-service-" + export_suffix)
                }
            },
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"resource_prefix": ""}, "resource_prefix must not be empty"),
        ({"resource_prefix": " invalid"}, "surrounding whitespace"),
        ({"resource_prefix": "invalid.name"}, "only alphanumeric"),
        ({"environment": ""}, "environment must not be empty"),
        ({"environment": "invalid/name"}, "only alphanumeric"),
        (
            {"resource_prefix": "x" * 70},
            "queue name must not exceed 80 characters",
        ),
        ({"visibility_timeout": Duration.seconds(0)}, "visibility_timeout"),
        ({"visibility_timeout": Duration.hours(13)}, "visibility_timeout"),
        (
            {"receive_message_wait_time": Duration.seconds(21)},
            "receive_message_wait_time",
        ),
        (
            {"command_retention_period": Duration.seconds(59)},
            "command_retention_period",
        ),
        (
            {"dead_letter_retention_period": Duration.days(15)},
            "dead_letter_retention_period",
        ),
        (
            {
                "command_retention_period": Duration.days(2),
                "dead_letter_retention_period": Duration.days(1),
            },
            "must be at least as long",
        ),
        ({"max_receive_count": 0}, "between 1 and 1000"),
        ({"max_receive_count": True}, "must be an integer"),
        ({"dead_letter_alarm_threshold": 0}, "must be at least 1"),
        ({"dead_letter_alarm_threshold": True}, "must be an integer"),
        (
            {"dead_letter_alarm_period": Duration.seconds(30)},
            "whole number of minutes",
        ),
        ({"table_deletion_protection": "yes"}, "must be a boolean"),
    ],
)
def test_state_stack_rejects_invalid_configuration(
    overrides: dict,
    message: str,
) -> None:
    app = cdk.App()
    arguments = {
        "resource_prefix": "example-service",
        "environment": "test",
        **overrides,
    }

    with pytest.raises(ValueError, match=message):
        CommandServiceStateStack(
            app,
            "InvalidCommandState",
            env=ENV,
            **arguments,
        )


def test_state_stack_contains_no_consumer_or_delivery_provider_values() -> None:
    source = (
        (
            Path(__file__).resolve().parents[3]
            / "plexus"
            / "infrastructure"
            / "command_service"
            / "state_stack.py"
        )
        .read_text()
        .casefold()
    )

    for forbidden_value in (
        "capacity",
        "call_criteria",
        "celery",
        "dashboard",
        "redis",
        "task_id",
        "lambda",
        "fargate",
        "kubernetes",
    ):
        assert forbidden_value not in source
