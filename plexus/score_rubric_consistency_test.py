import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from plexus.score_rubric_consistency import (
    ScoreRubricConsistencyRequest,
    ScoreRubricConsistencyService,
    merge_consistency_result_into_parameters,
)


def test_score_rubric_consistency_service_returns_compact_payload():
    def invoke(prompt: str, model: str) -> str:
        assert "Score code/configuration" in prompt
        assert model == "test-model"
        return json.dumps(
            {
                "status": "potential_conflict",
                "paragraph": (
                    "The rubric says two missing dosages should fail, but the prompt allows "
                    "two missing current medications. This may make the score more permissive "
                    "than the rubric during evaluation."
                ),
            }
        )

    result = ScoreRubricConsistencyService(
        invoke_model=invoke,
        model="test-model",
    ).generate(
        ScoreRubricConsistencyRequest(
            scorecard_identifier="Scorecard",
            score_identifier="Medication Review: Dosage",
            score_version_id="version-1",
            rubric_text="Fail when two or more current meds lack dosage.",
            score_code="Pass when no more than two meds lack dosage.",
        )
    )

    assert result.status == "potential_conflict"
    assert result.score_version_id == "version-1"
    assert "more permissive than the rubric" in result.paragraph
    assert result.diagnostics["rubric_characters"] > 0


def test_merge_consistency_result_into_parameters_preserves_existing_fields():
    service = ScoreRubricConsistencyService(
        invoke_model=lambda _prompt, _model: json.dumps(
            {"status": "consistent", "paragraph": "The score and rubric match."}
        )
    )
    result = service.generate(
        ScoreRubricConsistencyRequest(
            scorecard_identifier="Scorecard",
            score_identifier="Score",
            score_version_id="version-1",
            rubric_text="Rubric",
            score_code="Code",
        )
    )

    merged = merge_consistency_result_into_parameters(
        json.dumps({"days": 90}),
        result,
    )

    assert merged["days"] == 90
    assert merged["score_rubric_consistency_check"]["status"] == "consistent"
    assert merged["score_rubric_consistency_check"]["score_version_id"] == "version-1"


def test_score_rubric_consistency_retries_invalid_json_once():
    calls = []

    def invoke(prompt: str, _model: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            return ""
        return json.dumps(
            {"status": "consistent", "paragraph": "The score code follows the rubric."}
        )

    result = ScoreRubricConsistencyService(invoke_model=invoke).generate(
        ScoreRubricConsistencyRequest(
            scorecard_identifier="Scorecard",
            score_identifier="Score",
            score_version_id="version-1",
            rubric_text="Rubric",
            score_code="Code",
        )
    )

    assert result.status == "consistent"
    assert len(calls) == 2
    assert "prior response was not valid JSON" in calls[1]


class _SemanticReport:
    def __init__(self, fail_commits=()):
        self.value = None
        self.commits = []
        self.fail_commits = set(fail_commits)

    def load_semantic_budget_ledger(self):
        return deepcopy(self.value)

    def persist_semantic_budget_ledger(self, value):
        number = len(self.commits) + 1
        self.commits.append(deepcopy(value))
        if number in self.fail_commits:
            raise RuntimeError(f"commit {number} failed")
        self.value = deepcopy(value)


def _budgeted_service(*, responses, report=None, token_count=20, max_input_tokens=2000):
    from plexus.optimization.semantic_authority import (
        SemanticBudgetCoordinator,
        semantic_budget_spec,
    )

    report = report or _SemanticReport()
    coordinator = SemanticBudgetCoordinator.start_or_resume(
        report_service=report, run_key="run-1", spec=semantic_budget_spec("1")
    )
    authority = coordinator.view(
        target_id="scorecard-1:score-1",
        call_site="score_rubric_consistency",
        max_attempts=2,
    )
    calls = []

    class _Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            assert any(
                entry["status"] == "reserved"
                and entry["plan"]["attempt"] == len(calls)
                for entry in report.value["entries"]
            )
            value = responses[len(calls) - 1]
            if isinstance(value, Exception):
                raise value
            return value

    service = ScoreRubricConsistencyService(
        semantic_authority=authority,
        openai_client_factory=lambda: SimpleNamespace(responses=_Responses()),
        token_counter=lambda _prompt, _model: token_count,
        max_input_tokens=max_input_tokens,
        max_output_tokens=10,
    )
    return service, coordinator, report, calls


def _request():
    return ScoreRubricConsistencyRequest(
        scorecard_identifier="Scorecard",
        score_identifier="Score",
        score_version_id="version-1",
        rubric_text="Rubric",
        score_code="Code",
    )


def _response(text, *, usage=True, request_id="req-1"):
    return SimpleNamespace(
        id=request_id,
        output_text=text,
        usage=(
            SimpleNamespace(
                input_tokens=20,
                output_tokens=5,
                input_tokens_details=SimpleNamespace(cached_tokens=2),
            )
            if usage else None
        ),
    )


def test_budgeted_consistency_reserves_before_exact_model_contact_and_settles_usage():
    service, coordinator, report, calls = _budgeted_service(responses=[
        _response(json.dumps({"status": "consistent", "paragraph": "Matches."}))
    ])
    result = service.generate(_request())

    assert result.status == "consistent"
    assert calls[0]["model"] == "gpt-5-mini-2025-08-07"
    assert calls[0]["max_output_tokens"] == 10
    assert coordinator.ledger.summary()["settled_count"] == 1
    assert [commit["entries"][-1]["status"] for commit in report.commits[1:]] == [
        "reserved", "settled"
    ]


def test_default_openai_client_disables_hidden_retries(monkeypatch):
    from plexus.optimization.semantic_authority import (
        SemanticBudgetCoordinator,
        semantic_budget_spec,
    )

    report = _SemanticReport()
    coordinator = SemanticBudgetCoordinator.start_or_resume(
        report_service=report, run_key="run-hidden-retries", spec=semantic_budget_spec("1")
    )
    captured = {}

    class _Responses:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return _response(json.dumps({"status": "consistent", "paragraph": "Matches."}))

    def openai_factory(**kwargs):
        captured["client"] = kwargs
        return SimpleNamespace(responses=_Responses())

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr("openai.OpenAI", openai_factory)
    service = ScoreRubricConsistencyService(
        semantic_authority=coordinator.view(
            target_id="card:score", call_site="score_rubric_consistency", max_attempts=2
        ),
        token_counter=lambda *_args: 20,
        max_input_tokens=2000,
        max_output_tokens=10,
    )

    assert service.generate(_request()).status == "consistent"
    assert captured["client"]["max_retries"] == 0
    assert captured["request"]["model"] == "gpt-5-mini-2025-08-07"


def test_invalid_json_repair_is_the_second_and_final_physical_attempt():
    service, coordinator, _report, calls = _budgeted_service(responses=[
        _response("not json", request_id="req-1"),
        _response(json.dumps({"status": "consistent", "paragraph": "Repaired."}), request_id="req-2"),
    ])
    assert service.generate(_request()).status == "consistent"
    assert len(calls) == 2
    assert coordinator.ledger.summary()["settled_count"] == 2


def test_input_overflow_and_initial_publication_failure_make_zero_provider_calls():
    from plexus.optimization.semantic_authority import SemanticAuthorityPublicationError

    overflow, _coordinator, _report, overflow_calls = _budgeted_service(
        responses=[], token_count=2001
    )
    with pytest.raises(ValueError, match="max_input_tokens"):
        overflow.generate(_request())
    assert overflow_calls == []

    report = _SemanticReport(fail_commits={2})
    blocked, _coordinator, _report, blocked_calls = _budgeted_service(
        responses=[], report=report
    )
    with pytest.raises(SemanticAuthorityPublicationError):
        blocked.generate(_request())
    assert blocked_calls == []


def test_unicode_heavy_exact_payload_byte_bound_rejects_before_contact():
    service, _coordinator, _report, calls = _budgeted_service(
        responses=[], token_count=10, max_input_tokens=2000
    )
    request = ScoreRubricConsistencyRequest(
        **{**_request().__dict__, "rubric_text": "😀" * 400}
    )
    with pytest.raises(ValueError, match="max_input_tokens"):
        service.generate(request)
    assert calls == []


def test_missing_usage_or_post_contact_persistence_failure_is_unknown_and_never_repairs():
    from plexus.optimization.semantic_authority import SemanticOutcomeUnknown

    missing, coordinator, _report, calls = _budgeted_service(responses=[
        _response("not json", usage=False)
    ])
    with pytest.raises(SemanticOutcomeUnknown):
        missing.generate(_request())
    assert len(calls) == 1
    assert coordinator.ledger.summary()["outcome_unknown_count"] == 1

    report = _SemanticReport(fail_commits={3, 4})
    failed, coordinator, _report, calls = _budgeted_service(responses=[
        _response(json.dumps({"status": "consistent", "paragraph": "Matches."}))
    ], report=report)
    with pytest.raises(SemanticOutcomeUnknown):
        failed.generate(_request())
    assert len(calls) == 1
    assert coordinator.ledger.summary()["held_usd"] != "0"

    oversized_usage = SimpleNamespace(
        id="req-too-large",
        output_text=json.dumps({"status": "consistent", "paragraph": "Matches."}),
        usage=SimpleNamespace(
            input_tokens=2001,
            output_tokens=1,
            input_tokens_details=SimpleNamespace(cached_tokens=0),
        ),
    )
    bounded, coordinator, _report, calls = _budgeted_service(responses=[oversized_usage])
    with pytest.raises(SemanticOutcomeUnknown):
        bounded.generate(_request())
    assert len(calls) == 1
    assert coordinator.ledger.summary()["outcome_unknown_count"] == 1


def test_report_resume_replays_direct_response_without_contact_or_double_charge():
    first, coordinator, report, calls = _budgeted_service(responses=[
        _response(json.dumps({"status": "consistent", "paragraph": "Matches."}))
    ])
    first.generate(_request())
    spent = coordinator.ledger.summary()["settled_usd"]

    resumed, resumed_coordinator, _report, replay_calls = _budgeted_service(
        responses=[], report=report
    )
    assert resumed.generate(_request()).status == "consistent"
    assert replay_calls == []
    assert resumed_coordinator.ledger.summary()["settled_usd"] == spent


def test_default_consistency_never_falls_back_to_unbudgeted_openai():
    with pytest.raises(RuntimeError, match="semantic budget authority"):
        ScoreRubricConsistencyService(token_counter=lambda *_: 1).generate(_request())
