from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from proxy import app as proxy_app
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
        if model == "Identifier":
            key = (doc["itemId"], doc["name"])
        else:
            key = doc["id"]
        self.private[model][key] = doc
        return doc

    def update_private(self, model, input_doc):
        if model == "Identifier":
            key = (input_doc["itemId"], input_doc["name"])
        else:
            key = input_doc["id"]
        existing = self.private[model].get(key)
        if not existing:
            return None
        existing.update(input_doc)
        return existing

    def get_private(self, model, key):
        if model == "Identifier":
            private_key = (key["itemId"], key["name"])
        else:
            private_key = key["id"]
        return self.private[model].get(private_key)

    def delete_private(self, model, key):
        if model == "Identifier":
            private_key = (key["itemId"], key["name"])
        else:
            private_key = key["id"]
        return self.private[model].pop(private_key, None)

    def list_private(self, model, filters, sort_direction="ASC", sort_field=None, limit=None):
        docs = list(self.private[model].values())
        for name, expected in filters.items():
            docs = [doc for doc in docs if doc.get(name) == expected]
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
    assert store.private["Item"]["item-1"]["text"] == "private text"
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
