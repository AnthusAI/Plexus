from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _load_app_module():
    app_path = Path(__file__).with_name("app.py")
    spec = importlib.util.spec_from_file_location("console_chat_responder_app", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _stream_record(*, target="cloud", status="PENDING", event_name="INSERT"):
    return {
        "eventID": "event-1",
        "eventName": event_name,
        "dynamodb": {
            "SequenceNumber": "seq-1",
            "NewImage": {
                "id": {"S": "msg-1"},
                "accountId": {"S": "acct-1"},
                "sessionId": {"S": "sess-1"},
                "procedureId": {"S": "builtin:console/chat"},
                "role": {"S": "USER"},
                "humanInteraction": {"S": "CHAT"},
                "messageType": {"S": "MESSAGE"},
                "content": {"S": "Hello"},
                "responseTarget": {"S": target},
                "responseStatus": {"S": status},
                "createdAt": {"S": "2026-04-27T00:00:00.000Z"},
            },
        },
    }


def test_handler_processes_cloud_targeted_insert(monkeypatch):
    app = _load_app_module()
    calls = []

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")
    monkeypatch.setattr(app, "_load_provider_credentials", lambda: None)
    monkeypatch.setattr(app, "_resolve_client", SimpleNamespace)
    monkeypatch.setattr(
        app,
        "process_console_message",
        lambda _client, message, **kwargs: calls.append((message, kwargs)) or True,
    )

    result = app.handler({"Records": [_stream_record()]}, SimpleNamespace(aws_request_id="req-1"))

    assert result["processed"] == 1
    assert result["skipped"] == 0
    assert result["batchItemFailures"] == []
    assert calls[0][0]["id"] == "msg-1"
    assert calls[0][1]["expected_target"] == "cloud"


def test_handler_skips_local_target_when_cloud_worker_does_not_claim(monkeypatch):
    app = _load_app_module()

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")
    monkeypatch.setattr(app, "_load_provider_credentials", lambda: None)
    monkeypatch.setattr(app, "_resolve_client", SimpleNamespace)
    monkeypatch.setattr(app, "process_console_message", lambda *_args, **_kwargs: False)

    result = app.handler(
        {"Records": [_stream_record(target="local:ryan")]},
        SimpleNamespace(aws_request_id="req-1"),
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert result["batchItemFailures"] == []


def test_handler_ignores_non_insert_records(monkeypatch):
    app = _load_app_module()

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")
    monkeypatch.setattr(app, "_load_provider_credentials", lambda: None)
    monkeypatch.setattr(app, "_resolve_client", SimpleNamespace)

    result = app.handler(
        {"Records": [_stream_record(event_name="MODIFY")]},
        SimpleNamespace(aws_request_id="req-1"),
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1


def test_handler_reports_partial_batch_failure_when_processing_raises(monkeypatch):
    app = _load_app_module()

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")
    monkeypatch.setattr(app, "_load_provider_credentials", lambda: None)
    monkeypatch.setattr(app, "_resolve_client", SimpleNamespace)

    def fail_processing(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(app, "process_console_message", fail_processing)

    result = app.handler({"Records": [_stream_record()]}, SimpleNamespace(aws_request_id="req-1"))

    assert result["processed"] == 0
    assert result["skipped"] == 0
    assert result["batchItemFailures"] == [{"itemIdentifier": "seq-1"}]


def test_handler_skips_insert_without_new_image(monkeypatch):
    app = _load_app_module()

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")
    monkeypatch.setattr(app, "_load_provider_credentials", lambda: None)
    monkeypatch.setattr(app, "_resolve_client", SimpleNamespace)

    result = app.handler(
        {
            "Records": [
                {
                    "eventID": "event-1",
                    "eventName": "INSERT",
                    "dynamodb": {"SequenceNumber": "seq-1"},
                }
            ]
        },
        SimpleNamespace(aws_request_id="req-1"),
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1


def test_handler_duplicate_stream_delivery_counts_only_one_processed(monkeypatch):
    app = _load_app_module()
    outcomes = iter([True, False])

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")
    monkeypatch.setattr(app, "_load_provider_credentials", lambda: None)
    monkeypatch.setattr(app, "_resolve_client", SimpleNamespace)
    monkeypatch.setattr(app, "process_console_message", lambda *_args, **_kwargs: next(outcomes))

    result = app.handler(
        {"Records": [_stream_record(), _stream_record()]},
        SimpleNamespace(aws_request_id="req-1"),
    )

    assert result["processed"] == 1
    assert result["skipped"] == 1
    assert result["batchItemFailures"] == []


def test_resolve_client_uses_iam_auth_without_api_key(monkeypatch):
    app = _load_app_module()
    created = []

    class FakeClient:
        def __init__(self, *, api_url):
            created.append(api_url)

    monkeypatch.setenv("PLEXUS_API_URL", "https://example.appsync-api.us-west-2.amazonaws.com/graphql")
    monkeypatch.delenv("PLEXUS_API_KEY", raising=False)
    monkeypatch.delenv("PLEXUS_GRAPHQL_AUTH_MODE", raising=False)
    monkeypatch.setattr(app, "PlexusDashboardClient", FakeClient)

    app._resolve_client()

    assert created == ["https://example.appsync-api.us-west-2.amazonaws.com/graphql"]
    assert app.os.environ["PLEXUS_GRAPHQL_AUTH_MODE"] == "iam"


def test_load_provider_credentials_sets_openai_and_optional_anthropic(monkeypatch):
    app = _load_app_module()
    app._load_provider_credentials.cache_clear()

    class FakeSecretsManager:
        def get_secret_value(self, *, SecretId):
            assert SecretId == "plexus/production/config"
            return {
                "SecretString": json.dumps(
                    {
                        "openai-api-key": "test-openai-key",
                        "anthropic-api-key": "test-anthropic-key",
                    }
                )
            }

    monkeypatch.setenv("PLEXUS_CONFIG_SECRET_NAME", "plexus/production/config")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(app.boto3, "client", lambda service_name: FakeSecretsManager())

    app._load_provider_credentials()

    assert app.os.environ["OPENAI_API_KEY"] == "test-openai-key"
    assert app.os.environ["ANTHROPIC_API_KEY"] == "test-anthropic-key"


def test_load_provider_credentials_allows_missing_anthropic(monkeypatch):
    app = _load_app_module()
    app._load_provider_credentials.cache_clear()

    class FakeSecretsManager:
        def get_secret_value(self, *, SecretId):
            return {"SecretString": json.dumps({"openai-api-key": "test-openai-key"})}

    monkeypatch.setenv("PLEXUS_CONFIG_SECRET_NAME", "plexus/production/config")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(app.boto3, "client", lambda service_name: FakeSecretsManager())

    app._load_provider_credentials()

    assert app.os.environ["OPENAI_API_KEY"] == "test-openai-key"
    assert "ANTHROPIC_API_KEY" not in app.os.environ
