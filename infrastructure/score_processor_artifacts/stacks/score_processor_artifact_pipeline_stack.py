from __future__ import annotations

import os

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
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


class ScoreProcessorArtifactPipelineStack(Stack):
    """Pipeline that publishes immutable score processor image artifacts."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        channel: str,
        branch: str,
        github_owner: str = "AnthusAI",
        github_repo: str = "Plexus",
        trigger_on_push: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.channel = channel
        region = self.region
        account = self.account

        Tags.of(self).add("Service", "score-processor-artifacts")
        Tags.of(self).add("ArtifactChannel", channel)
        Tags.of(self).add("ManagedBy", "CDK")

        connection_arn = (
            os.environ.get("PLEXUS_GITHUB_CONNECTION_ARN")
            or ssm.StringParameter.value_for_string_parameter(
                self,
                "/plexus/github-connection-arn",
            )
        )

        repository = ecr.Repository(
            self,
            "ScoreProcessorRepository",
            repository_name=f"plexus/score-processor-artifacts-{channel}",
            image_scan_on_push=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Retain recent score processor image artifacts",
                    max_image_count=100,
                    tag_prefix_list=["git-"],
                )
            ],
        )

        image_uri_parameter_name = (
            f"/plexus/score-processor-artifacts/{channel}/image-uri"
        )
        image_digest_parameter_name = (
            f"/plexus/score-processor-artifacts/{channel}/image-digest"
        )
        image_tag_parameter_name = (
            f"/plexus/score-processor-artifacts/{channel}/image-tag"
        )
        source_revision_parameter_name = (
            f"/plexus/score-processor-artifacts/{channel}/source-revision"
        )

        source_output = codepipeline.Artifact("SourceOutput")
        image_detail_output = codepipeline.Artifact("ImageDetailOutput")

        build_project = codebuild.PipelineProject(
            self,
            "BuildProject",
            project_name=f"plexus-score-processor-artifacts-{channel}-build",
            timeout=Duration.minutes(60),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,
            ),
            environment_variables={
                "ECR_REPOSITORY_NAME": codebuild.BuildEnvironmentVariable(
                    value=repository.repository_name
                ),
                "ECR_REPOSITORY_URI": codebuild.BuildEnvironmentVariable(
                    value=repository.repository_uri
                ),
                "IMAGE_URI_PARAMETER_NAME": codebuild.BuildEnvironmentVariable(
                    value=image_uri_parameter_name
                ),
                "IMAGE_DIGEST_PARAMETER_NAME": codebuild.BuildEnvironmentVariable(
                    value=image_digest_parameter_name
                ),
                "IMAGE_TAG_PARAMETER_NAME": codebuild.BuildEnvironmentVariable(
                    value=image_tag_parameter_name
                ),
                "SOURCE_REVISION_PARAMETER_NAME": (
                    codebuild.BuildEnvironmentVariable(
                        value=source_revision_parameter_name
                    )
                ),
            },
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "env": {"shell": "bash"},
                    "phases": {
                        "pre_build": {
                            "commands": [
                                "set -euo pipefail",
                                (
                                    "DOCKERFILE=score-processor-lambda/"
                                    "Dockerfile.scoring-runtime"
                                ),
                                "test -f \"$DOCKERFILE\"",
                                (
                                    "SOURCE_REVISION=\"${CODEBUILD_RESOLVED_SOURCE_VERSION:-"
                                    "${CODEBUILD_SOURCE_VERSION:-manual}}\""
                                ),
                                (
                                    "SHORT_REVISION=$(printf '%s' \"$SOURCE_REVISION\" "
                                    "| tr -cd '[:alnum:]' | cut -c1-12)"
                                ),
                                (
                                    "if [ -z \"$SHORT_REVISION\" ]; then "
                                    "SHORT_REVISION=$(date -u +%Y%m%d%H%M%S); fi"
                                ),
                                "IMAGE_TAG=\"git-${SHORT_REVISION}\"",
                                (
                                    "if grep -q '^FROM python:' \"$DOCKERFILE\"; then "
                                    "sed -i 's#^FROM python:#FROM public.ecr.aws/docker/library/python:#' "
                                    "\"$DOCKERFILE\"; fi"
                                ),
                                (
                                    f"aws ecr get-login-password --region {region} "
                                    "| docker login --username AWS --password-stdin "
                                    "\"${ECR_REPOSITORY_URI%%/*}\""
                                ),
                            ]
                        },
                        "build": {
                            "commands": [
                                (
                                    "docker buildx build --platform linux/amd64 "
                                    "--provenance=false --sbom=false --push "
                                    "-f \"$DOCKERFILE\" "
                                    "-t \"$ECR_REPOSITORY_URI:$IMAGE_TAG\" ."
                                )
                            ]
                        },
                        "post_build": {
                            "commands": [
                                (
                                    "IMAGE_DIGEST=$(aws ecr describe-images "
                                    "--repository-name \"$ECR_REPOSITORY_NAME\" "
                                    "--image-ids imageTag=\"$IMAGE_TAG\" "
                                    "--query 'imageDetails[0].imageDigest' "
                                    "--output text)"
                                ),
                                "IMAGE_URI=\"$ECR_REPOSITORY_URI@$IMAGE_DIGEST\"",
                                (
                                    "printf "
                                    "'{\"imageUri\":\"%s\",\"imageDigest\":\"%s\","
                                    "\"imageTag\":\"%s\",\"repositoryUri\":\"%s\","
                                    "\"sourceRevision\":\"%s\"}\\n' "
                                    "\"$IMAGE_URI\" \"$IMAGE_DIGEST\" \"$IMAGE_TAG\" "
                                    "\"$ECR_REPOSITORY_URI\" \"$SOURCE_REVISION\" "
                                    "> image-detail.json"
                                ),
                                (
                                    "aws ssm put-parameter --overwrite --type String "
                                    "--name \"$IMAGE_URI_PARAMETER_NAME\" --value \"$IMAGE_URI\""
                                ),
                                (
                                    "aws ssm put-parameter --overwrite --type String "
                                    "--name \"$IMAGE_DIGEST_PARAMETER_NAME\" "
                                    "--value \"$IMAGE_DIGEST\""
                                ),
                                (
                                    "aws ssm put-parameter --overwrite --type String "
                                    "--name \"$IMAGE_TAG_PARAMETER_NAME\" "
                                    "--value \"$IMAGE_TAG\""
                                ),
                                (
                                    "aws ssm put-parameter --overwrite --type String "
                                    "--name \"$SOURCE_REVISION_PARAMETER_NAME\" "
                                    "--value \"$SOURCE_REVISION\""
                                ),
                                "cat image-detail.json",
                            ]
                        },
                    },
                    "artifacts": {"files": ["image-detail.json"]},
                }
            ),
        )

        repository.grant_pull_push(build_project)
        build_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ecr:DescribeImages"],
                resources=[repository.repository_arn],
            )
        )
        build_project.add_to_role_policy(
            iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"])
        )
        build_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:PutParameter"],
                resources=[
                    (
                        f"arn:aws:ssm:{region}:{account}:parameter/plexus/"
                        f"score-processor-artifacts/{channel}/*"
                    )
                ],
            )
        )

        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=f"plexus-score-processor-artifacts-{channel}-pipeline",
            cross_account_keys=False,
            pipeline_type=codepipeline.PipelineType.V2,
        )
        pipeline.add_stage(
            stage_name="Source",
            actions=[
                codepipeline_actions.CodeStarConnectionsSourceAction(
                    action_name="GitHub",
                    owner=github_owner,
                    repo=github_repo,
                    branch=branch,
                    output=source_output,
                    connection_arn=connection_arn,
                    trigger_on_push=trigger_on_push,
                )
            ],
        )
        pipeline.add_stage(
            stage_name="Build",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="BuildAndPublishImage",
                    project=build_project,
                    input=source_output,
                    outputs=[image_detail_output],
                )
            ],
        )

        self.repository = repository
        self.pipeline = pipeline
        self.build_project = build_project

        CfnOutput(self, "RepositoryUri", value=repository.repository_uri)
        CfnOutput(self, "PipelineName", value=pipeline.pipeline_name)
        CfnOutput(self, "BuildProjectName", value=build_project.project_name)
        CfnOutput(self, "ImageUriParameterName", value=image_uri_parameter_name)
        CfnOutput(self, "ImageDigestParameterName", value=image_digest_parameter_name)
        CfnOutput(self, "ImageTagParameterName", value=image_tag_parameter_name)
        CfnOutput(
            self,
            "SourceRevisionParameterName",
            value=source_revision_parameter_name,
        )
