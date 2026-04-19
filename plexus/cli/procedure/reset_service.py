"""
Reset service for procedure checkpoint management.

Handles clearing checkpoints for testing and development.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def reset_checkpoints(client, procedure_id: str, after_step: Optional[str] = None) -> Dict[str, Any]:
    """
    Clear procedure checkpoints.

    Args:
        client: PlexusDashboardClient
        procedure_id: Procedure ID
        after_step: If provided, clear this step and all subsequent ones.
                   If None, clear all checkpoints.

    Returns:
        Dict with:
            - cleared_count: int - Number of checkpoints cleared
            - remaining_count: int - Number of checkpoints remaining
    """
    # Get procedure
    query = """
        query GetProcedure($id: ID!) {
            getProcedure(id: $id) {
                id
                metadata
            }
        }
    """

    result = client.execute(query, {'id': procedure_id})
    procedure = result.get('getProcedure')

    if not procedure:
        raise ValueError(f"Procedure {procedure_id} not found")

    # Parse metadata
    metadata_str = procedure.get('metadata')
    if metadata_str:
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            metadata = {}
    else:
        metadata = {}

    checkpoints = metadata.get('checkpoints', {})
    initial_count = len(checkpoints)

    if after_step:
        # Partial clear: remove checkpoint and all subsequent ones
        if after_step not in checkpoints:
            logger.warning(f"Checkpoint '{after_step}' not found")
            return {
                'cleared_count': 0,
                'remaining_count': initial_count
            }

        target_time = checkpoints[after_step]['completed_at']

        # Remove all checkpoints at or after target time
        new_checkpoints = {
            k: v for k, v in checkpoints.items()
            if v['completed_at'] < target_time
        }

        metadata['checkpoints'] = new_checkpoints
    else:
        # Full clear: remove all checkpoints
        metadata['checkpoints'] = {}
        metadata['state'] = {}
        metadata['lua_state'] = {}

    # Update procedure
    mutation = """
        mutation UpdateProcedureMetadata($id: ID!, $metadata: AWSJSON!) {
            updateProcedure(input: {
                id: $id
                metadata: $metadata
                status: "PENDING"
            }) {
                id
            }
        }
    """

    client.execute(mutation, {
        'id': procedure_id,
        'metadata': json.dumps(metadata)
    })

    final_count = len(metadata.get('checkpoints', {}))
    cleared_count = initial_count - final_count

    logger.info(f"Cleared {cleared_count} checkpoints from procedure {procedure_id}")

    return {
        'cleared_count': cleared_count,
        'remaining_count': final_count
    }


def reset_checkpoints_only(client, procedure_id: str) -> Dict[str, Any]:
    """
    Clear procedure checkpoints while preserving accumulated State.

    Used before re-dispatching a procedure for continuation: Tactus must not
    replay cached steps, but the optimizer State (iterations, baselines, etc.)
    must survive so the optimizer can detect continuation and skip init.

    Returns:
        Dict with cleared_count and remaining_count
    """
    query = """
        query GetProcedure($id: ID!) {
            getProcedure(id: $id) {
                id
                metadata
            }
        }
    """

    result = client.execute(query, {'id': procedure_id})
    procedure = result.get('getProcedure')

    if not procedure:
        raise ValueError(f"Procedure {procedure_id} not found")

    metadata_str = procedure.get('metadata')
    if metadata_str:
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            metadata = {}
    else:
        metadata = {}

    initial_count = len(metadata.get('checkpoints', {}))

    # Clear ONLY checkpoints — state, lua_state are preserved intentionally
    metadata['checkpoints'] = {}

    mutation = """
        mutation UpdateProcedureMetadata($id: ID!, $metadata: AWSJSON!) {
            updateProcedure(input: {
                id: $id
                metadata: $metadata
                status: "PENDING"
            }) {
                id
            }
        }
    """

    client.execute(mutation, {
        'id': procedure_id,
        'metadata': json.dumps(metadata)
    })

    logger.info(f"Cleared {initial_count} checkpoints from procedure {procedure_id} (State preserved)")

    return {
        'cleared_count': initial_count,
        'remaining_count': 0
    }


def clone_state_for_branch(
    client,
    source_procedure_id: str,
    target_procedure_id: str,
    truncate_to_cycle: int,
) -> Dict[str, Any]:
    """
    Clone S3 state from source procedure to target, truncated to cycle N.

    Used to implement branching: the target procedure starts from cycle N of
    the source, with empty checkpoints (fresh execution), so the optimizer
    detects continuation at cycle N and runs additional cycles from there.

    The source procedure is never modified.

    Returns:
        Dict with source_procedure_id, target_procedure_id,
        truncated_to_cycle, iterations_copied.
    """
    from plexus.cli.procedure.tactus_adapters.storage import PlexusStorageAdapter
    from tactus.protocols.models import ProcedureMetadata

    source_storage = PlexusStorageAdapter(client, source_procedure_id)
    target_storage = PlexusStorageAdapter(client, target_procedure_id)

    # Load source state
    source_metadata = source_storage.load_procedure_metadata(source_procedure_id)
    source_state: Dict[str, Any] = dict(source_metadata.state or {})

    # Truncate iterations to the branch point
    iterations: List[Any] = source_state.get('iterations') or []
    truncated: List[Any] = iterations[:truncate_to_cycle]
    source_state['iterations'] = truncated

    # Clear mailbox watermark so the branch doesn't skip injected messages
    source_state.pop('last_mailbox_check', None)

    # _procedure_id will be overwritten by procedure_executor before the run,
    # but clear it now so the target doesn't accidentally poll the source mailbox.
    source_state.pop('_procedure_id', None)

    # Create fresh metadata for target: truncated state, no checkpoints, no lua_state
    target_metadata = ProcedureMetadata(
        procedure_id=target_procedure_id,
        execution_log=[],
        state=source_state,
        lua_state={},
    )

    target_storage.save_procedure_metadata(target_procedure_id, target_metadata)
    target_storage.update_procedure_status(target_procedure_id, 'PENDING')

    logger.info(
        "Cloned state from %s → %s (truncated to %d cycles, %d iterations copied)",
        source_procedure_id, target_procedure_id, truncate_to_cycle, len(truncated),
    )

    return {
        'source_procedure_id': source_procedure_id,
        'target_procedure_id': target_procedure_id,
        'truncated_to_cycle': truncate_to_cycle,
        'iterations_copied': len(truncated),
    }
