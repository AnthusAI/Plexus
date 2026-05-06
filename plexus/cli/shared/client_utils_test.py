import os
import subprocess
import sys
from pathlib import Path

import pytest

from plexus.cli.shared import client_utils

pytestmark = pytest.mark.unit


def test_create_client_prefers_explicit_runtime_api_credentials(monkeypatch):
    monkeypatch.setattr(client_utils, "load_config", lambda: None)
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct-key")
    monkeypatch.setenv("PLEXUS_API_URL", "https://runtime.example/graphql")
    monkeypatch.setenv("PLEXUS_API_KEY", "runtime-key")
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

    assert captured["api_url"] == "https://runtime.example/graphql"
    assert captured["api_key"] == "runtime-key"
    assert captured["account_key"] == "acct-key"


def test_create_client_uses_frontend_defaults_when_runtime_unset(monkeypatch):
    monkeypatch.setattr(client_utils, "load_config", lambda: None)
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct-key")
    monkeypatch.delenv("PLEXUS_API_URL", raising=False)
    monkeypatch.delenv("PLEXUS_API_KEY", raising=False)
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


def test_cli_startup_preserves_explicit_runtime_env_over_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "PLEXUS_API_URL=https://dotenv.example/graphql",
                "PLEXUS_API_KEY=dotenv-key",
                "PLEXUS_ACCOUNT_KEY=dotenv-account",
            ]
        )
    )
    repo_root = Path(__file__).resolve().parents[3]
    script = (
        "import os, sys\n"
        "import plexus.cli.shared.CommandLineInterface\n"
        "sys.stdout.write(os.environ['PLEXUS_API_URL'] + '\\n')\n"
        "sys.stdout.write(os.environ['PLEXUS_API_KEY'] + '\\n')\n"
        "sys.stdout.write(os.environ['PLEXUS_ACCOUNT_KEY'] + '\\n')\n"
        "sys.stdout.flush()\n"
        "os._exit(0)\n"
    )
    env = os.environ.copy()
    env.update(
        {
            "PLEXUS_API_URL": "https://runtime.example/graphql",
            "PLEXUS_API_KEY": "runtime-key",
            "PLEXUS_ACCOUNT_KEY": "runtime-account",
            "PYTHONPATH": f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == [
        "https://runtime.example/graphql",
        "runtime-key",
        "runtime-account",
    ]


def test_create_client_sets_actor_context_from_env(monkeypatch):
    monkeypatch.setattr(client_utils, "load_config", lambda: None)
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "acct-key")
    monkeypatch.setenv("PLEXUS_API_URL", "https://backend.example/graphql")
    monkeypatch.setenv("PLEXUS_API_KEY", "backend-key")
    monkeypatch.setenv("PLEXUS_ACTOR_USER_ID", "user-123")
    monkeypatch.setenv("PLEXUS_ACTOR_TYPE", "agent")
    monkeypatch.setenv("PLEXUS_ACTOR_KEY", "execute_tactus")
    monkeypatch.setenv("PLEXUS_ACTOR_SOURCE", "execute_tactus")

    captured = {}

    class _StubClient:
        def __init__(self, api_url=None, api_key=None, context=None):
            captured["actor_user_id"] = context.actor_user_id if context else None
            captured["actor_type"] = context.actor_type if context else None
            captured["actor_key"] = context.actor_key if context else None
            captured["actor_source"] = context.actor_source if context else None
            self.api_url = api_url
            self.context = context

    monkeypatch.setattr(client_utils, "PlexusDashboardClient", _StubClient)
    client_utils.create_client()

    assert captured["actor_user_id"] == "user-123"
    assert captured["actor_type"] == "agent"
    assert captured["actor_key"] == "execute_tactus"
    assert captured["actor_source"] == "execute_tactus"
