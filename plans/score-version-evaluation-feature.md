# Score Version Evaluation Feature - Implementation Summary

## Overview
Added the ability to run evaluations on specific score versions instead of just the champion version.

## Changes Made to `dashboard/components/ui/score-component.tsx`

### 1. Updated Menu Item Text (Line 1062)
- Changed "Promote" to "Promote to Champion" for clarity

### 2. Added New Menu Items to Version Dropdown (Lines 1064-1072)
Added two new menu items in the version actions dropdown:
- **Evaluate Accuracy**: Runs accuracy evaluation on the selected version
- **Evaluate Feedback**: Runs feedback evaluation on the selected version

The menu now includes:
```tsx
<DropdownMenuItem onClick={() => onPromoteToChampion(selectedVersion.id)}>
  <Crown className="mr-2 h-4 w-4" />
  Promote to Champion
</DropdownMenuItem>
<DropdownMenuSeparator />
<DropdownMenuItem onClick={() => handleEvaluateAccuracyForVersion(selectedVersion.id)}>
  <FlaskConical className="mr-2 h-4 w-4" />
  Evaluate Accuracy
</DropdownMenuItem>
<DropdownMenuItem onClick={() => handleEvaluateFeedbackForVersion(selectedVersion.id)}>
  <MessageCircleMore className="mr-2 h-4 w-4" />
  Evaluate Feedback
</DropdownMenuItem>
```

### 3. Added Handler Functions (Lines 807-863)

#### `handleEvaluateAccuracyForVersion(versionId: string)`
- Dispatches an accuracy evaluation command with the specific version ID
- Command format: `evaluate accuracy --score-id ${score.id} --version ${versionId}`
- Creates a task with type 'Accuracy Evaluation' and target 'evaluation'
- Shows success toast with the command details
- Notifies parent component via `onTaskCreated` callback

#### `handleEvaluateFeedbackForVersion(versionId: string)`
- Dispatches a feedback evaluation command with the specific version ID
- Command format: `evaluate feedback --score-id ${score.id} --version ${versionId}`
- Creates a task with type 'Feedback Evaluation' and target 'evaluation'
- Shows success toast with the command details
- Notifies parent component via `onTaskCreated` callback

## How It Works

1. **User navigates to a score** in the Evaluations dashboard
2. **Selects a non-champion version** from the version history sidebar
3. **Clicks the three-dot menu** next to the version header
4. **Sees three options**:
   - Promote to Champion
   - Evaluate Accuracy
   - Evaluate Feedback
5. **Clicking an evaluation option**:
   - Creates a remote task with the CLI command
   - Dispatches it to the evaluation worker
   - Shows a toast notification
   - Updates the task list in the parent component

## CLI Commands Used

The implementation leverages existing CLI commands that already support version parameters:

- `plexus evaluate accuracy --score-id <id> --version <version-id>`
- `plexus evaluate feedback --score-id <id> --version <version-id>`

Note: When `--version` is provided to the feedback command, it runs an accuracy evaluation using feedback items as the dataset (see `plexus/cli/evaluation/evaluations.py` lines 3083-3116).

## Testing Checklist

To verify the implementation:

1. ✓ Code compiles without syntax errors
2. ✓ Menu items only appear for non-champion versions
3. ✓ "Promote to Champion" text is correct
4. ✓ Handler functions are properly defined
5. ✓ Commands include both score-id and version parameters
6. ✓ Icons are properly imported (FlaskConical, MessageCircleMore)
7. ✓ Toast notifications are configured
8. ✓ Parent component notification via onTaskCreated

## Next Steps for Manual Testing

1. Start the dashboard application
2. Navigate to the Evaluations page
3. Select a scorecard with multiple score versions
4. Select a non-champion version
5. Click the three-dot menu next to the version
6. Verify "Promote to Champion" text appears
7. Verify "Evaluate Accuracy" and "Evaluate Feedback" options appear
8. Click "Evaluate Accuracy" and verify:
   - Task is created
   - Toast notification appears with correct command
   - Task appears in the task list
9. Click "Evaluate Feedback" and verify the same
10. Check that the tasks execute correctly on the worker

## Files Modified

- `dashboard/components/ui/score-component.tsx` (3 changes: 1 text update, 1 menu addition, 2 handler functions)

## Backup

A backup of the original file was created at:
- `dashboard/components/ui/score-component.tsx.backup`
