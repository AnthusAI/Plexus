# Score Processor Lambda

AWS Lambda function for processing scoring jobs from SQS queues. This Lambda is automatically triggered by SQS events, performs scoring using the Plexus scorecard system, and sends results back via a response queue.

## Architecture

- **Trigger**: SQS event source (automatic, one message per invocation, max 500 concurrent executions)
- **Input**: Receives messages from `PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL`
- **Processing**: Performs scoring using Plexus scorecard system
- **Output**: Sends results to `PLEXUS_RESPONSE_WORKER_QUEUE_URL`
- **Storage**: Creates ScoreResult in DynamoDB
- **Error Handling**: Failed messages are retried by SQS, then moved to DLQ after max retries

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

## Testing

The Lambda function has two types of tests:

### 1. Unit Tests (pytest)

Standard Python unit tests that run outside the container:

```bash
# Run from project root
make test-unit

# Or run pytest directly
cd .. && PYTHONPATH=score-processor-lambda pytest score-processor-lambda/tests/test_*.py -v
```

**What's tested:**
- Handler initialization
- Event parsing logic
- Environment variable validation
- Mock integration tests

### 2. Container Smoke Tests

Validates the Docker container has all dependencies correctly installed:

```bash
# Build and run smoke test
make test-smoke

# Or run manually
make build
docker run --rm \
  -v $(PWD)/tests/smoke_test.py:/var/task/smoke_test.py \
  --entrypoint python \
  score-processor-lambda:latest \
  smoke_test.py
```

**What's tested:**
- All dependencies importable (langchain, tactus, boto3, etc.)
- Pinned package versions match requirements.txt
- Plexus modules load correctly
- Handler can initialize
- NLTK data available
- Container filesystem writable

### Running All Tests

```bash
# Run both unit and smoke tests
make test

# Or run individually
make test-unit    # Unit tests only
make test-smoke   # Container smoke test only
```

### Pre-deployment Testing

Before deploying to AWS, run the full test suite:

```bash
# Build image and run all tests
make build-and-test
```

This ensures:
1. Image builds successfully
2. All dependencies install correctly
3. Pinned versions are correct (avoiding dependency resolution issues)
4. Handler can initialize
5. All imports work in the Lambda environment

### Test Files

- `tests/test_handler.py` - Unit tests for handler logic
- `tests/smoke_test.py` - Container smoke test
- `tests/conftest.py` - Pytest configuration and fixtures
- `Makefile` - Convenient test commands
- `tests/README.md` - Documentation for the test suite

**CI/CD Note**: These tests are excluded from the main GitHub Actions test suite (configured in `pytest.ini`) since they're specific to the Lambda container environment. Run them independently using the Makefile commands before deploying.

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

**SQS Event Source Trigger**:
The Lambda function is automatically triggered by the SQS queue (`PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL`) with the following configuration:
- **Batch size**: 1 (processes one message per Lambda invocation)
- **Max concurrency**: 500 (up to 500 concurrent Lambda executions)
- **Error handling**: On exception, the message is returned to the queue for retry (up to maxReceiveCount, then moved to DLQ)
- **Configuration**: Defined in `infrastructure/stacks/lambda_score_processor_stack.py` (lines 199-209)

### Manual Deployment (Emergency Only)

**⚠️ Warning:** Manual deployment should only be used in emergency situations. Normal deployment is handled automatically by the CDK pipeline when pushing to `main` or `staging` branches.

For emergency situations where the pipeline is unavailable, you can manually build and deploy using the commands below.

## Quick Commands

### Using Makefile (Recommended)

The Makefile provides convenient commands for local development and testing:

```bash
# Show all available commands
make help

# Testing
make test              # Run all tests (unit + smoke)
make test-unit         # Run pytest unit tests only
make test-smoke        # Run container smoke test
make build-and-test    # Build image and run smoke test

# Building (for local testing only)
make build             # Build Docker image locally

# Utilities
make info              # Show configuration
make clean             # Remove local images
```

**Local development workflow:**
```bash
# 1. Make changes to code or requirements
vim handler.py

# 2. Build and test locally
make build-and-test

# 3. Commit and push to trigger deployment
git add .
git commit -m "Update score processor"
git push origin main  # Triggers CDK pipeline deployment
```

**Note:** Deployment is handled automatically by AWS CDK pipelines. See the [Automated Deployment](#automated-deployment-recommended) section above for details. The infrastructure is defined in `infrastructure/stacks/lambda_score_processor_stack.py`.

### Manual Commands

If you prefer to run commands manually without the Makefile:

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

## Monitoring

Useful commands for monitoring the deployed Lambda function:

### View Lambda Logs

```bash
aws logs tail /aws/lambda/plexus-score-processor-lambda --follow --region us-west-2
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

# Check response
cat response.json | jq
```

### Get Lambda Function Info

```bash
aws lambda get-function \
  --function-name plexus-score-processor-lambda \
  --region us-west-2
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
