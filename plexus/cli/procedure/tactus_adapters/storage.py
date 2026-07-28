"""
Plexus Storage Adapter for Tactus.

Implements the Tactus StorageBackend protocol using Plexus GraphQL API.
The Procedure record is an index card: it holds legacy-compatible object keys
and replay_index. All procedure data (state, lua_state, checkpoints) lives in
application-authorized GraphQL artifact attachments.
"""

import logging
import json
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from tactus.protocols.models import ProcedureMetadata, CheckpointEntry
from plexus.cli.procedure.builtin_procedures import is_builtin_procedure_id
from plexus.dashboard.api.client import LONG_RUNNING_WRITE_RETRY_POLICY_NAME
from plexus.storage.graphql_artifact_store import (
    ArtifactIntegrityError,
    ArtifactTransferRequest,
    ArtifactUpload,
    GraphQLArtifactStore,
    GraphQLArtifactStoreError,
)

logger = logging.getLogger(__name__)

def _lua_to_serializable(value: Any) -> Any:
    """
    Recursively convert lupa Lua tables to JSON-serializable Python structures.

    lupa Lua tables have an .items() method but are not natively JSON-serializable.
    This converts them to Python dicts/lists so json.dumps() succeeds.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    # lupa Lua tables expose .items(); plain Python dicts/lists pass through below
    if hasattr(value, "items") and not isinstance(value, dict):
        try:
            keys = list(value.keys())
            if not keys:
                return []
            if all(isinstance(k, int) for k in keys):
                sorted_keys = sorted(keys)
                if sorted_keys == list(range(1, len(keys) + 1)):
                    return [_lua_to_serializable(value[k]) for k in sorted_keys]
            return {k: _lua_to_serializable(v) for k, v in value.items()}
        except Exception:
            return str(value)

    if isinstance(value, dict):
        return {k: _lua_to_serializable(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_lua_to_serializable(item) for item in value]

    # Fallback for unknown types — attempt JSON round-trip, else stringify
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


# Fields kept per iteration entry in the lightweight dashboard state.
_DASHBOARD_ITERATION_FIELDS = frozenset({
    'iteration', 'score_version_id',
    'recent_metrics', 'regression_metrics',
    'recent_deltas', 'regression_deltas',
    'accepted', 'skip_reason', 'disqualified',
    'done_reason', 'synthesis_strategy', 'synthesis_reasoning', 'dual_synthesis',
    'recent_evaluation_id', 'regression_evaluation_id',
    'recent_cost_per_item', 'regression_cost_per_item',
})

# Top-level state fields dropped from the dashboard projection.
_DASHBOARD_DROP_TOPLEVEL = frozenset({
    'last_regression_rca', 'last_recent_rca',
    'item_recurrence', 'known_contradictions',
})

# Recurrence patterns always surfaced in the dashboard projection.
_NOTABLE_RECURRENCE_PATTERNS = frozenset({
    'PERSISTENT', 'OSCILLATING', 'FLIP_FLOP', 'LATE_EMERGING',
})


def _has_repeat_recurrence_history(entry: Dict[str, Any]) -> bool:
    """Return True when an EMERGING item has enough history to help operators."""
    per_cycle = entry.get('per_cycle') or []
    if not isinstance(per_cycle, list):
        per_cycle = []
    wrong_count = entry.get('wrong_count') or 0
    correct_count = entry.get('correct_count') or 0
    return len(per_cycle) >= 2 or wrong_count >= 2 or (wrong_count >= 1 and correct_count >= 1)


def _build_notable_item_recurrence(tracker: Any) -> Optional[Dict[str, Any]]:
    """Return a compact subset of item_recurrence for the dashboard projection.

    Keeps notable patterns plus repeat-active EMERGING items, caps per_cycle
    history to the 5 most recent entries, and caps the total to 30 items sorted
    by pattern priority and wrong_count descending. Returns None if there are
    no useful recurrence items yet.
    """
    if not isinstance(tracker, dict) or not tracker:
        return None

    notable: List[tuple] = []
    for item_id, entry in tracker.items():
        if not isinstance(entry, dict):
            continue
        pattern = entry.get('pattern') or 'EMERGING'
        if pattern not in _NOTABLE_RECURRENCE_PATTERNS and not (
            pattern == 'EMERGING' and _has_repeat_recurrence_history(entry)
        ):
            continue
        # Keep only the 5 most recent per_cycle entries.
        per_cycle = entry.get('per_cycle') or []
        if isinstance(per_cycle, list) and len(per_cycle) > 5:
            per_cycle = per_cycle[-5:]
        trimmed = {**entry, 'per_cycle': per_cycle}
        if 'feedback_label' not in trimmed and 'recent_label' in trimmed:
            trimmed['feedback_label'] = trimmed.get('recent_label')
        notable.append((item_id, trimmed, pattern, entry.get('wrong_count', 0), entry.get('correct_count', 0)))

    if not notable:
        return None

    pattern_priority = {
        'OSCILLATING': 0,
        'PERSISTENT': 1,
        'FLIP_FLOP': 2,
        'LATE_EMERGING': 3,
        'EMERGING': 4,
    }

    # Sort by pattern priority, then activity volume, cap at 30.
    notable.sort(
        key=lambda t: (
            pattern_priority.get(t[2], 9),
            -(t[3] + t[4]),
            -t[3],
            str(t[0]),
        )
    )
    return {item_id: entry for item_id, entry, _, _, _ in notable[:30]}


def _build_dashboard_state(full_state: Dict[str, Any]) -> Dict[str, Any]:
    """Build a lightweight copy of the optimizer state for the dashboard.

    The full state can exceed 10 MB because each iteration's
    ``exploration_results`` embeds hypothesis details, transcripts, and
    evaluation data.  The dashboard only needs scalar metrics, deltas,
    and small summary fields — this projection keeps the file under ~50 KB.
    """
    if not isinstance(full_state, dict):
        return full_state

    out: Dict[str, Any] = {}
    for key, value in full_state.items():
        if key in _DASHBOARD_DROP_TOPLEVEL:
            continue
        if key == 'iterations' and isinstance(value, list):
            out['iterations'] = [
                {k: v for k, v in it.items() if k in _DASHBOARD_ITERATION_FIELDS}
                for it in value
                if isinstance(it, dict)
            ]
        else:
            out[key] = value

    # Add compact item recurrence for the problem-item tracker.
    notable = _build_notable_item_recurrence(full_state.get('item_recurrence') or {})
    if notable:
        out['notable_item_recurrence'] = notable

    return out


def _looks_like_optimizer_state(state: Any) -> bool:
    return isinstance(state, dict) and (
        "iterations" in state
        or "baseline_version_id" in state
        or "end_of_run_report" in state
        or "last_accepted_version_id" in state
    )


class ProcedureArtifactStorageError(RuntimeError):
    """Procedure persistence could not load or store a verified artifact."""


_PERSISTED_ARTIFACTS = {
    "state": ("state.json", "PROCEDURE_ATTACHMENT"),
    "lua_state": ("lua_state.json", "PROCEDURE_ATTACHMENT"),
    "checkpoints": ("checkpoints.json", "PROCEDURE_ATTACHMENT"),
    "dashboard_state": ("dashboard_state.json", "PROCEDURE_DASHBOARD_STATE"),
}


def _artifact_key(procedure_id: str, filename: str, artifact_type: str) -> str:
    prefix = "reportblocks/procedures" if artifact_type == "PROCEDURE_DASHBOARD_STATE" else "procedures"
    return f"{prefix}/{procedure_id}/{filename}"


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")


def _serialize_execution_log(entries: List[CheckpointEntry]) -> List[Dict[str, Any]]:
    """Preserve Tactus' position-based checkpoint records without narrowing their types."""
    serialized = []
    for entry in entries:
        source_location = entry.source_location
        if source_location is not None and hasattr(source_location, "model_dump"):
            source_location = source_location.model_dump(mode="json")
        serialized.append({
            "position": entry.position,
            "type": entry.type,
            "result": _lua_to_serializable(entry.result),
            "timestamp": entry.timestamp.isoformat(),
            "duration_ms": entry.duration_ms,
            "input_hash": entry.input_hash,
            "run_id": entry.run_id,
            "source_location": _lua_to_serializable(source_location),
            "captured_vars": _lua_to_serializable(entry.captured_vars),
        })
    return serialized


def _deserialize_execution_log(payload: Any) -> List[CheckpointEntry]:
    """Load current ordered logs and the legacy named-checkpoint object format."""
    if isinstance(payload, list):
        entries = []
        for raw_entry in payload:
            if not isinstance(raw_entry, dict):
                raise ProcedureArtifactStorageError("checkpoint artifact contains a malformed entry")
            try:
                entry_data = dict(raw_entry)
                entry_data["timestamp"] = datetime.fromisoformat(entry_data["timestamp"])
                entries.append(CheckpointEntry(**entry_data))
            except (KeyError, TypeError, ValueError) as exc:
                raise ProcedureArtifactStorageError("checkpoint artifact is malformed") from exc
        return entries

    if not isinstance(payload, dict):
        raise ProcedureArtifactStorageError("checkpoints artifact must contain an array or object")

    entries = []
    for position, (name, checkpoint_data) in enumerate(payload.items()):
        try:
            entries.append(CheckpointEntry(
                position=position,
                type="checkpoint",
                result={"name": name, "data": checkpoint_data.get("result")},
                timestamp=datetime.fromisoformat(checkpoint_data["completed_at"]),
                run_id=checkpoint_data.get("run_id"),
            ))
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ProcedureArtifactStorageError("checkpoint artifact is malformed") from exc
    return entries


def _pointer_read_request(
    procedure_id: str,
    pointer: Any,
    *,
    filename: str,
    artifact_type: str,
) -> ArtifactTransferRequest:
    """Build a verified read request or reject an unverifiable legacy pointer."""
    if not isinstance(pointer, dict) or not pointer.get("_s3_key"):
        raise ProcedureArtifactStorageError(f"{filename} is not an artifact metadata pointer")
    expected_key = _artifact_key(procedure_id, filename, artifact_type)
    if pointer["_s3_key"] != expected_key:
        raise ProcedureArtifactStorageError(
            f"{filename} pointer does not match the supported procedure artifact key"
        )
    sha256 = pointer.get("sha256") or pointer.get("checksum")
    size_bytes = pointer.get("size_bytes", pointer.get("size"))
    content_type = pointer.get("content_type") or pointer.get("contentType") or "application/json"
    if not isinstance(sha256, str) or not isinstance(size_bytes, int):
        raise ProcedureArtifactStorageError(
            f"{filename} legacy metadata lacks required integrity checksum or size"
        )
    try:
        return ArtifactTransferRequest(
            operation="READ",
            resource_type="PROCEDURE",
            resource_id=procedure_id,
            artifact_type=artifact_type,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=sha256,
        )
    except ValueError as exc:
        raise ProcedureArtifactStorageError(f"{filename} metadata has invalid integrity fields") from exc


def upload_procedure_attachment(
    client,
    procedure_id: str,
    filename: str,
    content: str | bytes,
    *,
    content_type: str,
    existing_metadata: Optional[Dict[str, Any]] = None,
    artifact_store=None,
) -> Dict[str, Any]:
    """Store procedure code or an attachment through an authorized ticket."""
    payload = content.encode("utf-8") if isinstance(content, str) else content
    if not isinstance(payload, bytes):
        raise TypeError("procedure attachment content must be bytes or text")
    request = ArtifactTransferRequest(
        operation="WRITE",
        resource_type="PROCEDURE",
        resource_id=procedure_id,
        artifact_type="PROCEDURE_ATTACHMENT",
        filename=filename,
        content_type=content_type,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    try:
        return (artifact_store or GraphQLArtifactStore(client)).upload_batch(
            [ArtifactUpload(request, payload, existing_metadata)]
        )[0]
    except GraphQLArtifactStoreError as exc:
        raise ProcedureArtifactStorageError(f"Unable to store {filename}") from exc


def download_procedure_attachment(
    client,
    procedure_id: str,
    filename: str,
    pointer: Any,
    *,
    content_type: str = "text/plain",
    artifact_store=None,
) -> bytes:
    """Load an integrity-verified procedure attachment through GraphQL tickets."""
    request = _pointer_read_request(
        procedure_id,
        pointer,
        filename=filename,
        artifact_type="PROCEDURE_ATTACHMENT",
    )
    if request.content_type != content_type:
        raise ProcedureArtifactStorageError(f"{filename} has an unexpected content type")
    try:
        return (artifact_store or GraphQLArtifactStore(client)).download_batch([request])[0]
    except GraphQLArtifactStoreError as exc:
        raise ProcedureArtifactStorageError(f"Unable to load verified {filename}") from exc


class PlexusStorageAdapter:
    """
    Implements Tactus StorageBackend protocol using Plexus GraphQL.

    Stores all procedure data (checkpoints, state, lua_state) in the
    Procedure.metadata JSON field via GraphQL mutations.
    """

    def __init__(self, client, procedure_id: str, *, artifact_store=None):
        """
        Initialize Plexus storage adapter.

        Args:
            client: PlexusDashboardClient instance
            procedure_id: ID of the procedure
        """
        self.client = client
        self.procedure_id = procedure_id
        self._is_builtin = is_builtin_procedure_id(procedure_id)
        self.artifact_store = artifact_store or GraphQLArtifactStore(client)
        self._metadata_cache: Optional[ProcedureMetadata] = None
        logger.info(f"PlexusStorageAdapter initialized for procedure {procedure_id}")

    def _fetch_raw_procedure_metadata(self, procedure_id: str) -> Dict[str, Any]:
        """Fetch the current raw Procedure.metadata envelope for merge-safe writes."""
        if self._is_builtin:
            return {}

        query = """
        query GetProcedure($id: ID!) {
            getProcedure(id: $id) {
                id
                metadata
            }
        }
        """

        response = self.client.execute(query, {'id': procedure_id})
        procedure_data = response.get('getProcedure') or {}
        raw_metadata = procedure_data.get('metadata') or {}
        if isinstance(raw_metadata, str):
            try:
                raw_metadata = json.loads(raw_metadata)
            except Exception:
                logger.warning("Procedure metadata was not valid JSON during merge; defaulting to empty object")
                raw_metadata = {}
        if not isinstance(raw_metadata, dict):
            return {}
        return raw_metadata

    def load_procedure_metadata(self, procedure_id: str) -> ProcedureMetadata:
        """Load verified procedure state and checkpoints through artifact tickets."""
        if procedure_id != self.procedure_id:
            logger.warning(f"Requested procedure_id {procedure_id} doesn't match initialized {self.procedure_id}")
            procedure_id = self.procedure_id

        # Check cache first
        if self._metadata_cache and self._metadata_cache.procedure_id == procedure_id:
            logger.debug(f"Returning cached metadata for {procedure_id}")
            return self._metadata_cache

        if self._is_builtin:
            metadata = ProcedureMetadata(procedure_id=procedure_id)
            self._metadata_cache = metadata
            logger.debug("Using in-memory metadata for built-in procedure %s", procedure_id)
            return metadata

        query = """
        query GetProcedure($id: ID!) {
            getProcedure(id: $id) {
                id
                metadata
                status
                waitingOnMessageId
            }
        }
        """

        response = self.client.execute(query, {'id': procedure_id})
        procedure_data = response.get('getProcedure')
        if not procedure_data:
            metadata = ProcedureMetadata(procedure_id=procedure_id)
            self._metadata_cache = metadata
            return metadata

        raw_metadata = procedure_data.get('metadata') or {}
        if isinstance(raw_metadata, str):
            try:
                raw_metadata = json.loads(raw_metadata)
            except json.JSONDecodeError as exc:
                raise ProcedureArtifactStorageError("Procedure metadata is not valid JSON") from exc
        if not isinstance(raw_metadata, dict):
            raise ProcedureArtifactStorageError("Procedure metadata must be an object")

        artifact_fields = ("state", "lua_state", "checkpoints")
        requests = []
        request_fields = []
        for field_name in artifact_fields:
            pointer = raw_metadata.get(field_name)
            if pointer in (None, {}):
                continue
            filename, artifact_type = _PERSISTED_ARTIFACTS[field_name]
            requests.append(
                _pointer_read_request(
                    procedure_id,
                    pointer,
                    filename=filename,
                    artifact_type=artifact_type,
                )
            )
            request_fields.append(field_name)

        loaded_fields: Dict[str, Any] = {"state": {}, "lua_state": {}, "checkpoints": {}}
        if requests:
            try:
                contents = self.artifact_store.download_batch(requests)
            except (GraphQLArtifactStoreError, ArtifactIntegrityError) as exc:
                raise ProcedureArtifactStorageError("Unable to load verified procedure artifacts") from exc
            for field_name, content in zip(request_fields, contents):
                try:
                    loaded_fields[field_name] = json.loads(content.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProcedureArtifactStorageError(
                        f"{field_name} artifact is not valid JSON"
                    ) from exc

        execution_log = _deserialize_execution_log(loaded_fields["checkpoints"])

        if not isinstance(loaded_fields["state"], dict) or not isinstance(loaded_fields["lua_state"], dict):
            raise ProcedureArtifactStorageError("procedure state artifacts must contain objects")
        metadata = ProcedureMetadata(
            procedure_id=procedure_id,
            execution_log=execution_log,
            replay_index=raw_metadata.get('replay_index', 0),
            state=loaded_fields["state"],
            lua_state=loaded_fields["lua_state"],
            status=procedure_data.get('status') or 'RUNNING',
            waiting_on_message_id=procedure_data.get('waitingOnMessageId'),
        )
        self._metadata_cache = metadata
        return metadata

    def save_procedure_metadata(self, procedure_id: str, metadata: ProcedureMetadata) -> None:
        """
        Save procedure metadata to Plexus via GraphQL.

        Args:
            procedure_id: Procedure ID (for API compatibility)
            metadata: ProcedureMetadata to save
        """
        checkpoints = _serialize_execution_log(metadata.execution_log)

        # Update the Procedure index only after all attachment writes succeed.
        mutation = """
        mutation UpdateProcedureMetadata($id: ID!, $metadata: AWSJSON!) {
            updateProcedure(input: {
                id: $id
                metadata: $metadata
            }) {
                id
                name
                description
                status
                featured
                isTemplate
                code
                category
                version
                isDefault
                parentProcedureId
                waitingOnMessageId
                metadata
                createdAt
                updatedAt
                accountId
                scorecardId
                scoreId
                scoreVersionId
            }
        }
        """

        if self._is_builtin:
            self._metadata_cache = metadata
            logger.debug("Saved in-memory metadata for built-in procedure %s", metadata.procedure_id)
            return

        metadata_json = self._fetch_raw_procedure_metadata(metadata.procedure_id)
        payloads = {
            "state": metadata.state,
            "dashboard_state": _build_dashboard_state(metadata.state or {}),
            "lua_state": metadata.lua_state,
            "checkpoints": checkpoints,
        }
        uploads = []
        upload_fields = []
        for field_name, payload in payloads.items():
            filename, artifact_type = _PERSISTED_ARTIFACTS[field_name]
            content = _json_bytes(payload)
            uploads.append(
                ArtifactUpload(
                    ArtifactTransferRequest(
                        operation="WRITE",
                        resource_type="PROCEDURE",
                        resource_id=metadata.procedure_id,
                        artifact_type=artifact_type,
                        filename=filename,
                        content_type="application/json",
                        size_bytes=len(content),
                        sha256=hashlib.sha256(content).hexdigest(),
                    ),
                    content,
                    metadata_json.get(field_name),
                )
            )
            upload_fields.append(field_name)
        try:
            pointers = self.artifact_store.upload_batch(uploads)
        except GraphQLArtifactStoreError as exc:
            raise ProcedureArtifactStorageError("Unable to store procedure artifacts") from exc
        metadata_json.update(dict(zip(upload_fields, pointers)))
        metadata_json['replay_index'] = metadata.replay_index
        if _looks_like_optimizer_state(metadata.state):
            # The optimizer-results lane owns its GraphQL artifact implementation.
            # Keep the established indexing integration and fail closed if it fails.
            from plexus.cli.shared.optimizer_results import (
                OPTIMIZER_ARTIFACTS_METADATA_KEY,
                OptimizerResultsService,
            )

            optimizer_index = OptimizerResultsService(self.client).index_optimizer_run(
                metadata.procedure_id,
                state_override=metadata.state,
                existing_metadata=metadata_json,
                persist_metadata_pointer=False,
            )
            metadata_json[OPTIMIZER_ARTIFACTS_METADATA_KEY] = optimizer_index["pointer"]
        self.client.execute(
            mutation,
            {'id': metadata.procedure_id, 'metadata': json.dumps(metadata_json)},
            retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
        )
        self._metadata_cache = metadata

    def update_procedure_status(
        self,
        procedure_id: str,
        status: str,
        waiting_on_message_id: Optional[str] = None
    ) -> None:
        """
        Update procedure status in Plexus.

        Args:
            procedure_id: Procedure ID
            status: New status
            waiting_on_message_id: Optional message ID if waiting for human
        """
        mutation = """
        mutation UpdateProcedureStatus($id: ID!, $status: String!, $waitingOnMessageId: String) {
            updateProcedure(input: {
                id: $id
                status: $status
                waitingOnMessageId: $waitingOnMessageId
            }) {
                id
                name
                description
                status
                featured
                isTemplate
                code
                category
                version
                isDefault
                parentProcedureId
                waitingOnMessageId
                metadata
                createdAt
                updatedAt
                accountId
                scorecardId
                scoreId
                scoreVersionId
            }
        }
        """

        try:
            if self._is_builtin:
                if self._metadata_cache is None:
                    self._metadata_cache = ProcedureMetadata(procedure_id=procedure_id)
                self._metadata_cache.status = status
                self._metadata_cache.waiting_on_message_id = waiting_on_message_id
                logger.debug("Updated in-memory status for built-in procedure %s -> %s", procedure_id, status)
                return

            self.client.execute(
                mutation,
                {
                    'id': procedure_id,
                    'status': status,
                    'waitingOnMessageId': waiting_on_message_id
                },
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )

            # Update cache
            if self._metadata_cache:
                self._metadata_cache.status = status
                self._metadata_cache.waiting_on_message_id = waiting_on_message_id

            logger.debug(f"Updated procedure {procedure_id} status to {status}")

        except Exception as e:
            logger.error(f"Error updating procedure status: {e}", exc_info=True)
            raise

    def checkpoint_exists(self, procedure_id: str, name: str) -> bool:
        """Check if checkpoint exists."""
        metadata = self.load_procedure_metadata(procedure_id)
        for entry in metadata.execution_log:
            if entry.type == 'checkpoint' and isinstance(entry.result, dict):
                if entry.result.get('name') == name:
                    return True
        return False

    def checkpoint_get(self, procedure_id: str, name: str) -> Optional[Any]:
        """Get checkpoint value."""
        metadata = self.load_procedure_metadata(procedure_id)
        for entry in metadata.execution_log:
            if entry.type == 'checkpoint' and isinstance(entry.result, dict):
                if entry.result.get('name') == name:
                    return entry.result.get('data')
        return None

    def checkpoint_save(
        self,
        procedure_id: str,
        name: str,
        result: Any
    ) -> None:
        """Save a checkpoint."""
        metadata = self.load_procedure_metadata(procedure_id)
        # Add new checkpoint to execution log
        position = len(metadata.execution_log)
        metadata.execution_log.append(CheckpointEntry(
            position=position,
            type='checkpoint',
            result={'name': name, 'data': result},
            timestamp=datetime.now(timezone.utc)
        ))
        self.save_procedure_metadata(procedure_id, metadata)

    def checkpoint_clear_all(self, procedure_id: str) -> None:
        """Clear all checkpoints (but preserve state)."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.execution_log.clear()
        self.save_procedure_metadata(procedure_id, metadata)

    def checkpoint_clear_after(self, procedure_id: str, name: str) -> None:
        """Clear checkpoint and all subsequent ones."""
        metadata = self.load_procedure_metadata(procedure_id)

        # Find the target checkpoint
        target_time = None
        for entry in metadata.execution_log:
            if entry.type == 'checkpoint' and isinstance(entry.result, dict):
                if entry.result.get('name') == name:
                    target_time = entry.timestamp
                    break

        if target_time is None:
            return

        # Keep only checkpoints older than target
        metadata.execution_log = [
            entry for entry in metadata.execution_log
            if entry.timestamp < target_time
        ]
        self.save_procedure_metadata(procedure_id, metadata)

    def get_state(self, procedure_id: str) -> Dict[str, Any]:
        """Get mutable state dictionary."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.state

    def set_state(self, procedure_id: str, state: Dict[str, Any]) -> None:
        """Set mutable state dictionary."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state = {k: _lua_to_serializable(v) for k, v in state.items()}
        self.save_procedure_metadata(procedure_id, metadata)

    def state_get(self, procedure_id: str, key: str, default: Any = None) -> Any:
        """Get state value."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.state.get(key, default)

    def state_set(self, procedure_id: str, key: str, value: Any) -> None:
        """Set state value."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state[key] = _lua_to_serializable(value)
        self.save_procedure_metadata(procedure_id, metadata)

    def state_delete(self, procedure_id: str, key: str) -> None:
        """Delete state key."""
        metadata = self.load_procedure_metadata(procedure_id)
        if key in metadata.state:
            del metadata.state[key]
            self.save_procedure_metadata(procedure_id, metadata)

    def state_clear(self, procedure_id: str) -> None:
        """Clear all state."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state = {}
        self.save_procedure_metadata(procedure_id, metadata)
