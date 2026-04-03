import pytest

from plexus.cli.shared.fetch_score_configurations import fetch_score_configurations


class _MockSession:
    def execute(self, _query, variable_values=None):
        version_id = (variable_values or {}).get("id")
        return {"getScoreVersion": None if version_id == "missing-version" else {"id": version_id, "configuration": "name: Test\nkey: test\nid: test-id\nclass: TestScore\n"}}


class _MockClient:
    def __enter__(self):
        return _MockSession()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_fetch_score_configurations_fails_fast_when_version_missing_without_cache():
    scorecard = {"id": "scorecard-1", "name": "Scorecard One"}
    target_scores = [
        {
            "id": "score-1",
            "name": "Score One",
            "championVersionId": "missing-version",
        }
    ]
    cache_status = {"score-1": False}

    with pytest.raises(ValueError) as exc:
        fetch_score_configurations(
            client=_MockClient(),
            scorecard_data=scorecard,
            target_scores=target_scores,
            cache_status=cache_status,
            use_cache=False,
        )

    assert "No configuration found for version: missing-version" in str(exc.value)
