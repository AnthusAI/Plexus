from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _load_console_auth_smoke_module():
    module_path = Path(__file__).with_name("console_auth_smoke.py")
    spec = importlib.util.spec_from_file_location("console_auth_smoke_test_module", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _args(**overrides):
    values = {
        "graphql_url": "https://example.appsync-api.us-east-1.amazonaws.com/graphql",
        "region": "us-east-1",
        "user_pool_id": "us-east-1_example",
        "account_key": "console-smoke",
        "account_name": "Console Smoke Account",
        "procedure_id": "builtin:console/chat",
        "prompt": "Read-only smoke prompt",
        "response_target": "cloud",
        "timeout_seconds": 5,
        "poll_interval_seconds": 0,
        "max_messages": 25,
        "keep_auth_artifacts": False,
        "require_dispatch_mode": None,
        "skip_start_console_run": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_run_smoke_can_queue_cloud_target_message_without_start_console_run(monkeypatch):
    module = _load_console_auth_smoke_module()
    auth = module.AuthArtifacts(
        app_client_id="app-client",
        temp_user_email="codex-console-smoke@example.com",
        id_token="id-token",
    )
    calls = []
    cleaned = []

    def fake_bootstrap_auth(region, user_pool_id):
        assert region == "us-east-1"
        assert user_pool_id == "us-east-1_example"
        return auth

    def fake_cleanup_auth(*, region, user_pool_id, auth):
        cleaned.append((region, user_pool_id, auth.temp_user_email))

    def fake_graphql(*, url, id_token, query, variables=None):
        calls.append({"query": query, "variables": variables or {}})
        assert url == "https://example.appsync-api.us-east-1.amazonaws.com/graphql"
        assert id_token == "id-token"

        if query == module.LIST_ACCOUNT_BY_KEY:
            return {
                "listAccountByKey": {
                    "items": [
                        {
                            "id": "account-1",
                            "key": "console-smoke",
                            "name": "Console Smoke Account",
                        }
                    ]
                }
            }
        if query == module.CREATE_CHAT_SESSION:
            return {"createChatSession": {"id": "session-1"}}
        if query == module.CREATE_CHAT_MESSAGE:
            return {"createChatMessage": {"id": "user-message-1"}}
        if query == module.LIST_MESSAGES:
            return {
                "listChatMessageBySessionIdAndCreatedAt": {
                    "items": [
                        {
                            "id": "assistant-message-1",
                            "role": "ASSISTANT",
                            "content": "READY",
                            "metadata": '{"streaming":{"state":"complete"}}',
                        }
                    ]
                }
            }
        raise AssertionError(f"Unexpected GraphQL query: {query}")

    monkeypatch.setattr(module, "bootstrap_auth", fake_bootstrap_auth)
    monkeypatch.setattr(module, "cleanup_auth", fake_cleanup_auth)
    monkeypatch.setattr(module, "graphql", fake_graphql)

    result = module.run_smoke(_args())

    create_message_calls = [
        call for call in calls if call["query"] == module.CREATE_CHAT_MESSAGE
    ]
    assert len(create_message_calls) == 1
    created_message_input = create_message_calls[0]["variables"]["input"]
    assert created_message_input["responseStatus"] == "PENDING"
    assert created_message_input["responseTarget"] == "cloud"
    assert created_message_input["content"] == "Read-only smoke prompt"

    assert all(call["query"] != module.START_CONSOLE_RUN for call in calls)
    assert all(call["query"] != module.GET_TASK for call in calls)
    assert result["run_id"] is None
    assert result["task_id"] is None
    assert result["assistant_message_id"] == "assistant-message-1"
    assert result["assistant_content_len"] == len("READY")
    assert result["auth_artifacts_cleaned"] is True
    assert cleaned == [
        ("us-east-1", "us-east-1_example", "codex-console-smoke@example.com")
    ]
