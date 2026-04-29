from __future__ import annotations

import json

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
except ImportError:  # pragma: no cover - compatibility only
    from langchain.schema import AIMessage, HumanMessage, SystemMessage, ToolMessage

from plexus.cli.procedure.logging_utils import (
    capture_llm_context_for_agent,
    capture_tactus_dspy_context_for_agent,
)


def test_capture_llm_context_disabled_writes_no_files(monkeypatch, tmp_path):
    monkeypatch.delenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR", raising=False)

    result = capture_llm_context_for_agent(
        "Test Agent",
        [SystemMessage(content="System prompt")],
        call_site="unit_test",
    )

    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_capture_llm_context_writes_markdown_and_json(monkeypatch, tmp_path):
    monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR", str(tmp_path))
    long_content = "line\n" * 80
    messages = [
        SystemMessage(content="System prompt"),
        HumanMessage(content=long_content),
        AIMessage(
            content="Calling a tool",
            tool_calls=[{"name": "lookup_policy", "args": {"topic": "rubric"}, "id": "call-1"}],
        ),
        ToolMessage(content="Tool result body", tool_call_id="call-1"),
    ]

    result = capture_llm_context_for_agent(
        "Optimizer Worker",
        messages,
        context="round 1",
        call_site="sop_worker_round",
        tools=["plexus_rubric_memory_evidence_pack", "stop_procedure"],
    )

    assert result is not None
    markdown_path = tmp_path / result["markdown_path"].split("/")[-1]
    json_path = tmp_path / result["json_path"].split("/")[-1]
    assert markdown_path.exists()
    assert json_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["agent_name"] == "Optimizer Worker"
    assert payload["call_site"] == "sop_worker_round"
    assert payload["message_count"] == 4
    assert payload["messages"][1]["content"] == long_content
    assert payload["messages"][2]["tool_calls"][0]["name"] == "lookup_policy"
    assert payload["messages"][3]["tool_call_id"] == "call-1"
    assert "plexus_rubric_memory_evidence_pack" in payload["tools"]
    assert long_content in markdown


def test_capture_llm_context_filter_includes_matching_call(monkeypatch, tmp_path):
    monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR", str(tmp_path))
    monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_FILTER", "worker,sme_gate")

    included = capture_llm_context_for_agent(
        "CODING_ASSISTANT (Worker)",
        [HumanMessage(content="Worker context")],
        call_site="sop_worker_round",
    )
    skipped = capture_llm_context_for_agent(
        "Report Writer",
        [HumanMessage(content="Report context")],
        call_site="final_summary",
    )

    assert included is not None
    assert skipped is None
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert len(list(tmp_path.glob("*.md"))) == 1


def test_capture_llm_context_preserves_rubric_memory_briefing(monkeypatch, tmp_path):
    monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR", str(tmp_path))
    briefing = (
        "=== RUBRIC MEMORY BRIEFING (official rubric + cited corpus evidence) ===\n"
        "- `corpus:01:abc` `evidence` `prefix`: Information Accuracy policy memory.\n"
        "=== END RUBRIC MEMORY BRIEFING ==="
    )

    capture_llm_context_for_agent(
        "CODING_ASSISTANT (Worker)",
        [
            SystemMessage(content="Worker system prompt"),
            HumanMessage(content=f"Planning context\n\n{briefing}"),
        ],
        context="round 1",
        call_site="sop_worker_round",
        tools=["plexus_rubric_memory_evidence_pack"],
    )

    markdown = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")
    payload = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))

    assert "=== RUBRIC MEMORY BRIEFING" in markdown
    assert "corpus:01:abc" in markdown
    assert "Information Accuracy policy memory" in payload["messages"][1]["content"]


def test_capture_tactus_dspy_context_serializes_prompt_context(monkeypatch, tmp_path):
    monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR", str(tmp_path))
    prompt_context = {
        "system_prompt": "Optimizer system prompt",
        "history": [
            {
                "role": "user",
                "content": (
                    "Planning context\n\n"
                    "=== RUBRIC MEMORY BRIEFING ===\n"
                    "`support:01:abc` prefix evidence\n"
                    "=== END RUBRIC MEMORY BRIEFING ==="
                ),
            },
            {"role": "assistant", "content": "Previous answer"},
        ],
        "user_message": "Generate the next hypothesis.",
        "tools": ["plexus_rubric_memory_evidence_pack"],
    }

    result = capture_tactus_dspy_context_for_agent(
        "Tactus DSPy Agent: hypothesis_planner",
        prompt_context,
        turn_count=1,
        call_site="tactus_dspy_agent_non_streaming",
    )

    assert result is not None
    payload = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    markdown = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")

    assert payload["agent_name"] == "Tactus DSPy Agent: hypothesis_planner"
    assert payload["call_site"] == "tactus_dspy_agent_non_streaming"
    assert payload["context"] == "turn 1 | Generate the next hypothesis."
    assert [message["role"] for message in payload["messages"]] == [
        "SYSTEM",
        "USER",
        "ASSISTANT",
        "USER",
    ]
    assert "=== RUBRIC MEMORY BRIEFING" in markdown
    assert "plexus_rubric_memory_evidence_pack" in payload["tools"]


def test_capture_tactus_dspy_context_filter_can_match_user_message_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR", str(tmp_path))
    monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_FILTER", "cycle_lab_report")

    included = capture_tactus_dspy_context_for_agent(
        "Tactus DSPy Agent: report_writer",
        {
            "system_prompt": "Report writer system prompt",
            "user_message": (
                "=== OPTIMIZER REPORT PHASE: cycle_lab_report ===\n"
                "Write the lab report."
            ),
        },
        turn_count=2,
        call_site="tactus_dspy_agent_non_streaming",
    )
    skipped = capture_tactus_dspy_context_for_agent(
        "Tactus DSPy Agent: report_writer",
        {
            "system_prompt": "Report writer system prompt",
            "user_message": (
                "=== OPTIMIZER REPORT PHASE: cycle_sme_agenda ===\n"
                "Write the SME agenda."
            ),
        },
        turn_count=3,
        call_site="tactus_dspy_agent_non_streaming",
    )

    assert included is not None
    assert skipped is None
    assert len(list(tmp_path.glob("*.json"))) == 1
    payload = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert "cycle_lab_report" in payload["context"]


def test_capture_markdown_escapes_nul_bytes_but_json_preserves_content(monkeypatch, tmp_path):
    monkeypatch.setenv("PLEXUS_CAPTURE_LLM_CONTEXT_DIR", str(tmp_path))

    capture_llm_context_for_agent(
        "Binary-ish Agent",
        [HumanMessage(content="before\x00after")],
        call_site="unit_test",
    )

    markdown_bytes = next(tmp_path.glob("*.md")).read_bytes()
    payload = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))

    assert b"\x00" not in markdown_bytes
    assert "before\\0after" in markdown_bytes.decode("utf-8")
    assert payload["messages"][0]["content"] == "before\x00after"
