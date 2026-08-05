import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest
from aws_cdk import aws_ecr, aws_ec2, aws_secretsmanager, aws_sns
from pathlib import Path

from plexus.infrastructure.command_service import (
    CommandServiceStateStack,
    CommandServiceWorkerStack,
    CommandWorkerEgressRule,
    CommandWorkerSecret,
)

ENV = cdk.Environment(account="123456789012", region="us-east-1")
IMAGE_DIGEST = "sha256:" + "a" * 64


def _stack(app: cdk.App | None = None, **kwargs) -> CommandServiceWorkerStack:
    app = app or cdk.App()
    network = cdk.Stack(app, "Network", env=ENV)
    vpc = aws_ec2.Vpc(network, "Vpc", max_azs=2, nat_gateways=1)
    state = CommandServiceStateStack(
        app,
        "CommandState",
        resource_prefix="example-service",
        environment="test",
        env=ENV,
    )
    repository_stack = cdk.Stack(app, "Repository", env=ENV)
    repository = aws_ecr.Repository(
        repository_stack,
        "WorkerRepository",
        repository_name="example-command-worker-test",
    )
    alerts = aws_sns.Topic(repository_stack, "Alerts")
    arguments = {
        "image_digest": IMAGE_DIGEST,
        "command": ["python", "-m", "worker"],
        "runtime_environment": {"COMMAND_WORKER_MODE": "celery"},
        "alert_topic": alerts,
        **kwargs,
    }
    return CommandServiceWorkerStack(
        app,
        "CommandWorker",
        resource_prefix="example-service",
        display_name="Example Service",
        environment="test",
        vpc=vpc,
        state=state,
        image_repository=repository,
        env=ENV,
        **arguments,
    )


def test_command_service_package_exports_worker_stack() -> None:
    assert CommandServiceWorkerStack
    assert CommandWorkerEgressRule
    assert CommandWorkerSecret


def test_worker_stack_synthesizes_an_always_on_private_fargate_service() -> None:
    stack = _stack()
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::ECS::Service",
        {
            "ServiceName": "example-service-test-command-worker",
            "DesiredCount": 1,
            "DeploymentConfiguration": {
                "DeploymentCircuitBreaker": {"Enable": True, "Rollback": True},
                "MinimumHealthyPercent": 100,
                "MaximumPercent": 200,
            },
            "NetworkConfiguration": assertions.Match.object_like(
                {"AwsvpcConfiguration": {"AssignPublicIp": "DISABLED"}}
            ),
        },
    )
    template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {
            "LogGroupName": "/aws/ecs/example-service/test/command-worker",
            "RetentionInDays": 30,
        },
    )
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "example-service-test-command-worker-running-tasks",
            "ComparisonOperator": "LessThanThreshold",
            "Threshold": 1,
            "TreatMissingData": "breaching",
        },
    )


def test_worker_task_role_has_only_lifecycle_and_consumer_permissions() -> None:
    template = assertions.Template.from_stack(_stack())
    policies = template.find_resources("AWS::IAM::Policy")
    statements = [
        statement
        for policy in policies.values()
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    ]

    assert any(
        statement["Action"] == ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        for statement in statements
    )
    assert any(
        set(statement["Action"])
        == {
            "sqs:ChangeMessageVisibility",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
            "sqs:GetQueueUrl",
            "sqs:ReceiveMessage",
        }
        for statement in statements
    )
    assert not any("sqs:SendMessage" in statement["Action"] for statement in statements)


def test_worker_stack_injects_only_managed_bindings_and_requested_runtime_values() -> (
    None
):
    template = assertions.Template.from_stack(_stack())
    definition = next(
        iter(template.find_resources("AWS::ECS::TaskDefinition").values())
    )
    environment = {
        item["Name"]: item["Value"]
        for item in definition["Properties"]["ContainerDefinitions"][0]["Environment"]
    }

    assert environment["COMMAND_WORKER_MODE"] == "celery"
    assert environment["PYTHONUNBUFFERED"] == "1"
    assert "COMMAND_LIFECYCLE_TABLE_NAME" in environment
    assert "COMMAND_QUEUE_URL" in environment


def test_worker_stack_grants_runtime_secret_to_execution_role() -> None:
    app = cdk.App()
    secret_stack = cdk.Stack(app, "Secrets", env=ENV)
    secret = aws_secretsmanager.Secret(secret_stack, "RuntimeSecret")
    stack = _stack(
        app,
        runtime_secrets=(
            CommandWorkerSecret(
                name="COMMAND_WORKER_TOKEN",
                secret=secret,
                json_field="token",
            ),
        ),
    )
    template = assertions.Template.from_stack(stack)
    definition = next(
        iter(template.find_resources("AWS::ECS::TaskDefinition").values())
    )
    secret_binding = definition["Properties"]["ContainerDefinitions"][0]["Secrets"]

    assert secret_binding[0]["Name"] == "COMMAND_WORKER_TOKEN"
    policies = template.find_resources("AWS::IAM::Policy")
    assert any(
        "secretsmanager:GetSecretValue" in statement["Action"]
        for policy in policies.values()
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"image_digest": "latest"}, "immutable sha256"),
        ({"command": ()}, "command must contain"),
        ({"desired_count": 0}, "at least 1"),
        ({"cpu": 1024, "memory_limit_mib": 1024}, "not valid"),
        (
            {
                "runtime_environment": {
                    "COMMAND_QUEUE_URL": "cannot-override-managed-value"
                }
            },
            "must not override",
        ),
        (
            {
                "runtime_secrets": (
                    CommandWorkerSecret(
                        name="COMMAND_QUEUE_URL",
                        secret=object(),
                    ),
                )
            },
            "must not override",
        ),
    ],
)
def test_worker_stack_rejects_invalid_configuration(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        _stack(**overrides)


def test_egress_rule_validates_cidr_port_and_description() -> None:
    assert CommandWorkerEgressRule("10.0.0.0/24", 1433, "SQL access")
    with pytest.raises(ValueError, match="IPv4"):
        CommandWorkerEgressRule("2001:db8::/64", 443, "IPv6 is not supported")
    with pytest.raises(ValueError, match="between 1 and 65535"):
        CommandWorkerEgressRule("10.0.0.0/24", 0, "bad port")


def test_worker_stack_contains_no_consumer_or_legacy_runtime_values() -> None:
    source = (
        (
            Path(__file__).resolve().parents[3]
            / "plexus"
            / "infrastructure"
            / "command_service"
            / "worker_stack.py"
        )
        .read_text()
        .casefold()
    )

    for forbidden_value in (
        "capacity",
        "call_criteria",
        "dashboard",
        "cli/shared",
        "systemd",
        "amazonssmmanagedinstancecore",
    ):
        assert forbidden_value not in source
