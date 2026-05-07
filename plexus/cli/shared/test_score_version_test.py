import asyncio

from plexus.cli.shared import score_version_test as svc


class _FakeClient:
    def _resolve_account_id(self):
        return "acct-1"


class _FakeScorecard:
    scores = [{"id": "score-1", "name": "Agent Misrepresentation"}]

    def build_dependency_graph(self, score_names):
        return {}, {"Agent Misrepresentation": "node-1"}


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
