from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from proxy import app as proxy_app

from test_app_routing import FailingUpstream, client_with_fakes


def test_shared_api_key_is_only_local_auth_boundary_and_does_not_scope_accounts(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    monkeypatch.setattr(proxy_app, "settings", replace(proxy_app.settings, proxy_api_key="shared-key"))
    monkeypatch.setattr(proxy_app, "upstream", FailingUpstream())

    store.upsert_private(
        "Item",
        {
            "id": "tenant-a-item",
            "accountId": "tenant-a",
            "text": "tenant A local data",
            "updatedAt": "2026-06-05T00:00:00Z",
        },
    )
    store.upsert_private(
        "Item",
        {
            "id": "tenant-b-item",
            "accountId": "tenant-b",
            "text": "tenant B local data",
            "updatedAt": "2026-06-05T00:01:00Z",
        },
    )

    query = """
    query VetLocalTenancy {
      listItems(limit: 10) {
        items { id accountId text }
        nextToken
      }
    }
    """

    unauthenticated = client.post("/graphql", json={"query": query})
    assert unauthenticated.status_code == 401

    response = client.post(
        "/graphql",
        headers={"x-api-key": "shared-key"},
        json={"query": query},
    )

    assert response.status_code == 200
    items = response.json()["data"]["listItems"]["items"]
    assert {item["accountId"] for item in items} == {"tenant-a", "tenant-b"}
    assert store.upstream_requests() == []


def test_readyz_only_proves_database_reachability_today(monkeypatch):
    client, store, _upstream = client_with_fakes(monkeypatch)
    store.ready = lambda: True

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert "contractVersion" not in response.json()
    assert "migration" not in response.json()


def test_local_subscription_roots_are_routable_but_not_served_over_http(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, _store, _upstream = client_with_fakes(monkeypatch)
    monkeypatch.setattr(proxy_app, "upstream", FailingUpstream())

    response = client.post(
        "/graphql",
        json={
            "query": """
            subscription VetLocalRealtime {
              onUpdateTask { id accountId status }
            }
            """
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "subscriptions are not supported"
