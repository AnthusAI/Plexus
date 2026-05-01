"""
`plexus execute` — run a Tactus snippet through the same runtime as execute_tactus.

The MCP directory must be on PYTHONPATH:
    export PYTHONPATH=/path/to/Plexus-4/MCP:$PYTHONPATH

Usage
-----
    # Inline snippet
    plexus execute 'return plexus.scorecards.list({})'

    # Read from a file
    plexus execute --file my_script.tactus

    # Read from stdin
    echo 'return plexus.api.list()' | plexus execute -

    # Pretty-print JSON output (default)
    plexus execute 'return plexus.scorecards.list({})' --pretty

    # Raw compact JSON (useful for piping)
    plexus execute 'return plexus.scorecards.list({})' --no-pretty

    # Print only the value, not the full envelope
    plexus execute 'return plexus.scorecards.list({})' --value-only
"""

import asyncio
import json
import sys

import click


@click.command("execute")
@click.argument("tactus", required=False)
@click.option(
    "--file", "-f",
    "tactus_file",
    type=click.Path(exists=True, allow_dash=True, readable=True),
    default=None,
    help="Read Tactus snippet from a file (use '-' for stdin).",
)
@click.option(
    "--pretty/--no-pretty",
    default=True,
    show_default=True,
    help="Pretty-print JSON output.",
)
@click.option(
    "--value-only",
    is_flag=True,
    default=False,
    help="Print only the 'value' field of the response envelope.",
)
@click.option(
    "--budget-usd",
    type=float,
    default=0.25,
    show_default=True,
    help="USD budget cap for this execution.",
)
@click.option(
    "--budget-seconds",
    type=float,
    default=60.0,
    show_default=True,
    help="Wall-clock seconds budget cap.",
)
def execute(
    tactus: str | None,
    tactus_file: str | None,
    pretty: bool,
    value_only: bool,
    budget_usd: float,
    budget_seconds: float,
) -> None:
    """Execute a Tactus snippet through the Plexus runtime.

    TACTUS is the snippet to run.  Alternatively supply --file / stdin.
    """
    # --- resolve the snippet source -----------------------------------------
    if tactus_file:
        if tactus_file == "-":
            snippet = sys.stdin.read()
        else:
            with open(tactus_file, encoding="utf-8") as fh:
                snippet = fh.read()
    elif tactus:
        snippet = tactus
    elif not sys.stdin.isatty():
        snippet = sys.stdin.read()
    else:
        raise click.UsageError(
            "Provide a TACTUS argument, --file, or pipe a snippet via stdin."
        )

    snippet = snippet.strip()
    if not snippet:
        raise click.UsageError("Tactus snippet is empty.")

    # --- run through the same path as the MCP tool --------------------------
    # Ensure the MCP directory itself is on sys.path so that MCP-internal
    # imports like `from shared.utils import ...` resolve correctly.
    import os as _os
    _mcp_dir = _os.path.normpath(
        _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "MCP")
    )
    if _os.path.isdir(_mcp_dir) and _mcp_dir not in sys.path:
        sys.path.insert(0, _mcp_dir)

    try:
        from MCP.tools.tactus_runtime.execute import (
            BudgetGate,
            BudgetSpec,
            _run_tactus_sync,
            _default_trace_store,
        )
    except ImportError as exc:
        raise click.ClickException(
            f"Could not import Tactus runtime (is the MCP directory on your path?): {exc}"
        ) from exc

    # BudgetGate accepts the limits we pass; trace store is ephemeral.
    budget = BudgetGate(BudgetSpec(usd=budget_usd, wallclock_seconds=budget_seconds))
    store = _default_trace_store()

    # _run_tactus_sync uses asyncio.run() internally for the async body but
    # is itself synchronous — we can call it directly from Click's sync context.
    # The `mcp` argument is only needed for MCP-loopback calls (none in the
    # direct-handler world), so we pass a lightweight stub.
    class _StubMCP:
        """Minimal stub satisfying the mcp parameter contract."""
        pass

    # Redirect stdout → stderr during execution so that any diagnostic print()
    # calls inside the runtime don't corrupt the JSON output.
    _real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        result = _run_tactus_sync(
            snippet,
            _StubMCP(),  # type: ignore[arg-type]
            trace_id=f"cli-{__import__('uuid').uuid4()}",
            trace_store=store,
            budget=budget,
        )
    finally:
        sys.stdout = _real_stdout

    # --- format and emit output ----------------------------------------------
    if value_only:
        output_obj = result.get("value")
    else:
        output_obj = result

    indent = 2 if pretty else None
    click.echo(json.dumps(output_obj, indent=indent, default=str))

    # Exit non-zero if the runtime reported an error.
    if not result.get("ok", True):
        sys.exit(1)
