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
     - Added account ID integration ✓
     - Fixed task creation and update issues ✓
     - Improved error handling and logging ✓
     - Enhanced datetime handling with robust parsing and formatting ✓
     - Fixed stage start time inheritance to prevent elapsed time resets ✓
     - Added safeguards against invalid datetime values ✓
     - Improved timezone handling and UTC consistency ✓

3. **UI Integration** ✓
   - Activity Dashboard improvements:
     - Added real-time task updates ✓
     - Fixed stage handling in task display ✓
     - Improved progress bar behavior ✓
     - Added proper error handling ✓
     - Cleaned up excessive logging ✓
     - Fixed type issues with GraphQL responses ✓
   - Task Component enhancements:
     - Added support for stage transitions ✓
     - Improved progress visualization ✓
     - Fixed stage visibility issues ✓
     - Added proper cleanup on unmount ✓
   - Task Dispatch Button implementation:
     - Created TaskDispatchButton component ✓
     - Added dropdown for action selection ✓
     - Implemented command configuration modal ✓
     - Connected to Amplify Gen2 API for task creation ✓
     - Successfully creating tasks in DynamoDB ✓
     - Added proper error handling and user feedback ✓

4. **Worker Integration** (In Progress)
   - Current status:
     - Task creation working through UI ✓
     - DynamoDB record created successfully ✓
     - Lambda trigger firing correctly ✓
     - Worker receiving task but failing to process
   - Next steps:
     - Debug worker task processing
     - Fix command execution in worker
     - Add better error reporting from worker to task record
     - Implement proper command validation
     - Add worker logging improvements
     - Test full task lifecycle with worker fixes

5. **Testing & Validation** (Partially Complete)
   - Write unit tests for `TaskProgressTracker` ✓
   - Add integration tests for demo and report tasks ✓
   - Verify UI updates work correctly ✓
     - Stage visibility working correctly ✓
     - Progress bar behavior fixed ✓
     - Status message updates working ✓
     - Stage transition animations smooth ✓
   - Test error handling and recovery ✓
   - Pending tests:
     - Worker command execution
     - Task lifecycle with worker integration
     - Error handling in worker process
     - Command validation and sanitization
     - Worker recovery scenarios

5. **Next Steps**
   - Add Task support to evaluation command
   - Implement consistent error handling across all commands
   - Add support for task cancellation
   - Improve task cleanup and resource management
   - Add monitoring and alerting for task failures

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

2. **Task Management CLI Tools** (In Progress)
   - Added CLI commands for task management:
     - `plexus tasks list` - List tasks with filtering options
       - Filter by account ID, status, and type
       - Display task details in formatted table
     - `plexus tasks delete` - Delete tasks and their stages
       - Delete by ID, account, status, or type
       - Confirmation prompt with task preview
       - Force option to skip confirmation
   - Implementation details:
     - Moved task commands to dedicated `TaskCommands.py`
     - Rich library integration for better UI
     - GraphQL mutations for task/stage deletion
   - Current challenges:
     - Testing needed for edge cases
     - Error handling improvements needed
     - Need to verify proper cleanup of related resources

3. **DynamoDB Indexes** (In Progress)
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

4. **System Testing**
   - Full Stack Integration ✓
     - Task creation from dashboard UI successful ✓
     - DynamoDB record creation working ✓
     - Lambda trigger dispatching correctly ✓
     - Celery task dispatch to workers functioning ✓
     - End-to-end task lifecycle verified ✓
     - Real-time progress updates flowing through system ✓
   - Infrastructure Integration ✓
     - DynamoDB stream configuration working ✓
     - AWS Lambda deployment and triggers working ✓
     - SQS message broker configured and tested ✓
     - Worker node deployment verified ✓
   - Performance Testing (In Progress)
     - Concurrent task handling
     - Worker scaling behavior
     - Queue depth monitoring
     - Task completion timing
   - Edge Cases (Pending)
     - Error recovery scenarios
     - Network failure handling
     - Task cancellation behavior
     - Resource cleanup verification

### Phase 5: UI Polish & Testing ✓

1. **Enhanced UI Components** ✓
   - Task component improvements:
     - Added pre-execution stage visualization ✓
     - Implemented smooth animations for state changes ✓
     - Added detailed progress tracking with timing ✓
     - Improved error state handling and display ✓
     - Added support for command display and status messages ✓
   - Progress bar enhancements:
     - Added segmented progress visualization ✓
     - Implemented stage transitions ✓
     - Added timing calculations and display ✓
     - Improved accessibility ✓

2. **Component Testing** ✓
   - Storybook integration:
     - Added comprehensive stories for Task component ✓
     - Added stories for TaskStatus component ✓
     - Added interactive demos with all states ✓
     - Added documentation for component usage ✓
   - Test coverage:
     - Added visual regression tests ✓
     - Added interaction tests ✓
     - Added accessibility tests ✓

3. **Error Handling & Recovery**
   - UI error states:
     - Added clear error messages ✓
     - Implemented retry functionality ✓
     - Added error boundary protection ✓
   - Backend error handling:
     - Added detailed error reporting from workers
     - Implemented automatic retry for transient failures
     - Added error logging and monitoring
   - Recovery procedures:
     - Added task cleanup on failure
     - Implemented worker recovery
     - Added system health monitoring

### Phase 6: Production Readiness

1. **Performance Optimization**
   - Implement task result caching
   - Add task batching for better throughput
   - Optimize database queries
   - Add performance monitoring
   - Implement rate limiting

2. **Monitoring & Alerting**
   - Set up CloudWatch dashboards
   - Configure alerts for:
     - Failed tasks
     - Long-running tasks
     - Queue depth
     - Worker health
     - System errors
   - Add operational metrics
   - Set up log aggregation

3. **Evaluation System Integration**
   - Migration Planning:
     - Audit current evaluation progress tracking
     - Map evaluation stages to task stages
     - Identify dependencies and affected components
     - Plan database schema updates
   - Implementation:
     - Update evaluation models to use task system
     - Migrate progress tracking to TaskProgressTracker
     - Update evaluation dashboard UI
     - Convert evaluation commands to use task dispatch
   - Testing:
     - Verify progress reporting accuracy
     - Test evaluation-specific stages
     - Validate error handling
     - Performance testing with large evaluations
   - Migration:
     - Database migration strategy
     - Backward compatibility plan
     - Rollout strategy
     - Monitoring during migration

4. **Documentation & Training**
   - System architecture documentation
   - Operational procedures
   - Troubleshooting guides
   - User documentation
   - API documentation
   - Example implementations

5. **Security & Compliance**
   - Security review
   - Access control implementation
   - Audit logging
   - Data retention policies
   - Compliance documentation

6. **Deployment & Operations**
   - Deployment automation
   - Backup procedures
   - Disaster recovery plan
   - Scaling procedures
   - Maintenance windows
   - Update procedures

### Next Steps

1. Begin evaluation system integration
   - Audit current evaluation progress tracking
   - Create migration plan
   - Update evaluation models
   - Test with sample evaluations
2. Complete edge case testing
3. Implement comprehensive error handling
4. Set up monitoring and alerting
5. Complete security review
6. Finalize documentation
7. Plan production deployment

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