"""
Score Editor Toolset for Feedback Alignment Optimizer

Provides a virtual in-memory YAML file editing interface for the code_editor agent.
Implements the standard str_replace_editor text editor tool protocol so Claude models
can make targeted, precise edits to score configuration YAML.

Key tools exposed:
- str_replace_editor: Standard Claude text editor tool (view/str_replace/insert/undo_edit)
- submit_score_version: State-transition tool that validates and creates a new ScoreVersion
- score_editor_setup: MCP tool called from Lua to initialize the virtual file
- score_editor_get_result: MCP tool called from Lua to retrieve the created version ID
- score_editor_get_content: MCP tool called from Lua to read current virtual file content
"""

import logging
from io import StringIO
from typing import Optional, List, Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from plexus.cli.shared.optimizer_shadow_invalidation import (
    OPTIMIZER_SHADOW_INVALID_FIELD,
    normalize_shadow_invalid_feedback_item_ids,
)

logger = logging.getLogger(__name__)

VIRTUAL_PATH = "score_config.yaml"
GUIDELINES_PATH = "guidelines.md"
ALLOWED_PATHS = (VIRTUAL_PATH, GUIDELINES_PATH)
EXTRACTION_LIKE_VALID_CLASSES = {
    "extract",
    "extracted",
    "found",
    "quoted",
    "quote",
    "located",
    "captured",
    "identified",
}
EXTRACTION_PROMPT_HINTS = (
    "extract",
    "extracted",
    "evidence summary",
    "exact evidence",
    "exact visible evidence",
    "verbatim evidence",
    "quote",
    "quotes",
    "ledger",
    "list every",
    "list each",
    "medication-by-medication",
)


class ScoreEditorToolset:
    """
    Manages a virtual in-memory YAML file for code_editor agent sessions.

    Lifecycle per iteration:
      1. Lua calls score_editor_setup(yaml_content, scorecard, score, iteration, hypothesis)
      2. code_editor agent calls str_replace_editor to view and edit the file
      3. code_editor agent calls submit_score_version() when edits are complete
      4. Lua calls score_editor_get_result() to retrieve the new version ID
    """

    def __init__(self, mcp_client=None):
        self._mcp_client = mcp_client
        self._files: dict[str, str] = {VIRTUAL_PATH: "", GUIDELINES_PATH: ""}
        self._original_files: dict[str, str] = {VIRTUAL_PATH: "", GUIDELINES_PATH: ""}
        self._histories: dict[str, List[str]] = {VIRTUAL_PATH: [], GUIDELINES_PATH: []}
        self._scorecard: str = ""
        self._score: str = ""
        self._iteration: int = 0
        self._hypothesis: str = ""
        self._dry_run: bool = False
        self._last_version_id: Optional[str] = None
        self._code_file_path: Optional[str] = None
        self._last_edit_error: Optional[str] = None
        self._parent_version_id: Optional[str] = None

    # ------------------------------------------------------------------
    # MCP tools (called from Lua via call_plexus_tool)
    # ------------------------------------------------------------------

    def _normalize_yaml_content(self, yaml_content: str, source: str) -> str:
        """
        Canonicalize score YAML before exposing it to the editor agent.

        This keeps the optimizer edit surface deterministic by converting
        escaped one-line prompt blobs into canonical block-scalar YAML.
        """
        try:
            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.width = 4096
            yaml.indent(mapping=2, sequence=4, offset=2)
            yaml.map_indent = 2
            yaml.sequence_indent = 4
            yaml.sequence_dash_offset = 2

            parsed = yaml.load(yaml_content or "")
            if not isinstance(parsed, dict):
                raise ValueError("Score configuration must be a YAML mapping.")

            def _rewrite_multiline_strings(value):
                if isinstance(value, dict):
                    for key in list(value.keys()):
                        value[key] = _rewrite_multiline_strings(value[key])
                    return value
                if isinstance(value, list):
                    for idx in range(len(value)):
                        value[idx] = _rewrite_multiline_strings(value[idx])
                    return value
                if isinstance(value, str) and "\n" in value:
                    return LiteralScalarString(value)
                return value

            shadow_ids = normalize_shadow_invalid_feedback_item_ids(
                parsed.get(OPTIMIZER_SHADOW_INVALID_FIELD)
            )
            if shadow_ids:
                parsed[OPTIMIZER_SHADOW_INVALID_FIELD] = shadow_ids
            else:
                parsed.pop(OPTIMIZER_SHADOW_INVALID_FIELD, None)
            for key in ("external_id", "externalId"):
                if key in parsed and parsed[key] is not None:
                    parsed[key] = str(parsed[key])

            normalized = _rewrite_multiline_strings(parsed)
            rendered = StringIO()
            yaml.dump(normalized, rendered)
            return rendered.getvalue()
        except Exception as exc:
            raise ValueError(f"Failed to normalize score YAML from {source}: {exc}") from exc

    def _parse_yaml_for_semantic_compare(self, yaml_content: str) -> Any:
        yaml = YAML(typ="safe")
        parsed = yaml.load(yaml_content or "")
        if isinstance(parsed, dict):
            shadow_ids = normalize_shadow_invalid_feedback_item_ids(
                parsed.get(OPTIMIZER_SHADOW_INVALID_FIELD)
            )
            if shadow_ids:
                parsed[OPTIMIZER_SHADOW_INVALID_FIELD] = shadow_ids
            else:
                parsed.pop(OPTIMIZER_SHADOW_INVALID_FIELD, None)
        return parsed

    def _yaml_semantically_equal(self, left: str, right: str) -> bool:
        try:
            return (
                self._parse_yaml_for_semantic_compare(left)
                == self._parse_yaml_for_semantic_compare(right)
            )
        except Exception:
            return False

    def setup(self, arguments: dict) -> dict:
        """
        Set up the score editor for a new iteration.

        Accepts optional yaml_content parameter. When provided by Lua (which already
        has the YAML from plexus_score_pull + File.read), content is loaded directly
        without any async API call — bypassing nested event loop issues in the Tactus
        agent context. When yaml_content is omitted, falls back to _load_content_from_api().
        """
        self._files = {VIRTUAL_PATH: "", GUIDELINES_PATH: ""}
        self._original_files = {VIRTUAL_PATH: "", GUIDELINES_PATH: ""}
        self._histories = {VIRTUAL_PATH: [], GUIDELINES_PATH: []}
        self._code_file_path = None
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
        self._last_edit_error = None
        self._parent_version_id = arguments.get("parent_version_id") or arguments.get("parentVersionId") or None

        code_file_path = arguments.get("code_file_path", "")
        if code_file_path:
            self._code_file_path = code_file_path

        yaml_content = arguments.get("yaml_content", "")
        guidelines_content = str(arguments.get("guidelines_content", "") or "")
        if yaml_content:
            try:
                normalized_yaml = self._normalize_yaml_content(yaml_content, "score_editor_setup yaml_content")
            except ValueError as exc:
                return {
                    "success": False,
                    "message": str(exc),
                    "path": VIRTUAL_PATH,
                    "code_file_path": self._code_file_path,
                }

            # Direct injection from Lua — no async call needed
            self._files[VIRTUAL_PATH] = normalized_yaml
            self._original_files[VIRTUAL_PATH] = normalized_yaml
            self._histories[VIRTUAL_PATH] = []
            self._files[GUIDELINES_PATH] = guidelines_content
            self._original_files[GUIDELINES_PATH] = guidelines_content
            self._histories[GUIDELINES_PATH] = []
            logger.info(
                "ScoreEditorToolset: loaded %d normalized chars directly for iteration %d, score=%s, dry_run=%s",
                len(normalized_yaml), self._iteration, self._score, self._dry_run,
            )
        else:
            # Fallback: try async API load (may fail in nested event loop contexts)
            load_error = self._load_content_from_api()
            if load_error:
                logger.warning("ScoreEditorToolset: eager load failed: %s", load_error)
            logger.info(
                "ScoreEditorToolset: initialized for iteration %d, score=%s, dry_run=%s, file=%s",
                self._iteration, self._score, self._dry_run, self._code_file_path,
            )

        return {
            "success": True,
            "message": (
                f"Score editor ready for iteration {self._iteration}. "
                f"Content: {len(self._files[VIRTUAL_PATH])} chars. "
                f"Code file: {self._code_file_path or 'not set'}."
            ),
            "path": VIRTUAL_PATH,
            "code_file_path": self._code_file_path,
        }

    def get_result(self, arguments: dict) -> dict:
        """Return the version ID created by the last submit_score_version call."""
        if self._last_version_id:
            return {"success": True, "version_id": self._last_version_id}
        return {
            "success": False,
            "version_id": None,
            "message": "No score version has been submitted yet",
        }

    def get_content(self, arguments: dict) -> dict:
        """Return the current virtual file content for Lua to build system messages."""
        modified_files = [
            path
            for path in ALLOWED_PATHS
            if self._files[path] != self._original_files[path]
        ]
        return {
            "success": True,
            "file_content": self._files[VIRTUAL_PATH],
            "guidelines_content": self._files[GUIDELINES_PATH],
            "files": {
                VIRTUAL_PATH: self._files[VIRTUAL_PATH],
                GUIDELINES_PATH: self._files[GUIDELINES_PATH],
            },
            "original": self._original_files[VIRTUAL_PATH],
            "original_guidelines": self._original_files[GUIDELINES_PATH],
            "modified": bool(modified_files),
            "modified_files": modified_files,
            "length": len(self._files[VIRTUAL_PATH]),
        }

    # ------------------------------------------------------------------
    # Helpers for str_replace error recovery
    # ------------------------------------------------------------------

    def _try_fix_indentation(self, content: str, old_str: str, new_str: str):
        """
        Try to fix indentation mismatches between old_str and file content.

        LLMs commonly strip leading whitespace when reproducing multi-line text.
        If old_str's lines match content lines after stripping, re-indent both
        old_str and new_str with the correct indentation and return the fixed pair.

        Returns (fixed_old, fixed_new) or None if no fix found.
        """
        old_lines = old_str.split("\n")
        if not old_lines or not old_lines[0].strip():
            return None

        # Find the first non-empty line of old_str in content (stripped match)
        first_stripped = old_lines[0].strip()
        if not first_stripped:
            return None

        content_lines = content.split("\n")
        for ci, cline in enumerate(content_lines):
            if cline.strip() == first_stripped:
                # Found the first line — determine the indent
                indent = cline[:len(cline) - len(cline.lstrip())]

                # Check if ALL old_str lines match content lines with this indent
                matched = True
                for oi, oline in enumerate(old_lines):
                    content_idx = ci + oi
                    if content_idx >= len(content_lines):
                        matched = False
                        break
                    # Empty lines (blank) should match blank content lines
                    if oline.strip() == "" and content_lines[content_idx].strip() == "":
                        continue
                    # Non-empty lines: stripped version must match
                    if oline.strip() != content_lines[content_idx].strip():
                        matched = False
                        break

                if matched:
                    # Re-indent old_str and new_str to match the file
                    fixed_old_lines = []
                    for oi, oline in enumerate(old_lines):
                        if oline.strip() == "":
                            fixed_old_lines.append(content_lines[ci + oi])
                        else:
                            fixed_old_lines.append(indent + oline.lstrip())
                    fixed_old = "\n".join(fixed_old_lines)

                    # Verify the fixed old_str actually matches
                    if fixed_old not in content:
                        continue  # Try next match location

                    # Apply the same indent to new_str
                    new_lines = new_str.split("\n")
                    fixed_new_lines = []
                    for nline in new_lines:
                        if nline.strip() == "":
                            fixed_new_lines.append(nline)
                        else:
                            fixed_new_lines.append(indent + nline.lstrip())
                    fixed_new = "\n".join(fixed_new_lines)

                    return (fixed_old, fixed_new)

        return None

    def _build_match_error(self, content: str, old_str: str, path: str) -> str:
        """
        Build a diagnostic error message showing the agent what went wrong.

        Instead of a generic "no match found", show the actual content near
        where the agent was trying to edit so it can see the indentation
        or other differences.
        """
        first_line = old_str.split("\n")[0]
        first_stripped = first_line.strip()
        hint_lines = []

        # Try to find the first line (stripped) in content
        content_lines = content.split("\n")
        match_line = None
        for i, cline in enumerate(content_lines):
            if first_stripped and first_stripped in cline:
                match_line = i
                break

        if match_line is not None:
            # Show the actual content around the match
            start = max(0, match_line - 1)
            end = min(len(content_lines), match_line + len(old_str.split("\n")) + 2)
            actual_lines = content_lines[start:end]
            actual_snippet = "\n".join(f"  {start + j + 1}| {ln}" for j, ln in enumerate(actual_lines))

            # Detect the specific problem
            actual_first = content_lines[match_line]
            old_first = old_str.split("\n")[0]
            if actual_first.strip() == old_first.strip() and actual_first != old_first:
                indent_actual = len(actual_first) - len(actual_first.lstrip())
                indent_old = len(old_first) - len(old_first.lstrip())
                hint_lines.append(
                    f"INDENTATION MISMATCH: Your old_str lines have "
                    f"{indent_old}-space indent but the file uses "
                    f"{indent_actual}-space indent."
                )
                hint_lines.append(
                    "Copy the text exactly as shown below, preserving "
                    "the leading spaces on each line."
                )
            else:
                hint_lines.append(
                    "The text you provided doesn't exactly match the file content. "
                    "Compare your old_str with the actual file content below."
                )

            hint_lines.append(f"\nActual file content near your match target:\n{actual_snippet}")
        else:
            # First line not found at all
            hint_lines.append(
                f"Error: No match found for old_str in {path}. "
                "The text you provided does not appear in the editable file. "
                "It may have come from another part of your prompt context "
                "(e.g. guidelines, RCA analysis, or instructions) rather than "
                f"from {path} itself."
            )
            hint_lines.append(
                f"\nUse str_replace_editor(command='view', path='{path}') "
                "to re-read the editable file and copy the exact text from there."
            )

        return "\n".join(hint_lines)

    # ------------------------------------------------------------------
    # Agent tools (called by code_editor agent)
    # ------------------------------------------------------------------

    def str_replace_editor(self, arguments: dict) -> str:
        """
        Standard Claude text editor tool — virtual in-memory implementation.

        Commands: view, str_replace, insert, undo_edit, create
        Path: must be one of the virtual editor files.

        On the first view command, automatically loads the current champion score
        YAML from the Plexus API (avoids passing large content through LLM args).
        """
        command = arguments.get("command", "")
        path = arguments.get("path", "")

        if path not in ALLOWED_PATHS:
            return (
                "Error: Unsupported file path for editor.\n"
                f"Requested path: {path}\n"
                f"Allowed paths: {', '.join(ALLOWED_PATHS)}"
            )

        content = self._files[path]
        history = self._histories[path]

        if command == "view":
            # Clear any pending edit error — viewing the file is the recovery action
            self._last_edit_error = None

            # Auto-load content on first view if not yet populated
            if not content:
                load_error = self._load_content_from_api()
                if load_error:
                    return f"Error loading score configuration: {load_error}"
                content = self._files[path]

            view_range = arguments.get("view_range")
            lines = content.split("\n")
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
                err = "Error: old_str is required for str_replace command"
                self._last_edit_error = err
                return err
            # Normalize escape sequences — LLM tool args often contain literal
            # backslash-escapes instead of the actual characters.  \n is the most
            # common, but \' and \t also occur in Lua code edits.
            for esc, char in [("\\n", "\n"), ("\\t", "\t"), ("\\'", "'"), ('\\"', '"')]:
                old_str = old_str.replace(esc, char)
                new_str = new_str.replace(esc, char)
            if old_str not in content:
                # Try auto-fixing indentation mismatches.
                # LLMs commonly strip leading whitespace when copying multi-line
                # text from context. Detect this and re-indent old_str/new_str.
                fixed = self._try_fix_indentation(content, old_str, new_str)
                if fixed:
                    old_str, new_str = fixed
                    logger.info(
                        "str_replace: auto-fixed indentation mismatch "
                        "(added %d-space indent)",
                        len(old_str.split("\n")[0]) - len(old_str.split("\n")[0].lstrip()),
                    )
                else:
                    # Build a diagnostic error message the agent can act on
                    err = self._build_match_error(content, old_str, path)
                    self._last_edit_error = err
                    return err
            count = content.count(old_str)
            if count > 1:
                err = (
                    f"Error: old_str matches {count} locations in the file. "
                    "Provide more surrounding context to make it unique."
                )
                self._last_edit_error = err
                return err
            history.append(content)
            self._files[path] = content.replace(old_str, new_str, 1)
            self._last_edit_error = None
            return self._format_edit_result("str_replace", path)

        elif command == "insert":
            insert_line = arguments.get("insert_line")
            new_str = arguments.get("new_str", "")
            if insert_line is None:
                err = "Error: insert_line is required for insert command"
                self._last_edit_error = err
                return err
            if not new_str:
                err = "Error: new_str is required for insert command"
                self._last_edit_error = err
                return err
            history.append(content)
            lines = content.split("\n")
            insert_at = max(0, min(int(insert_line), len(lines)))
            insert_lines = new_str.split("\n")
            lines[insert_at:insert_at] = insert_lines
            self._files[path] = "\n".join(lines)
            self._last_edit_error = None
            return self._format_edit_result("insert", path)

        elif command == "undo_edit":
            if not history:
                err = "Error: No previous edit to undo"
                self._last_edit_error = err
                return err
            self._files[path] = history.pop()
            self._last_edit_error = None
            return "Last edit undone.\n\n" + self._format_validation(path)

        elif command == "create":
            new_str = arguments.get("new_str", arguments.get("file_text", ""))
            history.append(content)
            self._files[path] = new_str
            self._last_edit_error = None
            return self._format_edit_result("create", path)

        else:
            return (
                f"Error: Unknown command '{command}'. "
                "Supported: view, str_replace, insert, undo_edit, create"
            )

    async def submit_score_version(self, arguments: dict) -> dict:
        """
        Validate and submit the current virtual file as a new score version.

        The score must be modified via str_replace_editor before calling this.
        Rejects if the content is unchanged from the original to prevent accidentally
        submitting an unmodified or stale score version.
        """
        version_note = arguments.get("version_note") or None

        # Guard 1: last edit call returned an error — agent must fix it before submitting
        if self._last_edit_error:
            return {
                "success": False,
                "error": (
                    "Cannot submit: the most recent str_replace_editor call returned an error:\n\n"
                    f"  {self._last_edit_error}\n\n"
                    "Fix the edit error first:\n"
                    "  • Call str_replace_editor(command='view', path='score_config.yaml') to re-read "
                    "the current file.\n"
                    "  • Copy the exact text you want to replace (including all whitespace/indentation).\n"
                    "  • Retry str_replace_editor with an exactly-matching old_str.\n"
                    "  • Then call submit_score_version again."
                ),
            }

        if not self._files[VIRTUAL_PATH]:
            return {
                "success": False,
                "error": (
                    "Cannot submit: no score code is loaded. "
                    "Call str_replace_editor(command='view', path='score_config.yaml') "
                    "to load the file, make your edit, then call submit_score_version."
                ),
            }

        code_changed = self._files[VIRTUAL_PATH] != self._original_files[VIRTUAL_PATH]
        guidelines_changed = self._files[GUIDELINES_PATH] != self._original_files[GUIDELINES_PATH]
        if not code_changed and not guidelines_changed:
            return {
                "success": False,
                "error": (
                    "Cannot submit: score code and guidelines are unchanged from the original baseline. "
                    "Use str_replace_editor to make a meaningful change, then call submit_score_version again."
                ),
            }

        # Guard 2b: reject YAML-equivalent changes, such as comments, key order, or block-scalar rendering only.
        if (
            code_changed
            and self._original_files[VIRTUAL_PATH]
            and self._yaml_semantically_equal(self._files[VIRTUAL_PATH], self._original_files[VIRTUAL_PATH])
            and not guidelines_changed
        ):
            return {
                "success": False,
                "error": (
                    "Cannot submit: the score configuration is semantically unchanged from the original "
                    "champion version. Formatting, comments, or key order do not count as optimizer evidence. "
                    "Use str_replace_editor to make a meaningful rubric or score-logic change, then call "
                    "submit_score_version again."
                ),
            }

        # Fix common YAML issues before validation
        # external_id / externalId must be a string, not an integer
        import re
        self._files[VIRTUAL_PATH] = re.sub(
            r'^(external_id:\s*)(\d+)\s*$',
            r'\1"\2"',
            self._files[VIRTUAL_PATH],
            flags=re.MULTILINE,
        )
        self._files[VIRTUAL_PATH] = re.sub(
            r'^(externalId:\s*)(\d+)\s*$',
            r'\1"\2"',
            self._files[VIRTUAL_PATH],
            flags=re.MULTILINE,
        )

        # Guard 3: validate YAML syntax — agent must fix structure errors before submitting
        errors = self._get_validation_errors()
        if errors:
            error_text = "\n".join(f"  - {e}" for e in errors)
            return {
                "success": False,
                "error": (
                    "Cannot submit: YAML validation failed. Fix these errors with "
                    f"str_replace_editor, then call submit_score_version again:\n{error_text}"
                ),
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

        # Call plexus.score.update directly (no MCP round-trip needed)
        try:
            import os, sys

            _mcp_dir = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "MCP")
            )
            if os.path.isdir(_mcp_dir) and _mcp_dir not in sys.path:
                sys.path.insert(0, _mcp_dir)

            from tools.tactus_runtime.execute import _default_score_update  # type: ignore

            payload = _default_score_update({
                "scorecard_identifier": self._scorecard,
                "score_identifier": self._score,
                "code": self._files[VIRTUAL_PATH],
                "guidelines": self._files[GUIDELINES_PATH],
                "parent_version_id": self._parent_version_id,
                "version_note": note,
            })

            if payload.get("success") is False:
                err = payload.get("error") or "plexus.score.update failed"
                validation_errors = payload.get("validation_errors")
                if isinstance(validation_errors, list) and validation_errors:
                    preview = "\n".join(str(e) for e in validation_errors[:10])[:1500]
                    err = f"{err}\n\nValidation errors:\n{preview}"
                return {"success": False, "error": err}

            version_id = payload.get("version_id")
            if version_id:
                self._last_version_id = version_id
                return {
                    "success": True,
                    "version_id": version_id,
                    "changed_fields": [
                        field
                        for field, changed in (
                            ("code", code_changed),
                            ("guidelines", guidelines_changed),
                        )
                        if changed
                    ],
                    "message": f"Score version created: {version_id}",
                }

            return {
                "success": False,
                "error": f"plexus.score.update returned unexpected format: {payload}",
            }

        except Exception as exc:
            logger.error("ScoreEditorToolset.submit_score_version error: %s", exc)
            return {"success": False, "error": f"Failed to create score version: {exc}"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_content_from_api(self) -> Optional[str]:
        """Load the current champion score YAML directly from the Plexus API.

        Uses plexus.score.pull which returns the YAML content in-memory without
        requiring the legacy plexus_score_pull MCP tool.
        Returns None on success, or an error string on failure.
        """
        if not self._scorecard or not self._score:
            return "Score editor not set up — call score_editor_setup first"

        import os
        import sys
        import time as _time

        _mcp_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "MCP")
        )
        if os.path.isdir(_mcp_dir) and _mcp_dir not in sys.path:
            sys.path.insert(0, _mcp_dir)

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                from tools.tactus_runtime.execute import _default_score_pull  # type: ignore

                pull_data = _default_score_pull({
                    "scorecard_identifier": self._scorecard,
                    "score_identifier": self._score,
                })

                if not pull_data.get("success"):
                    raise RuntimeError(f"score.pull failed: {pull_data}")

                yaml_content = pull_data.get("yaml_content") or ""
                if not yaml_content:
                    raise RuntimeError(f"score.pull returned empty yaml_content: {pull_data}")

                normalized_code = self._normalize_yaml_content(yaml_content, "plexus.score.pull")

                self._files[VIRTUAL_PATH] = normalized_code
                self._original_files[VIRTUAL_PATH] = normalized_code
                self._histories[VIRTUAL_PATH] = []
                guidelines_content = str(pull_data.get("guidelines") or "")
                self._files[GUIDELINES_PATH] = guidelines_content
                self._original_files[GUIDELINES_PATH] = guidelines_content
                self._histories[GUIDELINES_PATH] = []
                logger.info(
                    "ScoreEditorToolset: auto-loaded %d yaml chars and %d guideline chars for %s/%s via plexus.score.pull",
                    len(normalized_code), len(guidelines_content), self._scorecard, self._score,
                )
                return None

            except Exception as exc:
                if attempt < max_retries:
                    logger.warning(
                        "ScoreEditorToolset._load_content_from_api attempt %d/%d failed: %s, retrying...",
                        attempt, max_retries, exc,
                    )
                    _time.sleep(attempt * 3)
                else:
                    logger.error(
                        "ScoreEditorToolset._load_content_from_api failed after %d attempts: %s",
                        max_retries, exc,
                    )
                    return str(exc)

    def _format_edit_result(self, operation: str, path: str) -> str:
        validation = self._format_validation(path)
        return f"Edit applied ({operation}) on {path}.\n\n{validation}"

    def _format_validation(self, path: str = VIRTUAL_PATH) -> str:
        if path != VIRTUAL_PATH:
            return "No syntax validation is required for guidelines markdown."
        try:
            from plexus.linting.yaml_linter import YamlLinter
            linter = YamlLinter()
            result = linter.lint(self._files[VIRTUAL_PATH])
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
        errors: List[str] = []
        try:
            from plexus.linting.yaml_linter import YamlLinter
            result = YamlLinter().lint(self._files[VIRTUAL_PATH])
            errors.extend([
                f"{m.title}" + (f" (line {m.line})" if m.line else "") + f": {m.message}"
                for m in result.messages
                if m.level == "error"
            ])
        except Exception:
            pass

        errors.extend(self._get_structural_validation_errors())
        return errors

    def _get_structural_validation_errors(self) -> List[str]:
        """
        Reject optimizer-generated score YAML that uses Classifier as a free-form
        extractor. This catches the pseudo-extractor pattern before expensive
        evaluation starts.
        """
        try:
            yaml = YAML(typ="safe")
            parsed = yaml.load(self._files[VIRTUAL_PATH])
        except Exception:
            return []

        if not isinstance(parsed, dict):
            return []

        graph = parsed.get("graph")
        if not isinstance(graph, list):
            return []

        errors: List[str] = []
        for idx, node in enumerate(graph, start=1):
            if not isinstance(node, dict):
                continue

            node_class = str(node.get("class") or "").strip()
            if node_class != "Classifier":
                continue

            valid_classes = node.get("valid_classes")
            if not isinstance(valid_classes, list) or not valid_classes:
                continue

            normalized_valid_classes = {
                str(value).strip().lower()
                for value in valid_classes
                if str(value).strip()
            }
            if not normalized_valid_classes:
                continue

            extraction_like_classes = normalized_valid_classes.issubset(
                EXTRACTION_LIKE_VALID_CLASSES
            )
            if not extraction_like_classes:
                continue

            node_name = str(node.get("name") or f"graph[{idx}]")
            prompt_text = " ".join(
                str(node.get(field) or "")
                for field in ("system_message", "user_message")
            ).lower()
            looks_like_extractor = (
                node_name.lower().startswith("extract")
                or any(hint in prompt_text for hint in EXTRACTION_PROMPT_HINTS)
            )
            if not looks_like_extractor:
                continue

            errors.append(
                f"Structural validation failed for node '{node_name}': "
                "Classifier cannot be used for free-form extraction. "
                "Use class: Extractor, map output.extracted_text to a named state field, "
                f"and reserve valid_classes for closed-set labels. Found valid_classes={valid_classes!r}."
            )

        return errors

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

    def _extract_json_payload(self, mcp_response: Any) -> Optional[dict]:
        """
        Extract the JSON dict payload from MCP tool responses.

        MCP tools commonly return either:
          - direct dict payloads, or
          - {"content": [{"type": "text", "text": "{...json...}"}]}
        """
        import json

        if isinstance(mcp_response, dict):
            # Direct payload already
            if "success" in mcp_response:
                return mcp_response

            # MCP envelope
            for item in mcp_response.get("content", []):
                if not isinstance(item, dict) or item.get("type") != "text":
                    continue
                text = item.get("text", "")
                if not text:
                    continue
                try:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        return data
                except (ValueError, TypeError):
                    continue

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
                "Pass yaml_content (the current score YAML string) to load content directly "
                "without an API call. Call this before dispatching the code_editor agent."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "scorecard_identifier": {"type": "string", "description": "Scorecard name, key, or ID"},
                    "score_identifier": {"type": "string", "description": "Score name, key, or ID"},
                    "yaml_content": {"type": "string", "description": "Current score YAML content (direct injection, bypasses async API load)"},
                    "guidelines_content": {"type": "string", "description": "Current score guidelines markdown content"},
                    "code_file_path": {"type": "string", "description": "Path to the score YAML file on disk (metadata only)"},
                    "parent_version_id": {"type": "string", "description": "ScoreVersion ID this edit is based on; persisted as parentVersionId on submit"},
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
            description="Return the version ID created by the last submit_score_version call.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=instance.get_result,
        ))

        transport.register_tool(MCPToolInfo(
            name="score_editor_get_content",
            description="Return the current virtual file content and modification status.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=instance.get_content,
        ))

        transport.register_tool(MCPToolInfo(
            name="str_replace_editor",
            description=(
                "Edit a text file using view, str_replace, insert, undo_edit, or create commands. "
                f"Available files: '{VIRTUAL_PATH}', '{GUIDELINES_PATH}'."
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
                        "description": f"Path to the file (use '{VIRTUAL_PATH}' or '{GUIDELINES_PATH}')",
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
            name="submit_score_version",
            description=(
                "Submit the current virtual score file as a new score version. "
                "Validates YAML syntax first. Errors if the file is unchanged."
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
            handler=instance.submit_score_version,
        ))

        logger.info(
            "ScoreEditorToolset: registered score_editor_setup, score_editor_get_result, "
            "score_editor_get_content, str_replace_editor, submit_score_version on MCP transport"
        )
        return instance
