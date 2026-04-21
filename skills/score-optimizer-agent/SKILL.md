---
name: score-optimizer-agent
description: Run and debug the Plexus feedback-alignment optimizer from the direct CLI. Use this when starting a new optimizer procedure, resuming diagnosis after a failed run, or explaining what the optimizer is doing internally.
---

# Score Optimizer Agent

Use this skill when the task is to run, monitor, or debug the feedback-alignment optimizer for a Plexus score.

## Core Rule

During development and debugging, run the optimizer with the direct CLI:

```bash
plexus procedure optimize ...
```

Do not treat dispatcher state or dashboard status alone as proof that the optimizer is healthy. The direct CLI stdout/stderr log is the source of truth.

## What The Optimizer Actually Does

The convenience command `plexus procedure optimize` wraps `plexus/procedures/feedback_alignment_optimizer.yaml`.

A normal run does this:

1. Creates a new `Procedure` record.
2. Creates or reuses a `Task` plus dashboard stages.
3. Starts a Tactus runtime and a procedure chat session.
4. Pulls the starting score version locally.
5. Refreshes the contradictions report in the background.
6. Looks for reusable baselines.
7. If baselines are not reused, runs two fresh baseline evaluations in parallel:
   - regression baseline: `accuracy` evaluation on the associated deterministic dataset
   - recent baseline: `feedback` evaluation on the recent human-reviewed items
8. If baselines succeed, the optimizer proposes hypotheses, edits the score, submits candidate versions, evaluates them, compares deltas, and repeats up to `max_iterations`.

Default optimization objective is **alignment** (Gwet AC1 on recent feedback, with regression alignment also tracked).

## Identifier Resolution

`--scorecard/-s` and `--score/-c` use the shared DRY resolvers.

You can pass any of these if they uniquely resolve:
- DynamoDB ID
- external ID
- name
- key

Do not waste time resolving IDs manually unless there is an ambiguity or you need the exact resolved UUID for debugging.

## Preferred Run Command

From the repo root:

```bash
ts=$(date +%Y%m%d-%H%M%S)
log=/tmp/optimizer-$ts.log
plexus procedure optimize \
  -s "<scorecard>" \
  -c "<score>" \
  --days 90 \
  --max-samples 200 \
  --max-iterations 3 \
  2>&1 | tee "$log"
```

This gives you:
- direct CLI evidence
- a durable log file for traceback/error inspection
- early visibility into the created `Procedure` and `Task` IDs

## Useful CLI Flags

Required:
- `-s, --scorecard`
- `-c, --score`

Common:
- `-d, --days` — recent feedback lookback window
- `--max-samples` — per-evaluation feedback sample cap
- `--max-iterations` — optimizer cycle cap
- `--improvement-threshold` — minimum AC1 gain needed to keep iterating
- `-v, --version` — start from a specific score version instead of champion
- `--hint` — inject expert guidance into the optimizer context
- `--resume-regression-eval` — reuse a prior accuracy baseline
- `--resume-recent-eval` — reuse a prior feedback baseline
- `--dry-run` — analyze only, do not submit new score versions
- `-o, --output` — `table`, `json`, or `yaml`

## Objectives

Today, the simple `plexus procedure optimize` CLI is centered on the default **alignment** workflow.

The underlying procedure YAML supports these objective families:
- `alignment` (default)
- `precision_safe`
- `precision`
- `recall_safe`
- `recall`

Important:
- The convenience `optimize` CLI does **not** currently expose an `--optimization-objective` flag.
- If you need a non-default objective, use the procedure/YAML path instead of assuming the simple CLI can switch objectives.
- There is optimizer documentation for `cost_efficiency`, but do not assume that objective is wired through the current convenience command or current procedure scoring logic without checking the YAML first.

## How To Read A Live Run

Things you should expect to see early in the log:
- `Starting feedback alignment optimization...`
- `Created Task ... for procedure ...`
- `Running optimization procedure...`
- `Starting procedure run for procedure ID: ...`
- `Chat session created: ...`
- `Running 2 fresh baseline evaluation(s) ...`

If you do not see the baseline evaluations dispatch, the optimizer has not really started doing the important work yet.

## Failure Policy

Missing metadata is a real execution failure.

The system should fail fast when score execution returns `ERROR`. It should not silently normalize missing metadata into a model-visible blank and it should not reinterpret client-specific classes like `NA` in Plexus core.

For optimizer debugging, that means:
- if a baseline evaluation fails, stop and inspect the direct CLI log first
- look for the first concrete exception, not the final dashboard status
- use the item/content/feedback identifiers in the error to inspect the bad record or bad score code

## Practical Notes Learned From Live Runs

- The command may log `No Plexus configuration files found - using environment variables only`. That is normal in this environment.
- The optimizer currently dispatches the contradictions report in the background near cycle 0. That is not the baseline itself.
- A warning about the default procedure template query returning a null `Procedure.name` has been non-fatal in practice; procedure creation can still continue.
- There is still a stage-name mismatch in some runs (`baseline` vs dashboard stage names like `Evaluation`). Treat that as dashboard visibility noise unless the CLI log shows a real exception.
- A score can still explicitly instruct the model to output `NA` when metadata fields are blank. That is score-specific prompt behavior, not optimizer-core behavior. If that is wrong for the score, inspect the pulled score YAML and guidelines, not just the procedure runtime.
- If you need to prove health, prefer the live CLI process and its log over dashboard polling.

## When To Use MCP Instead

Use MCP tools for inspection and analysis around the optimizer, not as the primary execution path during debugging. Examples:
- inspect score metadata
- inspect evaluation results after dispatch
- inspect procedure chat or reports

But for actually running the optimizer in development:
- use `plexus procedure optimize`
- capture stdout/stderr
- keep the log file path

## Minimal Operator Summary

If you only remember five things, remember these:

1. Run the optimizer with `plexus procedure optimize`, not via indirect evidence.
2. Capture a log with `tee` every time.
3. `scorecard` and `score` accept ID, external ID, name, or key.
4. Default objective is alignment; non-default objectives require the procedure/YAML path.
5. Missing metadata is an error to investigate, not a score outcome to smooth over.
