parameters:
  - name: scorecard
    label: Scorecard
    type: scorecard_select
    required: true
    description: Select the scorecard for feedback analysis
  - name: days
    label: Analysis Period (days)
    type: number
    min: 1
    max: 365
    default: 10
    description: Number of days to include in the analysis

---

# Feedback Analysis + Vector Topic Memory Report
## Scorecard: {{ scorecard_name }}
## Last {{ days }} days

These agreement metrics are based on comparing the feedback edits from the scorecard {{ scorecard_name }} over the last {{ days }} days.

```block name="Feedback Analysis"
class: FeedbackAnalysis
scorecard: {{ scorecard }}
days: {{ days }}
```

---

## Persistent Vector Topic Memory

The VectorTopicMemory block rebuilds topic memory from the same feedback items as above — transcript text from Items linked to feedback in this scorecard and date range. Re-indexes into S3 Vectors with S3 embedding cache, global clustering, and memory weights.

```block name="Vector Topic Memory"
class: VectorTopicMemory
scorecard: {{ scorecard }}
days: {{ days }}
s3_vectors:
  region: us-west-2
clustering:
  min_topic_size: 10
```
