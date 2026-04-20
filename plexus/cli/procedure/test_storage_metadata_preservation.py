import json

from tactus.protocols.models import ProcedureMetadata

from plexus.cli.procedure.tactus_adapters.storage import PlexusStorageAdapter


class _FakeS3Client:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[(Bucket, Key)] = {
            "Body": Body,
            "ContentType": ContentType,
        }


class _FakeClient:
    def __init__(self):
        self.raw_metadata = {
            "runtime": {"pid": 12345, "host": "devbox", "started_at": "2026-04-20T00:00:00Z"},
            "last_failure": {"kind": "signal", "signal": "SIGTERM"},
            "custom": {"keep": True},
        }
        self.saved_metadata = None

    def execute(self, query, variables):
        if "getProcedure(id: $id)" in query:
            return {
                "getProcedure": {
                    "id": variables["id"],
                    "metadata": json.dumps(self.raw_metadata),
                    "status": "RUNNING",
                    "waitingOnMessageId": None,
                }
            }
        if "updateProcedure(input:" in query:
            self.saved_metadata = json.loads(variables["metadata"])
            return {
                "updateProcedure": {
                    "id": variables["id"],
                    "metadata": variables["metadata"],
                }
            }
        raise AssertionError(f"Unexpected query: {query}")


def test_save_procedure_metadata_preserves_runtime_and_failure_fields(monkeypatch):
    fake_client = _FakeClient()
    fake_s3 = _FakeS3Client()

    monkeypatch.setattr("plexus.cli.procedure.tactus_adapters.storage.boto3.client", lambda _name: fake_s3)

    storage = PlexusStorageAdapter(fake_client, "proc-123")
    metadata = ProcedureMetadata(
        procedure_id="proc-123",
        execution_log=[],
        replay_index=7,
        state={"iterations": [{"iteration": 1}]},
        lua_state={"cursor": 2},
        status="RUNNING",
        waiting_on_message_id=None,
    )

    storage.save_procedure_metadata("proc-123", metadata)

    assert fake_client.saved_metadata is not None
    assert fake_client.saved_metadata["runtime"] == fake_client.raw_metadata["runtime"]
    assert fake_client.saved_metadata["last_failure"] == fake_client.raw_metadata["last_failure"]
    assert fake_client.saved_metadata["custom"] == fake_client.raw_metadata["custom"]
    assert fake_client.saved_metadata["replay_index"] == 7
    assert fake_client.saved_metadata["state"]["_s3_key"].endswith("/state.json")
    assert fake_client.saved_metadata["lua_state"]["_s3_key"].endswith("/lua_state.json")
    assert fake_client.saved_metadata["checkpoints"]["_s3_key"].endswith("/checkpoints.json")
