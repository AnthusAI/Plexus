import os
import sys
import pytest
import json

# Ensure the MCP directory is importable for execute module patching
_mcp_dir = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "MCP")
)
if os.path.isdir(_mcp_dir) and _mcp_dir not in sys.path:
    sys.path.insert(0, _mcp_dir)


class FakeMCPClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def call_tool(self, tool_name, arguments):
        assert tool_name == "plexus_score_update"
        assert "code" in arguments
        self.calls.append((tool_name, arguments))
        return self._response


class FakePullMCPClient:
    def __init__(self, payload):
        self._payload = payload

    async def call_tool(self, tool_name, arguments):
        assert tool_name == "plexus_score_pull"
        return self._payload


VALID_TWO_STAGE_EXTRACTOR_YAML = """\
name: Test Score
key: test-score
class: LangGraphScore
model_provider: ChatOpenAI
model_name: gpt-5.4-nano
graph:
  - name: extract_dosage_evidence
    class: Extractor
    trust_model_output: true
    system_message: |-
      Extract only dosage evidence from the transcript.
    user_message: |-
      {{text}}
    edge:
      node: check_dosage_verification
      output:
        dosage_evidence: extracted_text
  - name: check_dosage_verification
    class: Classifier
    valid_classes:
      - Yes
      - No
    system_message: |-
      Use the extracted evidence to make the final decision.
    user_message: |-
      Transcript:
      {{text}}

      Extracted dosage evidence:
      {{dosage_evidence}}

      Respond in exactly two lines.
      Line 1: short explanation
      Line 2: Yes or No
output:
  value: classification
  explanation: explanation
"""


INVALID_PSEUDO_EXTRACTOR_YAML = """\
name: Test Score
key: test-score
class: LangGraphScore
model_provider: ChatOpenAI
model_name: gpt-5.4-nano
graph:
  - name: extract_dosage_evidence
    class: Classifier
    valid_classes:
      - Extracted
    system_message: |-
      Extract only dosage evidence from the transcript.
    user_message: |-
      {{text}}

      Respond in exactly two lines.
      Line 1: extracted dosage evidence
      Line 2: Extracted
    edge:
      node: check_dosage_verification
      output:
        dosage_evidence: explanation
  - name: check_dosage_verification
    class: Classifier
    valid_classes:
      - Yes
      - No
    user_message: |-
      {{dosage_evidence}}

      Line 1: short explanation
      Line 2: Yes or No
output:
  value: classification
  explanation: explanation
"""


@pytest.mark.asyncio
async def test_submit_score_version_surfaces_validation_errors_from_envelope(monkeypatch):
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset
    import tools.tactus_runtime.execute as _exec  # type: ignore

    monkeypatch.setattr(
        _exec,
        "_default_score_update",
        lambda args: {
            "success": False,
            "error": "YAML validation failed",
            "validation_errors": ["Schema Validation Failed: foo", "Another error"],
        },
    )

    toolset = ScoreEditorToolset()
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


@pytest.mark.asyncio
async def test_submit_score_version_rejects_semantically_unchanged_yaml():
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    mcp_client = FakeMCPClient({"success": True, "version_id": "should-not-create"})
    toolset = ScoreEditorToolset(mcp_client=mcp_client)
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"
    toolset._iteration = 1
    toolset._hypothesis = "h"
    toolset._dry_run = False
    toolset._original = (
        "name: Test Score\n"
        "key: test-score\n"
        "class: LangGraphScore\n"
        "model_name: gpt-5-mini\n"
    )
    toolset._content = (
        "# harmless formatting-only candidate\n"
        "key: test-score\n"
        "class: LangGraphScore\n"
        "model_name: gpt-5-mini\n"
        "name: Test Score\n"
    )

    result = await toolset.submit_score_version({"version_note": "format only"})

    assert result["success"] is False
    assert "semantically unchanged" in result["error"]
    assert mcp_client.calls == []


def test_setup_normalizes_direct_yaml_content_to_block_scalars():
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    raw_yaml = (
        "name: Test Score\n"
        "class: LangGraphScore\n"
        'system_message: "Line one\\n\\nLine two\\n"\n'
        'user_message: "Review this call\\n\\n{{text}}\\n"\n'
    )

    toolset = ScoreEditorToolset()
    result = toolset.setup(
        {
            "scorecard_identifier": "sc-1",
            "score_identifier": "score-1",
            "yaml_content": raw_yaml,
        }
    )

    assert result["success"] is True
    content = toolset.get_content({})["file_content"]
    assert "system_message: |" in content
    assert "user_message: |" in content
    assert "\\n\\n" not in content
    assert toolset._content == toolset._original


def test_setup_normalizes_numeric_external_id_to_string():
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    raw_yaml = (
        "name: Test Score\n"
        "external_id: 48381\n"
        "class: LangGraphScore\n"
        "graph: []\n"
    )

    toolset = ScoreEditorToolset()
    result = toolset.setup(
        {
            "scorecard_identifier": "sc-1",
            "score_identifier": "score-1",
            "yaml_content": raw_yaml,
        }
    )

    assert result["success"] is True
    content = toolset.get_content({})["file_content"]
    assert "external_id: '48381'" in content or 'external_id: "48381"' in content
    assert "external_id: 48381" not in content


def test_setup_fails_fast_when_direct_yaml_is_invalid():
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    toolset = ScoreEditorToolset()
    result = toolset.setup(
        {
            "scorecard_identifier": "sc-1",
            "score_identifier": "score-1",
            "yaml_content": "name: [unterminated\n",
        }
    )

    assert result["success"] is False
    assert "Failed to normalize score YAML" in result["message"]


def test_load_content_from_api_normalizes_yaml_before_exposing_it(monkeypatch):
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    raw_yaml = (
        "name: Test Score\n"
        "class: LangGraphScore\n"
        'system_message: "First line\\nSecond line\\n"\n'
        'user_message: "Review this call\\n{{text}}\\n"\n'
    )

    import tools.tactus_runtime.execute as _exec  # type: ignore
    monkeypatch.setattr(
        _exec,
        "_default_score_pull",
        lambda args: {"success": True, "yaml_content": raw_yaml, "guidelines": ""},
    )

    toolset = ScoreEditorToolset()
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"

    load_error = toolset._load_content_from_api()

    assert load_error is None
    assert "system_message: |" in toolset._content
    assert "user_message: |" in toolset._content
    assert toolset._content == toolset._original


def test_load_content_from_api_fails_clearly_on_invalid_yaml(monkeypatch):
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    import tools.tactus_runtime.execute as _exec  # type: ignore
    monkeypatch.setattr(
        _exec,
        "_default_score_pull",
        lambda args: {"success": True, "yaml_content": "name: [unterminated\n", "guidelines": ""},
    )

    toolset = ScoreEditorToolset()
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"

    load_error = toolset._load_content_from_api()

    assert load_error is not None
    assert "Failed to normalize score YAML" in load_error


@pytest.mark.asyncio
async def test_submit_score_version_rejects_classifier_as_extractor_candidate():
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    toolset = ScoreEditorToolset()
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"
    toolset._iteration = 1
    toolset._hypothesis = "structural"
    toolset._dry_run = False
    toolset._original = VALID_TWO_STAGE_EXTRACTOR_YAML
    toolset._content = INVALID_PSEUDO_EXTRACTOR_YAML

    result = await toolset.submit_score_version({"version_note": "reject pseudo extractor"})

    assert result["success"] is False
    assert "Structural validation failed" in result["error"]
    assert "Classifier cannot be used for free-form extraction" in result["error"]
    assert "class: Extractor" in result["error"]


@pytest.mark.asyncio
async def test_submit_score_version_allows_extractor_then_classifier_pattern(monkeypatch):
    import tools.tactus_runtime.execute as _exec  # type: ignore
    monkeypatch.setattr(
        _exec,
        "_default_score_update",
        lambda args: {"success": True, "version_id": "v-2"},
    )

    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    toolset = ScoreEditorToolset()
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"
    toolset._iteration = 1
    toolset._hypothesis = "structural"
    toolset._dry_run = False
    toolset._original = "name: baseline\nkey: baseline\nclass: LangGraphScore\n"
    toolset._content = VALID_TWO_STAGE_EXTRACTOR_YAML

    result = await toolset.submit_score_version({"version_note": "valid extractor chain"})

    assert result["success"] is True
    assert result["version_id"] == "v-2"
