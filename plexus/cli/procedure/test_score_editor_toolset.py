import pytest


class FakeMCPClient:
    def __init__(self, response):
        self._response = response

    async def call_tool(self, tool_name, arguments):
        assert tool_name == "plexus_score_update"
        assert "code" in arguments
        return self._response


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
