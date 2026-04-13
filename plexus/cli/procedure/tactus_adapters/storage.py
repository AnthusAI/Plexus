"""
Plexus Storage Adapter for Tactus.

Implements the Tactus StorageBackend protocol using Plexus GraphQL API.
Stores checkpoints and state in the Procedure.metadata JSON field.
"""

import logging
import json
import os
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from tactus.protocols.models import ProcedureMetadata, CheckpointEntry
from plexus.cli.procedure.builtin_procedures import is_builtin_procedure_id

logger = logging.getLogger(__name__)

# S3 offload settings for large metadata
_S3_THRESHOLD = 350_000  # bytes — offload state when metadata exceeds this (DynamoDB limit is 400KB)
_S3_BUCKET = os.environ.get("AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME", "reportblockdetails-production")


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


class PlexusStorageAdapter:
    """
    Implements Tactus StorageBackend protocol using Plexus GraphQL.

    Stores all procedure data (checkpoints, state, lua_state) in the
    Procedure.metadata JSON field via GraphQL mutations.
    """

    def __init__(self, client, procedure_id: str):
        """
        Initialize Plexus storage adapter.

        Args:
            client: PlexusDashboardClient instance
            procedure_id: ID of the procedure
        """
        self.client = client
        self.procedure_id = procedure_id
        self._is_builtin = is_builtin_procedure_id(procedure_id)
        self._metadata_cache: Optional[ProcedureMetadata] = None
        logger.info(f"PlexusStorageAdapter initialized for procedure {procedure_id}")

    def load_procedure_metadata(self, procedure_id: str) -> ProcedureMetadata:
        """
        Load procedure metadata from Plexus via GraphQL.

        Args:
            procedure_id: Procedure ID to load

        Returns:
            ProcedureMetadata with checkpoints, state, and lua_state
        """
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

        # Query GraphQL for procedure metadata
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

        try:
            response = self.client.execute(query, {'id': procedure_id})
            procedure_data = response.get('getProcedure')

            if not procedure_data:
                logger.warning(f"Procedure {procedure_id} not found, creating new metadata")
                metadata = ProcedureMetadata(procedure_id=procedure_id)
                self._metadata_cache = metadata
                return metadata

            # Parse metadata JSON field
            raw_metadata = procedure_data.get('metadata') or {}
            if isinstance(raw_metadata, str):
                try:
                    raw_metadata = json.loads(raw_metadata)
                except Exception:
                    logger.warning("Procedure metadata was not valid JSON; defaulting to empty object")
                    raw_metadata = {}

            # Convert checkpoint data to execution_log
            execution_log = []
            position = 0
            for name, ckpt_data in raw_metadata.get('checkpoints', {}).items():
                execution_log.append(CheckpointEntry(
                    position=position,
                    type='checkpoint',
                    result={'name': name, 'data': ckpt_data.get('result')},
                    timestamp=datetime.fromisoformat(ckpt_data.get('completed_at'))
                ))
                position += 1

            # Load state — may be offloaded to S3 for large procedures
            state_data = raw_metadata.get('state', {})
            if isinstance(state_data, dict) and '_s3_key' in state_data:
                try:
                    s3 = boto3.client('s3')
                    obj = s3.get_object(Bucket=_S3_BUCKET, Key=state_data['_s3_key'])
                    state_data = json.loads(obj['Body'].read().decode('utf-8'))
                    logger.info("Loaded state from S3: %s/%s", _S3_BUCKET, state_data.get('_s3_key', ''))
                except (ClientError, json.JSONDecodeError) as s3_err:
                    logger.error("Failed to load state from S3: %s — using empty state", s3_err)
                    state_data = {}

            # Create metadata object
            metadata = ProcedureMetadata(
                procedure_id=procedure_id,
                execution_log=execution_log,
                replay_index=raw_metadata.get('replay_index', 0),  # Default to 0 if not set
                state=state_data,
                lua_state=raw_metadata.get('lua_state', {}),
                status=procedure_data.get('status') or 'RUNNING',
                waiting_on_message_id=procedure_data.get('waitingOnMessageId')
            )

            self._metadata_cache = metadata
            logger.debug(f"Loaded metadata for {procedure_id}: {len(execution_log)} checkpoints, {len(metadata.state)} state keys")
            return metadata

        except Exception as e:
            logger.error(f"Error loading procedure metadata: {e}", exc_info=True)
            # Return empty metadata on error
            metadata = ProcedureMetadata(procedure_id=procedure_id)
            self._metadata_cache = metadata
            return metadata

    def save_procedure_metadata(self, procedure_id: str, metadata: ProcedureMetadata) -> None:
        """
        Save procedure metadata to Plexus via GraphQL.

        Args:
            procedure_id: Procedure ID (for API compatibility)
            metadata: ProcedureMetadata to save
        """
        # Convert execution_log to serializable format (store as checkpoints for backward compat)
        checkpoints_dict = {}
        for checkpoint in metadata.execution_log:
            if checkpoint.type == 'checkpoint' and isinstance(checkpoint.result, dict):
                name = checkpoint.result.get('name', f'checkpoint_{checkpoint.position}')
                checkpoints_dict[name] = {
                    'name': name,
                    'result': checkpoint.result.get('data'),
                    'completed_at': checkpoint.timestamp.isoformat()
                }

        # Build metadata JSON
        metadata_json = {
            'checkpoints': checkpoints_dict,
            'state': metadata.state,
            'lua_state': metadata.lua_state,
            'replay_index': metadata.replay_index
        }

        # Update via GraphQL mutation
        mutation = """
        mutation UpdateProcedureMetadata($id: ID!, $metadata: AWSJSON!) {
            updateProcedure(input: {
                id: $id
                metadata: $metadata
            }) {
                id
                metadata
            }
        }
        """

        try:
            if self._is_builtin:
                self._metadata_cache = metadata
                logger.debug("Saved in-memory metadata for built-in procedure %s", metadata.procedure_id)
                return

            serialized = json.dumps(metadata_json)

            # If metadata exceeds DynamoDB threshold, offload state to S3
            if len(serialized) > _S3_THRESHOLD:
                s3_key = f"procedures/{metadata.procedure_id}/state.json"
                state_json = json.dumps(metadata.state)
                try:
                    s3 = boto3.client('s3')
                    s3.put_object(
                        Bucket=_S3_BUCKET,
                        Key=s3_key,
                        Body=state_json.encode('utf-8'),
                        ContentType='application/json'
                    )
                    logger.info(
                        "Offloaded %d bytes of state to S3: %s/%s",
                        len(state_json), _S3_BUCKET, s3_key
                    )
                    # Replace state with S3 reference in metadata
                    metadata_json['state'] = {'_s3_key': s3_key}
                    serialized = json.dumps(metadata_json)
                except ClientError as s3_err:
                    logger.error("Failed to offload state to S3: %s", s3_err)
                    raise

            self.client.execute(mutation, {
                'id': metadata.procedure_id,
                'metadata': serialized
            })

            # Update cache
            self._metadata_cache = metadata
            logger.debug(f"Saved metadata for {metadata.procedure_id}")

        except Exception as e:
            logger.error(f"Error saving procedure metadata: {e}", exc_info=True)
            raise

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
                status
                waitingOnMessageId
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

            self.client.execute(mutation, {
                'id': procedure_id,
                'status': status,
                'waitingOnMessageId': waiting_on_message_id
            })

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
