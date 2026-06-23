import logging

import pytest

from plexus import CustomLogging


pytestmark = pytest.mark.unit


class _FakeResourceAlreadyExists(Exception):
    pass


class _FakeLogsClient:
    class exceptions:
        ResourceAlreadyExistsException = _FakeResourceAlreadyExists

    def __init__(self, fail_policy=False):
        self.fail_policy = fail_policy
        self.created_groups = []
        self.policy_groups = []

    def create_log_group(self, logGroupName):
        self.created_groups.append(logGroupName)

    def put_data_protection_policy(self, logGroupIdentifier, policyDocument):
        if self.fail_policy:
            raise RuntimeError("policy failed")
        self.policy_groups.append(logGroupIdentifier)
        return {}


class _FakeWatchtowerHandler(logging.Handler):
    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs


def test_setup_logging_uses_region_only_and_adds_redaction(monkeypatch):
    fake_client = _FakeLogsClient()
    calls = []

    def fake_boto_client(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return fake_client

    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATESTKEY1234567890")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(CustomLogging.boto3, "client", fake_boto_client)
    monkeypatch.setattr(CustomLogging.watchtower, "CloudWatchLogHandler", _FakeWatchtowerHandler)

    CustomLogging.setup_logging("plexus/api/test")

    assert calls == [{"args": ("logs",), "kwargs": {"region_name": "us-west-2"}}]
    assert fake_client.policy_groups == ["plexus/api/test"]
    assert CustomLogging.cloudwatch_handler is not None
    assert CustomLogging.redaction_filter in CustomLogging.cloudwatch_handler.filters


def test_setup_logging_fails_closed_when_policy_fails(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setattr(CustomLogging, "_cloudwatch_logs_client", lambda _region: _FakeLogsClient(fail_policy=True))
    monkeypatch.setattr(CustomLogging.watchtower, "CloudWatchLogHandler", _FakeWatchtowerHandler)

    CustomLogging.setup_logging("plexus/api/test")

    assert CustomLogging.cloudwatch_handler is None


def test_setup_logging_skips_cloudwatch_without_region(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_REGION_NAME", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    CustomLogging.setup_logging("plexus/api/test")

    assert CustomLogging.cloudwatch_handler is None
