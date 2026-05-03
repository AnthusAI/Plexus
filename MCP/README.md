# Plexus MCP Server

The Plexus MCP server exposes one programmable tool: `execute_tactus`.

Instead of publishing a separate MCP tool for every Plexus operation, the server
runs short Tactus/Lua snippets inside a sandboxed runtime. The runtime injects
`plexus` as a global host module, so agents can call Plexus APIs
programmatically without repeating the import boilerplate:

```lua
return plexus.score.info{
  scorecard_identifier = "Quality Assurance v1.0",
  score_identifier = "Compliance Check",
}
```

The MCP interface stays small while the Plexus runtime surface can grow behind
the `plexus` host module. This follows the broader Tactus
[One Tool For Everything](https://tactus.anth.us/use-cases/one-tool-programmable-api/)
pattern.

## Discovery

Start every session by discovering the available runtime API and docs from
inside `execute_tactus`:

```lua
return plexus.api.list()
```

```lua
return plexus.docs.list()
```

```lua
return plexus.docs.get{ key = "overview" }
```

Docs live under `plexus/docs/` and are exposed through `plexus.docs.*`. The
runtime rejects path traversal and unknown documentation keys.

## Common Calls

Run a local prediction:

```lua
return plexus.score.predict{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  item_id = "item-123",
  yaml = true,
}
```

Find feedback items:

```lua
return plexus.feedback.find{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  initial_value = "No",
  final_value = "Yes",
  limit = 5,
  days = 30,
}
```

Run a long evaluation with an async handle:

```lua
local handle = plexus.evaluation.run{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  n_samples = 200,
  yaml = true,
  async = true,
  budget = {
    usd = 0.25,
    wallclock_seconds = 900,
    depth = 1,
    tool_calls = 20,
  },
}

return { evaluation_handle = handle }
```

Poll, await, or cancel a handle in a later `execute_tactus` call:

```lua
return plexus.handle.await{ id = "<handle-id>", timeout = "PT10M" }
```

## Runtime Contract

`execute_tactus` returns a structured envelope with:

- `ok`: whether execution completed successfully
- `value`: the returned Lua/Tactus value, when successful
- `error`: structured error details, when unsuccessful
- `cost`: budget and usage information
- `api_calls`: Plexus runtime calls made by the snippet
- `trace_id` and trace metadata for debugging

Long-running calls such as `plexus.evaluation.run`, `plexus.report.run`, and
`plexus.procedure.run` require `async = true` with an explicit child `budget`.
Blocking calls that need handle semantics fail with a structured
`requires_handle_protocol` error.

## Server Entry Points

The main server entry point is `MCP/server.py`. It registers only
`execute_tactus`:

```bash
python MCP/server.py --transport stdio
```

Authenticated ASGI usage is wired through `MCP/asgi_app.py`.

## Adding Plexus Capabilities

Do not add a new top-level MCP tool for each feature. Add capabilities to the
Tactus runtime instead:

1. Implement or wire the Plexus SDK/service function.
2. Expose it through `MCP/tools/tactus_runtime/execute.py`, preferably as a
   direct handler.
3. Make it discoverable through `plexus.api.list()`.
4. Document the workflow under `plexus/docs/`.
5. Add tests in `MCP/tools/tactus_runtime/execute_test.py`.

This keeps the external MCP schema stable while giving agents a richer,
composable programming surface.

## Related Runtime Docs

- `MCP/tools/tactus_runtime/HANDLE_PROTOCOL.md`
- `plexus/docs/overview.md`
- `plexus/docs/discovery.md`
- `plexus/docs/evaluation-and-feedback/`
