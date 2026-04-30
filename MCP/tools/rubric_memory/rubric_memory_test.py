import json

import pytest

from rubric_memory.rubric_memory import (
    _coerce_citation_context,
    _coerce_json_object,
    _fetch_feedback_item_context,
    _fetch_score_result_context,
    _merge_context_value,
    register_rubric_memory_tools,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def execute(self, query, variables=None):
        self.calls.append((query, variables))
        key = variables["id"]
        return self.responses[key]


def test_fetch_score_result_context_hydrates_model_fields():
    client = FakeClient({
        "sr-1": {
            "getScoreResult": {
                "id": "sr-1",
                "value": "No",
                "explanation": "Dose missing.",
                "itemId": "item-1",
                "feedbackItemId": "fb-1",
                "scoreId": "score-1",
            }
        }
    })

    context = _fetch_score_result_context(client, "sr-1")

    assert context["score_result_id"] == "sr-1"
    assert context["score_id"] == "score-1"
    assert context["feedback_item_id"] == "fb-1"
    assert context["model_value"] == "No"
    assert context["model_explanation"] == "Dose missing."


def test_fetch_feedback_item_context_hydrates_transcript_and_feedback_fields():
    client = FakeClient({
        "fb-1": {
            "getFeedbackItem": {
                "id": "fb-1",
                "scoreId": "score-1",
                "scorecardId": "scorecard-1",
                "itemId": "item-1",
                "initialAnswerValue": "No",
                "finalAnswerValue": "Yes",
                "initialCommentValue": "initial",
                "finalCommentValue": "final",
                "editCommentValue": "reviewer edit",
                "item": {"id": "item-1", "text": "call transcript"},
            }
        }
    })

    context = _fetch_feedback_item_context(client, "fb-1")

    assert context["feedback_item_id"] == "fb-1"
    assert context["score_id"] == "score-1"
    assert context["transcript_text"] == "call transcript"
    assert context["feedback_value"] == "Yes"
    assert context["feedback_comment"] == "reviewer edit\nfinal\ninitial"


def test_merge_context_value_prefers_explicit_value():
    assert _merge_context_value("explicit", "fetched") == "explicit"
    assert _merge_context_value("", "fetched") == "fetched"


def test_coerce_json_object_accepts_dict_and_json_string():
    assert _coerce_json_object({"a": 1}, field_name="context") == {"a": 1}
    assert _coerce_json_object('{"a": 1}', field_name="context") == {"a": 1}


def test_coerce_citation_context_accepts_evidence_pack_wrapper_and_lua_arrays():
    context = _coerce_citation_context(
        {
            "success": True,
            "score_id": "score-1",
            "markdown_context": "context",
            "citation_index": {
                "2": {"id": "evidence:02", "kind": "corpus"},
                "1": {"id": "rubric:abc", "kind": "official_rubric"},
            },
            "machine_context": {"score_version_id": "version-1"},
            "diagnostics": {
                "1": {"kind": "prepared_corpus"},
            },
        },
        field_name="rubric_memory_context",
    )

    assert context == {
        "markdown_context": "context",
        "citation_index": [
            {"id": "rubric:abc", "kind": "official_rubric"},
            {"id": "evidence:02", "kind": "corpus"},
        ],
        "machine_context": {"score_version_id": "version-1"},
        "diagnostics": [{"kind": "prepared_corpus"}],
    }


def test_register_rubric_memory_tools_includes_sme_question_gate():
    class FakeServer:
        def __init__(self):
            self.tools = {}

        def tool(self):
            def decorator(func):
                self.tools[func.__name__] = func
                return func
            return decorator

    server = FakeServer()
    register_rubric_memory_tools(server)

    assert "plexus_rubric_memory_evidence_pack" in server.tools
    assert "plexus_rubric_memory_recent_entries" in server.tools
    assert "plexus_rubric_memory_sme_question_gate" in server.tools


@pytest.mark.asyncio
async def test_evidence_pack_tool_defaults_to_retrieval_only_context(monkeypatch):
    class FakeServer:
        def __init__(self):
            self.tools = {}

        def tool(self):
            def decorator(func):
                self.tools[func.__name__] = func
                return func
            return decorator

    class FakeCitation:
        def model_dump(self, mode="json"):
            return {"id": "evidence:01:test", "kind": "corpus_evidence"}

    class FakeContext:
        markdown_context = "retrieval context"
        citation_index = [FakeCitation()]
        machine_context = {"context_kind": "retrieval_only"}
        diagnostics = [{"kind": "query_plan"}]

    class FakeProvider:
        def __init__(self, api_client):
            self.api_client = api_client

        async def retrieve_for_score_item(self, **kwargs):
            assert kwargs["score_id"] == "score-1"
            return FakeContext()

        async def generate_for_score_item(self, **_kwargs):
            pytest.fail("default evidence-pack MCP call must not run synthesis")

    import shared.utils
    import plexus.rubric_memory

    monkeypatch.setattr(shared.utils, "create_dashboard_client", object)
    monkeypatch.setattr(
        plexus.rubric_memory,
        "RubricMemoryContextProvider",
        FakeProvider,
    )

    server = FakeServer()
    register_rubric_memory_tools(server)

    payload = json.loads(
        await server.tools["plexus_rubric_memory_evidence_pack"](
            scorecard_identifier="Scorecard A",
            score_identifier="Medication Review: Dosage",
            score_id="score-1",
        )
    )

    assert payload["success"] is True
    assert payload["synthesized"] is False
    assert payload["markdown_context"] == "retrieval context"
    assert payload["machine_context"]["context_kind"] == "retrieval_only"


@pytest.mark.asyncio
async def test_recent_entries_tool_returns_recent_briefing_context(monkeypatch):
    class FakeServer:
        def __init__(self):
            self.tools = {}

        def tool(self):
            def decorator(func):
                self.tools[func.__name__] = func
                return func
            return decorator

    class FakeCitation:
        def model_dump(self, mode="json"):
            return {"id": "evidence:01:recent", "kind": "corpus_evidence"}

    class FakeContext:
        markdown_context = "recent rubric memory"
        citation_index = [FakeCitation()]
        machine_context = {"context_kind": "recent_briefing"}
        diagnostics = [{"kind": "recent_rubric_memory"}]

    class FakeProvider:
        def __init__(self, api_client):
            self.api_client = api_client

        async def retrieve_recent(self, **kwargs):
            assert kwargs["score_id"] == "score-1"
            assert kwargs["days"] == 30
            assert kwargs["query"] == "recent SME update"
            return FakeContext()

    import shared.utils
    import plexus.rubric_memory

    monkeypatch.setattr(shared.utils, "create_dashboard_client", object)
    monkeypatch.setattr(
        plexus.rubric_memory,
        "RubricMemoryRecentBriefingProvider",
        FakeProvider,
    )

    server = FakeServer()
    register_rubric_memory_tools(server)

    payload = json.loads(
        await server.tools["plexus_rubric_memory_recent_entries"](
            scorecard_identifier="Scorecard A",
            score_identifier="Medication Review: Dosage",
            score_id="score-1",
            query="recent SME update",
            days=30,
        )
    )

    assert payload["success"] is True
    assert payload["markdown_context"] == "recent rubric memory"
    assert payload["machine_context"]["context_kind"] == "recent_briefing"
