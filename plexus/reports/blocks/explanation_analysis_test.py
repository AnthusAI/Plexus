from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.reports.blocks.explanation_analysis import ExplanationAnalysis


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.context = MagicMock(account_id="acct-1")
    client.execute.return_value = {}
    return client


@pytest.fixture
def explanation_block(mock_api_client):
    block = ExplanationAnalysis(
        config={"scorecard": "97", "days": 14},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    block.log_messages = []
    return block


def import_biblicus_modules():
    reinforcement_module = pytest.importorskip("biblicus.analysis.reinforcement_memory")
    embedding_module = pytest.importorskip("biblicus.analysis.reinforcement_memory._embedding")
    clusterer_module = pytest.importorskip("biblicus.analysis.reinforcement_memory._clusterer")
    return reinforcement_module, embedding_module, clusterer_module


@pytest.mark.asyncio
async def test_generate_filters_and_groups_score_result_explanations(explanation_block):
    scorecard = MagicMock(id="scorecard-1", name="Test Scorecard")
    captured = {}

    async def capture_analysis(per_score_raw_texts):
        captured["per_score_raw_texts"] = per_score_raw_texts
        return {
            "scores": [
                {
                    "score_id": "44245",
                    "score_name": "Program Match",
                    "items_processed": 2,
                    "cluster_version": "cv-1",
                    "topics": [],
                }
            ]
        }

    with patch(
        "plexus.dashboard.api.models.scorecard.Scorecard.get_by_external_id",
        return_value=scorecard,
    ), patch(
        "plexus.reports.blocks.feedback_utils.fetch_scores_for_scorecard",
        new=AsyncMock(
            return_value=[
                {
                    "plexus_score_id": "score-1",
                    "plexus_score_name": "Program Match",
                    "cc_question_id": "44245",
                }
            ]
        ),
    ), patch(
        "plexus.reports.blocks.feedback_utils.fetch_score_results_for_score",
        new=AsyncMock(
            return_value=[
                {
                    "id": "sr-keep-1",
                    "value": "No",
                    "explanation": "First retained explanation.",
                    "type": "prediction",
                    "status": "COMPLETED",
                    "code": "200",
                    "evaluationId": None,
                    "itemId": "item-1",
                    "scoreId": "score-1",
                    "updatedAt": "2026-03-04T19:00:00Z",
                },
                {
                    "id": "sr-keep-2",
                    "value": "Yes",
                    "explanation": "Second retained explanation.",
                    "type": "prediction",
                    "status": "COMPLETED",
                    "code": "200",
                    "evaluationId": None,
                    "itemId": "item-2",
                    "scoreId": "score-1",
                    "updatedAt": "2026-03-05T19:00:00Z",
                },
                {
                    "id": "sr-skip-eval",
                    "value": "No",
                    "explanation": "Skip evaluation rows.",
                    "type": "prediction",
                    "status": "COMPLETED",
                    "code": "200",
                    "evaluationId": "eval-1",
                    "itemId": "item-3",
                    "scoreId": "score-1",
                    "updatedAt": "2026-03-05T19:00:00Z",
                },
                {
                    "id": "sr-skip-empty",
                    "value": "No",
                    "explanation": "   ",
                    "type": "prediction",
                    "status": "COMPLETED",
                    "code": "200",
                    "evaluationId": None,
                    "itemId": "item-4",
                    "scoreId": "score-1",
                    "updatedAt": "2026-03-05T19:00:00Z",
                },
                {
                    "id": "sr-skip-status",
                    "value": "No",
                    "explanation": "Skip failed rows.",
                    "type": "prediction",
                    "status": "ERROR",
                    "code": "500",
                    "evaluationId": None,
                    "itemId": "item-5",
                    "scoreId": "score-1",
                    "updatedAt": "2026-03-05T19:00:00Z",
                },
            ]
        ),
    ), patch.object(
        explanation_block,
        "_run_explanation_analysis",
        new=AsyncMock(side_effect=capture_analysis),
    ):
        output, logs = await explanation_block.generate()

    retained_items = captured["per_score_raw_texts"][0]["items"]
    assert [item["score_result_id"] for item in retained_items] == ["sr-keep-1", "sr-keep-2"]
    assert [item["text"] for item in retained_items] == [
        "First retained explanation.",
        "Second retained explanation.",
    ]
    assert retained_items[0]["timestamp"] == datetime(2026, 3, 4, 19, 0, tzinfo=timezone.utc)

    assert output["type"] == "ExplanationAnalysis"
    assert output["items_processed"] == 2
    assert output["total_score_results_retrieved"] == 5
    assert output["total_explanations_retained"] == 2
    assert "Processed 2 production ScoreResult explanations" in output["summary"]
    assert "Retained 2 production ScoreResult explanations" in logs


@pytest.mark.asyncio
async def test_run_explanation_analysis_outputs_topics_with_identifiers_and_cause(explanation_block):
    per_score_raw_texts = [
        {
            "score_id": "44245",
            "score_name": "Program Match",
            "items": [
                {
                    "doc_id": "sr-1",
                    "score_result_id": "sr-1",
                    "item_id": "item-1",
                    "value": "No",
                    "text": "Explanation one",
                    "timestamp": datetime(2026, 3, 4, 19, 0, tzinfo=timezone.utc),
                    "score_result": {"id": "sr-1", "value": "No", "explanation": "Explanation one"},
                },
                {
                    "doc_id": "sr-2",
                    "score_result_id": "sr-2",
                    "item_id": "item-2",
                    "value": "Yes",
                    "text": "Explanation two",
                    "timestamp": datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
                    "score_result": {"id": "sr-2", "value": "Yes", "explanation": "Explanation two"},
                },
            ],
        }
    ]

    class StubClusterer:
        def __init__(self, min_topic_size):
            self.min_topic_size = min_topic_size

        def cluster(self, embeddings, texts):
            return [0, 0], "cv-1"

        def get_keywords(self, tid, n=8):
            return ["billing", "coverage"]

        def get_representative_exemplars(self, tid, n=3):
            return [(0, "Explanation one"), (1, "Explanation two")]

    reinforcement_module, _, clusterer_module = import_biblicus_modules()

    with patch.object(
        reinforcement_module,
        "sentence_transformer_embedder",
        return_value=lambda texts: [[0.1, 0.2], [0.3, 0.4]],
    ), patch(
        "plexus.reports.blocks.explanation_analysis.TopicClusterer",
        new=StubClusterer,
        create=True,
    ), patch.object(
        clusterer_module,
        "TopicClusterer",
        new=StubClusterer,
    ), patch(
        "plexus.reports.blocks.explanation_analysis.fetch_item_identifiers",
        new=AsyncMock(
            side_effect=[
                [{"name": "call_id", "value": "A-1"}],
                [{"name": "call_id", "value": "A-2"}],
            ]
        ),
    ), patch.object(
        explanation_block,
        "_gather_explanation_causal_context",
        new=AsyncMock(
            side_effect=[
                {"explanation_text": "Explanation one"},
                {"explanation_text": "Explanation two"},
            ]
        ),
    ), patch.object(
        explanation_block,
        "_generate_topic_label_llm",
        return_value="Coverage Mismatch",
    ), patch.object(
        explanation_block,
        "_infer_explanation_root_cause_llm",
        side_effect=["Missing exception handling", "Guidelines not explicit"],
    ), patch.object(
        explanation_block,
        "_synthesize_topic_cause_llm",
        return_value="Guidelines miss key exception wording",
    ):
        output = await explanation_block._run_explanation_analysis(per_score_raw_texts)

    assert output is not None
    score_output = output["scores"][0]
    assert score_output["items_processed"] == 2
    assert score_output["cluster_version"] == "cv-1"
    assert len(score_output["topics"]) == 1

    topic = score_output["topics"][0]
    assert topic["label"] == "Coverage Mismatch"
    assert topic["member_count"] == 2
    assert topic["cause"] == "Guidelines miss key exception wording"
    assert topic["root_cause"] == "Guidelines miss key exception wording"
    assert topic["exemplars"][0]["item_id"] == "item-1"
    assert topic["exemplars"][0]["identifiers"] == [{"name": "call_id", "value": "A-1"}]


@pytest.mark.asyncio
async def test_run_explanation_analysis_failure_is_best_effort(explanation_block):
    per_score_raw_texts = [
        {
            "score_id": "44245",
            "score_name": "Program Match",
            "items": [
                {
                    "doc_id": "sr-1",
                    "score_result_id": "sr-1",
                    "item_id": "item-1",
                    "value": "No",
                    "text": "Explanation one",
                    "timestamp": datetime(2026, 3, 4, 19, 0, tzinfo=timezone.utc),
                    "score_result": {"id": "sr-1", "value": "No", "explanation": "Explanation one"},
                },
                {
                    "doc_id": "sr-2",
                    "score_result_id": "sr-2",
                    "item_id": "item-2",
                    "value": "Yes",
                    "text": "Explanation two",
                    "timestamp": datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
                    "score_result": {"id": "sr-2", "value": "Yes", "explanation": "Explanation two"},
                },
            ],
        }
    ]

    reinforcement_module, _, _ = import_biblicus_modules()

    with patch.object(
        reinforcement_module,
        "sentence_transformer_embedder",
        side_effect=RuntimeError("embedding exploded"),
    ):
        output = await explanation_block._run_explanation_analysis(per_score_raw_texts)

    assert output is None
    assert "ExplanationAnalysis failed (non-fatal)" in "\n".join(explanation_block.log_messages)
