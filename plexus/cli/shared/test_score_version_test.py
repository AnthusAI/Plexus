import asyncio

from plexus.cli.shared import score_version_test as svc


class _FakeClient:
    def _resolve_account_id(self):
        return "acct-1"


class _FakeScorecard:
    scores = [{"id": "score-1", "name": "Agent Misrepresentation"}]

    def build_dependency_graph(self, score_names):
        return {}, {"Agent Misrepresentation": "node-1"}


class _FakeScoreResult:
    value = "No"
    explanation = "Test explanation"

    def __init__(self, trace=None, metadata=None):
        self.metadata = metadata or {}
        if trace is not None:
            self.metadata["trace"] = trace


def test_score_version_test_explicit_items_override_samples(monkeypatch):
    monkeypatch.setattr(
        svc,
        "_resolve_scorecard_and_score",
        lambda **_: (
            "scorecard-1",
            "score-1",
            {"id": "score-1", "name": "Agent Misrepresentation", "championVersionId": "champ-1"},
        ),
    )
    monkeypatch.setattr(svc, "resolve_item_identifier", lambda _client, identifier, _account_id: identifier)
    monkeypatch.setattr(svc, "load_scorecard_from_api", lambda **_: _FakeScorecard())

    async def _fake_predict(**kwargs):
        return {
            "item_id": kwargs["item_id"],
            "passed": True,
            "score": {"name": "Agent Misrepresentation", "value": "No", "explanation": "", "cost": {}},
        }

    monkeypatch.setattr(svc, "_predict_single_item", _fake_predict)

    result = asyncio.run(
        svc.run_score_version_test(
            client=_FakeClient(),
            scorecard_identifier="sc",
            score_identifier="score",
            samples=3,
            item_identifiers=["item-x", "item-y"],
            days=90,
        )
    )

    assert result["passed"] is True
    assert result["requested_samples"] == 3
    assert result["selected_samples"] == 2
    assert result["selection_source"] == "explicit_items"


def test_score_version_test_fails_on_selection_shortfall(monkeypatch):
    monkeypatch.setattr(
        svc,
        "_resolve_scorecard_and_score",
        lambda **_: (
            "scorecard-1",
            "score-1",
            {"id": "score-1", "name": "Agent Misrepresentation", "championVersionId": "champ-1"},
        ),
    )
    monkeypatch.setattr(
        svc,
        "_sample_recent_feedback_item_ids",
        lambda **_: ["item-only-one"],
    )
    monkeypatch.setattr(
        svc,
        "_sample_recent_scorecard_item_ids",
        lambda **_: [],
    )

    result = asyncio.run(
        svc.run_score_version_test(
            client=_FakeClient(),
            scorecard_identifier="sc",
            score_identifier="score",
            samples=3,
            item_identifiers=None,
            days=90,
        )
    )

    assert result["passed"] is False
    assert result["failure_code"] == "selection_shortfall"
    assert result["selected_samples"] == 1
    assert result["predictions"] == []

def test_score_version_test_fails_on_unresolved_prompt_placeholders(monkeypatch):
    trace = {
        "node_results": [
            {
                "node_name": "classifier",
                "input": {
                    "prompt_diagnostics": {
                        "unresolved_placeholders": [
                            {
                                "placeholder": "{xcc: disposition}",
                                "node_name": "classifier",
                                "role": "system",
                                "excerpt": "Disposition: {xcc: disposition}",
                                "metadata_keys": ["disposition"],
                            }
                        ]
                    }
                },
                "output": {"classification": "No"},
            }
        ]
    }

    class FakeClient(_FakeClient):
        def execute(self, _query, _variables):
            return {
                "getItem": {
                    "id": "item-1",
                    "text": "transcript",
                    "metadata": '{"disposition":"Set Outside 48"}',
                }
            }

    class FakeScorecard(_FakeScorecard):
        async def score_entire_text(self, **kwargs):
            assert kwargs["metadata"][svc.CAPTURE_RENDERED_MESSAGES_METADATA_KEY] is True
            return {"node-1": _FakeScoreResult(trace=trace)}

    result = asyncio.run(
        svc._predict_single_item(
            client=FakeClient(),
            scorecard_instance=FakeScorecard(),
            resolved_score_name="Agent Misrepresentation",
            target_result_id="node-1",
            score_name_for_output="Agent Misrepresentation",
            item_id="item-1",
        )
    )

    assert result["passed"] is False
    assert result["failure_code"] == "unresolved_prompt_placeholders"
    assert result["prompt_diagnostics"]["unresolved_placeholders"][0]["placeholder"] == "{xcc: disposition}"
    assert result["score_input"]["metadata"] == {"disposition": "Set Outside 48"}
    assert result["score_input"]["metadata_keys"] == ["disposition"]
    assert result["score_input"]["text_excerpt"] == "transcript"


def test_score_version_test_uses_fallback_scorecard_items(monkeypatch):
    monkeypatch.setattr(
        svc,
        "_resolve_scorecard_and_score",
        lambda **_: (
            "target-scorecard-id",
            "score-1",
            {"id": "score-1", "name": "Agent Misrepresentation", "championVersionId": "champ-1"},
        ),
    )
    monkeypatch.setattr(
        svc,
        "_sample_recent_feedback_item_ids",
        lambda **_: [],
    )

    calls = []

    def _sample_recent_scorecard_item_ids(**kwargs):
        calls.append(kwargs["scorecard_id"])
        if kwargs["scorecard_id"] == "target-scorecard-id":
            return []
        if kwargs["scorecard_id"] == "source-scorecard-id":
            return ["item-a", "item-b"]
        return []

    monkeypatch.setattr(
        svc,
        "_sample_recent_scorecard_item_ids",
        _sample_recent_scorecard_item_ids,
    )
    monkeypatch.setattr(
        svc,
        "resolve_scorecard_identifier",
        lambda _client, identifier: "source-scorecard-id" if identifier == "source-scorecard" else None,
    )
    monkeypatch.setattr(svc, "load_scorecard_from_api", lambda **_: _FakeScorecard())

    async def _fake_predict(**kwargs):
        return {
            "item_id": kwargs["item_id"],
            "passed": True,
            "score": {"name": "Agent Misrepresentation", "value": "No", "explanation": "", "cost": {}},
        }

    monkeypatch.setattr(svc, "_predict_single_item", _fake_predict)

    result = asyncio.run(
        svc.run_score_version_test(
            client=_FakeClient(),
            scorecard_identifier="target-scorecard",
            score_identifier="score",
            samples=2,
            item_identifiers=None,
            fallback_scorecard_identifier="source-scorecard",
            days=90,
        )
    )

    assert result["passed"] is True
    assert result["selected_samples"] == 2
    assert result["selection_source"] == "fallback_scorecard_items"
    assert calls == ["target-scorecard-id", "source-scorecard-id"]


def test_score_version_test_uses_placeholder_failure_code_for_batch(monkeypatch):
    monkeypatch.setattr(
        svc,
        "_resolve_scorecard_and_score",
        lambda **_: (
            "scorecard-1",
            "score-1",
            {"id": "score-1", "name": "Agent Misrepresentation", "championVersionId": "champ-1"},
        ),
    )
    monkeypatch.setattr(svc, "resolve_item_identifier", lambda _client, identifier, _account_id: identifier)
    monkeypatch.setattr(svc, "load_scorecard_from_api", lambda **_: _FakeScorecard())

    async def _fake_predict(**kwargs):
        return {
            "item_id": kwargs["item_id"],
            "passed": False,
            "failure_code": "unresolved_prompt_placeholders",
            "message": "Rendered LLM prompt still contains unresolved template placeholders.",
            "score": {"name": "Agent Misrepresentation", "value": "No", "explanation": "", "cost": {}},
        }

    monkeypatch.setattr(svc, "_predict_single_item", _fake_predict)

    result = asyncio.run(
        svc.run_score_version_test(
            client=_FakeClient(),
            scorecard_identifier="sc",
            score_identifier="score",
            samples=1,
            item_identifiers=["item-x"],
            days=90,
        )
    )

    assert result["passed"] is False
    assert result["failure_code"] == "unresolved_prompt_placeholders"
