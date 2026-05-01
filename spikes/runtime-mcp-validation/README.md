# Runtime MCP Validation Spike

This directory contains the gating spike for Kanbus epic `plx-f978d2`.

The goal is to measure whether frontier models can use a single
`execute_tactus`-style interface to write Plexus-flavored Tactus code against a
stubbed `plexus` module.

## Contents

- `boot_prompt.md` — compact tool-description / boot prompt used in the spike.
- `plexus_module_stub.py` — deterministic fixture-backed `plexus.*` module.
- `fixtures/plexus_stub_data.json` — scorecards, scores, items, evaluations,
  feedback, datasets, reports, procedures, and docs fixtures.
- `tasks/*.yaml` — curated representative tasks and expected outcomes.
- `harness.py` — task loader, Tactus executor, provider adapters, outcome checkers,
  and result writer.
- `report.py` — report scaffold generator for harness result directories.
- `measure_mcp_catalog.py` — measures current FastMCP tool-schema context cost
  against the proposed single-tool payload.
- `report_template.md` — final report requirements and gate reminder.
- `host_module_contract.md` — contract between Plexus and Tactus for
  `runtime.register_python_module("plexus", ...)`.
- `results/` — ignored generated output from harness runs.

## Local Smoke Test

Run the deterministic oracle, which exercises the fixture module and checkers
without calling external model APIs:

```bash
python spikes/runtime-mcp-validation/harness.py --validate-tasks
python spikes/runtime-mcp-validation/harness.py --all --model stub-oracle --run-id local-smoke
```

Expected result:

```text
tasks_valid: true
task_count: 15
boot_prompt_tokens: less than or equal to 2000
stub-oracle passed: 15 / 15
```

## Real Model Runs

Before making any paid/provider call, check local readiness without printing
secret values:

```bash
python spikes/runtime-mcp-validation/harness.py --check-providers
```

The harness accepts provider-prefixed model ids:

```bash
python spikes/runtime-mcp-validation/harness.py --task predict_single_item --model anthropic:claude-4.6-sonnet
python spikes/runtime-mcp-validation/harness.py --task predict_single_item --model openai:gpt-5.3-codex
python spikes/runtime-mcp-validation/harness.py --task predict_single_item --model litellm:gemini/gemini-3.1-pro
```

For matrix-style runs, pass a comma-separated `--models` list:

```bash
python spikes/runtime-mcp-validation/harness.py \
  --task predict_single_item \
  --models anthropic:claude-4.6-sonnet,openai:gpt-5.3-codex \
  --run-id provider-readiness-matrix-001
```

Short aliases are also supported:

- `claude-*` -> Anthropic
- `gpt-*` -> OpenAI
- `gemini-*` -> LiteLLM with `gemini/<model>`

Required environment variables depend on provider:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- Provider-specific LiteLLM variables for Gemini or other backends, commonly
  `GOOGLE_API_KEY`, `GEMINI_API_KEY`, `VERTEXAI_PROJECT`, or cloud-provider
  credentials.

Start with one low-cost readiness call before any matrix run:

```bash
python spikes/runtime-mcp-validation/harness.py \
  --task predict_single_item \
  --model litellm:<configured-low-cost-model> \
  --run-id provider-readiness-001
```

Only run the full 15-task x 4-model matrix after a single-task provider run has
produced a result JSON and summary CSV in `results/`, and after confirming the
expected spike cost cap is still acceptable.

The harness enforces this by refusing `--all` with real providers unless
`--allow-full-matrix` is explicitly passed:

```bash
python spikes/runtime-mcp-validation/harness.py \
  --all \
  --models anthropic:claude-4.6-sonnet,openai:gpt-5.3-codex,litellm:<configured-model> \
  --allow-full-matrix \
  --readiness-run-id provider-readiness-matrix-001 \
  --run-id matrix-001
```

Do not use `--allow-full-matrix` until the one-task readiness run succeeds.
The harness enforces this by requiring `--readiness-run-id` for full
real-provider matrix runs. The referenced run must contain at least one
successful real-provider task result.

The harness also applies a pre-dispatch cost-plan check. By default it estimates
each real provider task/model call at `$0.20` and refuses any run whose planned
real-provider calls exceed the `$50` spike cap. Override only with an explicit
reason:

```bash
python spikes/runtime-mcp-validation/harness.py \
  --all \
  --models anthropic:claude-4.6-sonnet,openai:gpt-5.3-codex \
  --allow-full-matrix \
  --readiness-run-id provider-readiness-matrix-001 \
  --max-total-cost-usd 50 \
  --estimated-real-call-cost-usd 0.20 \
  --run-id matrix-001
```

## Report Drafts

After any harness run, generate a report scaffold from its result directory:

```bash
python spikes/runtime-mcp-validation/measure_mcp_catalog.py --run-id <run-id>
python spikes/runtime-mcp-validation/report.py --run-id <run-id>
```

The report is written to `results/<run-id>/report.md`, which is ignored with the
rest of generated results. Stub-oracle reports are useful for validating the
report generator, but they deliberately remain `PENDING` because the proceed
gate requires real frontier-model results from `plx-724038`.

Each harness run also writes `results/<run-id>/run_metadata.json` with the
selected tasks, selected models, boot-prompt token count, and cost-plan settings.

## How It Works

For real model runs, the harness:

1. Sends `boot_prompt.md` plus the task prompt to the selected model.
2. Asks for Tactus code only.
3. Extracts fenced or raw Tactus code.
4. Executes it with Lupa and a host-provided `require("plexus")` shim.
5. Converts Tactus table values back to Python values.
6. Checks the final value, API calls, stream events, forbidden APIs, cost, and
   structured errors against the task definition.

This is a spike harness, not the production `execute_tactus` implementation.
The `require("plexus")` shim is a temporary stand-in for the Tactus host-module
mechanism tracked in epic `plx-cb988c`.

The production integration contract is documented in `host_module_contract.md`.
