# Long-running APIs

Reference for the Plexus runtime APIs that can take more than a few
seconds and therefore require the handle protocol.

The long-running APIs are:

- `plexus.evaluation.run`
- `plexus.report.run`
- `plexus.procedure.run`

All three behave identically with respect to the protocol described
here. See `handles-and-budgets` for the handle lifecycle.

## Two modes

Each long-running API has two valid call shapes.

### 1. Bounded synchronous run

```tactus
evaluate{
  score_id = "score_compliance_tone",
  item_count = 200,
}
```

The runtime executes the operation, streams progress events to the MCP
client, and returns the operation's final value as the tool result.
Bounded runs are appropriate when you can confidently bound the cost in
seconds (single-digit minutes) and the user is waiting on the result.

The runtime enforces the active ambient budget. If a synchronous run
would exceed the remaining `wallclock_seconds`, `usd`, or `tool_calls`
allotment, dispatch fails before any work begins.

### 2. Async dispatch with explicit child budget

```tactus
local handle = evaluate{
  score_id = "score_compliance_tone",
  item_count = 1000,
  async = true,
  budget = {
    usd = 0.50,
    wallclock_seconds = 1800,
    depth = 1,
    tool_calls = 10,
  },
}
```

`async = true` returns a **handle** instead of a result. The handle is
persisted, scoped to the parent trace, and can be polled, awaited, or
cancelled in subsequent `execute_tactus` calls.

## The async budget contract

Async dispatch **requires** an explicit child `budget` table with all
four keys:

| Key | Type | Meaning |
|-----|------|---------|
| `usd` | number | Maximum USD the child run may spend. |
| `wallclock_seconds` | number | Maximum wallclock seconds for the child. |
| `depth` | int | Maximum recursive procedure depth allowed. |
| `tool_calls` | int | Maximum tool calls the child may make. |

Omitting the `budget` table or any required key returns a structured
error (`error.code = "child_budget_required"`) and dispatches nothing.

The runtime carves the requested allocation from the parent budget
before dispatch:

- If the parent does not have enough budget for the requested child
  allocation, dispatch fails with `error.code = "budget_exceeded"`
  and nothing is consumed.
- If the carve succeeds, the child amount is reserved (subtracted from
  the parent's remaining budget) and propagated to the worker process.
- The handle's `child_budget` field exposes the actual carved amount.

Workers enforce the propagated budget at their execution boundary:

- Evaluation CLI workers load `PLEXUS_CHILD_BUDGET`, enforce wallclock,
  and reject scorecard cost totals that exceed the child USD.
- Durable programmatic report-block workers enforce wallclock from the
  `child_budget` payload before running the block.
- Procedure workers enforce wallclock, apply `depth` as Tactus
  `max_depth`, and reject LLM cost events that exceed the child USD.

## Blocking long-running calls (without `async`)

A long-running API called without `async = true` is **not** silently
allowed. The runtime:

1. Records the attempt on `api_calls` so the trace shows the intent.
2. Sets the response `error.code = "requires_handle_protocol"`.
3. Returns immediately without dispatching.

There is no fallback. Either call with `async = true` and an explicit
child budget, or accept the bounded synchronous form (which is itself a
direct execution path with cost ceilings already enforced — see the
specific API for which forms are bounded-sync versus async-only).

## Cost recording

Async dispatch records exactly one `plexus.<namespace>.run` call in the
response cost envelope and trace, even when the dispatch is rejected
(missing budget, budget exceeded, etc.). This makes failed dispatch
attempts visible in `api_calls`.

## See also

- `handles-and-budgets` — handle lifecycle (`peek`, `status`, `await`,
  `cancel`) and how the runtime carves and propagates child budgets.
- `procedures/README` — procedure-specific run patterns.
- `reports/README` — report-specific run patterns.
- `evaluation-and-feedback/feedback-alignment` — protocol for using
  evaluations to validate score changes.
