# Plexus Action Dispatch System

## Overview

This document outlines the implementation of Plexus's two-level dispatch system:

1. **Action Dispatch**: The high-level system connecting user applications (like the React dashboard) to the Python backend. This system uses an Amplify GraphQL Action model with realtime updates to manage long-running AI operations.

2. **Command Dispatch**: The lower-level mechanism that dispatches CLI commands to Plexus worker nodes through Celery, handling the actual execution of AI operations.

## Core Architecture

### Action Processing
- Actions represent high-level AI operations requested by users
- Each Action maps to one or more CLI commands
- Support both synchronous and asynchronous execution modes
- Maintain consistent environment and configuration across workers
- Preserve all existing CLI functionality and error handling

### Command System
- Celery tasks wrap CLI command execution
- Progress tracking for long-running operations (Partial)
- Configurable timeouts and retry policies
- Result storage and retrieval
- Support for command cancellation (Pending)

### Worker Infrastructure
- AWS SQS for message broker
- AWS DynamoDB for result backend
- Configurable worker pools
- Resource management and monitoring (Partial)
- Health checks and automatic recovery (Partial)

## Implementation Status

### Phase 1: Core Integration ✓
1. Set up basic Celery infrastructure ✓
   - Configure AWS SQS connection ✓
   - Set up AWS DynamoDB result backend ✓
   - Basic worker management ✓
2. Implement universal command execution ✓
   - Command string parsing ✓
   - Output capture ✓
   - Basic error handling ✓
3. Add worker CLI command ✓
   - Basic configuration options ✓
   - Process management ✓
   - Logging setup ✓

### Phase 2: Reliability & Monitoring (In Progress)
1. Enhanced error handling (Partial)
   - Retry mechanisms
   - Timeout handling ✓
   - Resource limits
   - Click exit code handling ✓
   - Command validation ✓
2. Progress tracking (Pending)
   - Action state updates
   - Progress reporting
   - Cancellation support (Pending)
3. Result management ✓
   - Persistent storage ✓
   - Result expiration ✓
   - Query interfaces ✓

### Phase 3: Production Readiness (Pending)
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

## Current Implementation Details

### Command Dispatch
The command system supports:
- Synchronous and asynchronous execution
- Timeout configuration
- Output streaming to caller
- Action ID tracking for async operations

### Result Format
Commands return results in a standardized format:
```python
{
    'status': 'success' | 'error',  # Command execution status
    'command': str,                 # Original command string
    'stdout': str,                  # Captured standard output
    'stderr': str,                  # Captured error output
    'error': str,                   # Error message if status is 'error'
}
```

### Error Handling
The system handles various error conditions:
- Click usage/help messages are captured and returned as successful output
- Command validation failures are captured in stderr
- Command execution failures include error details in the result
- System exits are handled gracefully with appropriate status codes

## Dashboard Integration

### Architecture
- Action model in Amplify schema represents both request and results
- Lambda trigger on Action creation starts Celery commands
- Celery worker updates Action records directly through AppSync
- Frontend components use normal Amplify subscriptions for realtime updates

### Action Model Integration
- Action records include Celery command ID and status
- Worker updates include required DataStore fields (_lastChangedAt, _version, _deleted)
- Frontend subscribes to Action updates through standard Amplify patterns
- Conflict resolution handled by Amplify DataStore

### Implementation Requirements
- AWS credentials and permissions for Celery worker AppSync access
- Lambda function configuration in Amplify schema
- Action model schema with appropriate fields and triggers
- Worker code to perform AppSync mutations

### Next Steps
1. Define Action model schema with required fields
2. Implement Lambda trigger for action creation
3. Add AppSync mutation capability to Celery worker
4. Create frontend components for action management
5. Set up proper AWS permissions and credentials
6. Test end-to-end action lifecycle

## Environment Configuration

### Required Environment Variables
- `CELERY_AWS_ACCESS_KEY_ID`: AWS access key for SQS
- `CELERY_AWS_SECRET_ACCESS_KEY`: AWS secret key for SQS
- `CELERY_AWS_REGION_NAME`: AWS region for SQS
- `CELERY_RESULT_BACKEND_TEMPLATE`: DynamoDB backend URL template

## Next Steps

1. Implement and test action cancellation
2. Implement progress tracking for long-running actions
3. Add resource monitoring and limits
4. Enhance error handling with retry policies
5. Add security measures
6. Create monitoring dashboards
7. Write comprehensive documentation

## Usage Example

Start a worker:
```bash
plexus action worker --concurrency=4 --loglevel=INFO
```

Execute a command:
```bash
# Synchronous execution
plexus action dispatch "evaluate accuracy --help"

# Asynchronous execution
plexus action dispatch --async "evaluate accuracy --scorecard-name test"
```

Check action status:
```bash
plexus action status <action-id>