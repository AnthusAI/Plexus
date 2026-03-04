"""
OpenSearch + Embeddings Stack for Vector Topic Memory.

Provisions:
- OpenSearch domain (t3.small.search, 10GB EBS, single node)
- S3 bucket for embedding cache (plexus-embeddings-{env})
- IAM access for the deploying account

Deploy separately for development: python deploy_opensearch.py
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_iam as iam,
    aws_s3 as s3,
)
from aws_cdk import aws_opensearchservice as opensearch
from constructs import Construct


class OpenSearchStack(Stack):
    """
    CDK Stack for Vector Topic Memory: OpenSearch domain + embeddings bucket.

    OpenSearch: single t3.small.search node, 10GB EBS, no multi-AZ.
    Embeddings: S3 bucket for EmbeddingCache (all-MiniLM-L6-v2, 384 dims).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str = "development",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment

        # 1. OpenSearch domain
        self.domain = self._create_opensearch_domain()

        # 2. Embeddings S3 bucket
        self.embeddings_bucket = self._create_embeddings_bucket()

        # 3. Outputs
        self._create_outputs()

    def _create_opensearch_domain(self) -> opensearch.Domain:
        """Create minimal OpenSearch domain for topic memory (384-dim vectors)."""
        return opensearch.Domain(
            self,
            "TopicMemoryDomain",
            domain_name=f"plexus-vtm-{self.environment_name}"[:28],
            version=opensearch.EngineVersion.OPENSEARCH_2_5,
            capacity=opensearch.CapacityConfig(
                data_nodes=1,
                data_node_instance_type="t3.small.search",
                multi_az_with_standby_enabled=False,
            ),
            ebs=opensearch.EbsOptions(volume_size=10),
            enforce_https=True,
            node_to_node_encryption=True,
            removal_policy=RemovalPolicy.DESTROY if self.environment_name == "development" else RemovalPolicy.RETAIN,
            access_policies=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    principals=[iam.AccountRootPrincipal()],
                    actions=["es:*"],
                    resources=["*"],
                ),
            ],
        )

    def _create_embeddings_bucket(self) -> s3.Bucket:
        """Create S3 bucket for embedding cache (EmbeddingCache / EmbeddingService)."""
        bucket_name = f"plexus-embeddings-{self.environment_name}"
        return s3.Bucket(
            self,
            "EmbeddingsBucket",
            bucket_name=bucket_name,
            removal_policy=RemovalPolicy.DESTROY if self.environment_name == "development" else RemovalPolicy.RETAIN,
            auto_delete_objects=self.environment_name == "development",
        )

    def _create_outputs(self) -> None:
        """Export endpoint and bucket for runtime configuration."""
        # OpenSearch endpoint (use domain_endpoint which includes https://)
        endpoint = self.domain.domain_endpoint
        CfnOutput(
            self,
            "OpenSearchEndpoint",
            value=endpoint,
            description="OpenSearch domain endpoint for OPENSEARCH_ENDPOINT",
            export_name=f"PlexusOpenSearchEndpoint-{self.environment_name}",
        )
        CfnOutput(
            self,
            "OpenSearchEndpointUrl",
            value=f"https://{endpoint}",
            description="Full OpenSearch URL",
        )

        # Embeddings bucket
        CfnOutput(
            self,
            "EmbeddingsBucketName",
            value=self.embeddings_bucket.bucket_name,
            description="S3 bucket for EMBEDDING_CACHE_BUCKET",
            export_name=f"PlexusEmbeddingsBucket-{self.environment_name}",
        )
