# Score Version Evaluation with Dialogs - Implementation Summary

## Overview
Enhanced the evaluations dashboard to support running evaluations on specific score versions with proper dialog-based UI for configuring evaluation parameters before execution.

## Problem Solved
Previously, clicking "Evaluate Accuracy" or "Evaluate Feedback" on a score version would immediately dispatch the command without allowing the user to configure parameters. This was inconsistent with the evaluations dashboard's "Run" button behavior.

## Solution
Implemented a DRY, reusable dialog system that:
1. Opens a configuration dialog when user clicks evaluation options
2. Pre-fills scorecard and score names from context
3. Allows user to adjust parameters before running
4. Uses separate dialogs for different evaluation types (accuracy vs feedback)

## Changes Made

### 1. Created FeedbackEvaluationDialog Component
**File:** `dashboard/components/task-dispatch/dialogs/FeedbackEvaluationDialog.tsx`

A specialized dialog for feedback evaluations with parameters:
- `scorecardName`: Pre-filled from context
- `scoreName`: Pre-filled from context
- `days`: Number of days to look back for feedback items (default: 7)

Generates command: `evaluate feedback --scorecard "X" --score "Y" --days N [--version <id>]`

### 2. Enhanced EvaluationDialog
**File:** `dashboard/components/task-dispatch/dialogs/EvaluationDialog.tsx`

Added `initialOptions` prop support to pre-fill:
- `scorecardName`
- `scoreName`
- Other parameters (numberOfSamples, samplingMethod, etc.)

### 3. Updated Score Component
**File:** `dashboard/components/ui/score-component.tsx`

Changes:
- Imported both `EvaluationDialog` and `FeedbackEvaluationDialog`
- Added state management for both dialogs
- Updated handlers to open dialogs instead of immediate dispatch:
  - `handleEvaluateAccuracyForVersion`: Opens EvaluationDialog
  - `handleEvaluateFeedbackForVersion`: Opens FeedbackEvaluationDialog
- Added dispatch handlers:
  - `handleEvaluationDispatch`: Handles accuracy evaluation dispatch
  - `handleFeedbackDispatch`: Handles feedback evaluation dispatch
- Added JSX for both dialogs with proper props

### 4. Created Storybook Story
**File:** `dashboard/stories/task-dispatch/FeedbackEvaluationDialog.stories.tsx`

Two stories:
- `Default`: Shows dialog with default values
- `WithInitialValues`: Shows dialog with pre-filled scorecard/score

### 5. Updated Exports
**File:** `dashboard/components/task-dispatch/index.ts`

Added export for `FeedbackEvaluationDialog`

## User Flow

### Accuracy Evaluation on Specific Version
1. User navigates to a scorecard and selects a non-champion version
2. User clicks three-dot menu next to version header
3. User selects "Evaluate Accuracy"
4. **EvaluationDialog opens** with:
   - Pre-filled scorecard name
   - Pre-filled score name
   - Default values for other parameters
5. User adjusts parameters:
   - Number of samples
   - Sampling method
   - Load fresh data toggle
   - Visualize toggle
   - Log to LangGraph toggle
6. User clicks "Run Evaluation"
7. Command dispatched: `evaluate accuracy --scorecard "X" --score "Y" --number-of-samples N --sampling-method M --version <version-id>`
8. Task created and appears in task list
9. Toast notification confirms dispatch

### Feedback Evaluation on Specific Version
1. User navigates to a scorecard and selects a non-champion version
2. User clicks three-dot menu next to version header
3. User selects "Evaluate Feedback"
4. **FeedbackEvaluationDialog opens** with:
   - Pre-filled scorecard name
   - Pre-filled score name
   - Default days value (7)
5. User adjusts days parameter
6. User clicks "Run Evaluation"
7. Command dispatched: `evaluate feedback --scorecard "X" --score "Y" --days N --version <version-id>`
8. Task created and appears in task list
9. Toast notification confirms dispatch

## Technical Details

### Dialog System Architecture
The implementation follows the existing task-dispatch pattern:

```typescript
interface TaskDialogProps {
  action: TaskAction
  isOpen: boolean
  onClose: () => void
  onDispatch: (command: string, target?: string) => Promise<void>
}

// Extended with initialOptions
type DialogWithInitialOptions = TaskDialogProps & {
  initialOptions?: Partial<OptionsType>
}
```

### Command Generation

**Accuracy Evaluation:**
```typescript
const command = `evaluate accuracy --scorecard "${scorecardName}" --score "${scoreName}" --number-of-samples ${numberOfSamples} --sampling-method ${samplingMethod} ${loadFresh ? '--fresh' : ''} ${visualize ? '--visualize' : ''} ${logToLanggraph ? '--log-to-langgraph' : ''}`
```

**Feedback Evaluation:**
```typescript
const command = `evaluate feedback --scorecard "${scorecardName}" --score "${scoreName}" --days ${days}`
```

**Version Parameter:**
Both commands append `--version ${versionId}` when evaluating a specific version.

## DRY Principles Applied

1. **Reused existing EvaluationDialog** for accuracy evaluations instead of creating duplicate
2. **Shared task dispatch infrastructure** from evaluations dashboard
3. **Common dialog components** (Dialog, DialogContent, Button, etc.) from UI library
4. **Consistent pattern** for state management and handlers
5. **Shared types** (TaskDialogProps, TaskAction) from task-dispatch module

## Files Modified/Created

### Created
- `dashboard/components/task-dispatch/dialogs/FeedbackEvaluationDialog.tsx`
- `dashboard/stories/task-dispatch/FeedbackEvaluationDialog.stories.tsx`

### Modified
- `dashboard/components/ui/score-component.tsx`
- `dashboard/components/task-dispatch/dialogs/EvaluationDialog.tsx`
- `dashboard/components/task-dispatch/index.ts`

## Testing Checklist

### Storybook Testing
- [ ] Navigate to Evaluations/Dispatch/EvaluationDialog
- [ ] Verify dialog renders correctly
- [ ] Test all form fields
- [ ] Navigate to Evaluations/Dispatch/FeedbackEvaluationDialog
- [ ] Verify feedback dialog renders correctly
- [ ] Test days input field

### Dashboard Testing
- [ ] Navigate to scorecard with multiple versions
- [ ] Select non-champion version
- [ ] Click "Evaluate Accuracy"
  - [ ] Dialog opens
  - [ ] Scorecard/score pre-filled
  - [ ] Can adjust parameters
  - [ ] Command generates correctly
  - [ ] Task created successfully
- [ ] Click "Evaluate Feedback"
  - [ ] Dialog opens
  - [ ] Scorecard/score pre-filled
  - [ ] Can adjust days
  - [ ] Command generates correctly
  - [ ] Task created successfully

### Command Execution Testing
- [ ] Verify accuracy evaluation runs on worker
- [ ] Verify feedback evaluation runs on worker
- [ ] Verify results appear in evaluations dashboard
- [ ] Verify version ID is correctly used

## CLI Commands Reference

### Accuracy Evaluation
```bash
plexus evaluate accuracy \
  --scorecard "Call Criteria" \
  --score "Greeting" \
  --number-of-samples 10 \
  --sampling-method random \
  --version <version-id>
```

### Feedback Evaluation
```bash
plexus evaluate feedback \
  --scorecard "Call Criteria" \
  --score "Greeting" \
  --days 7 \
  --version <version-id>
```

## Benefits

1. **Consistency**: Matches the evaluations dashboard "Run" button behavior
2. **Flexibility**: Users can adjust parameters before running
3. **DRY**: Reuses existing components and patterns
4. **Type Safety**: Proper TypeScript types throughout
5. **User Experience**: Clear, intuitive workflow with proper feedback
6. **Maintainability**: Follows established patterns, easy to extend

## Future Enhancements

Potential improvements:
1. Add validation for parameter values
2. Save user's last-used parameters
3. Add tooltips explaining each parameter
4. Support for additional evaluation types (consistency, alignment)
5. Batch evaluation across multiple versions
