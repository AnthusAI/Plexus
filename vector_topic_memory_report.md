parameters:
  - name: scorecard
    label: Scorecard
    type: scorecard_select
    required: true
    description: Scorecard for feedback items (transcript source)
  - name: score_id
    label: Target Score ID
    type: string
    required: false
    description: Optional specific score ID to analyze. If empty, analyzes all scores in the scorecard.
  - name: days
    label: Analysis Period (days)
    type: number
    min: 1
    max: 365
    default: 10
    description: Number of days of feedback to include

---

# Vector Topic Memory Report
## Scorecard: {{ scorecard_name }}
## Last {{ days }} days

Rebuilds topic memory from **edit comments** (reviewer feedback) in this scorecard and date range. Clusters what reviewers are saying when they correct scores. Re-indexes into OpenSearch with S3 embedding cache, global clustering, and memory weights.

```block name="Vector Topic Memory"
class: VectorTopicMemory
scorecard: {{ scorecard }}
score_id: {{ score_id }}
days: {{ days }}
data:
  content_source: edit_comment
opensearch:
  region: us-west-2
clustering:
  min_topic_size: 2
  min_samples: 2
  cluster_selection_method: eom
  cluster_selection_epsilon: 0.5
label:
  use_llm: true
  model: gpt-4o-mini
  api_key_env_var: OPENAI_API_KEY
```
