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
   - Action and ActionStage models deployed in Amplify ✓
   - Bidirectional relationships configured ✓
   - Indexes set up for efficient querying ✓
   - Command string field added for task dispatch ✓

2. **Current Implementation Status**
   - Action and ActionStage Python client models created ✓
   - Basic CRUD operations implemented ✓
   - Progress tracking methods added ✓
   - Test coverage completed ✓
   - Mock responses aligned with GraphQL schema ✓
   - Demo command updated with Action support ✓
   - Multi-stage progress tracking implemented ✓
   - Progress updates working in both Celery and direct execution ✓

3. **Current Challenges**
   - Need to ensure atomic updates for counters
   - Need to handle partial failures in stage updates
   - Need to implement proper error propagation
   - Need to optimize subscription updates
   - Need to implement proper cleanup of completed actions

4. **Next Implementation Steps**
   1. ✓ Create frontend components for progress display
      - ✓ Action list and detail views showing status and progress
      - ✓ Stage-based progress visualization using SegmentedProgressBar
      - ✓ Real-time subscription updates
      - ✓ Error handling and completion states
      - ✓ Rich visual feedback for the 3-stage model
      - ✓ Pre-execution status display with animations
      - ✓ Command and status message display
      - ✓ Progress timing information

   2. Create Lambda function for Action-to-Celery dispatch
      - Triggered on Action creation
      - Extracts command and Action ID
      - Dispatches Celery task with `--action-id`
      - Handles errors and updates Action status
      - Enables UI-driven command execution

   3. Update other commands with Action support
      - Add `--action-id` parameter to all long-running commands
      - Implement stage-based progress tracking
      - Add proper error handling and status updates
      - Test with both direct and Celery execution

   4. Implement Action cleanup and maintenance
      - Add TTL for completed/failed Actions
      - Implement periodic cleanup of old Actions
      - Add monitoring for stuck/zombie Actions
      - Create Action archival process if needed

   5. Add Action management features
      - List view with filtering and sorting
      - Detail view with stage history
      - Manual retry/cancel capabilities
      - Batch operation support

5. **Technical Considerations**
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

### Testing with Demo Command
The demo command provides a way to test Action functionality:

```bash
# Run demo with new auto-created Action
plexus command demo

# Run demo with existing Action
plexus command demo --action-id YOUR_ACTION_ID
```

The demo command simulates a long-running task:
1. Pre-execution stages (8-12 seconds total):
   - Initial state (2-3s)
   - Dispatched state (2-3s)
   - Celery task creation (2-3s)
   - Worker claiming (2-3s)
2. Processing stages:
   - Initialization (4-6 seconds)
   - Main processing (2000 items over ~20 seconds)
   - Finalizing (2-4 seconds)

The command updates progress in real-time and works with both direct execution and Celery dispatch.

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

1. **Frontend Development**
   - Build Action list view with status indicators
   - Create Action detail view with stage visualization
   - Implement real-time subscription updates
   - Add error handling and completion states
   - Create intuitive command trigger UI

2. **Action-to-Celery Integration**
   - Implement Action creation Lambda
   - Set up Celery task dispatch
   - Add error handling and status updates
   - Test end-to-end flow from UI to worker

3. **Command Integration**
   - Add Action support to evaluation command
   - Add Action support to training command
   - Add Action support to dataset commands
   - Test all commands with both direct and Celery execution

4. **Testing & Documentation**
   - Write integration tests for Action-enabled commands
   - Add examples of Action usage to command docs
   - Document stage-based progress tracking
   - Create usage examples for frontend components

5. **Deployment & Monitoring**
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

# Run the demo task with Action tracking
plexus command demo --action-id <action-id>

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
- When run with `--action-id`, updates Action stages:
  1. Initialization (4-6 seconds)
  2. Processing (2000 items over ~20 seconds)
  3. Finalizing (2-4 seconds)

The evaluation command processes scorecard evaluations with:
- Real-time progress updates
- Proper async execution handling
- Detailed status reporting
- Error handling and cleanup