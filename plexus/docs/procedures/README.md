# Procedures

Topic index for Plexus Procedures — multi-step Tactus-driven workflows
that orchestrate scores, evaluations, optimizers, and chat sessions.

## When to use Procedures

Procedures are the right tool when you need:

- A repeatable, parameterized multi-step workflow (e.g. "for every score
  on this scorecard, pull the champion, run a 200-item evaluation, and
  open an optimizer if AC1 < 0.7").
- A long-running orchestration that should be visible as a first-class
  record in the dashboard, with chat sessions and tool-call history.
- A workflow that should be cancelable, resumable, and auditable.

## Plexus runtime APIs (`execute_tactus`)

- `procedure.list{}` — list procedures for the active account
  (`PLEXUS_ACCOUNT_KEY`). Helper alias: `procedures{}`.
- `procedure.info{ id = "<procedure-id>" }` — fetch a single procedure
  with its current chat sessions. Helper alias: `procedure{ id = ... }`.
- `procedure.chat_sessions{ id = "<procedure-id>" }` — list chat
  sessions for a procedure. Helper alias: `procedure_sessions{ ... }`.
- `procedure.chat_messages{ id = "<procedure-id>", session_id = "..." }`
  — fetch chat messages for a specific session, including tool calls
  and tool responses by default. Helper alias:
  `procedure_messages{ ... }`.
- `procedure.run{ id = "<procedure-id>", async = true, budget = {...} }`
  — long-running. Must use `async = true` with an explicit
  `budget = { usd, wallclock_seconds, depth, tool_calls }`. Returns a
  handle. Helper alias: `procedure_run{ ... }`.

## Reading patterns

```tactus
local procs = procedures{ limit = 10 }
local first = procedure{ id = procs[1].id }
return {
  procedure_id = first.id,
  template = first.template_name,
  session_count = #first.chat_sessions,
}
```

## Long-running pattern

See `long-running-apis` and `handles-and-budgets` at the top of
`plexus/docs/` for the full handle / budget contract used by
`procedure.run`. The async dispatch is rejected without an explicit child
budget.

## Follow-up content

This index is a placeholder. Deeper procedure-authoring content (template
shape, optimizer-procedure recipes, branching strategies) is tracked as a
follow-up to the `execute_tactus` themed-docs work.
