# Runtime MCP Validation Report Template

This is the human-facing template for Kanbus task `plx-8e009e`.

The final go/no-go report must be generated from real frontier-model harness
results. Stub-oracle results may validate the harness and report generator, but
they do not satisfy the initiative proceed gate.

## Required Inputs

- A completed harness run directory under `results/<run-id>/`.
- `summary.csv` from the harness.
- Per-task JSON transcripts under `results/<run-id>/<model-id>/`.
- At least four real frontier-model result sets, unless the stakeholder
  explicitly changes the gate.

## Proceed Gate

Proceed only if at least two real frontier models achieve at least 85% first-try
success across the curated task set.

## Sections

1. Executive summary
2. Quantitative results
3. Failure-mode classification
4. Streaming UX assessment
5. Context / token overhead
6. Decision

## Generator

Use:

```bash
python spikes/runtime-mcp-validation/report.py --run-id <run-id>
```

The generated `results/<run-id>/report.md` is ignored by git because result files
are generated artifacts. Copy final findings into the Kanbus task and attach or
publish the report according to the team's review workflow.
