# Topic Stability Testing Guide

## What is Topic Stability?

Topic stability measures how **consistent** your topics are across different runs with different data samples. It answers: "If I run this analysis multiple times, will I get similar topics?"

## Understanding Stability Scores

### Score Ranges:
- **0.7 - 1.0** (High) ✅: Topics are reliable and consistent
- **0.5 - 0.7** (Medium) ⚠️: Moderate stability, some variation expected  
- **0.0 - 0.5** (Low) ❌: Topics vary significantly, may need more data or different parameters

### What Affects Stability?

1. **Data Size**: More documents = more stable topics
2. **Topic Specificity**: Specific topics (e.g., "credit card payments") are more stable than generic ones (e.g., "general inquiries")
3. **Min Topic Size**: Larger minimum topic sizes = more stable topics
4. **Number of Topics**: Fewer topics = generally more stable

## How to Enable Stability Assessment

Add this to your report YAML under `bertopic_analysis`:

```yaml
bertopic_analysis:
  remove_stop_words: true
  num_topics: 10
  min_topic_size: 8
  
  # Enable stability assessment
  stability:
    enabled: true         # Turn on stability testing
    n_runs: 10           # Number of bootstrap runs (default: 10)
    sample_fraction: 0.8  # Use 80% of data per run (default: 0.8)
```

## Testing Steps

### 1. Enable Stability in Your Report
Edit your report configuration and add the `stability` section shown above.

### 2. Run the Report
The stability assessment will run automatically after the main topic modeling.

**Expected time**: If your main analysis takes 2 minutes, stability with 10 runs will take ~20 minutes.

### 3. Check the Logs
```bash
# Check if stability is running
grep "Starting topic stability assessment" /tmp/plexus_report_*/log.txt

# Check stability results
grep "Topic stability assessment completed" /tmp/plexus_report_*/log.txt

# See stability scores
grep "mean_stability" /tmp/plexus_report_*/log.txt
```

### 4. View Results in Dashboard
The report will show a **Topic Stability Assessment** section with:
- **Overall stability score** displayed as a percentage with color-coded badge
  - 🟢 Green (>70%): High stability
  - 🟡 Yellow (50-70%): Medium stability  
  - 🔴 Red (<50%): Low stability
- **Per-topic stability scores** showing which topics are most/least stable
- **Methodology information** (Bootstrap sampling with Jaccard similarity)
- **Configuration details** (number of runs, sample fraction)

### 5. Check the Logs
Look for these key log messages:
```bash
# Stability was enabled and ran
grep "✅ Loaded topic stability data" /path/to/log.txt

# View the stability score
grep "Mean stability:" /path/to/log.txt

# Example output:
# ✅ Loaded topic stability data from /tmp/plexus_report_xyz/topic_stability.json
# 🔍 Mean stability score: 0.723
# 🔍 Number of runs: 10
# ✅ Added stability data to report output
#    • Mean stability: 0.723
#    • Per-topic stability scores: 9
```

### 6. Check the Attachment
A `topic_stability.json` file will be attached with detailed metrics including:
- `mean_stability`: Overall score (0.0 to 1.0)
- `per_topic_stability`: Individual scores for each topic
- `consistency_scores`: All pairwise similarity scores
- `methodology`: Description of how it was calculated

## Interpreting Your Results

### If You See Low Stability (< 0.5):

**Possible causes:**
1. **Not enough data** - Try increasing `sample_size`
2. **Topics too small** - Increase `min_topic_size` (try 15-20)
3. **Too many topics** - Reduce `num_topics` or let it auto-detect
4. **Generic topics** - Topics like "general questions" are inherently unstable

**Solutions:**
```yaml
bertopic_analysis:
  num_topics: 5          # Fewer, more distinct topics
  min_topic_size: 15     # Larger minimum size
  sample_size: 3000      # More data (if available)
```

### If You See Medium Stability (0.5 - 0.7):

**This is normal** for many real-world datasets. It means:
- Topics are generally consistent
- Some variation between runs is expected
- Results are still useful and interpretable

### If You See High Stability (> 0.7):

**Excellent!** Your topics are:
- Highly consistent across runs
- Reliable for decision-making
- Well-separated and distinct

## Comparing Stability vs. Manual Runs

### What You're Seeing Now:
Running the same report multiple times and getting "similar but not identical" results.

### What Stability Assessment Does:
- Runs the analysis 10 times internally with different data samples
- Measures how similar the topics are across those runs
- Gives you a **quantitative score** instead of just eyeballing it

### Example:

**Without stability assessment:**
- Run 1: Topics seem reasonable
- Run 2: Topics are similar but different
- You: "Are these stable? 🤔"

**With stability assessment:**
- Stability score: 0.72
- Interpretation: "High stability - topics are consistent"
- You: "Great, I can trust these results! ✅"

## Performance Notes

- **n_runs: 5** - Quick test (~10 minutes)
- **n_runs: 10** - Good balance (~20 minutes) ← **Recommended**
- **n_runs: 20** - High confidence (~40 minutes)

## Example Output

```json
{
  "n_runs": 10,
  "sample_fraction": 0.8,
  "mean_stability": 0.68,
  "per_topic_stability": {
    "0": 0.75,  // Payment inquiries - High stability
    "1": 0.82,  // Credit card issues - High stability
    "2": 0.55,  // General questions - Medium stability
    "3": 0.48   // Mixed inquiries - Low stability
  },
  "methodology": "Bootstrap sampling with Jaccard similarity"
}
```

## Quick Test

Want to test quickly? Use these settings:

```yaml
bertopic_analysis:
  num_topics: 5
  min_topic_size: 10
  stability:
    enabled: true
    n_runs: 5          # Quick test with 5 runs
    sample_fraction: 0.8
```

This will run faster and give you a sense of stability without waiting too long.

