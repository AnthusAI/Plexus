"""
Tests for plexus/reports/action_items_utils.py

Covers:
- collect_action_items: all-scorecards mode, single-scorecard mode
- Filtering by AC1 threshold, recency, and zero-mismatch exclusion
- Sort order: member_count DESC, then days_inactive ASC
- _extract_topics_for_scores: topic matching by score_id
"""

import pytest
from unittest.mock import MagicMock, patch

from plexus.reports.action_items_utils import collect_action_items, _extract_topics_for_scores


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_topic(label, member_count, days_inactive, score_id=None, is_trending=False, is_new=False, cause=None):
    return {
        "label": label,
        "member_count": member_count,
        "days_inactive": days_inactive,
        "is_trending": is_trending,
        "is_new": is_new,
        "cause": cause,
        "keywords": ["kw1", "kw2"],
        "exemplars": [
            {
                "text": "example edit comment",
                "initial_answer_value": "Yes",
                "final_answer_value": "No",
                "identifiers": [{"url": "https://example.com/r/1"}],
            }
        ],
    }


def _make_score(score_id, score_name, ac1, mismatches):
    return {"score_id": score_id, "score_name": score_name, "ac1": ac1, "mismatches": mismatches}


def _make_memories(score_id, topics):
    return {"scores": [{"score_id": score_id, "topics": topics}]}


# ── collect_action_items: single-scorecard mode ───────────────────────────────

class TestCollectActionItemsSingleScorecard:

    def _output(self, scores, memories=None, memories_file=None, overall_ac1=None, scorecard_name="Test Scorecard"):
        out = {
            "scorecard_name": scorecard_name,
            "overall_ac1": overall_ac1,
            "scores": scores,
            "date_range": {"start": "2026-01-01", "end": "2026-03-28"},
        }
        if memories is not None:
            out["memories"] = memories
        if memories_file is not None:
            out["memories_file"] = memories_file
        return out

    def test_basic_item_returned(self):
        topics = [_make_topic("Prescriber not verified", member_count=5, days_inactive=10)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Medication Review", ac1=0.3, mismatches=5)]
        output = self._output(scores, memories=memories)

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)

        assert len(items) == 1
        assert items[0]["score_name"] == "Medication Review"
        assert items[0]["topic_label"] == "Prescriber not verified"
        assert items[0]["member_count"] == 5

    def test_score_above_ac1_threshold_excluded(self):
        topics = [_make_topic("Something", member_count=5, days_inactive=5)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Good Score", ac1=0.9, mismatches=2)]
        output = self._output(scores, memories=memories)

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)
        assert items == []

    def test_score_with_zero_mismatches_excluded(self):
        topics = [_make_topic("Something", member_count=5, days_inactive=5)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Perfect Score", ac1=0.5, mismatches=0)]
        output = self._output(scores, memories=memories)

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)
        assert items == []

    def test_topic_too_old_excluded(self):
        topics = [_make_topic("Stale topic", member_count=10, days_inactive=45)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Bad Score", ac1=0.2, mismatches=10)]
        output = self._output(scores, memories=memories)

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)
        assert items == []

    def test_overall_ac1_above_threshold_returns_empty(self):
        topics = [_make_topic("Something", member_count=5, days_inactive=5)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Score", ac1=0.5, mismatches=3)]
        output = self._output(scores, memories=memories, overall_ac1=0.95)

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)
        assert items == []

    def test_score_with_none_ac1_included(self):
        """Scores with no AC1 data (insufficient items) should still be included."""
        topics = [_make_topic("Something", member_count=3, days_inactive=5)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Sparse Score", ac1=None, mismatches=3)]
        output = self._output(scores, memories=memories)

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)
        assert len(items) == 1

    def test_exemplar_enriched_fields_preserved(self):
        topics = [_make_topic("Topic", member_count=5, days_inactive=5)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Score", ac1=0.3, mismatches=5)]
        output = self._output(scores, memories=memories)

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)

        exemplar = items[0]["exemplars"][0]
        assert exemplar["initial_answer_value"] == "Yes"
        assert exemplar["final_answer_value"] == "No"
        assert exemplar["text"] == "example edit comment"

    def test_scorecard_name_from_hint(self):
        topics = [_make_topic("Topic", member_count=5, days_inactive=5)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Score", ac1=0.3, mismatches=5)]
        # output without scorecard_name
        output = {"scores": scores, "memories": memories}

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30,
                                     scorecard_name_hint="My Scorecard")
        assert items[0]["scorecard_name"] == "My Scorecard"

    def test_memories_file_fetched_when_present(self):
        topics = [_make_topic("Topic", member_count=5, days_inactive=5)]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Score", ac1=0.3, mismatches=5)]
        output = self._output(scores, memories_file="s3/path/to/memories.yaml")

        with patch("plexus.reports.action_items_utils.fetch_memories", return_value=memories) as mock_fetch:
            items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)

        mock_fetch.assert_called_once_with("s3/path/to/memories.yaml")
        assert len(items) == 1

    def test_memories_file_error_returns_empty(self):
        scores = [_make_score("score-1", "Score", ac1=0.3, mismatches=5)]
        output = self._output(scores, memories_file="bad/path.yaml")

        with patch("plexus.reports.action_items_utils.fetch_memories", side_effect=Exception("S3 error")):
            items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)

        assert items == []


# ── collect_action_items: all-scorecards mode ─────────────────────────────────

class TestCollectActionItemsAllScorecards:

    def _scorecard_entry(self, name, scorecard_id, scores, overall_ac1=None):
        return {
            "scorecard_name": name,
            "scorecard_id": scorecard_id,
            "overall_ac1": overall_ac1,
            "scores": scores,
            "memories_file": f"s3/path/{scorecard_id}.yaml",
        }

    def test_all_scorecards_mode_returns_items_from_each(self):
        scores_a = [_make_score("s1", "Score A", ac1=0.3, mismatches=5)]
        scores_b = [_make_score("s2", "Score B", ac1=0.4, mismatches=3)]
        topics_a = [_make_topic("Topic A", member_count=5, days_inactive=5)]
        topics_b = [_make_topic("Topic B", member_count=3, days_inactive=7)]
        memories_a = _make_memories("s1", topics_a)
        memories_b = _make_memories("s2", topics_b)

        output = {
            "mode": "all_scorecards",
            "scorecards": [
                self._scorecard_entry("Scorecard A", "sc-a", scores_a),
                self._scorecard_entry("Scorecard B", "sc-b", scores_b),
            ],
        }

        def fake_fetch(path):
            return memories_a if "sc-a" in path else memories_b

        with patch("plexus.reports.action_items_utils.fetch_memories", side_effect=fake_fetch):
            items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)

        assert len(items) == 2
        scorecard_names = {i["scorecard_name"] for i in items}
        assert "Scorecard A" in scorecard_names
        assert "Scorecard B" in scorecard_names

    def test_scorecard_above_ac1_threshold_skipped(self):
        scores = [_make_score("s1", "Score", ac1=0.3, mismatches=5)]
        output = {
            "mode": "all_scorecards",
            "scorecards": [
                {**self._scorecard_entry("Good Scorecard", "sc-a", scores), "overall_ac1": 0.95}
            ],
        }

        with patch("plexus.reports.action_items_utils.fetch_memories") as mock_fetch:
            items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)

        mock_fetch.assert_not_called()
        assert items == []

    def test_scorecard_without_memories_file_skipped(self):
        scores = [_make_score("s1", "Score", ac1=0.3, mismatches=5)]
        output = {
            "mode": "all_scorecards",
            "scorecards": [
                {"scorecard_name": "No Memories", "scores": scores}  # no memories_file
            ],
        }

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)
        assert items == []


# ── Sort order ─────────────────────────────────────────────────────────────────

class TestSortOrder:

    def test_sorted_by_member_count_desc_then_days_inactive_asc(self):
        topics_score1 = [
            _make_topic("Small recent", member_count=3, days_inactive=2),
            _make_topic("Large old", member_count=12, days_inactive=15),
            _make_topic("Large recent", member_count=12, days_inactive=5),
            _make_topic("Medium", member_count=7, days_inactive=8),
        ]
        memories = _make_memories("score-1", topics_score1)
        scores = [_make_score("score-1", "Score", ac1=0.3, mismatches=20)]
        output = {"scores": scores, "memories": memories}

        items = collect_action_items(output, ac1_threshold=0.8, recency_days=30)

        counts = [i["member_count"] for i in items]
        assert counts == [12, 12, 7, 3], f"Expected [12, 12, 7, 3], got {counts}"

        # Within the two 12-count items, most recent (lower days_inactive) should be first
        twelve_items = [i for i in items if i["member_count"] == 12]
        assert twelve_items[0]["days_inactive"] == 5
        assert twelve_items[1]["days_inactive"] == 15


# ── _extract_topics_for_scores ─────────────────────────────────────────────────

class TestExtractTopicsForScores:

    def test_score_id_not_in_memories_returns_no_topics(self):
        scores = [_make_score("score-x", "Unknown", ac1=0.3, mismatches=5)]
        memories = _make_memories("score-other", [_make_topic("Topic", 5, 5)])

        items = _extract_topics_for_scores(scores, memories, "Scorecard", 0.8, 30)
        assert items == []

    def test_multiple_topics_per_score_all_included(self):
        topics = [
            _make_topic("Topic 1", member_count=5, days_inactive=5),
            _make_topic("Topic 2", member_count=3, days_inactive=10),
        ]
        memories = _make_memories("score-1", topics)
        scores = [_make_score("score-1", "Score", ac1=0.3, mismatches=8)]

        items = _extract_topics_for_scores(scores, memories, "Scorecard", 0.8, 30)
        assert len(items) == 2

    def test_item_contains_expected_fields(self):
        topic = _make_topic("My Topic", member_count=7, days_inactive=4,
                            is_trending=True, cause="Root cause text")
        memories = _make_memories("score-1", [topic])
        scores = [_make_score("score-1", "Score Name", ac1=0.25, mismatches=7)]

        items = _extract_topics_for_scores(scores, memories, "My Scorecard", 0.8, 30)
        item = items[0]

        assert item["scorecard_name"] == "My Scorecard"
        assert item["score_name"] == "Score Name"
        assert item["score_ac1"] == 0.25
        assert item["topic_label"] == "My Topic"
        assert item["cause"] == "Root cause text"
        assert item["member_count"] == 7
        assert item["days_inactive"] == 4
        assert item["is_trending"] is True
        assert item["is_new"] is False
        assert item["keywords"] == ["kw1", "kw2"]
