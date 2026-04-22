import pytest


class FakeMCPClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def call_tool(self, tool_name, arguments):
        assert tool_name == "plexus_score_update"
        assert "code" in arguments
        self.calls.append((tool_name, arguments))
        return self._response


def _make_toolset(monkeypatch, response=None):
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    client = FakeMCPClient(response or {"success": True, "version_id": "version-123"})
    toolset = ScoreEditorToolset(mcp_client=client)
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"
    toolset._iteration = 1
    toolset._hypothesis = "h"
    toolset._dry_run = False
    monkeypatch.setattr(toolset, "_format_validation", lambda: "✓ YAML syntax valid")
    monkeypatch.setattr(toolset, "_get_validation_errors", lambda: [])
    return toolset, client


def test_replace_lines_replaces_inclusive_line_range_and_undo_restores(monkeypatch):
    toolset, _client = _make_toolset(monkeypatch)
    toolset._original = "one\ntwo\nthree\n"
    toolset._content = toolset._original

    result = toolset.str_replace_editor({
        "command": "replace_lines",
        "path": "score_config.yaml",
        "start_line": 2,
        "end_line": 3,
        "new_str": "updated two\nupdated three",
    })

    assert "Edit applied (replace_lines)." in result
    assert toolset._content == "one\nupdated two\nupdated three\n"

    undo_result = toolset.str_replace_editor({
        "command": "undo_edit",
        "path": "score_config.yaml",
    })

    assert "Last edit undone." in undo_result
    assert toolset._content == toolset._original


def test_replace_lines_invalid_range_returns_actionable_error(monkeypatch):
    toolset, _client = _make_toolset(monkeypatch)
    toolset._original = "one\ntwo\n"
    toolset._content = toolset._original

    result = toolset.str_replace_editor({
        "command": "replace_lines",
        "path": "score_config.yaml",
        "start_line": 2,
        "end_line": 4,
        "new_str": "replacement",
    })

    assert "Invalid line range" in result
    assert "view with a bounded view_range" in result


@pytest.mark.asyncio
async def test_replace_lines_then_submit_score_version_works(monkeypatch):
    toolset, client = _make_toolset(monkeypatch, {"success": True, "version_id": "version-456"})
    toolset._original = "name: test\nprompt: |\n  old line\n"
    toolset._content = toolset._original

    edit_result = toolset.str_replace_editor({
        "command": "replace_lines",
        "path": "score_config.yaml",
        "start_line": 2,
        "end_line": 3,
        "new_str": "prompt: |\n  updated line",
    })

    assert "Edit applied (replace_lines)." in edit_result

    result = await toolset.submit_score_version({"version_note": "line-based edit"})

    assert result["success"] is True
    assert result["version_id"] == "version-456"
    assert client.calls[-1][1]["code"] == "name: test\nprompt: |\n  updated line\n"


@pytest.mark.asyncio
async def test_submit_score_version_surfaces_validation_errors_from_envelope():
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    mcp_response = {
        "content": [
            {
                "type": "text",
                "text": (
                    '{\n'
                    '  "success": false,\n'
                    '  "error": "YAML validation failed",\n'
                    '  "validation_errors": ["Schema Validation Failed: foo", "Another error"]\n'
                    "}\n"
                ),
            }
        ]
    }

    toolset = ScoreEditorToolset(mcp_client=FakeMCPClient(mcp_response))
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"
    toolset._iteration = 1
    toolset._hypothesis = "h"
    toolset._dry_run = False
    toolset._original = "a: 1\n"
    toolset._content = "a: 2\n"  # modified

    result = await toolset.submit_score_version({"version_note": "n"})

    assert result["success"] is False
    assert "YAML validation failed" in result["error"]
    assert "Validation errors:" in result["error"]
    assert "Schema Validation Failed" in result["error"]
