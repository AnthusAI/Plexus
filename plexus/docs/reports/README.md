# Reports

Topic index for Plexus Reports — generated artifacts assembled from one or
more report blocks, persisted as durable records with attachments.

## When to use Reports

Reports are the right tool when you need:

- A persistent, attributable artifact summarizing analytical work
  (cost analysis, evaluation comparisons, alignment summaries).
- A versioned record that can be linked, shared, and re-generated from a
  report configuration.
- Block-based composition: each report is a sequence of typed report
  blocks whose outputs are stored as S3 attachments and surfaced through
  the dashboard.

## Plexus runtime APIs (`execute_tactus`)

- `report.configurations_list{}` — list report configurations for the
  active account. Helper alias: `report_configs{}`.
- `report.run{ configuration_id = "...", async = true, budget = {...} }`
  — long-running. Must use `async = true` with an explicit
  `budget = { usd, wallclock_seconds, depth, tool_calls }`. Returns a
  handle whose status refreshes from the underlying durable task.
  Helper alias: `report{ ... }` (also `report_run{ ... }`).

The blocking form of `report.run` returns a structured
`requires_handle_protocol` error rather than tying up the runtime.

## Reading patterns

```tactus
local configs = report_configs{}
return {
  count = #configs,
  first_id = configs[1] and configs[1].id or nil,
}
```

## Long-running pattern

See `long-running-apis` and `handles-and-budgets` at the top of
`plexus/docs/` for the handle / budget contract used by `report.run`.

## Persistence policy

ReportBlock output is always stored as S3 file attachments. The
`ReportBlock.output` DynamoDB field is metadata-only (a compact envelope
plus an attachment pointer). Treat handle results as references; fetch
the underlying attachments when you need full payload content.

## Follow-up content

This index is a placeholder. Deeper report-block authoring guidance
(block types, configuration YAML, attachment patterns) is tracked as a
follow-up to the `execute_tactus` themed-docs work.
