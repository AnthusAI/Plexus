import importlib.util
from pathlib import Path

import pytest


class FakeMCPClient:
    def __init__(self, response):
        self._response = response

    async def call_tool(self, tool_name, arguments):
        assert tool_name in {"plexus_score_update", "plexus_score_pull"}
        if tool_name == "plexus_score_update":
            assert "code" in arguments
        return self._response


RAW_MULTILINE_YAML = (
    'name: "Example Score"\n'
    'system_message: "Line one\\nLine two\\nLine three"\n'
    'user_message: "Question one\\nQuestion two"\n'
    'externalId: "12345"\n'
)


def load_score_editor_toolset_class():
    module_path = Path(__file__).parent / "tactus_adapters" / "score_editor_toolset.py"
    spec = importlib.util.spec_from_file_location("score_editor_toolset_test_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.ScoreEditorToolset


@pytest.mark.asyncio
async def test_submit_score_version_surfaces_validation_errors_from_envelope():
    ScoreEditorToolset = load_score_editor_toolset_class()

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


def test_setup_normalizes_multiline_yaml_for_editor_surface():
    ScoreEditorToolset = load_score_editor_toolset_class()

    toolset = ScoreEditorToolset()

    result = toolset.setup(
        {
            "scorecard_identifier": "sc-1",
            "score_identifier": "score-1",
            "yaml_content": RAW_MULTILINE_YAML,
        }
    )

    assert result["success"] is True
    assert "system_message: |" in toolset._content
    assert "user_message: |" in toolset._content
    assert '"Line one\\nLine two\\nLine three"' not in toolset._content
    assert toolset._content == toolset._original


def test_setup_returns_explicit_error_for_invalid_yaml():
    ScoreEditorToolset = load_score_editor_toolset_class()

    toolset = ScoreEditorToolset()

    result = toolset.setup(
        {
            "scorecard_identifier": "sc-1",
            "score_identifier": "score-1",
            "yaml_content": "name: [unterminated\n",
        }
    )

    assert result["success"] is False
    assert "Failed to normalize score YAML" in result["error"]
    assert toolset.get_content({})["success"] is False
    assert "Failed to normalize score YAML" in toolset.get_content({})["error"]


def test_load_content_from_api_normalizes_yaml(tmp_path):
    ScoreEditorToolset = load_score_editor_toolset_class()

    yaml_path = tmp_path / "score.yaml"
    yaml_path.write_text(RAW_MULTILINE_YAML, encoding="utf-8")

    mcp_response = {
        "content": [
            {
                "type": "text",
                "text": (
                    "{\n"
                    '  "success": true,\n'
                    f'  "codeFilePath": "{yaml_path}"\n'
                    "}\n"
                ),
            }
        ]
    }

    toolset = ScoreEditorToolset(mcp_client=FakeMCPClient(mcp_response))
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"

    error = toolset._load_content_from_api()

    assert error is None
    assert "system_message: |" in toolset._content
    assert "user_message: |" in toolset._content
    assert toolset._content == toolset._original


@pytest.mark.asyncio
async def test_submit_score_version_accepts_normalized_yaml_content():
    ScoreEditorToolset = load_score_editor_toolset_class()

    mcp_response = {
        "content": [
            {
                "type": "text",
                "text": (
                    "{\n"
                    '  "success": true,\n'
                    '  "newVersionId": "ver-123"\n'
                    "}\n"
                ),
            }
        ]
    }

    toolset = ScoreEditorToolset(mcp_client=FakeMCPClient(mcp_response))
    setup_result = toolset.setup(
        {
            "scorecard_identifier": "sc-1",
            "score_identifier": "score-1",
            "yaml_content": RAW_MULTILINE_YAML,
        }
    )
    assert setup_result["success"] is True

    toolset._content = toolset._content.replace("Line three", "Line three updated")

    result = await toolset.submit_score_version({"version_note": "normalize prompts"})

    assert result["success"] is True
    assert result["version_id"] == "ver-123"
