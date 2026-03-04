"""
OpenSearch + S3 Vectors + Embeddings Stack for Semantic Reinforcement Memory.

Provisions:
- OpenSearch domain (existing prototype vector store)
- S3 Vectors bucket + index (new vector store path)
- S3 bucket for embedding cache (plexus-embeddings-{env})

Deploy separately for development: python deploy_opensearch.py
(script name is retained to migrate the existing stack in-place).
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_iam as iam,
    aws_s3 as s3,
)
from aws_cdk import aws_opensearchservice as opensearch
from aws_cdk import aws_s3vectors as s3vectors
from constructs import Construct


class TopicMemoryVectorStack(Stack):
    """
    CDK Stack for Semantic Reinforcement Memory with dual vector stores.

    OpenSearch: existing prototype store for continuity.
    S3 Vectors: new runtime target (float32, 384 dimensions, cosine distance).
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

        # 1. Existing OpenSearch domain kept for side-by-side availability.
        self.domain = self._create_opensearch_domain()

        # 2. New S3 Vectors bucket + index.
        self.vector_bucket_name = f"plexus-vectors-{self.environment_name}"
        self.vector_index_name = f"topic-memory-idx-{self.environment_name}"
        self.vector_bucket = self._create_vector_bucket()
        self.vector_index = self._create_vector_index()

        # 3. Embeddings S3 bucket.
        self.embeddings_bucket = self._create_embeddings_bucket()

        # 4. Outputs.
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

    def _create_vector_bucket(self) -> s3vectors.CfnVectorBucket:
        """Create S3 Vectors bucket for topic-memory vectors."""
        bucket = s3vectors.CfnVectorBucket(
            self,
            "TopicMemoryVectorBucket",
            vector_bucket_name=self.vector_bucket_name,
        )
        bucket.apply_removal_policy(
            RemovalPolicy.DESTROY
            if self.environment_name == "development"
            else RemovalPolicy.RETAIN
        )
        return bucket

    def _create_vector_index(self) -> s3vectors.CfnIndex:
        """Create S3 Vectors index for 384-dim sentence embeddings."""
        index = s3vectors.CfnIndex(
            self,
            "TopicMemoryVectorIndex",
            vector_bucket_name=self.vector_bucket_name,
            index_name=self.vector_index_name,
            data_type="float32",
            dimension=384,
            distance_metric="cosine",
        )
        index.apply_removal_policy(
            RemovalPolicy.DESTROY
            if self.environment_name == "development"
            else RemovalPolicy.RETAIN
        )
        index.add_dependency(self.vector_bucket)
        return index

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
        """Export OpenSearch, S3 vectors, and embeddings outputs."""
        # OpenSearch endpoint kept available while runtime shifts to S3 vectors.
        endpoint = self.domain.domain_endpoint
        CfnOutput(
            self,
            "OpenSearchEndpoint",
            value=endpoint,
            description="OpenSearch endpoint for OPENSEARCH_ENDPOINT",
            export_name=f"PlexusOpenSearchEndpoint-{self.environment_name}",
        )
        CfnOutput(
            self,
            "OpenSearchEndpointUrl",
            value=f"https://{endpoint}",
            description="Full OpenSearch URL",
        )

        # S3 Vectors bucket + index for new runtime path.
        CfnOutput(
            self,
            "S3VectorBucketName",
            value=self.vector_bucket_name,
            description="S3 Vectors bucket for S3_VECTOR_BUCKET_NAME",
            export_name=f"PlexusS3VectorBucket-{self.environment_name}",
        )
        CfnOutput(
            self,
            "S3VectorBucketArn",
            value=self.vector_bucket.attr_vector_bucket_arn,
            description="S3 Vectors bucket ARN",
            export_name=f"PlexusS3VectorBucketArn-{self.environment_name}",
        )
        CfnOutput(
            self,
            "S3VectorIndexName",
            value=self.vector_index_name,
            description="S3 Vectors index name for S3_VECTOR_INDEX_NAME",
            export_name=f"PlexusS3VectorIndex-{self.environment_name}",
        )
        CfnOutput(
            self,
            "S3VectorIndexArn",
            value=self.vector_index.attr_index_arn,
            description="S3 Vectors index ARN for S3_VECTOR_INDEX_ARN (optional)",
            export_name=f"PlexusS3VectorIndexArn-{self.environment_name}",
        )

        # Shared embeddings bucket.
        CfnOutput(
            self,
            "EmbeddingsBucketName",
            value=self.embeddings_bucket.bucket_name,
            description="S3 bucket for EMBEDDING_CACHE_BUCKET",
            export_name=f"PlexusEmbeddingsBucket-{self.environment_name}",
        )
