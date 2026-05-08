---
id: reports.feedback-overview
title: Feedback Overview Report
summary: "Combined feedback overview report: volume timeline, feedback alignment, and optional contradictions for one score."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, overview, console]
related:
  - reports.reports-catalog
  - reports.feedback-alignment
  - reports.feedback-volume-timeline
  - reports.feedback-contradictions
---
# Feedback Overview Report

Feedback Overview is the broad stakeholder report for one score. It combines:

- Feedback Volume Timeline
- Feedback Alignment
- Feedback Contradictions when champion guidelines are available

## Likely User Wording

- "feedback overview"
- "score overview"
- "overall feedback report"
- "run the full report for this score"
- "give me volume, alignment, and contradictions"

## Inputs

Required:
- scorecard
- score

Optional:
- `days`, or `start_date` plus `end_date`
- timeline bucket options
- contradiction mode and topic limits

## Console Usage

Feedback Overview is a composed report, not a single report block class. If a
matching account-specific ReportConfiguration exists, use that configuration:

```tactus
local configs = report_configs{}
return configs
```

Then run the matching configuration:

```tactus
local h = plexus.report.run({
  configuration_id = "<feedback-overview-report-configuration-id>",
  parameters = {
    scorecard = "<resolved-scorecard-id>",
    score = "<resolved-score-id>",
    days = 30,
  },
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 900, depth = 1, tool_calls = 3 },
})
return {
  handle_id = h["id"],
  task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"],
  report_id = h["dispatch_result"] and h["dispatch_result"]["report_id"],
}
```

If no configuration exists, tell the user this overview is composed and offer
to run the component reports individually.

## Interpretation

Use the overview to brief stakeholders on feedback volume, feedback/prediction
agreement, and likely contradiction themes in one place. Do not use it when the
user only wants a single metric; use the specific component report instead.
