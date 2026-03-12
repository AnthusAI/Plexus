import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from plexus.reports.blocks.cost_analysis import CostAnalysis


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "test-account-id"
    return client


class TestCostAnalysis:
    def test_compute_item_analysis_counts_unique_items_and_averages(
        self, mock_api_client
    ):
        block = CostAnalysis(
            config={}, params={"account_id": "acct"}, api_client=mock_api_client
        )

        results = [
            {"itemId": "i1", "cost": {"total_cost": "0.40"}},
            {
                "itemId": "i1",
                "cost": {"total_cost": "0.10"},
            },  # same item, should de-dupe
            {"itemId": "i2", "cost": {"total_cost": "0.50"}},
            {"itemId": "i3", "cost": {}},  # no cost -> not counted
            {"cost": {"total_cost": "0.20"}},  # missing itemId -> not counted
        ]

        item_analysis = block._compute_item_analysis(
            results=results,
            total_cost_str="1.00",
            total_calls_str="10",
        )

        assert item_analysis["count"] == 2
        assert item_analysis["total_cost"] == 1.0
        assert item_analysis["average_cost"] == 0.5
        assert item_analysis["average_calls"] == 5.0

    def test_resolve_time_window_end_date_only_uses_days_when_hours_none(
        self, mock_api_client
    ):
        block = CostAnalysis(config={}, params={}, api_client=mock_api_client)

        cfg = {"end_date": "2025-01-02T12:00:00+00:00"}
        start_time, end_time = block._resolve_time_window(cfg, hours=None, days=2)

        assert end_time == datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
        assert start_time == end_time - timedelta(days=2)

    @pytest.mark.asyncio
    async def test_generate_summary_breakdown_defaults_group_by_score_when_scorecard_set(
        self, mock_api_client
    ):
        config = {"scorecard": "scorecard-any-id", "mode": "summary", "breakdown": True}
        block = CostAnalysis(
            config=config, params={"account_id": "acct"}, api_client=mock_api_client
        )

        scorecard_obj = MagicMock()
        scorecard_obj.id = "sc-1"
        scorecard_obj.name = "My Scorecard"

        analyzer = MagicMock()
        analyzer.list_raw.return_value = [
            {"itemId": "i1", "cost": {"total_cost": "0.20"}}
        ]
        analyzer.analyze.return_value = {
            "headline": {
                "average_cost": "0.10",
                "count": 2,
                "total_cost": "0.20",
                "average_calls": "1.00",
                "total_calls": "2",
            },
            "hours": 1,
            "days": 0,
            "filters": {"scorecardId": "sc-1"},
            "scoreNameIndex": {"s2": "Score Two", "s1": "Score One"},
            "groups": [
                {
                    "group": {"scoreId": "s1"},
                    "average_cost": "0.02",
                    "count": 1,
                    "total_cost": "0.02",
                    "average_calls": "1.00",
                    "min_cost": "0.01",
                    "q1_cost": "0.01",
                    "median_cost": "0.02",
                    "q3_cost": "0.02",
                    "max_cost": "0.02",
                },
                {
                    "group": {"scoreId": "s2"},
                    "average_cost": "0.10",
                    "count": 1,
                    "total_cost": "0.10",
                    "average_calls": "1.00",
                    "min_cost": "0.10",
                    "q1_cost": "0.10",
                    "median_cost": "0.10",
                    "q3_cost": "0.10",
                    "max_cost": "0.10",
                },
            ],
        }

        with (
            patch(
                "plexus.cli.scorecard.scorecards.resolve_scorecard_identifier",
                return_value="sc-1",
            ),
            patch(
                "plexus.reports.blocks.cost_analysis.Scorecard.get_by_id",
                return_value=scorecard_obj,
            ),
            patch(
                "plexus.costs.cost_analysis.ScoreResultCostAnalyzer",
                return_value=analyzer,
            ),
            patch.object(
                block,
                "_to_thread",
                new=AsyncMock(
                    side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
                ),
            ),
            patch.object(
                block,
                "_compute_item_analysis",
                return_value={
                    "count": 1,
                    "total_cost": 0.2,
                    "average_cost": 0.2,
                    "average_calls": 1.0,
                },
            ),
        ):
            output, log = await block.generate()

        assert log is not None
        assert output is not None
        assert output["block_title"] == "Cost Analysis"
        assert output["scorecardName"] == "My Scorecard"

        analyzer.analyze.assert_called_once_with(group_by="score")

        groups = output["groups"]
        assert groups[0]["group"]["scoreId"] == "s2"  # sorted desc by average_cost
        assert groups[0]["group"]["scoreName"] == "Score Two"
        assert groups[1]["group"]["scoreId"] == "s1"
        assert groups[1]["group"]["scoreName"] == "Score One"

    @pytest.mark.asyncio
    async def test_generate_all_scorecards_mode(self, mock_api_client):
        config = {"scorecard": "all", "hours": 24, "mode": "summary"}
        block = CostAnalysis(
            config=config, params={"account_id": "acct"}, api_client=mock_api_client
        )

        scorecards = [
            MagicMock(id="sc-1", name="Scorecard 1", externalId="ext-1"),
            MagicMock(id="sc-2", name="Scorecard 2", externalId="ext-2"),
        ]

        def analyzer_factory(*args, **kwargs):
            analyzer = MagicMock()
            scorecard_id = str(kwargs.get("scorecard_id"))
            if scorecard_id == "sc-1":
                analyzer.list_raw.return_value = [
                    {"itemId": "i1", "cost": {"total_cost": "1.00"}}
                ]
                analyzer.analyze.return_value = {
                    "headline": {
                        "average_cost": "1.00",
                        "count": 1,
                        "total_cost": "1.00",
                        "average_calls": "1.00",
                        "total_calls": "1",
                    },
                    "groups": [],
                    "scoreNameIndex": {},
                }
            else:
                analyzer.list_raw.return_value = []
                analyzer.analyze.return_value = {
                    "headline": {
                        "average_cost": "0.00",
                        "count": 0,
                        "total_cost": "0.00",
                        "average_calls": "0.00",
                        "total_calls": "0",
                    },
                    "groups": [],
                    "scoreNameIndex": {},
                }
            return analyzer

        def item_analysis_side_effect(*, results, total_cost_str, total_calls_str):
            total_cost = float(total_cost_str or 0)
            return {
                "count": len(results),
                "total_cost": total_cost,
                "average_cost": (total_cost / len(results)) if results else 0.0,
                "average_calls": 0.0,
            }

        with (
            patch(
                "plexus.reports.blocks.cost_analysis.feedback_utils.fetch_all_scorecards",
                new=AsyncMock(return_value=scorecards),
            ),
            patch(
                "plexus.costs.cost_analysis.ScoreResultCostAnalyzer",
                side_effect=analyzer_factory,
            ),
            patch.object(
                block,
                "_to_thread",
                new=AsyncMock(
                    side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)
                ),
            ),
            patch.object(
                block, "_compute_item_analysis", side_effect=item_analysis_side_effect
            ),
        ):
            output, log = await block.generate()

        assert log is not None
        assert output is not None
        assert output["mode"] == "all_scorecards"
        assert output["total_scorecards_analyzed"] == 2
        assert output["total_scorecards_with_data"] == 1
        assert output["total_scorecards_without_data"] == 1

        scorecards_out = output["scorecards"]
        assert scorecards_out[0]["scorecard_id"] == "sc-1"
        assert scorecards_out[0]["rank"] == 1
        assert scorecards_out[1]["scorecard_id"] == "sc-2"
        assert scorecards_out[1]["rank"] == 2
