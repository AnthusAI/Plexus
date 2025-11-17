# Score Processor Lambda

AWS Lambda function for processing scoring jobs from SQS queues. This Lambda polls the SQS queue for scoring job requests, performs scoring using the Plexus scorecard system, and sends results back via a response queue.

## Architecture

- **Trigger**: Manual invocation (polls SQS queue)
- **Input**: Retrieves one message from `PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL`
- **Processing**: Performs scoring using Plexus scorecard system
- **Output**: Sends results to `PLEXUS_RESPONSE_WORKER_QUEUE_URL`
- **Storage**: Creates ScoreResult in DynamoDB

## Prerequisites

- Docker with buildx support
- AWS CLI configured with appropriate credentials
- Access to ECR repository: `{AWS_ACCOUNT}.dkr.ecr.us-west-2.amazonaws.com/plexus/score-processor-lambda`
- Lambda function: `plexus-score-processor-lambda`

## Environment Variables

The Lambda function requires these environment variables:

- `PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL` - SQS queue URL for incoming job requests
- `PLEXUS_RESPONSE_WORKER_QUEUE_URL` - SQS queue URL for sending results
- `PLEXUS_ACCOUNT_KEY` - Plexus account key for authentication

**Note**: `SCORECARD_CACHE_DIR` is automatically set to `/tmp/scorecards` in the handler code since `/tmp` is the only writable directory in Lambda.

## Deployment

### Automated Deployment (Recommended)

The Lambda function is automatically deployed via AWS CDK pipelines when changes are pushed to the repository:

- **Staging Environment**: Automatically deploys when changes are pushed to the `staging` branch
- **Production Environment**: Automatically deploys when changes are pushed to the `main` branch

The pipeline automatically:
1. Builds the Docker image with proper Lambda-compatible settings (`--platform linux/amd64 --provenance=false`)
2. Pushes the image to ECR (`plexus/score-processor-lambda:latest`)
3. Updates the Lambda function with the new image
4. Deploys all infrastructure changes via CDK

**Infrastructure Files**:
- Stack definition: `infrastructure/stacks/lambda_score_processor_stack.py`
- Pipeline configuration: `infrastructure/pipelines/base_pipeline.py`

**How It Works**:
1. Push code changes to `main` (production) or `staging` branch
2. GitHub webhook triggers AWS CodePipeline
3. Pipeline runs CDK synth to generate CloudFormation templates
4. Docker build step builds and pushes the Lambda container image to ECR
5. CDK deploys the Lambda function and any infrastructure updates
6. Lambda function automatically uses the latest image from ECR

**Note**: The Lambda function is NOT automatically triggered by SQS yet. It must be invoked manually until SQS event source is enabled in the CDK stack.

### Manual Deployment (Development/Testing)

For local development and testing, you can manually build and deploy using the commands below.

## Quick Commands

### ECR Login

```bash
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin {AWS_ACCOUNT}.dkr.ecr.us-west-2.amazonaws.com
```

### Build and Push Image

Build and push the Docker image to ECR (use this command to ensure Lambda compatibility):

```bash
docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --push \
  -f score-processor-lambda/Dockerfile \
  -t {AWS_ACCOUNT}.dkr.ecr.us-west-2.amazonaws.com/plexus/score-processor-lambda:latest \
  .
```

**Important**: The `--provenance=false` flag is required to prevent Docker from creating attestation manifests that Lambda doesn't support.

### Update Lambda Function with New Image

After pushing a new image, update the Lambda function:

```bash
aws lambda update-function-code \
  --function-name plexus-score-processor-lambda \
  --image-uri {AWS_ACCOUNT}.dkr.ecr.us-west-2.amazonaws.com/plexus/score-processor-lambda:latest \
  --region us-west-2
```

### Update Environment Variables

```bash
aws lambda update-function-configuration \
  --function-name plexus-score-processor-lambda \
  --environment Variables="{PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL=<queue-url>,PLEXUS_RESPONSE_WORKER_QUEUE_URL=<response-queue-url>,PLEXUS_ACCOUNT_KEY=<account-key>}" \
  --region us-west-2
```

### Update Timeout and Memory

```bash
aws lambda update-function-configuration \
  --function-name plexus-score-processor-lambda \
  --timeout 300 \
  --memory-size 2048 \
  --region us-west-2
```

### Invoke Lambda Function (Test)

```bash
aws lambda invoke \
  --function-name plexus-score-processor-lambda \
  --region us-west-2 \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  response.json | base64 --decode
```

Then check the response:

```bash
cat response.json | jq
```

### Get Lambda Function Info

```bash
aws lambda get-function \
  --function-name plexus-score-processor-lambda \
  --region us-west-2
```

### View Lambda Logs

```bash
aws logs tail /aws/lambda/plexus-score-processor-lambda --follow --region us-west-2
```

### Get Latest Log Stream

```bash
aws logs describe-log-streams \
  --log-group-name /aws/lambda/plexus-score-processor-lambda \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --region us-west-2
```

## Development Workflow

1. **Make code changes** to `handler.py` or update dependencies in `requirements.txt`

2. **Build and push** the new image:
   ```bash
   aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin {AWS_ACCOUNT}.dkr.ecr.us-west-2.amazonaws.com

   docker buildx build --platform linux/amd64 --provenance=false --push -f score-processor-lambda/Dockerfile -t {AWS_ACCOUNT}.dkr.ecr.us-west-2.amazonaws.com/plexus/score-processor-lambda:latest .
   ```

3. **Update Lambda** with the new image:
   ```bash
   aws lambda update-function-code --function-name plexus-score-processor-lambda --image-uri {AWS_ACCOUNT}.dkr.ecr.us-west-2.amazonaws.com/plexus/score-processor-lambda:latest --region us-west-2
   ```

4. **Test** the function:
   ```bash
   aws lambda invoke --function-name plexus-score-processor-lambda --region us-west-2 --log-type Tail response.json
   cat response.json | jq
   ```

5. **Monitor logs**:
   ```bash
   aws logs tail /aws/lambda/plexus-score-processor-lambda --follow --region us-west-2
   ```

## Local Testing

To test the image locally before pushing:

```bash
# Build locally
docker buildx build --platform linux/amd64 --load -f score-processor-lambda/Dockerfile -t score-processor-lambda:latest .

# Run container with environment variables
docker run --rm \
  -e PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL=<queue-url> \
  -e PLEXUS_RESPONSE_WORKER_QUEUE_URL=<response-queue-url> \
  -e PLEXUS_ACCOUNT_KEY=<account-key> \
  -e AWS_ACCESS_KEY_ID=<your-key> \
  -e AWS_SECRET_ACCESS_KEY=<your-secret> \
  -e AWS_DEFAULT_REGION=us-west-2 \
  score-processor-lambda:latest
```

## Troubleshooting

### Lambda function not processing messages

1. Check environment variables are set correctly
2. Verify IAM role has SQS permissions
3. Check CloudWatch logs for errors
4. Verify SQS queue has messages

### Image build fails

1. Ensure Docker buildx is installed: `docker buildx version`
2. Make sure you're in the Plexus project root directory
3. Verify all source files exist: `plexus/` directory and `handler.py`

### Lambda manifest error

If you get "image manifest, config or layer media type... is not supported":
- Ensure you're using `--provenance=false` flag
- Use `--platform linux/amd64` flag
- Push directly with buildx using `--push` (don't load then push separately)

## Function Configuration

- **Runtime**: Python 3.11 (via container)
- **Memory**: 2048 MB
- **Timeout**: 300 seconds (5 minutes)
- **Architecture**: x86_64
- **IAM Role**: `plexusScoreProcessor-role-ls7dow27`
  - AmazonDynamoDBFullAccess
  - AmazonS3FullAccess
  - AmazonSQSFullAccess
  - CloudWatchFullAccess (for metrics publishing)
- **Log Group**: `/aws/lambda/plexus-score-processor-lambda`

## Files

- `Dockerfile` - Container image definition
- `handler.py` - Lambda entry point and job processing logic
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Dependencies

Major dependencies include:
- `awslambdaric` - Lambda runtime interface
- LangChain/LangGraph stack for AI scoring
- `boto3` - AWS SDK
- Data science libraries: numpy, pandas, matplotlib, scikit-learn, xgboost
- Plexus codebase (copied from `plexus/` directory)
