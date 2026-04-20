parameters:
  - name: scorecard
    label: Scorecard
    type: scorecard_select
    required: true
  - name: score
    label: Score
    type: score_select
    required: true
    depends_on: scorecard
  - name: days
    label: Trailing Days
    type: number
    required: false
    default: 90
  - name: start_date
    label: Start Date
    type: text
    required: false
    default: ""
  - name: end_date
    label: End Date
    type: text
    required: false
    default: ""
  - name: bucket_type
    label: Timeline Bucket Type
    type: select
    required: true
    default: trailing_7d
    options:
      - value: trailing_1d
        label: Trailing 1 Day
      - value: trailing_7d
        label: Trailing 7 Day
      - value: trailing_14d
        label: Trailing 14 Day
      - value: trailing_30d
        label: Trailing 30 Day
      - value: calendar_day
        label: Calendar Day
      - value: calendar_week
        label: Calendar Week
      - value: calendar_biweek
        label: Calendar Biweek
      - value: calendar_month
        label: Calendar Month
  - name: timezone
    label: Timezone
    type: text
    required: true
    default: UTC
  - name: week_start
    label: Week Start
    type: select
    required: true
    default: monday
    options:
      - value: monday
        label: Monday
      - value: sunday
        label: Sunday
  - name: show_bucket_details
    label: Show Bucket Details
    type: boolean
    required: true
    default: false
  - name: max_items
    label: Acceptance Max Items
    type: number
    required: true
    default: 200
  - name: mode
    label: Contradictions Mode
    type: select
    required: true
    default: contradictions
    options:
      - value: contradictions
        label: Contradictions
      - value: aligned
        label: Aligned
  - name: max_feedback_items
    label: Contradictions Max Feedback Items
    type: number
    required: true
    default: 400
  - name: num_topics
    label: Contradictions Topic Count
    type: number
    required: true
    default: 8
  - name: max_concurrent
    label: Contradictions Max Concurrent
    type: number
    required: true
    default: 20
---

```block name="Feedback Alignment Timeline"
class: FeedbackAlignmentTimeline
scorecard: {{ scorecard }}
score: {{ score }}
{% if start_date and end_date %}
start_date: {{ start_date }}
end_date: {{ end_date }}
{% elif days %}
days: {{ days }}
{% endif %}
bucket_type: {{ bucket_type }}
timezone: {{ timezone }}
week_start: {{ week_start }}
show_bucket_details: {{ show_bucket_details }}
```

```block name="Acceptance Rate"
class: AcceptanceRate
scorecard: {{ scorecard }}
score: {{ score }}
{% if start_date and end_date %}
start_date: {{ start_date }}
end_date: {{ end_date }}
{% elif days %}
days: {{ days }}
{% endif %}
include_item_acceptance_rate: true
max_items: {{ max_items }}
```

```block name="Feedback Contradictions"
class: FeedbackContradictions
scorecard: {{ scorecard }}
score: {{ score }}
{% if start_date and end_date %}
start_date: {{ start_date }}
end_date: {{ end_date }}
{% elif days %}
days: {{ days }}
{% endif %}
mode: {{ mode }}
max_feedback_items: {{ max_feedback_items }}
num_topics: {{ num_topics }}
max_concurrent: {{ max_concurrent }}
```
