# execute_tactus long-running handle protocol

This file documents the contract for long-running Plexus runtime APIs called
from `execute_tactus`. The full design lives in Kanbus epic `plx-247588`
(streaming + handle ergonomics for long-running operations) and depends on
the budget plumbing from `plx-a4b033`.

The current `execute_tactus` build implements handle-based async paths for
`plexus.evaluation.run{ async = true }`, `plexus.report.run{ async = true }`,
and `plexus.procedure.run{ async = true }`. Blocking long-running calls still
short-circuit with a structured error so an MCP client cannot accidentally tie
up the synchronous Tactus runtime for tens of minutes or hours.

## Long-running APIs

The following APIs are long-running:

- `plexus.evaluation.run` — direct handler; `async = true` dispatches a
  background CLI evaluation and creates an evaluation handle.
- `plexus.report.run` — direct handler; `async = true` dispatches a durable
  background report-block task and creates a report handle.
- `plexus.procedure.run` — direct handler; `async = true` dispatches through
  `ProcedureService.run_procedure(..., async_mode=True)` and creates a
  procedure handle.

`LONG_RUNNING_METHODS` is now empty. When a direct long-running handler is
called without `async = true`, it:

1. Records the attempt on `api_calls` so the trace shows the intent.
2. Sets `handle_protocol_required = (namespace, method)`.
3. Raises `RequiresHandleProtocol`, which surfaces in the response envelope
   as `error.code = "requires_handle_protocol"`.

No MCP-loopback call is made and no remote dispatch is started for blocking
forms.

For `async = true`, `PlexusRuntimeModule`:

1. Checks the active budget before dispatch.
2. Requires an explicit child `budget = { usd, wallclock_seconds, depth, tool_calls }`.
3. Carves that child budget from the parent budget before dispatch.
4. Dispatches the operation in non-blocking mode.
5. Creates a persisted handle record through `TactusHandleStore`.
6. Returns the public handle table to Tactus.
7. Records exactly one `plexus.<namespace>.run` API call in the response and
   trace cost envelope.

## Protocol

Two complementary mechanisms (per `plx-247588`):

### 1. Streaming during a blocking call

For runs that complete in a "feel-tolerable" timeframe (single-digit
minutes), `execute_tactus` blocks while progress events stream up to the
MCP client through FastMCP `Context` progress and info messages. Tactus
runtime log events flow through the same stream handler shape used by
`_PlexusTraceLogBridge`, and Plexus runtime API calls emit progress messages
as they are invoked.

Response envelope additions:

- Streaming notifications carry `{ kind, message, payload, cost }` shaped
  events.
- Final envelope is the same `ok`/`value`/`error`/`cost`/`api_calls` shape
  used today.

### 2. Handle-based async for very long operations

For runs measured in tens of minutes or hours, `async = true` opts into
the handle model:

```tactus
local handle = plexus.evaluation.run{
  scorecard_name = "Compliance",
  item_count = 5000,
  async = true,
  budget = {
    usd = 1.00,
    wallclock_seconds = 1800,
    depth = 1,
    tool_calls = 10,
  },
}
return { evaluation_handle = handle }
```

The public handle includes `child_budget` so clients can inspect the allocation
that was actually carved and propagated.

`handle` is a small Lua table with at minimum:

- `id` — opaque handle ID, scoped to the current runtime trace family
- `kind` — one of `evaluation`, `report`, `procedure`
- `status_url` — best-effort dashboard URL when available
- `created_at` — ISO 8601 string
- `parent_trace_id` — the `execute_tactus` trace that created the handle

Subsequent `execute_tactus` calls can:

```tactus
local result = plexus.handle.await{ id = "<id>", timeout = "PT10M" }
local snapshot = plexus.handle.peek{ id = "<id>" }
plexus.handle.cancel{ id = "<id>" }
```

Handle storage and lifecycle are owned by `TactusHandleStore`, which defaults
to JSON files next to the Tactus trace directory. Each handle records the
parent trace, original args, dispatch result, status URL, and refreshed status
data when available. Evaluation handles refresh from `plexus.evaluation.info`
when the dispatch result includes an `evaluation_id`; process-backed
evaluation handles fall back to process liveness.

Implemented handle calls:

- `plexus.handle.peek{ id = "..." }` refreshes and returns the latest stored
  status.
- `plexus.handle.status{ id = "..." }` is an alias for `peek`.
- `plexus.handle.await{ id = "...", timeout = "PT10M" }` polls until a terminal
  status or timeout.
- `plexus.handle.cancel{ id = "..." }` records cancellation intent in the
  handle store and propagates cancellation where the handle carries a supported
  target:
  - `process_id` handles receive `SIGTERM`.
  - `task_id` handles mark the dashboard Task `CANCELLED`.
  - evaluation handles with `evaluation_id` mark the Evaluation `CANCELLED`.
  Report and procedure workers now check dashboard Task cancellation before
  entering major execution phases and stop without converting cancellation into
  a generic failure.

A spawn that would exceed the parent budget is rejected before any remote
dispatch. Evaluation dispatch receives the child allocation in
`PLEXUS_CHILD_BUDGET`, report-block task metadata stores it in the durable
programmatic payload, and procedure dispatch passes it in Tactus context as
`_plexus_child_budget`.

Workers now enforce those propagated budgets at their execution boundary:

- evaluation CLI workers load `PLEXUS_CHILD_BUDGET`, enforce wallclock, and
  reject known scorecard cost totals that exceed the child USD budget.
- durable programmatic report-block workers enforce wallclock from the
  `child_budget` payload before running the block.
- procedure workers enforce wallclock, apply `depth` as Tactus `max_depth`, and
  reject LLM cost events that exceed the child USD budget.

## Remaining Work

- Evaluation worker-side cancellation remains cooperative beyond process
  termination and Evaluation record updates; deeper in-process checkpoints can
  be added if evaluations begin running without a killable process boundary.
- Report configuration handles currently require a dedicated report task
  dispatch path; the implemented report handle path is for durable
  programmatic report-block tasks.
- Full child tool-call accounting remains limited by worker-specific telemetry;
  current enforcement covers dispatch reservation, worker wallclock/depth, and
  known USD cost emissions.

## Removing Gates

There is intentionally no fallback: each long-running API is either a direct
handler with an async handle path or rejects blocking calls with
`requires_handle_protocol`.
