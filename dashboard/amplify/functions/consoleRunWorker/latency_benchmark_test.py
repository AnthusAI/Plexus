from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_benchmark_module():
    benchmark_path = Path(__file__).with_name("latency_benchmark.py")
    spec = importlib.util.spec_from_file_location("console_latency_benchmark", benchmark_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cloud_benchmark_dispatches_each_persisted_message_to_the_responder(monkeypatch):
    benchmark = _load_benchmark_module()
    invocations = []

    class LambdaClient:
        def invoke(self, **kwargs):
            invocations.append(kwargs)

    monkeypatch.setattr(benchmark.boto3, "client", lambda service, **kwargs: LambdaClient())

    benchmark._dispatch_responder_message(
        message_id="message-123",
        responder_function="sandbox-responder:interactive",
        aws_region="us-east-1",
    )

    assert len(invocations) == 1
    invocation = invocations[0]
    assert invocation["FunctionName"] == "sandbox-responder:interactive"
    assert invocation["InvocationType"] == "Event"
    assert invocation["Payload"] == json.dumps({"directMessageId": "message-123"}).encode("utf-8")


def test_cloud_benchmark_can_use_the_console_dispatcher_path(monkeypatch):
    benchmark = _load_benchmark_module()
    invocations = []

    class LambdaClient:
        def invoke(self, **kwargs):
            invocations.append(kwargs)
            return {"FunctionError": None, "Payload": None}

    monkeypatch.setattr(benchmark.boto3, "client", lambda service, **kwargs: LambdaClient())

    benchmark._dispatch_console_message(
        message_id="message-456",
        dispatcher_function="sandbox-dispatcher",
        aws_region="us-east-1",
    )

    assert len(invocations) == 1
    invocation = invocations[0]
    assert invocation["FunctionName"] == "sandbox-dispatcher"
    assert invocation["InvocationType"] == "RequestResponse"
    assert invocation["Payload"] == json.dumps({"arguments": {"messageId": "message-456"}}).encode("utf-8")


def test_cloud_benchmark_rejects_a_run_that_would_leave_messages_pending():
    benchmark = _load_benchmark_module()

    with pytest.raises(RuntimeError, match="--responder-function or --dispatcher-function is required"):
        benchmark.run_benchmark(
            client=object(),
            account_id="account-123",
            session_id="session-123",
            response_target="cloud",
            model="gpt-5.4-mini",
            samples=1,
            timeout_seconds=1,
            poll_interval_seconds=0,
            procedure_id="builtin:console/chat",
        )
