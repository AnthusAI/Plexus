from pathlib import Path

import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest

from plexus.infrastructure.scoring_service import (
    ScoringServiceAsyncScoringStack,
    ScoringServiceContainerRepositoryStack,
    ScoringServiceIntegrationStack,
    ScoringServiceMonitoringStack,
    ScoringServiceNetworkStack,
    ScoringServiceOperationsStack,
    ScoringServiceRepositoryStack,
    ScoringServiceScheduledWorkersStack,
)


def test_scoring_service_platform_exports_complete_reusable_surface() -> None:
    assert ScoringServiceNetworkStack
    assert ScoringServiceOperationsStack
    assert ScoringServiceAsyncScoringStack
    assert ScoringServiceContainerRepositoryStack
    assert ScoringServiceRepositoryStack
    assert ScoringServiceIntegrationStack
    assert ScoringServiceScheduledWorkersStack
    assert ScoringServiceMonitoringStack


def test_container_repository_stack_uses_consumer_supplied_identity() -> None:
    app = cdk.App()
    stack = ScoringServiceContainerRepositoryStack(
        app,
        "ScoringRuntimeImages",
        repository_name="example-scoring-runtime-test",
        service_name="example-scoring-runtime",
        environment="test",
        output_export_name="example-scoring-runtime-test-repository-uri",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )

    template = assertions.Template.from_stack(stack)
    template.has_resource_properties(
        "AWS::ECR::Repository",
        {
            "RepositoryName": "example-scoring-runtime-test",
            "ImageScanningConfiguration": {"ScanOnPush": True},
            "ImageTagMutability": "IMMUTABLE_WITH_EXCLUSION",
        },
    )
    template.has_output(
        "RuntimeRepositoryUri",
        {"Export": {"Name": "example-scoring-runtime-test-repository-uri"}},
    )


def test_scoring_service_platform_contains_no_consumer_specific_values() -> None:
    source_root = (
        Path(__file__).resolve().parents[3]
        / "plexus"
        / "infrastructure"
        / "scoring_service"
    )
    source = "\n".join(
        path.read_text()
        for path in source_root.glob("*.py")
        if path.name != "__init__.py"
    )

    for forbidden_value in (
        "capacity-aqa",
        "Capacity AQA",
        "CAPACITY_AQA",
        "CALL_CRITERIA",
    ):
        assert forbidden_value not in source


def _async_stack(
    app: cdk.App,
    *,
    image_uri: str | None = None,
) -> ScoringServiceAsyncScoringStack:
    operations = ScoringServiceOperationsStack(
        app,
        "Operations",
        resource_prefix="example-scoring",
        environment="test",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    return ScoringServiceAsyncScoringStack(
        app,
        "AsyncScoring",
        resource_prefix="example-scoring",
        environment="test",
        score_processor_repository_name="plexus/score-processor-artifacts-test",
        score_processor_image_uri=image_uri,
        runtime_config_secret_name="example/test/runtime-config",
        alert_topic=operations.alert_topic,
        read_bucket_parameters={"Input": "/example/input-bucket"},
        read_write_bucket_parameters={"Output": "/example/output-bucket"},
        bucket_environment_variables={
            "Input": ("INPUT_BUCKET",),
            "Output": ("OUTPUT_BUCKET",),
        },
        secret_environment={"PLEXUS_API_KEY": "PLEXUS_API_KEY"},
        bedrock_model_resources=[
            "arn:aws:bedrock:*::foundation-model/*",
        ],
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )


def test_async_scoring_stack_requires_deploy_time_immutable_image() -> None:
    stack = _async_stack(cdk.App())
    template = assertions.Template.from_stack(stack)

    template.has_parameter(
        "ScoreProcessorImageUri",
        {
            "Type": "String",
            "AllowedPattern": r"^.+@sha256:[0-9a-f]{64}$",
        },
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Code": {"ImageUri": {"Ref": "ScoreProcessorImageUri"}}},
    )
    assert "ScoreProcessorImageUriParameterName" not in template.to_json()["Outputs"]


def test_async_scoring_stack_accepts_only_digest_image_uris() -> None:
    digest_uri = (
        "123456789012.dkr.ecr.us-east-1.amazonaws.com/"
        "plexus/score-processor-artifacts-test@sha256:"
        + "a" * 64
    )
    stack = _async_stack(cdk.App(), image_uri=digest_uri)
    assertions.Template.from_stack(stack).has_resource_properties(
        "AWS::Lambda::Function",
        {"Code": {"ImageUri": digest_uri}},
    )

    with pytest.raises(ValueError, match="immutable sha256 digest"):
        _async_stack(cdk.App(), image_uri="repository:latest")


def test_reusable_platform_stacks_synthesize_with_consumer_configuration() -> None:
    app = cdk.App()
    env = cdk.Environment(account="123456789012", region="us-east-1")
    network = ScoringServiceNetworkStack(
        app,
        "Network",
        resource_prefix="example-scoring",
        display_name="Example Scoring",
        environment="test",
        availability_zones=("us-east-1a", "us-east-1b"),
        env=env,
    )
    operations = ScoringServiceOperationsStack(
        app,
        "PlatformOperations",
        resource_prefix="example-scoring",
        environment="test",
        env=env,
    )
    async_scoring = ScoringServiceAsyncScoringStack(
        app,
        "PlatformAsyncScoring",
        resource_prefix="example-scoring",
        environment="test",
        score_processor_repository_name="plexus/score-processor-artifacts-test",
        score_processor_image_uri=None,
        runtime_config_secret_name="example/test/runtime-config",
        alert_topic=operations.alert_topic,
        read_bucket_parameters={},
        read_write_bucket_parameters={},
        bucket_environment_variables={},
        secret_environment={},
        bedrock_model_resources=[],
        env=env,
    )
    ScoringServiceRepositoryStack(
        app,
        "Repository",
        resource_prefix="example-scoring",
        environment="test",
        env=env,
    )
    integration = ScoringServiceIntegrationStack(
        app,
        "Integration",
        resource_prefix="example-scoring",
        display_name="Example Scoring",
        environment="test",
        response_destination="object-store",
        response_worker_requires_sql_egress=False,
        vpc=network.vpc,
        serverless_runtime_image_tag="bootstrap",
        api_handler_command=("consumer.api.handler",),
        response_worker_handler_command=("consumer.response.handler",),
        health_route_path="/health",
        prediction_route_path="/score/{request_id}",
        scoring_scope_description="Submit scoring requests",
        standard_request_queue=async_scoring.queues.request_queue,
        response_queue=async_scoring.queues.response_queue,
        runtime_config_secret_name="example/test/runtime-config",
        read_bucket_parameters={},
        read_write_bucket_parameters={},
        bucket_environment_variables={},
        runtime_environment={"CONSUMER_ENVIRONMENT": "test"},
        state_table_environment_variable="REQUEST_STATE_TABLE",
        response_destination_environment_variable="RESPONSE_DESTINATION",
        runtime_secret_id_environment_variable="RUNTIME_SECRET_ID",
        verification_scope_name=None,
        alert_topic=operations.alert_topic,
        env=env,
    )
    scheduled = ScoringServiceScheduledWorkersStack(
        app,
        "ScheduledWorkers",
        resource_prefix="example-scoring",
        display_name="Example Scoring",
        environment="test",
        vpc=network.vpc,
        worker_definitions=(),
        runtime_config_secret_name="example/test/runtime-config",
        base_environment={"CONSUMER_ENVIRONMENT": "test"},
        worker_type_environment_variable="WORKER_TYPE",
        required_environment_variable_list_name="REQUIRED_ENVIRONMENT",
        worker_type_tag_key="ScheduledWorkerType",
        alert_topic=operations.alert_topic,
        alert_key=operations.alert_key,
        env=env,
    )
    monitoring = ScoringServiceMonitoringStack(
        app,
        "Monitoring",
        resource_prefix="example-scoring",
        display_name="Example Scoring",
        dashboard_name_prefix="ExampleScoring",
        environment="test",
        alert_topic=operations.alert_topic,
        api_id=integration.api.api_id,
        nat_gateway_ids=network.nat_gateway_ids,
        state_machine_arns=[
            machine.state_machine_arn for machine in scheduled.state_machines
        ],
        env=env,
    )

    assembly = app.synth()
    assert assembly.get_stack_by_name(network.stack_name)
    assert assembly.get_stack_by_name(integration.stack_name)
    assert assembly.get_stack_by_name(monitoring.stack_name)
