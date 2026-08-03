from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
import ipaddress
import re

from aws_cdk import (
    ArnFormat,
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
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_kms as kms,
    aws_logs as logs,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


@dataclass(frozen=True)
class ScheduledWorkerConfigValue:
    name: str
    value: str
    required: bool = True


@dataclass(frozen=True)
class ScheduledWorkerSecretValue:
    name: str
    json_field: str | None = None
    required: bool = True


@dataclass(frozen=True)
class ScheduledWorkerDefinition:
    worker_type: str
    command: Sequence[str]
    schedule: events.Schedule | None = None
    enabled: bool = False
    cpu: int = 1024
    memory_limit_mib: int = 4096
    ephemeral_storage_gib: int = 21
    timeout: Duration = field(default_factory=lambda: Duration.hours(7))
    image_tag: str | None = None
    runtime_environment: Sequence[ScheduledWorkerConfigValue] = field(
        default_factory=tuple
    )
    runtime_secrets: Sequence[ScheduledWorkerSecretValue] = field(default_factory=tuple)
    environment: Mapping[str, str] = field(default_factory=dict)
    runtime_secret_json_fields: Mapping[str, str] = field(default_factory=dict)
    required_environment_variables: Sequence[str] = field(default_factory=tuple)
    prevent_overlapping_runs: bool = True


class ScoringServiceScheduledWorkersStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        display_name: str,
        environment: str,
        vpc: ec2.IVpc,
        worker_definitions: Sequence[ScheduledWorkerDefinition],
        runtime_config_secret_name: str | None = None,
        runtime_config_secret_complete_arn: str | None = None,
        default_worker_image_tag: str = "bootstrap",
        sql_egress_cidrs: Sequence[str] = ("0.0.0.0/0",),
        sql_egress_ports: Sequence[int] = (1433,),
        allow_public_https_egress: bool = True,
        base_environment: Mapping[str, str],
        worker_type_environment_variable: str,
        required_environment_variable_list_name: str,
        worker_type_tag_key: str,
        alert_topic: sns.ITopic,
        alert_key: kms.IKey,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not resource_prefix.strip():
            raise ValueError("resource_prefix must not be empty")
        if not display_name.strip():
            raise ValueError("display_name must not be empty")

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", f"{resource_prefix}-scheduled-workers")
        Tags.of(self).add("Environment", environment)

        self.environment_name = environment
        self.resource_prefix = resource_prefix
        self.display_name = display_name
        self.base_environment = dict(base_environment)
        self.worker_type_environment_variable = worker_type_environment_variable
        self.required_environment_variable_list_name = (
            required_environment_variable_list_name
        )
        self.worker_type_tag_key = worker_type_tag_key
        self.vpc = vpc
        self.default_worker_image_tag = default_worker_image_tag
        self.sql_egress_cidrs = self._validated_cidrs(sql_egress_cidrs)
        self.sql_egress_ports = self._validated_ports(sql_egress_ports)

        self.alert_topic = alert_topic
        self.alert_key = alert_key
        self.state_machines: list[sfn.StateMachine] = []

        self.worker_image_repository = ecr.Repository(
            self,
            "ScheduledWorkerImageRepository",
            repository_name=f"{resource_prefix}-scheduled-workers-{environment}",
            image_scan_on_push=True,
            image_tag_mutability=ecr.TagMutability.IMMUTABLE,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=25)],
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.worker_security_group = ec2.SecurityGroup(
            self,
            "ScheduledWorkerSecurityGroup",
            vpc=vpc,
            security_group_name=f"{resource_prefix}-scheduled-workers-{environment}",
            description=(
                f"Outbound-only security group for {display_name} {environment} "
                "scheduled workers"
            ),
            allow_all_outbound=False,
        )
        self._add_worker_egress_rules(
            allow_public_https_egress=allow_public_https_egress,
        )

        self.cluster = ecs.Cluster(
            self,
            "ScheduledWorkerCluster",
            cluster_name=f"{resource_prefix}-scheduled-workers-{environment}",
            vpc=vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )

        runtime_config_secret_name = (
            runtime_config_secret_name
            or f"{resource_prefix}/{environment}/runtime-config"
        )
        if runtime_config_secret_complete_arn:
            runtime_secret = secretsmanager.Secret.from_secret_complete_arn(
                self,
                "RuntimeConfigSecret",
                runtime_config_secret_complete_arn,
            )
        else:
            runtime_secret = secretsmanager.Secret.from_secret_name_v2(
                self,
                "RuntimeConfigSecret",
                runtime_config_secret_name,
            )

        seen_worker_types: set[str] = set()
        for worker_definition in worker_definitions:
            if worker_definition.worker_type in seen_worker_types:
                raise ValueError(
                    f"duplicate scheduled worker type: {worker_definition.worker_type}"
                )
            seen_worker_types.add(worker_definition.worker_type)
            state_machine = self._create_worker(
                worker_definition=worker_definition,
                runtime_secret=runtime_secret,
                runtime_config_secret_name=runtime_config_secret_name,
            )
            self.state_machines.append(state_machine)

        CfnOutput(
            self,
            "ScheduledWorkerImageRepositoryUri",
            value=self.worker_image_repository.repository_uri,
            export_name=(
                f"{resource_prefix}-scheduled-workers-{environment}-repository-uri"
            ),
        )
        CfnOutput(
            self,
            "ScheduledWorkerClusterName",
            value=self.cluster.cluster_name,
            export_name=(
                f"{resource_prefix}-scheduled-workers-{environment}-cluster-name"
            ),
        )

    def _add_worker_egress_rules(
        self,
        *,
        allow_public_https_egress: bool,
    ) -> sfn.StateMachine:
        if allow_public_https_egress:
            self.worker_security_group.add_egress_rule(
                peer=ec2.Peer.any_ipv4(),
                connection=ec2.Port.tcp(443),
                description="Scheduled workers to public HTTPS APIs and AWS endpoints",
            )

        for cidr in self.sql_egress_cidrs:
            for port in self.sql_egress_ports:
                self.worker_security_group.add_egress_rule(
                    peer=ec2.Peer.ipv4(cidr),
                    connection=ec2.Port.tcp(port),
                    description=f"Scheduled workers to SQL endpoint tcp/{port}",
                )

    def _create_worker(
        self,
        *,
        worker_definition: ScheduledWorkerDefinition,
        runtime_secret: secretsmanager.ISecret,
        runtime_config_secret_name: str,
    ) -> None:
        worker_id = self._construct_id(worker_definition.worker_type)
        worker_name = (
            f"{self.resource_prefix}-scheduled-worker-"
            f"{self.environment_name}-{worker_definition.worker_type}"
        )

        log_group = logs.LogGroup(
            self,
            f"{worker_id}LogGroup",
            log_group_name=(
                f"/aws/ecs/{self.resource_prefix}/{self.environment_name}/"
                f"scheduled-workers/{worker_definition.worker_type}"
            ),
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.RETAIN,
        )

        ecs_source_arn = f"arn:{self.partition}:ecs:{self.region}:{self.account}:*"
        ecs_tasks_principal = iam.ServicePrincipal(
            "ecs-tasks.amazonaws.com",
            conditions={
                "StringEquals": {"aws:SourceAccount": self.account},
                "ArnLike": {"aws:SourceArn": ecs_source_arn},
            },
        )
        task_role = iam.Role(
            self,
            f"{worker_id}TaskRole",
            assumed_by=ecs_tasks_principal,
        )
        execution_role = iam.Role(
            self,
            f"{worker_id}ExecutionRole",
            assumed_by=ecs_tasks_principal,
        )

        task_definition = ecs.FargateTaskDefinition(
            self,
            f"{worker_id}TaskDefinition",
            family=worker_name,
            cpu=worker_definition.cpu,
            memory_limit_mib=worker_definition.memory_limit_mib,
            ephemeral_storage_gib=worker_definition.ephemeral_storage_gib,
            task_role=task_role,
            execution_role=execution_role,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )

        managed_environment = {
            "AWS_REGION": self.region,
            "AWS_DEFAULT_REGION": self.region,
            **self.base_environment,
            self.worker_type_environment_variable: worker_definition.worker_type,
            "PYTHONUNBUFFERED": "1",
        }
        runtime_environment = self._runtime_environment(worker_definition)
        runtime_secrets = self._runtime_secrets(worker_definition)
        required_environment_variables = self._required_environment_variables(
            worker_definition,
            managed_environment_names=managed_environment.keys(),
            runtime_environment_names=runtime_environment.keys(),
            runtime_secret_names=runtime_secrets.keys(),
        )
        managed_environment[self.required_environment_variable_list_name] = ",".join(
            required_environment_variables
        )

        container = task_definition.add_container(
            f"{worker_id}Container",
            container_name=worker_definition.worker_type,
            image=ecs.ContainerImage.from_ecr_repository(
                self.worker_image_repository,
                worker_definition.image_tag or self.default_worker_image_tag,
            ),
            command=list(worker_definition.command),
            environment={
                **managed_environment,
                **runtime_environment,
            },
            secrets={
                env_name: ecs.Secret.from_secrets_manager(runtime_secret, json_field)
                for env_name, json_field in runtime_secrets.items()
            },
            logging=ecs.LogDriver.aws_logs(
                stream_prefix=worker_definition.worker_type,
                log_group=log_group,
            ),
        )
        runtime_secret.grant_read(execution_role)
        self.worker_image_repository.grant_pull(execution_role)

        state_machine = self._create_worker_state_machine(
            worker_definition=worker_definition,
            worker_id=worker_id,
            worker_name=worker_name,
            task_definition=task_definition,
            container=container,
        )
        state_machine.add_to_role_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:GenerateDataKey*"],
                resources=[self.alert_key.key_arn],
            )
        )
        state_machine.node.add_dependency(log_group)

        if worker_definition.schedule is not None:
            self._create_schedule(
                worker_definition=worker_definition,
                worker_id=worker_id,
                worker_name=worker_name,
                state_machine=state_machine,
            )

        for alarm_id, metric_name, description in [
            ("Failure", "ExecutionsFailed", "failures"),
            ("Timeout", "ExecutionsTimedOut", "timeouts"),
            ("Abort", "ExecutionsAborted", "aborts"),
        ]:
            alarm = cloudwatch.Alarm(
                self,
                f"{worker_id}StateMachine{alarm_id}Alarm",
                metric=self._state_machine_metric(
                    state_machine,
                    metric_name,
                    period=Duration.minutes(5),
                ),
                evaluation_periods=1,
                threshold=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                alarm_description=(
                    f"Alarm for {worker_name} state machine {description}"
                ),
            )
            alarm.add_alarm_action(cloudwatch_actions.SnsAction(self.alert_topic))

        Tags.of(task_definition).add(
            self.worker_type_tag_key,
            worker_definition.worker_type,
        )
        CfnOutput(
            self,
            f"{worker_id}StateMachineArn",
            value=state_machine.state_machine_arn,
            export_name=(
                f"{self.resource_prefix}-scheduled-worker-"
                f"{self.environment_name}-{worker_definition.worker_type}-state-machine-arn"
            ),
        )
        return state_machine

    def _create_schedule(
        self,
        *,
        worker_definition: ScheduledWorkerDefinition,
        worker_id: str,
        worker_name: str,
        state_machine: sfn.IStateMachine,
    ) -> None:
        schedule_name = (
            f"{self.resource_prefix}-sw-{self.environment_name}-"
            f"{worker_definition.worker_type}-schedule"
        )
        schedule_dead_letter_queue = sqs.Queue(
            self,
            f"{worker_id}ScheduleDeadLetterQueue",
            queue_name=f"{schedule_name}-dlq",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            retention_period=Duration.days(14),
        )
        schedule_rule = events.Rule(
            self,
            f"{worker_id}Schedule",
            rule_name=schedule_name,
            description=f"Run {worker_name}",
            enabled=worker_definition.enabled,
            schedule=worker_definition.schedule,
        )
        schedule_rule.add_target(
            targets.SfnStateMachine(
                state_machine,
                dead_letter_queue=schedule_dead_letter_queue,
                max_event_age=Duration.hours(2),
                retry_attempts=3,
            )
        )
        schedule_dlq_alarm = cloudwatch.Alarm(
            self,
            f"{worker_id}ScheduleDeliveryFailureAlarm",
            metric=schedule_dead_letter_queue.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(5),
                statistic="Maximum",
            ),
            evaluation_periods=1,
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            alarm_description=f"Alarm when EventBridge cannot start {worker_name}",
        )
        schedule_dlq_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic)
        )

        if worker_definition.enabled:
            missed_start_alarm = cloudwatch.Alarm(
                self,
                f"{worker_id}MissedStartAlarm",
                metric=self._state_machine_metric(
                    state_machine,
                    "ExecutionsStarted",
                    period=Duration.hours(7),
                ),
                evaluation_periods=1,
                threshold=1,
                comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
                alarm_description=f"Alarm when {worker_name} does not start within 7 hours",
            )
            missed_start_alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(self.alert_topic)
            )

    def _runtime_environment(
        self,
        worker_definition: ScheduledWorkerDefinition,
    ) -> dict[str, str]:
        runtime_environment = dict(worker_definition.environment)
        for name, value in runtime_environment.items():
            self._validate_environment_variable_name(name)
            if not isinstance(value, str):
                raise ValueError(
                    f"{worker_definition.worker_type} environment value for {name} "
                    "must be a string"
                )

        for config_value in worker_definition.runtime_environment:
            self._validate_environment_variable_name(config_value.name)
            if not isinstance(config_value.value, str):
                raise ValueError(
                    f"{worker_definition.worker_type} runtime config value for "
                    f"{config_value.name} must be a string"
                )
            if config_value.name in runtime_environment:
                raise ValueError(
                    f"{worker_definition.worker_type} defines "
                    f"{config_value.name} more than once as runtime configuration"
                )
            runtime_environment[config_value.name] = config_value.value

        return runtime_environment

    def _runtime_secrets(
        self,
        worker_definition: ScheduledWorkerDefinition,
    ) -> dict[str, str]:
        runtime_secrets = dict(worker_definition.runtime_secret_json_fields)
        for name, json_field in runtime_secrets.items():
            self._validate_environment_variable_name(name)
            if not json_field:
                raise ValueError(
                    f"{worker_definition.worker_type} secret mapping for {name} "
                    "must specify a Secrets Manager JSON field"
                )

        for secret_value in worker_definition.runtime_secrets:
            self._validate_environment_variable_name(secret_value.name)
            if secret_value.name in runtime_secrets:
                raise ValueError(
                    f"{worker_definition.worker_type} defines "
                    f"{secret_value.name} more than once as a runtime secret"
                )
            runtime_secrets[secret_value.name] = (
                secret_value.json_field or secret_value.name
            )

        return runtime_secrets

    def _required_environment_variables(
        self,
        worker_definition: ScheduledWorkerDefinition,
        *,
        managed_environment_names: Iterable[str],
        runtime_environment_names: Iterable[str],
        runtime_secret_names: Iterable[str],
    ) -> list[str]:
        runtime_environment_name_set = set(runtime_environment_names)
        runtime_secret_name_set = set(runtime_secret_names)
        collisions = sorted(runtime_environment_name_set & runtime_secret_name_set)
        if collisions:
            raise ValueError(
                f"{worker_definition.worker_type} defines environment variables "
                f"as both config and secrets: {', '.join(collisions)}"
            )

        managed_collisions = sorted(
            set(managed_environment_names)
            & (runtime_environment_name_set | runtime_secret_name_set)
        )
        if managed_collisions:
            raise ValueError(
                f"{worker_definition.worker_type} overrides managed runtime "
                f"environment variables: {', '.join(managed_collisions)}"
            )

        if worker_definition.required_environment_variables:
            required_names = list(worker_definition.required_environment_variables)
        else:
            required_names = [
                config_value.name
                for config_value in worker_definition.runtime_environment
                if config_value.required
            ]
            required_names.extend(
                secret_value.name
                for secret_value in worker_definition.runtime_secrets
                if secret_value.required
            )
            required_names.extend(worker_definition.runtime_secret_json_fields.keys())

        deduped_required_names: list[str] = []
        seen_required_names: set[str] = set()
        for required_name in required_names:
            self._validate_environment_variable_name(required_name)
            if required_name in seen_required_names:
                continue
            seen_required_names.add(required_name)
            deduped_required_names.append(required_name)

        available_names = (
            set(managed_environment_names)
            | runtime_environment_name_set
            | runtime_secret_name_set
        )
        missing_names = sorted(set(deduped_required_names) - available_names)
        if missing_names:
            raise ValueError(
                f"{worker_definition.worker_type} requires runtime environment "
                f"variables without configured sources: {', '.join(missing_names)}"
            )

        return deduped_required_names

    def _state_machine_metric(
        self,
        state_machine: sfn.IStateMachine,
        metric_name: str,
        *,
        period: Duration,
    ) -> cloudwatch.Metric:
        return cloudwatch.Metric(
            namespace="AWS/States",
            metric_name=metric_name,
            dimensions_map={"StateMachineArn": state_machine.state_machine_arn},
            statistic="Sum",
            period=period,
        )

    def _create_worker_state_machine(
        self,
        *,
        worker_definition: ScheduledWorkerDefinition,
        worker_id: str,
        worker_name: str,
        task_definition: ecs.FargateTaskDefinition,
        container: ecs.ContainerDefinition,
    ) -> sfn.StateMachine:
        state_machine_arn = self.format_arn(
            service="states",
            resource="stateMachine",
            resource_name=worker_name,
            arn_format=ArnFormat.COLON_RESOURCE_NAME,
        )
        run_task = sfn_tasks.EcsRunTask(
            self,
            f"Run{worker_id}Task",
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            cluster=self.cluster,
            task_definition=task_definition,
            launch_target=sfn_tasks.EcsFargateLaunchTarget(
                platform_version=ecs.FargatePlatformVersion.LATEST,
            ),
            assign_public_ip=False,
            security_groups=[self.worker_security_group],
            subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            container_overrides=[
                sfn_tasks.ContainerOverride(
                    container_definition=container,
                    command=list(worker_definition.command),
                )
            ],
            result_path="$.WorkerTask",
        )

        launch_failure_alert = self._failure_alert(
            worker_id=worker_id,
            failure_id="Launch",
            worker_type=worker_definition.worker_type,
            subject=f"Scheduled worker launch failed ({worker_definition.worker_type})",
            message="Scheduled worker ECS task could not be launched",
            log_group_name=(
                f"/aws/ecs/{self.resource_prefix}/{self.environment_name}/"
                f"scheduled-workers/{worker_definition.worker_type}"
            ),
            include_task_result=False,
        )
        launch_failed = sfn.Fail(
            self,
            f"{worker_id}LaunchFailed",
            cause="Scheduled worker ECS task could not be launched",
        )
        run_task.add_catch(
            launch_failure_alert.next(launch_failed),
            errors=["States.ALL"],
            result_path="$.Failure",
        )

        succeeded = sfn.Succeed(self, f"{worker_id}Succeeded")
        failed_alert = self._failure_alert(
            worker_id=worker_id,
            failure_id="Exit",
            worker_type=worker_definition.worker_type,
            subject=f"Scheduled worker failed ({worker_definition.worker_type})",
            message="Scheduled worker ECS task exited unsuccessfully",
            log_group_name=(
                f"/aws/ecs/{self.resource_prefix}/{self.environment_name}/"
                f"scheduled-workers/{worker_definition.worker_type}"
            ),
            include_task_result=True,
        )
        failed = sfn.Fail(
            self,
            f"{worker_id}Failed",
            cause="Scheduled worker ECS task exited unsuccessfully",
        )

        check_exit_code = sfn.Choice(self, f"Check{worker_id}ExitCode")
        check_exit_code.when(
            sfn.Condition.number_equals("$.WorkerTask.Containers[0].ExitCode", 0),
            succeeded,
        )
        check_exit_code.otherwise(failed_alert.next(failed))

        worker_run_definition = run_task.next(check_exit_code)

        if worker_definition.prevent_overlapping_runs:
            list_running_executions = sfn_tasks.CallAwsService(
                self,
                f"List{worker_id}RunningExecutions",
                service="sfn",
                action="listExecutions",
                parameters={
                    "StateMachineArn": state_machine_arn,
                    "StatusFilter": "RUNNING",
                    "MaxResults": 2,
                },
                iam_resources=[state_machine_arn],
                result_path="$.RunningExecutions",
            )
            guard_failure_alert = self._failure_alert(
                worker_id=worker_id,
                failure_id="ConcurrencyGuard",
                worker_type=worker_definition.worker_type,
                subject=(
                    f"Scheduled worker concurrency guard failed "
                    f"({worker_definition.worker_type})"
                ),
                message="Scheduled worker concurrency guard could not list executions",
                log_group_name=(
                    f"/aws/ecs/{self.resource_prefix}/{self.environment_name}/"
                    f"scheduled-workers/{worker_definition.worker_type}"
                ),
                include_task_result=False,
            )
            guard_failed = sfn.Fail(
                self,
                f"{worker_id}ConcurrencyGuardFailed",
                cause="Scheduled worker concurrency guard could not list executions",
            )
            list_running_executions.add_catch(
                guard_failure_alert.next(guard_failed),
                errors=["States.ALL"],
                result_path="$.Failure",
            )

            skipped_for_running_execution = sfn.Succeed(
                self,
                f"{worker_id}SkippedForRunningExecution",
                comment="A prior execution for this scheduled worker is still running.",
            )
            check_running_executions = sfn.Choice(
                self,
                f"Check{worker_id}RunningExecutions",
            )
            check_running_executions.when(
                sfn.Condition.is_present(
                    "$.RunningExecutions.Executions[1].ExecutionArn"
                ),
                skipped_for_running_execution,
            )
            check_running_executions.otherwise(worker_run_definition)
            definition = list_running_executions.next(check_running_executions)
        else:
            definition = worker_run_definition

        state_machine = sfn.StateMachine(
            self,
            f"{worker_id}StateMachine",
            state_machine_name=worker_name,
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=worker_definition.timeout,
        )
        state_machine.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ecs:RunTask"],
                resources=[
                    self.format_arn(
                        service="ecs",
                        resource="task-definition",
                        resource_name=f"{worker_name}:*",
                        arn_format=ArnFormat.SLASH_RESOURCE_NAME,
                    )
                ],
                conditions={"ArnEquals": {"ecs:cluster": self.cluster.cluster_arn}},
            )
        )

        return state_machine

    def _failure_alert(
        self,
        *,
        worker_id: str,
        failure_id: str,
        worker_type: str,
        subject: str,
        message: str,
        log_group_name: str,
        include_task_result: bool,
    ) -> sfn_tasks.SnsPublish:
        alert_message: dict[str, object] = {
            "message": message,
            "workerType": worker_type,
            "failurePhase": failure_id,
            "stateMachineExecutionId": sfn.JsonPath.string_at("$$.Execution.Id"),
            "logGroupName": log_group_name,
        }
        if include_task_result:
            alert_message.update(
                {
                    "ecsTaskArn": sfn.JsonPath.string_at("$.WorkerTask.TaskArn"),
                    "ecsStoppedReason": sfn.JsonPath.string_at(
                        "$.WorkerTask.StoppedReason"
                    ),
                    "containerName": sfn.JsonPath.string_at(
                        "$.WorkerTask.Containers[0].Name"
                    ),
                    "containerExitCode": sfn.JsonPath.number_at(
                        "$.WorkerTask.Containers[0].ExitCode"
                    ),
                }
            )
        else:
            alert_message.update(
                {
                    "launchError": sfn.JsonPath.string_at("$.Failure.Error"),
                    "launchCause": sfn.JsonPath.string_at("$.Failure.Cause"),
                }
            )

        return sfn_tasks.SnsPublish(
            self,
            f"Publish{worker_id}{failure_id}FailureAlert",
            topic=self.alert_topic,
            subject=subject,
            message=sfn.TaskInput.from_object(alert_message),
        )

    def _construct_id(self, worker_type: str) -> str:
        parts = [part for part in re.split(r"[^A-Za-z0-9]+", worker_type) if part]
        if not parts:
            raise ValueError(
                "worker_type must contain at least one alphanumeric character"
            )
        return "".join(part[:1].upper() + part[1:] for part in parts)

    def _validate_environment_variable_name(self, name: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(
                f"invalid scheduled worker environment variable name: {name}"
            )

    def _validated_cidrs(self, cidrs: Sequence[str]) -> tuple[str, ...]:
        validated_cidrs: list[str] = []
        for cidr in cidrs:
            try:
                network = ipaddress.ip_network(cidr)
            except ValueError as error:
                raise ValueError(
                    f"invalid scheduled worker SQL egress CIDR: {cidr}"
                ) from error
            if network.version != 4:
                raise ValueError(
                    f"scheduled worker SQL egress CIDR must be IPv4: {cidr}"
                )
            validated_cidrs.append(str(network))
        return tuple(validated_cidrs)

    def _validated_ports(self, ports: Sequence[int]) -> tuple[int, ...]:
        validated_ports: list[int] = []
        for port in ports:
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ValueError(f"invalid scheduled worker SQL egress port: {port}")
            validated_ports.append(port)
        if not validated_ports:
            raise ValueError(
                "at least one scheduled worker SQL egress port is required"
            )
        return tuple(validated_ports)
