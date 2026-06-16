from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from plexus.workers.scoring_api import app, log_auth_configuration
from plexus.workers.scoring_job import ScoringJobError


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_scoring_api_key(monkeypatch):
    monkeypatch.delenv("SCORING_API_KEY", raising=False)
    monkeypatch.delenv("SCORING_API_AUTH_REQUIRED", raising=False)


def test_score_endpoint_returns_result():
    expected = {
        "status": "success",
        "scoring_job_id": "job-1",
        "item_id": "item-1",
        "scorecard": "card",
        "score": "score",
        "value": "Yes",
        "explanation": "matched",
        "metadata": {},
        "score_result_id": "score-result-1",
    }

    with patch(
        "plexus.workers.scoring_api.process_scoring_job_sync",
        return_value=expected,
    ) as process:
        response = client.post(
            "/v1/score",
            json={
                "scoring_job_id": "job-1",
                "scorecard": "card",
                "score": "score",
                "item_id": "item-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == expected
    process.assert_called_once_with(
        scoring_job_id="job-1",
        scorecard_name="card",
        score_name="score",
        item_id="item-1",
        account_key=None,
    )


def test_score_endpoint_validates_required_fields():
    response = client.post("/v1/score", json={"scoring_job_id": "job-1"})

    assert response.status_code == 422


def test_score_endpoint_returns_structured_scoring_error():
    with patch(
        "plexus.workers.scoring_api.process_scoring_job_sync",
        side_effect=ScoringJobError("Item 'item-1' not found", status_code=404),
    ):
        response = client.post(
            "/v1/score",
            json={
                "scoring_job_id": "job-1",
                "scorecard": "card",
                "score": "score",
                "item_id": "item-1",
            },
    )

    assert response.status_code == 404
    payload = response.json()
    request_id = payload.pop("request_id")
    assert len(request_id) == 32
    assert payload == {
        "error": "scoring_request_failed",
        "message": "Requested scoring resource was not found.",
        "scoring_job_id": "job-1",
    }


def test_score_endpoint_logs_sanitized_scoring_error():
    with patch("plexus.workers.scoring_api.logger.warning") as warning:
        with patch(
            "plexus.workers.scoring_api.process_scoring_job_sync",
            side_effect=ScoringJobError(
                "Item 'item-1'\nforged=1 not found",
                status_code=404,
                reason_code="item_not_found",
            ),
        ):
            response = client.post(
                "/v1/score",
                json={
                    "scoring_job_id": "job-1\nforged=1",
                    "scorecard": "card",
                    "score": "score",
                    "item_id": "item-1",
                },
            )

    assert response.status_code == 404
    request_id = response.json()["request_id"]
    warning.assert_called_once_with(
        "Scoring request failed request_id=%s status_code=%s reason_code=%s",
        request_id,
        404,
        "item_not_found",
    )


def test_scoring_error_reason_code_does_not_depend_on_message_content():
    from plexus.workers.scoring_api import scoring_error_reason_code

    score_error = ScoringJobError(
        "Score 'foo' not found in scorecard",
        status_code=404,
        reason_code="score_not_found",
    )
    assert scoring_error_reason_code(score_error) == "score_not_found"

    misleading_name_error = ScoringJobError(
        "Scorecard 'item-review-card' not found",
        status_code=404,
        reason_code="scorecard_not_found",
    )
    assert scoring_error_reason_code(misleading_name_error) == "scorecard_not_found"

    unclassified_error = ScoringJobError("Item 'item-1' not found", status_code=404)
    assert scoring_error_reason_code(unclassified_error) == "resource_not_found"


def test_score_endpoint_requires_configured_api_key(monkeypatch):
    monkeypatch.setenv("SCORING_API_KEY", "test-scoring-key")

    response = client.post(
        "/v1/score",
        json={
            "scoring_job_id": "job-1",
            "scorecard": "card",
            "score": "score",
            "item_id": "item-1",
        },
    )

    assert response.status_code == 401


def test_score_endpoint_rejects_wrong_configured_api_key(monkeypatch):
    monkeypatch.setenv("SCORING_API_KEY", "test-scoring-key")

    response = client.post(
        "/v1/score",
        headers={"x-plexus-scoring-api-key": "wrong-key"},
        json={
            "scoring_job_id": "job-1",
            "scorecard": "card",
            "score": "score",
            "item_id": "item-1",
        },
    )

    assert response.status_code == 401


def test_score_endpoint_fails_closed_when_auth_required_without_key(monkeypatch):
    monkeypatch.setenv("SCORING_API_AUTH_REQUIRED", "true")

    response = client.post(
        "/v1/score",
        json={
            "scoring_job_id": "job-1",
            "scorecard": "card",
            "score": "score",
            "item_id": "item-1",
        },
    )

    assert response.status_code == 503


def test_scoring_api_logs_warning_when_auth_disabled():
    with patch("plexus.workers.scoring_api.logger.warning") as warning:
        log_auth_configuration()

    warning.assert_called_once_with(
        "Scoring API inbound authentication is disabled because SCORING_API_KEY is not set"
    )


def test_score_endpoint_accepts_configured_api_key(monkeypatch):
    monkeypatch.setenv("SCORING_API_KEY", "test-scoring-key")
    expected = {
        "status": "success",
        "scoring_job_id": "job-1",
        "item_id": "item-1",
        "scorecard": "card",
        "score": "score",
        "value": "Yes",
        "explanation": "matched",
        "metadata": {},
        "score_result_id": "score-result-1",
    }

    with patch(
        "plexus.workers.scoring_api.process_scoring_job_sync",
        return_value=expected,
    ):
        response = client.post(
            "/v1/score",
            headers={"x-plexus-scoring-api-key": "test-scoring-key"},
            json={
                "scoring_job_id": "job-1",
                "scorecard": "card",
                "score": "score",
                "item_id": "item-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == expected
