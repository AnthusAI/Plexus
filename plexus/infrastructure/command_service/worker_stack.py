"""Always-on ECS deployment for the portable command service worker."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import ipaddress
import re

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
)
from constructs import Construct

from .state_stack import CommandServiceStateStack

_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_FARGATE_MEMORY_BY_CPU = {
    256: {512, 1024, 2048},
    512: {1024, 2048, 3072, 4096},
    1024: set(range(2048, 8193, 1024)),
    2048: set(range(4096, 16385, 1024)),
    4096: set(range(8192, 30721, 1024)),
}
_MANAGED_ENVIRONMENT_NAMES = {
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "COMMAND_LIFECYCLE_TABLE_NAME",
    "COMMAND_QUEUE_URL",
    "PYTHONUNBUFFERED",
}


@dataclass(frozen=True)
class CommandWorkerEgressRule:
    """A consumer-supplied outbound TCP destination for command execution."""

    cidr: str
    port: int
    description: str

    def __post_init__(self) -> None:
        try:
            network = ipaddress.ip_network(self.cidr)
        except ValueError as error:
            raise ValueError("cidr must be a valid IPv4 CIDR") from error
        if network.version != 4:
            raise ValueError("cidr must be a valid IPv4 CIDR")
        if not isinstance(self.port, int) or isinstance(self.port, bool):
            raise ValueError("port must be an integer")
        if self.port < 1 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")
        if not self.description.strip():
            raise ValueError("description must not be empty")


@dataclass(frozen=True)
class CommandWorkerSecret:
    """A named Secrets Manager value injected by ECS at task startup."""

    name: str
    secret: secretsmanager.ISecret
    json_field: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")


class CommandServiceWorkerStack(Stack):
    """Run the portable command worker continuously on ECS/Fargate.

    The stack receives a consumer-owned immutable image and runtime bindings.
    It owns only generic command delivery: consuming the command queue and
    applying lifecycle mutations through ``CommandServiceStateStack``.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        display_name: str,
        environment: str,
        vpc: ec2.IVpc,
        state: CommandServiceStateStack,
        image_repository: ecr.IRepository,
        image_digest: str,
        command: Sequence[str],
        runtime_environment: Mapping[str, str],
        runtime_secrets: Sequence[CommandWorkerSecret] = (),
        desired_count: int = 1,
        cpu: int = 1024,
        memory_limit_mib: int = 4096,
        allow_public_https_egress: bool = True,
        additional_egress_rules: Sequence[CommandWorkerEgressRule] = (),
        alert_topic: sns.ITopic | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._validate_nonempty("resource_prefix", resource_prefix)
        self._validate_nonempty("display_name", display_name)
        self._validate_nonempty("environment", environment)
        if not _IMAGE_DIGEST.fullmatch(image_digest):
            raise ValueError("image_digest must be an immutable sha256 digest")
        if not command or not all(
            isinstance(argument, str) and argument for argument in command
        ):
            raise ValueError("command must contain non-empty string arguments")
        if not isinstance(desired_count, int) or isinstance(desired_count, bool):
            raise ValueError("desired_count must be an integer")
        if desired_count < 1:
            raise ValueError("desired_count must be at least 1")
        if cpu not in _FARGATE_MEMORY_BY_CPU:
            raise ValueError("cpu must be a supported Fargate CPU value")
        if memory_limit_mib not in _FARGATE_MEMORY_BY_CPU[cpu]:
            raise ValueError("memory_limit_mib is not valid for the selected cpu")
        if not isinstance(allow_public_https_egress, bool):
            raise ValueError("allow_public_https_egress must be a boolean")
        if _MANAGED_ENVIRONMENT_NAMES & runtime_environment.keys():
            raise ValueError("runtime_environment must not override managed variables")
        secret_names = [secret.name for secret in runtime_secrets]
        if len(secret_names) != len(set(secret_names)):
            raise ValueError("runtime_secrets must not contain duplicate names")
        if _MANAGED_ENVIRONMENT_NAMES & set(secret_names):
            raise ValueError("runtime_secrets must not override managed variables")

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", f"{resource_prefix}-command-service")
        Tags.of(self).add("Environment", environment)

        worker_name = f"{resource_prefix}-{environment}-command-worker"
        self.cluster = ecs.Cluster(
            self,
            "CommandWorkerCluster",
            cluster_name=f"{resource_prefix}-{environment}-command-workers",
            vpc=vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )
        self.security_group = ec2.SecurityGroup(
            self,
            "CommandWorkerSecurityGroup",
            vpc=vpc,
            security_group_name=worker_name,
            description=(
                f"Outbound-only security group for {display_name} {environment} "
                "command worker"
            ),
            allow_all_outbound=False,
        )
        if allow_public_https_egress:
            self.security_group.add_egress_rule(
                peer=ec2.Peer.any_ipv4(),
                connection=ec2.Port.tcp(443),
                description="Command worker to public HTTPS APIs and AWS endpoints",
            )
        for rule in additional_egress_rules:
            self.security_group.add_egress_rule(
                peer=ec2.Peer.ipv4(rule.cidr),
                connection=ec2.Port.tcp(rule.port),
                description=rule.description,
            )

        retention = (
            logs.RetentionDays.THREE_MONTHS
            if environment.casefold() == "production"
            else logs.RetentionDays.ONE_MONTH
        )
        self.log_group = logs.LogGroup(
            self,
            "CommandWorkerLogGroup",
            log_group_name=f"/aws/ecs/{resource_prefix}/{environment}/command-worker",
            retention=retention,
            removal_policy=RemovalPolicy.RETAIN,
        )

        ecs_tasks_principal = iam.ServicePrincipal(
            "ecs-tasks.amazonaws.com",
            conditions={
                "StringEquals": {"aws:SourceAccount": self.account},
                "ArnLike": {
                    "aws:SourceArn": f"arn:{self.partition}:ecs:{self.region}:{self.account}:*"
                },
            },
        )
        self.task_role = iam.Role(
            self,
            "CommandWorkerTaskRole",
            assumed_by=ecs_tasks_principal,
        )
        self.execution_role = iam.Role(
            self,
            "CommandWorkerExecutionRole",
            assumed_by=ecs_tasks_principal,
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )
        state.grant_lifecycle_worker(self.task_role)
        state.queue.grant_consume_messages(self.task_role)
        image_repository.grant_pull(self.execution_role)

        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "CommandWorkerTaskDefinition",
            family=worker_name,
            cpu=cpu,
            memory_limit_mib=memory_limit_mib,
            task_role=self.task_role,
            execution_role=self.execution_role,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )
        self.task_definition.add_container(
            "CommandWorkerContainer",
            container_name="command-worker",
            image=ecs.ContainerImage.from_ecr_repository(
                image_repository,
                image_digest,
            ),
            command=list(command),
            environment={
                "AWS_REGION": self.region,
                "AWS_DEFAULT_REGION": self.region,
                "COMMAND_LIFECYCLE_TABLE_NAME": state.table.table_name,
                "COMMAND_QUEUE_URL": state.queue.queue_url,
                "PYTHONUNBUFFERED": "1",
                **dict(runtime_environment),
            },
            secrets={
                secret.name: ecs.Secret.from_secrets_manager(
                    secret.secret,
                    secret.json_field,
                )
                for secret in runtime_secrets
            },
            logging=ecs.LogDriver.aws_logs(
                log_group=self.log_group,
                stream_prefix="command-worker",
            ),
        )
        for secret in runtime_secrets:
            secret.secret.grant_read(self.execution_role)

        self.service = ecs.FargateService(
            self,
            "CommandWorkerService",
            service_name=worker_name,
            cluster=self.cluster,
            task_definition=self.task_definition,
            desired_count=desired_count,
            assign_public_ip=False,
            security_groups=[self.security_group],
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            min_healthy_percent=100,
            max_healthy_percent=200,
        )
        self.service.node.add_dependency(self.log_group)

        running_alarm = cloudwatch.Alarm(
            self,
            "CommandWorkerRunningTaskAlarm",
            alarm_name=f"{worker_name}-running-tasks",
            alarm_description="Command worker has fewer running tasks than desired",
            metric=cloudwatch.Metric(
                namespace="ECS/ContainerInsights",
                metric_name="RunningTaskCount",
                dimensions_map={
                    "ClusterName": self.cluster.cluster_name,
                    "ServiceName": self.service.service_name,
                },
                period=Duration.minutes(1),
                statistic="Minimum",
            ),
            threshold=desired_count,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
        )
        if alert_topic is not None:
            running_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alert_topic))
        self.running_task_alarm = running_alarm

        CfnOutput(
            self,
            "CommandWorkerClusterName",
            value=self.cluster.cluster_name,
            export_name=f"{resource_prefix}-{environment}-command-worker-cluster-name",
        )
        CfnOutput(
            self,
            "CommandWorkerServiceName",
            value=self.service.service_name,
            export_name=f"{resource_prefix}-{environment}-command-worker-service-name",
        )

    @staticmethod
    def _validate_nonempty(name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must not be empty")
