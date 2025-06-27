# Plexus Dataset Configuration YAML Format Documentation

## Core Concepts

A **Dataset** configuration defines how to retrieve and prepare data for training and evaluation in Plexus. The CallCriteriaDBCache class provides flexible data loading from the Call Criteria database using two main approaches: **queries** for database searches and **searches** for working with specific lists of IDs.

## Basic Structure

```yaml
class: CallCriteriaDBCache

# Use either queries, searches, or both
queries:
  - # Query configuration options
searches:
  - # Search configuration options

balance: false  # Whether to balance positive/negative examples
```

## Queries Section

The `queries` section executes database queries to retrieve data based on various criteria.

### Basic Query Configuration

```yaml
queries:
  - scorecard_id: 1329    # Required: Scorecard ID to query
    number: 8000          # Optional: Maximum number of records (default: unlimited)
```

### Date Range Filtering

```yaml
queries:
  - scorecard_id: 1464
    start_date: "2024-01-01"  # Format: YYYY-MM-DD
    end_date: "2024-12-31"    # Format: YYYY-MM-DD
```

### Score-Based Filtering

Filter records based on specific score values:

```yaml
queries:
  - scorecard_id: 555
    score_id: 12345           # Score ID to filter on
    answer: "Yes"             # Specific answer value to match
    # OR use include/exclude lists:
    include_values: ["Yes", "Good"]  # Only include these values
    exclude_values: ["No", "Bad"]    # Exclude these values
```

### Quality Filters

```yaml
queries:
  - scorecard_id: 1329
    bad_call: false                    # Include/exclude bad calls (default: false)
    minimum_calibration_count: 3       # Minimum number of calibrations required
```

### Reviewer Filtering

```yaml
queries:
  - scorecard_id: 555
    reviewer: "john.smith"  # Filter by specific reviewer
```

### Custom SQL Queries

Execute custom SQL with parameter substitution:

```yaml
queries:
  - scorecard_id: 1329
    number: 8000
    query: |
      SELECT DISTINCT TOP {number} 
          a.scorecard as scorecard_id,
          a.f_id,
          a.call_date
      FROM 
          vwForm a 
      JOIN 
          otherformdata ofd ON a.review_id = ofd.xcc_id
      WHERE 
          a.scorecard = {scorecard_id} 
          AND a.transcript_analyzed IS NOT NULL 
          AND a.max_reviews != -1
          AND ofd.data_key = 'SOLD_FLAG'
          AND ofd.data_value = '1'
      ORDER BY 
          a.call_date DESC, a.f_id DESC
```

**Note:** Custom queries must select either:
- `f_id` (preferred), OR  
- Both `content_id` and `scorecard_id`

### File-Based Queries

Load form IDs from CSV/Excel files:

```yaml
queries:
  - scorecard_id: 1329
    item_list_filename: "path/to/file.csv"  # CSV or Excel file
    # File must contain one of these columns (case-insensitive):
    # - form_id or f_id (preferred)
    # - report_id 
    # - phone (matches against phone/ani fields)
```

### Value Overrides

Override database values with custom values:

```yaml
queries:
  - scorecard_id: 555
    values:
      - "Score Name": "Override Value"
        "Another Score": "Another Override"
```

## Searches Section

The `searches` section works with predefined lists of IDs rather than database queries.

### Direct Item Lists

Specify form IDs directly in the configuration:

```yaml
searches:
  - scorecard_id: 1329
    items:
      - form_id: 12345
      - form_id: 12346
      - form_id: 12347
```

### File-Based Searches

Load form IDs from CSV/Excel files:

```yaml
searches:
  - scorecard_id: 1329
    item_list_filename: "training_data.csv"
```

**Supported file columns (case-insensitive):**
- `form_id` or `f_id` - Direct form ID lookup (preferred)
- `report_id` - Converts report IDs to form IDs
- `phone` - Matches against phone/ANI fields in database

### Column Mappings

Map CSV columns to score values in the resulting dataset:

```yaml
searches:
  - scorecard_id: 1329
    item_list_filename: "data_with_labels.csv"
    column_mappings:
      - dataframe_column: "Quality Score"    # Name in resulting dataset
        csv_column: "Human_Quality_Rating"   # Column name in CSV file
      - dataframe_column: "Sentiment"
        csv_column: "Manual_Sentiment"
```

### Value Overrides in Searches

Override database values for all items in the search:

```yaml
searches:
  - scorecard_id: 1329
    item_list_filename: "positive_examples.csv"
    values:
      - "Training Label": "Positive"
        "Data Source": "Manual Review"
```

## Advanced Configuration

### Combining Queries and Searches

You can use both queries and searches in the same dataset:

```yaml
class: CallCriteriaDBCache

queries:
  - scorecard_id: 1329
    number: 5000
    start_date: "2024-01-01"

searches:
  - scorecard_id: 1329
    item_list_filename: "additional_examples.csv"

balance: false
```

### Data Balancing

Enable automatic balancing of positive/negative examples:

```yaml
class: CallCriteriaDBCache

queries:
  - scorecard_id: 555
    score_id: 12345

balance: true  # Automatically balance the dataset
```

### Multiple Configurations

Process multiple scorecards or different criteria:

```yaml
class: CallCriteriaDBCache

queries:
  - scorecard_id: 1329
    number: 3000
    answer: "Yes"
  - scorecard_id: 1330
    number: 3000
    answer: "No"

searches:
  - scorecard_id: 1329
    item_list_filename: "scorecard_1329_examples.csv"
  - scorecard_id: 1330
    item_list_filename: "scorecard_1330_examples.csv"

balance: false
```

## Complete Example

```yaml
class: CallCriteriaDBCache

queries:
  # Get recent high-quality calls
  - scorecard_id: 1329
    number: 5000
    start_date: "2024-06-01"
    minimum_calibration_count: 2
    bad_call: false
    exclude_values: ["Unclear", "N/A"]
    
  # Custom query for specific criteria
  - scorecard_id: 1464
    query: |
      SELECT TOP 2000 f_id
      FROM vwForm vf
      JOIN otherformdata ofd ON vf.review_id = ofd.xcc_id
      WHERE vf.scorecard = {scorecard_id}
      AND ofd.data_key = 'CUSTOMER_TYPE'
      AND ofd.data_value = 'Premium'
      ORDER BY vf.call_date DESC

searches:
  # Manually curated examples with labels
  - scorecard_id: 1329
    item_list_filename: "expert_labeled_calls.csv"
    column_mappings:
      - dataframe_column: "Expert Rating"
        csv_column: "quality_score"
      - dataframe_column: "Confidence"
        csv_column: "expert_confidence"
    
  # Override values for specific test set
  - scorecard_id: 1329
    item_list_filename: "test_set.csv"
    values:
      - "Dataset Split": "Test"
        "Source": "Holdout Set"

balance: true
```

## Output Dataset Structure

The resulting dataset will contain these columns:

- `scorecard_id`: The scorecard ID
- `content_id`: Unique report/content identifier  
- `form_id`: Form ID (if available)
- `text`: The call transcript text
- `metadata`: JSON string containing call metadata
- `IDs`: JSON array with form ID, report ID, and session ID
- Score columns: One column per score with the score name
- Comment columns: `{Score Name} comment` for each score
- Confidence columns: `{Score Name} confidence` for scores with confidence values

## Best Practices

1. **Use specific date ranges** to ensure reproducible datasets
2. **Include quality filters** like `minimum_calibration_count` and `bad_call: false`
3. **Limit result sets** with `number` to avoid memory issues
4. **Use column mappings** when you have external labels to incorporate
5. **Test with small numbers first** before running large queries
6. **Combine multiple approaches** - use queries for broad criteria and searches for specific examples
