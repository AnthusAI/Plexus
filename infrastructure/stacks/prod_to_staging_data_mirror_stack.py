"""CodeBuild job for mirroring Plexus production data into staging."""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_assets as s3_assets,
)
from constructs import Construct


class ProdToStagingDataMirrorStack(Stack):
    """Manual CodeBuild runner for destructive production-to-staging data refreshes."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_id: str = "d1vx7jva4xxlue",
        source_table_suffix: str = "xp6b4qnyovcjxh5p4yz57ygwku-NONE",
        target_table_suffix: str = "5urd722zufd3tj43kvbrlsrkjm-NONE",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = kwargs.get("env").region if kwargs.get("env") else "us-east-1"
        account = kwargs.get("env").account if kwargs.get("env") else "*"

        Tags.of(self).add("Service", "plexus-data-mirror")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("SourceEnvironment", "production")
        Tags.of(self).add("TargetEnvironment", "staging")

        run_log_bucket = s3.Bucket(
            self,
            "RunLogBucket",
            bucket_name=f"plexus-prod-to-staging-mirror-runs-{account}-{region}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireMirrorRunLogsAfter180Days",
                    enabled=True,
                    expiration=Duration.days(180),
                )
            ],
        )

        source_asset = s3_assets.Asset(
            self,
            "MirrorRunnerAsset",
            path="data_mirror",
        )

        project = codebuild.Project(
            self,
            "MirrorProject",
            project_name="plexus-prod-to-staging-data-mirror",
            description="Manual destructive mirror of Plexus main production data into staging",
            source=codebuild.Source.s3(
                bucket=source_asset.bucket,
                path=source_asset.s3_object_key,
            ),
            timeout=Duration.hours(8),
            queued_timeout=Duration.hours(1),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                compute_type=codebuild.ComputeType.LARGE,
            ),
            environment_variables={
                "AWS_REGION": codebuild.BuildEnvironmentVariable(value=region),
                "EXPECTED_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=account),
                "AMPLIFY_APP_ID": codebuild.BuildEnvironmentVariable(value=app_id),
                "SOURCE_TABLE_SUFFIX": codebuild.BuildEnvironmentVariable(value=source_table_suffix),
                "TARGET_TABLE_SUFFIX": codebuild.BuildEnvironmentVariable(value=target_table_suffix),
                "MIRROR_MODE": codebuild.BuildEnvironmentVariable(value="preflight"),
                "MIRROR_RUN_LOG_BUCKET": codebuild.BuildEnvironmentVariable(value=run_log_bucket.bucket_name),
            },
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "env": {"shell": "bash"},
                    "phases": {
                        "install": {
                            "commands": [
                                "set -euo pipefail",
                                "python3 --version",
                                "python3 -m pip install --upgrade pip",
                                "python3 -m pip install -r requirements.txt",
                            ]
                        },
                        "build": {
                            "commands": [
                                "set -euo pipefail",
                                "RUN_PREFIX=\"runs/${CODEBUILD_BUILD_ID//:/_}\"",
                                "set +e",
                                "python3 prod_to_staging_mirror.py 2>&1 | tee mirror.log",
                                "STATUS=${PIPESTATUS[0]}",
                                "set -e",
                                "aws s3 cp mirror.log \"s3://$MIRROR_RUN_LOG_BUCKET/$RUN_PREFIX/mirror.log\"",
                                "exit $STATUS",
                            ]
                        },
                    },
                    "artifacts": {"files": ["mirror.log"]},
                }
            ),
        )

        source_asset.grant_read(project)
        run_log_bucket.grant_read_write(project)

        table_resources = [
            f"arn:aws:dynamodb:{region}:{account}:table/*-{source_table_suffix}",
            f"arn:aws:dynamodb:{region}:{account}:table/*-{target_table_suffix}",
        ]
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:DescribeTable",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem",
                    "dynamodb:Query",
                ],
                resources=[table_resources[0]],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:DescribeTable",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem",
                    "dynamodb:Query",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:PutItem",
                    "dynamodb:DeleteItem",
                ],
                resources=[table_resources[1]],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(actions=["dynamodb:ListTables"], resources=["*"])
        )

        source_buckets = [
            "amplify-d1vx7jva4xxlue-ma-datasourcesbucketa1d38c0-memqyep8frdb",
            "amplify-d1vx7jva4xxlue-ma-reportblockdetailsbucket-gpos9qryoip8",
            "amplify-d1vx7jva4xxlue-ma-scoreresultattachmentsbu-tvxo9hgmmpjk",
            "amplify-d1vx7jva4xxlue-ma-taskattachmentsbucket5ce-lexp0hwtoiqu",
            "amplify-d1vx7jva4xxlue-ma-rubricmemorybucket827768-zkrpyuf8ec32",
        ]
        target_buckets = [
            "amplify-d1vx7jva4xxlue-st-datasourcesbucketa1d38c0-aq7wslsg1zlk",
            "amplify-d1vx7jva4xxlue-st-reportblockdetailsbucket-2zg0b5t0l0qt",
            "amplify-d1vx7jva4xxlue-st-scoreresultattachmentsbu-ou07sntftvd7",
            "amplify-d1vx7jva4xxlue-st-taskattachmentsbucket5ce-wap7oaygmo04",
            "amplify-d1vx7jva4xxlue-st-rubricmemorybucket827768-bs8rfrbij69y",
        ]
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket", "s3:GetBucketLocation"],
                resources=[f"arn:aws:s3:::{bucket}" for bucket in source_buckets + target_buckets],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:GetObjectTagging"],
                resources=[f"arn:aws:s3:::{bucket}/*" for bucket in source_buckets],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                ],
                resources=[f"arn:aws:s3:::{bucket}/*" for bucket in target_buckets],
            )
        )

        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:ListEventSourceMappings",
                    "lambda:GetEventSourceMapping",
                    "lambda:UpdateEventSourceMapping",
                ],
                resources=["*"],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:ListUserPools",
                    "cognito-idp:ListUsers",
                    "cognito-idp:DescribeUserPool",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminUpdateUserAttributes",
                ],
                resources=["*"],
            )
        )

        self.project = project
        self.run_log_bucket = run_log_bucket

        CfnOutput(self, "BuildProjectName", value=project.project_name)
        CfnOutput(self, "RunLogBucketName", value=run_log_bucket.bucket_name)
