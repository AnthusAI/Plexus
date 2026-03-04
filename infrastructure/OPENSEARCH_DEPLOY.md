# Vector Topic Memory: OpenSearch + Embeddings Deployment

Deploy the OpenSearch vector store and S3 embedding cache for the VectorTopicMemory report block.

## Prerequisites

1. **AWS CLI** configured with credentials
2. **CDK bootstrapped**: `cdk bootstrap aws://ACCOUNT_ID/us-west-2`
3. **Service-linked role** (created automatically by AWS Console; if missing):
   ```bash
   aws iam create-service-linked-role --aws-service-name es.amazonaws.com
   ```
4. **Python deps**: `pip install aws-cdk-lib constructs`

## Deploy (Development)

```bash
cd infrastructure
python deploy_opensearch.py   # Synthesize
npx cdk deploy plexus-opensearch-development --app "python deploy_opensearch.py" --require-approval never
```

OpenSearch domain creation takes **~10–15 minutes**.

## After Deployment

1. **Get outputs**:
   ```bash
   aws cloudformation describe-stacks --stack-name plexus-opensearch-development --query 'Stacks[0].Outputs'
   ```

2. **Set environment variables**:
   ```bash
   export OPENSEARCH_ENDPOINT=<OpenSearchEndpoint from output>
   export EMBEDDING_CACHE_BUCKET=plexus-embeddings-development
   ```

   Or add to `.plexus/config.yaml` or `.env`:
   ```
   OPENSEARCH_ENDPOINT: https://vpc-plexus-vtm-dev-xxxxx.us-west-2.es.amazonaws.com
   EMBEDDING_CACHE_BUCKET: plexus-embeddings-development
   ```

3. **Run VectorTopicMemory report** with a report config that includes the VectorTopicMemory block and a valid data source.

## Stack Contents

| Resource | Purpose |
|----------|---------|
| OpenSearch domain | Vector index for topic memory (384-dim, all-MiniLM-L6-v2) |
| S3 bucket | Embedding cache (avoids re-embedding on re-index) |

## Instance Configuration

- **Instance**: t3.small.search (cheapest dev option)
- **Storage**: 10 GB EBS
- **Nodes**: 1 data node, no multi-AZ
