"""
Plexus Storage Adapter for Tactus.

Implements the Tactus StorageBackend protocol using Plexus GraphQL API.
Stores checkpoints and state in the Procedure.metadata JSON field.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from tactus.protocols.models import ProcedureMetadata, CheckpointData

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

            # Convert checkpoint data
            checkpoints = {}
            for name, ckpt_data in raw_metadata.get('checkpoints', {}).items():
                checkpoints[name] = CheckpointData(
                    name=name,
                    result=ckpt_data.get('result'),
                    completed_at=datetime.fromisoformat(ckpt_data.get('completed_at'))
                )

            # Create metadata object
            metadata = ProcedureMetadata(
                procedure_id=procedure_id,
                checkpoints=checkpoints,
                state=raw_metadata.get('state', {}),
                lua_state=raw_metadata.get('lua_state', {}),
                status=procedure_data.get('status', 'RUNNING'),
                waiting_on_message_id=procedure_data.get('waitingOnMessageId')
            )

            self._metadata_cache = metadata
            logger.debug(f"Loaded metadata for {procedure_id}: {len(checkpoints)} checkpoints, {len(metadata.state)} state keys")
            return metadata

        except Exception as e:
            logger.error(f"Error loading procedure metadata: {e}", exc_info=True)
            # Return empty metadata on error
            metadata = ProcedureMetadata(procedure_id=procedure_id)
            self._metadata_cache = metadata
            return metadata

    def save_procedure_metadata(self, metadata: ProcedureMetadata) -> None:
        """
        Save procedure metadata to Plexus via GraphQL.

        Args:
            metadata: ProcedureMetadata to save
        """
        # Convert checkpoints to serializable format
        checkpoints_dict = {}
        for name, checkpoint in metadata.checkpoints.items():
            checkpoints_dict[name] = {
                'name': checkpoint.name,
                'result': checkpoint.result,
                'completed_at': checkpoint.completed_at.isoformat()
            }

        # Build metadata JSON
        metadata_json = {
            'checkpoints': checkpoints_dict,
            'state': metadata.state,
            'lua_state': metadata.lua_state
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
        return name in metadata.checkpoints

    def checkpoint_get(self, procedure_id: str, name: str) -> Optional[Any]:
        """Get checkpoint value."""
        metadata = self.load_procedure_metadata(procedure_id)
        checkpoint = metadata.checkpoints.get(name)
        return checkpoint.result if checkpoint else None

    def checkpoint_save(
        self,
        procedure_id: str,
        name: str,
        result: Any
    ) -> None:
        """Save a checkpoint."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.checkpoints[name] = CheckpointData(
            name=name,
            result=result,
            completed_at=datetime.now(timezone.utc)
        )
        self.save_procedure_metadata(metadata)

    def checkpoint_clear_all(self, procedure_id: str) -> None:
        """Clear all checkpoints (but preserve state)."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.checkpoints.clear()
        self.save_procedure_metadata(metadata)

    def checkpoint_clear_after(self, procedure_id: str, name: str) -> None:
        """Clear checkpoint and all subsequent ones."""
        metadata = self.load_procedure_metadata(procedure_id)

        if name not in metadata.checkpoints:
            return

        target_time = metadata.checkpoints[name].completed_at

        # Keep only checkpoints older than target
        metadata.checkpoints = {
            k: v for k, v in metadata.checkpoints.items()
            if v.completed_at < target_time
        }
        self.save_procedure_metadata(metadata)

    def get_state(self, procedure_id: str) -> Dict[str, Any]:
        """Get mutable state dictionary."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.state

    def set_state(self, procedure_id: str, state: Dict[str, Any]) -> None:
        """Set mutable state dictionary."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state = state
        self.save_procedure_metadata(metadata)

    def state_get(self, procedure_id: str, key: str, default: Any = None) -> Any:
        """Get state value."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.state.get(key, default)

    def state_set(self, procedure_id: str, key: str, value: Any) -> None:
        """Set state value."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state[key] = value
        self.save_procedure_metadata(metadata)

    def state_delete(self, procedure_id: str, key: str) -> None:
        """Delete state key."""
        metadata = self.load_procedure_metadata(procedure_id)
        if key in metadata.state:
            del metadata.state[key]
            self.save_procedure_metadata(metadata)

    def state_clear(self, procedure_id: str) -> None:
        """Clear all state."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state = {}
        self.save_procedure_metadata(metadata)
