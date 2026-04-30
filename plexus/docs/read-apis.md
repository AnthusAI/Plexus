# Read APIs

Reference for the read-only Plexus runtime APIs available in
`execute_tactus`. These calls are inexpensive, deterministic, and safe
to use freely.

## Scorecards

- `scorecards{ ... }` (alias for `plexus.scorecards.list`) — list all
  scorecards visible to the active account. Returns rows with `id`,
  `key`, `name`, `externalId`, `description`, `createdAt`, `updatedAt`.
- `scorecard{ id = "..." }` (alias for `plexus.scorecards.info`) — fetch
  a single scorecard with its sections and scores. Accepts `id`, `name`,
  `key`, or `external_id`.

```tactus
local cards = scorecards{}
for _, card in ipairs(cards) do
  if card.key == "selectquote_hcs_medium_risk" then
    return scorecard{ id = card.id }
  end
end
```

## Scores

- `score{ id = "..." }` (alias for `plexus.score.info`) — fetch score
  details, champion version, and version history. Accepts `id`, `name`,
  `key`, `external_id`, or `score_id` (with optional `scorecard_id`,
  `scorecard_name`, `scorecard_key` to disambiguate).
- `score_evaluations{ id = "..." }` — list recent evaluations for a
  score.

```tactus
local detail = score{ id = "score_compliance_tone" }
return {
  champion_version_id = detail.championVersionId,
  recent_evaluations = score_evaluations{ id = detail.id, limit = 5 },
}
```

## Items

- `item{ id = "..." }` (alias for `plexus.item.info`) — fetch a single
  item, including transcript and any attached score results.
- `last_item{}` (alias for `plexus.item.last`) — fetch the most recent
  item for the active account (handy when you need a known-good item ID
  for a smoke test).

```tactus
local last = last_item{}
return item{ id = last.id }
```

## Feedback

- `feedback{ ... }` (alias for `plexus.feedback.find`) — find feedback
  items where human reviewers corrected predictions (FN/FP/etc.).
  Required filters typically include `scorecard`, `score`, and one of
  `final_value` / `initial_value` / `kind`. Read
  `evaluation-and-feedback/feedback-alignment` for the full filter
  contract and baseline-first protocol.
- `feedback_alignment{ ... }` (alias for `plexus.feedback.alignment`) —
  generate the confusion matrix, accuracy, and AC1 agreement summary
  for a score over a window. Run this **first** when investigating
  score behavior; raw feedback finds are for drilldown after the
  summary.

```tactus
local summary = feedback_alignment{
  scorecard = "selectquote_hcs_medium_risk",
  score = "Compliance Tone",
  days = 30,
}
return {
  ac1 = summary.ac1,
  accuracy = summary.accuracy,
  total = summary.total,
}
```

## Evaluations (read-only forms)

- `evaluation{ id = "..." }` (alias for `plexus.evaluation.info`) —
  fetch a specific evaluation's metrics. Without an `id`, returns the
  most recent evaluation for the active account.
- `recent_evaluations{ ... }` (alias for `plexus.evaluation.find_recent`)
  — list recent evaluations with optional filters.
- `compare_evaluations{ ... }` (alias for `plexus.evaluation.compare`)
  — compare two evaluations side-by-side.

```tactus
local recents = recent_evaluations{ limit = 5 }
return evaluation{ id = recents[1].id }
```

`evaluation.run` is **not** a read API — see `long-running-apis`.

## Datasets

- `dataset_association{ ... }` (alias for
  `plexus.dataset.check_associated`) — check whether a dataset is
  associated with a given score / scorecard.
- `dataset{ ... }` (alias for `plexus.dataset.build_from_feedback_window`)
  — build a dataset payload from a feedback window. This is read-shaped
  but can be expensive on wide windows; prefer narrow windows during
  exploration.

## Procedures and reports

Procedure and report **read** forms (`procedures{}`, `procedure{}`,
`procedure_sessions{}`, `procedure_messages{}`, `report_configs{}`) are
documented in the per-theme indexes:

- `procedures/README` (`docs.get{ key = "theme-procedures" }`)
- `reports/README` (`docs.get{ key = "theme-reports" }`)

## Cost note

Read APIs do not consume `usd` or `tokens` from your budget; they each
count as exactly one `tool_calls` against the active budget. The default
ambient budget allows tens of read calls per `execute_tactus` invocation,
which is enough for nearly all discovery and triage workflows.
