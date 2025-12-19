"""
Resume service for procedure HITL operations.

Handles resuming procedures that are waiting for human responses.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def resume_procedure(client, procedure_id: str) -> Dict[str, Any]:
    """
    Resume a single procedure (idempotent).

    Args:
        client: PlexusDashboardClient
        procedure_id: Procedure ID to resume

    Returns:
        Dict with:
            - resumed: bool - Whether procedure was resumed
            - status: str - Current procedure status
            - reason: str - Why no action was taken (if not resumed)
            - message: str - Additional information
    """
    # Get procedure
    query = """
        query GetProcedure($id: ID!) {
            getProcedure(id: $id) {
                id
                status
                waitingOnMessageId
                code
            }
        }
    """

    result = client.execute(query, {'id': procedure_id})
    procedure = result.get('getProcedure')

    if not procedure:
        return {
            'resumed': False,
            'status': 'NOT_FOUND',
            'reason': 'Procedure not found'
        }

    status = procedure.get('status')

    # Check if procedure is waiting for human
    if status != 'WAITING_FOR_HUMAN':
        return {
            'resumed': False,
            'status': status,
            'reason': f'Procedure is not waiting for human (status: {status})'
        }

    # Check if there's a response
    pending_message_id = procedure.get('waitingOnMessageId')
    if not pending_message_id:
        return {
            'resumed': False,
            'status': status,
            'reason': 'No pending message ID found'
        }

    logger.info(f"Looking for RESPONSE with parentMessageId={pending_message_id}")

    # Check for response message using GSI
    response_query = """
        query FindResponse($parentId: String!) {
            listChatMessageByParentMessageId(
                parentMessageId: $parentId
                filter: {
                    humanInteraction: {eq: RESPONSE}
                }
                limit: 1
            ) {
                items {
                    id
                    createdAt
                }
            }
        }
    """

    response_result = client.execute(response_query, {'parentId': pending_message_id})
    logger.info(f"Query result: {response_result}")
    responses = response_result.get('listChatMessageByParentMessageId', {}).get('items', [])
    logger.info(f"Found {len(responses)} RESPONSE messages")

    if not responses:
        return {
            'resumed': False,
            'status': status,
            'reason': 'Still waiting for human response'
        }

    # Found a response - re-run the procedure
    logger.info(f"Resuming procedure {procedure_id} with response...")

    from plexus.cli.procedure.service import ProcedureService
    service = ProcedureService(client)

    try:
        # Run procedure (will replay checkpoints and continue from HITL point)
        import asyncio
        run_result = asyncio.run(service.run_experiment(
            procedure_id=procedure_id
        ))

        # run_result is a dict, not an object
        if run_result.get('success'):
            return {
                'resumed': True,
                'status': run_result.get('status') or 'COMPLETE',
                'message': 'Procedure resumed and executed successfully'
            }
        else:
            return {
                'resumed': True,
                'status': run_result.get('status') or 'ERROR',
                'message': f"Procedure resumed but failed: {run_result.get('message', 'Unknown error')}"
            }

    except Exception as e:
        logger.error(f"Error running procedure {procedure_id}: {e}", exc_info=True)
        return {
            'resumed': False,
            'status': 'ERROR',
            'reason': f'Failed to run procedure: {e}'
        }


def resume_all_pending(client) -> Dict[str, Any]:
    """
    Resume all procedures waiting for human responses.

    Args:
        client: PlexusDashboardClient

    Returns:
        Dict with:
            - found: int - Number of waiting procedures found
            - resumed: int - Number successfully resumed
            - resumed_ids: List[str] - IDs of resumed procedures
    """
    # Query all procedures with status WAITING_FOR_HUMAN
    query = """
        query ListWaitingProcedures {
            listProcedures(
                filter: {
                    status: {eq: "WAITING_FOR_HUMAN"}
                }
            ) {
                items {
                    id
                    waitingOnMessageId
                }
            }
        }
    """

    result = client.execute(query)
    procedures = result.get('listProcedures', {}).get('items', [])

    logger.info(f"Found {len(procedures)} procedures waiting for human")

    resumed_count = 0
    resumed_ids = []

    for proc in procedures:
        proc_id = proc['id']
        logger.info(f"Checking procedure {proc_id}...")

        result = resume_procedure(client, proc_id)

        if result['resumed']:
            resumed_count += 1
            resumed_ids.append(proc_id)
            logger.info(f"✓ Resumed {proc_id}")
        else:
            logger.debug(f"• Skipped {proc_id}: {result['reason']}")

    return {
        'found': len(procedures),
        'resumed': resumed_count,
        'resumed_ids': resumed_ids
    }
