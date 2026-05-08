---
id: reports._index
title: Reports
summary: "Report block authoring, persistence, and analysis configuration."
namespace: reports
status: canonical
disclosure: overview
audience: agent
tags: [index]
---
# Reports

Report block authoring, persistence, and analysis configuration.

Start with `reports.reports-catalog` when a Console user asks what reports
exist, uses a shorthand report name, or asks to run a report.

## Topics in this namespace

Use `plexus.docs.list({ namespace = "reports" })` to list every topic, then `plexus.docs.get({ key = "<id>" })` for the full doc.

Current canonical topics include:
- `reports.reports-catalog` — user-facing report inventory, aliases, routing rules, and durable async patterns.
- `reports.feedback-overview` — composed feedback overview report guidance.
- `reports.feedback-alignment` — feedback/prediction agreement and mismatch report.
- `reports.feedback-alignment-timeline` — alignment/AC1 trend over time.
- `reports.feedback-volume-timeline` — feedback volume trend over time.
- `reports.feedback-contradictions` — contradiction and aligned-example analysis against guidelines.
- `reports.acceptance-rate` — score-result acceptance metrics.
- `reports.acceptance-rate-timeline` — acceptance trend over time.
- `reports.correction-rate` — feedback correction behavior.
- `reports.recent-feedback` — recent feedback examples.
- `reports.score-champion-version-timeline` — champion promotion timeline.
- `reports.scorecard-history` — ScorecardHistory scope, filters, summaries, evaluations, and output contract.
- `reports.score-results-report` — item-specific score result report.
- `reports.topic-analysis-configuration` — TopicAnalysis configuration details.
- `reports.report-block-s3-storage` — report block detail persistence behavior.
