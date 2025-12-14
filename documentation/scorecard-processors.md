# Scorecard Processors

## Overview

Processors are a powerful feature in Plexus that allow you to transform text and filter datasets automatically during training, evaluation, and prediction. They ensure consistent data preprocessing across all operations, which is critical for model performance and reliability.

**Key Benefits:**
- **Consistency**: Same transformations apply across training, evaluation, and production
- **Modularity**: Chain multiple processors together
- **Flexibility**: Configure at scorecard or score level
- **Reusability**: Use same processors across multiple scores

## Configuration Format

Processors can be configured at two levels in your scorecard YAML:

### Score-Level Configuration (Recommended)

Score-level processors apply only to a specific score:

```yaml
scores:
  - name: IVR Present
    id: 33612
    class: ExplainableClassifier
    data:
      processors:
        - class: RemoveSpeakerIdentifiersTranscriptFilter
        - class: RemoveStopWordsTranscriptFilter
      queries:
        - scorecard-id: 975
          number: 10000
```

### Scorecard-Level Configuration

Scorecard-level processors apply to ALL scores in the scorecard (unless overridden at the score level):

```yaml
name: My Scorecard
id: 975
processors:
  - class: FilterCustomerOnlyProcessor
scores:
  - name: Score 1
    # Will use scorecard-level processors
  - name: Score 2
    data:
      processors:
        - class: RemoveSpeakerIdentifiersTranscriptFilter
    # Will use score-level processors (overrides scorecard-level)
```

**Important**: Score-level processors completely override scorecard-level processors. They don't merge.

---

## Text Preprocessing Processors

Text preprocessing processors operate on transcript text during all operations (training, evaluation, prediction).

### RemoveSpeakerIdentifiersTranscriptFilter

Removes speaker labels like "Agent:", "Customer:", "Speaker1:" from transcripts.

**Use Case**: When you want to analyze only the content without speaker attribution, or when speaker labels might confuse the model.

**Configuration**:
```yaml
processors:
  - class: RemoveSpeakerIdentifiersTranscriptFilter
```

**Example Transformation**:
- **Before**: `"Agent: Hello there. Customer: Hi, I need help."`
- **After**: `"Hello there. Hi, I need help."`

**Parameters**: None

**Implementation Details**:
- Uses regex pattern: `(?:^|\b)\w+:\s*`
- Removes labels at line start or word boundaries
- Works with multiline transcripts
- Handles various formats: Agent:, Speaker1:, User123:, etc.

---

### FilterCustomerOnlyProcessor

Keeps only customer utterances, removing all agent speech. Also removes speaker labels in the process.

**Use Case**: Analyzing customer sentiment, language patterns, or behavior without agent influence.

**Configuration**:
```yaml
processors:
  - class: FilterCustomerOnlyProcessor
```

**Example Transformation**:
- **Before**: `"Agent: Hello. Customer: Hi there. Agent: How can I help?"`
- **After**: `"Hi there."`

**Parameters**: None

**Notes**:
- This processor automatically removes speaker labels
- If chaining with `RemoveSpeakerIdentifiersTranscriptFilter`, apply this first
- Returns minimal output if no customer speech exists

**Common Pattern**:
```yaml
processors:
  - class: FilterCustomerOnlyProcessor
  # No need for RemoveSpeakerIdentifiersTranscriptFilter since this already removes labels
```

---

### RemoveStopWordsTranscriptFilter

Removes common English stop words (the, a, an, is, etc.) from text.

**Use Case**: Focus models on meaningful keywords rather than common words. Useful for keyword-based classifiers.

**Configuration**:
```yaml
processors:
  - class: RemoveStopWordsTranscriptFilter
```

**Example Transformation**:
- **Before**: `"I am very happy with the excellent service"`
- **After**: `"happy excellent service"`

**Parameters**: None

**Stop Words Removed**: Uses NLTK's English stopwords list (e.g., "the", "a", "an", "is", "am", "are", "was", "were", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "should", "could", "may", "might", etc.)

**Caution**: May remove contextually important words. Test with your specific use case.

---

### ExpandContractionsProcessor

Expands English contractions to their full forms.

**Use Case**: Normalize text for better model understanding, especially when training data has inconsistent contraction usage.

**Configuration**:
```yaml
processors:
  - class: ExpandContractionsProcessor
```

**Example Transformations**:
- **Before**: `"I don't think it's working"`
- **After**: `"I do not think it is working"`

**Common Expansions**:
- don't → do not
- won't → will not
- can't → cannot
- it's → it is
- I'll → I will
- they're → they are
- you've → you have

**Parameters**: None

**Library Used**: Uses the `contractions` Python library

---

### AddUnknownSpeakerIdentifiersTranscriptFilter

Replaces all speaker labels with "Unknown Speaker:", anonymizing speakers while maintaining turn structure.

**Use Case**: Privacy protection, speaker anonymization, or normalizing different speaker label formats.

**Configuration**:
```yaml
processors:
  - class: AddUnknownSpeakerIdentifiersTranscriptFilter
```

**Example Transformation**:
- **Before**: `"Agent: Hello. Customer: Hi there."`
- **After**: `"Unknown Speaker: Hello. Unknown Speaker: Hi there."`

**Parameters**: None

**Use Cases**:
- Privacy-preserving model training
- Normalizing inconsistent speaker labels
- Removing speaker-specific information

---

### AddEnumeratedSpeakerIdentifiersTranscriptFilter

Replaces speaker identifiers with enumerated labels (Speaker A, Speaker B, etc.) in order of first appearance. This processor maintains speaker identity while normalizing labels.

**Use Case**: Normalize speaker labels while preserving speaker identity, useful for multi-speaker analysis or when you need consistent speaker labeling across conversations.

**Configuration**:
```yaml
processors:
  - class: AddEnumeratedSpeakerIdentifiersTranscriptFilter
```

**Example Transformation**:
- **Before**: `"Agent: Hello. Customer: Hi there. Agent: How can I help?"`
- **After**: `"Speaker A: Hello. Speaker B: Hi there. Speaker A: How can I help?"`

**How It Works**:
1. **First Pass**: Identifies all unique speaker identifiers in order of first appearance
2. **Second Pass**: Replaces each speaker with enumerated label (A, B, C, etc.)
3. **Consistency**: Same speaker always gets the same label

**Parameters**: None

**Label Format**:
- First 26 speakers: A, B, C, ... Z
- Beyond 26 speakers: AA, AB, AC, ... (if needed)

**Use Cases**:
- Normalize inconsistent speaker formats (Agent, Rep, User123 → Speaker A, B, C)
- Maintain speaker identity for analysis while anonymizing names
- Prepare transcripts for models that need consistent speaker labels

**Example with Multiple Formats**:
- **Before**: `"Agent: Hi. Speaker1: Hello. Rep: Good morning."`
- **After**: `"Speaker A: Hi. Speaker B: Hello. Speaker C: Good morning."`

---

### RelevantWindowsTranscriptFilter

Filters transcript to relevant windows based on specific criteria.

**Use Case**: Focus analysis on specific conversation segments.

**Configuration**:
```yaml
processors:
  - class: RelevantWindowsTranscriptFilter
    parameters:
      # Parameters depend on implementation
```

**Parameters**: Varies based on implementation (consult source code or team)

**Note**: This processor has specific implementation details that may vary by use case.

---

## Dataset Filtering Processors

Dataset processors operate on entire dataframes during **training only**. They filter or transform rows before model training. These do NOT apply during prediction or evaluation.

### ByColumnValueDatasetFilter

Filter dataset rows based on column values.

**Use Case**: Include or exclude specific data subsets during training.

**Configuration**:
```yaml
data:
  processors:
    - class: ByColumnValueDatasetFilter
      parameters:
        filter-type: include  # or 'exclude'
        column-name: call_type
        value: inbound
```

**Parameters**:
- `filter-type` (required): Either "include" or "exclude"
- `column-name` (required): Name of column to filter on
- `value` (required): Value to match

**Example**:
```yaml
# Only train on inbound calls
processors:
  - class: ByColumnValueDatasetFilter
    parameters:
      filter-type: include
      column-name: call_type
      value: inbound
```

**Behavior**:
- `include`: Keeps only rows where column equals value
- `exclude`: Removes rows where column equals value

---

### DownsampleClassDatasetFilter

Downsample majority class to balance dataset.

**Use Case**: Handle class imbalance in training data by reducing the majority class to match the largest minority class.

**Configuration**:
```yaml
data:
  processors:
    - class: DownsampleClassDatasetFilter
      parameters:
        column-name: label
        value: yes
```

**Parameters**:
- `column-name` (required): Name of label column
- `value` (required): Class value to downsample

**Example**:
```yaml
# If 'yes' has 5000 samples and 'no' has 2000 samples,
# downsample 'yes' to 2000 samples
processors:
  - class: DownsampleClassDatasetFilter
    parameters:
      column-name: sentiment
      value: positive
```

**Behavior**:
- If target class is already smaller than other classes: no downsampling
- If target class is larger: randomly samples to match largest non-target class
- Uses `random_state=1` for reproducibility

---

### ColumnDatasetFilter

Select or exclude specific columns from dataset.

**Use Case**: Remove unnecessary columns or focus on specific features.

**Configuration**:
```yaml
data:
  processors:
    - class: ColumnDatasetFilter
      parameters:
        filter-type: include  # or 'exclude'
        columns: [text, label, content_id]
```

**Parameters**:
- `filter-type` (required): Either "include" or "exclude"
- `columns` (required): List of column names

**Special Behavior**:
- In `include` mode, the 'text' column is ALWAYS included automatically
- In `exclude` mode, excludes specified columns (errors are ignored if column doesn't exist)

**Example**:
```yaml
# Keep only essential columns
processors:
  - class: ColumnDatasetFilter
    parameters:
      filter-type: include
      columns: [label, metadata]  # 'text' is auto-included
```

---

### MergeColumnsDatasetFilter

Merge multiple label columns into a single column with new label values.

**Use Case**: Combine related labels for multi-task learning or simplify label structure.

**Configuration**:
```yaml
data:
  processors:
    - class: MergeColumnsDatasetFilter
      parameters:
        new_column_name: combined_label
        columns_to_merge:
          Wrong Phone Number - Internal:
            labels: [yes]
            new_label: Internal
          Wrong Phone Number - External:
            labels: [Diff. Trucking, Diff. Co., Other]
            new_label: External
```

**Parameters**:
- `new_column_name` (required): Name for merged output column
- `columns_to_merge` (required): Dictionary mapping source columns to new labels
  - Each entry has:
    - `labels`: List of values to match in that column
    - `new_label`: New label value to assign

**Example from Legacy Scorecard**:
```yaml
# Merge two "wrong phone number" columns into one
processors:
  - class: MergeColumnsDatasetFilter
    parameters:
      columns_to_merge:
        'Wrong Phone Number - Internal':
          labels: ['Yes']
          new_label: 'Internal'
        'Wrong Phone Number - External':
          labels: ['Diff. Trucking', 'Diff. Co.', 'Other']
          new_label: 'External'
      new_column_name: 'Wrong Phone Number - Combined'
```

**Behavior**:
- Uses XOR logic to identify uniquely matched rows
- Preserves original columns
- Creates new column with merged labels

---

## Processor Execution

### Order Matters

Processors are applied sequentially in the order specified. The output of one processor becomes the input to the next.

**Example**:
```yaml
processors:
  - class: FilterCustomerOnlyProcessor      # 1. Keep only customer speech
  - class: RemoveSpeakerIdentifiersTranscriptFilter  # 2. Remove "Customer:" labels
  - class: ExpandContractionsProcessor      # 3. Expand contractions
```

**Result**: Customer speech with no labels and expanded contractions.

**Wrong Order Example**:
```yaml
processors:
  - class: RemoveSpeakerIdentifiersTranscriptFilter  # 1. Remove labels FIRST
  - class: FilterCustomerOnlyProcessor      # 2. Can't filter - labels are gone!
```

**Result**: May not filter properly since `FilterCustomerOnlyProcessor` looks for "Customer:" labels.

### When Processors Run

1. **Training**: Processors run once during `ScoreData.process_data()` before model training
2. **Evaluation**: Processors run on each text during evaluation via `Scorecard.score_entire_text()`
3. **Prediction**: Processors run on each text during production predictions via `Score.apply_processors_to_text()`

**Critical Guarantee**: The same processor configuration produces identical transformations across all three operations.

### Error Handling

If a processor fails:
- The error is logged
- Processing continues with remaining processors
- Original text is used if all processors fail
- Individual processor failures don't crash the entire pipeline

---

## Common Processor Chains

### Customer-Only Analysis
```yaml
processors:
  - class: FilterCustomerOnlyProcessor
  # No need for RemoveSpeakerIdentifiersTranscriptFilter - already removes labels
```

### Clean Text for Keyword Extraction
```yaml
processors:
  - class: RemoveStopWordsTranscriptFilter
  - class: RemoveSpeakerIdentifiersTranscriptFilter
```

### Normalized Text for Training
```yaml
processors:
  - class: ExpandContractionsProcessor
  - class: RemoveSpeakerIdentifiersTranscriptFilter
```

### Customer Analysis with Normalized Text
```yaml
processors:
  - class: FilterCustomerOnlyProcessor
  - class: ExpandContractionsProcessor
```

### Balanced Training Dataset
```yaml
data:
  processors:
    # First filter to subset
    - class: ByColumnValueDatasetFilter
      parameters:
        filter-type: include
        column-name: call_type
        value: inbound
    # Then balance classes
    - class: DownsampleClassDatasetFilter
      parameters:
        column-name: label
        value: positive
```

---

## Troubleshooting

### Processor Not Found

**Error**: `ValueError: Unknown processor: MyProcessor`

**Solutions**:
1. Verify processor class name is spelled correctly (case-sensitive)
2. Check that processor exists in `plexus/processors/` directory
3. Verify processor is imported in `plexus/processors/__init__.py`

**Available Processors**:
- Text: RemoveSpeakerIdentifiersTranscriptFilter, FilterCustomerOnlyProcessor, RemoveStopWordsTranscriptFilter, ExpandContractionsProcessor, AddUnknownSpeakerIdentifiersTranscriptFilter, RelevantWindowsTranscriptFilter
- Dataset: ByColumnValueDatasetFilter, ColumnDatasetFilter, DownsampleClassDatasetFilter, MergeColumnsDatasetFilter

### Processor Has No Effect

**Possible Causes**:
1. Text doesn't match expected format (e.g., no speaker labels for `RemoveSpeakerIdentifiersTranscriptFilter`)
2. Processor order is wrong (e.g., removing labels before filtering by speaker)
3. Parameters are missing or incorrect

**Debugging**:
- Check training logs for processor summary tables showing "Before" and "After"
- Examine sample text to see actual transformations
- Verify text format matches processor expectations

### Parameter Errors

**Error**: Processor fails with `KeyError` or `AttributeError`

**Solutions**:
- Verify all required parameters are provided
- Check parameter names match exactly (note: hyphens like `column-name` not underscores)
- Review processor documentation above for required parameters

**Example**:
```yaml
# WRONG - missing required parameter
processors:
  - class: ByColumnValueDatasetFilter
    parameters:
      filter-type: include
      # Missing: column-name and value

# RIGHT
processors:
  - class: ByColumnValueDatasetFilter
    parameters:
      filter-type: include
      column-name: status
      value: active
```

### Dataset Processor Applied During Prediction

**Issue**: Dataset processors (ByColumnValueDatasetFilter, etc.) don't work during prediction

**Explanation**: This is expected behavior! Dataset processors only run during **training**. They're designed to filter/transform training datasets, not individual prediction inputs.

**Solution**: Use text preprocessing processors for prediction-time transformations.

### Training vs Prediction Inconsistency

**Issue**: Model performs differently in training vs production

**Cause**: Processors may not be applied consistently

**Solution**:
1. Verify same processor configuration in both contexts
2. Check logs to confirm processors ran during training
3. Test with small example to verify transformations match

---

## Creating Custom Processors

### For Developers

To create a custom processor:

1. **Create processor class** in `plexus/processors/YourProcessor.py`:

```python
import pandas as pd
from plexus.processors.DataframeProcessor import DataframeProcessor

class YourProcessor(DataframeProcessor):
    def __init__(self, **parameters):
        super().__init__(**parameters)
        # Extract parameters
        self.your_param = parameters.get('your_param')

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        # Get a sample for display
        if len(dataframe) > 0:
            random_row = dataframe.sample(n=1).index[0]
            self.before_summary = dataframe.at[random_row, 'text'][:100]

        # Transform text
        dataframe['text'] = dataframe['text'].apply(
            lambda text: self.transform_text(text)
        )

        # Get sample after transformation
        if len(dataframe) > 0:
            self.after_summary = dataframe.at[random_row, 'text'][:100]

        self.display_summary()
        return dataframe

    def transform_text(self, text: str) -> str:
        # Your transformation logic here
        return text.upper()  # Example
```

2. **Import in `__init__.py`**:

```python
from .YourProcessor import YourProcessor
```

3. **Use in scorecard YAML**:

```yaml
processors:
  - class: YourProcessor
    parameters:
      your_param: value
```

### Best Practices

1. **Always call `super().__init__(**parameters)`** in your `__init__` method
2. **Store parameters as instance variables** for access in `process()`
3. **Set `before_summary` and `after_summary`** to show transformation results
4. **Call `self.display_summary()`** to show rich console output
5. **Return the dataframe** from `process()` method
6. **Handle edge cases**: empty text, None values, missing columns
7. **Add clear docstrings** explaining purpose and parameters

---

## Performance Considerations

### Training Performance

- Processors run once per dataset during training
- Multiple processors chain sequentially
- Use dataset processors to reduce dataset size early
- Text processors operate on each row

### Prediction Performance

- Processors run on EVERY prediction
- Keep processor chains minimal for production
- Text transformations add latency
- Consider caching if same text predicted multiple times

### Recommendations

- **Training**: Use extensive preprocessing (stopwords, expansions, filtering)
- **Production**: Keep minimal processors for performance
- **Balance**: More preprocessing → better model → potentially simpler production pipeline

---

## FAQ

**Q: Can I use different processors for training vs prediction?**
A: No. Consistency across training and prediction is critical. The same processor configuration must be used in both contexts.

**Q: How do I debug processor transformations?**
A: Check training logs for processor summary tables showing "Before" and "After" examples. Each processor displays a sample transformation.

**Q: Can processors access metadata or other columns?**
A: Yes. Processors receive the full dataframe. Text processors typically operate on the 'text' column, but can access any column.

**Q: What happens if a processor fails?**
A: The error is logged, processing continues with remaining processors, and the original text is used if all processors fail.

**Q: Do I need to retrain when changing processors?**
A: Yes. Changing processors changes the input representation, so the model must be retrained.

**Q: Can I chain dataset and text processors?**
A: Yes! Dataset processors run first during training, then text processors. Example:
```yaml
data:
  processors:
    - class: ByColumnValueDatasetFilter  # Dataset processor
      parameters:
        filter-type: include
        column-name: quality
        value: high
    - class: RemoveSpeakerIdentifiersTranscriptFilter  # Text processor
```

---

## Additional Resources

- **Source Code**: `plexus/processors/`
- **Tests**: `plexus/tests/test_processor*.py`
- **Factory**: `plexus/processors/ProcessorFactory.py`
- **Integration**:
  - Training: `plexus/scores/core/ScoreData.py` (lines 188-232)
  - Prediction: `plexus/scores/Score.py` (lines 847-901)
  - Evaluation: `plexus/Scorecard.py` (lines 480-507)

---

## Version History

- **Current**: Full processor system with 10+ processors
- **Legacy**: Original implementation in Contactics NI 3.0 scorecard

---

**Need Help?** Contact the Plexus team or check the test files for usage examples.
