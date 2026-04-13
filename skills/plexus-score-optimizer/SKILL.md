---
name: plexus-score-optimizer
description: Start a feedback alignment optimization run for a Plexus score. Creates and launches a Feedback Alignment Optimizer procedure that iterates automatically over N cycles.
---

# Plexus Score Optimizer

Use this skill when a user wants to run an automated optimization procedure for a Plexus score.

## Input

Required:
- `scorecard` — scorecard name, key, or ID
- `score` — score name, key, or ID

Optional:
- `max_cycles` — number of optimization cycles (default: 10)
- `max_samples` — feedback samples per eval (default: 200)
- `start_version` — score version ID to start from instead of the champion
- `resume_feedback_eval` — feedback baseline eval ID to reuse
- `resume_accuracy_eval` — accuracy baseline eval ID to reuse
- `hint` — free-text expert hint to include in the agent's context

## How to Run

### Step 1 — Resolve scorecard and score IDs

Use `plexus_score_info` to resolve the score. Get the scorecard ID and score ID.

### Step 2 — Patch the optimizer YAML

Read the existing optimizer YAML from a recent procedure run for the same account (use `plexus_procedure_list` then `plexus_procedure_yaml`). Set `value:` fields on the relevant params:

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

start_version:         # only if provided
  type: string
  value: "<version_id>"

resume_feedback_eval:  # only if provided
  type: string
  value: "<eval_id>"

resume_accuracy_eval:  # only if provided
  type: string
  value: "<eval_id>"

hint:                  # only if provided
  type: string
  value: "<hint text>"
```

Save the patched YAML to a temp file.

### Step 3 — Create and run the procedure

```bash
/Users/ryan/miniconda3/bin/python -m plexus procedure create \
  --scorecard "<scorecard name>" \
  --score "<score name>" \
  --account "call-criteria" \
  --yaml /tmp/optimizer_patched.yaml
```

The procedure ID is printed in the output (`Creating Task for procedure <ID>`). The CLI may crash on display after creation — that's okay, the procedure is created.

```bash
/Users/ryan/miniconda3/bin/python -m plexus procedure run \
  --id <procedure_id> \
  --account "call-criteria"
```

Run this in the background.

### Step 4 — Report back

Tell the user the procedure ID and the dashboard URL:
`http://localhost:3000/lab/procedures/<procedure_id>`
