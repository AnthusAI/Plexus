import sys
from datetime import datetime
from pathlib import Path


METRICS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(METRICS_DIR))

from bucket_counter import (  # noqa: E402
    count_feedback_records_efficiently,
    dedupe_feedback_records,
)
from graphql_client import GraphQLClient  # noqa: E402
from graphql_queries import query_feedback_items_in_window  # noqa: E402
from handler import update_buckets  # noqa: E402


def test_dedupe_feedback_records_prefers_latest_effective_timestamp():
    records = [
        {
            "id": "feedback-1",
            "scorecardId": "scorecard-1",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "yes",
            "updatedAt": "2026-04-24T00:00:00Z",
        },
        {
            "id": "feedback-1",
            "scorecardId": "scorecard-1",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "no",
            "editedAt": "2026-04-24T01:00:00Z",
            "updatedAt": "2026-04-24T01:00:00Z",
        },
    ]

    deduped = dedupe_feedback_records(records)

    assert len(deduped) == 1
    assert deduped[0]["finalAnswerValue"] == "no"


def test_count_feedback_records_efficiently_writes_scoped_buckets_and_metadata():
    records = [
        {
            "id": "feedback-1",
            "scorecardId": "scorecard-1",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "no",
            "editedAt": "2026-04-24T12:00:00Z",
        },
        {
            "id": "feedback-2",
            "scorecardId": "scorecard-1",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "yes",
            "updatedAt": "2026-04-24T12:01:00Z",
        },
        {
            "id": "feedback-3",
            "scorecardId": "scorecard-1",
            "scoreId": "score-2",
            "initialAnswerValue": "yes",
            "finalAnswerValue": None,
            "updatedAt": "2026-04-24T12:02:00Z",
        },
    ]

    counts = count_feedback_records_efficiently(records, "account-1")

    account_one_min = [
        bucket
        for bucket in counts
        if bucket["record_type"] == "feedbackItems"
        and bucket["number_of_minutes"] == 1
    ]
    scorecard_one_min = [
        bucket
        for bucket in counts
        if bucket["record_type"] == "feedbackItemsByScorecard"
        and bucket["number_of_minutes"] == 1
    ]
    score_one_min = [
        bucket
        for bucket in counts
        if bucket["record_type"] == "feedbackItemsByScore"
        and bucket["number_of_minutes"] == 1
    ]

    assert len(account_one_min) == 3
    assert sum(bucket["count"] for bucket in account_one_min) == 3
    assert sum(bucket["metadata"]["changedCount"] for bucket in account_one_min) == 1
    assert sum(bucket["metadata"]["unchangedCount"] for bucket in account_one_min) == 1
    assert sum(bucket["metadata"]["invalidCount"] for bucket in account_one_min) == 1

    assert len(scorecard_one_min) == 3
    assert {bucket["scorecard_id"] for bucket in scorecard_one_min} == {"scorecard-1"}

    assert len(score_one_min) == 3
    assert sorted(bucket["score_id"] for bucket in score_one_min) == [
        "score-1",
        "score-1",
        "score-2",
    ]


def test_graphql_client_generates_scoped_composite_keys():
    client = GraphQLClient.__new__(GraphQLClient)

    assert client.generate_composite_key(
        "feedbackItems",
        "2026-04-24T12:00:00Z",
        1,
    ) == "feedbackItems#2026-04-24T12:00:00Z#1"
    assert client.generate_composite_key(
        "feedbackItemsByScorecard",
        "2026-04-24T12:00:00Z",
        1,
        scorecard_id="scorecard-1",
    ) == "feedbackItemsByScorecard#scorecard-1#2026-04-24T12:00:00Z#1"
    assert client.generate_composite_key(
        "feedbackItemsByScore",
        "2026-04-24T12:00:00Z",
        1,
        scorecard_id="scorecard-1",
        score_id="score-1",
    ) == "feedbackItemsByScore#score-1#2026-04-24T12:00:00Z#1"


def test_update_buckets_passes_scope_and_metadata_to_graphql_client():
    class FakeGraphQLClient:
        def __init__(self):
            self.calls = []

        def upsert_aggregated_metrics(self, **kwargs):
            self.calls.append(kwargs)

    graphql_client = FakeGraphQLClient()
    buckets = [
        {
            "account_id": "account-1",
            "record_type": "feedbackItemsByScore",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "time_range_start": "2026-04-24T12:00:00Z",
            "time_range_end": "2026-04-24T12:01:00Z",
            "number_of_minutes": 1,
            "count": 1,
            "complete": True,
            "metadata": {
                "changedCount": 1,
                "unchangedCount": 0,
                "invalidCount": 0,
            },
        }
    ]

    updates, errors = update_buckets(graphql_client, buckets)

    assert updates == 1
    assert errors == 0
    assert graphql_client.calls == [
        {
            "account_id": "account-1",
            "record_type": "feedbackItemsByScore",
            "time_range_start": "2026-04-24T12:00:00Z",
            "time_range_end": "2026-04-24T12:01:00Z",
            "number_of_minutes": 1,
            "count": 1,
            "complete": True,
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "metadata": {
                "changedCount": 1,
                "unchangedCount": 0,
                "invalidCount": 0,
            },
        }
    ]


def test_query_feedback_items_uses_edited_and_updated_indexes_then_dedupes():
    class FakeGraphQLClient:
        def __init__(self):
            self.queries = []

        def execute_query(self, query, variables):
            self.queries.append(query)
            if "listFeedbackItemByAccountIdAndEditedAt" in query:
                return {
                    "listFeedbackItemByAccountIdAndEditedAt": {
                        "items": [
                            {
                                "id": "feedback-1",
                                "scorecardId": "scorecard-1",
                                "scoreId": "score-1",
                                "initialAnswerValue": "yes",
                                "finalAnswerValue": "no",
                                "editedAt": "2026-04-24T12:00:00Z",
                                "updatedAt": "2026-04-24T12:00:00Z",
                                "createdAt": "2026-04-24T11:59:00Z",
                            }
                        ],
                        "nextToken": None,
                    }
                }
            return {
                "listFeedbackItemByAccountIdAndUpdatedAt": {
                    "items": [
                        {
                            "id": "feedback-1",
                            "scorecardId": "scorecard-1",
                            "scoreId": "score-1",
                            "initialAnswerValue": "yes",
                            "finalAnswerValue": "yes",
                            "updatedAt": "2026-04-24T11:59:00Z",
                            "createdAt": "2026-04-24T11:59:00Z",
                        }
                    ],
                    "nextToken": None,
                }
            }

    client = FakeGraphQLClient()
    records = query_feedback_items_in_window(
        client,
        "account-1",
        datetime.fromisoformat("2026-04-24T00:00:00+00:00"),
        datetime.fromisoformat("2026-04-25T00:00:00+00:00"),
    )

    assert len(client.queries) == 2
    assert any("listFeedbackItemByAccountIdAndEditedAt" in query for query in client.queries)
    assert any("listFeedbackItemByAccountIdAndUpdatedAt" in query for query in client.queries)
    assert len(records) == 1
    assert records[0]["finalAnswerValue"] == "no"
