"""Behavior specifications for application-authorized Tactus persistence.

Feature: Procedure lifecycle persistence without workload credentials
  Scenario: Start, checkpoint, stop, and resume a procedure
    Given a supported Plexus Tactus storage adapter and an artifact store
    When the procedure persists state, Lua state, checkpoints, and dashboard state
    Then all attachments use one authorized batch, metadata retains compatible keys,
    and resume restores verified state without constructing an S3 client

  Scenario: Legacy attachment metadata has no integrity information
    Given a legacy pointer containing only _s3_key
    When a procedure tries to resume from it
    Then persistence fails clearly rather than downloading unchecked bytes
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import boto3
import pytest
from tactus.protocols.models import CheckpointEntry, ProcedureMetadata

from plexus.cli.procedure.tactus_adapters.storage import (
    PlexusStorageAdapter,
    ProcedureArtifactStorageError,
    download_procedure_attachment,
    upload_procedure_attachment,
)


class _MemoryArtifactStore:
    def __init__(self):
        self.upload_batches = []
        self.download_batches = []
        self.objects = {}

    @staticmethod
    def _key(request):
        prefix = (
            "reportblocks/procedures"
            if request.artifact_type == "PROCEDURE_DASHBOARD_STATE"
            else "procedures"
        )
        return f"{prefix}/{request.resource_id}/{request.filename}"

    def upload_batch(self, uploads):
        self.upload_batches.append(list(uploads))
        metadata = []
        for upload in uploads:
            key = self._key(upload.request)
            self.objects[key] = upload.content
            metadata.append(
                {
                    "_s3_key": key,
                    "sha256": hashlib.sha256(upload.content).hexdigest(),
                    "size_bytes": len(upload.content),
                    "content_type": upload.request.content_type,
                }
            )
        return metadata

    def download_batch(self, requests):
        self.download_batches.append(list(requests))
        return [self.objects[self._key(request)] for request in requests]

    def download_bytes(self, request):
        return self.download_batch([request])[0]


class _ProcedureClient:
    def __init__(self):
        self.metadata = {}
        self.status = "RUNNING"
        self.executions = []

    def execute(self, query, variables, retry_policy=None):
        self.executions.append((query, variables, retry_policy))
        if "getProcedure(id: $id)" in query:
            return {
                "getProcedure": {
                    "id": variables["id"],
                    "metadata": json.dumps(self.metadata),
                    "status": self.status,
                    "waitingOnMessageId": None,
                }
            }
        if "updateProcedure(input:" in query:
            if "metadata" in variables:
                self.metadata = json.loads(variables["metadata"])
            if "status" in variables:
                self.status = variables["status"]
            return {"updateProcedure": {"id": variables["id"]}}
        raise AssertionError(f"Unexpected GraphQL operation: {query}")


def _metadata() -> ProcedureMetadata:
    return ProcedureMetadata(
        procedure_id="procedure-1",
        execution_log=[
            CheckpointEntry(
                position=0,
                type="explicit_checkpoint",
                result={"phase": "start"},
                timestamp=datetime.now(timezone.utc),
                duration_ms=12.5,
                input_hash="input-hash",
                run_id="run-1",
                captured_vars={"phase": "before-checkpoint"},
            )
        ],
        replay_index=1,
        state={"phase": "running"},
        lua_state={"cursor": 3},
        status="RUNNING",
        waiting_on_message_id=None,
    )


def test_start_checkpoint_stop_and_resume_use_graphql_artifacts_without_s3(monkeypatch):
    client = _ProcedureClient()
    artifacts = _MemoryArtifactStore()
    monkeypatch.setattr(
        boto3,
        "client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("S3 must not be used")),
    )
    storage = PlexusStorageAdapter(client, "procedure-1", artifact_store=artifacts)

    storage.save_procedure_metadata("procedure-1", _metadata())
    storage.checkpoint_save("procedure-1", "paused", {"phase": "checkpoint"})
    storage.update_procedure_status("procedure-1", "STOPPED")
    resumed = PlexusStorageAdapter(
        client,
        "procedure-1",
        artifact_store=artifacts,
    ).load_procedure_metadata("procedure-1")

    assert len(artifacts.upload_batches) == 2
    assert len(artifacts.upload_batches[0]) == 4
    assert {item.request.filename for item in artifacts.upload_batches[0]} == {
        "state.json",
        "lua_state.json",
        "checkpoints.json",
        "dashboard_state.json",
    }
    assert len(artifacts.download_batches) == 1
    assert client.metadata["state"]["_s3_key"] == "procedures/procedure-1/state.json"
    assert client.metadata["dashboard_state"]["_s3_key"] == (
        "reportblocks/procedures/procedure-1/dashboard_state.json"
    )
    assert client.metadata["checkpoints"]["sha256"]
    assert client.metadata["lua_state"]["size_bytes"] > 0
    assert client.status == "STOPPED"
    assert resumed.state["phase"] == "running"
    assert resumed.lua_state == {"cursor": 3}
    assert len(resumed.execution_log) == 2
    assert resumed.execution_log[0].type == "explicit_checkpoint"
    assert resumed.execution_log[0].result == {"phase": "start"}
    assert resumed.execution_log[0].duration_ms == 12.5
    assert resumed.execution_log[0].input_hash == "input-hash"
    assert resumed.execution_log[0].run_id == "run-1"
    assert resumed.execution_log[0].captured_vars == {"phase": "before-checkpoint"}
    assert resumed.execution_log[1].type == "checkpoint"
    assert resumed.execution_log[1].result == {
        "name": "paused",
        "data": {"phase": "checkpoint"},
    }


def test_resume_supports_legacy_named_checkpoint_object_format():
    client = _ProcedureClient()
    artifacts = _MemoryArtifactStore()
    checkpoints = {
        "started": {
            "name": "started",
            "result": {"phase": "start"},
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    client.metadata = {
        "state": {},
        "lua_state": {},
        "checkpoints": {
            "_s3_key": "procedures/procedure-1/checkpoints.json",
            "sha256": hashlib.sha256(json.dumps(checkpoints).encode()).hexdigest(),
            "size_bytes": len(json.dumps(checkpoints).encode()),
            "content_type": "application/json",
        },
    }
    artifacts.objects["procedures/procedure-1/checkpoints.json"] = json.dumps(checkpoints).encode()

    resumed = PlexusStorageAdapter(
        client,
        "procedure-1",
        artifact_store=artifacts,
    ).load_procedure_metadata("procedure-1")

    assert resumed.execution_log[0].type == "checkpoint"
    assert resumed.execution_log[0].result == {
        "name": "started",
        "data": {"phase": "start"},
    }


def test_resume_rejects_legacy_pointer_without_checksum_or_size():
    client = _ProcedureClient()
    client.metadata = {
        "state": {"_s3_key": "procedures/procedure-1/state.json"},
        "lua_state": {},
        "checkpoints": {},
    }

    with pytest.raises(ProcedureArtifactStorageError, match="integrity"):
        PlexusStorageAdapter(
            client,
            "procedure-1",
            artifact_store=_MemoryArtifactStore(),
        ).load_procedure_metadata("procedure-1")


def test_procedure_code_keeps_legacy_key_and_loads_only_with_integrity_metadata(monkeypatch):
    client = _ProcedureClient()
    artifacts = _MemoryArtifactStore()
    monkeypatch.setattr(
        boto3,
        "client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("S3 must not be used")),
    )

    pointer = upload_procedure_attachment(
        client,
        "procedure-1",
        "code.tac",
        "name: verified procedure",
        content_type="text/plain",
        artifact_store=artifacts,
    )
    loaded = download_procedure_attachment(
        client,
        "procedure-1",
        "code.tac",
        pointer,
        content_type="text/plain",
        artifact_store=artifacts,
    )

    assert pointer["_s3_key"] == "procedures/procedure-1/code.tac"
    assert pointer["sha256"]
    assert loaded == b"name: verified procedure"
