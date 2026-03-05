parameters:
  - name: scorecard
    label: Scorecard
    type: scorecard_select
    required: true
    description: Scorecard used to query production ScoreResult records
  - name: score_id
    label: Target Score
    type: score_select
    depends_on: scorecard
    required: false
    description: Optional specific score to analyze. If empty, analyzes all scores in the scorecard.
  - name: days
    label: Analysis Period (days)
    type: number
    min: 1
    max: 365
    default: 10
    description: Number of days of ScoreResult records to include

---

# Semantic Reinforcement Memory Report (ScoreResult = No)
## Scorecard: {{ scorecard_name }}
{% if score_id is defined and score_id %}
## Score: {{ score_id_name }}
{% endif %}
## Last {{ days }} days

Rebuilds topic memory from **production ScoreResult explanations** where answer value is `No`.  
This mode uses the same S3 Vectors memory pipeline (embed -> index -> cluster -> memory weight scoring).

```block name="Vector Topic Memory"
class: VectorTopicMemory
scorecard: {{ scorecard }}
{% if score_id is defined and score_id %}
score_id: {{ score_id }}
{% endif %}
days: {{ days }}
data:
  content_source: score_result_no_explanation
s3_vectors:
  region: us-west-2
clustering:
  min_topic_size: 8
  min_topic_fraction: 0.01
  target_max_topics_per_score: 30
  min_samples: 5
  cluster_selection_method: eom
  cluster_selection_epsilon: 0.5
label:
  use_llm: true
  model: gpt-4o-mini
  api_key_env_var: OPENAI_API_KEY
  max_topics_to_label: 20
  label_min_member_count: 12
```
