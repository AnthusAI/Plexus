import json
import sys

import pytest

from plexus.logging import cloudwatch_logger


pytestmark = pytest.mark.unit


class _FakeResourceAlreadyExists(Exception):
    pass


class _FakeLogsClient:
    class exceptions:
        ResourceAlreadyExistsException = _FakeResourceAlreadyExists

    def __init__(self) -> None:
        self.create_group_calls = 0
        self.create_stream_calls = 0
        self.put_policy_calls = 0
        self.log_events: list[dict] = []

    def create_log_group(self, **_kwargs) -> None:
        self.create_group_calls += 1

    def create_log_stream(self, **_kwargs) -> None:
        self.create_stream_calls += 1

    def put_data_protection_policy(self, **_kwargs) -> dict:
        self.put_policy_calls += 1
        return {
            "ResponseMetadata": {
                "RequestId": "req-123",
                "HTTPStatusCode": 200,
            }
        }

    def put_log_events(self, **kwargs) -> None:
        self.log_events.append(kwargs)


def _build_logger(client: _FakeLogsClient, invocation_id: str) -> cloudwatch_logger.PlexusCloudWatchLogger:
    logger = cloudwatch_logger.PlexusCloudWatchLogger(
        account_key="call-criteria",
        component_name="console-chat",
        invocation_id=invocation_id,
        log_category="console",
    )
    logger._logs_client = client
    return logger


def test_cloudwatch_logs_client_uses_default_credentials(monkeypatch) -> None:
    calls: list[dict] = []

    class _FakeBoto3:
        @staticmethod
        def client(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return _FakeLogsClient()

    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATESTKEY1234567890")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3)

    logger = cloudwatch_logger.PlexusCloudWatchLogger(
        account_key="call-criteria",
        component_name="console-chat",
        invocation_id="msg-1",
        log_category="console",
    )

    assert logger._logs_client is not None
    assert calls == [{"args": ("logs",), "kwargs": {"region_name": "us-west-2"}}]


def test_cloudwatch_policy_apply_is_idempotent_per_log_group(monkeypatch) -> None:
    monkeypatch.setattr(cloudwatch_logger, "_POLICY_APPLIED_LOG_GROUPS", set())
    client = _FakeLogsClient()

    _build_logger(client, "msg-1").open()
    _build_logger(client, "msg-2").open()

    assert client.put_policy_calls == 1


def test_cloudwatch_open_logs_compact_policy_result(monkeypatch) -> None:
    monkeypatch.setattr(cloudwatch_logger, "_POLICY_APPLIED_LOG_GROUPS", set())
    client = _FakeLogsClient()
    captured: list[str] = []

    def _capture(msg: str, *args) -> None:
        rendered = msg % args if args else msg
        captured.append(rendered)

    monkeypatch.setattr(cloudwatch_logger.logger, "info", _capture)
    _build_logger(client, "msg-1").open()

    assert any("Applied data protection policy to" in line for line in captured)
    assert all("ResponseMetadata" not in line for line in captured)


def test_cloudwatch_open_emits_timing_metrics_event(monkeypatch) -> None:
    monkeypatch.setattr(cloudwatch_logger, "_POLICY_APPLIED_LOG_GROUPS", set())
    client = _FakeLogsClient()

    _build_logger(client, "msg-1").open()

    messages = [
        event["logEvents"][0]["message"]
        for event in client.log_events
        if event.get("logEvents")
    ]
    metric_events = [
        json.loads(message)
        for message in messages
        if '"event": "cloudwatch_open_metrics"' in message
    ]
    assert len(metric_events) == 1
    assert metric_events[0]["timings_ms"]["create_log_group_ms"] >= 0
    assert metric_events[0]["timings_ms"]["apply_policy_ms"] >= 0
    assert metric_events[0]["timings_ms"]["total_ms"] >= 0


def test_cloudwatch_open_fails_closed_without_data_policy(monkeypatch) -> None:
    class _PolicyFailureClient(_FakeLogsClient):
        def put_data_protection_policy(self, **_kwargs) -> dict:
            raise RuntimeError("policy failed")

    monkeypatch.setattr(cloudwatch_logger, "_POLICY_APPLIED_LOG_GROUPS", set())
    client = _PolicyFailureClient()
    logger = _build_logger(client, "msg-1")

    logger.open()

    assert logger._logs_client is None
    assert client.create_stream_calls == 0
    assert client.log_events == []


def test_cloudwatch_put_redacts_message() -> None:
    client = _FakeLogsClient()
    logger = _build_logger(client, "msg-1")

    logger._put(logger._run_stream, "Email person@example.com token=secret")

    message = client.log_events[0]["logEvents"][0]["message"]
    assert "[REDACTED_EMAIL]" in message
    assert "person@example.com" not in message
    assert "token=[REDACTED_SECRET]" in message
