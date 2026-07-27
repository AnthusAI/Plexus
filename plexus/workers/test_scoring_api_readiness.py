from urllib.error import URLError

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from plexus.workers import scoring_api
from plexus.workers.scoring_job import ScoringJobError


def test_proxy_readiness_url_replaces_graphql_path():
    assert (
        scoring_api.proxy_readiness_url("http://plexus-graphql-proxy:8000/graphql")
        == "http://plexus-graphql-proxy:8000/readyz"
    )


def test_readyz_checks_proxy_when_explicitly_required(monkeypatch):
    monkeypatch.setenv("PLEXUS_SCORING_REQUIRE_PROXY_READY", "1")
    monkeypatch.setenv("PLEXUS_API_URL", "http://plexus-graphql-proxy:8000/graphql")
    monkeypatch.setattr(scoring_api, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("down")))

    with pytest.raises(HTTPException) as exc_info:
        scoring_api.readyz()

    assert exc_info.value.status_code == 503


def test_readyz_skips_proxy_when_not_required(monkeypatch):
    monkeypatch.delenv("PLEXUS_SCORING_REQUIRE_PROXY_READY", raising=False)
    monkeypatch.setattr(scoring_api, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError))

    assert scoring_api.readyz() == {"status": "ready"}


def test_score_exposes_a_stable_reason_code_for_retryable_conflicts(monkeypatch):
    def raise_in_progress(**_kwargs):
        raise ScoringJobError(
            "Scoring job is already being processed",
            status_code=409,
            reason_code="scoring_job_in_progress",
        )

    monkeypatch.setattr(scoring_api, "process_scoring_job_sync", raise_in_progress)

    with TestClient(scoring_api.app) as client:
        response = client.post(
            "/v1/score",
            json={
                "scoring_job_id": "retryable-job",
                "scorecard": "scorecard",
                "score": "score",
                "item_id": "item",
            },
        )

    assert response.status_code == 409
    assert response.json()["error"] == "scoring_request_failed"
    assert response.json()["reason_code"] == "scoring_job_in_progress"
