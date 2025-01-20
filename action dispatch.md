# Action Dispatch System

## Stage Name Mapping Issue

The SegmentedProgressBar component is displaying incorrect stage names - showing "Finalizing" when it should be showing "Initializing". This appears to be a data transformation issue rather than a UI component issue.

### Current Implementation
1. Backend sends stage data with specific names and ordering
2. `transformActionToActivity` processes stages and determines current stage
3. Stage configs are created with lowercase keys but preserve display case
4. `ActionStatus` passes these to `SegmentedProgressBar`
5. `SegmentedProgressBar` does case-insensitive comparison

### Progress Made
1. Fixed Task stories to properly include stage configs with correct labels and colors
2. Updated `transformActionToActivity` to include stage configuration properties directly in stage objects
3. Unified the stage and stageConfig objects to ensure consistency
4. Fixed color assignments for stages (bg-secondary for Processing, bg-primary for others)

### Current Issues
1. Stage segments are still not displaying labels in the activity dashboard
2. Need to verify that stage data from backend matches expected format
3. Need to trace how stage data flows through Task -> ActionStatus -> SegmentedProgressBar

### Next Steps
1. Log raw stage data from backend to verify format
2. Add logging in Task component to verify stage data is passed correctly
3. Check ActionStatus component's handling of stage configs
4. Verify SegmentedProgressBar's rendering of stage labels

### Questions to Answer
1. Is the stage data coming from the backend in the expected format?
2. Are we losing stage labels somewhere in the component hierarchy?
3. Is the SegmentedProgressBar receiving the correct props? 