# Plexus Lambda Docker Setup

This directory contains the Docker infrastructure for packaging the Plexus application as AWS Lambda-compatible containers. The setup uses a two-stage architecture: a base image containing all dependencies, and lightweight function images that add specific handlers.

## Architecture Overview

### Two-Stage Build Pattern

1. **Base Image** (`Dockerfile.base`): Contains the complete Plexus application with all dependencies
2. **Function Images** (`Dockerfile.fn`): Lightweight images that extend the base with specific Lambda handlers

This approach provides several benefits:
- **Faster builds**: Base image is built once, function images build in seconds
- **Consistency**: All functions share the same dependency versions
- **Efficiency**: Function images are small (just the handler code)
- **Maintainability**: Dependencies managed in one place

### Base Image Architecture

The base image uses a multi-stage build to handle complex dependencies:

#### Stage 1: Builder (manylinux2014)
- Uses `quay.io/pypa/manylinux2014_x86_64` for ABI compatibility
- Compiles binary dependencies (`pycurl`, `psycopg[binary]`)
- Builds all Python wheels including the Plexus package
- Installs dependencies to `/opt/python/lib/python3.11/site-packages`

Key features:
- **Binary dependencies**: Builds `pycurl` with OpenSSL support
- **Database support**: Includes `psycopg` with bundled `libpq`
- **VCS dependencies**: Pulls dependencies from GitHub (e.g., openai_cost_calculator)
- **SQLAlchemy compatibility**: Patches version for Python 3.11 compatibility
- **Separate installation**: Installs dependencies first, then Plexus package to optimize caching

#### Stage 2: Lambda Runtime
- Based on `public.ecr.aws/lambda/python:3.11`
- Copies pre-built packages from builder stage
- Includes runtime dependencies (libcurl for pycurl)
- Verifies all imports work correctly
- Copies Lambda handler as the final layer (for optimal caching)

## Prerequisites

### Docker Buildx Setup
Docker buildx is required for multi-platform builds:

```bash
# Create and activate a new builder
docker buildx create --use --name bld

# Bootstrap the builder
docker buildx inspect --bootstrap
```

### AWS ECR Authentication
Authenticate with ECR before pushing images:

```bash
# Login to ECR (replace with your region and account ID)
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-west-2.amazonaws.com
```

### ECR Repository Setup
Create repositories if they don't exist:

```bash
# Create base image repository
aws ecr create-repository \
  --repository-name plexus/lambda-base \
  --region us-west-2

# Create function image repository
aws ecr create-repository \
  --repository-name plexus/lambda-score-processing \
  --region us-west-2
```

## Building Images

### Important: Build Location
All docker builds **must be run from the Plexus project root**, not from the docker directory. This ensures proper access to the entire codebase.

### Building the Base Image

The base image contains all Plexus dependencies and should be rebuilt when:
- Python dependencies change (`pyproject.toml`)
- Plexus core code changes
- Base configuration changes

```bash
# From Plexus project root
BASE=123456789012.dkr.ecr.us-west-2.amazonaws.com/plexus/lambda-base:py311-amd64

# Build for linux/amd64 (Lambda architecture)
docker buildx build \
  --platform linux/amd64 \
  --load \
  -t "$BASE" \
  -f docker/Dockerfile.base \
  .

# Push to ECR
docker push $BASE
```

### Building Function Images

Function images are lightweight and should be rebuilt when:
- Handler code changes (`lambda_functions/*/handler.py`)
- Base image is updated

```bash
# From Plexus project root
FN=123456789012.dkr.ecr.us-west-2.amazonaws.com/plexus/lambda-score-processing:py311-amd64

# Build function image
docker buildx build \
  --platform linux/amd64 \
  --load \
  -t "$FN" \
  -f docker/Dockerfile.fn \
  .

# Push to ECR
docker push $FN
```

**Note**: Update the handler path in `Dockerfile.fn` to match your function:
```dockerfile
COPY lambda_functions/score_processing/handler.py ${LAMBDA_TASK_ROOT}/
```

## Handler Implementation

### Score Processing Handler

Located at `lambda_functions/score_processing/handler.py`, this handler:

1. **Environment Setup**: Configures matplotlib for Lambda's read-only filesystem
2. **API Client**: Initializes connection to Plexus GraphQL API
3. **Job Processing**: Implements a queue-based scoring system
   - Finds pending scoring jobs from DynamoDB
   - Claims jobs by updating status to IN_PROGRESS
   - Executes scoring using the Plexus Scorecard system
   - Stores results back to DynamoDB
   - Uploads trace data and logs to S3

### Key Components

- **JobProcessor class**: Main orchestration logic
- **Async processing**: Uses asyncio for efficient I/O operations
- **Error handling**: Comprehensive error logging and job status updates
- **S3 integration**: Uploads trace files and logs as attachments
- **Cache management**: Creates ScoreResults for API memoization

## Environment Variables

Required environment variables for Lambda functions:

```bash
# Plexus API Configuration
PLEXUS_API_URL=https://your-api-endpoint/graphql
PLEXUS_API_KEY=your-api-key
PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT=0  # Disable schema introspection

# OpenAI Configuration (for scoring)
OPENAI_API_KEY=sk-...

# AWS Configuration (set by Lambda runtime)
AWS_REGION=us-west-2

# Storage Configuration
AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME=scoreresultattachments-production

# Optional Configuration
ACCOUNT_KEY=account-key  # Default account for processing
```

## Local Testing

### Running Function Locally

```bash
# Build the function image locally
docker build -t plexus-score-processing -f docker/Dockerfile.fn .

# Run with environment variables
docker run \
  -e PLEXUS_API_URL="https://..." \
  -e PLEXUS_API_KEY="..." \
  -e OPENAI_API_KEY="sk-..." \
  -e AWS_REGION="us-west-2" \
  plexus-score-processing
```

### Testing with Lambda RIE

Use AWS Lambda Runtime Interface Emulator for local testing:

```bash
# Run with Lambda RIE
docker run -p 9000:8080 \
  -e PLEXUS_API_URL="https://..." \
  -e PLEXUS_API_KEY="..." \
  -e OPENAI_API_KEY="sk-..." \
  plexus-score-processing

# Invoke the function
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{}'
```

## Deployment to AWS Lambda

### Creating a Lambda Function

```bash
# Create function from ECR image
aws lambda create-function \
  --function-name plexus-score-processing \
  --package-type Image \
  --code ImageUri=123456789012.dkr.ecr.us-west-2.amazonaws.com/plexus/lambda-score-processing:py311-amd64 \
  --role arn:aws:iam::123456789012:role/lambda-execution-role \
  --timeout 900 \
  --memory-size 2048 \
  --environment Variables="{
    PLEXUS_API_URL=https://...,
    PLEXUS_API_KEY=...,
    OPENAI_API_KEY=...,
    AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME=scoreresultattachments-production
  }"
```

### Updating Existing Function

```bash
# Update function code with new image
aws lambda update-function-code \
  --function-name plexus-score-processing \
  --image-uri 123456789012.dkr.ecr.us-west-2.amazonaws.com/plexus/lambda-score-processing:py311-amd64
```

## Troubleshooting

### Common Build Issues

**Problem**: Build fails with "no space left on device"
- **Cause**: Docker build cache full
- **Solution**: Clean up: `docker system prune -a`

**Problem**: Handler cannot be imported
- **Cause**: Handler path mismatch
- **Solution**: Verify `COPY` path in Dockerfile.fn matches actual handler location

### Runtime Issues

**Problem**: Out of memory errors
- **Solution**: Increase Lambda memory (current: 2048MB)
- **Solution**: Review scorecard complexity and input size

**Problem**: S3 upload failures
- **Solution**: Verify IAM role has S3 write permissions
- **Solution**: Check bucket name environment variable

**Problem**: GraphQL query failures
- **Solution**: Verify `PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT=0` is set
- **Solution**: Check API key and endpoint configuration

## File Structure

```
docker/
├── README.md           # This file
├── Dockerfile.base     # Base image with all dependencies
└── Dockerfile.fn       # Function image template

lambda_functions/
└── score_processing/
    └── handler.py      # Lambda handler implementation

.dockerignore          # Excludes unnecessary files from build context
```

## Build Optimization

### Layer Caching Strategy

The Dockerfiles are optimized for caching:

1. **Base Image**:
   - System dependencies (rarely change)
   - Binary wheels (pycurl, psycopg) - cached per dependency version
   - Python dependencies - cached per pyproject.toml
   - Plexus package - invalidates when code changes
   - Handler - **copied last** to maximize cache reuse

2. **Function Image**:
   - Based on stable base image
   - Only handler code changes frequently
   - Builds in seconds when base is cached

### Reducing Build Times

- **Multi-stage builds**: Keep builder separate from runtime
- **Order COPY commands**: Most stable files first
- **Minimize context**: Use `.dockerignore` aggressively

### Image Size Optimization

Optimization techniques used:
- Multi-stage build discards build tools
- `yum clean all` removes package manager cache
- Only necessary runtime dependencies included
- Binary wheels reduce dependency size

## Adding New Lambda Functions

To create a new Lambda function:

1. **Create handler**: Add new file in `lambda_functions/your_function/handler.py`

2. **Update Dockerfile.fn**: Change the COPY line to your handler:
   ```dockerfile
   COPY lambda_functions/your_function/handler.py ${LAMBDA_TASK_ROOT}/
   ```

3. **Build function image**:
   ```bash
   FN=123456789012.dkr.ecr.us-west-2.amazonaws.com/plexus/lambda-your-function:py311-amd64
   docker buildx build --platform linux/amd64 --load -t "$FN" -f docker/Dockerfile.fn .
   docker push $FN
   ```

4. **Deploy to Lambda**: Use the new image URI in Lambda configuration

## Maintenance

### Monitoring

Key metrics to monitor:
- Lambda duration (should be < 15 minutes)
- Memory usage (adjust if consistently high)
- Error rates (check CloudWatch logs)
- Cold start times (consider provisioned concurrency)

## References

- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Docker Buildx Documentation](https://docs.docker.com/reference/cli/docker/buildx/)
- [AWS ECR Documentation](https://docs.aws.amazon.com/ecr/)