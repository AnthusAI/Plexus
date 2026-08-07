import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest

from plexus.infrastructure.service_network import (
    ServiceNetworkFoundationStack,
    resolve_service_network_environment,
)

ENV = cdk.Environment(account="123456789012", region="us-east-1")
ROLE_ARN = "arn:aws:iam::123456789012:role/amplify-deployment"


@pytest.mark.parametrize(
    ("source", "environment", "cidr"),
    [
        ("main", "production", "10.60.0.0/20"),
        ("production", "production", "10.60.0.0/20"),
        ("staging", "staging", "10.60.16.0/20"),
    ],
)
def test_long_lived_environment_mapping(source, environment, cidr) -> None:
    resolved = resolve_service_network_environment(source)
    assert resolved.environment == environment
    assert resolved.cidr == cidr


@pytest.mark.parametrize("value", ["", "development", "sandbox", "feature/foo"])
def test_long_lived_environment_mapping_rejects_unknown_environment(value) -> None:
    with pytest.raises(ValueError, match="main/production or staging"):
        resolve_service_network_environment(value)


def test_foundation_publishes_isolated_network_and_image_contract() -> None:
    app = cdk.App()
    stack = ServiceNetworkFoundationStack(
        app,
        "Foundation",
        service_prefix="plexus",
        environment="staging",
        amplify_deployment_role_arn=ROLE_ARN,
        env=ENV,
    )
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::EC2::VPC",
        {"CidrBlock": "10.60.16.0/20", "EnableDnsHostnames": True},
    )
    assert len(template.find_resources("AWS::EC2::NatGateway")) == 2
    template.has_resource_properties(
        "AWS::ECR::Repository",
        {
            "ImageTagMutability": "IMMUTABLE",
            "ImageScanningConfiguration": {"ScanOnPush": True},
        },
    )
    # The Amplify deployment role is imported and immutable.  Its grant must
    # therefore be a separately synthesized IAM policy, not a no-op CDK grant.
    policies = template.find_resources("AWS::IAM::Policy")
    amplify_policy = next(
        resource["Properties"]
        for resource in policies.values()
        if resource["Properties"].get("Roles") == ["amplify-deployment"]
    )
    statements = amplify_policy["PolicyDocument"]["Statement"]
    assert any("ssm:GetParameter" in statement["Action"] for statement in statements)
    ecr_actions = next(
        statement["Action"]
        for statement in statements
        if "ecr:PutImage" in statement["Action"]
    )
    assert {
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:DescribeImages",
    } <= set(ecr_actions)
    assert {
        "Action": "ecr:GetAuthorizationToken",
        "Effect": "Allow",
        "Resource": "*",
    } in statements
    parameters = template.find_resources("AWS::SSM::Parameter")
    assert {resource["Properties"]["Name"] for resource in parameters.values()} == {
        "/plexus/staging/command-service/vpc-id",
        "/plexus/staging/command-service/availability-zones",
        "/plexus/staging/command-service/private-subnet-ids",
        "/plexus/staging/command-service/worker-image-repository-uri",
        "/plexus/staging/command-service/worker-image-repository-arn",
    }
    outputs = template.to_json()["Outputs"]
    assert {output["Export"]["Name"] for output in outputs.values()} == {
        "plexus-staging-command-service-vpc-id",
        "plexus-staging-command-service-availability-zones",
        "plexus-staging-command-service-private-subnet-ids",
        "plexus-staging-command-service-worker-image-repository-uri",
        "plexus-staging-command-service-worker-image-repository-arn",
    }
