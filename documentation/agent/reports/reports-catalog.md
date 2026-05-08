---
id: reports.reports-catalog
title: Reports Catalog
summary: "User-facing Plexus reports, aliases, routing guidance, and report-run discovery rules for Console agents."
namespace: reports
status: canonical
disclosure: overview
audience: agent
tags: [reports, catalog, console, routing]
related:
  - reports.feedback-alignment
  - reports.feedback-overview
  - reports.scorecard-history
  - mcp.long-running-apis
---
# Reports Catalog

Use this catalog whenever a Console user asks what reports exist, asks what a
report does, or asks to run a report.

## Required Console Workflow

1. If the user asks about reports generally, load this catalog first.
2. If the user asks for a specific report, load the matching per-report topic
   before constructing the `plexus.report.run` call.
3. Resolve scorecard and score shorthand before running anything. Use
   `plexus.scorecards.search` and `plexus.score.search` instead of guessing.
4. Persisted reports must use `plexus.report.run`. Do not use
   `plexus.feedback.alignment` for a report; that is inline analysis.
5. Use `async = true` with a child budget for Console report runs.
6. Return durable IDs: `handle_id`, `task_id`, `report_id` when present.

Account-specific configured reports are separate from the code-defined reports
below. If the user asks for a named report configuration, first inspect
`report_configs{}` / `plexus.report.configurations_list{}`. Run a configured
report with `plexus.report.run{ configuration_id = "...", parameters = {...} }`.

## User-Facing Report Inventory

| User wording | Official title | Runtime target | Doc |
| --- | --- | --- | --- |
| feedback overview, score overview, overall feedback report | Feedback Overview | configured report / composed CLI report | `reports.feedback-overview` |
| alignment report, feedback alignment, AC1 report, agreement report | Feedback Alignment | `block_class = "FeedbackAlignment"` | `reports.feedback-alignment` |
| alignment timeline, feedback over time, AC1 trend | Feedback Alignment Timeline | `block_class = "FeedbackAlignmentTimeline"` | `reports.feedback-alignment-timeline` |
| feedback volume, feedback trend, volume timeline | Feedback Volume Timeline | `block_class = "FeedbackVolumeTimeline"` | `reports.feedback-volume-timeline` |
| contradictions, conflicting feedback, bad feedback, aligned examples | Feedback Contradictions / Aligned Items | `block_class = "FeedbackContradictions"` | `reports.feedback-contradictions` |
| acceptance rate, reviewer acceptance, edit acceptance | Acceptance Rate | `block_class = "AcceptanceRate"` | `reports.acceptance-rate` |
| acceptance timeline, acceptance over time | Acceptance Rate Timeline | `block_class = "AcceptanceRateTimeline"` | `reports.acceptance-rate-timeline` |
| correction rate, correction behavior, edit rate | Correction Rate | `block_class = "CorrectionRate"` | `reports.correction-rate` |
| recent feedback, latest feedback, feedback rows | Recent Feedback | `block_class = "RecentFeedback"` | `reports.recent-feedback` |
| champion timeline, champion versions, promotion timeline | Score Champion Version Timeline | `block_class = "ScoreChampionVersionTimeline"` | `reports.score-champion-version-timeline` |
| scorecard history, version history, change report | Scorecard History | `block_class = "ScorecardHistory"` | `reports.scorecard-history` |
| score results, item results, item report | Score Results Report | `block_class = "ScoreResultsReport"` | `reports.score-results-report` |

`reports.topic-analysis-configuration` documents Topic Analysis configuration.
Use it when the user specifically asks about topic modeling report setup, not
as the default answer to "what reports can you run?"

## Routing Hints

- If the user says "what reports can you run?", summarize the inventory above
  and cite `reports.reports-catalog`.
- If the user says "run a report on feedback for this score", prefer Feedback
  Overview if they want a broad stakeholder report; otherwise ask whether they
  want alignment, volume, contradictions, or recent feedback.
- If the user says "alignment", "agreement", "AC1", or "how well does feedback
  match predictions", use Feedback Alignment.
- If the user says "timeline" without another qualifier, ask whether they mean
  feedback alignment, feedback volume, acceptance rate, or champion versions.
- If the user says "champion", "promoted", or "version comparison", use Score
  Champion Version Timeline or Scorecard History depending on whether they want
  a chronological champion timeline or detailed version-change summaries.
- If the user gives a shorthand scorecard or score name, search first and then
  use the resolved IDs in `block_config`.

## Durable Async Pattern

```tactus
local h = plexus.report.run({
  block_class = "FeedbackAlignment",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    days = 30,
    memory_analysis = false,
  },
  cache_key = "console-report:<unique>",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})

return {
  handle_id = h["id"],
  status = h["status"],
  task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"],
  report_id = h["dispatch_result"] and h["dispatch_result"]["report_id"],
}
```
