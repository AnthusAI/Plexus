"""
Stack for Plexus application deployment pipeline.

This stack creates a CodePipeline that deploys Plexus application code to EC2 instances
using CodeDeploy. Unlike the infrastructure pipeline's broken post-deploy step, this
uses native CodeDeployServerDeployAction which properly waits for deployment completion.
"""

import boto3
from aws_cdk import (
    Stack,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
    aws_codedeploy as codedeploy,
    aws_iam as iam,
    Tags,
)
from constructs import Construct
from .shared.naming import get_resource_name


class AppDeploymentPipelineStack(Stack):
    """
    CDK Stack for application deployment pipeline.

    Creates a CodePipeline that:
    1. Sources code from GitHub via CodeConnection
    2. Builds deployment bundle (code + deployment_artifacts)
    3. Deploys to EC2 using CodeDeploy with proper waiting
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        branch: str,
        github_owner: str = "AnthusAI",
        github_repo: str = "Plexus",
        **kwargs
    ) -> None:
        """
        Initialize the app deployment pipeline stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('staging' or 'production')
            branch: Git branch to watch ('staging' or 'main')
            github_owner: GitHub organization/owner name
            github_repo: GitHub repository name
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = environment
        self.branch = branch

        # Add environment tag to all resources in this stack
        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Service", "app-deployment")
        Tags.of(self).add("ManagedBy", "CDK")

        # Fetch GitHub CodeConnection ARN from SSM Parameter Store
        ssm = boto3.client('ssm', region_name=kwargs.get('env').region if kwargs.get('env') else 'us-west-2')
        try:
            response = ssm.get_parameter(Name='/plexus/github-connection-arn')
            connection_arn = response['Parameter']['Value']
        except Exception as e:
            raise ValueError(
                f"Failed to fetch GitHub connection ARN from SSM Parameter Store: {e}\n"
                "Create it with: aws ssm put-parameter --name /plexus/github-connection-arn "
                "--value 'arn:aws:codeconnections:us-west-2:ACCOUNT:connection/ID' --type String"
            )

        # Reference existing CodeDeploy application and deployment group
        # These are created by CodeDeployStack
        codedeploy_app_name = get_resource_name("code-deploy", environment, "app")
        codedeploy_group_name = get_resource_name("code-deploy", environment, "group")

        codedeploy_app = codedeploy.ServerApplication.from_server_application_name(
            self,
            "CodeDeployApp",
            server_application_name=codedeploy_app_name
        )

        codedeploy_group = codedeploy.ServerDeploymentGroup.from_server_deployment_group_attributes(
            self,
            "CodeDeployGroup",
            application=codedeploy_app,
            deployment_group_name=codedeploy_group_name
        )

        # Create CodeBuild project to prepare deployment bundle
        build_project = codebuild.PipelineProject(
            self,
            "BuildProject",
            project_name=get_resource_name("app-deploy", environment, "build"),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "build": {
                        "commands": [
                            # Create deployment bundle with code and deployment artifacts
                            "echo 'Creating deployment bundle...'",
                            # Copy deployment artifacts (appspec.yml and scripts) to root
                            "cp infrastructure/deployment_artifacts/appspec.yml .",
                            "cp -r infrastructure/deployment_artifacts/scripts .",
                            # Create zip with everything except infrastructure directory and build artifacts
                            "zip -r deployment.zip . -x '*.git*' -x '*node_modules*' -x '*.venv*' -x '*__pycache__*' -x 'infrastructure/*' -x 'mlruns/*'",
                            "echo 'Deployment bundle created successfully'"
                        ]
                    }
                },
                "artifacts": {
                    "files": ["deployment.zip"]
                }
            })
        )

        # Create CodePipeline
        source_output = codepipeline.Artifact("SourceOutput")
        build_output = codepipeline.Artifact("BuildOutput")

        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=get_resource_name("app-deploy", environment, "pipeline"),
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
                            trigger_on_push=False  # Triggered manually by GitHub Actions
                        )
                    ]
                ),
                codepipeline.StageProps(
                    stage_name="Build",
                    actions=[
                        codepipeline_actions.CodeBuildAction(
                            action_name="CreateDeploymentBundle",
                            project=build_project,
                            input=source_output,
                            outputs=[build_output]
                        )
                    ]
                ),
                codepipeline.StageProps(
                    stage_name="Deploy",
                    actions=[
                        codepipeline_actions.CodeDeployServerDeployAction(
                            action_name="DeployToEC2",
                            input=build_output,
                            deployment_group=codedeploy_group
                        )
                    ]
                )
            ]
        )

        # Grant pipeline role permission to read GitHub connection ARN
        pipeline.role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{kwargs.get('env').region if kwargs.get('env') else 'us-west-2'}:{kwargs.get('env').account if kwargs.get('env') else '*'}:parameter/plexus/github-connection-arn"]
            )
        )

        # Grant pipeline role permission to use CodeDeploy
        pipeline.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "codedeploy:GetDeploymentConfig",
                    "codedeploy:GetApplication",
                    "codedeploy:GetDeploymentGroup",
                    "codedeploy:GetDeployment",
                    "codedeploy:CreateDeployment",
                    "codedeploy:RegisterApplicationRevision"
                ],
                resources=["*"]
            )
        )

        self.pipeline = pipeline
