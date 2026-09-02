---
id: reports.optimization-survey-handoff
title: Optimization Survey Agent Handoff
summary: "Follow up an optimization survey from a compact Report handoff and verified attachments without loading exhaustive Report state."
namespace: reports
status: canonical
disclosure: cookbook
audience: agent
tags: [reports, optimization, handoff, artifacts, champion]
related:
  - reports._index
  - reports.reports-catalog
  - evaluation-feedback.optimizer-procedures
  - score-authoring.rubric-consistency
---
# Optimization Survey Agent Handoff

Use this workflow when you have an optimization-survey Report ID and need to
investigate or complete its follow-up work. The Report is an immutable finding,
not a task tracker and not proof that its frozen state is still current.

Do not begin by reading Report parameters, ReportBlock output, raw feedback, or
the stakeholder presentation. The supported handoff keeps the initial response
small and points to the exact attachment needed for each finding.

## 1. Read the Compact Handoff

```tactus
local report = plexus.report.info{ id = "<report-id>" }
return report
```

Inspect:

- `decision_summary`: the current compact reader's interpretation of the
  immutable overview. Prefer this when an older published handoff uses generic
  wording such as “evidence incomplete.” It distinguishes a configured
  diagnosis count limit, budget exhaustion, incomplete diagnosis evidence,
  and an actual run failure without rewriting the Report.
- `agent_handoff.provisional`: `true` means the run had not finalized when this
  revision was published.
- `agent_handoff.conclusion`, `coverage`, `limitations`, and `next_checkpoint`.
- `workstream_counts` in priority order.
- `priority_representatives` for the first findings worth opening.
- `followup_page_logical_ids` for the complete, paged recommendation set.

Historical Reports without a handoff return `agent_handoff = null`. Do not fall
back to inlining their full parameters. A `decision_summary` may still explain
their safe compact overview; use the dashboard or a newer survey for details.

A configured diagnosis limit means only that the run examined a bounded subset.
Candidates beyond the limit were not judged safe, unsafe, useful, or useless.
Do not treat that condition as a model failure or as a negative decision about
the deferred candidates.

## 2. Open Only the Relevant Attachment

List attachment metadata when you need discovery or pagination:

```tactus
return plexus.report.artifacts{
  report_id = "<report-id>",
  revision = <revision-number>,
  kind = "scorecard_followups",
  limit = 25,
  cursor = "<optional-next-cursor>",
}
```

Then read an exact logical ID from the handoff or artifact list:

```tactus
return plexus.report.artifact{
  report_id = "<report-id>",
  revision = <revision-number>,
  logical_id = "scorecard_followups:<revision>:0001",
}
```

JSON, Markdown, and CSV may be inlined only when small and checksum-verified.
Large or binary artifacts return metadata and a dashboard link. Never treat a
partial download or an object key outside the Report manifest as evidence.

## 3. Verify Live Resources

Choose one follow-up item. Use its exact `resource_refs`; do not resolve a score
from its display name.

```tactus
local live_score = plexus.score.info{
  id = "<resource_refs.score_id>",
  scorecard_id = "<resource_refs.scorecard_id>",
}

local evaluations = {}
for index, evaluation_id in ipairs(<resource_refs.evaluation_ids-or-empty-table>) do
  evaluations[index] = plexus.evaluation.info{ id = evaluation_id }
end

local child = nil
if <resource_refs.procedure_id-or-nil> then
  child = plexus.procedure.info{ id = "<resource_refs.procedure_id>" }
end

return { score = live_score, evaluations = evaluations, procedure = child }
```

Before proposing any mutation, compare the live state with every applicable
`frozen_preconditions` field:

- champion version;
- feedback watermark;
- configuration digest;
- guideline digest;
- evidence fingerprint and referenced terminal evaluations.

If a precondition changed or cannot be verified, stop and refresh the evidence.
An old recommendation remains an audit finding; it is not permission to act.

## 4. Follow the Recommendation with Existing Tools

Use the item's `suggested_calls` as a starting point, then follow the normal
score-authoring and evaluation workflow.

- `complete_promotion_evidence`: run or inspect the missing matched evaluation
  evidence. This is not promotion-ready.
- `review_promotion`: verify all terminal evaluations and policy constraints,
  then request human approval for the guarded promotion below.
- `investigate_optimizer_failure`: inspect the exact Procedure, Task, score
  brief, and evaluation references before deciding whether a retry is safe.
- contradiction or guideline/structure repair: open the referenced score brief,
  verify the live code and guidelines, and use the normal score update plus
  evaluation workflow. Never edit automatically from the finding alone.
- collection or monitoring work: verify the current feedback watermark and
  collection policy before recommending a change.

For a genuinely promotion-ready item, use the exact guarded arguments emitted
in `suggested_calls.mutation`:

```tactus
return plexus.score.set_champion{
  score_id = "<resource_refs.score_id>",
  version_id = "<resource_refs.candidate_version_id>",
  expected_champion_version_id = "<frozen champion version id>",
}
```

This mutation still requires the normal human approval. The champion
precondition is also checked atomically; a concurrent champion change fails
closed. Never use `no_confirm = true` unless the human explicitly approved the
exact promotion in the current interaction.

## Safety Boundary

The handoff never authorizes automatic score, guideline, feedback-collection,
or champion changes. Raw feedback, prompts, transcripts, and exhaustive
evidence remain in restricted immutable artifacts and are not returned by the
compact Report APIs.
