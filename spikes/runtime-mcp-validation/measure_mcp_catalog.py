"""Measure current Plexus MCP tool-catalog context overhead.

This script imports the modular Plexus MCP server, registers its real FastMCP
tools, serializes the MCP tool schemas, and compares that payload to the
proposed single `execute_tactus` tool description used by this spike.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

from harness import BOOT_PROMPT, RESULTS_DIR, estimate_tokens


ROOT = Path(__file__).resolve().parents[2]
MCP_DIR = ROOT / "MCP"


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def single_tool_schema() -> dict[str, Any]:
    return {
        "name": "execute_tactus",
        "description": BOOT_PROMPT.read_text(),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tactus": {
                    "type": "string",
                    "description": "Tactus code to execute in the Plexus runtime.",
                }
            },
            "required": ["tactus"],
            "additionalProperties": False,
        },
    }


async def load_current_tool_schemas() -> list[dict[str, Any]]:
    sys.path.insert(0, str(MCP_DIR))
    sys.path.insert(0, str(ROOT))

    # The MCP server imports the full Plexus stack and logs heavily during module
    # import. Keep stdout/stderr clean so this script emits machine-readable JSON.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import server

        server.register_all_tools()
        tools = await server.mcp.list_tools()

    return [tool.to_mcp_tool().model_dump(mode="json", exclude_none=True) for tool in tools]


def describe_payload(payload: Any) -> dict[str, int]:
    serialized = compact_json(payload)
    return {
        "bytes": len(serialized.encode("utf-8")),
        "chars": len(serialized),
        "tokens": estimate_tokens(serialized),
    }


async def measure() -> dict[str, Any]:
    current_tools = await load_current_tool_schemas()
    single_tool = [single_tool_schema()]

    current_payload = describe_payload(current_tools)
    single_payload = describe_payload(single_tool)

    largest_tools = sorted(
        (
            {
                "name": tool["name"],
                "tokens": describe_payload(tool)["tokens"],
                "bytes": describe_payload(tool)["bytes"],
            }
            for tool in current_tools
        ),
        key=lambda item: item["tokens"],
        reverse=True,
    )[:10]

    return {
        "current_mcp_tool_count": len(current_tools),
        "current_mcp_catalog": current_payload,
        "single_execute_tactus_tool": single_payload,
        "token_reduction": current_payload["tokens"] - single_payload["tokens"],
        "token_reduction_ratio": (
            round(current_payload["tokens"] / single_payload["tokens"], 2)
            if single_payload["tokens"]
            else None
        ),
        "largest_current_tools": largest_tools,
        "measurement_notes": [
            "Current catalog is serialized from FastMCP tool.to_mcp_tool().model_dump().",
            "Single-tool payload uses boot_prompt.md as the execute_tactus description.",
            "Token counts use the same estimator as the spike harness.",
        ],
    }


def write_measurement(result: dict[str, Any], run_id: str) -> Path:
    directory = RESULTS_DIR / run_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "mcp_catalog_measurement.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="Optional harness run id to save measurement into")
    args = parser.parse_args()

    result = asyncio.run(measure())
    if args.run_id:
        path = write_measurement(result, args.run_id)
        result["path"] = str(path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
