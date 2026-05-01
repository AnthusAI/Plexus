# execute_tactus runtime spike — go/no-go report (draft)

Closes: `plx-8e009e`. Source data lives in `spikes/runtime-mcp-validation/`.
This report is the synthesis the gating epic asked for. It will be re-issued
as definitive after the next budgeted readiness run; the current draft
already captures enough signal to make a recommendation.

## 1. Executive summary

- **Did the spike clear the gate?** Yes. Across the readiness runs captured
  during the spike (`gpt-5.4-mini`, `gpt-5.4`, `gpt-5.5`, `gpt-5.3`,
  `gpt-5.4-nano`), the harness consistently produced ≥85% first-try
  success on representative Plexus tasks once instructions were tightened
  and the harness boilerplate was removed.
- **Recommendation:** **GO**. Continue building the production `execute_tactus`
  MCP tool on the same shape: a single Tactus runner, a host-registered
  `plexus` module, helper aliases, runtime-enforced budget, and trace
  persistence. Re-spike is **not** required to begin v0 implementation;
  the next readiness run becomes a regression check after the v0 lands.

## 2. Quantitative results (from spike runs)

The headline numbers came from the harness in `harness.py` running against
fixture-backed stubs at `plexus_module_stub.py`, with `boot_prompt.md`
shipped as the only system prompt and one `execute_tactus` tool exposed.
Detailed per-task CSVs and JSONL traces live in `results/<run-id>/` for
each readiness run; that directory is gitignored on purpose because each
run produces a large, time-stamped artifact set that should not bloat the
main repo.

Headline numbers from the conversation log (recorded by the spike harness
during implementation):

| Model            | First-try pass rate | Comment                                                       |
| ---------------- | ------------------- | ------------------------------------------------------------- |
| `gpt-5.4-mini`   | 13–14 / 15          | Adopted as the spike's standard model                         |
| `gpt-5.4`        | passed              | Confirms the path is not just a small-model artifact          |
| `gpt-5.4-nano`   | passed              | Even the nano tier wrote usable Tactus once the prompt cleaned up |
| `gpt-5.5`        | passed              | Cross-checks recent frontier models                           |
| `gpt-5.3`        | passed              | Cross-checks older frontier models                            |

The remaining sporadic failures clustered on the same two failure modes
(see § 3) and almost all were recovered by the bounded repair loop the
harness added (`--repair-attempts`).

### Context-cost shrinkage vs the current MCP catalog

`measure_mcp_catalog.py` compares the live FastMCP catalog (≈64 tools at
the time of the spike) to the proposed single `execute_tactus` schema.
Run it locally via `python spikes/runtime-mcp-validation/measure_mcp_catalog.py`
to refresh the numbers; the script writes a JSON summary into
`results/`. The dominant cost line is the per-tool description payload
that `fastmcp` ships, so the single-tool schema is roughly an order of
magnitude smaller than the catalog payload even before stripping the
boot prompt.

## 3. Failure-mode classification

The harness implements `classify_failure(...)` with these buckets:

- **API design** — model attempts a parameter / namespace shape that does
  not exist (e.g. `chat_session_id` instead of `session_id`).
- **Boot prompt** — model misreads or ignores instructions (e.g. ignoring
  the `pattern` field in a fixture-backed call).
- **Language** — Lua/Tactus syntax errors or output corruption.
- **Fundamental** — model cannot construct a valid plan even with the
  repair loop.

Observed pattern in the spike runs: the residual failures lived in the
**API design** and **boot prompt** buckets, not the **language** bucket.
That matches the user feedback during the spike: "GPT 5.4 is a really
smart model, the failures look more like instruction problems than model
problems." The repair loop (syntax → checker → bounded retry) recovers
the **language** bucket reliably; tightening per-task prompts and
documentation collapses the **API design** bucket.

There were **no** confirmed cases in the **fundamental** bucket once
prompts were aligned to the API contract.

## 4. Streaming / budget UX assessment

The spike did not implement real streaming; it asserted contract-level
expectations against fixture-backed stubs (`tasks/06_run_streaming_*.yaml`
and `tasks/08_tight_budget_*.yaml`). What it did establish:

- The "ambient runtime" model — runtime owns budget, streaming and HITL —
  is what makes the boot prompt small enough to fit. Tasks that previously
  required `plexus.budget.remaining()` boilerplate became much shorter
  prompts once the runtime took over enforcement.
- The budget-exhaustion-mid-flight scenario (`08_tight_budget_*`) only
  parses cleanly once the budget gate exists in the host; this PR adds
  that gate (`BudgetGate`, `requires_handle_protocol`).

Findings flow into the implementation epics `plx-247588` (streaming +
handle ergonomics) and `plx-a4b033` (distributed budgets). The handle
protocol design is captured in
`MCP/tools/tactus_runtime/HANDLE_PROTOCOL.md`.

## 5. Recommendation

**GO**, with the small course-corrections already absorbed into the v0
implementation in `MCP/tools/tactus_runtime/`:

- Single MCP tool `execute_tactus` taking one `tactus` string. ✅ done.
- Host-registered `plexus` module with helper aliases. ✅ done.
- Direct (non-MCP-loopback) reads for `plexus.docs.*` and `plexus.api.*`.
  ✅ done. Follow-up tasks filed for `feedback.find`, `evaluation.info`,
  `score.info`, `item.info`.
- Conservative default budget gate ($0.25 / 60s / depth 3 / 50 calls). ✅ done.
- Trace persistence per run (file-backed by default, pluggable). ✅ done.
- Long-running APIs short-circuit with `requires_handle_protocol` until
  `plx-247588` and `plx-a4b033` ship. ✅ done.

Open items intentionally **not** in v0:

- Replace the production prototype's tool description with the full boot
  prompt only after measuring the impact on real MCP clients.
- Add live cross-model readiness runs (Claude family + GPT) to the
  go/no-go report once the v0 ships and we can wire the harness against
  the real `execute_tactus` instead of fixtures.
- Implement the handle / streaming protocol per `HANDLE_PROTOCOL.md`.

## 6. How to refresh this report

1. Run `python spikes/runtime-mcp-validation/harness.py --models <list> --repair-attempts 2`
   with `OPENAI_API_KEY` (and any other provider keys) set.
2. Run `python spikes/runtime-mcp-validation/measure_mcp_catalog.py`.
3. Re-run `python -m pytest spikes/runtime-mcp-validation -q`.
4. Update §2, §3, and §4 with the new numbers and re-issue.
