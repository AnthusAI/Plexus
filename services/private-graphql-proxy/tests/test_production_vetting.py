from __future__ import annotations

from dataclasses import replace

import pytest

from proxy import app as proxy_app
from proxy.config import Settings

from test_app_routing import FailingUpstream, client_with_fakes


def test_api_key_mode_is_only_local_auth_boundary_and_does_not_scope_accounts(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, store, _upstream = client_with_fakes(monkeypatch)
    monkeypatch.setattr(
        proxy_app,
        "settings",
        replace(
            proxy_app.settings,
            backend_mode="local",
            auth_mode="api_key",
            auth_mode_explicit=True,
            proxy_api_key="shared-key",
            upstream_disabled=True,
        ),
    )
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

    wrong_key = client.post(
        "/graphql",
        headers={"x-api-key": "wrong-key"},
        json={"query": query},
    )
    assert wrong_key.status_code == 401

    response = client.post(
        "/graphql",
        headers={"x-api-key": "shared-key"},
        json={"query": query},
    )

    assert response.status_code == 200
    items = response.json()["data"]["listItems"]["items"]
    assert {item["accountId"] for item in items} == {"tenant-a", "tenant-b"}
    assert store.upstream_requests() == []


def test_trusted_open_mode_accepts_no_key_and_does_not_scope_accounts(monkeypatch):
    client, store, _upstream = client_with_fakes(monkeypatch)
    monkeypatch.setattr(
        proxy_app,
        "settings",
        replace(
            proxy_app.settings,
            backend_mode="local",
            auth_mode="trusted_open",
            auth_mode_explicit=True,
            proxy_api_key=None,
            upstream_disabled=True,
        ),
    )
    monkeypatch.setattr(proxy_app, "upstream", FailingUpstream())

    store.upsert_private(
        "Item",
        {
            "id": "trusted-tenant-a-item",
            "accountId": "trusted-tenant-a",
            "text": "trusted tenant A local data",
            "updatedAt": "2026-06-05T00:00:00Z",
        },
    )
    store.upsert_private(
        "Item",
        {
            "id": "trusted-tenant-b-item",
            "accountId": "trusted-tenant-b",
            "text": "trusted tenant B local data",
            "updatedAt": "2026-06-05T00:01:00Z",
        },
    )

    response = client.post(
        "/graphql",
        json={
            "query": """
            query TrustedOpenLocalTenancy {
              listItems(limit: 10) {
                items { id accountId text }
                nextToken
              }
            }
            """
        },
    )

    assert response.status_code == 200
    items = response.json()["data"]["listItems"]["items"]
    assert {item["accountId"] for item in items} == {"trusted-tenant-a", "trusted-tenant-b"}
    assert store.upstream_requests() == []


def test_readyz_reports_security_mode_metadata(monkeypatch):
    client, store, _upstream = client_with_fakes(monkeypatch)
    store.ready = lambda: True
    monkeypatch.setattr(
        proxy_app,
        "settings",
        replace(
            proxy_app.settings,
            backend_mode="local",
            auth_mode="trusted_open",
            auth_mode_explicit=True,
            proxy_api_key=None,
            upstream_disabled=True,
        ),
    )

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "backendMode": "local",
        "authMode": "trusted_open",
        "authModeExplicit": True,
        "upstreamDisabled": True,
        "externalAccessControlRequired": True,
        "artifactTicketsEnabled": False,
    }


def test_trusted_open_mode_is_invalid_outside_local_backend(monkeypatch):
    client, store, _upstream = client_with_fakes(monkeypatch)
    store.ready = lambda: True
    monkeypatch.setattr(
        proxy_app,
        "settings",
        replace(
            proxy_app.settings,
            backend_mode="amplify",
            auth_mode="trusted_open",
            auth_mode_explicit=True,
            proxy_api_key=None,
            upstream_disabled=True,
        ),
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "trusted_open requires PLEXUS_BACKEND_MODE=local" in response.json()["detail"]


def test_trusted_open_mode_requires_upstream_disabled(monkeypatch):
    client, store, _upstream = client_with_fakes(monkeypatch)
    store.ready = lambda: True
    monkeypatch.setattr(
        proxy_app,
        "settings",
        replace(
            proxy_app.settings,
            backend_mode="local",
            auth_mode="trusted_open",
            auth_mode_explicit=True,
            proxy_api_key=None,
            upstream_disabled=False,
        ),
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "trusted_open requires PLEXUS_PROXY_UPSTREAM_DISABLED=true" in response.json()["detail"]


def test_security_configuration_fails_startup_for_invalid_trusted_open(monkeypatch):
    monkeypatch.setattr(
        proxy_app,
        "settings",
        replace(
            proxy_app.settings,
            backend_mode="amplify",
            auth_mode="trusted_open",
            auth_mode_explicit=True,
            proxy_api_key=None,
            upstream_disabled=True,
        ),
    )

    with pytest.raises(RuntimeError, match="trusted_open requires PLEXUS_BACKEND_MODE=local"):
        proxy_app.assert_security_configuration()


def test_local_artifact_tickets_require_explicit_api_key_auth(monkeypatch):
    client, store, _upstream = client_with_fakes(monkeypatch)
    store.ready = lambda: True
    monkeypatch.setattr(
        proxy_app,
        "artifact_ticket_configuration",
        replace(proxy_app.artifact_ticket_configuration, enabled=True),
    )
    monkeypatch.setattr(
        proxy_app,
        "settings",
        replace(
            proxy_app.settings,
            backend_mode="local",
            auth_mode="trusted_open",
            auth_mode_explicit=True,
            proxy_api_key=None,
            upstream_disabled=True,
        ),
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "explicit PLEXUS_PROXY_AUTH_MODE=api_key" in response.json()["detail"]


def test_settings_infer_auth_mode_from_api_key(monkeypatch):
    monkeypatch.delenv("PLEXUS_PROXY_AUTH_MODE", raising=False)
    monkeypatch.setenv("PLEXUS_PROXY_API_KEY", "configured-key")

    settings = Settings.from_env()

    assert settings.auth_mode == "api_key"
    assert settings.auth_mode_explicit is False


def test_settings_infer_trusted_open_without_api_key(monkeypatch):
    monkeypatch.delenv("PLEXUS_PROXY_AUTH_MODE", raising=False)
    monkeypatch.delenv("PLEXUS_PROXY_API_KEY", raising=False)

    settings = Settings.from_env()

    assert settings.auth_mode == "trusted_open"
    assert settings.auth_mode_explicit is False


def test_local_subscription_roots_are_routable_but_not_served_over_http(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    client, _store, _upstream = client_with_fakes(monkeypatch)
    monkeypatch.setattr(
        proxy_app,
        "settings",
        replace(
            proxy_app.settings,
            backend_mode="local",
            auth_mode="trusted_open",
            auth_mode_explicit=True,
            proxy_api_key=None,
            upstream_disabled=True,
        ),
    )
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
