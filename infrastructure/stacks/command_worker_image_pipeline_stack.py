"""Pipeline that publishes immutable portable command-worker images."""

import os

from aws_cdk import CfnOutput, Stack, Tags, aws_codebuild as codebuild, aws_codepipeline as codepipeline, aws_codepipeline_actions as actions, aws_ecr as ecr, aws_iam as iam, aws_ssm as ssm
from constructs import Construct

from .shared.constants import COMMAND_WORKER_REPOSITORY_BASE


class CommandWorkerImagePipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, environment: str, branch: str, github_owner: str = "AnthusAI", github_repo: str = "Plexus", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        region = kwargs.get("env").region if kwargs.get("env") else "us-west-2"
        Tags.of(self).add("Service", "command-worker-image")
        Tags.of(self).add("Environment", environment)
        connection_arn = os.environ.get("PLEXUS_GITHUB_CONNECTION_ARN") or ssm.StringParameter.value_for_string_parameter(self, "/plexus/github-connection-arn")
        repository = ecr.Repository.from_repository_name(self, "CommandWorkerRepository", repository_name=f"{COMMAND_WORKER_REPOSITORY_BASE}-{environment}")
        source = codepipeline.Artifact("SourceOutput")
        self.build_project = codebuild.PipelineProject(
            self, "BuildProject", project_name=f"plexus-command-worker-{environment}-image-build",
            environment=codebuild.BuildEnvironment(build_image=codebuild.LinuxBuildImage.STANDARD_7_0, privileged=True),
            environment_variables={"ECR_REPOSITORY_URI": codebuild.BuildEnvironmentVariable(value=repository.repository_uri)},
            build_spec=codebuild.BuildSpec.from_object({"version": "0.2", "phases": {"pre_build": {"commands": ["set -euo pipefail", "IMAGE_TAG=$(printf '%s' \"${CODEBUILD_RESOLVED_SOURCE_VERSION}\" | cut -c1-12)", f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin \"${{ECR_REPOSITORY_URI%%/*}}\"" ]}, "build": {"commands": ["docker buildx build --platform linux/amd64 --provenance=false --sbom=false --push -f plexus/command_worker/Dockerfile -t $ECR_REPOSITORY_URI:$IMAGE_TAG .", "IMAGE_DIGEST=$(aws ecr describe-images --repository-name ${ECR_REPOSITORY_URI##*/} --image-ids imageTag=$IMAGE_TAG --query 'imageDetails[0].imageDigest' --output text)", "printf '{\"imageUri\":\"%s@%s\",\"imageTag\":\"%s\",\"imageDigest\":\"%s\"}\\n' $ECR_REPOSITORY_URI $IMAGE_DIGEST $IMAGE_TAG $IMAGE_DIGEST > image-detail.json"]}}, "artifacts": {"files": ["image-detail.json"]}}),
        )
        repository.grant_pull_push(self.build_project)
        self.build_project.add_to_role_policy(iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"]))
        self.pipeline = codepipeline.Pipeline(self, "Pipeline", pipeline_name=f"plexus-command-worker-{environment}-image-pipeline", cross_account_keys=False, stages=[codepipeline.StageProps(stage_name="Source", actions=[actions.CodeStarConnectionsSourceAction(action_name="GitHub", owner=github_owner, repo=github_repo, branch=branch, output=source, connection_arn=connection_arn, trigger_on_push=False)]), codepipeline.StageProps(stage_name="Build", actions=[actions.CodeBuildAction(action_name="BuildAndPublishImage", project=self.build_project, input=source)])])
        CfnOutput(self, "RepositoryUri", value=repository.repository_uri)
        CfnOutput(self, "PipelineName", value=self.pipeline.pipeline_name)
