# Tactus Host Module Contract

This spike assumes Plexus will be exposed to Tactus as an explicit host module,
not as part of the Tactus standard library.

## Host Registration

Production code should register the Plexus capability module on a runtime before
executing user-supplied Tactus code:

```python
runtime.register_python_module("plexus", plexus_module)
```

Tactus code then imports Plexus with the ordinary Tactus `require` mechanism:

```tactus
local plexus = require("plexus")
```

The `plexus` name is an explicit host capability. It must not be discoverable via
arbitrary Python imports, filesystem paths, or the Tactus standard library.

## Required Tactus Behavior

- Host module names are validated as dotted identifiers.
- Host modules cannot use the reserved `tactus.*` namespace.
- Explicit host modules resolve before local `.tac` files, so `plexus.tac` cannot
  shadow `require("plexus")`.
- Tactus stdlib Python modules remain fallback behavior after `.tac` searchers,
  preserving existing Tactus-first semantics for `tactus.*`.
- Re-registering a host module clears Tactus's require cache for that module.

## Spike Harness Shim

The current harness uses a direct Lupa shim for `require("plexus")` because the
host-module API is being developed in Tactus first. The Tactus-side contract is
already the same as production:

```tactus
local plexus = require("plexus")
```

Once Plexus depends on a Tactus version with host modules, the shim should be
removed and replaced with `runtime.register_python_module("plexus", ...)`.
