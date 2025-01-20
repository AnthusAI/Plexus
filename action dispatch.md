# Action Dispatch System

## Stage Name Mapping Issue

The SegmentedProgressBar component is displaying incorrect stage names - showing "Finalizing" when it should be showing "Initializing". This appears to be a data transformation issue rather than a UI component issue.

### Current Implementation
1. Backend sends stage data with specific names and ordering
2. `transformActionToActivity` processes stages and determines current stage
3. Stage configs are created with lowercase keys but preserve display case
4. `ActionStatus` passes these to `SegmentedProgressBar`
5. `SegmentedProgressBar` does case-insensitive comparison

### Investigation Needed
1. Verify raw stage data from backend
2. Check stage transformation in `transformActionToActivity`
3. Trace data flow through components
4. Fix stage name mapping

### Next Steps
Begin by examining the raw stage data from the backend to understand the source of the name mismatch. 