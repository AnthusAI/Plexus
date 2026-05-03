import pytest
import json


class FakeMCPClient:
    def __init__(self, response):
        self._response = response

    async def call_tool(self, tool_name, arguments):
        assert tool_name == "plexus_score_update"
        assert "code" in arguments
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


def test_load_content_from_api_normalizes_yaml_before_exposing_it(tmp_path):
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    raw_yaml = (
        "name: Test Score\n"
        "class: LangGraphScore\n"
        'system_message: "First line\\nSecond line\\n"\n'
        'user_message: "Review this call\\n{{text}}\\n"\n'
    )
    code_path = tmp_path / "score.yaml"
    code_path.write_text(raw_yaml, encoding="utf-8")

    mcp_response = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "success": True,
                        "codeFilePath": str(code_path),
                    }
                ),
            }
        ]
    }

    toolset = ScoreEditorToolset(mcp_client=FakePullMCPClient(mcp_response))
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"

    load_error = toolset._load_content_from_api()

    assert load_error is None
    assert toolset._code_file_path == str(code_path)
    assert "system_message: |" in toolset._content
    assert "user_message: |" in toolset._content
    assert toolset._content == toolset._original


def test_load_content_from_api_fails_clearly_on_invalid_yaml(tmp_path):
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    code_path = tmp_path / "invalid-score.yaml"
    code_path.write_text("name: [unterminated\n", encoding="utf-8")

    mcp_response = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "success": True,
                        "codeFilePath": str(code_path),
                    }
                ),
            }
        ]
    }

    toolset = ScoreEditorToolset(mcp_client=FakePullMCPClient(mcp_response))
    toolset._scorecard = "sc-1"
    toolset._score = "score-1"

    load_error = toolset._load_content_from_api()

    assert load_error is not None
    assert "Failed to normalize score YAML" in load_error


@pytest.mark.asyncio
async def test_submit_score_version_rejects_classifier_as_extractor_candidate():
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    toolset = ScoreEditorToolset(mcp_client=FakeMCPClient({"success": True, "version_id": "v-1"}))
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
async def test_submit_score_version_allows_extractor_then_classifier_pattern():
    from plexus.cli.procedure.tactus_adapters.score_editor_toolset import ScoreEditorToolset

    toolset = ScoreEditorToolset(mcp_client=FakeMCPClient({"success": True, "version_id": "v-2"}))
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
