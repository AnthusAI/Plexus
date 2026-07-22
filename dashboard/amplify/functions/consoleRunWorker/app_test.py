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


def test_runtime_imports_are_deferred_until_a_direct_message_needs_processing(monkeypatch):
    app = _load_app_module()
    runtime_loads = []

    assert app._console_runtime.cache_info().currsize == 0

    def runtime():
        runtime_loads.append(True)
        return {
            "production_response_target": "cloud",
            "build_response_owner": lambda target, **_kwargs: {"target": target},
            "normalize_response_target": lambda target: target,
            "process_console_message": lambda *_args, **_kwargs: True,
        }

    monkeypatch.setattr(app, "_console_runtime", runtime)
    monkeypatch.setattr(app, "_load_provider_credentials", lambda: None)
    monkeypatch.setattr(app, "_resolve_client", SimpleNamespace)
    monkeypatch.setattr(app, "fetch_console_message", lambda *_args: {"id": "msg-direct"})
    monkeypatch.setattr(app, "process_console_message", lambda *_args, **_kwargs: True)

    assert app.handler({}, SimpleNamespace(aws_request_id="req-empty"))["processed"] == 0
    assert runtime_loads == []

    assert app.handler({"directMessageId": "msg-direct"}, SimpleNamespace(aws_request_id="req-1"))["processed"] == 1
    assert runtime_loads == [True]


def test_lambda_runtime_disables_redundant_custom_cloudwatch_shipping(monkeypatch):
    app = _load_app_module()
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "console-responder")
    monkeypatch.delenv("PLEXUS_DISABLE_CLOUDWATCH_LOGS", raising=False)

    app._prepare_console_runtime_environment()

    assert app.os.environ["PLEXUS_DISABLE_CLOUDWATCH_LOGS"] == "true"


def test_warm_interactive_runtime_prepares_reusable_console_state(monkeypatch):
    app = _load_app_module()
    app._warm_interactive_runtime.cache_clear()
    client = object()
    calls = []

    monkeypatch.setattr(app, "_load_provider_credentials", lambda: calls.append("credentials"))
    monkeypatch.setattr(app, "_resolve_client", lambda: client)
    monkeypatch.setattr(
        app,
        "_console_runtime",
        lambda: {"warm_console_runtime": lambda value: calls.append(("warm", value))},
    )

    app._warm_interactive_runtime()
    app._warm_interactive_runtime()

    assert calls == ["credentials", ("warm", client)]


def test_handler_ignores_legacy_stream_payload(monkeypatch):
    app = _load_app_module()
    calls = []

    result = app.handler({"Records": [_stream_record()]}, SimpleNamespace(aws_request_id="req-1"))
    assert result["processed"] == 0
    assert result["skipped"] == 0
    assert result["batchItemFailures"] == []
    assert calls == []


def test_handler_processes_direct_message_without_waiting_for_a_stream_record(monkeypatch):
    app = _load_app_module()
    calls = []

    monkeypatch.setenv("CONSOLE_RESPONSE_TARGET", "cloud")
    monkeypatch.delenv("PLEXUS_LAMBDA_REQUEST_ID", raising=False)
    monkeypatch.setattr(app, "_load_provider_credentials", lambda: None)
    monkeypatch.setattr(app, "_resolve_client", SimpleNamespace)
    monkeypatch.setattr(
        app,
        "fetch_console_message",
        lambda _client, message_id: {**_stream_record()["dynamodb"]["NewImage"], "id": message_id},
    )
    monkeypatch.setattr(
        app,
        "process_console_message",
        lambda _client, message, **kwargs: calls.append((message, kwargs)) or True,
    )

    result = app.handler({"directMessageId": "msg-direct"}, SimpleNamespace(aws_request_id="req-direct"))

    assert result == {"processed": 1, "skipped": 0, "batchItemFailures": []}
    assert calls[0][0]["id"] == "msg-direct"
    assert calls[0][1]["expected_target"] == "cloud"
    assert isinstance(calls[0][1]["poll_context"]["direct_message_fetch_ms"], int)
    assert "PLEXUS_LAMBDA_REQUEST_ID" not in app.os.environ


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
    assert result["skipped"] == 0
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
    assert result["skipped"] == 0


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
    assert result["batchItemFailures"] == []


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
    assert result["skipped"] == 0


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

    assert result["processed"] == 0
    assert result["skipped"] == 0
    assert result["batchItemFailures"] == []


def test_resolve_client_uses_iam_auth_without_api_key(monkeypatch):
    app = _load_app_module()
    created = []

    class FakeClient:
        def __init__(self, *, api_url, context):
            created.append((api_url, context.account_key))

    monkeypatch.setenv("PLEXUS_API_URL", "https://example.appsync-api.us-west-2.amazonaws.com/graphql")
    monkeypatch.setenv("PLEXUS_GRAPHQL_AUTH_MODE", "iam")
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "call-criteria")
    monkeypatch.delenv("PLEXUS_API_KEY", raising=False)
    monkeypatch.setattr(app, "PlexusDashboardClient", FakeClient)

    app._resolve_client()

    assert created == [("https://example.appsync-api.us-west-2.amazonaws.com/graphql", "call-criteria")]


def test_resolve_client_requires_iam_auth_mode(monkeypatch):
    app = _load_app_module()

    monkeypatch.setenv("PLEXUS_API_URL", "https://example.appsync-api.us-west-2.amazonaws.com/graphql")
    monkeypatch.delenv("PLEXUS_GRAPHQL_AUTH_MODE", raising=False)

    try:
        app._resolve_client()
    except RuntimeError as exc:
        assert "PLEXUS_GRAPHQL_AUTH_MODE must be iam" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


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
