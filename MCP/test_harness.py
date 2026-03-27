#!/usr/bin/env python3
"""
Plexus MCP Server Test Harness

Starts the MCP server as a subprocess (same way Claude Code does) and sends
JSON-RPC messages over stdio to test tools end-to-end without needing to
restart the MCP server in the IDE.

Usage:
    python test_harness.py                    # Run all tests
    python test_harness.py --tool evaluation_run  # Test specific tool
    python test_harness.py --list             # List available tests
    python test_harness.py --interactive      # Interactive REPL mode

The server is started fresh for each test run and killed when done.
"""

import os
import sys
import json
import time
import subprocess
import threading
import argparse
from typing import Optional, Any

# ── Server configuration (mirrors ~/.cursor/mcp.json) ──────────────────────
PYTHON = "/home/ryan/miniconda3/envs/py311/bin/python"
WRAPPER = "/home/ryan/projects/Plexus/MCP/plexus_fastmcp_wrapper.py"
TARGET_CWD = "/home/ryan/projects/Plexus/"
SERVER_ENV = {
    **os.environ,
    "PYTHONUNBUFFERED": "1",
    "PYTHONPATH": "/home/ryan/projects/Plexus",
}

# ── Colours ─────────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ── MCP Server subprocess wrapper ───────────────────────────────────────────

class MCPServer:
    """Manages a single MCP server subprocess with JSON-RPC communication."""

    def __init__(self, timeout: float = 30.0, verbose: bool = False):
        self.timeout = timeout
        self.verbose = verbose
        self._proc: Optional[subprocess.Popen] = None
        self._msg_id = 0
        self._reader_thread: Optional[threading.Thread] = None
        self._pending: dict = {}  # id -> response event + result
        self._lock = threading.Lock()
        self._initialized = False

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self):
        """Start the MCP server subprocess."""
        cmd = [PYTHON, WRAPPER, "--transport", "stdio", "--target-cwd", TARGET_CWD]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=SERVER_ENV,
            cwd=TARGET_CWD,
        )
        # Background thread drains stderr (avoids deadlock)
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        # Background thread reads responses
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        print(f"{CYAN}[harness] Server started (pid {self._proc.pid}){RESET}", file=sys.stderr)

    def stop(self):
        """Kill the server subprocess."""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            self._proc = None
            self._initialized = False
        print(f"{CYAN}[harness] Server stopped{RESET}", file=sys.stderr)

    def restart(self):
        self.stop()
        time.sleep(0.5)
        self.start()
        self.initialize()

    # ── MCP protocol ─────────────────────────────────────────────────────────

    def initialize(self) -> dict:
        """Send MCP initialize handshake."""
        resp = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-harness", "version": "1.0"},
        })
        # Send initialized notification (no response expected)
        self._send_notification("notifications/initialized", {})
        self._initialized = True
        return resp

    def list_tools(self) -> list[dict]:
        """Return list of registered tools."""
        resp = self._rpc("tools/list", {})
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict = None, timeout: float = None) -> dict:
        """Call a named tool and return the result dict."""
        return self._rpc(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            timeout=timeout or self.timeout,
        )

    # ── internals ────────────────────────────────────────────────────────────

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _send(self, msg: dict):
        line = json.dumps(msg) + "\n"
        if self.verbose:
            print(f"{YELLOW}>>> {line.strip()}{RESET}", file=sys.stderr)
        self._proc.stdin.write(line.encode())
        self._proc.stdin.flush()

    def _send_notification(self, method: str, params: dict):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _rpc(self, method: str, params: dict, timeout: float = None) -> dict:
        msg_id = self._next_id()
        event = threading.Event()
        with self._lock:
            self._pending[msg_id] = {"event": event, "result": None}
        self._send({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params})
        waited = event.wait(timeout=timeout or self.timeout)
        if not waited:
            raise TimeoutError(f"Timed out waiting for response to '{method}' (id={msg_id})")
        with self._lock:
            entry = self._pending.pop(msg_id, {})
        return entry.get("result", {})

    def _read_loop(self):
        """Background thread: read newline-delimited JSON from server stdout."""
        while self._proc and self._proc.poll() is None:
            try:
                raw = self._proc.stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                if self.verbose:
                    print(f"{YELLOW}<<< {line}{RESET}", file=sys.stderr)
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg_id = msg.get("id")
                if msg_id is not None:
                    with self._lock:
                        if msg_id in self._pending:
                            self._pending[msg_id]["result"] = msg
                            self._pending[msg_id]["event"].set()
            except Exception as e:
                print(f"{RED}[harness] read_loop error: {e}{RESET}", file=sys.stderr)
                break

    def _drain_stderr(self):
        """Background thread: drain server stderr to keep the pipe from blocking."""
        while self._proc and self._proc.poll() is None:
            try:
                line = self._proc.stderr.readline()
                if not line:
                    break
                if self.verbose:
                    print(f"[server] {line.decode().rstrip()}", file=sys.stderr)
            except Exception:
                break

    def __enter__(self):
        self.start()
        self.initialize()
        return self

    def __exit__(self, *_):
        self.stop()


# ── Test runner ──────────────────────────────────────────────────────────────

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.skipped = False
        self.message = ""
        self.duration = 0.0


def run_test(name: str, fn, server: MCPServer) -> TestResult:
    result = TestResult(name)
    t0 = time.time()
    try:
        fn(server, result)
        if not result.skipped:
            result.passed = True
    except Exception as e:
        result.message = str(e)
    result.duration = time.time() - t0
    icon = (f"{GREEN}PASS{RESET}" if result.passed
            else f"{YELLOW}SKIP{RESET}" if result.skipped
            else f"{RED}FAIL{RESET}")
    extra = f"  {result.message}" if result.message else ""
    print(f"  [{icon}] {name} ({result.duration:.1f}s){extra}")
    return result


# ── Individual tests ─────────────────────────────────────────────────────────

def test_server_starts(server: MCPServer, result: TestResult):
    """Server process should be running after initialization."""
    assert server._proc is not None, "Process not started"
    assert server._proc.poll() is None, "Process exited prematurely"
    assert server._initialized, "Initialize handshake not completed"


def test_list_tools(server: MCPServer, result: TestResult):
    """tools/list should return a non-empty list including key tools."""
    tools = server.list_tools()
    tool_names = {t["name"] for t in tools}
    required = {"plexus_evaluation_run", "plexus_evaluation_info", "plexus_scorecards_list"}
    missing = required - tool_names
    assert not missing, f"Missing tools: {missing}"
    result.message = f"{len(tools)} tools registered"


def test_evaluation_info_latest(server: MCPServer, result: TestResult):
    """plexus_evaluation_info with use_latest=True should return evaluation data."""
    resp = server.call_tool("plexus_evaluation_info", {
        "use_latest": True,
        "output_format": "json",
    }, timeout=30)
    assert "error" not in resp, f"Got error: {resp.get('error')}"
    content = resp.get("result", {}).get("content", [])
    assert content, f"Empty content in response: {resp}"
    text = content[0].get("text", "") if content else ""
    assert text, "Empty text in response"
    data = json.loads(text)
    assert "id" in data, f"No 'id' in response: {data}"
    result.message = f"Latest eval: {data['id'][:8]}... status={data.get('status')}"


def test_scorecards_list(server: MCPServer, result: TestResult):
    """plexus_scorecards_list should return scorecards."""
    resp = server.call_tool("plexus_scorecards_list", {}, timeout=30)
    content = resp.get("result", {}).get("content", [])
    assert content, f"Empty content: {resp}"
    text = content[0].get("text", "")
    assert "SelectQuote" in text or "scorecard" in text.lower(), f"Unexpected content: {text[:200]}"
    result.message = f"{len(text)} chars returned"


def test_evaluation_run_dispatches(server: MCPServer, result: TestResult):
    """plexus_evaluation_run feedback should dispatch without timing out.

    This is the core test for the timeout bug. Currently the tool blocks until
    the evaluation completes (~5 min), causing AbortError in Claude Code.
    After the fix, it should return an evaluation_id immediately.
    """
    # Use a small evaluation to keep test fast; once fix is in, this should
    # return quickly even for large evaluations.
    resp = server.call_tool("plexus_evaluation_run", {
        "scorecard_name": "SelectQuote HCS Medium-Risk",
        "score_name": "Shipping Address",
        "evaluation_type": "feedback",
        "days": 7,
    }, timeout=120)  # 2-minute timeout; currently fails because tool blocks for full run

    content = resp.get("result", {}).get("content", [])
    assert content, f"Empty content — tool may have timed out or errored: {resp}"
    text = content[0].get("text", "") if content else ""

    # Check for dispatched response (fix target: returns immediately)
    try:
        data = json.loads(text)
        eval_id = data.get("evaluation_id") or data.get("id")
        assert eval_id, f"No evaluation_id in response: {data}"
        result.message = f"evaluation_id={eval_id[:8]}..."
    except json.JSONDecodeError:
        # Might be a plain string response
        assert "evaluation" in text.lower(), f"Unexpected text response: {text[:200]}"
        result.message = text[:80]


# ── Test registry ────────────────────────────────────────────────────────────

TESTS = {
    "server_starts":           test_server_starts,
    "list_tools":              test_list_tools,
    "scorecards_list":         test_scorecards_list,
    "evaluation_info_latest":  test_evaluation_info_latest,
    "evaluation_run_dispatches": test_evaluation_run_dispatches,
}

FAST_TESTS = ["server_starts", "list_tools"]  # sub-second tests


# ── Interactive mode ─────────────────────────────────────────────────────────

def interactive(server: MCPServer):
    """Simple REPL for calling tools manually."""
    print(f"\n{BOLD}Interactive MCP REPL{RESET}")
    print("Commands:")
    print("  list                     — list tools")
    print("  call <tool> [json_args]  — call a tool")
    print("  restart                  — restart server")
    print("  quit / exit              — exit\n")

    while True:
        try:
            line = input(f"{CYAN}mcp>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line in ("quit", "exit"):
            break
        if line == "list":
            tools = server.list_tools()
            for t in tools:
                print(f"  {t['name']}")
        elif line == "restart":
            server.restart()
            print("Server restarted.")
        elif line.startswith("call "):
            parts = line[5:].split(None, 1)
            tool_name = parts[0]
            args = json.loads(parts[1]) if len(parts) > 1 else {}
            try:
                resp = server.call_tool(tool_name, args, timeout=120)
                content = resp.get("result", {}).get("content", [{}])
                text = content[0].get("text", json.dumps(resp, indent=2)) if content else json.dumps(resp, indent=2)
                print(text[:2000])
            except TimeoutError as e:
                print(f"{RED}Timeout: {e}{RESET}")
            except Exception as e:
                print(f"{RED}Error: {e}{RESET}")
        else:
            print(f"Unknown command: {line}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plexus MCP Server Test Harness")
    parser.add_argument("--list", action="store_true", help="List available tests")
    parser.add_argument("--tool", metavar="NAME", help="Run only tests matching name")
    parser.add_argument("--fast", action="store_true", help="Run only fast (sub-second) tests")
    parser.add_argument("--interactive", action="store_true", help="Start interactive REPL")
    parser.add_argument("--verbose", action="store_true", help="Show raw JSON-RPC messages")
    args = parser.parse_args()

    if args.list:
        print("Available tests:")
        for name in TESTS:
            tag = " [fast]" if name in FAST_TESTS else ""
            print(f"  {name}{tag}")
        return

    # Select tests to run
    if args.fast:
        selected = {k: v for k, v in TESTS.items() if k in FAST_TESTS}
    elif args.tool:
        selected = {k: v for k, v in TESTS.items() if args.tool in k}
        if not selected:
            print(f"{RED}No tests matching '{args.tool}'{RESET}")
            sys.exit(1)
    elif args.interactive:
        selected = {}
    else:
        selected = TESTS

    with MCPServer(timeout=60, verbose=args.verbose) as server:
        if args.interactive:
            interactive(server)
            return

        print(f"\n{BOLD}Running {len(selected)} test(s)...{RESET}\n")
        results = [run_test(name, fn, server) for name, fn in selected.items()]

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    total_time = sum(r.duration for r in results)

    print(f"\n{BOLD}Results: {GREEN}{passed} passed{RESET}", end="")
    if failed:
        print(f", {RED}{failed} failed{RESET}", end="")
    if skipped:
        print(f", {YELLOW}{skipped} skipped{RESET}", end="")
    print(f"  ({total_time:.1f}s total){RESET}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
