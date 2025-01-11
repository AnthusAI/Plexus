# Plexus Action Dispatch System

## Overview

This document outlines the implementation of Plexus's two-level dispatch system:

1. **Action Dispatch**: The high-level system connecting user applications (like the React dashboard) to the Python backend. This system uses an Amplify GraphQL Action model with realtime updates to manage long-running AI operations.

2. **Command Dispatch**: The lower-level mechanism that dispatches CLI commands to Plexus worker nodes through Celery, handling the actual execution of AI operations.

## Core Architecture

### Action Processing
- Actions represent high-level AI operations requested by users ✓
- Each Action maps to one or more CLI commands ✓
- Support both synchronous and asynchronous execution modes ✓
- Maintain consistent environment and configuration across workers ✓
- Preserve all existing CLI functionality and error handling ✓

### Command System
- Celery tasks wrap CLI command execution ✓
- Progress tracking for long-running operations ✓
- Configurable timeouts and retry policies ✓
- Result storage and retrieval ✓
- Task cancellation removed (YAGNI - complexity outweighed benefits) ✓
- Task targeting system for worker specialization ✓
  - Target string format: `domain/subdomain` ✓
  - Pattern matching with wildcards ✓
  - Worker configuration for target patterns ✓
  - Examples:
    - `datasets/call-criteria`
    - `training/call-criteria`
    - `[datasets,training]/call-criteria`
    - `*/gpu-required`

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

### Phase 2: Reliability & Monitoring ✓
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
4. Task targeting ✓
   - Target string format definition ✓
   - Pattern matching implementation ✓
   - Worker configuration ✓
   - Unit test coverage ✓

### Phase 3: Action-Command Integration (In Progress)

1. **Model Implementation** ✓
   - Action and ActionStage models deployed in Amplify
   - Bidirectional relationships configured
   - Indexes set up for efficient querying
   - Command string field added for task dispatch

2. **Next Implementation Steps**
   1. Create Lambda function for Action-to-Celery dispatch
      - Triggered on Action creation
      - Extracts command and Action ID
      - Dispatches Celery task with `--action-id`
      - Handles errors and updates Action status

   2. Add Action and ActionStage model classes to Python client
      - Create model classes matching Amplify schema
      - Add methods for creating and updating actions
      - Implement stage management utilities
      - Add real-time progress tracking integration

   3. Update Celery worker for Action support
      - Parse `--action-id` from command string
      - Update Action progress during execution
      - Stream stdout/stderr to Action record
      - Handle errors and completion status

   4. Create frontend components for progress display
      - Action list and detail views
      - Real-time progress updates
      - Stage-based progress visualization
      - Error handling and retry UI

3. **Technical Considerations**
   - Use DynamoDB GSI on accountId for efficient listing ✓
   - Consider TTL for cleanup of completed actions
   - Use atomic updates for counters
   - Handle partial failures in stage updates
   - Optimize subscription updates to minimize network traffic
   - Ensure task targeting is respected in Action-to-Command dispatch

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
   - Commands like `evaluate accuracy` manage their own event loops ✓
   - Event loops are created and managed within the command ✓
   - Loops are not closed to allow reuse in worker processes ✓
   - Progress updates work seamlessly with async execution ✓

2. Dispatch-level async:
   - Celery handles task dispatch asynchronously ✓
   - Commands can be run in background with progress tracking ✓
   - Results are stored in DynamoDB for retrieval ✓
   - Status updates flow through the Action model ✓

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

## Next Steps

1. **Python Client Implementation**
   - Create Action and ActionStage model classes
   - Add methods for action lifecycle management
   - Integrate with existing Celery task system
   - Add real-time progress tracking

2. **Frontend Development**
   - Build action list and detail views
   - Implement real-time progress updates
   - Add stage-based progress visualization
   - Create error handling and retry UI

3. **Testing & Documentation**
   - Write unit tests for new models
   - Add integration tests for action lifecycle
   - Document API changes and new features
   - Create usage examples

4. **Deployment & Monitoring**
   - Set up proper AWS permissions
   - Configure monitoring and alerts
   - Add operational dashboards
   - Document operational procedures

## Environment Configuration

### Required Environment Variables
- `CELERY_AWS_ACCESS_KEY_ID`: AWS access key for SQS
- `CELERY_AWS_SECRET_ACCESS_KEY`: AWS secret key for SQS
- `CELERY_AWS_REGION_NAME`: AWS region for SQS
- `CELERY_RESULT_BACKEND_TEMPLATE`: DynamoDB backend URL template

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