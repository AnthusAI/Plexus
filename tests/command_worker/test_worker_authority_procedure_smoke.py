"""Bounded procedure/state load through the declared worker authority."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

from plexus.cli.procedure.tactus_adapters.storage import PlexusStorageAdapter
from plexus.dashboard.api.models.procedure import Procedure
from plexus.storage.graphql_artifact_store import GraphQLArtifactStore


def _procedure_authority() -> set[str]:
    path = (
        Path(__file__).parents[2]
        / "dashboard"
        / "amplify"
        / "command-service"
        / "action-authority.json"
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    actions = manifest["actions"]

    def resolve(action: str, visiting: frozenset[str] = frozenset()) -> set[str]:
        assert action not in visiting
        entry = actions[action]
        return set(entry["appsync"]).union(
            *(resolve(parent, visiting | {action}) for parent in entry.get("inherits", []))
        )

    return resolve("procedure.run")


def test_declared_procedure_authority_loads_procedure_and_verified_state() -> None:
    state_bytes = b'{"iteration":2,"status":"RUNNING"}'
    state_sha = hashlib.sha256(state_bytes).hexdigest()
    allowed = _procedure_authority()
    observed: list[str] = []

    class AuthorityClient:
        def execute(self, query, variables=None, **_kwargs):
            operation_type = "Mutation" if re.search(r"\bmutation\b", query) else "Query"
            field_match = re.search(r"\b(getProcedure|createArtifactTransferTickets)\s*\(", query)
            assert field_match, query
            root = f"{operation_type}/{field_match.group(1)}"
            assert root in allowed, f"procedure smoke used undeclared root {root}"
            observed.append(root)
            if root == "Mutation/createArtifactTransferTickets":
                return {
                    "createArtifactTransferTickets": [{
                        "objectKey": "procedures/procedure-1/state.json",
                        "method": "GET",
                        "url": "https://artifacts.example/procedures/procedure-1/state.json",
                        "requiredHeaders": {},
                        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                    }]
                }
            return {
                "getProcedure": {
                    "id": "procedure-1",
                    "name": "Bounded smoke",
                    "description": "",
                    "status": "RUNNING",
                    "featured": False,
                    "isTemplate": False,
                    "code": "class: BeamSearch",
                    "category": None,
                    "version": None,
                    "isDefault": False,
                    "parentProcedureId": None,
                    "metadata": {
                        "state": {
                            "_s3_key": "procedures/procedure-1/state.json",
                            "sha256": state_sha,
                            "size_bytes": len(state_bytes),
                            "content_type": "application/json",
                        }
                    },
                    "createdAt": "2026-08-06T00:00:00Z",
                    "updatedAt": "2026-08-06T00:00:00Z",
                    "accountId": "account-1",
                    "scorecardId": None,
                    "scoreId": None,
                    "scoreVersionId": None,
                    "attachedFiles": [],
                    "createdByUserId": None,
                    "state": None,
                }
            }

    class HTTPSession:
        def request(self, method, url, **_kwargs):
            assert method == "GET"
            assert url.endswith("/procedures/procedure-1/state.json")
            return SimpleNamespace(status_code=200, content=state_bytes, text="")

    client = AuthorityClient()
    procedure = Procedure.get_by_id("procedure-1", client)
    storage = PlexusStorageAdapter(
        client,
        procedure.id,
        artifact_store=GraphQLArtifactStore(client, http_session=HTTPSession()),
    )

    metadata = storage.load_procedure_metadata(procedure.id)

    assert procedure.accountId == "account-1"
    assert metadata.state == {"iteration": 2, "status": "RUNNING"}
    assert observed == [
        "Query/getProcedure",
        "Query/getProcedure",
        "Mutation/createArtifactTransferTickets",
    ]
