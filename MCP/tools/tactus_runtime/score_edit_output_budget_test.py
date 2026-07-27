"""Behavior coverage for complete score-edit output budgeting."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from . import execute

pytestmark = pytest.mark.unit


def test_given_large_score_when_editing_then_complete_configuration_has_output_budget(
    tmp_path, monkeypatch
) -> None:
    """A targeted edit must not be constrained by the legacy 5K-token ceiling."""
    base_code = (
        "name: Large Score\n"
        "class: LangGraphScore\n"
        "enabled: false\n"
        "prompt: |\n"
        + "  Preserve this complete configuration line.\n" * 3_000
    )
    candidate_code = base_code.replace("enabled: false", "enabled: true", 1)
    base_guidelines = "# Guidelines\n" + "Preserve this policy.\n" * 500
    observed: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.api_key = api_key

    class FakeToolset:
        def setup(self, args: dict) -> dict:
            assert args["yaml_content"] == base_code
            assert args["guidelines_content"] == base_guidelines
            return {"success": True}

        def str_replace_editor(self, args: dict) -> str:
            assert args["new_str"] == candidate_code
            return "ok"

        async def submit_score_version(self, _args: dict) -> dict:
            return {
                "success": True,
                "version_id": "sv-large",
                "parent_version_id": "sv-parent",
                "changed_fields": ["code"],
            }

    def fake_create_score_edit_response(**kwargs):
        observed.update(kwargs)
        return (
            {
                "code": candidate_code,
                "guidelines": base_guidelines,
                "note": "Enable the score without changing the rest of the configuration.",
                "summary": "Enabled the score.",
            },
            True,
        )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setitem(
        sys.modules,
        "plexus.cli.procedure.tactus_adapters.score_editor_toolset",
        SimpleNamespace(
            GUIDELINES_PATH="score_guidelines.md",
            ScoreEditorToolset=FakeToolset,
            VIRTUAL_PATH="score_config.yaml",
        ),
    )
    monkeypatch.setattr(execute, "_create_score_edit_response", fake_create_score_edit_response)
    monkeypatch.setattr(
        execute,
        "_default_score_pull",
        lambda args: (
            {
                "yaml_content": candidate_code,
                "guidelines": base_guidelines,
                "version_id": "sv-large",
                "parent_version_id": "sv-parent",
            }
            if str(args.get("version_id") or "") == "sv-large"
            else {
                "yaml_content": base_code,
                "guidelines": base_guidelines,
                "version_id": "sv-parent",
                "parent_version_id": "sv-grandparent",
            }
        ),
    )
    monkeypatch.setattr(
        execute,
        "_default_score_test",
        lambda _args: {"success": True, "passed": True},
    )

    result_path = tmp_path / "result.json"
    execute._run_score_edit_job(
        {
            "scorecard_identifier": "card",
            "score_identifier": "score",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "instruction": "Enable the score and preserve all other YAML.",
        },
        str(result_path),
    )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    complete_payload_bytes = len(
        json.dumps(
            {
                "code": candidate_code,
                "guidelines": base_guidelines,
                "note": "",
                "summary": "",
            },
            ensure_ascii=False,
        ).encode("utf-8")
    )
    assert payload["success"] is True
    assert observed["prompt"].find(base_code) >= 0
    assert observed["max_output_tokens"] >= complete_payload_bytes + 4_096
