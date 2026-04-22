---
name: plexus-score-optimizer
description: Start a feedback alignment optimization run for a Plexus score. Creates and launches a Feedback Alignment Optimizer procedure that iterates automatically over N cycles.
---

# Plexus Score Optimizer

Use this skill when a user wants to run, resume, or steer an automated optimization procedure for a Plexus score.

## Optimization Mindset

The optimizer is not just a code-tuning loop. Its job is to move a measurable needle such as alignment, AC1, accuracy, precision, recall, or cost efficiency.

That means the work usually falls into three lanes:

1. Improve the score logic or prompt under the current rubric.
2. Identify rubric gaps, policy ambiguities, or clarification questions for stakeholders and SMEs.
3. Identify feedback items that appear inconsistent with the rubric expressed in the current guidelines or newer SME decisions.

This is how the optimizer "moves the goal posts" in a disciplined way:

- The iterative metacognitive loop tries to improve a quantifiable metric.
- Contradiction analysis shows where the current feedback set may not match the current rubric.
- SME questions help refine the rubric when the current guidelines are underspecified or outdated.
- Approved feedback invalidation removes labels that were created under a different rubric or were simply applied incorrectly.

Do not treat every contradiction as a score bug. Some contradictions mean:

- the score needs to change
- the rubric needs clarification
- the feedback should be invalidated
- the item is mechanical noise and should not drive optimization

## Guardrails

- Never invalidate feedback automatically.
- Never invalidate feedback just because a contradiction report flagged an item.
- Always discuss candidate invalidation groups with the user first.
- Only invalidate items after the user explicitly approves the exact group.
- Use the contradiction report output as the source of truth for triage.
- Drill into individual items only after the report identifies a specific contradiction theme or candidate set.

## Input

Required:
- `scorecard` — scorecard name, key, or ID
- `score` — score name, key, or ID

Optional:
- `days` — feedback window in days (default: 90)
- `max_cycles` — number of optimization cycles (default: 10)
- `max_samples` — feedback samples per eval (skill default: 200; pass it explicitly)
- `start_version` — score version ID to start from instead of the champion
- `resume_recent_eval` — recent feedback baseline eval ID to reuse
- `resume_regression_eval` — regression baseline eval ID to reuse
- `hint` — free-text expert hint to include in the agent's context

## Recommended Workflow

### Step 1 - Resolve the score context

Use the CLI, not MCP-style tool names:

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli score info \
  --scorecard "<scorecard>" \
  --score "<score>"
```

### Step 2 - Run or refresh the contradictions report

If a current contradictions report does not already exist for the score and time window, run one.

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli feedback report contradictions \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --days <days> \
  --fresh \
  --format json
```

Useful options:

- `--mode contradictions` is the default and is the normal triage mode.
- `--background` queues the report for dispatcher execution.
- If you use `--background`, process it with:

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli command dispatcher --once
```

Use the contradictions report to sort findings into these buckets:

- score logic change
- rubric clarification / SME question
- feedback invalidation candidate
- mechanical / no action

### Step 3 - Handle contradiction findings at the right level

Use the report output first. Do not start by spelunking individual feedback items.

When the report reveals a contradiction cluster:

- summarize the shared pattern
- explain whether it looks like a score issue, rubric issue, or feedback-quality issue
- propose a candidate invalidation group only when the contradiction clearly reflects old or incorrect rubric application

Examples of strong invalidation candidates:

- feedback created before a newer objective rule replaced an older vague standard such as "most"
- feedback that clearly enforced "all medications" after the rubric changed to "two or more misses"
- feedback that contradicts explicit newer SME guidance already reflected in the guidelines

Examples that are usually not invalidation-first:

- unresolved rubric ambiguity
- customer-uncertainty edge cases that SMEs have not answered yet
- truncated or mechanically corrupted transcripts

### Step 4 - Invalidate feedback only after explicit user approval

Once the user approves an exact group, invalidate the items one at a time with the CLI:

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli feedback invalidate "<identifier>" \
  --scorecard "<scorecard>" \
  --score "<score>"
```

Notes:

- This command is for operator-approved targeted invalidation only.
- It must not be used automatically by the optimizer.
- It accepts a direct feedback item ID or an item identifier and resolves deterministically.
- Use `--scorecard` and `--score` to disambiguate item-level matches when needed.

### Step 5 - Launch the optimizer

Prefer the direct optimizer CLI for normal runs:

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli procedure optimize \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --days <days> \
  --max-samples <max_samples> \
  --max-iterations <max_cycles> \
  --version "<start_version>" \
  --resume-recent-eval "<resume_recent_eval>" \
  --resume-regression-eval "<resume_regression_eval>" \
  --hint "<hint>"
```

Only include the optional flags that were actually provided.
If the user does not specify `max_samples`, this skill should still pass `--max-samples 200`.

### Step 6 - Advanced manual procedure path

Keep this path for cases where you want to inspect or patch optimizer YAML directly.

List recent procedures:

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli procedure list \
  --account "call-criteria" \
  --scorecard "<scorecard>"
```

Pull the latest YAML from a recent optimizer procedure:

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli procedure pull <procedure_id> \
  --output /tmp/optimizer_patched.yaml
```

Patch the YAML locally. Set `value:` fields on the relevant params:

```yaml
scorecard:
  type: string
  value: "<scorecard name>"

score:
  type: string
  value: "<score name>"

max_iterations:
  type: number
  value: <max_cycles>

max_samples:
  type: number
  value: <max_samples>

days:
  type: number
  value: <days>

start_version:         # only if provided
  type: string
  value: "<version_id>"

resume_recent_eval:    # only if provided
  type: string
  value: "<eval_id>"

resume_regression_eval:# only if provided
  type: string
  value: "<eval_id>"

hint:                  # only if provided
  type: string
  value: "<hint text>"
```

Create the procedure from YAML:

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli procedure create \
  --account "call-criteria" \
  --scorecard "<scorecard name>" \
  --score "<score name>" \
  --yaml /tmp/optimizer_patched.yaml \
  --output json
```

Then run it:

```bash
/Users/ryan/miniconda3/bin/python -m plexus.cli procedure run <procedure_id>
```

### Step 7 - Report back

Report:

- the procedure ID
- the starting score version
- the key optimizer parameters
- whether contradictions / invalidation triage influenced the baseline definition
- the dashboard URL:
  `http://localhost:3000/lab/procedures/<procedure_id>`
