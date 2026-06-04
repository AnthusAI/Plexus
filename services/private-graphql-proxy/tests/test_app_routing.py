from __future__ import annotations

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

    def list_private(self, model, filters, sort_direction="ASC", sort_field=None, limit=None):
        docs = list(self.private.setdefault(model, {}).values())
        for name, expected in filters.items():
            docs = [doc for doc in docs if doc.get(name) == expected]
        if sort_field:
            docs.sort(key=lambda doc: doc.get(sort_field) or "", reverse=sort_direction == "DESC")
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
