"""
Reset service for procedure checkpoint management.

Handles clearing checkpoints for testing and development.
"""

import logging
import json
from typing import Dict, Any, Optional
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

    result = client.query(query, {'id': procedure_id})
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

    client.mutate(mutation, {
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
