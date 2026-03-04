# Semantic Reinforcement Memory: Dual-Store Deployment

Deploy both vector stores (OpenSearch + S3 Vectors) plus S3 embedding cache for the Semantic Reinforcement Memory prototype.

## Prerequisites

1. **AWS CLI** configured with credentials
2. **CDK bootstrapped**: `cdk bootstrap aws://ACCOUNT_ID/us-west-2`
3. **Python deps**: `pip install aws-cdk-lib constructs`

## Deploy (Development)

```bash
cd infrastructure
python deploy_opensearch.py   # Synthesize
npx cdk deploy plexus-opensearch-development --app "python deploy_opensearch.py" --require-approval never
```

S3 Vectors resources are usually fast to create; OpenSearch domain updates can take longer.

## After Deployment

1. **Get outputs**:
   ```bash
   aws cloudformation describe-stacks --stack-name plexus-opensearch-development --query 'Stacks[0].Outputs'
   ```

2. **Set environment variables**:
   ```bash
   export OPENSEARCH_ENDPOINT=<OpenSearchEndpoint from output>  # optional legacy path
   export S3_VECTOR_BUCKET_NAME=<S3VectorBucketName from output>
   export S3_VECTOR_INDEX_NAME=<S3VectorIndexName from output>
   export S3_VECTOR_INDEX_ARN=<S3VectorIndexArn from output>  # optional
   export EMBEDDING_CACHE_BUCKET=plexus-embeddings-development
   ```

   Or add to `.plexus/config.yaml` or `.env`:
   ```
   OPENSEARCH_ENDPOINT: https://vpc-...
   S3_VECTOR_BUCKET_NAME: plexus-vectors-development
   S3_VECTOR_INDEX_NAME: topic-memory-idx-development
   S3_VECTOR_INDEX_ARN: arn:aws:s3vectors:...
   EMBEDDING_CACHE_BUCKET: plexus-embeddings-development
   ```

3. **Run Semantic Reinforcement Memory report** with a report config that includes the VectorTopicMemory block and a valid data source.
   Current runtime path uses S3 Vectors; OpenSearch is retained for side-by-side availability.

## Stack Contents

| Resource | Purpose |
|----------|---------|
| OpenSearch domain | Existing prototype vector store retained during transition |
| S3 Vectors bucket + index | Vector store for topic memory (float32, 384-dim, cosine) |
| S3 bucket | Embedding cache (avoids re-embedding on re-index) |
