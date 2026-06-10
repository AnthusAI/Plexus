from unittest.mock import patch

from fastapi.testclient import TestClient

from plexus.workers.scoring_api import app
from plexus.workers.scoring_job import ScoringJobError


client = TestClient(app)


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
    assert response.json() == {
        "error": "scoring_request_failed",
        "message": "Item 'item-1' not found",
        "scoring_job_id": "job-1",
    }
