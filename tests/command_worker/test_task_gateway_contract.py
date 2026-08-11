"""Contract evidence for the conditional AppSync Task gateway."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from plexus.command_worker import (
    CommandRecord,
    CommandStatus,
    ProgressUpdate,
    request_digest,
)
from plexus.command_worker.adapters.task_store import GraphQLTaskStoreGateway

NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


class RecordingConditionalClient:
    """Small AppSync generated-model double with conditional failure results."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.tasks: dict[str, dict] = {}
        self.raise_conditional = False

    def execute(self, document: str, variables: dict) -> dict:
        self.calls.append((document, variables))
        if "query GetTask" in document:
            return {"getTask": self.tasks.get(variables["id"])}
        if "mutation CreateTask" in document:
            task = variables["input"]
            if task["id"] in self.tasks:
                if self.raise_conditional:
                    raise Exception(
                        "GraphQL query failed: The conditional request failed"
                    )
                return {"errors": [{"errorType": "ConditionalCheckFailedException"}]}
            self.tasks[task["id"]] = dict(task)
            return {"createTask": self.tasks[task["id"]]}
        if "mutation UpdateTask" in document:
            task = self.tasks[variables["input"]["id"]]
            condition = variables["condition"]
            fence = condition.get("fencingToken", {}).get("eq")
            if fence is not None and task.get("fencingToken") != fence:
                if self.raise_conditional:
                    raise Exception(
                        "GraphQL query failed: The conditional request failed"
                    )
                return {"errors": [{"message": "The conditional request failed"}]}
            task.update(variables["input"])
            return {"updateTask": task}
        raise AssertionError(document)


def _command() -> CommandRecord:
    return CommandRecord(
        command_id="task-1",
        tenant_id="tenant-1",
        target="evaluate",
        idempotency_key="key-1",
        idempotency_namespace="command.submit:v1",
        created_at=NOW,
        updated_at=NOW,
        submitted_by="principal-1",
        payload={"argv": ["evaluate"]},
        status=CommandStatus.ANNOUNCED,
        request_digest=request_digest("evaluate", {"argv": ["evaluate"]}),
    )


def _fields() -> dict[str, str]:
    return {"accountId": "account-1", "type": "evaluate", "command": "evaluate"}


def test_gateway_uses_conditional_create_and_fenced_lifecycle_mutations() -> None:
    client = RecordingConditionalClient()
    gateway = GraphQLTaskStoreGateway(client)
    command = _command()

    assert gateway.announce_task(command, _fields()).disposition.value == "NEW"
    claim = gateway.claim_task(command.envelope, "worker-1", NOW, timedelta(minutes=1))
    assert claim.token == "1"
    assert gateway.progress_task(
        "task-1",
        claim.token,
        ProgressUpdate(0.5, "halfway", {"processed": 5, "total": 10}),
        NOW,
    )
    assert not gateway.complete_task("task-1", "0", {"stale": True}, NOW)
    assert gateway.complete_task("task-1", "1", {"ok": True}, NOW)

    create_document, create_variables = client.calls[0]
    assert "ModelTaskConditionInput" in create_document
    assert create_variables["input"]["commandPayload"] == json.dumps(
        {"argv": ["evaluate"]}, separators=(",", ":")
    )
    completion_variables = next(
        variables
        for document, variables in reversed(client.calls)
        if "UpdateTask" in document and "commandResult" in variables["input"]
    )
    assert completion_variables["input"]["commandResult"] == json.dumps(
        {"ok": True}, separators=(",", ":")
    )
    update_documents = [
        document for document, _ in client.calls if "UpdateTask" in document
    ]
    assert update_documents and all(
        "condition: $condition" in document for document in update_documents
    )
    assert not any("TaskStage" in document for document, _ in client.calls)
    assert client.tasks["task-1"]["status"] == "COMPLETED"


def test_gateway_uses_authenticated_tenant_as_task_account_id() -> None:
    client = RecordingConditionalClient()
    gateway = GraphQLTaskStoreGateway(client)

    gateway.announce_task(_command(), {**_fields(), "accountId": "untrusted"})

    assert client.tasks["task-1"]["accountId"] == "tenant-1"
    assert "tenantId" not in client.tasks["task-1"]


def test_gateway_recovers_expired_cancellation_as_task_terminal_state() -> None:
    client = RecordingConditionalClient()
    gateway = GraphQLTaskStoreGateway(client)
    command = _command()
    gateway.announce_task(command, _fields())
    claim = gateway.claim_task(command.envelope, "worker-1", NOW, timedelta(minutes=1))
    assert gateway.request_task_cancel("tenant-1", "task-1", NOW).changed
    assert (
        gateway.claim_task(
            command.envelope,
            "worker-2",
            NOW + timedelta(minutes=2),
            timedelta(minutes=1),
        ).value
        == "terminal"
    )
    assert client.tasks["task-1"]["lifecycleStatus"] == "CANCELLED"
    assert claim.token == "1"


def test_gateway_normalizes_conditional_graphql_exceptions() -> None:
    client = RecordingConditionalClient()
    gateway = GraphQLTaskStoreGateway(client)
    command = _command()
    gateway.announce_task(command, _fields())
    client.raise_conditional = True

    duplicate = gateway.announce_task(command, _fields())
    assert duplicate.disposition.value == "EXISTING"
    claim = gateway.claim_task(command.envelope, "worker-1", NOW, timedelta(minutes=1))
    assert claim.token == "1"
    assert not gateway.complete_task("task-1", "0", {"stale": True}, NOW)


def test_gateway_accepts_awsjson_string_payloads_from_get_task() -> None:
    client = RecordingConditionalClient()
    gateway = GraphQLTaskStoreGateway(client)
    command = _command()

    gateway.announce_task(command, _fields())
    client.tasks["task-1"]["commandPayload"] = '{"argv":["evaluate"]}'

    record = gateway.get_command("tenant-1", "task-1")
    assert record is not None
    assert dict(record.payload) == {"argv": ("evaluate",)}


def test_gateway_accepts_double_encoded_awsjson_payloads_from_get_task() -> None:
    client = RecordingConditionalClient()
    gateway = GraphQLTaskStoreGateway(client)
    command = _command()

    gateway.announce_task(command, _fields())
    client.tasks["task-1"]["commandPayload"] = '"{\\"argv\\":[\\"evaluate\\"]}"'

    record = gateway.get_command("tenant-1", "task-1")
    assert record is not None
    assert dict(record.payload) == {"argv": ("evaluate",)}


def test_dispatcher_and_gateway_preserve_awsjson_payload_integrity() -> None:
    dispatcher_path = (
        Path(__file__).resolve().parents[2]
        / "dashboard"
        / "amplify"
        / "functions"
        / "taskDispatcher"
        / "index.py"
    )
    spec = importlib.util.spec_from_file_location(
        "task_dispatcher_contract", dispatcher_path
    )
    assert spec and spec.loader
    dispatcher = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = dispatcher
    spec.loader.exec_module(dispatcher)

    payload = {"argv": ["evaluate", "feedback"], "task_id": "task-1"}
    task = {
        "id": "task-1",
        "accountId": "tenant-1",
        "target": "evaluation",
        "idempotencyKey": "key-1",
        "createdAt": NOW.isoformat(),
        "commandPayload": '{"argv":["evaluate","feedback"],"task_id":"task-1"}',
    }
    message = dispatcher.envelope(task)
    assert message["payload"] == payload

    class ReadOnlyTaskClient:
        def execute(self, document: str, variables: dict) -> dict:
            if "query GetTask" not in document:
                raise AssertionError(document)
            return {
                "getTask": {
                    "id": "task-1",
                    "accountId": "tenant-1",
                    "target": "evaluation",
                    "idempotencyKey": "key-1",
                    "idempotencyNamespace": "command.submit:v1",
                    "submittedBy": "principal-1",
                    "createdAt": NOW.isoformat(),
                    "updatedAt": NOW.isoformat(),
                    "lifecycleStatus": "ANNOUNCED",
                    "digestAlgorithm": "sha256",
                    "digestCanonicalizationVersion": 1,
                    "idempotencyDigest": request_digest(
                        "evaluation", payload
                    ).value,
                    "commandPayload": '"{\\"argv\\":[\\"evaluate\\",\\"feedback\\"],\\"task_id\\":\\"task-1\\"}"',
                }
            }

    gateway = GraphQLTaskStoreGateway(ReadOnlyTaskClient())
    command = gateway.get_command("tenant-1", "task-1")
    assert command is not None
    assert dict(command.payload) == {"argv": ("evaluate", "feedback"), "task_id": "task-1"}
    assert command.request_digest == request_digest(command.target, command.payload)
