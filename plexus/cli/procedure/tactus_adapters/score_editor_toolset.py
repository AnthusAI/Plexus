"""
Score Editor Toolset for Feedback Alignment Optimizer

Provides a virtual in-memory YAML file editing interface for the code_editor agent.
Implements the standard str_replace_editor text editor tool protocol so Claude models
can make targeted, precise edits to score configuration YAML.

Key tools exposed:
- str_replace_editor: Standard Claude text editor tool (view/str_replace/insert/undo_edit)
- submit_score_code: State-transition tool that validates and creates a new ScoreVersion
- score_editor_setup: MCP tool called from Lua to initialize the virtual file
- score_editor_get_result: MCP tool called from Lua to retrieve the created version ID
"""

import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

VIRTUAL_PATH = "score_config.yaml"


class ScoreEditorToolset:
    """
    Manages a virtual in-memory YAML file for code_editor agent sessions.

    Lifecycle per iteration:
      1. Lua calls score_editor_setup(yaml_content, scorecard, score, iteration, hypothesis)
      2. code_editor agent calls str_replace_editor to view and edit the file
      3. code_editor agent calls submit_score_code() when edits are complete
      4. Lua calls score_editor_get_result() to retrieve the new version ID
    """

    def __init__(self, mcp_client=None):
        self._mcp_client = mcp_client
        self._content: str = ""
        self._original: str = ""
        self._history: List[str] = []
        self._scorecard: str = ""
        self._score: str = ""
        self._iteration: int = 0
        self._hypothesis: str = ""
        self._dry_run: bool = False
        self._last_version_id: Optional[str] = None

    # ------------------------------------------------------------------
    # MCP tools (called from Lua via call_plexus_tool)
    # ------------------------------------------------------------------

    def setup(self, arguments: dict) -> dict:
        """
        Set up the score editor for a new iteration.

        NOTE: yaml_content is NOT accepted here — it is too large to pass through
        the orchestrator LLM. Instead, content is auto-loaded on the first
        str_replace_editor(command="view") call via the MCP client.
        """
        self._content = ""       # will be loaded lazily on first view
        self._original = ""
        self._history = []
        # Only overwrite scorecard/score if the caller provides non-empty values.
        # When the orchestrator LLM calls setup({}) (args stripped by DSPy), we
        # preserve the values pre-populated by procedure_executor from context.
        new_scorecard = arguments.get("scorecard_identifier", arguments.get("scorecard", ""))
        new_score = arguments.get("score_identifier", arguments.get("score", ""))
        if new_scorecard:
            self._scorecard = new_scorecard
        if new_score:
            self._score = new_score
        self._iteration = int(arguments.get("iteration", 0) or 0)
        self._hypothesis = str(arguments.get("hypothesis", "") or "")
        self._dry_run = bool(arguments.get("dry_run", False))
        self._last_version_id = None
        logger.info(
            "ScoreEditorToolset: initialized for iteration %d, score=%s, dry_run=%s",
            self._iteration, self._score, self._dry_run,
        )
        return {
            "success": True,
            "message": (
                f"Score editor ready for iteration {self._iteration}. "
                f"Call str_replace_editor(command=\"view\", path=\"{VIRTUAL_PATH}\") "
                f"to load and view the current score configuration."
            ),
            "path": VIRTUAL_PATH,
        }

    def get_result(self, arguments: dict) -> dict:
        """Return the version ID created by the last submit_score_code call."""
        if self._last_version_id:
            return {"success": True, "version_id": self._last_version_id}
        return {
            "success": False,
            "version_id": None,
            "message": "No score version has been submitted yet",
        }

    # ------------------------------------------------------------------
    # Agent tools (called by code_editor agent)
    # ------------------------------------------------------------------

    def str_replace_editor(self, arguments: dict) -> str:
        """
        Standard Claude text editor tool — virtual in-memory implementation.

        Commands: view, str_replace, insert, undo_edit, create
        Path: must be 'score_config.yaml'

        On the first view command, automatically loads the current champion score
        YAML from the Plexus API (avoids passing large content through LLM args).
        """
        command = arguments.get("command", "")
        path = arguments.get("path", "")

        if path != VIRTUAL_PATH:
            return (
                f"Error: Only '{VIRTUAL_PATH}' is available for editing.\n"
                f"Requested path: {path}\n"
                f"Use: str_replace_editor(command=\"view\", path=\"{VIRTUAL_PATH}\")"
            )

        if command == "view":
            # Auto-load content on first view if not yet populated
            if not self._content:
                load_error = self._load_content_from_api()
                if load_error:
                    return f"Error loading score configuration: {load_error}"

            view_range = arguments.get("view_range")
            lines = self._content.split("\n")
            if view_range and len(view_range) == 2:
                start = max(0, int(view_range[0]) - 1)
                end = min(len(lines), int(view_range[1]))
                selected = lines[start:end]
                return "\n".join(f"{start + i + 1}\t{line}" for i, line in enumerate(selected))
            return "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(lines))

        elif command == "str_replace":
            old_str = arguments.get("old_str")
            new_str = arguments.get("new_str", "")
            if not old_str:
                return "Error: old_str is required for str_replace command"
            if old_str not in self._content:
                # Provide a helpful snippet of the area around the expected location
                return (
                    "Error: No match found for old_str. The exact text (including whitespace "
                    "and indentation) was not found in the file.\n\n"
                    "Tip: Use view to re-read the file and copy old_str exactly."
                )
            count = self._content.count(old_str)
            if count > 1:
                return (
                    f"Error: old_str matches {count} locations in the file. "
                    "Provide more surrounding context to make it unique."
                )
            self._history.append(self._content)
            self._content = self._content.replace(old_str, new_str, 1)
            return self._format_edit_result("str_replace")

        elif command == "insert":
            insert_line = arguments.get("insert_line")
            new_str = arguments.get("new_str", "")
            if insert_line is None:
                return "Error: insert_line is required for insert command"
            if not new_str:
                return "Error: new_str is required for insert command"
            self._history.append(self._content)
            lines = self._content.split("\n")
            insert_at = max(0, min(int(insert_line), len(lines)))
            insert_lines = new_str.split("\n")
            lines[insert_at:insert_at] = insert_lines
            self._content = "\n".join(lines)
            return self._format_edit_result("insert")

        elif command == "undo_edit":
            if not self._history:
                return "Error: No previous edit to undo"
            self._content = self._history.pop()
            return "Last edit undone.\n\n" + self._format_validation()

        elif command == "create":
            new_str = arguments.get("new_str", arguments.get("file_text", ""))
            self._history.append(self._content)
            self._content = new_str
            return self._format_edit_result("create")

        else:
            return (
                f"Error: Unknown command '{command}'. "
                "Supported: view, str_replace, insert, undo_edit, create"
            )

    async def submit_score_code(self, arguments: dict) -> dict:
        """
        Validate and submit the current virtual file as a new score version.

        - Errors if the file is unchanged from the original.
        - Errors if YAML syntax validation fails.
        - In dry_run mode, records a fake version ID without calling the API.
        - On success, stores the new version ID for Lua to retrieve via score_editor_get_result.
        """
        version_note = arguments.get("version_note") or None

        if self._content == self._original:
            return {
                "success": False,
                "error": (
                    "Score code is unchanged from the original. "
                    "Make edits using str_replace_editor before calling submit_score_code."
                ),
            }

        # Validate YAML syntax
        errors = self._get_validation_errors()
        if errors:
            error_text = "\n".join(f"  - {e}" for e in errors)
            return {
                "success": False,
                "error": f"YAML validation failed. Fix these errors before submitting:\n{error_text}",
            }

        note = version_note or (
            f"Iteration {self._iteration}: {self._hypothesis[:150]}"
            if self._hypothesis
            else f"Iteration {self._iteration}: automated optimizer update"
        )

        # Dry run: skip API call
        if self._dry_run:
            fake_id = f"dry-run-iter-{self._iteration}"
            self._last_version_id = fake_id
            logger.info("ScoreEditorToolset: dry_run=True, skipping plexus_score_update")
            return {
                "success": True,
                "version_id": fake_id,
                "message": f"Dry run: score version not created (would be: iteration {self._iteration})",
                "dry_run": True,
            }

        # Call plexus_score_update via MCP client
        if not self._mcp_client:
            return {"success": False, "error": "No MCP client available for score update"}

        try:
            update_result = await self._mcp_client.call_tool(
                "plexus_score_update",
                {
                    "scorecard_identifier": self._scorecard,
                    "score_identifier": self._score,
                    "code": self._content,
                    "version_note": note,
                },
            )

            # Extract version ID from MCP response envelope
            version_id = self._extract_version_id(update_result)
            if version_id:
                self._last_version_id = version_id
                return {
                    "success": True,
                    "version_id": version_id,
                    "message": f"Score version created: {version_id}",
                }
            else:
                return {
                    "success": False,
                    "error": f"plexus_score_update returned unexpected format: {update_result}",
                }

        except Exception as exc:
            logger.error("ScoreEditorToolset.submit_score_code error: %s", exc)
            return {"success": False, "error": f"Failed to create score version: {exc}"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_content_from_api(self) -> Optional[str]:
        """
        Load the current champion score YAML via plexus_score_pull.
        plexus_score_pull writes the code to a local file and returns the path.
        Returns None on success, or an error string on failure.
        """
        if not self._mcp_client or not self._scorecard or not self._score:
            return "Score editor not set up — call score_editor_setup first"

        import asyncio
        import json
        import os

        async def _do_pull():
            return await self._mcp_client.call_tool(
                "plexus_score_pull",
                {
                    "scorecard_identifier": self._scorecard,
                    "score_identifier": self._score,
                },
            )

        try:
            # Run the async pull in a thread to avoid nested event loop issues
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _do_pull())
                result = future.result(timeout=60)

            # plexus_score_pull returns {"content": [{"type": "text", "text": "{...json...}"}]}
            # The inner JSON has {"success": true, "codeFilePath": "/path/to/file.yaml", ...}
            pull_data = None
            if isinstance(result, dict):
                for item in result.get("content", []):
                    if isinstance(item, dict) and item.get("type") == "text":
                        try:
                            pull_data = json.loads(item["text"])
                            break
                        except (ValueError, TypeError, KeyError):
                            pass
                # Also try direct dict fields (non-wrapped response)
                if pull_data is None:
                    pull_data = result

            if not pull_data or not pull_data.get("success"):
                return f"plexus_score_pull failed: {result}"

            code_file_path = pull_data.get("codeFilePath")
            if not code_file_path:
                return f"plexus_score_pull returned no codeFilePath: {pull_data}"

            if not os.path.exists(code_file_path):
                return f"plexus_score_pull wrote to {code_file_path} but file does not exist"

            with open(code_file_path, "r") as f:
                code = f.read()

            if not code:
                return f"Score code file is empty: {code_file_path}"

            self._content = code
            self._original = code
            self._history = []
            logger.info(
                "ScoreEditorToolset: auto-loaded %d chars for %s/%s from %s",
                len(code), self._scorecard, self._score, code_file_path,
            )
            return None

        except Exception as exc:
            logger.error("ScoreEditorToolset._load_content_from_api error: %s", exc)
            return str(exc)

    def _format_edit_result(self, operation: str) -> str:
        validation = self._format_validation()
        return f"Edit applied ({operation}).\n\n{validation}"

    def _format_validation(self) -> str:
        try:
            from plexus.linting.yaml_linter import YamlLinter
            linter = YamlLinter()
            result = linter.lint(self._content)
            errors = [m for m in result.messages if m.level == "error"]
            warnings = [m for m in result.messages if m.level == "warning"]
            if not errors:
                if warnings:
                    lines = [f"✓ YAML syntax valid ({len(warnings)} warning(s)):"]
                    for m in warnings[:3]:
                        loc = f" (line {m.line})" if m.line else ""
                        lines.append(f"  ⚠ {m.title}{loc}: {m.message}")
                    return "\n".join(lines)
                return "✓ YAML syntax valid"
            lines = [f"✗ YAML validation failed ({len(errors)} error(s)):"]
            for m in errors[:5]:
                loc = f" (line {m.line})" if m.line else ""
                lines.append(f"  ✗ {m.title}{loc}: {m.message}")
                if m.suggestion:
                    lines.append(f"    → {m.suggestion}")
            return "\n".join(lines)
        except Exception as exc:
            return f"(Validation unavailable: {exc})"

    def _get_validation_errors(self) -> List[str]:
        try:
            from plexus.linting.yaml_linter import YamlLinter
            result = YamlLinter().lint(self._content)
            return [
                f"{m.title}" + (f" (line {m.line})" if m.line else "") + f": {m.message}"
                for m in result.messages
                if m.level == "error"
            ]
        except Exception:
            return []

    def _extract_version_id(self, mcp_response: Any) -> Optional[str]:
        """Extract newVersionId or version_id from a MCP tool call response."""
        import json

        if not isinstance(mcp_response, dict):
            return None

        # Direct fields (non-wrapped response)
        for key in ("newVersionId", "version_id", "versionId"):
            if mcp_response.get(key):
                return mcp_response[key]

        # MCP content envelope: {"content": [{"type": "text", "text": "..."}]}
        for item in mcp_response.get("content", []):
            if not isinstance(item, dict):
                continue
            text = item.get("text", "")
            if not text:
                continue
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    for key in ("newVersionId", "version_id", "versionId"):
                        if data.get(key):
                            return data[key]
            except (ValueError, TypeError):
                pass

        return None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    @classmethod
    def register_on_transport(cls, transport, mcp_client=None) -> "ScoreEditorToolset":
        """
        Create a ScoreEditorToolset instance and register all four tools on the
        InProcessMCPTransport so they are available via call_plexus_tool() from Lua
        and via the agent toolset registry after mcp_adapter.load_tools().

        Call this BEFORE mcp_adapter.load_tools() in procedure_executor.py.
        """
        from plexus.cli.procedure.mcp_transport import MCPToolInfo

        instance = cls(mcp_client=mcp_client)

        transport.register_tool(MCPToolInfo(
            name="score_editor_setup",
            description=(
                "Set up the score editor for a new iteration. "
                "The score YAML is loaded automatically on first view — do NOT pass yaml_content. "
                "Call this before dispatching the code_editor agent each iteration."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "scorecard_identifier": {"type": "string", "description": "Scorecard name, key, or ID"},
                    "score_identifier": {"type": "string", "description": "Score name, key, or ID"},
                    "iteration": {"type": "integer", "description": "Current iteration number"},
                    "hypothesis": {"type": "string", "description": "Short hypothesis for the version note (max 200 chars)"},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["scorecard_identifier", "score_identifier"],
                "additionalProperties": False,
            },
            handler=instance.setup,
        ))

        transport.register_tool(MCPToolInfo(
            name="score_editor_get_result",
            description="Return the version ID created by the last submit_score_code call.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=instance.get_result,
        ))

        transport.register_tool(MCPToolInfo(
            name="str_replace_editor",
            description=(
                "Edit a text file using view, str_replace, insert, undo_edit, or create commands. "
                f"The only available file is '{VIRTUAL_PATH}'."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["view", "str_replace", "create", "insert", "undo_edit"],
                        "description": "The editing command to run",
                    },
                    "path": {
                        "type": "string",
                        "description": f"Path to the file (use '{VIRTUAL_PATH}')",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "For str_replace: the exact text to replace",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "For str_replace/insert/create: the replacement or new text",
                    },
                    "insert_line": {
                        "type": "integer",
                        "description": "For insert: line number to insert after",
                    },
                    "view_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "For view: [start_line, end_line] to limit output",
                    },
                },
                "required": ["command", "path"],
                "additionalProperties": False,
            },
            handler=instance.str_replace_editor,
        ))

        transport.register_tool(MCPToolInfo(
            name="submit_score_code",
            description=(
                "Submit the current virtual score file as a new score version. "
                "Validates YAML syntax first. Errors if the file is unchanged. "
                "Call done() after this succeeds."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "version_note": {
                        "type": "string",
                        "description": "Optional note for the score version (auto-generated if omitted)",
                    },
                },
                "additionalProperties": False,
            },
            handler=instance.submit_score_code,
        ))

        logger.info(
            "ScoreEditorToolset: registered score_editor_setup, score_editor_get_result, "
            "str_replace_editor, submit_score_code on MCP transport"
        )
        return instance
