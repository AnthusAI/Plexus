# Plexus Remote CLI Execution Plan

## Overview

This document outlines the implementation plan for adding remote CLI command execution capabilities to Plexus using Celery. The goal is to enable any existing Plexus CLI command to be executed remotely while maintaining reliability, security, and observability.

## Core Architecture

### Command Processing ✓
- Commands are passed as strings and parsed using `shlex` to handle complex arguments properly ✓
- Support both synchronous and asynchronous execution modes ✓
- Maintain consistent environment and configuration across workers ✓
- Preserve all existing CLI functionality and error handling ✓

### Task System ✓
- Celery tasks wrap CLI command execution ✓
- Progress tracking for long-running operations (Partial)
- Configurable timeouts and retry policies ✓
- Result storage and retrieval ✓
- Support for task cancellation (Pending)

### Worker Infrastructure ✓
- AWS SQS for message broker ✓
- AWS DynamoDB for result backend ✓
- Configurable worker pools ✓
- Resource management and monitoring (Partial)
- Health checks and automatic recovery (Partial)

## Implementation Status

### Phase 1: Core Integration ✓
1. Set up basic Celery infrastructure ✓
   - Configure AWS SQS connection ✓
   - Set up AWS DynamoDB result backend ✓
   - Basic worker management ✓
2. Implement universal command execution task ✓
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
   - Task state updates
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

### Command Execution Task
The task system is implemented in `plexus/cli/ActionTasks.py` with the following features:
- Command string parsing using `shlex`
- Output capture for both stdout and stderr
- Error handling with detailed status reporting
- Support for Click's exit codes and error handling
- Graceful handling of help/usage messages

### Worker Configuration
Worker management is implemented in `plexus/cli/ActionCommands.py` with:
- Configurable concurrency
- Queue selection (standardized on 'celery' queue)
- Log level control
- AWS SQS/DynamoDB integration

### Command Dispatch
The dispatch system supports:
- Synchronous and asynchronous execution
- Timeout configuration
- Output streaming to caller
- Task ID tracking for async operations

### Result Format
Tasks return results in a standardized format:
```python
{
    'status': 'success' | 'error',  # Task execution status
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
- Task execution failures include error details in the result
- System exits are handled gracefully with appropriate status codes

## Environment Configuration

### Required Environment Variables
- `CELERY_AWS_ACCESS_KEY_ID`: AWS access key for SQS
- `CELERY_AWS_SECRET_ACCESS_KEY`: AWS secret key for SQS
- `CELERY_AWS_REGION_NAME`: AWS region for SQS
- `CELERY_RESULT_BACKEND_TEMPLATE`: DynamoDB backend URL template

## Next Steps

1. Implement and test task cancellation
2. Implement progress tracking for long-running tasks
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

Check task status:
```bash
plexus action status <task-id>