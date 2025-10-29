# Topic Analysis Configuration Guide

This guide documents the configuration options for the Topic Analysis report block, including the new n-gram export and topic stability assessment features.

## Table of Contents

1. [Overview](#overview)
2. [Basic Configuration](#basic-configuration)
3. [N-gram Export Configuration](#n-gram-export-configuration)
4. [Topic Stability Assessment](#topic-stability-assessment)
5. [Complete Configuration Example](#complete-configuration-example)
6. [Output Files](#output-files)
7. [Frontend Display](#frontend-display)

## Overview

The Topic Analysis report block performs automated topic modeling on text data using BERTopic. It can extract topics from documents, generate visualizations, and provide detailed analysis including n-gram statistics and stability metrics.

## Basic Configuration

```yaml
class: TopicAnalysis
data:
  source: my-data-source
  content_column: "text"
  sample_size: 2000

bertopic_analysis:
  num_topics: 10
  min_topic_size: 8
  top_n_words: 6
```

### Core Parameters

- **`num_topics`** (int, default: 10): Target number of topics to discover
- **`min_topic_size`** (int, default: 8): Minimum number of documents per topic
- **`top_n_words`** (int, default: 6): Number of keywords to extract per topic

## N-gram Export Configuration

The n-gram export feature generates a comprehensive list of all n-grams (keywords) for each topic, ranked by their c-TF-IDF scores. This helps understand the frequency and uniqueness of terms within each topic.

### Configuration

```yaml
bertopic_analysis:
  # ... other parameters ...
  
  # N-gram export configuration
  max_ngrams_per_topic: 100  # Maximum n-grams to export per topic
```

### Parameters

- **`max_ngrams_per_topic`** (int, default: 100): Maximum number of n-grams to export per topic
  - Higher values provide more comprehensive keyword lists
  - Lower values focus on the most relevant terms
  - Recommended range: 50-200

### Output

The n-gram export creates a CSV file (`complete_topic_ngrams.csv`) with the following structure:

| Column | Type | Description |
|--------|------|-------------|
| `topic_id` | int | Numeric topic identifier |
| `topic_name` | string | Human-readable topic name (fine-tuned by LLM) |
| `ngram` | string | The keyword or phrase |
| `c_tf_idf_score` | float | Relevance score (higher = more important) |
| `rank` | int | Rank within the topic (1 = most relevant) |

### Frontend Display

In the dashboard, n-grams are displayed:
- **Default view**: Top 10 n-grams per topic
- **Expandable**: Click "Show all" to view complete list
- **Per-topic**: Each topic shows its own n-grams in the topic accordion

## Topic Stability Assessment

Topic stability assessment evaluates how consistent topics are across different data samples using bootstrap sampling and Jaccard similarity. This helps determine if your topic model is robust or if parameters need adjustment.

### Configuration

```yaml
bertopic_analysis:
  # ... other parameters ...
  
  # Topic stability assessment (opt-in)
  stability:
    enabled: true              # Enable stability assessment
    n_runs: 10                 # Number of bootstrap runs
    sample_fraction: 0.8       # Fraction of data to sample per run
```

### Parameters

- **`stability.enabled`** (bool, default: false): Enable topic stability assessment
  - **Important**: This is opt-in and disabled by default
  - Enabling this will increase processing time significantly
  
- **`stability.n_runs`** (int, default: 10): Number of bootstrap sampling runs
  - More runs provide more reliable stability estimates
  - Recommended range: 5-20
  - Higher values increase processing time linearly
  
- **`stability.sample_fraction`** (float, default: 0.8): Fraction of data to sample in each run
  - Range: 0.0-1.0 (typically 0.7-0.9)
  - Higher values make samples more similar to full dataset
  - Lower values test stability under more variation

### Stability Metrics

The stability assessment produces:

1. **Mean Stability Score** (0.0-1.0):
   - **High (>0.7)**: Topics are very stable and consistent
   - **Medium (0.5-0.7)**: Topics are moderately stable
   - **Low (<0.5)**: Topics are unstable, consider adjusting parameters

2. **Per-Topic Stability**: Individual stability scores for each topic

3. **Methodology**: Description of the stability assessment method used

### Output

Stability results are saved to `topic_stability.json`:

```json
{
  "n_runs": 10,
  "sample_fraction": 0.8,
  "mean_stability": 0.75,
  "std_stability": 0.05,
  "per_topic_stability": {
    "0": 0.85,
    "1": 0.70,
    "2": 0.60
  },
  "methodology": "Bootstrap sampling with Jaccard similarity",
  "interpretation": {
    "high": "> 0.7 (topics are very stable and consistent)",
    "medium": "0.5 - 0.7 (topics are moderately stable)",
    "low": "< 0.5 (topics are unstable, consider adjusting parameters)"
  }
}
```

### Frontend Display

In the dashboard, stability metrics are displayed in a dedicated section:
- **Overall stability score** with color-coded badge (green/yellow/red)
- **Per-topic stability** showing individual topic scores
- **Methodology information** explaining how stability was calculated
- **Interpretation guide** helping understand the scores

## Complete Configuration Example

Here's a comprehensive example with all features enabled:

```yaml
class: TopicAnalysis
data:
  source: customer-calls-2024
  content_column: "transcript"
  sample_size: 2000

preprocessing:
  customer_only: false
  
  llm_extraction:
    method: "itemize"
    provider: "openai"
    model: "gpt-4o"
    prompt_template: |
      Summarize the key customer intent from this call transcript.
      
      Transcript: {{text}}
      
      Return JSON: {"items": ["..."]}
    max_retries: 3

bertopic_analysis:
  # Core topic modeling parameters
  num_topics: 10
  min_topic_size: 8
  top_n_words: 6
  
  # Stop words filtering
  remove_stop_words: true
  custom_stop_words:
    - "called to"
    - "wanted to"
    - "needed to"
  min_df: 2
  
  # N-gram export configuration
  max_ngrams_per_topic: 100
  
  # Topic stability assessment
  stability:
    enabled: true
    n_runs: 10
    sample_fraction: 0.8
  
  # Fine-tuning with LLM
  fine_tuning:
    use_representation_model: true
    provider: "openai"
    model: "gpt-4o-mini"
    nr_docs: 100
    diversity: 0.2
    doc_length: 400
    prompt: |
      Given these keywords: [KEYWORDS]
      And these examples: [DOCUMENTS]
      
      Provide a clear topic name describing the customer call reason.

final_summarization:
  model: "gpt-4o"
  provider: "openai"
  temperature: 0.3
  prompt: |
    Summarize the topic analysis results...
```

## Output Files

The topic analysis generates several output files:

### Always Generated

1. **`topics_visualization.html`**: Interactive topic visualization
2. **`heatmap_visualization.html`**: Topic similarity heatmap
3. **`topic_info.csv`**: Topic statistics and metadata

### Conditionally Generated

4. **`complete_topic_ngrams.csv`**: Complete n-gram list (always generated)
5. **`topic_stability.json`**: Stability metrics (only if `stability.enabled: true`)

## Frontend Display

### N-grams Section

For each topic in the accordion:
- Shows top 10 n-grams by default
- Displays c-TF-IDF scores
- "Show all" button expands to full list
- Sorted by rank (most relevant first)

### Stability Section

Appears after the main topic results:
- Overall stability score with interpretation
- Per-topic stability breakdown
- Methodology and configuration details
- Color-coded badges for quick assessment

## Best Practices

### N-gram Export

1. **Start with default** (`max_ngrams_per_topic: 100`):
   - Provides good balance between comprehensiveness and noise
   
2. **Increase for detailed analysis** (200-500):
   - When you need to see the full keyword distribution
   - For identifying subtle patterns
   
3. **Decrease for focused analysis** (25-50):
   - When you only care about top keywords
   - To reduce file size and processing time

### Topic Stability

1. **Enable for production models**:
   - Helps validate that your topics are robust
   - Identifies when parameters need adjustment
   
2. **Start with defaults** (`n_runs: 10`, `sample_fraction: 0.8`):
   - Good balance between accuracy and speed
   
3. **Increase runs for critical applications** (15-20):
   - More reliable stability estimates
   - Better confidence in results
   
4. **Adjust sample_fraction based on data size**:
   - Larger datasets: Can use lower fractions (0.7)
   - Smaller datasets: Use higher fractions (0.9)

### Performance Considerations

- **N-gram export**: Minimal performance impact (~1-2 seconds)
- **Stability assessment**: Significant impact (10x processing time with default settings)
  - Each run re-trains the entire model
  - Consider enabling only when needed
  - Use lower `n_runs` for faster results

## Troubleshooting

### N-grams Not Appearing

- Check that `complete_topic_ngrams.csv` exists in output directory
- Verify `max_ngrams_per_topic` is set to a reasonable value
- Ensure topics were successfully generated

### Stability Scores Are Low

Low stability (<0.5) indicates:
- Topics are not robust across different data samples
- Consider adjusting:
  - `min_topic_size`: Increase to merge small topics
  - `num_topics`: Reduce to find broader themes
  - `remove_stop_words`: Enable to reduce noise
  - Data quality: Ensure input text is clean and relevant

### Stability Assessment Takes Too Long

- Reduce `n_runs` (try 5 instead of 10)
- Reduce `sample_size` in main data configuration
- Disable stability for iterative development, enable for final runs

## Migration Guide

### Upgrading from Previous Versions

If you have existing topic analysis configurations:

1. **N-gram export is automatic**:
   - No configuration changes required
   - CSV file will be generated automatically
   - Frontend will display n-grams automatically

2. **Stability is opt-in**:
   - Add `stability` section to enable
   - Default behavior unchanged (no stability assessment)

3. **No breaking changes**:
   - All existing configurations continue to work
   - New features are additive

### Example Migration

**Before:**
```yaml
bertopic_analysis:
  num_topics: 10
  min_topic_size: 8
```

**After (with new features):**
```yaml
bertopic_analysis:
  num_topics: 10
  min_topic_size: 8
  max_ngrams_per_topic: 100  # Optional, defaults to 100
  stability:                  # Optional, disabled by default
    enabled: true
    n_runs: 10
    sample_fraction: 0.8
```

## Support

For questions or issues:
1. Check the [BERTopic documentation](https://maartengr.github.io/BERTopic/)
2. Review example configurations in `examples/topic_analysis/`
3. Contact the development team

## Changelog

### Version 2.0.0 (Current)

**New Features:**
- ✨ N-gram export with c-TF-IDF scores
- ✨ Topic stability assessment with bootstrap sampling
- ✨ Frontend display of n-grams and stability metrics

**Improvements:**
- 📊 Enhanced topic analysis output
- 🎨 Better visualization of topic quality
- 📈 Quantitative stability metrics

**Configuration:**
- `max_ngrams_per_topic`: Control n-gram export size
- `stability.enabled`: Opt-in stability assessment
- `stability.n_runs`: Configure bootstrap runs
- `stability.sample_fraction`: Configure sampling strategy


