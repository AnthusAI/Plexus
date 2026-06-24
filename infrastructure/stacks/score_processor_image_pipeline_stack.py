"""
Pipeline for building the Lambda score processor image.

This is intentionally separate from the broader legacy infrastructure pipeline so
we can restore scoring capacity without recreating unrelated infrastructure.
"""

import os

from aws_cdk import (
    CfnOutput,
    Stack,
    Tags,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_ssm as ssm,
)
from constructs import Construct

from .shared.constants import LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE


class ScoreProcessorImagePipelineStack(Stack):
    """Manually triggered pipeline that builds and pushes the score processor image."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        branch: str,
        github_owner: str = "AnthusAI",
        github_repo: str = "Plexus",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = kwargs.get("env").region if kwargs.get("env") else "us-west-2"
        account = kwargs.get("env").account if kwargs.get("env") else "*"

        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Service", "score-processor-image")
        Tags.of(self).add("ManagedBy", "CDK")

        connection_arn = (
            os.environ.get("PLEXUS_GITHUB_CONNECTION_ARN")
            or ssm.StringParameter.value_for_string_parameter(
                self,
                "/plexus/github-connection-arn",
            )
        )

        repository_name = f"{LAMBDA_SCORE_PROCESSOR_REPOSITORY_BASE}-{environment}"
        repository = ecr.Repository.from_repository_name(
            self,
            "ScoreProcessorRepository",
            repository_name=repository_name,
        )

        source_output = codepipeline.Artifact("SourceOutput")

        build_project = codebuild.PipelineProject(
            self,
            "BuildProject",
            project_name=f"plexus-score-processor-{environment}-image-build",
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,
            ),
            environment_variables={
                "IMAGE_ALIAS": codebuild.BuildEnvironmentVariable(value=environment),
                "ECR_REPOSITORY_URI": codebuild.BuildEnvironmentVariable(
                    value=repository.repository_uri,
                ),
            },
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "env": {
                    "shell": "bash",
                },
                "phases": {
                    "pre_build": {
                        "commands": [
                            "set -euo pipefail",
                            "DOCKERFILE=score-processor-lambda/Dockerfile",
                            "IMAGE_TAG=$(printf '%s' \"${CODEBUILD_RESOLVED_SOURCE_VERSION:-${CODEBUILD_SOURCE_VERSION:-manual}}\" | cut -c1-12)",
                            "if [ -z \"$IMAGE_TAG\" ]; then IMAGE_TAG=$(date +%Y%m%d%H%M%S); fi",
                            "if grep -q '^FROM python:' \"$DOCKERFILE\"; then sed -i 's#^FROM python:#FROM public.ecr.aws/docker/library/python:#' \"$DOCKERFILE\"; fi",
                            "if aws secretsmanager describe-secret --secret-id dockerhub-credentials >/dev/null 2>&1; then "
                            "export DOCKERHUB_USERNAME=$(aws secretsmanager get-secret-value --secret-id dockerhub-credentials --query SecretString --output text | jq -r .username); "
                            "export DOCKERHUB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id dockerhub-credentials --query SecretString --output text | jq -r .password); "
                            "echo \"$DOCKERHUB_PASSWORD\" | docker login --username \"$DOCKERHUB_USERNAME\" --password-stdin; "
                            "else echo 'Docker Hub credentials not found; using public ECR base image'; fi",
                            f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin \"${{ECR_REPOSITORY_URI%%/*}}\"",
                        ]
                    },
                    "build": {
                        "commands": [
                            "docker buildx build --platform linux/amd64 --provenance=false --sbom=false --push "
                            "-f \"$DOCKERFILE\" "
                            "-t \"$ECR_REPOSITORY_URI:latest\" "
                            "-t \"$ECR_REPOSITORY_URI:$IMAGE_ALIAS\" "
                            "-t \"$ECR_REPOSITORY_URI:$IMAGE_TAG\" .",
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "IMAGE_URI=\"$ECR_REPOSITORY_URI:$IMAGE_TAG\"",
                            "printf '{\"imageUri\":\"%s\",\"imageTag\":\"%s\",\"latestUri\":\"%s\"}\\n' \"$IMAGE_URI\" \"$IMAGE_TAG\" \"$ECR_REPOSITORY_URI:latest\" > image-detail.json",
                        ]
                    },
                },
                "artifacts": {
                    "files": ["image-detail.json"],
                },
            }),
        )

        repository.grant_pull_push(build_project)
        build_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )
        build_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:DescribeSecret",
                    "secretsmanager:GetSecretValue",
                ],
                resources=[f"arn:aws:secretsmanager:{region}:{account}:secret:dockerhub-credentials-*"],
            )
        )

        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=f"plexus-score-processor-{environment}-image-pipeline",
            cross_account_keys=False,
            stages=[
                codepipeline.StageProps(
                    stage_name="Source",
                    actions=[
                        codepipeline_actions.CodeStarConnectionsSourceAction(
                            action_name="GitHub",
                            owner=github_owner,
                            repo=github_repo,
                            branch=branch,
                            output=source_output,
                            connection_arn=connection_arn,
                            trigger_on_push=False,
                        )
                    ],
                ),
                codepipeline.StageProps(
                    stage_name="Build",
                    actions=[
                        codepipeline_actions.CodeBuildAction(
                            action_name="BuildAndPublishImage",
                            project=build_project,
                            input=source_output,
                        )
                    ],
                ),
            ],
        )

        self.pipeline = pipeline
        self.build_project = build_project

        CfnOutput(self, "ScoreProcessorRepositoryUri", value=repository.repository_uri)
        CfnOutput(self, "PipelineName", value=pipeline.pipeline_name)
        CfnOutput(self, "BuildProjectName", value=build_project.project_name)
