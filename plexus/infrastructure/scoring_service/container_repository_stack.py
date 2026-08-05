from __future__ import annotations

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, Tags, aws_ecr as ecr
from constructs import Construct


class ScoringServiceContainerRepositoryStack(Stack):
    """A reusable ECR repository for a consumer-owned scoring runtime."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        repository_name: str,
        service_name: str,
        environment: str,
        output_export_name: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        for property_name, value in (
            ("repository_name", repository_name),
            ("service_name", service_name),
            ("environment", environment),
        ):
            if not value.strip():
                raise ValueError(f"{property_name} must not be empty")

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", service_name)
        Tags.of(self).add("Environment", environment)

        self.repository = ecr.Repository(
            self,
            "RuntimeRepository",
            repository_name=repository_name,
            image_scan_on_push=True,
            image_tag_mutability=ecr.TagMutability.IMMUTABLE_WITH_EXCLUSION,
            image_tag_mutability_exclusion_filters=[
                ecr.ImageTagMutabilityExclusionFilter.wildcard("buildcache")
            ],
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Expire superseded BuildKit cache manifests",
                    tag_status=ecr.TagStatus.UNTAGGED,
                    max_image_age=Duration.days(7),
                ),
                ecr.LifecycleRule(max_image_count=25),
            ],
            removal_policy=RemovalPolicy.RETAIN,
        )

        output = CfnOutput(
            self,
            "RuntimeRepositoryUri",
            value=self.repository.repository_uri,
        )
        if output_export_name is not None:
            if not output_export_name.strip():
                raise ValueError("output_export_name must not be empty when provided")
            output.export_name = output_export_name
