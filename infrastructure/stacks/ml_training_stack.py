"""
ML Training Infrastructure Stack.

This stack provisions resources needed for ML model training:
- S3 bucket for training data and model artifacts
- IAM roles and policies for SageMaker training jobs
- Lifecycle policies for artifact retention

The bucket name follows the pattern: plexus-{environment}-training
For local development, use environment='development'
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    aws_s3 as s3,
    aws_iam as iam,
)
from constructs import Construct


class MLTrainingStack(Stack):
    """
    CDK Stack for ML training infrastructure.

    Creates S3 bucket and IAM resources needed for training ML models
    both locally and on SageMaker.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        **kwargs
    ) -> None:
        """
        Initialize the ML training stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('development', 'staging', 'production')
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment

        # Create S3 bucket for training artifacts
        self.training_bucket = self._create_training_bucket()

        # Create S3 bucket for inference/production models
        self.inference_bucket = self._create_inference_bucket()

        # Create IAM role for SageMaker training jobs
        self.sagemaker_training_role = self._create_sagemaker_training_role()

        # Create shared IAM role for SageMaker inference endpoints
        self.sagemaker_inference_role = self._create_sagemaker_inference_role()

        # Outputs
        self._create_outputs()

    def _create_training_bucket(self) -> s3.Bucket:
        """
        Create S3 bucket for storing training data and model artifacts.

        Bucket structure:
        - training-data/{scorecard_key}/{score_key}/data.csv
        - models/{scorecard_key}/{score_key}/model.tar.gz
        - training-code/{scorecard_key}/{score_key}/sourcedir.tar.gz

        Returns:
            S3 Bucket construct
        """
        bucket_name = f"plexus-{self.environment_name}-training"

        # For development, use shorter retention and easier cleanup
        # For production, use longer retention and stricter policies
        if self.environment_name == 'development':
            removal_policy = RemovalPolicy.DESTROY
            lifecycle_rules = [
                s3.LifecycleRule(
                    id="DeleteOldTrainingData",
                    enabled=True,
                    prefix="training-data/",
                    expiration=Duration.days(7)  # Keep training data for 7 days
                ),
                s3.LifecycleRule(
                    id="DeleteOldModels",
                    enabled=True,
                    prefix="models/",
                    expiration=Duration.days(30)  # Keep models for 30 days
                )
            ]
        else:
            removal_policy = RemovalPolicy.RETAIN
            lifecycle_rules = [
                s3.LifecycleRule(
                    id="TransitionOldTrainingData",
                    enabled=True,
                    prefix="training-data/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                ),
                s3.LifecycleRule(
                    id="TransitionOldModels",
                    enabled=True,
                    prefix="models/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ]

        bucket = s3.Bucket(
            self,
            "TrainingBucket",
            bucket_name=bucket_name,
            versioned=True,  # Keep version history for model artifacts
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=removal_policy,
            auto_delete_objects=(removal_policy == RemovalPolicy.DESTROY),
            lifecycle_rules=lifecycle_rules,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # Note: We don't add a bucket policy for SageMaker access here.
        # Instead, the SageMaker execution roles in the inference stacks
        # have IAM policies that grant them access to this bucket.
        # This avoids issues with service principals vs role ARNs in S3 requests.

        return bucket

    def _create_inference_bucket(self) -> s3.Bucket:
        """
        Create S3 bucket for storing production inference models.

        This bucket is separate from the training bucket to keep production
        models stable during training iterations.

        Bucket structure:
        - models/{scorecard_key}/{score_key}/{version_id}/model.tar.gz

        Returns:
            S3 Bucket construct
        """
        bucket_name = f"plexus-{self.environment_name}-inference"

        # For development, use shorter retention and easier cleanup
        # For production, use longer retention and stricter policies
        if self.environment_name == 'development':
            removal_policy = RemovalPolicy.DESTROY
            lifecycle_rules = [
                s3.LifecycleRule(
                    id="DeleteOldModels",
                    enabled=True,
                    prefix="models/",
                    expiration=Duration.days(30)  # Keep models for 30 days
                )
            ]
        else:
            removal_policy = RemovalPolicy.RETAIN
            lifecycle_rules = [
                s3.LifecycleRule(
                    id="TransitionOldModels",
                    enabled=True,
                    prefix="models/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ]

        bucket = s3.Bucket(
            self,
            "InferenceBucket",
            bucket_name=bucket_name,
            versioned=True,  # Keep version history for model artifacts
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=removal_policy,
            auto_delete_objects=(removal_policy == RemovalPolicy.DESTROY),
            lifecycle_rules=lifecycle_rules,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        return bucket

    def _create_sagemaker_training_role(self) -> iam.Role:
        """
        Create IAM role for SageMaker training jobs.

        This role allows SageMaker to:
        - Read training data from S3
        - Write model artifacts to S3
        - Write logs to CloudWatch

        Returns:
            IAM Role construct
        """
        role = iam.Role(
            self,
            "SageMakerTrainingRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            description=f"Role for SageMaker training jobs in {self.environment_name}",
            managed_policies=[
                # Basic SageMaker permissions
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                )
            ],
            inline_policies={
                "TrainingBucketAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                            ],
                            resources=[
                                self.training_bucket.bucket_arn,
                                f"{self.training_bucket.bucket_arn}/*",
                            ],
                        )
                    ]
                )
            },
        )

        return role

    def _create_sagemaker_inference_role(self) -> iam.Role:
        """
        Create shared IAM role for SageMaker inference endpoints.

        This role is used by all SageMaker inference endpoints to:
        - Read model artifacts from the inference bucket
        - Write logs to CloudWatch

        Creating one shared role instead of per-endpoint roles:
        - Avoids IAM propagation delays
        - Simplifies permission management
        - Reduces infrastructure overhead

        Returns:
            IAM Role construct
        """
        role = iam.Role(
            self,
            "SageMakerInferenceRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            description=f"Shared role for SageMaker inference endpoints in {self.environment_name}",
            managed_policies=[
                # Basic SageMaker permissions
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                )
            ],
            inline_policies={
                "InferenceBucketAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3:GetObject",
                                "s3:ListBucket",
                            ],
                            resources=[
                                self.inference_bucket.bucket_arn,
                                f"{self.inference_bucket.bucket_arn}/*",
                            ],
                        )
                    ]
                )
            },
        )

        return role

    def _create_outputs(self):
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "TrainingBucketName",
            value=self.training_bucket.bucket_name,
            description="S3 bucket for training data and model artifacts",
            export_name=f"plexus-{self.environment_name}-training-bucket-name"
        )

        CfnOutput(
            self,
            "TrainingBucketArn",
            value=self.training_bucket.bucket_arn,
            description="ARN of the training bucket",
            export_name=f"plexus-{self.environment_name}-training-bucket-arn"
        )

        CfnOutput(
            self,
            "InferenceBucketName",
            value=self.inference_bucket.bucket_name,
            description="S3 bucket for production inference models",
            export_name=f"plexus-{self.environment_name}-inference-bucket-name"
        )

        CfnOutput(
            self,
            "InferenceBucketArn",
            value=self.inference_bucket.bucket_arn,
            description="ARN of the inference bucket",
            export_name=f"plexus-{self.environment_name}-inference-bucket-arn"
        )

        CfnOutput(
            self,
            "SageMakerTrainingRoleArn",
            value=self.sagemaker_training_role.role_arn,
            description="IAM role for SageMaker training jobs",
            export_name=f"plexus-{self.environment_name}-sagemaker-training-role-arn"
        )

        CfnOutput(
            self,
            "SageMakerInferenceRoleArn",
            value=self.sagemaker_inference_role.role_arn,
            description="Shared IAM role for SageMaker inference endpoints",
            export_name=f"plexus-{self.environment_name}-sagemaker-inference-role-arn"
        )
