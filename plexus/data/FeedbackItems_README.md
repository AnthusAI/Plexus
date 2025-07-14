# FeedbackItems Data Cache

## Overview

The `FeedbackItems` class is a data cache implementation that loads datasets from feedback items. It extends the base `DataCache` class and provides functionality to:

1. **Load and sample feedback items** from a specific scorecard and score over a time period
2. **Build confusion matrices** from the feedback data (initial vs final values)
3. **Sample items from each matrix cell** to create balanced training datasets
4. **Prioritize items with edit comments** when applying sampling limits
5. **Cache results** for efficient repeated access

## Configuration Format

```yaml
data: FeedbackItems
  scorecard: "Agent Misrepresentation"  # name, key, ID, or external ID
  score: "Agent Misrepresentation"      # name, key, ID, or external ID  
  days: 14                              # required: days back to search
  limit: 200                            # optional: total dataset size limit
  limit_per_cell: 100                   # optional: max items per confusion matrix cell
```

## Parameters

### Required Parameters
- **`scorecard`** (str): Scorecard identifier - accepts name, key, ID, or external ID
- **`score`** (str): Score identifier within the scorecard - accepts name, key, ID, or external ID
- **`days`** (int): Number of days back to search for feedback items (must be positive)

### Optional Parameters
- **`limit`** (int): Maximum total number of items in the final dataset
- **`limit_per_cell`** (int): Maximum number of items to sample from each confusion matrix cell
- **`cache_file`** (str): Cache file name (default: "feedback_items_cache.parquet")
- **`local_cache_directory`** (str): Local cache directory (default: "./.plexus_training_data_cache/")

## Sampling Logic

The class implements a sophisticated sampling strategy that prioritizes items with edit comments:

### Sampling Rules
1. **If fewer items than limit**: Take all items
2. **If more items than limit**: Prioritize items with edit comments
3. **If still more than limit after including all with edit comments**: Randomly sample from items with edit comments

### Confusion Matrix Sampling
- Items are grouped by confusion matrix cells based on `(initial_value, final_value)` pairs
- Each cell is sampled independently up to `limit_per_cell` 
- Items with edit comments are prioritized within each cell
- An overall `limit` is applied across all cells after sampling

## Dataset Structure

The generated dataset includes these columns:

### Core Columns
- **`{score_name}`**: Final answer value (ground truth label)
- **`{score_name} comment`**: Final comment/explanation
- **`{score_name} initial`**: Initial answer value (for reference)
- **`{score_name} initial comment`**: Initial comment (for reference)
- **`{score_name} edit comment`**: Edit comment (if available)

### Metadata Columns
- **`item_id`**: Feedback item ID
- **`external_id`**: External item ID
- **`text`**: Item description/content
- **`identifiers`**: Item identifiers
- **`scorecard_id`**, **`score_id`**, **`account_id`**: System IDs
- **`created_at`**, **`updated_at`**, **`edited_at`**: Timestamps
- **`editor_name`**, **`is_agreement`**: Additional metadata

## Example Usage

```python
from plexus.data.FeedbackItems import FeedbackItems

# Initialize the data cache
feedback_cache = FeedbackItems(
    scorecard="Customer Service Quality",
    score="Agent Politeness", 
    days=30,
    limit=500,
    limit_per_cell=50
)

# Load the dataset
df = feedback_cache.load_dataframe(fresh=True)

# The dataframe now contains sampled feedback items with:
# - 'Agent Politeness' column containing ground truth labels
# - 'Agent Politeness comment' column containing explanations
# - Balanced sampling across confusion matrix cells
# - Prioritization of items with edit comments
```

## Caching

The class provides automatic caching:
- **Cache key generation** based on all parameters for uniqueness
- **Parquet format** for efficient storage and loading
- **Fresh data option** to bypass cache when needed
- **Cache invalidation** through the `fresh=True` parameter

## Testing

Comprehensive test cases are provided in `test_feedback_sampling.py` covering:

1. **Scenario 1**: Fewer items than limit (take all)
2. **Scenario 2**: Prioritize edit comments with room for others
3. **Scenario 3**: More items with comments than limit (sample from comments)
4. **Scenario 4**: No items with comments (random sampling)
5. **Scenario 5**: All items have comments (random sampling from all)
6. **Edge cases**: Empty lists, zero limits

## Integration

The class integrates with existing Plexus infrastructure:
- Uses `FeedbackService` for efficient feedback item retrieval
- Leverages `resolve_scorecard_identifier` and `resolve_score_identifier` for flexible ID resolution
- Follows the same patterns as other data cache classes like `CallCriteriaDBCache`
- Compatible with existing configuration and evaluation frameworks