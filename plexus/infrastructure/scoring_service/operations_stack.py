from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
    Tags,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_kms as kms,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_ssm as ssm,
)
from constructs import Construct


class ScoringServiceOperationsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        environment: str,
        alert_email_parameter_name: str | None = None,
        release_pipeline_name: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not resource_prefix.strip():
            raise ValueError("resource_prefix must not be empty")
        release_pipeline_name = release_pipeline_name or (
            f"{resource_prefix}-release-pipeline-{environment}"
        )

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", f"{resource_prefix}-operations")
        Tags.of(self).add("Environment", environment)

        sns_key = kms.Key(
            self,
            "OperationsAlertsKey",
            alias=f"alias/{resource_prefix}-{environment}-operations-alerts",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        self.alert_key = sns_key
        for service_principal in (
            "cloudwatch.amazonaws.com",
            "events.amazonaws.com",
        ):
            sns_key.add_to_resource_policy(
                iam.PolicyStatement(
                    principals=[iam.ServicePrincipal(service_principal)],
                    actions=["kms:Decrypt", "kms:GenerateDataKey*"],
                    resources=["*"],
                )
            )
        self.alert_topic = sns.Topic(
            self,
            "OperationsAlertsTopic",
            topic_name=f"{resource_prefix}-{environment}-operations-alerts",
            master_key=sns_key,
        )
        self.alert_topic.apply_removal_policy(RemovalPolicy.RETAIN)

        if alert_email_parameter_name:
            alert_email = ssm.StringParameter.value_for_string_parameter(
                self,
                alert_email_parameter_name,
            )
            self.alert_topic.add_subscription(
                subscriptions.EmailSubscription(alert_email)
            )

        pipeline_failure_rule = events.Rule(
            self,
            "ReleasePipelineFailureRule",
            event_pattern=events.EventPattern(
                source=["aws.codepipeline"],
                detail_type=["CodePipeline Pipeline Execution State Change"],
                detail={
                    "pipeline": [release_pipeline_name],
                    "state": ["FAILED", "CANCELED", "SUPERSEDED"],
                },
            ),
        )
        pipeline_failure_rule.add_target(targets.SnsTopic(self.alert_topic))

        CfnOutput(
            self,
            "OperationsAlertsTopicArn",
            value=self.alert_topic.topic_arn,
            export_name=(
                f"{resource_prefix}-{environment}-operations-alerts-topic-arn"
            ),
        )
