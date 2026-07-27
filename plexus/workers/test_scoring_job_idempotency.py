import pytest

from plexus.workers.scoring_job import (
    ScoringJobError,
    _claim_scoring_job,
    _existing_score_result_response,
    _find_existing_score_result,
    score_result_id_for_job,
)


class FakeClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def execute(self, query, variables):
        self.calls.append((query, variables))
        return {"listScoreResults": {"items": self.items}}


def _lookup(client):
    return _find_existing_score_result(
        client,
        scoring_job_id="job-1",
        item_id="item-1",
        scorecard_id="scorecard-1",
        score_id="score-1",
        account_id="account-1",
    )


def test_idempotency_lookup_returns_exactly_one_matching_result():
    existing = {
        "id": "result-1",
        "value": "yes",
        "itemId": "item-1",
        "scorecardId": "scorecard-1",
        "scoreId": "score-1",
        "accountId": "account-1",
    }
    client = FakeClient([existing])

    assert _lookup(client) == existing
    assert client.calls[0][1] == {"filter": {"scoringJobId": {"eq": "job-1"}}}


def test_idempotency_lookup_rejects_a_job_key_for_a_different_resource():
    client = FakeClient(
        [{"id": "other", "itemId": "other-item", "scorecardId": "scorecard-1", "scoreId": "score-1", "accountId": "account-1"}]
    )

    with pytest.raises(ScoringJobError, match="already bound to a different resource") as error:
        _lookup(client)

    assert error.value.status_code == 409
    assert error.value.reason_code == "scoring_job_scope_conflict"


def test_idempotency_lookup_rejects_existing_duplicate_results():
    duplicate = {"itemId": "item-1", "scorecardId": "scorecard-1", "scoreId": "score-1", "accountId": "account-1"}

    with pytest.raises(ScoringJobError, match="Multiple persisted results") as error:
        _lookup(FakeClient([{**duplicate, "id": "result-1"}, {**duplicate, "id": "result-2"}]))

    assert error.value.status_code == 409
    assert error.value.reason_code == "duplicate_scoring_job_results"


def test_idempotent_response_is_explicit_and_parses_metadata():
    response = _existing_score_result_response(
        {"id": "result-1", "value": "yes", "explanation": "already scored", "metadata": '{"source":"persisted"}'},
        scoring_job_id="job-1",
        item_id="item-1",
        scorecard_name="scorecard",
        score_name="score",
    )

    assert response["score_result_id"] == "result-1"
    assert response["idempotent_replay"] is True
    assert response["metadata"] == {"source": "persisted"}


def test_scoring_job_result_id_is_stable_and_scoped_to_the_target():
    kwargs = {
        "scoring_job_id": "job-1",
        "item_id": "item-1",
        "scorecard_id": "scorecard-1",
        "score_id": "score-1",
        "account_id": "account-1",
    }

    assert score_result_id_for_job(**kwargs) == score_result_id_for_job(**kwargs)
    assert score_result_id_for_job(**kwargs) != score_result_id_for_job(
        **{**kwargs, "item_id": "item-2"}
    )


def test_scoring_job_claim_uses_durable_scope_and_returns_state():
    client = FakeClient([])
    client.execute = lambda query, variables: {"claimScoringJob": {"state": "CLAIMED", "scoreResultId": "result-1"}}

    claim = _claim_scoring_job(
        client,
        scoring_job_id="job-1",
        item_id="item-1",
        scorecard_id="scorecard-1",
        score_id="score-1",
        account_id="account-1",
        score_result_id="result-1",
    )

    assert claim == {"state": "CLAIMED", "scoreResultId": "result-1"}
