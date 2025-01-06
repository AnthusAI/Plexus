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
- Progress tracking for long-running operations ✓
- Configurable timeouts and retry policies
- Result storage and retrieval ✓
- Task cancellation removed (YAGNI - complexity outweighed benefits)

### Worker Infrastructure
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
2. Implement universal command execution ✓
   - Command string parsing ✓
   - Output capture ✓
   - Basic error handling ✓
3. Add worker CLI command ✓
   - Basic configuration options ✓
   - Process management ✓
   - Logging setup ✓

### Phase 2: Reliability & Monitoring (In Progress)
1. Enhanced error handling ✓
   - Retry mechanisms ✓
   - Timeout handling ✓
   - Resource limits (Pending)
   - Click exit code handling ✓
   - Command validation ✓
2. Progress tracking ✓
   - Action state updates ✓
   - Progress reporting ✓
   - Status messages ✓
   - Task cancellation removed (SQS limitations make this impractical)
3. Result management ✓
   - Persistent storage ✓
   - Result expiration ✓
   - Query interfaces ✓

### Phase 3: Action-Command Integration
1. Action Model Implementation
   - Define Action GraphQL model schema
   - Add required fields for command tracking
   - Configure real-time subscriptions
   - Set up DynamoDB table and indexes

2. Command Progress Integration
   - Extend command dispatch to update Action records
   - Add progress reporting to Action updates
   - Implement status message propagation
   - Handle command completion state

3. React Dashboard Components
   - Create ActionProgress component
   - Implement real-time progress display
   - Add command status visualization
   - Handle command lifecycle events

4. End-to-End Integration
   - Connect React components to Action model
   - Test long-running command updates
   - Verify real-time progress display
   - Validate error handling and recovery

## Current Implementation Details

### Command Dispatch
The command system supports:
- Synchronous and asynchronous execution ✓
- Timeout configuration ✓
- Output streaming to caller ✓
- Action ID tracking for async operations ✓
- Rich progress display with status messages ✓
- Live progress updates for both sync and async operations ✓

### Progress Tracking
The system provides detailed progress information:
- Current item count and total items ✓
- Progress bar with percentage complete ✓
- Time elapsed and estimated time remaining ✓
- Dynamic status messages based on progress ✓
- Clean display using Rich library ✓
- Support for both local and remote progress updates ✓

Progress tracking has been integrated into:
- The demo command (fully tested) ✓
- The evaluation command (fully tested) ✓
  - Added progress reporting to evaluation process ✓
  - Supports remote tracking through Celery ✓
  - Successfully tested with real evaluation runs ✓

### Async Command Handling
The system handles async commands in two ways:
1. Command-level async:
   - Commands like `evaluate accuracy` manage their own event loops
   - Event loops are created and managed within the command
   - Loops are not closed to allow reuse in worker processes
   - Progress updates work seamlessly with async execution

2. Dispatch-level async:
   - Celery handles task dispatch asynchronously
   - Commands can be run in background with progress tracking
   - Results are stored in DynamoDB for retrieval
   - Status updates flow through the Action model

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
- Click usage/help messages are captured and returned as successful output ✓
- Command validation failures are captured in stderr ✓
- Command execution failures include error details in the result ✓
- System exits are handled gracefully with appropriate status codes ✓
- Async command failures are properly propagated and logged ✓

## Dashboard Integration

### Architecture
- Action model in Amplify schema represents both request and results
- Lightweight Lambda function dispatches Celery commands on Action creation
- Celery worker updates Action records directly through AppSync
- Frontend components use normal Amplify subscriptions for realtime updates

### Lambda Implementation
- Minimal Python script with Celery as only dependency
- Infrastructure defined in Amplify backend.ts using CDK:
  - SQS queue for Celery broker
  - DynamoDB table for Celery results
  - IAM permissions for Lambda to access both
- Configuration accessed through Amplify's injected `env` object
- Dispatches command asynchronously and exits immediately
- No need for full Plexus installation in Lambda environment

### CDK Infrastructure
- Define SQS queue and DynamoDB table in backend.ts
- Create IAM policies for Lambda to access these resources
- Export queue URL and table name through Lambda environment
- Share same resources between Lambda and Celery workers
- Ensure proper permissions for AppSync mutations

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

1. Add resource monitoring and limits
2. Enhance error handling with retry policies
3. Add security measures
4. Create monitoring dashboards
5. Write comprehensive documentation

## Usage Example

Start a worker:
```bash
# Start worker in the correct directory for scorecard access
cd path/to/call-criteria-python
plexus command worker --concurrency=4 --loglevel=INFO
```

Execute commands:
```bash
# Run the demo task synchronously with progress display
plexus command demo

# Run an evaluation asynchronously
plexus command dispatch "evaluate accuracy --scorecard-name agent-scorecard --number-of-samples 10"

# Check the status of an async task
plexus command status <task-id>
```

The demo command processes 2000 items over 20 seconds, displaying:
- Current progress and item count
- Status messages that update based on progress
- Time elapsed and estimated time remaining
- A Rich progress bar with visual feedback

The evaluation command processes scorecard evaluations with:
- Real-time progress updates
- Proper async execution handling
- Detailed status reporting
- Error handling and cleanup