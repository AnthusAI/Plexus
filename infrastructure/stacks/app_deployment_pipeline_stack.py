"""
Stack for Plexus application deployment pipeline.

This stack creates a CodePipeline that deploys Plexus application code to EC2 instances
using CodeDeploy. Unlike the infrastructure pipeline's broken post-deploy step, this
uses native CodeDeployServerDeployAction which properly waits for deployment completion.

This stack is self-contained and creates its own CodeDeploy application and deployment group.
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

    This stack creates its own CodeDeploy resources for clean separation.
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

        # Create CodeDeploy service role
        codedeploy_service_role = iam.Role(
            self,
            "CodeDeployServiceRole",
            role_name=get_resource_name("app-deploy", environment, "codedeploy-role"),
            assumed_by=iam.ServicePrincipal("codedeploy.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSCodeDeployRole")
            ]
        )

        # Create EC2 instance role (or reference existing one)
        # This role is attached to EC2 instances and allows them to pull from S3, run SSM commands, etc.
        ec2_role = iam.Role(
            self,
            "EC2InstanceRole",
            role_name=get_resource_name("app-deploy", environment, "ec2-role"),
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeDeployFullAccess")
            ]
        )

        # Create CodeDeploy Application
        codedeploy_app = codedeploy.ServerApplication(
            self,
            "CodeDeployApp",
            application_name=get_resource_name("app-deploy", environment, "app")
        )

        # Create CodeDeploy Deployment Group
        codedeploy_group = codedeploy.ServerDeploymentGroup(
            self,
            "CodeDeployGroup",
            application=codedeploy_app,
            deployment_group_name=get_resource_name("app-deploy", environment, "group"),
            install_agent=True,
            ec2_instance_tags=codedeploy.InstanceTagSet({
                "Environment": [environment]
            }),
            role=codedeploy_service_role,
            deployment_config=codedeploy.ServerDeploymentConfig.ALL_AT_ONCE,
            ignore_poll_alarms_failure=False,
            auto_rollback=codedeploy.AutoRollbackConfig(
                failed_deployment=True,
                stopped_deployment=True,
                deployment_in_alarm=False
            )
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
                            "echo 'Deployment bundle created successfully'"
                        ]
                    }
                },
                "artifacts": {
                    "files": ["**/*"],
                    "exclude-paths": [
                        ".git/**/*",
                        "node_modules/**/*",
                        ".venv/**/*",
                        "__pycache__/**/*",
                        "infrastructure/**/*",
                        "mlruns/**/*"
                    ]
                }
            })
        )

        # Create CodePipeline
        source_output = codepipeline.Artifact("SourceOutput")
        build_output = codepipeline.Artifact("BuildOutput")

        # Grant the deployment group's S3 bucket read access
        # This is needed for CodeDeploy to retrieve artifacts
        codedeploy_bucket_name = f"plexus-{environment}-code-deployments"

        pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=get_resource_name("app-deploy", environment, "pipeline"),
            cross_account_keys=False,  # Disable KMS encryption to avoid permission issues
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

        self.pipeline = pipeline
        self.codedeploy_app = codedeploy_app
        self.codedeploy_group = codedeploy_group
        self.ec2_role = ec2_role
