import logging

import pytest

from plexus import CustomLogging


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _enable_cloudwatch_logging_for_each_test(monkeypatch):
    """Keep these tests independent of Lambda-specific process state."""
    monkeypatch.delenv("PLEXUS_DISABLE_CLOUDWATCH_LOGS", raising=False)


class _FakeResourceAlreadyExists(Exception):
    pass


class _FakeLogsClient:
    class exceptions:
        ResourceAlreadyExistsException = _FakeResourceAlreadyExists

    def __init__(self, fail_policy=False, access_denied_policy=False):
        self.fail_policy = fail_policy
        self.access_denied_policy = access_denied_policy
        self.created_groups = []
        self.policy_groups = []

    def create_log_group(self, logGroupName):
        self.created_groups.append(logGroupName)

    def put_data_protection_policy(self, logGroupIdentifier, policyDocument):
        if self.access_denied_policy:
            raise RuntimeError(
                "An error occurred (AccessDeniedException) when calling the "
                "PutDataProtectionPolicy operation: not authorized"
            )
        if self.fail_policy:
            raise RuntimeError("policy failed")
        self.policy_groups.append(logGroupIdentifier)
        return {}


class _FakeWatchtowerHandler(logging.Handler):
    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs
        self.records = []

    def emit(self, record):
        self.records.append(record)


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
    assert CustomLogging.root_cloudwatch_handler is None


def test_setup_logging_can_attach_redacting_cloudwatch_to_root(monkeypatch):
    fake_client = _FakeLogsClient()
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    calls = []

    def fake_boto_client(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return fake_client

    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setattr(CustomLogging.boto3, "client", fake_boto_client)
    monkeypatch.setattr(CustomLogging.watchtower, "CloudWatchLogHandler", _FakeWatchtowerHandler)

    try:
        CustomLogging.setup_logging("plexus/api/test", attach_root=True)

        assert calls == [{"args": ("logs",), "kwargs": {"region_name": "us-west-2"}}]
        assert fake_client.policy_groups == ["plexus/api/test"]
        assert CustomLogging.cloudwatch_handler is not None
        assert CustomLogging.root_cloudwatch_handler is not None
        assert CustomLogging.root_cloudwatch_handler in root_logger.handlers
        assert CustomLogging.redaction_filter in CustomLogging.root_cloudwatch_handler.filters
        assert CustomLogging.root_cloudwatch_handler.kwargs["log_group_name"] == "plexus/api/test"
        assert CustomLogging.root_cloudwatch_handler.kwargs["log_stream_name"].endswith("-root")
    finally:
        if CustomLogging.root_cloudwatch_handler in root_logger.handlers:
            root_logger.removeHandler(CustomLogging.root_cloudwatch_handler)
        root_logger.handlers[:] = original_handlers
        CustomLogging.root_cloudwatch_handler = None


def test_set_log_group_reattaches_root_handler_when_framework_removed_it(monkeypatch):
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    setup_calls = []

    monkeypatch.setattr(CustomLogging, "_get_aws_logging_config", lambda: ("us-west-2", True))

    def fake_setup_logging(log_group_name, attach_root=False):
        setup_calls.append((log_group_name, attach_root))
        CustomLogging.current_log_group_name = log_group_name
        CustomLogging.root_cloudwatch_handler = _FakeWatchtowerHandler(log_group_name=log_group_name)
        if attach_root:
            root_logger.addHandler(CustomLogging.root_cloudwatch_handler)

    monkeypatch.setattr(CustomLogging, "setup_logging", fake_setup_logging)
    monkeypatch.delenv("environment", raising=False)

    try:
        CustomLogging.set_log_group("plexus/api/test", attach_root=True)
        root_logger.removeHandler(CustomLogging.root_cloudwatch_handler)

        CustomLogging.set_log_group("plexus/api/test", attach_root=True)

        assert setup_calls == [
            ("plexus/api/test", True),
            ("plexus/api/test", True),
        ]
        assert CustomLogging.root_cloudwatch_handler in root_logger.handlers
    finally:
        if CustomLogging.root_cloudwatch_handler in root_logger.handlers:
            root_logger.removeHandler(CustomLogging.root_cloudwatch_handler)
        root_logger.handlers[:] = original_handlers
        CustomLogging.root_cloudwatch_handler = None


def test_setup_logging_fails_closed_when_policy_fails(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setattr(CustomLogging, "_cloudwatch_logs_client", lambda _region: _FakeLogsClient(fail_policy=True))
    monkeypatch.setattr(CustomLogging.watchtower, "CloudWatchLogHandler", _FakeWatchtowerHandler)

    CustomLogging.setup_logging("plexus/api/test")

    assert CustomLogging.cloudwatch_handler is None


def test_setup_logging_warns_concisely_when_policy_permission_missing(monkeypatch):
    warnings = []
    errors = []
    plexus_logger = logging.getLogger("plexus")

    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setattr(
        CustomLogging,
        "_cloudwatch_logs_client",
        lambda _region: _FakeLogsClient(access_denied_policy=True),
    )
    monkeypatch.setattr(CustomLogging.watchtower, "CloudWatchLogHandler", _FakeWatchtowerHandler)
    monkeypatch.setattr(plexus_logger, "warning", lambda message, *args, **_kwargs: warnings.append(message % args))
    monkeypatch.setattr(plexus_logger, "error", lambda message, *args, **_kwargs: errors.append(message % args if args else message))

    CustomLogging.setup_logging("plexus/api/test")

    assert CustomLogging.cloudwatch_handler is None
    assert warnings == [
        "CloudWatch logging disabled for plexus/api/test: missing logs:PutDataProtectionPolicy permission"
    ]
    assert errors == []


def test_setup_logging_skips_cloudwatch_without_region(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_REGION_NAME", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    CustomLogging.setup_logging("plexus/api/test")

    assert CustomLogging.cloudwatch_handler is None
