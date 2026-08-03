from __future__ import annotations

from collections.abc import Sequence

from aws_cdk import (
    Duration,
    Stack,
    Tags,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
)
from constructs import Construct


class ScoringServiceMonitoringStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        display_name: str,
        dashboard_name_prefix: str,
        environment: str,
        alert_topic: sns.ITopic,
        api_id: str,
        nat_gateway_ids: Sequence[str],
        state_machine_arns: Sequence[str],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not resource_prefix.strip():
            raise ValueError("resource_prefix must not be empty")
        if not display_name.strip():
            raise ValueError("display_name must not be empty")
        if not dashboard_name_prefix.strip():
            raise ValueError("dashboard_name_prefix must not be empty")

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", f"{resource_prefix}-monitoring")
        Tags.of(self).add("Environment", environment)

        period = Duration.minutes(5)
        api_dimensions = {"ApiId": api_id, "Stage": "$default"}
        function_names = [
            f"{resource_prefix}-api-{environment}",
            f"{resource_prefix}-scoring-{environment}-score-processor",
            f"{resource_prefix}-response-worker-{environment}",
        ]
        queue_names = [
            f"{resource_prefix}-scoring-{environment}-standard-request-queue",
            f"{resource_prefix}-scoring-{environment}-response-queue",
            f"{resource_prefix}-scoring-{environment}-standard-request-dlq",
            f"{resource_prefix}-scoring-{environment}-response-dlq",
        ]

        dashboard = cloudwatch.Dashboard(
            self,
            "OperationsDashboard",
            dashboard_name=(
                f"{dashboard_name_prefix}-{environment.title()}-Operations"
            ),
        )
        dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown=(
                    f"# {display_name} {environment.title()} Operations\n"
                    "Serverless API, async scoring, delivery, scheduled workers, "
                    "and network health."
                ),
                width=24,
                height=2,
            )
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API Requests and Errors",
                left=[
                    self._metric(
                        "AWS/ApiGateway",
                        metric_name,
                        api_dimensions,
                        statistic="Sum",
                        period=period,
                    )
                    for metric_name in ("Count", "4xx", "5xx")
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="API Latency",
                left=[
                    self._metric(
                        "AWS/ApiGateway",
                        "Latency",
                        api_dimensions,
                        statistic=statistic,
                        period=period,
                    )
                    for statistic in ("p95", "p99")
                ],
                width=12,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Queue Backlog and In-flight Messages",
                left=[
                    self._metric(
                        "AWS/SQS",
                        metric_name,
                        {"QueueName": queue_name},
                        statistic="Maximum",
                        period=period,
                        label=f"{queue_name} {metric_name}",
                    )
                    for queue_name in queue_names
                    for metric_name in (
                        "ApproximateNumberOfMessagesVisible",
                        "ApproximateNumberOfMessagesNotVisible",
                    )
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Queue Oldest Message Age",
                left=[
                    self._metric(
                        "AWS/SQS",
                        "ApproximateAgeOfOldestMessage",
                        {"QueueName": queue_name},
                        statistic="Maximum",
                        period=period,
                        label=queue_name,
                    )
                    for queue_name in queue_names
                ],
                width=12,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda Invocations, Errors, and Throttles",
                left=[
                    self._metric(
                        "AWS/Lambda",
                        metric_name,
                        {"FunctionName": function_name},
                        statistic="Sum",
                        period=period,
                        label=f"{function_name} {metric_name}",
                    )
                    for function_name in function_names
                    for metric_name in ("Invocations", "Errors", "Throttles")
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Lambda Duration and Concurrency",
                left=[
                    self._metric(
                        "AWS/Lambda",
                        "Duration",
                        {"FunctionName": function_name},
                        statistic="p95",
                        period=period,
                        label=f"{function_name} p95 duration",
                    )
                    for function_name in function_names
                ],
                right=[
                    self._metric(
                        "AWS/Lambda",
                        "ConcurrentExecutions",
                        {"FunctionName": function_name},
                        statistic="Maximum",
                        period=period,
                        label=f"{function_name} concurrency",
                    )
                    for function_name in function_names
                ],
                width=12,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Async State Table",
                left=[
                    self._metric(
                        "AWS/DynamoDB",
                        metric_name,
                        {"TableName": (f"{resource_prefix}-async-state-{environment}")},
                        statistic="Sum",
                        period=period,
                    )
                    for metric_name in (
                        "SystemErrors",
                        "UserErrors",
                        "ThrottledRequests",
                    )
                ],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Scheduled Worker Executions",
                left=[
                    self._metric(
                        "AWS/States",
                        metric_name,
                        {"StateMachineArn": state_machine_arn},
                        statistic="Sum",
                        period=period,
                        label=f"{metric_name} {state_machine_arn.rsplit(':', 1)[-1]}",
                    )
                    for state_machine_arn in state_machine_arns
                    for metric_name in (
                        "ExecutionsSucceeded",
                        "ExecutionsFailed",
                        "ExecutionsTimedOut",
                        "ExecutionsAborted",
                    )
                ],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Scheduled Worker Resources",
                left=[
                    self._metric(
                        "ECS/ContainerInsights",
                        metric_name,
                        {
                            "ClusterName": (
                                f"{resource_prefix}-scheduled-workers-{environment}"
                            )
                        },
                        statistic="Average",
                        period=period,
                    )
                    for metric_name in (
                        "CpuUtilized",
                        "MemoryUtilized",
                        "EphemeralStorageUtilized",
                    )
                ],
                width=8,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="NAT Gateway Health",
                left=[
                    self._metric(
                        "AWS/NATGateway",
                        metric_name,
                        {"NatGatewayId": nat_gateway_id},
                        statistic="Sum",
                        period=period,
                        label=f"{nat_gateway_id} {metric_name}",
                    )
                    for nat_gateway_id in nat_gateway_ids
                    for metric_name in (
                        "ErrorPortAllocation",
                        "PacketsDropCount",
                        "ConnectionAttemptCount",
                        "ConnectionEstablishedCount",
                    )
                ],
                width=12,
            ),
            cloudwatch.LogQueryWidget(
                title="Rejected VPC Flows",
                log_group_names=[f"/{resource_prefix}/network/vpc-flow-logs"],
                query_lines=[
                    "fields @timestamp, srcAddr, dstAddr, dstPort, protocol, action",
                    "filter action = 'REJECT'",
                    "sort @timestamp desc",
                    "limit 50",
                ],
                width=12,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.LogQueryWidget(
                title="Recent API and Worker Errors",
                log_group_names=[
                    f"/aws/apigateway/{resource_prefix}-{environment}",
                    f"/aws/lambda/{resource_prefix}-api-{environment}",
                    f"/aws/lambda/{resource_prefix}-response-worker-{environment}",
                    (
                        f"/plexus/score-processor/"
                        f"{resource_prefix}-scoring-{environment}"
                    ),
                ],
                query_lines=[
                    "fields @timestamp, @log, @message",
                    "filter @message like /(?i)(error|exception|failed)/",
                    "sort @timestamp desc",
                    "limit 100",
                ],
                width=24,
            )
        )

        alarm_action = cloudwatch_actions.SnsAction(alert_topic)
        for function_name in function_names:
            for metric_name in ("Errors", "Throttles"):
                alarm = cloudwatch.Alarm(
                    self,
                    f"{self._construct_id(function_name)}{metric_name}Alarm",
                    alarm_name=f"{function_name}-{metric_name.lower()}",
                    metric=self._metric(
                        "AWS/Lambda",
                        metric_name,
                        {"FunctionName": function_name},
                        statistic="Sum",
                        period=period,
                    ),
                    threshold=1,
                    evaluation_periods=1,
                    comparison_operator=(
                        cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
                    ),
                    treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                )
                alarm.add_alarm_action(alarm_action)

        self.dashboard = dashboard

    @staticmethod
    def _metric(
        namespace: str,
        metric_name: str,
        dimensions: dict[str, str],
        *,
        statistic: str,
        period: Duration,
        label: str | None = None,
    ) -> cloudwatch.Metric:
        return cloudwatch.Metric(
            namespace=namespace,
            metric_name=metric_name,
            dimensions_map=dimensions,
            statistic=statistic,
            period=period,
            label=label,
        )

    @staticmethod
    def _construct_id(value: str) -> str:
        return "".join(part.title() for part in value.replace("-", " ").split())
