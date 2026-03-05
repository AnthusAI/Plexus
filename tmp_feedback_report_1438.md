# Feedback Analysis - Scorecard 1438 (90 days)

parameters:
  - name: scorecard
    type: scorecard_select
    label: Scorecard
  - name: days
    type: number
    label: Days
    default: 90

---

# Feedback Analysis Report

```block
class: FeedbackAnalysis
config:
  scorecard: "{{ scorecard }}"
  days: {{ days }}
```
