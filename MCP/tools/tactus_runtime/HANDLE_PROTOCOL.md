# execute_tactus long-running handle protocol (v0 specification)

This file documents the contract for long-running Plexus runtime APIs called
from `execute_tactus`. The full design lives in Kanbus epic `plx-247588`
(streaming + handle ergonomics for long-running operations) and depends on
the budget plumbing from `plx-a4b033`.

The current `execute_tactus` build deliberately does **not** implement the
handle/streaming model. Instead, it short-circuits the long-running calls
with a structured error so an MCP client cannot accidentally tie up the
synchronous Tactus runtime for tens of minutes or hours and cannot bypass
the budget gate by hiding cost behind a dispatched task.

## Long-running APIs

The following entries in `MCP_TOOL_MAP` are classified as long-running and
gated by `LONG_RUNNING_METHODS` in `execute.py`:

- `plexus.evaluation.run`
- `plexus.report.run`
- `plexus.procedure.run`

When called in v0, `PlexusRuntimeModule._call`:

1. Records the attempt on `api_calls` so the trace shows the intent.
2. Sets `handle_protocol_required = (namespace, method)`.
3. Raises `RequiresHandleProtocol`, which surfaces in the response envelope
   as `error.code = "requires_handle_protocol"`.

No MCP-loopback call is made and no remote dispatch is started.

## Required protocol (target shape, not yet implemented)

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

Handle storage and lifecycle are owned by the same trace persistence layer
introduced in this PR (`TactusTraceStore`). Each handle carves a sub-budget
out of the parent's `BudgetGate` envelope at creation time. A spawn that
would exceed the parent budget is rejected before any remote dispatch.

## Why this gate exists in v0

- The synchronous `_run_async_from_sync` bridge cannot honour wallclock
  budgets sensibly for runs that intentionally take an hour.
- Running these APIs through the v0 MCP-loopback path would create
  unbudgeted dispatched workers, exactly the failure mode `plx-a4b033`
  ("distributed budget infrastructure", priority 0) was filed to prevent.
- The handle protocol must own its own trace records, sub-budget carving,
  and cancellation semantics; bolting it onto the synchronous path now
  would create a design we would have to rip out.

## Removing the gate

When the implementation tasks for `plx-247588` and `plx-a4b033` ship, the
`LONG_RUNNING_METHODS` set in `execute.py` should shrink as each API gains
its handle/streaming wiring. There is intentionally no fallback: each
removal must come with the real handle/streaming integration and updated
tests that exercise the new contract end to end.
