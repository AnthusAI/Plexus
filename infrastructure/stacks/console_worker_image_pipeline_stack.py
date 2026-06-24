"""
Stack for building the Amplify console worker image.

The pipeline builds the Lambda container image used by the Amplify Gen 2
ConsoleRunWorker stack, pushes it to ECR, and updates the matching Amplify
branch environment variable. It does not start an Amplify deployment.
"""

import os
from typing import Optional

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

from .shared.constants import CONSOLE_WORKER_REPOSITORY_BASE


class ConsoleWorkerImagePipelineStack(Stack):
    """
    CDK Stack for the console worker image build pipeline.

    Creates a manually triggered CodePipeline that:
    1. Sources code from GitHub via CodeConnection
    2. Builds and pushes the console worker Lambda image to ECR
    3. Updates CONSOLE_WORKER_IMAGE_URI on the matching Amplify branch
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        branch: str,
        github_owner: str = "AnthusAI",
        github_repo: str = "Plexus",
        amplify_app_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = kwargs.get("env").region if kwargs.get("env") else "us-west-2"
        account = kwargs.get("env").account if kwargs.get("env") else "*"

        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Service", "console-worker-image")
        Tags.of(self).add("ManagedBy", "CDK")

        connection_arn = (
            os.environ.get("PLEXUS_GITHUB_CONNECTION_ARN")
            or ssm.StringParameter.value_for_string_parameter(
                self,
                "/plexus/github-connection-arn",
            )
        )

        resolved_amplify_app_id = (
            amplify_app_id
            or os.environ.get("PLEXUS_AMPLIFY_APP_ID")
            or ssm.StringParameter.value_for_string_parameter(
                self,
                "/plexus/amplify-app-id",
            )
        )

        repository_name = f"{CONSOLE_WORKER_REPOSITORY_BASE}-{environment}"
        repository = ecr.Repository.from_repository_name(
            self,
            "ConsoleWorkerRepository",
            repository_name=repository_name,
        )

        source_output = codepipeline.Artifact("SourceOutput")

        build_project = codebuild.PipelineProject(
            self,
            "BuildProject",
            project_name=f"plexus-console-worker-{environment}-build",
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,
            ),
            environment_variables={
                "AMPLIFY_APP_ID": codebuild.BuildEnvironmentVariable(
                    value=resolved_amplify_app_id,
                ),
                "AMPLIFY_BRANCH": codebuild.BuildEnvironmentVariable(
                    value=branch,
                ),
                "IMAGE_ALIAS": codebuild.BuildEnvironmentVariable(
                    value=environment,
                ),
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
                            "DOCKERFILE=dashboard/amplify/functions/consoleRunWorker/Dockerfile",
                            "IMAGE_TAG=$(printf '%s' \"${CODEBUILD_RESOLVED_SOURCE_VERSION:-${CODEBUILD_SOURCE_VERSION:-manual}}\" | cut -c1-12)",
                            "if [ -z \"$IMAGE_TAG\" ]; then IMAGE_TAG=$(date +%Y%m%d%H%M%S); fi",
                            "if grep -q '^FROM python:' \"$DOCKERFILE\"; then sed -i 's#^FROM python:#FROM public.ecr.aws/docker/library/python:#' \"$DOCKERFILE\"; fi",
                            "if aws secretsmanager describe-secret --secret-id dockerhub-credentials >/dev/null 2>&1; then "
                            "export DOCKERHUB_USERNAME=$(aws secretsmanager get-secret-value --secret-id dockerhub-credentials --query SecretString --output text | jq -r .username); "
                            "export DOCKERHUB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id dockerhub-credentials --query SecretString --output text | jq -r .password); "
                            "echo \"$DOCKERHUB_PASSWORD\" | docker login --username \"$DOCKERHUB_USERNAME\" --password-stdin; "
                            "else echo 'Docker Hub credentials not found; continuing without Docker Hub login'; fi",
                            f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin \"${{ECR_REPOSITORY_URI%%/*}}\"",
                        ]
                    },
                    "build": {
                        "commands": [
                            "docker buildx build --platform linux/amd64 --provenance=false --sbom=false --push "
                            "-f \"$DOCKERFILE\" "
                            "-t \"$ECR_REPOSITORY_URI:$IMAGE_ALIAS\" "
                            "-t \"$ECR_REPOSITORY_URI:$IMAGE_TAG\" .",
                            "touch /tmp/console-worker-image-pushed",
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "[ -f /tmp/console-worker-image-pushed ] || { echo 'Skipping Amplify branch update because image build/push did not complete'; exit 1; }",
                            "IMAGE_URI=\"$ECR_REPOSITORY_URI:$IMAGE_TAG\"",
                            "CURRENT_ENV=$(aws amplify get-branch --app-id \"$AMPLIFY_APP_ID\" --branch-name \"$AMPLIFY_BRANCH\" --query 'branch.environmentVariables' --output json)",
                            "UPDATED_ENV=$(jq -cn --argjson env \"$CURRENT_ENV\" --arg image \"$IMAGE_URI\" '($env // {}) + {\"CONSOLE_WORKER_IMAGE_URI\": $image}')",
                            "aws amplify update-branch --app-id \"$AMPLIFY_APP_ID\" --branch-name \"$AMPLIFY_BRANCH\" --environment-variables \"$UPDATED_ENV\" >/tmp/amplify-update-branch.json",
                            "printf '{\"imageUri\":\"%s\",\"imageTag\":\"%s\"}\\n' \"$IMAGE_URI\" \"$IMAGE_TAG\" > image-detail.json",
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
        build_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "amplify:GetBranch",
                    "amplify:UpdateBranch",
                ],
                resources=[
                    f"arn:aws:amplify:{region}:{account}:apps/{resolved_amplify_app_id}",
                    f"arn:aws:amplify:{region}:{account}:apps/{resolved_amplify_app_id}/branches/{branch}",
                ],
            )
        )

        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=f"plexus-console-worker-{environment}-pipeline",
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

        CfnOutput(self, "ConsoleWorkerRepositoryUri", value=repository.repository_uri)
        CfnOutput(self, "PipelineName", value=pipeline.pipeline_name)
        CfnOutput(self, "BuildProjectName", value=build_project.project_name)
