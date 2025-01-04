# Plexus Remote CLI Execution Plan

## Overview

This document outlines the implementation plan for adding remote CLI command execution capabilities to Plexus using Celery. The goal is to enable any existing Plexus CLI command to be executed remotely while maintaining reliability, security, and observability.

## Core Architecture

### Command Processing
- Commands will be passed as strings and parsed using `shlex` to handle complex arguments properly
- Support both synchronous and asynchronous execution modes
- Maintain consistent environment and configuration across workers
- Preserve all existing CLI functionality and error handling

### Task System
- Celery tasks will wrap CLI command execution
- Progress tracking for long-running operations
- Configurable timeouts and retry policies
- Result storage and retrieval
- Support for task cancellation

### Worker Infrastructure
- AWS SQS for message broker
- AWS DynamoDB for result backend
- Configurable worker pools
- Resource management and monitoring
- Health checks and automatic recovery

## Implementation Phases

### Phase 1: Core Integration
1. Set up basic Celery infrastructure
   - Configure AWS SQS connection
   - Set up AWS DynamoDB result backend
   - Basic worker management
2. Implement universal command execution task
   - Command string parsing
   - Output capture
   - Basic error handling
3. Add worker CLI command
   - Basic configuration options
   - Process management
   - Logging setup

### Phase 2: Reliability & Monitoring
1. Enhanced error handling
   - Retry mechanisms
   - Timeout handling
   - Resource limits
2. Progress tracking
   - Task state updates
   - Progress reporting
   - Cancellation support
3. Result management
   - Persistent storage
   - Result expiration
   - Query interfaces

### Phase 3: Production Readiness
1. Security enhancements
   - Input validation
   - Authentication/authorization
   - Audit logging
2. Monitoring system
   - Worker health checks
   - Resource usage tracking
   - Alert configuration
3. Documentation and examples
   - API documentation
   - Configuration guide
   - Usage examples

## Technical Details

### Command Execution Task
See `plexus/cli/CeleryTasks.py` for the implementation of the `run_cli_command` task.

### Worker Configuration
See `plexus/cli/CeleryTasks.py` for the implementation of the worker command and its configuration options.

## Security Considerations

### Input Validation
- Sanitize all command inputs
- Validate command structure
- Check argument types and ranges
- Prevent command injection

### Authentication
- Verify task origin
- Validate user permissions
- Track command attribution
- Audit logging

### Resource Protection
- Rate limiting
- Resource quotas
- Timeout enforcement
- Worker isolation

## Monitoring & Observability

### Health Metrics
- Worker status
- Queue depths
- Processing times
- Error rates
- Resource usage

### Logging
- Structured log format
- Command execution details
- Error tracing
- Audit events

### Alerting
- Worker failures
- Queue backlog
- Error thresholds
- Resource exhaustion

## Future Enhancements

### Planned Features
1. Task prioritization
2. Command scheduling
3. Batch processing
4. Result caching
5. Web dashboard

### Potential Improvements
1. Custom queue routing
2. Enhanced progress reporting
3. Resource optimization
4. Distributed tracing
5. Performance analytics

## Development Guidelines

### Code Organization
- Keep task definitions centralized
- Maintain clear separation of concerns
- Use consistent error handling
- Document all configurations

### Testing Strategy
1. Unit tests for task logic
2. Integration tests with Celery
3. End-to-end command testing
4. Performance benchmarking
5. Security testing

### Deployment Considerations
- Environment configuration
- Worker scaling
- Monitoring setup
- Backup procedures
- Update processes

## Questions for Implementation

1. How should we handle long-running tasks that exceed timeout limits?
2. What's the best strategy for managing worker resources across different command types?
3. How can we ensure consistent environment configuration across workers?
4. What metrics are most important for monitoring system health?
5. How should we handle task prioritization for different command types?

## Success Criteria

- All existing CLI commands work remotely
- Reliable error handling and recovery
- Clear monitoring and observability
- Secure command execution
- Scalable worker infrastructure
- Comprehensive documentation

## Key Implementation Details

### Command String Parsing
- Use `shlex` for robust command parsing to handle spaces, quotes, and special characters correctly:
  ```python
  command_args = shlex.split('evaluate accuracy --scorecard-name "My Complex Name"')
  ```

### Task Configuration
- Configure tasks with specific timeouts and retry policies:
  ```python
  @celery_app.task(
      bind=True,
      time_limit=3600,  # 1 hour timeout
      soft_time_limit=3300,  # Soft timeout 55 minutes
      max_retries=3
  )
  ```

### Progress Tracking
- Use Celery's built-in state updates for tracking long-running tasks:
  ```python
  self.update_state(state='STARTED', meta={'status': 'Initializing'})
  self.update_state(state='PROGRESS', meta={'status': 'Command completed'})
  ```

### Worker Configuration Options
- Implement flexible worker configuration through CLI parameters:
  ```python
  @click.option('--concurrency', default=4, help='Number of worker processes')
  @click.option('--queue', default='default', help='Queue to process')
  @click.option('--loglevel', default='INFO', help='Logging level')
  ```

### Error Recovery
- Implement retry logic with exponential backoff:
  ```python
  except Exception as exc:
      logger.error(f"Task failed: {exc}")
      self.retry(exc=exc, countdown=60)  # Retry after 1 minute
  ```

### Result Backend Configuration
- Configure result storage with appropriate expiration:
  ```python
  result_backend='redis://localhost:6379/0',
  result_expires=86400,  # Results expire after 24 hours
  task_track_started=True
  ```

## Environment Configuration

### Required Environment Variables
- `CELERY_AWS_ACCESS_KEY_ID`: AWS access key for SQS
- `CELERY_AWS_SECRET_ACCESS_KEY`: AWS secret key for SQS
- `CELERY_AWS_REGION_NAME`: AWS region for SQS
- `CELERY_BROKER_URL`: SQS broker URL template
- `CELERY_RESULT_BACKEND`: Redis backend URL template

### Broker URL Construction
- Safely quote AWS credentials
- Support both SQS and Redis URL formats
- Handle region-specific configurations

## Output Handling

### Command Output Capture
- Use `StringIO` to capture stdout and stderr
- Implement proper cleanup of file descriptors
- Handle binary output when necessary

### Result Structure
```python
{
    "stdout": "captured standard output",
    "stderr": "captured error output",
    "status": "success/error",
    "metadata": {
        "duration": "execution time",
        "exit_code": "command exit code",
        "worker_id": "ID of worker that processed task"
    }
}
```

## Infrastructure Setup

### AWS Resources
The system requires several AWS resources that we'll provision using AWS CDK. Initial implementation will focus on:

1. SQS Queue for Celery Message Broker
2. DynamoDB Table for Result Backend (alternative to Redis)
3. IAM Roles and Policies

### CDK Implementation
Example infrastructure code (to be integrated with Amplify Gen2):

```typescript
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cdk from 'aws-cdk-lib';

const backend = defineBackend({
  auth,
  data
});

const actionManagementStack = backend.createStack('ActionManagementStack');

// Message Broker Queue
const queue = new sqs.Queue(actionManagementStack, 'ActionDispatchMessageBroker', {
  queueName: 'action-dispatch-message-broker',
  visibilityTimeout: cdk.Duration.seconds(30),
  retentionPeriod: cdk.Duration.days(4)
});

// Results Table
const table = new dynamodb.Table(actionManagementStack, 'Actions', {
  partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});
```

### Infrastructure TODOs
1. Research Amplify Gen2 CDK extension integration
2. Define IAM roles and permissions
3. Configure VPC settings if needed
4. Set up CloudWatch logging
5. Define scaling policies
6. Implement backup strategies

### Infrastructure Considerations
- Region-specific configurations
- Development vs. production environments
- Cost optimization
- Security best practices
- Monitoring and alerting setup
- Backup and disaster recovery