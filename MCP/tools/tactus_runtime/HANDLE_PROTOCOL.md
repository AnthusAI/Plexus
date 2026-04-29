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
2. Dispatches the operation in non-blocking mode.
3. Creates a persisted handle record through `TactusHandleStore`.
4. Returns the public handle table to Tactus.
5. Records exactly one `plexus.<namespace>.run` API call in the response and
   trace cost envelope.

## Protocol

Two complementary mechanisms (per `plx-247588`):

### 1. Streaming during a blocking call

For runs that complete in a "feel-tolerable" timeframe (single-digit
minutes), `execute_tactus` blocks while progress events stream up to the
MCP client through the existing `PlexusTraceSink` /
`_PlexusTraceLogBridge` machinery in
`plexus/cli/procedure/tactus_adapters/trace.py`. Cost events flow on the
same channel.

Response envelope additions:

- `partial = true` while progress is in flight.
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
}
return { evaluation_handle = handle }
```

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

A spawn that would exceed the parent budget is rejected before any remote
dispatch.

## Remaining Work

- Streaming progress notifications still need to be wired to MCP clients.
- Deeper worker-side cancellation remains cooperative: dashboard Tasks and
  Evaluation records are marked cancelled, but any worker already running must
  honor that status to stop promptly.
- Report configuration handles currently require a dedicated report task
  dispatch path; the implemented report handle path is for durable
  programmatic report-block tasks.
- Distributed budget sub-carving from `plx-a4b033` still needs to attach
  child work to parent budgets across dispatch boundaries.

## Removing Gates

There is intentionally no fallback: each long-running API is either a direct
handler with an async handle path or rejects blocking calls with
`requires_handle_protocol`.
