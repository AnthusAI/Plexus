import { CfnOutput, CfnResource, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface TopicMemoryVectorStoreStackProps extends StackProps {
  environmentName: string;
}

function normalizeEnvironmentName(value: string): string {
  const normalized = (value || 'development')
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return normalized || 'development';
}

export class TopicMemoryVectorStoreStack extends Stack {
  public readonly vectorBucketName: string;
  public readonly vectorIndexName: string;
  public readonly embeddingsBucketName: string;

  constructor(scope: Construct, id: string, props: TopicMemoryVectorStoreStackProps) {
    super(scope, id, props);

    const environmentName = normalizeEnvironmentName(props.environmentName);
    const isDevelopment = environmentName === 'development';

    this.vectorBucketName = `plexus-vectors-${environmentName}`;
    this.vectorIndexName = `topic-memory-idx-${environmentName}`;
    this.embeddingsBucketName = `plexus-embeddings-${environmentName}`;

    const vectorBucket = new CfnResource(this, 'TopicMemoryVectorBucket', {
      type: 'AWS::S3Vectors::VectorBucket',
      properties: {
        VectorBucketName: this.vectorBucketName,
      },
    });
    vectorBucket.applyRemovalPolicy(
      isDevelopment ? RemovalPolicy.DESTROY : RemovalPolicy.RETAIN
    );

    const vectorIndex = new CfnResource(this, 'TopicMemoryVectorIndex', {
      type: 'AWS::S3Vectors::Index',
      properties: {
        DataType: 'float32',
        Dimension: 384,
        DistanceMetric: 'cosine',
        IndexName: this.vectorIndexName,
        VectorBucketName: this.vectorBucketName,
      },
    });
    vectorIndex.addDependency(vectorBucket);
    vectorIndex.applyRemovalPolicy(
      isDevelopment ? RemovalPolicy.DESTROY : RemovalPolicy.RETAIN
    );

    const embeddingsBucket = new s3.Bucket(this, 'EmbeddingsBucket', {
      bucketName: this.embeddingsBucketName,
      removalPolicy: isDevelopment ? RemovalPolicy.DESTROY : RemovalPolicy.RETAIN,
      autoDeleteObjects: isDevelopment,
    });

    new CfnOutput(this, 'S3VectorBucketName', {
      value: this.vectorBucketName,
      description: 'S3 Vectors bucket for S3_VECTOR_BUCKET_NAME',
      exportName: `PlexusS3VectorBucket-${environmentName}`,
    });

    new CfnOutput(this, 'S3VectorBucketArn', {
      value: vectorBucket.getAtt('VectorBucketArn').toString(),
      description: 'S3 Vectors bucket ARN',
      exportName: `PlexusS3VectorBucketArn-${environmentName}`,
    });

    new CfnOutput(this, 'S3VectorIndexName', {
      value: this.vectorIndexName,
      description: 'S3 Vectors index name for S3_VECTOR_INDEX_NAME',
      exportName: `PlexusS3VectorIndex-${environmentName}`,
    });

    new CfnOutput(this, 'S3VectorIndexArn', {
      value: vectorIndex.getAtt('IndexArn').toString(),
      description: 'S3 Vectors index ARN for S3_VECTOR_INDEX_ARN (optional)',
      exportName: `PlexusS3VectorIndexArn-${environmentName}`,
    });

    new CfnOutput(this, 'EmbeddingsBucketName', {
      value: embeddingsBucket.bucketName,
      description: 'S3 bucket for EMBEDDING_CACHE_BUCKET',
      exportName: `PlexusEmbeddingsBucket-${environmentName}`,
    });
  }
}
