"""Stable VPC and image-repository foundations for long-lived services."""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
    Tags,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_ssm as ssm,
)
from constructs import Construct

from .vpc import build_service_vpc


@dataclass(frozen=True)
class ServiceNetworkSettings:
    """The only supported long-lived service-network environments."""

    environment: str
    cidr: str


_ENVIRONMENTS = {
    "production": ServiceNetworkSettings("production", "10.60.0.0/20"),
    "staging": ServiceNetworkSettings("staging", "10.60.16.0/20"),
}
_ENVIRONMENT_ALIASES = {
    "main": "production",
    "production": "production",
    "staging": "staging",
}


def resolve_service_network_environment(value: str) -> ServiceNetworkSettings:
    """Resolve a deployment branch/environment without permitting cross-environment use."""

    normalized = value.strip().casefold()
    target = _ENVIRONMENT_ALIASES.get(normalized)
    if target is None:
        raise ValueError(
            "service-network foundations support only main/production or staging"
        )
    return _ENVIRONMENTS[target]


class ServiceNetworkFoundationStack(Stack):
    """Own stable, service-neutral VPC and immutable worker-image primitives.

    Application stacks import the SSM/CloudFormation contract rather than owning
    NAT gateways or an ECR repository.  This keeps ordinary application releases
    from replacing network resources.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        service_prefix: str,
        environment: str,
        amplify_deployment_role_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        if not service_prefix.strip():
            raise ValueError("service_prefix must not be empty")
        if not amplify_deployment_role_arn.strip():
            raise ValueError("amplify_deployment_role_arn must not be empty")
        settings = resolve_service_network_environment(environment)
        prefix = service_prefix.strip().casefold()
        self.environment_name = settings.environment
        self.service_prefix = prefix
        self.contract_prefix = f"/{prefix}/{settings.environment}/command-service"
        export_prefix = f"{prefix}-{settings.environment}-command-service"

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", prefix)
        Tags.of(self).add("Environment", settings.environment)

        self.vpc, self.flow_log_group = build_service_vpc(
            self,
            cidr=settings.cidr,
            max_azs=2,
            availability_zones=None,
            nat_gateways=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private-egress",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )
        self.worker_image_repository = ecr.Repository(
            self,
            "CommandWorkerImageRepository",
            image_scan_on_push=True,
            image_tag_mutability=ecr.TagMutability.IMMUTABLE,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=20)],
            removal_policy=RemovalPolicy.RETAIN,
        )
        # The Amplify role is owned outside this stack.  CDK intentionally makes
        # an imported role immutable, so ``add_to_principal_policy`` and ECR
        # grants silently do not produce a deployable policy.  Attach a separate
        # inline policy by role name instead.  This is still scoped to the
        # environment's contract parameters and image repository.
        deployment_role = iam.Role.from_role_arn(
            self, "AmplifyDeploymentRole", amplify_deployment_role_arn, mutable=False
        )
        iam.CfnPolicy(
            self,
            "AmplifyCommandServiceAccess",
            policy_name=f"{prefix}-{settings.environment}-command-service-amplify",
            roles=[deployment_role.role_name],
            policy_document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["ssm:GetParameter"],
                        resources=[
                            self.format_arn(
                                service="ssm",
                                resource="parameter",
                                resource_name=f"{prefix}/{settings.environment}/command-service/*",
                            )
                        ],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:CompleteLayerUpload",
                            "ecr:DescribeImages",
                            "ecr:InitiateLayerUpload",
                            "ecr:PutImage",
                            "ecr:UploadLayerPart",
                        ],
                        resources=[self.worker_image_repository.repository_arn],
                    ),
                    iam.PolicyStatement(
                        actions=["ecr:GetAuthorizationToken"], resources=["*"]
                    ),
                ]
            ),
        )

        private_subnet_ids = ",".join(
            subnet.subnet_id for subnet in self.vpc.private_subnets
        )
        availability_zones = ",".join(self.vpc.availability_zones)
        self.contract_parameters = {
            "vpc_id": ssm.StringParameter(
                self,
                "VpcIdParameter",
                parameter_name=f"{self.contract_prefix}/vpc-id",
                string_value=self.vpc.vpc_id,
            ),
            "availability_zones": ssm.StringParameter(
                self,
                "AvailabilityZonesParameter",
                parameter_name=f"{self.contract_prefix}/availability-zones",
                string_value=availability_zones,
            ),
            "private_subnet_ids": ssm.StringParameter(
                self,
                "PrivateSubnetIdsParameter",
                parameter_name=f"{self.contract_prefix}/private-subnet-ids",
                string_value=private_subnet_ids,
            ),
            "worker_image_repository_uri": ssm.StringParameter(
                self,
                "WorkerImageRepositoryUriParameter",
                parameter_name=f"{self.contract_prefix}/worker-image-repository-uri",
                string_value=self.worker_image_repository.repository_uri,
            ),
            "worker_image_repository_arn": ssm.StringParameter(
                self,
                "WorkerImageRepositoryArnParameter",
                parameter_name=f"{self.contract_prefix}/worker-image-repository-arn",
                string_value=self.worker_image_repository.repository_arn,
            ),
        }
        outputs = (
            ("VpcId", self.vpc.vpc_id, "vpc-id"),
            ("AvailabilityZones", availability_zones, "availability-zones"),
            ("PrivateSubnetIds", private_subnet_ids, "private-subnet-ids"),
            (
                "WorkerImageRepositoryUri",
                self.worker_image_repository.repository_uri,
                "worker-image-repository-uri",
            ),
            (
                "WorkerImageRepositoryArn",
                self.worker_image_repository.repository_arn,
                "worker-image-repository-arn",
            ),
        )
        for construct_name, value, suffix in outputs:
            CfnOutput(
                self,
                construct_name,
                value=value,
                export_name=f"{export_prefix}-{suffix}",
            )
