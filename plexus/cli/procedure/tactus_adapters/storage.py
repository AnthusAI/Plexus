"""
Plexus Storage Adapter for Tactus.

Implements the Tactus StorageBackend protocol using Plexus GraphQL API.
Stores checkpoints and state in the Procedure.metadata JSON field.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from tactus.protocols.models import ProcedureMetadata, CheckpointEntry

logger = logging.getLogger(__name__)


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

        # Query GraphQL for procedure metadata
        query = """
        query GetProcedure($id: ID!) {
            procedure(id: $id) {
                id
                metadata
                status
                waitingOnMessageId
            }
        }
        """

        try:
            response = self.client.execute(query, {'id': procedure_id})
            procedure_data = response.get('procedure')

            if not procedure_data:
                logger.warning(f"Procedure {procedure_id} not found, creating new metadata")
                metadata = ProcedureMetadata(procedure_id=procedure_id)
                self._metadata_cache = metadata
                return metadata

            # Parse metadata JSON field
            raw_metadata = procedure_data.get('metadata') or {}

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

            # Create metadata object
            metadata = ProcedureMetadata(
                procedure_id=procedure_id,
                execution_log=execution_log,
                replay_index=raw_metadata.get('replay_index'),
                state=raw_metadata.get('state', {}),
                lua_state=raw_metadata.get('lua_state', {}),
                status=procedure_data.get('status', 'RUNNING'),
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
        mutation UpdateProcedureMetadata($id: ID!, $metadata: JSON!) {
            updateProcedure(input: {
                id: $id
                metadata: $metadata
            }) {
                procedure {
                    id
                    metadata
                }
            }
        }
        """

        try:
            self.client.execute(mutation, {
                'id': metadata.procedure_id,
                'metadata': metadata_json
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
        mutation UpdateProcedureStatus($id: ID!, $status: ProcedureStatus!, $waitingOnMessageId: ID) {
            updateProcedure(input: {
                id: $id
                status: $status
                waitingOnMessageId: $waitingOnMessageId
            }) {
                procedure {
                    id
                    status
                    waitingOnMessageId
                }
            }
        }
        """

        try:
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
        metadata.state = state
        self.save_procedure_metadata(procedure_id, metadata)

    def state_get(self, procedure_id: str, key: str, default: Any = None) -> Any:
        """Get state value."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.state.get(key, default)

    def state_set(self, procedure_id: str, key: str, value: Any) -> None:
        """Set state value."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state[key] = value
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
