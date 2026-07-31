"""Contract tests for the GraphQL boundary used by optimizer child dispatch.

These tests deliberately exercise the real query/mutation shapes and their
variables with a recording GraphQL executor.  The state machine itself is
specified separately in :mod:`optimizer_dispatch_test`; this module proves
the production adapter provides its durable, fail-closed protocol.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from graphql import parse, print_ast
from graphql.language.ast import InputObjectTypeDefinitionNode, ObjectTypeDefinitionNode


ACCOUNT_ID = "account-opaque"
PROCEDURE_ID = "procedure-generated"
TASK_ID = "task-generated"


def _procedure(*, procedure_id: str = PROCEDURE_ID, metadata: Any | None = None) -> dict[str, Any]:
    return {
        "id": procedure_id,
        "accountId": ACCOUNT_ID,
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "name": "Feedback alignment optimizer",
        "category": "optimizer",
        "version": "optimizer-task-dispatch-v1",
        "featured": False,
        "isTemplate": False,
        "status": "RUNNING",
        "metadata": metadata if metadata is not None else {},
        "createdAt": "2026-07-30T12:00:00Z",
        "updatedAt": "2026-07-30T12:00:00Z",
    }


def _task(*, task_id: str = TASK_ID, metadata: Any | None = None) -> dict[str, Any]:
    return {
        "id": task_id,
        "accountId": ACCOUNT_ID,
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "type": "Procedure",
        "status": "PENDING",
        "target": f"procedure/{PROCEDURE_ID}",
        "command": f"procedure run {PROCEDURE_ID}",
        "dispatchStatus": "HELD",
        "celeryTaskId": None,
        "metadata": metadata if metadata is not None else {},
        "createdAt": "2026-07-30T12:00:00Z",
        "updatedAt": "2026-07-30T12:00:00Z",
    }


class _RecordingClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def execute(self, query: str, variables: dict[str, Any] | None = None, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append((query, deepcopy(variables)))
        if not self.responses:
            raise AssertionError(f"unexpected GraphQL request: {query}")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return deepcopy(response)


class _ArtifactStore:
    def __init__(self, *, payload: bytes) -> None:
        self.payload = payload
        self.uploads: list[Any] = []
        self.downloads: list[Any] = []

    def upload_batch(self, uploads):
        self.uploads.extend(uploads)
        upload = uploads[0]
        request = upload.request
        return [{
            "_s3_key": f"procedures/{request.resource_id}/{request.filename}",
            "sha256": request.sha256,
            "size_bytes": request.size_bytes,
            "content_type": request.content_type,
        }]

    def download_batch(self, requests):
        self.downloads.extend(requests)
        return [self.payload]


def _adapter(client: _RecordingClient, *, artifact_store: Any | None = None):
    from plexus.optimization.optimizer_dispatch_backend import GraphQLOptimizerDispatchBackend

    return GraphQLOptimizerDispatchBackend(
        client,
        artifact_store=artifact_store,
        page_size=2,
    )


def _dispatch_request() -> dict[str, Any]:
    return {
        "account_id": ACCOUNT_ID,
        "run_key": "run-key",
        "scorecard_id": "scorecard-opaque",
        "score_id": "score-opaque",
        "assessment_fingerprint": "assessment-fingerprint",
        "limits": {
            "max_cost_usd": 5.0,
            "max_samples": 50,
            "max_iterations": 2,
            "max_concurrency": 1,
        },
        "optimizer_yaml": "name: optimizer\n",
        "stages": [],
    }


def test_account_scans_are_exhaustive_paginated_and_map_json_metadata() -> None:
    client = _RecordingClient([
        {"listProcedureByAccountIdUpdatedAt": {
            "items": [_procedure(metadata=json.dumps({"marker": "first"}))],
            "nextToken": "next-procedures",
        }},
        {"listProcedureByAccountIdUpdatedAt": {
            "items": [_procedure(procedure_id="procedure-second")], "nextToken": None,
        }},
        {"listTaskByAccountIdUpdatedAt": {
            "items": [_task(metadata=json.dumps({"marker": "first"}))],
            "nextToken": "next-tasks",
        }},
        {"listTaskByAccountIdUpdatedAt": {
            "items": [_task(task_id="task-second")], "nextToken": None,
        }},
    ])
    backend = _adapter(client)

    procedures = list(backend.procedure_pages_for_account(ACCOUNT_ID))
    tasks = list(backend.task_pages_for_account(ACCOUNT_ID))

    assert [page["items"][0]["id"] for page in procedures] == [PROCEDURE_ID, "procedure-second"]
    assert procedures[0]["items"][0]["metadata"] == json.dumps({"marker": "first"})
    assert [page["items"][0]["id"] for page in tasks] == [TASK_ID, "task-second"]
    assert tasks[0]["items"][0]["metadata"] == json.dumps({"marker": "first"})
    assert "listProcedureByAccountIdUpdatedAt" in client.calls[0][0]
    assert client.calls[0][1] == {
        "accountId": ACCOUNT_ID,
        "updatedAt": {"ge": "2000-01-01T00:00:00.000Z"},
        "sortDirection": "DESC",
        "limit": 2,
        "nextToken": None,
    }
    assert client.calls[1][1]["nextToken"] == "next-procedures"
    assert "listTaskByAccountIdUpdatedAt" in client.calls[2][0]
    assert client.calls[3][1]["nextToken"] == "next-tasks"


@pytest.mark.parametrize("connection", [
    {},
    {"items": "not-a-list", "nextToken": None},
    {"items": [], "nextToken": 42},
])
def test_malformed_account_page_fails_closed(connection: dict[str, Any]) -> None:
    client = _RecordingClient([{"listProcedureByAccountIdUpdatedAt": connection}])

    with pytest.raises(RuntimeError, match="procedure account scan"):
        list(_adapter(client).procedure_pages_for_account(ACCOUNT_ID))


def test_repeated_pagination_token_fails_closed_without_requesting_a_cycle() -> None:
    client = _RecordingClient([
        {"listTaskByAccountIdUpdatedAt": {"items": [], "nextToken": "repeat"}},
        {"listTaskByAccountIdUpdatedAt": {"items": [], "nextToken": "repeat"}},
    ])

    with pytest.raises(RuntimeError, match="pagination token cycle"):
        list(_adapter(client).task_pages_for_account(ACCOUNT_ID))

    assert len(client.calls) == 2


def test_real_adapter_skips_malformed_optimizer_metadata_on_unrelated_legacy_row() -> None:
    from plexus.optimization.optimizer_dispatch import OptimizerTaskDispatchService

    request = _dispatch_request()
    bootstrap = OptimizerTaskDispatchService(_adapter(_RecordingClient([])))
    planned = bootstrap.step(request, None, may_mutate=False)
    attempted = bootstrap.step(request, planned, may_mutate=False)
    exact = _procedure(metadata=json.dumps({
        "optimizer_launch_spec": planned["launch_spec"],
    }))
    unrelated = _procedure(
        procedure_id="legacy-unrelated",
        metadata="{optimizer_launch_spec: broken legacy json",
    )
    unrelated["scoreId"] = "other-score"
    client = _RecordingClient([
        {"listProcedureByAccountIdUpdatedAt": {
            "items": [unrelated], "nextToken": "exact",
        }},
        {"listProcedureByAccountIdUpdatedAt": {
            "items": [exact], "nextToken": None,
        }},
    ])

    observed = OptimizerTaskDispatchService(_adapter(client)).step(
        request, attempted, may_mutate=False,
    )

    assert observed["phase"] == "procedure_record_observed"
    assert observed["procedure_id"] == PROCEDURE_ID
    assert observed["procedure"]["metadata"] == exact["metadata"]


def test_graphql_operations_validate_against_checked_in_amplify_contract() -> None:
    schema_path = (
        Path(__file__).parents[2]
        / "services/private-graphql-proxy/schema/amplify.graphql"
    )
    # Parse the checked-in contract directly. Its generated model types omit
    # implicit Amplify id fields and reference enums from another fragment, so
    # a focused AST contract comparison is more accurate than fabricating a
    # globally valid standalone schema.
    schema_document = parse(schema_path.read_text(encoding="utf-8"))
    object_types = {
        definition.name.value: definition
        for definition in schema_document.definitions
        if isinstance(definition, ObjectTypeDefinitionNode)
    }
    input_types = {
        definition.name.value: definition
        for definition in schema_document.definitions
        if isinstance(definition, InputObjectTypeDefinitionNode)
    }
    task_metadata = {
        "procedure_id": PROCEDURE_ID,
        "dispatch_policy": "held_once",
    }
    held_task = _task(metadata=task_metadata)
    pending_task = _task(metadata=task_metadata)
    pending_task["dispatchStatus"] = "PENDING"
    updated_procedure = _procedure(metadata={"updated": True})
    created_stage = {
        "id": "stage-generated", "taskId": TASK_ID, "name": "Setup",
        "order": 1, "status": "PENDING", "statusMessage": None,
    }
    client = _RecordingClient([
        {"listProcedureByAccountIdUpdatedAt": {"items": [], "nextToken": None}},
        {"listTaskByAccountIdUpdatedAt": {"items": [], "nextToken": None}},
        {"createProcedure": _procedure(metadata={"optimizer_launch_spec": {"id": "launch"}})},
        {"getProcedure": _procedure()},
        {"updateProcedure": updated_procedure},
        {"createTask": held_task},
        {"getTask": held_task},
        {"getTask": held_task},
        {"updateTask": pending_task},
        {"listTaskStageByTaskId": {"items": [], "nextToken": None}},
        {"createTaskStage": created_stage},
    ])
    backend = _adapter(client)

    list(backend.procedure_pages_for_account(ACCOUNT_ID))
    list(backend.task_pages_for_account(ACCOUNT_ID))
    backend.create_procedure({
        "accountId": ACCOUNT_ID,
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "name": "Feedback alignment optimizer",
        "category": "optimizer",
        "version": "optimizer-task-dispatch-v1",
        "featured": False,
        "isTemplate": False,
        "status": "RUNNING",
        "metadata": {"optimizer_launch_spec": {"id": "launch"}},
    })
    create_input = client.calls[-1][1]["input"]
    backend.get_procedure(PROCEDURE_ID)
    backend._update_procedure_metadata(PROCEDURE_ID, {"updated": True})
    backend.create_task({
        "accountId": ACCOUNT_ID,
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "type": "Procedure",
        "status": "PENDING",
        "target": f"procedure/{PROCEDURE_ID}",
        "command": f"procedure run {PROCEDURE_ID}",
        "dispatchStatus": "HELD",
        "metadata": task_metadata,
    })
    backend.get_task(TASK_ID)
    backend.release_held_task(TASK_ID)
    list(backend.task_stage_pages_for_task(TASK_ID))
    backend._create_task_stage(
        TASK_ID, {"name": "Setup", "order": 1, "status": "PENDING"}
    )

    for query, _variables in client.calls:
        operation = parse(query).definitions[0]
        root_name = "Query" if operation.operation.value == "query" else "Mutation"
        root_fields = {field.name.value: field for field in object_types[root_name].fields}
        selected_field = operation.selection_set.selections[0]
        assert selected_field.name.value in root_fields
        contract_arguments = {
            argument.name.value: print_ast(argument.type)
            for argument in root_fields[selected_field.name.value].arguments
        }
        for variable in operation.variable_definitions:
            assert print_ast(variable.type) == contract_arguments[variable.variable.name.value]
    procedure_input_fields = {
        field.name.value: print_ast(field.type)
        for field in input_types["CreateProcedureInput"].fields
    }
    assert procedure_input_fields["createdAt"] == "AWSDateTime!"
    assert procedure_input_fields["updatedAt"] == "AWSDateTime!"
    assert create_input["createdAt"].endswith("Z")
    assert create_input["updatedAt"] == create_input["createdAt"]


def test_create_records_use_server_generated_ids_and_physical_identity() -> None:
    launch_spec = {"identity": "launch-identity", "account_id": ACCOUNT_ID}
    procedure = _procedure(metadata={"optimizer_launch_spec": launch_spec})
    task = _task(metadata={"procedure_id": PROCEDURE_ID})
    client = _RecordingClient([
        {"createProcedure": procedure},
        {"createTask": task},
    ])
    backend = _adapter(client)

    created_procedure = backend.create_procedure({
        "accountId": ACCOUNT_ID,
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "name": "Feedback alignment optimizer",
        "category": "optimizer",
        "version": "optimizer-task-dispatch-v1",
        "featured": False,
        "isTemplate": False,
        "status": "RUNNING",
        "metadata": {"optimizer_launch_spec": launch_spec},
    })
    created_task = backend.create_task({
        "accountId": ACCOUNT_ID,
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "type": "Procedure",
        "status": "PENDING",
        "target": f"procedure/{PROCEDURE_ID}",
        "command": f"procedure run {PROCEDURE_ID}",
        "dispatchStatus": "HELD",
        "metadata": {"procedure_id": PROCEDURE_ID},
    })

    procedure_input = client.calls[0][1]["input"]
    task_input = client.calls[1][1]["input"]
    assert "id" not in procedure_input and "id" not in task_input
    assert procedure_input["accountId"] == ACCOUNT_ID
    assert procedure_input["scorecardId"] == "scorecard-opaque"
    assert procedure_input["scoreId"] == "score-opaque"
    assert procedure_input["category"] == "optimizer"
    assert procedure_input["version"] == "optimizer-task-dispatch-v1"
    assert json.loads(procedure_input["metadata"]) == {"optimizer_launch_spec": launch_spec}
    assert task_input["dispatchStatus"] == "HELD"
    assert task_input["target"] == f"procedure/{PROCEDURE_ID}"
    assert task_input["command"] == f"procedure run {PROCEDURE_ID}"
    assert created_procedure["id"] == PROCEDURE_ID
    assert created_task["id"] == TASK_ID


def test_create_procedure_decodes_matching_awsjson_metadata_before_comparison() -> None:
    launch_spec = {"identity": "launch-identity", "account_id": ACCOUNT_ID}
    client = _RecordingClient([{"createProcedure": _procedure(
        metadata=json.dumps({"optimizer_launch_spec": launch_spec})
    )}])

    created = _adapter(client).create_procedure({
        "accountId": ACCOUNT_ID,
        "scorecardId": "scorecard-opaque",
        "scoreId": "score-opaque",
        "name": "Feedback alignment optimizer",
        "category": "optimizer",
        "version": "optimizer-task-dispatch-v1",
        "featured": False,
        "isTemplate": False,
        "status": "RUNNING",
        "metadata": {"optimizer_launch_spec": launch_spec},
    })

    assert json.loads(created["metadata"])["optimizer_launch_spec"] == launch_spec


def test_procedure_yaml_uses_supported_procedure_attachment_route_and_readback() -> None:
    yaml_text = "name: optimizer\n" + ("# body\n" * 80_000)
    payload = yaml_text.encode("utf-8")
    checksum = hashlib.sha256(payload).hexdigest()
    existing = _procedure()
    updated = _procedure(metadata={
        "optimizer_launch_spec": {"identity": "launch-identity"},
        "optimizer_yaml_sha256": checksum,
        "code_artifact": {
            "key": f"procedures/{PROCEDURE_ID}/code.tac",
            "_s3_key": f"procedures/{PROCEDURE_ID}/code.tac",
            "sha256": checksum,
            "size_bytes": len(payload),
            "content_type": "text/plain",
        },
    })
    client = _RecordingClient([
        {"updateProcedure": updated},
        {"getProcedure": updated},
    ])
    store = _ArtifactStore(payload=payload)

    persisted = _adapter(client, artifact_store=store).upload_and_verify_procedure_yaml(
        existing,
        yaml_text,
        {
            "optimizer_launch_spec": {"identity": "launch-identity"},
            "optimizer_yaml_sha256": checksum,
        },
    )

    upload_request = store.uploads[0].request
    assert upload_request.resource_type == "PROCEDURE"
    assert upload_request.artifact_type == "PROCEDURE_ATTACHMENT"
    assert upload_request.resource_id == PROCEDURE_ID
    assert upload_request.filename == "code.tac"
    assert persisted["metadata"]["code_artifact"]["key"] == f"procedures/{PROCEDURE_ID}/code.tac"
    update_input = client.calls[0][1]["input"]
    assert update_input["id"] == PROCEDURE_ID
    assert json.loads(update_input["metadata"])["code_artifact"]["_s3_key"] == f"procedures/{PROCEDURE_ID}/code.tac"
    assert store.downloads[0].artifact_type == "PROCEDURE_ATTACHMENT"
    assert store.downloads[0].resource_type == "PROCEDURE"


def test_bad_procedure_attachment_pointer_or_readback_fails_closed() -> None:
    yaml_text = "name: optimizer\n"
    checksum = hashlib.sha256(yaml_text.encode()).hexdigest()
    procedure = _procedure(metadata={
        "optimizer_launch_spec": {"identity": "launch-identity"},
        "optimizer_yaml_sha256": checksum,
        "code_artifact": {
            "key": "procedures/other/code.tac",
            "_s3_key": "procedures/other/code.tac",
            "sha256": checksum,
            "size_bytes": len(yaml_text.encode()),
            "content_type": "text/plain",
        },
    })
    client = _RecordingClient([{"getProcedure": procedure}])

    with pytest.raises(RuntimeError, match="outside the procedure namespace"):
        _adapter(client, artifact_store=_ArtifactStore(payload=yaml_text.encode())).read_procedure_artifact(
            f"procedures/{PROCEDURE_ID}/code.tac"
        )


def test_task_stage_reconciliation_is_paginated_idempotent_and_readable() -> None:
    task = _task()
    client = _RecordingClient([
        {"listTaskStageByTaskId": {"items": [{
            "id": "stage-setup", "taskId": TASK_ID, "name": "Setup", "order": 1,
            "status": "PENDING", "statusMessage": None,
        }], "nextToken": "more"}},
        {"listTaskStageByTaskId": {"items": [], "nextToken": None}},
        {"createTaskStage": {
            "id": "stage-optimize", "taskId": TASK_ID, "name": "Optimize", "order": 2,
            "status": "PENDING", "statusMessage": None,
        }},
        {"listTaskStageByTaskId": {"items": [{
            "id": "stage-setup", "taskId": TASK_ID, "name": "Setup", "order": 1,
            "status": "PENDING", "statusMessage": None,
        }, {
            "id": "stage-optimize", "taskId": TASK_ID, "name": "Optimize", "order": 2,
            "status": "PENDING", "statusMessage": None,
        }], "nextToken": None}},
        {"listTaskStageByTaskId": {"items": [{
            "id": "stage-setup", "taskId": TASK_ID, "name": "Setup", "order": 1,
            "status": "PENDING", "statusMessage": None,
        }, {
            "id": "stage-optimize", "taskId": TASK_ID, "name": "Optimize", "order": 2,
            "status": "PENDING", "statusMessage": None,
        }], "nextToken": None}},
    ])
    backend = _adapter(client)
    expected = [
        {"name": "Setup", "order": 1, "status": "PENDING"},
        {"name": "Optimize", "order": 2, "status": "PENDING"},
    ]

    backend.reconcile_task_stages(TASK_ID, expected)
    pages = list(backend.task_stage_pages_for_task(TASK_ID))

    assert len(pages) == 1
    assert {stage["name"] for stage in pages[0]["items"]} == {"Setup", "Optimize"}
    create_input = client.calls[2][1]["input"]
    assert create_input == {"taskId": TASK_ID, "name": "Optimize", "order": 2, "status": "PENDING"}


def test_lost_task_stage_create_response_adopts_exhaustive_readback_without_duplicate() -> None:
    stage = {
        "id": "stage-generated", "taskId": TASK_ID, "name": "Setup", "order": 1,
        "status": "PENDING", "statusMessage": None,
    }
    client = _RecordingClient([
        {"listTaskStageByTaskId": {"items": [], "nextToken": None}},
        TimeoutError("create response lost"),
        {"listTaskStageByTaskId": {"items": [stage], "nextToken": None}},
        {"listTaskStageByTaskId": {"items": [stage], "nextToken": None}},
    ])
    backend = _adapter(client)

    result = backend.reconcile_task_stages(
        TASK_ID, [{"name": "Setup", "order": 1, "status": "PENDING"}]
    )

    assert result == [stage]
    assert sum("mutation CreateTaskStage" in query for query, _ in client.calls) == 1


def test_lost_task_stage_create_response_without_readback_never_retries_create() -> None:
    client = _RecordingClient([
        {"listTaskStageByTaskId": {"items": [], "nextToken": None}},
        TimeoutError("create response lost"),
        {"listTaskStageByTaskId": {"items": [], "nextToken": None}},
    ])
    backend = _adapter(client)

    with pytest.raises(RuntimeError, match="outcome is unknown"):
        backend.reconcile_task_stages(
            TASK_ID, [{"name": "Setup", "order": 1, "status": "PENDING"}]
        )

    assert sum("mutation CreateTaskStage" in query for query, _ in client.calls) == 1


def test_stage_reconciliation_rejects_ambiguous_or_malformed_existing_evidence() -> None:
    client = _RecordingClient([{"listTaskStageByTaskId": {"items": [{
        "id": "stage-1", "taskId": TASK_ID, "name": "Setup", "order": 1,
        "status": "PENDING",
    }, {
        "id": "stage-2", "taskId": TASK_ID, "name": "Setup", "order": 1,
        "status": "PENDING",
    }], "nextToken": None}}])

    with pytest.raises(RuntimeError, match="ambiguous"):
        _adapter(client).reconcile_task_stages(
            TASK_ID, [{"name": "Setup", "order": 1, "status": "PENDING"}]
        )


def test_release_uses_only_held_to_pending_update_then_observes_readback() -> None:
    task_metadata = {
        "procedure_id": PROCEDURE_ID,
        "dispatch_policy": "held_once",
    }
    held = _task(metadata=task_metadata)
    pending = _task(metadata=task_metadata)
    pending["dispatchStatus"] = "PENDING"
    client = _RecordingClient([
        {"getTask": held},
        {"updateTask": pending},
        {"getTask": pending},
    ])
    backend = _adapter(client)

    backend.release_held_task(TASK_ID)
    observed = backend.get_task(TASK_ID)

    update_input = client.calls[1][1]["input"]
    assert update_input["id"] == TASK_ID
    assert update_input["dispatchStatus"] == "PENDING"
    assert update_input["status"] == "PENDING"
    assert update_input["target"] == f"procedure/{PROCEDURE_ID}"
    assert observed["dispatchStatus"] == "PENDING"


@pytest.mark.parametrize("bad", [
    {**_task(), "scorecardId": "wrong"},
    {**_task(), "scoreId": "wrong"},
    {**_task(), "metadata": {"procedure_id": "other"}},
])
def test_created_task_rejects_physical_identity_or_metadata_mismatch(bad: dict[str, Any]) -> None:
    client = _RecordingClient([{"createTask": bad}])

    with pytest.raises(RuntimeError, match="created Task"):
        _adapter(client).create_task({
            "accountId": ACCOUNT_ID,
            "scorecardId": "scorecard-opaque",
            "scoreId": "score-opaque",
            "type": "Procedure",
            "status": "PENDING",
            "target": f"procedure/{PROCEDURE_ID}",
            "command": f"procedure run {PROCEDURE_ID}",
            "dispatchStatus": "HELD",
            "metadata": {"procedure_id": PROCEDURE_ID},
        })
