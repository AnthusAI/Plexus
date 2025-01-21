# Plexus Task Dispatch System

## Overview

This document outlines the implementation of Plexus's two-level dispatch system:

1. **Task Dispatch**: The high-level system connecting user applications (like the React dashboard) to the Python backend. This system uses an Amplify GraphQL Task model with realtime updates to manage long-running AI operations.

2. **Command Dispatch**: The lower-level mechanism that dispatches CLI commands to Plexus worker nodes through Celery, handling the actual execution of AI operations.

## Core Architecture

### Task Processing
- Tasks represent high-level AI operations requested by users ✓
- Each Task maps to one or more CLI commands ✓
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
   - Task state updates ✓
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

### Phase 3: Task-Command Integration (Current Phase)

#### Current Status
- Schema deployment (Needs Update)
  - Action model needs renaming to Task
  - ActionStage model needs renaming to TaskStage
  - Relationships and queries need updating
  - New Task-Evaluation relationship needed

- Command Dispatch System ✓
  - Synchronous and asynchronous execution
  - Timeout configuration
  - Output streaming to caller
  - Task ID tracking for async operations
  - Rich progress display with status messages
  - Live progress updates for both sync and async operations

- Progress Tracking ✓
  - Current item count and total items
  - Progress bar with percentage complete
  - Time elapsed and estimated time remaining
  - Dynamic status messages based on progress
  - Clean display using Rich library
  - Support for both local and remote progress updates

- Frontend Integration (In Progress)
  - Real-time task status updates in dashboard
  - Progress visualization
  - Stage tracking display
  - Error handling and display
  - ActionStatus component needs renaming to TaskStatus
  - EvaluationTask component needs Task integration

#### Current Challenges
- Need to ensure atomic updates for counters
- Need to handle partial failures in stage updates
- Need to implement proper error propagation
- Need to optimize subscription updates
- Need to implement proper cleanup of completed tasks
- Need to integrate evaluation process with Task system
- Need to complete Action-to-Task nomenclature refactoring:
  - Rename ActionStatus component to TaskStatus
  - Update API schema to rename Action model to Task
  - Update API schema to rename ActionStage to TaskStage
  - Update all frontend components using ActionStatus
  - Update all code referencing Action/ActionStage models

#### Next Steps

1. **Action-to-Task Refactoring**
   - API Schema Updates:
     - Rename Action model to Task
     - Rename ActionStage to TaskStage
     - Update all relationships and queries
     - Deploy schema changes
   - Frontend Component Updates:
     - Rename ActionStatus to TaskStatus
     - Update all imports and references
     - Test all component variants with new names
   - Evaluation Integration:
     - Modify evaluation process to create Task records
     - Update EvaluationTask to use Task records for progress
     - Ensure proper Task-Evaluation record association
     - Migrate evaluation progress tracking to TaskStage system
   - Testing & Validation:
     - Verify all renamed components work correctly
     - Test Task-Evaluation relationships
     - Validate progress tracking in evaluation process
     - Check all UI components display correctly

2. **Frontend Development**
   - Refine TaskStatus Component States
   - Update Activity Dashboard Integration
   - Fix Realtime Updates
   - Improve Task List Display
   - Polish Task Component UI
   - Create intuitive command trigger UI

3. **Backend Integration**
   - Create Lambda function for Task-to-Celery dispatch
   - Set up Celery task dispatch
   - Add error handling and status updates
   - Test end-to-end flow from UI to worker
   - Add Task support to evaluation command
   - Add Task support to training command
   - Add Task support to dataset commands

4. **System Maintenance**
   - Implement Task cleanup with TTL
   - Set up monitoring for long-running tasks
   - Add operational dashboards
   - Configure alerts
   - Implement periodic cleanup
   - Monitor Task-Evaluation relationships

5. **Testing & Documentation**
   - Write comprehensive tests for Task model operations
   - Validate index performance
   - Test edge cases in async operation handling
   - Document Task-Evaluation relationships
   - Create troubleshooting guide
   - Update API documentation
   - Create usage examples

## Implementation Details

### Command Dispatch
The command system supports:
- Synchronous and asynchronous execution ✓
- Timeout configuration ✓
- Output streaming to caller ✓
- Task ID tracking for async operations ✓
- Rich progress display with status messages ✓
- Live progress updates for both sync and async operations ✓

### Testing with Demo Command
The demo command provides a way to test Task functionality:

```bash
# Run demo with new auto-created Task
plexus command demo

# Run demo with existing Task
plexus command demo --task-id YOUR_TASK_ID
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
   - Status updates flow through the Task model ✓

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

# Run the demo task with Task tracking
plexus command demo --task-id <task-id>

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
- When run with `--task-id`, updates Task stages:
  1. Initialization (4-6 seconds)
  2. Processing (2000 items over ~20 seconds)
  3. Finalizing (2-4 seconds)

The evaluation command processes scorecard evaluations with:
- Real-time progress updates
- Proper async execution handling
- Detailed status reporting
- Error handling and cleanup

The evaluation command processes scorecard evaluations with:
- Real-time progress updates
- Proper async execution handling
- Detailed status reporting
- Error handling and cleanup 