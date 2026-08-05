from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_ecr as ecr,
)
from constructs import Construct


class ScoringServiceRepositoryStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        environment: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not resource_prefix.strip():
            raise ValueError("resource_prefix must not be empty")

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", f"{resource_prefix}-serverless-images")
        Tags.of(self).add("Environment", environment)

        self.repository = ecr.Repository(
            self,
            "ServerlessRuntimeRepository",
            repository_name=f"{resource_prefix}-serverless-runtime-{environment}",
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

        CfnOutput(
            self,
            "ServerlessRuntimeRepositoryUri",
            value=self.repository.repository_uri,
            export_name=(
                f"{resource_prefix}-serverless-runtime-{environment}-repository-uri"
            ),
        )
