from __future__ import annotations

import asyncio
import json
import threading
from datetime import timedelta

from fastapi.testclient import TestClient

from proxy import app as proxy_app
from proxy.schema_contract import get_schema_contract
from proxy.store import utcnow


class InMemoryStore:
    def __init__(self):
        self.private = {
            "Item": {},
            "Identifier": {},
            "ScoreResult": {},
            "FeedbackItem": {},
        }
        self.cache = {}
        self.upstream_audit = []
        self.scoring_claims = {}

    def claim_scoring_job(
        self,
        *,
        account_id,
        scoring_job_id,
        item_id,
        scorecard_id,
        score_id,
        score_result_id,
    ):
        key = (account_id, scoring_job_id)
        existing = self.scoring_claims.get(key)
        if not existing:
            self.scoring_claims[key] = {
                "itemId": item_id,
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "scoreResultId": score_result_id,
            }
            return {"state": "CLAIMED", "scoreResultId": score_result_id}
        if (existing["itemId"], existing["scorecardId"], existing["scoreId"]) != (
            item_id,
            scorecard_id,
            score_id,
        ):
            return {"state": "CONFLICT", "scoreResultId": existing["scoreResultId"]}
        if self.get_private("ScoreResult", {"id": existing["scoreResultId"]}):
            return {"state": "COMPLETED", "scoreResultId": existing["scoreResultId"]}
        return {"state": "IN_PROGRESS", "scoreResultId": existing["scoreResultId"]}

    def upsert_private(self, model, input_doc):
        doc = dict(input_doc)
        key = self._key(model, doc)
        self.private.setdefault(model, {})
        self.private[model][key] = doc
        return doc

    def update_private(self, model, input_doc):
        key = self._key(model, input_doc)
        self.private.setdefault(model, {})
        existing = self.private[model].get(key)
        if not existing:
            return None
        existing.update(input_doc)
        return existing

    def get_private(self, model, key):
        private_key = self._key(model, key)
        return self.private.setdefault(model, {}).get(private_key)

    def delete_private(self, model, key):
        private_key = self._key(model, key)
        return self.private.setdefault(model, {}).pop(private_key, None)

    def list_private(self, model, filters, sort_direction="ASC", sort_field=None, limit=None, offset=0):
        docs = list(self.private.setdefault(model, {}).values())
        for name, expected in filters.items():
            if isinstance(expected, dict):
                if "eq" in expected:
                    docs = [doc for doc in docs if doc.get(name) == expected["eq"]]
                elif "beginsWith" in expected:
                    prefix = str(expected["beginsWith"])
                    docs = [doc for doc in docs if str(doc.get(name) or "").startswith(prefix)]
                elif "between" in expected and isinstance(expected["between"], list) and len(expected["between"]) == 2:
                    start, end = (str(expected["between"][0]), str(expected["between"][1]))
                    docs = [doc for doc in docs if start <= str(doc.get(name) or "") <= end]
                else:
                    if "ge" in expected:
                        docs = [doc for doc in docs if str(doc.get(name) or "") >= str(expected["ge"])]
                    if "le" in expected:
                        docs = [doc for doc in docs if str(doc.get(name) or "") <= str(expected["le"])]
            else:
                docs = [doc for doc in docs if doc.get(name) == expected]
        if sort_field:
            docs.sort(key=lambda doc: doc.get(sort_field) or "", reverse=sort_direction == "DESC")
        if offset:
            docs = docs[offset:]
        if limit:
            docs = docs[:limit]
        return docs

    def get_cache(self, cache_key):
        return self.cache.get(cache_key)

    def put_cache(self, cache_key, operation_name, query, variables, response, ttl_seconds, stale_seconds):
        now = utcnow()
        self.cache[cache_key] = {
            "response": response,
            "fetched_at": now,
            "expires_at": now + timedelta(seconds=ttl_seconds),
            "stale_until": now + timedelta(seconds=stale_seconds),
        }

    def record_upstream_request(self, operation_name, root_fields, forwarded_query, variables):
        self.upstream_audit.append(
            {
                "operation_name": operation_name,
                "root_fields": root_fields,
                "forwarded_query": forwarded_query,
                "variables": variables,
            }
        )

    def upstream_requests(self):
        return self.upstream_audit

    def _key(self, model, doc):
        key_fields = get_schema_contract().primary_key_fields(model)
        return tuple(doc.get(field) for field in key_fields)


class FakeUpstream:
    def __init__(self):
        self.calls = 0

    def execute(self, query, variables, operation_name):
        self.calls += 1
        score_id = variables.get("id") or variables.get("scoreId")
        return {"data": {"getScore": {"id": score_id, "name": "Cached score"}}}


class FailingUpstream:
    def execute(self, query, variables, operation_name):
        raise AssertionError("local-mode request unexpectedly forwarded upstream")


def client_with_fakes(monkeypatch):
    store = InMemoryStore()
    upstream = FakeUpstream()
    monkeypatch.setattr(proxy_app, "store", store)
    monkeypatch.setattr(proxy_app, "upstream", upstream)
    return TestClient(proxy_app.app), store, upstream


def test_private_operation_uses_local_store_only(monkeypatch):
    client, store, upstream = client_with_fakes(monkeypatch)

    response = client.post(
        "/graphql",
        json={
            "query": """
            mutation CreateItem($input: CreateItemInput!) {
                createItem(input: $input) { id accountId text }
            }
            """,
            "variables": {
                "input": {
                    "id": "item-1",
                    "accountId": "account-1",
                    "text": "private text",
                }
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["createItem"]["id"] == "item-1"
    assert set(response.json()["data"]["createItem"]) == {"id", "accountId", "text"}
    assert store.private["Item"][("item-1",)]["text"] == "private text"
    assert upstream.calls == 0


def test_claim_scoring_job_is_private_and_idempotent(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, upstream = client_with_fakes(monkeypatch)
    payload = {
        "query": """
        mutation ClaimScore($input: ClaimScoringJobInput!) {
            claimScoringJob(input: $input) { state scoreResultId }
        }
        """,
        "variables": {
            "input": {
                "accountId": "account-1",
                "scoringJobId": "job-1",
                "itemId": "item-1",
                "scorecardId": "scorecard-1",
                "scoreId": "score-1",
                "scoreResultId": "result-1",
            }
        },
    }

    first = client.post("/graphql", json=payload)
    second = client.post("/graphql", json=payload)

    assert first.status_code == 200
    assert first.json()["data"]["claimScoringJob"] == {"state": "CLAIMED", "scoreResultId": "result-1"}
    assert second.json()["data"]["claimScoringJob"] == {"state": "IN_PROGRESS", "scoreResultId": "result-1"}

    store.upsert_private("ScoreResult", {"id": "result-1"})
    completed = client.post("/graphql", json=payload)
    assert completed.status_code == 200
    assert completed.json()["data"]["claimScoringJob"] == {"state": "COMPLETED", "scoreResultId": "result-1"}
    assert upstream.calls == 0


def test_local_artifact_transfer_ticket_mutation_is_handled_without_upstream(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, _store, upstream = client_with_fakes(monkeypatch)

    class FakeArtifactTickets:
        def issue(self, requests):
            assert requests[0]["resourceId"] == "task-1"
            return [{
                "objectKey": "tasks/task-1/output.json",
                "method": "GET",
                "url": "https://plexus-local-object-store:9000/signed",
                "requiredHeaders": {},
                "expiresAt": "2026-07-28T20:00:00Z",
            }]

    monkeypatch.setattr(proxy_app, "artifact_tickets", FakeArtifactTickets())
    response = client.post(
        "/graphql",
        json={
            "query": """
            mutation Tickets($requests: [ArtifactTransferRequestInput!]!) {
                createArtifactTransferTickets(requests: $requests) {
                    objectKey method url requiredHeaders expiresAt
                }
            }
            """,
            "variables": {"requests": [{
                "operation": "READ",
                "resourceType": "TASK",
                "resourceId": "task-1",
                "artifactType": "TASK_ATTACHMENT",
                "filename": "output.json",
                "contentType": "application/json",
                "sizeBytes": 42,
                "sha256": "a" * 64,
            }]},
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["createArtifactTransferTickets"][0]["method"] == "GET"
    assert upstream.calls == 0


def test_control_operation_is_cached(monkeypatch):
    client, _store, upstream = client_with_fakes(monkeypatch)
    payload = {
        "query": "query GetScore($id: ID!) { getScore(id: $id) { id name } }",
        "variables": {"id": "score-1"},
        "operationName": "GetScore",
    }

    first = client.post("/graphql", json=payload)
    second = client.post("/graphql", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == {"getScore": {"id": "score-1", "name": "Cached score"}}
    assert second.json()["data"] == first.json()["data"]
    assert upstream.calls == 1


def test_graphql_endpoint_supports_local_cors_preflight(monkeypatch):
    client, _store, _upstream = client_with_fakes(monkeypatch)
    response = client.options(
        "/graphql",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_graphql_private_store_work_does_not_block_the_event_loop(monkeypatch):
    """A slow local-store request must leave probes and peer requests responsive."""
    handler_thread_ids = []

    class FakeRequest:
        async def json(self):
            return {"query": 'query { getItem(id: "item-1") { id } }'}

    def blocking_handler(*_args, **_kwargs):
        handler_thread_ids.append(threading.get_ident())
        return {"id": "item-1"}

    monkeypatch.setattr(proxy_app, "handle_private_field", blocking_handler)

    async def invoke():
        event_loop_thread_id = threading.get_ident()
        response = await proxy_app.graphql_endpoint(FakeRequest(), None)
        return event_loop_thread_id, response

    event_loop_thread_id, response = asyncio.run(invoke())

    assert json.loads(response.body) == {
        "data": {"getItem": {"id": "item-1"}},
        "extensions": {"proxy": {"private": ["getItem"], "control": []}},
    }
    assert handler_thread_ids != [event_loop_thread_id]


def test_mixed_query_splits_private_and_control_roots(monkeypatch):
    client, store, upstream = client_with_fakes(monkeypatch)
    store.upsert_private(
        "Item",
        {"id": "item-1", "accountId": "account-1", "text": "private text"},
    )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query Mixed($itemId: ID!, $scoreId: ID!) {
                getItem(id: $itemId) { id text }
                getScore(id: $scoreId) { id name }
            }
            """,
            "variables": {"itemId": "item-1", "scoreId": "score-1"},
            "operationName": "Mixed",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["getItem"]["text"] == "private text"
    assert response.json()["data"]["getScore"]["id"] == "score-1"
    assert upstream.calls == 1
    assert store.upstream_audit[0]["root_fields"] == ["getScore"]
    assert "getItem" not in store.upstream_audit[0]["forwarded_query"]


def test_local_mode_routes_control_model_crud_to_local_store(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, upstream = client_with_fakes(monkeypatch)

    response = client.post(
        "/graphql",
        json={
            "query": """
            mutation CreateScorecard($input: CreateScorecardInput!) {
                createScorecard(input: $input) { id name key accountId }
            }
            """,
            "variables": {
                "input": {
                    "id": "scorecard-1",
                    "name": "Local Demo Scorecard",
                    "key": "local-demo-scorecard",
                    "accountId": "account-1",
                }
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["createScorecard"]["id"] == "scorecard-1"
    assert store.private["Scorecard"][("scorecard-1",)]["key"] == "local-demo-scorecard"
    assert upstream.calls == 0


def test_local_mode_resolves_manifest_relationship_selections(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, upstream = client_with_fakes(monkeypatch)
    store.upsert_private("Account", {"id": "account-1", "name": "Demo", "key": "local-demo"})
    store.upsert_private(
        "Scorecard",
        {"id": "scorecard-1", "name": "Demo Scorecard", "key": "demo", "accountId": "account-1"},
    )
    store.upsert_private(
        "ScorecardSection",
        {"id": "section-1", "name": "Section", "order": 1, "scorecardId": "scorecard-1"},
    )
    store.upsert_private(
        "Score",
        {
            "id": "score-1",
            "name": "Demo Score",
            "type": "LangGraphScore",
            "order": 1,
            "externalId": "score-ext-1",
            "sectionId": "section-1",
            "scorecardId": "scorecard-1",
        },
    )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query GetScorecard($id: ID!) {
                getScorecard(id: $id) {
                    id
                    name
                    account { id key }
                    sections { items { id name } }
                    scores { items { id name scorecard { id name } } }
                }
            }
            """,
            "variables": {"id": "scorecard-1"},
        },
    )

    data = response.json()["data"]["getScorecard"]
    assert response.status_code == 200
    assert data["account"] == {"id": "account-1", "key": "local-demo"}
    assert data["sections"]["items"] == [{"id": "section-1", "name": "Section"}]
    assert data["scores"]["items"][0]["scorecard"] == {
        "id": "scorecard-1",
        "name": "Demo Scorecard",
    }
    assert upstream.calls == 0


def test_local_mode_supports_legacy_index_root_alias_queries(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    store.upsert_private(
        "Item",
        {
            "id": "item-legacy-1",
            "accountId": "account-1",
            "text": "legacy index root compatibility",
            "createdAt": "2026-06-04T00:00:00Z",
            "updatedAt": "2026-06-04T00:00:00Z",
        },
    )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query LegacyItemIndex($accountId: String!) {
                listItemByAccountIdAndCreatedAt(accountId: $accountId, sortDirection: DESC, limit: 10) {
                    items { id accountId text }
                    nextToken
                }
            }
            """,
            "variables": {"accountId": "account-1"},
        },
    )

    assert response.status_code == 200
    connection = response.json()["data"]["listItemByAccountIdAndCreatedAt"]
    assert connection["items"][0]["id"] == "item-legacy-1"


def test_local_mode_supports_cli_item_task_index_aliases_without_upstream(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    monkeypatch.setattr(proxy_app, "upstream", FailingUpstream())
    store.upsert_private(
        "Item",
        {
            "id": "item-cli-1",
            "accountId": "account-1",
            "text": "cli item list compatibility",
            "createdAt": "2026-06-04T00:00:00Z",
            "updatedAt": "2026-06-04T01:00:00Z",
        },
    )
    store.upsert_private(
        "Task",
        {
            "id": "task-cli-1",
            "accountId": "account-1",
            "type": "prediction",
            "status": "COMPLETED",
            "createdAt": "2026-06-04T00:00:00Z",
            "updatedAt": "2026-06-04T02:00:00Z",
        },
    )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query CliIndexAliases($accountId: String!) {
                items: listItemByAccountIdAndUpdatedAt(accountId: $accountId, sortDirection: DESC, limit: 1) {
                    items { id accountId updatedAt }
                    nextToken
                }
                tasks: listTaskByAccountIdAndUpdatedAt(accountId: $accountId, sortDirection: DESC, limit: 1) {
                    items { id accountId updatedAt }
                    nextToken
                }
            }
            """,
            "variables": {"accountId": "account-1"},
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["items"]["items"][0]["id"] == "item-cli-1"
    assert data["tasks"]["items"][0]["id"] == "task-cli-1"
    assert store.upstream_requests() == []


def test_local_mode_supports_composite_legacy_index_root_alias_queries(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    store.upsert_private(
        "AggregatedMetrics",
        {
            "accountId": "account-1",
            "compositeKey": "metrics-1",
            "recordType": "items",
            "timeRangeStart": "2026-06-04T00:00:00Z",
            "timeRangeEnd": "2026-06-04T01:00:00Z",
            "numberOfMinutes": 60,
            "count": 5,
            "complete": True,
        },
    )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query LegacyAggregatedMetricsIndex($accountId: String!, $recordType: String!) {
                listAggregatedMetricsByAccountIdAndRecordTypeAndTimeRangeStart(
                    accountId: $accountId
                    recordTypeTimeRangeStart: { beginsWith: { recordType: $recordType } }
                    limit: 10
                ) {
                    items { accountId compositeKey recordType count }
                    nextToken
                }
            }
            """,
            "variables": {"accountId": "account-1", "recordType": "items"},
        },
    )

    assert response.status_code == 200
    connection = response.json()["data"]["listAggregatedMetricsByAccountIdAndRecordTypeAndTimeRangeStart"]
    assert connection["items"][0]["compositeKey"] == "metrics-1"


def test_local_mode_supports_feedback_composite_alias_without_upstream(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    monkeypatch.setattr(proxy_app, "upstream", FailingUpstream())
    store.upsert_private(
        "FeedbackItem",
        {
            "id": "feedback-cli-1",
            "accountId": "account-1",
            "scorecardId": "scorecard-1",
            "scoreId": "score-1",
            "itemId": "item-1",
            "finalAnswerValue": "Yes",
            "editedAt": "2026-06-05T01:00:00Z",
            "createdAt": "2026-06-05T01:00:00Z",
            "updatedAt": "2026-06-05T01:00:00Z",
        },
    )
    store.upsert_private(
        "FeedbackItem",
        {
            "id": "feedback-cli-other",
            "accountId": "account-1",
            "scorecardId": "scorecard-other",
            "scoreId": "score-other",
            "itemId": "item-other",
            "finalAnswerValue": "No",
            "editedAt": "2026-06-05T01:30:00Z",
            "createdAt": "2026-06-05T01:30:00Z",
            "updatedAt": "2026-06-05T01:30:00Z",
        },
    )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query FeedbackAlias($accountId: String!, $scorecardId: String!, $scoreId: String!) {
                listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
                    accountId: $accountId
                    scorecardIdScoreIdEditedAt: {
                        between: [
                            { scorecardId: $scorecardId, scoreId: $scoreId, editedAt: "2026-06-05T00:00:00Z" }
                            { scorecardId: $scorecardId, scoreId: $scoreId, editedAt: "2026-06-06T00:00:00Z" }
                        ]
                    }
                    sortDirection: DESC
                    limit: 10
                ) {
                    items { id accountId itemId finalAnswerValue }
                    nextToken
                }
            }
            """,
            "variables": {
                "accountId": "account-1",
                "scorecardId": "scorecard-1",
                "scoreId": "score-1",
            },
        },
    )

    assert response.status_code == 200
    connection = response.json()["data"]["listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt"]
    assert [item["id"] for item in connection["items"]] == ["feedback-cli-1"]
    assert connection["items"][0]["finalAnswerValue"] == "Yes"
    assert store.upstream_requests() == []


def test_local_mode_lists_feedback_items_for_conjunctive_filter(monkeypatch):
    """The standard all-time feedback query must work against local storage."""
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    for feedback_id, scorecard_id, score_id in (
        ("feedback-standard-1", "scorecard-1", "score-1"),
        ("feedback-standard-other", "scorecard-other", "score-other"),
    ):
        store.upsert_private(
            "FeedbackItem",
            {
                "id": feedback_id,
                "accountId": "account-1",
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "itemId": f"item-{feedback_id}",
                "createdAt": "2026-06-05T01:00:00Z",
                "updatedAt": "2026-06-05T01:00:00Z",
            },
        )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query StandardFeedbackFilter($filter: ModelFeedbackItemFilterInput) {
                listFeedbackItems(filter: $filter, limit: 1000) { items { id } }
            }
            """,
            "variables": {
                "filter": {
                    "and": [
                        {"accountId": {"eq": "account-1"}},
                        {"scorecardId": {"eq": "scorecard-1"}},
                        {"scoreId": {"eq": "score-1"}},
                    ]
                }
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["listFeedbackItems"]["items"] == [{"id": "feedback-standard-1"}]


def test_local_mode_returns_next_token_for_feedback_composite_alias(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    monkeypatch.setattr(proxy_app, "upstream", FailingUpstream())

    for idx in range(1, 4):
        store.upsert_private(
            "FeedbackItem",
            {
                "id": f"feedback-page-{idx}",
                "accountId": "account-1",
                "scorecardId": "scorecard-1",
                "scoreId": "score-1",
                "itemId": f"item-{idx}",
                "finalAnswerValue": "Yes" if idx % 2 else "No",
                "editedAt": f"2026-06-05T0{idx}:00:00Z",
                "createdAt": f"2026-06-05T0{idx}:00:00Z",
                "updatedAt": f"2026-06-05T0{idx}:00:00Z",
            },
        )

    query = """
    query FeedbackAliasPage($accountId: String!, $scorecardId: String!, $scoreId: String!, $nextToken: String) {
        listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
            accountId: $accountId
            scorecardIdScoreIdEditedAt: {
                between: [
                    { scorecardId: $scorecardId, scoreId: $scoreId, editedAt: "2026-06-05T00:00:00Z" }
                    { scorecardId: $scorecardId, scoreId: $scoreId, editedAt: "2026-06-06T00:00:00Z" }
                ]
            }
            sortDirection: ASC
            limit: 2
            nextToken: $nextToken
        ) {
            items { id itemId editedAt }
            nextToken
        }
    }
    """
    variables = {"accountId": "account-1", "scorecardId": "scorecard-1", "scoreId": "score-1", "nextToken": None}

    first_response = client.post("/graphql", json={"query": query, "variables": variables})
    assert first_response.status_code == 200
    first_connection = first_response.json()["data"]["listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt"]
    assert [item["id"] for item in first_connection["items"]] == ["feedback-page-1", "feedback-page-2"]
    assert first_connection["nextToken"]

    variables["nextToken"] = first_connection["nextToken"]
    second_response = client.post("/graphql", json={"query": query, "variables": variables})
    assert second_response.status_code == 200
    second_connection = second_response.json()["data"]["listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt"]
    assert [item["id"] for item in second_connection["items"]] == ["feedback-page-3"]
    assert second_connection["nextToken"] is None
    assert store.upstream_requests() == []


def test_local_mode_supports_synthetic_legacy_score_index_queries(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    store.upsert_private(
        "Score",
        {
            "id": "score-legacy-1",
            "name": "Legacy Score",
            "scorecardId": "scorecard-1",
            "order": 1,
            "createdAt": "2026-06-04T00:00:00Z",
            "updatedAt": "2026-06-04T00:00:00Z",
        },
    )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query LegacyScoreIndex($scorecardId: String!) {
                listScoreByScorecardIdAndOrder(scorecardId: $scorecardId, sortDirection: ASC, limit: 10) {
                    items { id name scorecardId order }
                    nextToken
                }
            }
            """,
            "variables": {"scorecardId": "scorecard-1"},
        },
    )

    assert response.status_code == 200
    connection = response.json()["data"]["listScoreByScorecardIdAndOrder"]
    assert connection["items"][0]["id"] == "score-legacy-1"
