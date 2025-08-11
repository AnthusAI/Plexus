import pytest
from datetime import datetime, timedelta, timezone


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    def execute(self, query, variables):
        # Return page by nextToken
        nt = variables.get('nextToken')
        if nt is None:
            self.calls += 1
            return self.pages[0]
        elif nt == 'NEXT1':
            self.calls += 1
            return self.pages[1]
        else:
            return {list(self.pages[0].keys())[0]: {"items": [], "nextToken": None}}


def make_page(top_key, items, next_token=None):
    return {top_key: {"items": items, "nextToken": next_token}}


def test_account_level_summary_with_costs():
    from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

    items1 = [
        {"id": "a1", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s1", "score": {"id": "s1", "name": "Score 1"},
         "metadata": {"cost": {"total_cost": "0.10", "input_cost": "0.06", "output_cost": "0.04", "prompt_tokens": 100, "completion_tokens": 20, "llm_calls": 1}}},
        {"id": "a2", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s2", "score": {"id": "s2", "name": "Score 2"},
         "cost": {"total_cost": "0.02", "input_cost": "0.01", "output_cost": "0.01", "prompt_tokens": 50, "completion_tokens": 5, "llm_calls": 1}},
    ]
    items2 = [
        {"id": "a3", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s1", "score": {"id": "s1", "name": "Score 1"},
         "metadata": {"cost": {"total_cost": "0.05", "input_cost": "0.03", "output_cost": "0.02", "prompt_tokens": 40, "completion_tokens": 10, "llm_calls": 1}}},
    ]

    top_key = "listScoreResultByAccountIdAndUpdatedAt"
    client = FakeClient([
        make_page(top_key, items1, next_token="NEXT1"),
        make_page(top_key, items2, next_token=None),
    ])

    analyzer = ScoreResultCostAnalyzer(client=client, account_id="acct", days=0, hours=1)
    summary = analyzer.summarize()

    assert summary["totals"]["count"] == 3
    assert summary["totals"]["total_cost"] == "0.17"
    assert any(g["scoreId"] == "s1" and g["count"] == 2 for g in summary["groups"]) 
    assert any(g["scoreId"] == "s2" and g["count"] == 1 for g in summary["groups"]) 


def test_single_entry_cache_reuses_results_without_requery(monkeypatch):
    from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

    # Ensure clean cache
    ScoreResultCostAnalyzer.clear_cache()

    top_key = "listScoreResultByAccountIdAndUpdatedAt"
    items = [{"id": "a", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s1", "metadata": {"cost": {"total_cost": "0.10"}}}]

    client = FakeClient([make_page(top_key, items, next_token=None)])
    analyzer = ScoreResultCostAnalyzer(client=client, account_id="acct", days=0, hours=1)

    # First call should query once
    s1 = analyzer.summarize()
    assert client.calls == 1
    assert s1["totals"]["count"] == 1

    # Second call with same params reuses cache; no extra client.execute
    s2 = analyzer.summarize()
    assert client.calls == 1
    assert s2["totals"]["count"] == 1


def test_cache_invalidates_when_params_change():
    from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

    # Ensure clean cache
    ScoreResultCostAnalyzer.clear_cache()

    top_key = "listScoreResultByAccountIdAndUpdatedAt"
    client = FakeClient([make_page(top_key, [], next_token=None)])

    # First analyzer: days=7
    a1 = ScoreResultCostAnalyzer(client=client, account_id="acct", days=0, hours=1)
    _ = a1.summarize()
    assert client.calls == 1

    # Second analyzer: change days -> causes requery
    a2 = ScoreResultCostAnalyzer(client=client, account_id="acct", days=0, hours=3)
    _ = a2.summarize()
    assert client.calls == 2


def test_scorecard_filtered_query():
    from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

    items = [{"id": "x", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s1", "score": {"id": "s1", "name": "Score 1"},
              "metadata": {"cost": {"total_cost": "0.01"}}}]
    top_key = "listScoreResultByScorecardIdAndUpdatedAt"
    client = FakeClient([make_page(top_key, items, next_token=None)])

    analyzer = ScoreResultCostAnalyzer(client=client, account_id="acct", days=0, hours=1, scorecard_id="sc1")
    raw = analyzer.list_raw()
    assert len(raw) == 1


def test_score_filtered_query():
    from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

    items = [{"id": "y", "accountId": "acct", "scorecardId": "sc2", "scoreId": "s2", "score": {"id": "s2", "name": "Score 2"},
              "cost": {"total_cost": "0.03"}}]
    top_key = "listScoreResultByScoreIdAndUpdatedAt"
    client = FakeClient([make_page(top_key, items, next_token=None)])

    analyzer = ScoreResultCostAnalyzer(client=client, account_id="acct", days=0, hours=1, score_id="s2")
    summary = analyzer.summarize()
    assert summary["totals"]["total_cost"] == "0.03"


def test_excludes_entries_without_cost_in_summarize():
    from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

    top_key = "listScoreResultByAccountIdAndUpdatedAt"
    # Mix of entries: one with metadata.cost, one with top-level cost, one with no cost
    items = [
        {"id": "c1", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s1",
         "metadata": {"cost": {"total_cost": "0.01", "llm_calls": 1}}},
        {"id": "c2", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s2",
         "cost": {"total_cost": "0.02", "llm_calls": 1}},
        {"id": "c3", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s3"},  # no cost
    ]
    client = FakeClient([make_page(top_key, items, next_token=None)])

    analyzer = ScoreResultCostAnalyzer(client=client, account_id="acct", days=0, hours=1)
    summary = analyzer.summarize()

    # Totals should only include 2 entries with cost
    assert summary["totals"]["count"] == 2
    assert summary["totals"]["total_cost"] == "0.03"
    # Groups should not include the s3 entry
    group_ids = {(g["scorecardId"], g["scoreId"]) for g in summary["groups"]}
    assert ("sc1", "s1") in group_ids and ("sc1", "s2") in group_ids
    assert ("sc1", "s3") not in group_ids


def test_excludes_entries_without_cost_in_analyze():
    from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

    top_key = "listScoreResultByAccountIdAndUpdatedAt"
    items = [
        {"id": "c1", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s1",
         "metadata": {"cost": {"total_cost": "0.01", "llm_calls": 1}}},
        {"id": "c2", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s2"},  # no cost
        {"id": "c3", "accountId": "acct", "scorecardId": "sc1", "scoreId": "s2",
         "cost": {"total_cost": "0.02", "llm_calls": 2}},
    ]
    client = FakeClient([make_page(top_key, items, next_token=None)])

    analyzer = ScoreResultCostAnalyzer(client=client, account_id="acct", days=0, hours=1)
    analysis = analyzer.analyze(group_by="score")

    # Headline count should be 2 (only entries with cost)
    assert analysis["headline"]["count"] == 2
    assert analysis["headline"]["total_cost"] == "0.03"
    # Grouped stats should have two groups for s1 and s2
    by_score = {g["group"].get("scoreId"): g for g in analysis["groups"]}
    assert "s1" in by_score and "s2" in by_score
    assert by_score["s1"]["count"] == 1
    assert by_score["s2"]["count"] == 1
