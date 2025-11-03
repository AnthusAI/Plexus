# Multi-Score FeedbackItems with ScoreResult Fallback

**Status**: Implementation Complete - Awaiting Testing on Whitelisted Machine  
**Date**: 2025-11-03  
**Branch**: [Current feature branch]

## Overview

Enhanced the `FeedbackItems` data source to support multiple scores with intelligent fallback from FeedbackItems to ScoreResults. This enables creating training datasets that include columns for multiple scores, where values come from human feedback when available, or AI predictions when feedback doesn't exist.

## Problem Statement

Previously, `FeedbackItems` only supported a single score. To create comprehensive training datasets for multi-score evaluation scenarios, we needed:

1. Support for multiple scores in a single dataset
2. Ability to include scores that have human feedback (FeedbackItems)
3. Ability to include scores that only have AI predictions (ScoreResults)
4. Fallback mechanism: FeedbackItem → ScoreResult → None

## Implementation Details

### 1. Parameters Update

**File**: `plexus/data/FeedbackItems.py`

```python
class Parameters(DataCache.Parameters):
    scorecard: Union[str, int]
    score: Optional[Union[str, int]] = None  # Deprecated, use scores
    scores: Optional[List[Union[str, int]]] = None  # NEW: List of scores
    days: int
    limit: Optional[int] = None
    # ... other parameters
```

**Backward Compatibility**: The validator automatically converts a single `score` parameter to a `scores` list internally.

### 2. Core Method Changes

#### `_resolve_identifiers()`
**Before**: `(scorecard_id, scorecard_name, score_id, score_name)`  
**After**: `(scorecard_id, scorecard_name, [(score_id, score_name), ...])`

Returns a list of resolved score tuples instead of a single score.

#### `_fetch_feedback_items_for_scores()` (NEW)
Fetches feedback items for all specified scores.

**Returns**: `Dict[score_id, List[FeedbackItem]]`

#### `_fetch_score_results_for_items()` (NEW)
Fetches ScoreResults for all items/scores as fallback data.

**Returns**: `Dict[item_id, Dict[score_id, ScoreResult]]`

**Key Features**:
- Queries ScoreResults for each item/score combination
- Filters out evaluation-type results (only production ScoreResults)
- Provides fallback values when FeedbackItems don't exist

#### `_create_dataset_rows()`
Completely rewritten to handle multiple scores with fallback logic.

**Algorithm**:
1. Collect all unique item IDs across all scores
2. Create one row per item (not per feedback item)
3. For each score, populate columns using fallback logic:
   - **PRIMARY**: Use `FeedbackItem.finalAnswerValue` if available
   - **FALLBACK**: Use `ScoreResult.value` if no FeedbackItem
   - **DEFAULT**: Use `None` if neither exists

#### `_generate_cache_identifier()`
Updated to include all score IDs in the cache key for proper cache invalidation.

#### `load_dataframe()`
Orchestrates the complete multi-score flow:
1. Resolve all score identifiers
2. Fetch feedback items for all scores
3. Collect unique item IDs
4. Fetch ScoreResults as fallback
5. Create dataset with proper columns
6. Cache result

### 3. Dataset Structure

**Base Columns** (same for all datasets):
- `content_id`: DynamoDB item ID
- `feedback_item_id`: Comma-separated feedback item IDs
- `IDs`: JSON hash of identifiers
- `metadata`: JSON metadata structure
- `text`: Item text content
- `call_date`: Extracted call date

**Score Columns** (3 per score):
- `{score_name}`: Score value (from FeedbackItem or ScoreResult)
- `{score_name} comment`: Explanation/comment
- `{score_name} edit comment`: Edit comment (only from FeedbackItems)

**Example** with 3 scores:
```
Columns: [
  'content_id', 'feedback_item_id', 'IDs', 'metadata', 'text', 'call_date',
  'Sentiment', 'Sentiment comment', 'Sentiment edit comment',
  'Agent Misrepresentation', 'Agent Misrepresentation comment', 'Agent Misrepresentation edit comment',
  'Compliance Issue', 'Compliance Issue comment', 'Compliance Issue edit comment'
]
```

## Usage

### YAML Configuration

```yaml
class: FeedbackItems

scorecard: 1527  # or scorecard name/key
scores:
  - "Sentiment"
  - "Agent Misrepresentation"
  - "Compliance Issue"
days: 30
limit: 100
```

### Python API

```python
from plexus.data.FeedbackItems import FeedbackItems

feedback_items = FeedbackItems(
    scorecard=1527,
    scores=["Sentiment", "Agent Misrepresentation"],
    days=30,
    limit=100
)

df = feedback_items.load_dataframe(fresh=True)
```

### Backward Compatibility

Single score still works (automatically converted to list):

```yaml
class: FeedbackItems

scorecard: 1527
score: "Sentiment"  # Still supported
days: 30
```

## Testing

### Test Configuration

**Data Source**: CallCriteriaDBCache with scorecard 1527 (Sanmar - Credit QA - Topic Modeling)

```yaml
class: CallCriteriaDBCache

queries:
  - scorecard_id: 1527
    number: 20000
    query: |
      SELECT DISTINCT TOP {number}
        xcc_report_new.scorecard AS scorecard_id,
        xcc_report_new.id AS report_id
      FROM xcc_report_new
      JOIN Transcript t ON t.XccID = xcc_report_new.ID
      JOIN tp.TranscriptSpeaker ts ON ts.TranscriptID = t.ID
      JOIN tp.SpeakerType st ON st.ID = ts.SpeakerTypeID
      WHERE xcc_report_new.scorecard = {scorecard_id}
        AND xcc_report_new.bad_call IS NULL
        AND ts.SpeakerTypeID IN (2,3)

scores:
  - "Sentiment"

balance: false
```

### Test Steps (On Whitelisted Machine)

1. **Navigate to project directory**
   ```bash
   cd /path/to/Plexus
   git checkout [feature-branch]
   git pull
   ```

2. **Load the dataset**
   ```bash
   # Using CLI
   python -m plexus.cli dataset load 76064f0d-50e5-41d2-9b0f-ae1a4f69ffe3
   
   # Or using MCP tool
   plexus_dataset_load(source_identifier="76064f0d-50e5-41d2-9b0f-ae1a4f69ffe3")
   ```

3. **Verify the dataset**
   ```python
   import pandas as pd
   
   # Load the generated parquet file
   df = pd.read_parquet('.plexus_training_data_cache/dataframes/[cache_file].parquet')
   
   # Check structure
   print(f"Shape: {df.shape}")
   print(f"Columns: {list(df.columns)}")
   
   # Verify fallback logic worked
   print(f"\nSentiment values: {df['Sentiment'].notna().sum()}/{len(df)}")
   print(f"Items with feedback_item_id: {df['feedback_item_id'].str.len().gt(0).sum()}")
   ```

4. **Expected Results**
   - Dataset should have ~20,000 rows (or up to limit if specified)
   - Columns: 6 base + 3 for "Sentiment" score = 9 total
   - Most items should have "Sentiment" values (from ScoreResults fallback)
   - Some items may have feedback_item_id (those with FeedbackItems)
   - Items with feedback_item_id should use FeedbackItem values
   - Items without feedback_item_id should use ScoreResult values

### Validation Checklist

- [ ] Dataset loads without errors
- [ ] Correct number of columns (6 base + 3 per score)
- [ ] Column names match expected format
- [ ] Items have values in score columns (not all None)
- [ ] Fallback logic works (ScoreResults used when no FeedbackItems)
- [ ] Items with FeedbackItems use those values (not ScoreResults)
- [ ] No duplicate rows (one row per item)
- [ ] Cache file generated successfully

## Files Modified

- `plexus/data/FeedbackItems.py` (~400 lines changed)
  - Updated `Parameters` class
  - Modified `_resolve_identifiers()`
  - Added `_fetch_feedback_items_for_scores()`
  - Added `_fetch_score_results_for_items()`
  - Rewrote `_create_dataset_rows()`
  - Updated `load_dataframe()`
  - Updated `_generate_cache_identifier()`

## Technical Notes

### Fallback Logic Implementation

For each item/score combination:

```python
if feedback_item exists for (item_id, score_id):
    # Use FeedbackItem (human feedback)
    value = feedback_item.finalAnswerValue
    comment = feedback_item.finalCommentValue or initialCommentValue
    edit_comment = feedback_item.editCommentValue
else:
    # Fallback to ScoreResult (AI prediction)
    score_result = score_results_map.get(item_id, {}).get(score_id)
    if score_result:
        value = score_result.value
        comment = score_result.explanation
        edit_comment = ""  # No edit comment for ScoreResults
    else:
        # No data available
        value = None
        comment = ""
        edit_comment = ""
```

### Performance Considerations

- Fetches feedback items for all scores in parallel (async)
- Fetches ScoreResults in batch for all items
- Single pass through items to create rows
- Cache identifier includes all score IDs for proper invalidation

### Limitations

- Reload mode not yet supported for multi-score datasets
- Confusion matrix sampling only uses first score
- All scores must belong to the same scorecard

## Future Enhancements

1. **Multi-score sampling**: Implement confusion matrix sampling that considers all scores
2. **Reload support**: Add reload mode for multi-score datasets
3. **Cross-scorecard support**: Allow scores from different scorecards
4. **Performance optimization**: Batch GraphQL queries for ScoreResults
5. **Metadata enrichment**: Include ScoreResult metadata (confidence, model version, etc.)

## Status

✅ Implementation complete  
✅ No linter errors  
✅ Structure verified (empty dataset test passed)  
⏳ Awaiting real data test on whitelisted machine

## Contact

For questions or issues, contact the development team or refer to:
- Implementation: `plexus/data/FeedbackItems.py`
- Test data source: https://lab.callcriteria.com/lab/sources/76064f0d-50e5-41d2-9b0f-ae1a4f69ffe3

