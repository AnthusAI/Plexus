import os

import pytest

from plexus.cli.shared import client_utils

pytestmark = pytest.mark.unit


def test_create_client_prefers_next_public_api_credentials(monkeypatch):
    monkeypatch.setattr(client_utils, "load_config", lambda: None)
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct-key")
    monkeypatch.setenv("PLEXUS_API_URL", "https://legacy.example/graphql")
    monkeypatch.setenv("PLEXUS_API_KEY", "legacy-key")
    monkeypatch.setenv("NEXT_PUBLIC_PLEXUS_API_URL", "https://frontend.example/graphql")
    monkeypatch.setenv("NEXT_PUBLIC_PLEXUS_API_KEY", "frontend-key")

    captured = {}

    class _StubClient:
        def __init__(self, api_url=None, api_key=None, context=None):
            captured["api_url"] = api_url
            captured["api_key"] = api_key
            captured["account_key"] = context.account_key if context else None
            self.api_url = api_url
            self.context = context

    monkeypatch.setattr(client_utils, "PlexusDashboardClient", _StubClient)

    client_utils.create_client()

    assert captured["api_url"] == "https://frontend.example/graphql"
    assert captured["api_key"] == "frontend-key"
    assert captured["account_key"] == "acct-key"


def test_create_client_uses_backend_credentials_when_next_public_unset(monkeypatch):
    monkeypatch.setattr(client_utils, "load_config", lambda: None)
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct-key")
    monkeypatch.setenv("PLEXUS_API_URL", "https://backend.example/graphql")
    monkeypatch.setenv("PLEXUS_API_KEY", "backend-key")
    monkeypatch.delenv("NEXT_PUBLIC_PLEXUS_API_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_PLEXUS_API_KEY", raising=False)

    captured = {}

    class _StubClient:
        def __init__(self, api_url=None, api_key=None, context=None):
            captured["api_url"] = api_url
            captured["api_key"] = api_key
            captured["account_key"] = context.account_key if context else None
            self.api_url = api_url
            self.context = context

    monkeypatch.setattr(client_utils, "PlexusDashboardClient", _StubClient)

    client_utils.create_client()

    assert captured["api_url"] == "https://backend.example/graphql"
    assert captured["api_key"] == "backend-key"
    assert captured["account_key"] == "acct-key"
