parameters:
  - name: scorecard
    label: Scorecard
    type: scorecard_select
    required: true
    description: Select the scorecard for this report
  - name: days
    label: Analysis Period (days)
    type: number
    min: 1
    max: 365
    default: 30
    description: Number of days to include in the feedback analysis

---

# Feedback Analysis Report
## Scorecard: {{ scorecard_name }}
## Last {{ days }} days

These agreement metrics are based on comparing the feedback edits from the scorecard {{ scorecard_name }} over the last {{ days }} days.

```block name="Feedback Analysis"
class: FeedbackAnalysis
scorecard: {{ scorecard }}
days: {{ days }}
```
