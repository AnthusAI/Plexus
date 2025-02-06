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

### Phase 3: Standardized Progress Tracking ✓

1. **Create TaskProgressTracker Class** ✓
   - Core functionality:
     - Track current stage, processed items, total items ✓
     - Calculate elapsed time and estimated completion ✓
     - Generate status messages based on progress ✓
     - Handle stage transitions and updates ✓
     - Support both local and remote progress updates ✓
   - Key features:
     - Thread-safe singleton pattern for global state ✓
     - Context manager interface for automatic cleanup ✓
     - Support for both sync and async operations ✓
     - Atomic counter updates ✓
     - Rich status message generation ✓
     - Error state handling ✓
     - Estimated completion time in UTC ✓
     - Items per second calculation ✓
     - Stage management with configurable stages ✓

2. **Refactor Demo Command** ✓
   - Move progress tracking logic from `demo` command to `TaskProgressTracker` ✓
   - Use the new tracker for:
     - Stage management ✓
     - Progress calculations ✓
     - Status message generation ✓
     - Time tracking ✓
   - Validate the implementation works with:
     - Direct execution ✓
     - Celery dispatch ✓
     - Task API integration ✓
   - Improvements:
     - Fixed elapsed time calculation to use completion time ✓
     - Corrected stage status updates through Task API ✓
     - Added real-time status message updates during processing ✓
     - Implemented proper stage transitions with status messages ✓
     - Added final completion status message ✓

3. **Refactor ReportTask** ✓
   - Update `ReportTask` to use `TaskProgressTracker` ✓
   - Ensure compatibility with existing UI components ✓
   - Maintain current progress visualization features ✓
   - Add support for rich status messages ✓

4. **Testing & Validation** (In Progress)
   - Write unit tests for `TaskProgressTracker` ✓
     - Basic progress tracking ✓
     - Update progress ✓
     - Elapsed time ✓
     - Estimated time remaining ✓
     - Stage management ✓
     - Context manager ✓
     - Error handling ✓
     - Status message generation ✓
     - Estimated completion time ✓
     - Items per second ✓
   - Add integration tests for demo and report tasks ✓
   - Verify UI updates work correctly (Debugging)
     - Investigating stage visibility issues in UI
     - Fixing progress bar behavior for Setup/Finalizing stages
     - Ensuring proper status message updates
     - Validating stage transition animations
   - Test error handling and recovery ✓

5. **Command Integration** (Partially Complete)
   - Add Task support to evaluation command ✓
   - Implement consistent error handling ✓
   - Current debugging focus:
     - Progress bar visibility for different stage types
     - Stage transition handling in UI
     - Status message updates during transitions
     - Proper cleanup of completed stages

### Phase 4: Backend Integration (In Progress)

1. **Lambda Integration** ✓
   - ✓ Create Lambda function for Task-to-Celery dispatch
   - ✓ Set up DynamoDB stream trigger
   - ✓ Basic dispatch logic implemented
   - Implementation challenges resolved:
     1. Initial Node.js Lambda approach:
        - Successfully deployed and triggered by DynamoDB streams
        - Failed to integrate with Celery due to TypeScript limitations
        - Direct SQS message posting worked but wasn't ideal
     2. Python Lambda solution:
        - Successfully implemented with native Celery library
        - Properly configured with environment variables
        - Successfully deployed and triggered by DynamoDB streams
     3. Current status:
        - ✓ Python function successfully deployed
        - ✓ Stream trigger working correctly
        - ✓ Celery task dispatch confirmed
        - ✓ Progress updates flowing through Task model
        - ✓ Full end-to-end integration tested and working
   - Remaining tasks:
     - Add more comprehensive error handling
     - Implement retry strategies for edge cases
     - Add detailed logging for debugging
     - Set up monitoring and alerting

2. **DynamoDB Indexes** (In Progress)
   - Current state:
     ```typescript
     .secondaryIndexes((idx) => [
         idx("accountId").sortKeys(["updatedAt"]),
         idx("scorecardId"),
         idx("scoreId"),
         idx("updatedAt")
     ])
     ```
   - Planned changes (one per deployment):
     1. Add `updatedAt` sort key to `scorecardId` index
     2. Add `updatedAt` sort key to `scoreId` index
     3. Remove standalone `updatedAt` index (redundant)

3. **System Testing**
   - ✓ Initial test successful with Node.js Lambda
   - ✓ DynamoDB stream configuration working
   - Current challenges:
     - Python Lambda trigger not firing
     - Stream configuration may need adjustment
   - Pending tests:
     - Python Lambda trigger verification
     - Celery task dispatch with environment variables
     - Progress reporting
     - State transitions
     - Concurrent operations

### Phase 5: System Maintenance

1. **Task Lifecycle Management**
   - Implement Task cleanup with TTL
   - Set up monitoring for long-running tasks
   - Add operational dashboards
   - Configure alerts
   - Implement periodic cleanup
   - Monitor Task-Evaluation relationships

2. **Performance Monitoring**
   - Set up metrics collection
   - Create performance dashboards
   - Configure performance alerts
   - Monitor system resource usage
   - Track task completion times

3. **System Health**
   - Monitor worker health
   - Track queue depths
   - Monitor database performance
   - Set up system alerts
   - Implement auto-recovery

### Phase 6: Testing & Documentation

1. **Testing**
   - Write comprehensive tests for Task model operations
   - Validate index performance
   - Test edge cases in async operation handling
   - Test error recovery scenarios
   - Verify monitoring systems
   - Test cleanup processes

2. **Documentation**
   - Document Task-Evaluation relationships
   - Create troubleshooting guide
   - Update API documentation
   - Create usage examples
   - Document monitoring setup
   - Add maintenance procedures

3. **Validation**
   - Perform load testing
   - Validate error handling
   - Test recovery procedures
   - Verify monitoring accuracy
   - Test alert systems

## Implementation Details

### Command Dispatch
The command system supports:
- Synchronous and asynchronous execution ✓
- Timeout configuration ✓
- Output streaming to caller ✓
- Task ID tracking for async operations ✓
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

### Task Progress UI Behavior
The system follows specific rules for displaying progress in the UI:

1. **Progress Bar Visibility**
   - Only stages with `total_items` set will show progress bars in the UI
   - Setup and Finalizing stages typically should not show progress
   - Main Processing stages should show progress bars

2. **Stage Configuration**
   - Each stage can be configured with:
     - Name and order
     - Optional total_items for progress tracking
     - Status messages for user feedback
     - Start and completion times
     - Estimated completion time

3. **Implementation Files**
   - Core Progress Tracking:
     - `plexus/cli/task_progress_tracker.py`: Main implementation
     - Contains `TaskProgressTracker`, `StageConfig`, and `Stage` classes
     - Detailed configuration options in class docstrings
   - UI Components:
     - `dashboard/components/Task.tsx`: Main task display component
     - `dashboard/components/ui/task-status.tsx`: Progress bar implementation

4. **Best Practices**
   - Setup stages: Quick preparation, no progress bar needed
   - Processing stages: Main work stages with progress bars
   - Finalizing stages: Cleanup/completion steps, no progress bar needed
   - Always provide meaningful status messages for each stage
   - Use estimated completion times when available

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
- Real-time status messages with items/sec rate ✓
- Time elapsed and estimated time remaining
- A Rich progress bar with visual feedback
- When run with `--task-id`, updates Task stages:
  1. Initialization (4-6 seconds) with "Setting up..." message ✓
  2. Processing (2000 items over ~20 seconds) with live progress updates ✓
  3. Finalizing (2-4 seconds) with proper completion message ✓

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

## Next Steps

1. **System Hardening**
   - Add comprehensive error handling to Lambda function
   - Implement retry strategies for network issues
   - Add detailed logging for debugging
   - Set up monitoring and alerting
   - Add dead letter queues for failed tasks
   - Implement task timeout handling

2. **Performance Optimization**
   - Profile Lambda function performance
   - Optimize DynamoDB read/write patterns
   - Tune Celery worker configurations
   - Implement task batching where appropriate
   - Add performance metrics collection
   - Set up performance monitoring

3. **Testing & Validation**
   - Add integration tests for full task lifecycle
   - Test error recovery scenarios
   - Validate concurrent task handling
   - Test system under load
   - Verify monitoring accuracy
   - Document testing procedures

4. **Documentation**
   - Update deployment procedures
   - Document environment configuration
   - Add troubleshooting guides
   - Document index usage patterns
   - Create operational runbooks
   - Add monitoring documentation 