import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest
from aws_cdk import Duration
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager

from plexus.infrastructure.constructs import AsyncScoreProcessing
from plexus.infrastructure.constructs.async_score_processing import (
    AsyncScoreProcessingProps,
)


def _build_template():
    app = cdk.App()
    stack = cdk.Stack(
        app,
        "TestAsyncScoreProcessing",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    repository = ecr.Repository.from_repository_name(
        stack,
        "ImageRepository",
        repository_name="plexus/score-processor-artifacts-development",
    )
    secret = secretsmanager.Secret.from_secret_name_v2(
        stack,
        "RuntimeConfig",
        secret_name="plexus/development/config",
    )
    construct = AsyncScoreProcessing(
        stack,
        "AsyncScoreProcessing",
        props=AsyncScoreProcessingProps(
            resource_prefix="plexus-development-scoring",
            environment_name="development",
            image_repository=repository,
            image_tag_or_digest="sha256:1234567890abcdef",
            runtime_config_secret=secret,
            reserved_concurrency=25,
            max_event_source_concurrency=10,
            visibility_timeout=Duration.seconds(1800),
            environment_variables={"CUSTOM_MODE": "enabled"},
            bedrock_model_resources=[
                "arn:aws:bedrock:*::foundation-model/*",
            ],
            additional_policy_statements=[
                iam.PolicyStatement(
                    actions=["s3:GetObject"],
                    resources=["arn:aws:s3:::example-bucket/*"],
                )
            ],
        ),
    )
    return assertions.Template.from_stack(stack), construct


def test_construct_creates_standard_request_and_response_queues_with_dlqs():
    template, _ = _build_template()

    template.resource_count_is("AWS::SQS::Queue", 4)
    for queue_name in [
        "plexus-development-scoring-standard-request-queue",
        "plexus-development-scoring-standard-request-dlq",
        "plexus-development-scoring-response-queue",
        "plexus-development-scoring-response-dlq",
    ]:
        template.has_resource_properties(
            "AWS::SQS::Queue",
            {
                "QueueName": queue_name,
                "SqsManagedSseEnabled": True,
            },
        )

    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "plexus-development-scoring-standard-request-queue",
            "VisibilityTimeout": 1800,
            "RedrivePolicy": assertions.Match.object_like(
                {
                    "maxReceiveCount": 3,
                }
            ),
        },
    )


def test_construct_retains_owned_queues_by_default():
    template, _ = _build_template()

    queues = template.find_resources("AWS::SQS::Queue")
    assert len(queues) == 4
    for queue in queues.values():
        assert queue["DeletionPolicy"] == "Retain"
        assert queue["UpdateReplacePolicy"] == "Retain"


def test_construct_creates_explicit_retained_log_group():
    template, _ = _build_template()

    template.has_resource(
        "AWS::Logs::LogGroup",
        {
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
            "Properties": {
                "LogGroupName": ("/plexus/score-processor/plexus-development-scoring"),
                "RetentionInDays": 30,
            },
        },
    )


def test_construct_rejects_visibility_shorter_than_six_lambda_timeouts():
    app = cdk.App()
    stack = cdk.Stack(app, "InvalidVisibility")
    repository = ecr.Repository.from_repository_name(
        stack,
        "ImageRepository",
        repository_name="plexus/score-processor-artifacts-development",
    )
    secret = secretsmanager.Secret.from_secret_name_v2(
        stack,
        "RuntimeConfig",
        secret_name="plexus/development/config",
    )

    with pytest.raises(ValueError, match="at least six times"):
        AsyncScoreProcessing(
            stack,
            "AsyncScoreProcessing",
            props=AsyncScoreProcessingProps(
                resource_prefix="plexus-development-scoring",
                environment_name="development",
                image_repository=repository,
                image_tag_or_digest="sha256:1234567890abcdef",
                runtime_config_secret=secret,
                lambda_timeout=Duration.seconds(300),
                visibility_timeout=Duration.seconds(300),
            ),
        )


def test_construct_creates_lambda_from_pinned_ecr_image():
    template, _ = _build_template()
    template_text = json.dumps(template.to_json())

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "plexus-development-scoring-score-processor",
            "MemorySize": 3008,
            "PackageType": "Image",
            "ReservedConcurrentExecutions": 25,
            "Timeout": 300,
        },
    )
    assert "sha256:1234567890abcdef" in template_text
    assert "latest" not in template_text


def test_construct_wires_lambda_environment_from_queues_and_secret_mapping():
    template, _ = _build_template()
    template_text = json.dumps(template.to_json())

    assert "PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL" in template_text
    assert "PLEXUS_RESPONSE_WORKER_QUEUE_URL" in template_text
    assert "PLEXUS_ACCOUNT_KEY" in template_text
    assert "PLEXUS_API_KEY" in template_text
    assert "PLEXUS_API_URL" in template_text
    assert "OPENAI_API_KEY" in template_text
    assert "CUSTOM_MODE" in template_text
    assert "enabled" in template_text
    assert "OPENBLAS_NUM_THREADS" in template_text
    assert "NUMEXPR_NUM_THREADS" in template_text


def test_construct_adds_sqs_event_source_with_concurrency_cap():
    template, _ = _build_template()

    template.has_resource_properties(
        "AWS::Lambda::EventSourceMapping",
        {
            "BatchSize": 1,
            "ScalingConfig": {"MaximumConcurrency": 10},
        },
    )


def test_construct_uses_scoped_iam_instead_of_broad_managed_policies():
    template, _ = _build_template()
    template_json = template.to_json()
    template_text = json.dumps(template_json)

    assert "AmazonDynamoDBFullAccess" not in template_text
    assert "AmazonS3FullAccess" not in template_text
    assert "AmazonSQSFullAccess" not in template_text
    assert "CloudWatchFullAccess" not in template_text
    assert "sqs:ReceiveMessage" in template_text
    assert "sqs:DeleteMessage" in template_text
    assert "sqs:SendMessage" in template_text
    assert "secretsmanager:GetSecretValue" in template_text
    assert "ecr:BatchGetImage" in template_text
    assert "bedrock:InvokeModel" in template_text
    assert "s3:GetObject" in template_text
    assert "arn:aws:s3:::example-bucket/*" in template_text


def test_construct_creates_dlq_visibility_alarms():
    template, _ = _build_template()

    template.resource_count_is("AWS::CloudWatch::Alarm", 2)
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "plexus-development-scoring-StandardRequestDeadLetterQueueAlarm",
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "EvaluationPeriods": 1,
            "Threshold": 1,
            "TreatMissingData": "notBreaching",
        },
    )
