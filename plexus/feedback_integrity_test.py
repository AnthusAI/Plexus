from __future__ import annotations

import pytest

from plexus.feedback_integrity import collect_feedback_score_integrity


class _StubClient:
    def __init__(self):
        self._feedback_pages = [
            {
                "items": [
                    {"id": "f-1", "scorecardId": "sc-1", "scoreId": "score-a"},
                    {"id": "f-2", "scorecardId": "sc-1", "scoreId": "score-missing"},
                ],
                "nextToken": "next-1",
            },
            {
                "items": [
                    {"id": "f-3", "scorecardId": "sc-2", "scoreId": "score-missing"},
                ],
                "nextToken": None,
            },
        ]
        self._page_index = 0

    def execute(self, query, variables):
        if "ListFeedbackIntegrityItems" in query:
            page = self._feedback_pages[self._page_index]
            self._page_index += 1
            return {"listFeedbackItems": page}
        if "GetScoreIntegrity" in query:
            score_id = str((variables or {}).get("id") or "")
            if score_id == "score-a":
                return {"getScore": {"id": "score-a"}}
            return {"getScore": None}
        raise AssertionError(f"Unexpected query {query} with variables={variables}")


@pytest.mark.asyncio
async def test_collect_feedback_score_integrity_reports_orphaned_score_refs():
    client = _StubClient()
    result = await collect_feedback_score_integrity(
        api_client=client,
        account_id="acct-1",
    )

    assert result["feedback_total"] == 3
    assert result["distinct_score_ids_in_feedback"] == 2
    assert result["missing_score_ids"] == 1
    assert result["orphaned_feedback_items"] == 2
    assert result["orphaned_percentage"] == pytest.approx(66.6667, rel=1e-4)
    assert result["orphaned_score_ids"] == ["score-missing"]
    assert result["orphaned_by_scorecard_score"][0]["score_id"] == "score-missing"


@pytest.mark.asyncio
async def test_collect_feedback_score_integrity_handles_empty_feedback_window():
    class _EmptyClient:
        def execute(self, query, variables):
            if "ListFeedbackIntegrityItems" in query:
                return {"listFeedbackItems": {"items": [], "nextToken": None}}
            raise AssertionError("No score lookups expected for empty window")

    result = await collect_feedback_score_integrity(
        api_client=_EmptyClient(),
        account_id="acct-1",
    )

    assert result["feedback_total"] == 0
    assert result["orphaned_feedback_items"] == 0
    assert result["orphaned_by_scorecard_score"] == []
