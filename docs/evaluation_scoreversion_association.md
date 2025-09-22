# Evaluation ScoreVersion Association

This document describes the ScoreVersion association feature for `plexus evaluate accuracy` command, including the new `--latest` flag functionality.

## Overview

Evaluation records are now properly associated with specific ScoreVersions to provide accurate tracking of which score version was used for each evaluation. This enables precise performance tracking and historical analysis of score improvements.

## Version Selection Options

### 1. **Champion Version (Default)**
```bash
plexus evaluate accuracy --scorecard my_scorecard --score my_score
```
- Uses the current champion version of the score
- This is the default behavior when no version flags are specified

### 2. **Specific Version**
```bash
plexus evaluate accuracy --scorecard my_scorecard --score my_score --version abc123-def4-5678-90ab-cdef12345678
```
- Uses the exact ScoreVersion ID specified
- Useful for evaluating a specific historical version or comparing different versions

### 3. **Latest Version (NEW)**
```bash
plexus evaluate accuracy --scorecard my_scorecard --score my_score --latest
```
- Uses the most recent ScoreVersion by `createdAt` timestamp
- Leverages the `scoreId` index sorted by `createdAt` for efficient queries
- Useful for always evaluating the newest version regardless of champion status

### 4. **YAML Mode (Local Files)**
```bash
plexus evaluate accuracy --scorecard my_scorecard --score my_score --yaml
```
- Uses local YAML configuration files
- **Does NOT associate with any ScoreVersion** since local files represent champion versions
- Existing behavior preserved for local development workflows

## Flag Validation

- `--version` and `--latest` are mutually exclusive
- Using both will show an error: "Cannot use both --version and --latest options. Choose one."
- `--yaml` flag takes precedence and prevents all ScoreVersion association

## Implementation Details

### Version Resolution Process

1. **Flag Validation**: Check for conflicting flags (`--version` + `--latest`)
2. **Version Resolution**: 
   - If `--latest`: Query for most recent ScoreVersion using GraphQL index
   - If `--version`: Use the specific version ID provided  
   - Otherwise: Use champion version from score configuration
3. **Scorecard Loading**: Load scorecard with resolved version
4. **Evaluation Association**: Associate evaluation record with determined ScoreVersion

### GraphQL Query for Latest Version
```graphql
query ListScoreVersionByScoreIdAndCreatedAt($scoreId: String!, $sortDirection: ModelSortDirection, $limit: Int) {
  listScoreVersionByScoreIdAndCreatedAt(scoreId: $scoreId, sortDirection: $sortDirection, limit: $limit) {
    items {
      id
      createdAt
    }
  }
}
```

### Database Schema Integration

The evaluation record includes `scoreVersionId` field that references the ScoreVersion:

```javascript
Evaluation: {
  // ... other fields
  scoreVersionId: a.string(),
  scoreVersion: a.belongsTo('ScoreVersion', 'scoreVersionId'),
  // ...
}
```

## Error Handling

- **API Failures**: Falls back to champion version with warning
- **Score ID Resolution**: Falls back to champion version if score ID cannot be determined
- **No Versions Found**: Falls back to champion version with warning
- **GraphQL Errors**: Graceful degradation with logging

## Logging

Comprehensive logging shows the version resolution process:

```
2025-09-04 21:30:00 [INFO] --latest flag specified for primary score: my_score
2025-09-04 21:30:01 [INFO] Fetching latest ScoreVersion for score ID: abc123-...
2025-09-04 21:30:01 [INFO] Found latest ScoreVersion: xyz789-... (created: 2025-09-04T20:00:00Z)  
2025-09-04 21:30:01 [INFO] Resolved --latest to version: xyz789-...
2025-09-04 21:30:02 [INFO] Will set scoreVersionId to xyz789-... in initial evaluation record
```

## Use Cases

1. **Performance Tracking**: Compare accuracy across different score versions
2. **Regression Testing**: Ensure new versions don't degrade performance  
3. **A/B Testing**: Evaluate different score configurations systematically
4. **Historical Analysis**: Track score performance evolution over time
5. **Development Workflow**: Always evaluate the latest development version

## Migration Notes

- Existing evaluations without `scoreVersionId` are preserved
- New evaluations automatically get ScoreVersion association
- No breaking changes to existing functionality
- YAML mode behavior unchanged for local development workflows

## Testing

Comprehensive test coverage includes:

- `tests/cli/test_evaluation_latest_flag.py` - Tests `--latest` flag functionality
- `tests/cli/test_evaluation_scoreversion_association.py` - Tests ScoreVersion association logic
- 34 test cases covering validation, resolution, error handling, and edge cases

All tests pass and provide stability for the new functionality.