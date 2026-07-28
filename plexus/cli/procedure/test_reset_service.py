from datetime import datetime, timezone
from typing import Any, Dict

from tactus.protocols.models import CheckpointEntry, ProcedureMetadata

from plexus.cli.procedure.reset_service import clone_state_for_branch, reset_checkpoints_only


class _FakeStorageAdapter:
    _metadata_by_id: Dict[str, ProcedureMetadata] = {}
    _status_by_id: Dict[str, str] = {}

    def __init__(self, _client: Any, procedure_id: str):
        self.procedure_id = procedure_id

    def load_procedure_metadata(self, procedure_id: str) -> ProcedureMetadata:
        return self._metadata_by_id[procedure_id]

    def save_procedure_metadata(self, procedure_id: str, metadata: ProcedureMetadata) -> None:
        self._metadata_by_id[procedure_id] = metadata

    def update_procedure_status(self, procedure_id: str, status: str) -> None:
        self._status_by_id[procedure_id] = status


def test_clone_state_for_branch_clears_costs_and_runtime_mailbox_state(monkeypatch):
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.storage.PlexusStorageAdapter",
        _FakeStorageAdapter,
    )

    _FakeStorageAdapter._metadata_by_id = {
        "source-proc": ProcedureMetadata(
            procedure_id="source-proc",
            execution_log=[],
            state={
                "iterations": [
                    {"iteration": 1, "accepted": True},
                    {"iteration": 2, "accepted": False},
                ],
                "costs": {
                    "evaluation": {"incurred_total": 1.23},
                    "inference": {"total": 0.45},
                },
                "last_mailbox_check": "2026-04-19T12:00:00Z",
                "_procedure_id": "source-proc",
            },
            lua_state={"foo": "bar"},
        ),
        "target-proc": ProcedureMetadata(
            procedure_id="target-proc",
            execution_log=[],
            state={"stale": True},
            lua_state={"stale": True},
        ),
    }

    result = clone_state_for_branch(
        client=object(),
        source_procedure_id="source-proc",
        target_procedure_id="target-proc",
        truncate_to_cycle=1,
    )

    assert result["iterations_copied"] == 1

    target = _FakeStorageAdapter._metadata_by_id["target-proc"]
    assert target.execution_log == []
    assert target.lua_state == {}
    assert target.state.get("iterations") == [{"iteration": 1, "accepted": True}]
    assert "costs" not in target.state
    assert "last_mailbox_check" not in target.state
    assert "_procedure_id" not in target.state
    assert _FakeStorageAdapter._status_by_id["target-proc"] == "PENDING"


def test_reset_checkpoints_only_counts_execution_log_and_preserves_state(monkeypatch):
    metadata = ProcedureMetadata(
        procedure_id="procedure-1",
        execution_log=[
            CheckpointEntry(
                position=0,
                type="checkpoint",
                result={"value": 1},
                timestamp=datetime.now(timezone.utc),
            ),
            CheckpointEntry(
                position=1,
                type="checkpoint",
                result={"value": 2},
                timestamp=datetime.now(timezone.utc),
            ),
        ],
        state={"preserved": True},
        lua_state={"cursor": 7},
    )
    saved = []
    statuses = []

    class _Storage:
        def __init__(self, _client, _procedure_id):
            pass

        def load_procedure_metadata(self, _procedure_id):
            return metadata

        def save_procedure_metadata(self, procedure_id, updated):
            saved.append((procedure_id, updated))

        def update_procedure_status(self, procedure_id, status, waiting_on_message_id=None):
            statuses.append((procedure_id, status, waiting_on_message_id))

    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.storage.PlexusStorageAdapter",
        _Storage,
    )

    class _Client:
        def execute(self, query, variables):
            if "GetProcedure" in query:
                return {
                    "getProcedure": {
                        "id": "procedure-1",
                        "metadata": '{"checkpoints":{"_s3_key":"key","sha256":"sum","size_bytes":2,"content_type":"application/json"}}',
                    }
                }
            if "UpdateProcedure" in query:
                return {"updateProcedure": {"id": "procedure-1"}}
            raise AssertionError(query)

    result = reset_checkpoints_only(_Client(), "procedure-1")

    assert result == {"cleared_count": 2, "remaining_count": 0}
    assert len(saved) == 1
    assert saved[0][0] == "procedure-1"
    assert saved[0][1].execution_log == []
    assert saved[0][1].state == {"preserved": True}
    assert saved[0][1].lua_state == {"cursor": 7}
    assert statuses == [("procedure-1", "PENDING", None)]
