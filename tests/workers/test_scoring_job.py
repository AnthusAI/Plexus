from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from plexus.workers.scoring_job import ScoringJobError, process_scoring_job_sync


class FakeScoreInstance:
    def __init__(self, result):
        self.result = result
        self.async_setup = AsyncMock()
        self.predict = AsyncMock(return_value=result)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_process_scoring_job_sync_persists_result(monkeypatch):
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct-1")

    fake_client = Mock()
    fake_client.execute.return_value = {
        "data": {
            "createScoreResult": {
                "id": "score-result-1",
            },
        },
    }
    fake_item = SimpleNamespace(id="item-1", text="hello", accountId="acct-1")
    fake_score_obj = SimpleNamespace(id="score-1")
    fake_result = SimpleNamespace(
        value={"label": "Yes"},
        explanation="matched",
        metadata={"tokens": 12},
    )
    fake_score_instance = FakeScoreInstance(fake_result)

    with patch(
        "plexus.dashboard.api.client.PlexusDashboardClient",
        return_value=fake_client,
    ):
        with patch("plexus.dashboard.api.models.item.Item.get_by_id", return_value=fake_item):
            with patch(
                "plexus.cli.shared.direct_memoized_resolvers.direct_memoized_resolve_scorecard_identifier",
                return_value="scorecard-1",
            ):
                with patch(
                    "plexus.dashboard.api.models.scorecard.Scorecard.get_by_id",
                    return_value=SimpleNamespace(id="scorecard-1"),
                ):
                    with patch(
                        "plexus.dashboard.api.models.score.Score.get_by_name",
                        return_value=fake_score_obj,
                    ):
                        with patch(
                            "plexus.scores.Score.Score.load",
                            return_value=fake_score_instance,
                        ):
                            result = process_scoring_job_sync(
                                scoring_job_id="job-1",
                                scorecard_name="card",
                                score_name="score",
                                item_id="item-1",
                            )

    assert result["status"] == "success"
    assert result["score_result_id"] == "score-result-1"
    assert result["result_id"] == "score-result-1"
    assert result["value"] == {"label": "Yes"}
    fake_client.execute.assert_called_once()
    fake_score_instance.async_setup.assert_awaited_once()
    fake_score_instance.predict.assert_awaited_once()


def test_process_scoring_job_sync_raises_404_for_missing_item(monkeypatch):
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct-1")

    with patch("plexus.dashboard.api.client.PlexusDashboardClient", return_value=Mock()):
        with patch("plexus.dashboard.api.models.item.Item.get_by_id", return_value=None):
            try:
                process_scoring_job_sync(
                    scoring_job_id="job-1",
                    scorecard_name="card",
                    score_name="score",
                    item_id="missing-item",
                )
            except ScoringJobError as exc:
                assert exc.status_code == 404
                assert "missing-item" in str(exc)
            else:
                raise AssertionError("Expected ScoringJobError")
