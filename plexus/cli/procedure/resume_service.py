"""
Resume service for procedure HITL operations.

Handles resuming procedures that are waiting for human responses.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from plexus.cli.procedure.scheduled_continuation import (
    canonical_time_wait_request,
    time_wait_is_due,
)

logger = logging.getLogger(__name__)
_TERMINAL_TASK_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}
_CHILD_REFERENCE_FIELDS = (
    "id", "procedure_id", "task_id", "scorecard_id", "score_id",
)
_PROCEDURE_SCAN_PAGE_SIZE = 1000


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _stored_json_value(value: Any, parsed: Dict[str, Any]) -> str:
    """Preserve the exact AWSJSON string used by optimistic conditions."""
    return value if isinstance(value, str) else json.dumps(parsed)


def _canonical_child_request(value: Any) -> Dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("mode") != "any":
        return None
    children = value.get("children")
    if not isinstance(children, list) or not children:
        return None
    normalized = []
    identities = set()
    for child in children:
        if not isinstance(child, dict):
            return None
        reference = {
            field: child.get(field).strip()
            if isinstance(child.get(field), str) else ""
            for field in _CHILD_REFERENCE_FIELDS
        }
        if any(not reference[field] for field in _CHILD_REFERENCE_FIELDS):
            return None
        if reference["id"] in identities:
            return None
        identities.add(reference["id"])
        normalized.append(reference)
    return {"children": normalized, "mode": "any"}


def _pending_checkpoint_entry(
    metadata: Any,
    *,
    checkpoint_type: str,
    expected_run_id: str | None,
) -> Any | None:
    """Return the pending entry at Tactus's exact durable replay boundary."""
    execution_log = getattr(metadata, "execution_log", None)
    if not isinstance(execution_log, list) or not execution_log:
        return None
    replay_index = getattr(metadata, "replay_index", None)
    if (
        isinstance(replay_index, bool)
        or not isinstance(replay_index, int)
        or replay_index < 1
        or replay_index > len(execution_log)
    ):
        return None
    index = replay_index - 1
    entry = execution_log[index]
    result = getattr(entry, "result", None)
    if index != len(execution_log) - 1 or getattr(entry, "position", index) != index:
        return None
    if (
        getattr(entry, "type", None) != checkpoint_type
        or not isinstance(result, dict)
        or result.get("pending") is not True
        or not isinstance(expected_run_id, str)
        or not expected_run_id
        or getattr(entry, "run_id", None) != expected_run_id
    ):
        return None
    return entry


def _load_pending_external_child_request(
    client, procedure_id: str, *, expected_run_id: str | None = None,
) -> Dict[str, Any] | None:
    """Load the exact pending Tactus checkpoint at the replay boundary."""
    try:
        from plexus.cli.procedure.tactus_adapters.storage import PlexusStorageAdapter

        metadata = PlexusStorageAdapter(client, procedure_id).load_procedure_metadata(
            procedure_id
        )
        entry = _pending_checkpoint_entry(
            metadata,
            checkpoint_type="external_children_wait",
            expected_run_id=expected_run_id,
        )
        if entry is None:
            return None
        return _canonical_child_request(entry.result.get("request"))
    except Exception as exc:
        logger.warning(
            "Could not load pending external-child checkpoint for %s: %s",
            procedure_id,
            exc,
        )
        return None


def _load_pending_time_wait_request(
    client, procedure_id: str, *, expected_run_id: str | None = None,
) -> Dict[str, Any] | None:
    """Load only the indexed native Tactus time-wait checkpoint."""
    try:
        from plexus.cli.procedure.tactus_adapters.storage import PlexusStorageAdapter

        metadata = PlexusStorageAdapter(client, procedure_id).load_procedure_metadata(
            procedure_id
        )
        entry = _pending_checkpoint_entry(
            metadata,
            checkpoint_type="scheduled_continuation",
            expected_run_id=expected_run_id,
        )
        if entry is None:
            return None
        return canonical_time_wait_request(entry.result.get("request"))
    except Exception as exc:
        logger.warning(
            "Could not load pending scheduled-continuation checkpoint for %s: %s",
            procedure_id,
            exc,
        )
        return None


def _optimizer_backend(client):
    from plexus.optimization.optimizer_dispatch_backend import (
        GraphQLOptimizerDispatchBackend,
    )

    return GraphQLOptimizerDispatchBackend(client)


def _boundary(
    *, procedure_id: str, parent_task_id: str, request: Dict[str, Any], children: Any,
) -> Dict[str, Any]:
    return {
        "procedure_id": procedure_id,
        "parent_task_id": parent_task_id,
        "request": request,
        "children": children if isinstance(children, list) else [],
    }


def _resume_after_child_completion(
    client,
    procedure: Dict[str, Any],
    *,
    checkpoint_request: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Repair and atomically rearm one exclusively corroborated parent."""
    status = "WAITING_FOR_CHILDREN"
    procedure_id = procedure.get("id")
    account_id = procedure.get("accountId")
    if not isinstance(procedure_id, str) or not procedure_id or not isinstance(account_id, str) or not account_id:
        return {"resumed": False, "status": status, "reason": "Exclusive parent identity is incomplete"}

    metadata = _json_object(procedure.get("metadata"))
    runtime = metadata.get("runtime")
    expected_run_id = runtime.get("tactus_run_id") if isinstance(runtime, dict) else None
    checkpoint_request = checkpoint_request or _load_pending_external_child_request(
        client, procedure_id, expected_run_id=expected_run_id,
    )
    if checkpoint_request is None:
        return {
            "resumed": False,
            "status": status,
            "reason": "Durable child-wait checkpoint is missing or malformed",
        }

    procedure_boundary = metadata.get("waiting_for_children")
    parent_task_id = (
        procedure_boundary.get("parent_task_id")
        if isinstance(procedure_boundary, dict)
        else runtime.get("task_id") if isinstance(runtime, dict) else None
    )
    if not isinstance(parent_task_id, str) or not parent_task_id:
        return {"resumed": False, "status": status, "reason": "Exclusive parent Task identity is missing"}
    if isinstance(procedure_boundary, dict) and (
        procedure_boundary.get("procedure_id") != procedure_id
        or procedure_boundary.get("parent_task_id") != parent_task_id
        or _canonical_child_request(procedure_boundary.get("request")) != checkpoint_request
    ):
        return {"resumed": False, "status": status, "reason": "Exclusive parent Procedure boundary does not match checkpoint"}

    backend = _optimizer_backend(client)
    parent_task = backend.get_task(parent_task_id)
    if not isinstance(parent_task, dict):
        return {"resumed": False, "status": status, "reason": "Exclusive parent Task was not found"}
    parent_task_metadata = _json_object(parent_task.get("metadata"))
    if (
        parent_task.get("accountId") != account_id
        or parent_task.get("target") not in {f"procedure/{procedure_id}", f"procedure/run/{procedure_id}"}
        or parent_task.get("command") != f"procedure run {procedure_id}"
        or parent_task_metadata.get("procedure_id") != procedure_id
    ):
        return {"resumed": False, "status": status, "reason": "Exclusive parent Task linkage is invalid"}
    task_boundary = parent_task_metadata.get("waiting_for_children")
    if isinstance(task_boundary, dict) and (
        task_boundary.get("procedure_id") != procedure_id
        or task_boundary.get("parent_task_id") != parent_task_id
        or _canonical_child_request(task_boundary.get("request")) != checkpoint_request
    ):
        return {"resumed": False, "status": status, "reason": "Exclusive parent Task boundary does not match checkpoint"}

    observed_children = (
        procedure_boundary.get("children")
        if isinstance(procedure_boundary, dict)
        else task_boundary.get("children") if isinstance(task_boundary, dict) else []
    )
    canonical_boundary = _boundary(
        procedure_id=procedure_id,
        parent_task_id=parent_task_id,
        request=checkpoint_request,
        children=observed_children,
    )

    if procedure.get("status") != "WAITING_FOR_CHILDREN":
        if procedure.get("status") != "RUNNING":
            return {"resumed": False, "status": str(procedure.get("status")), "reason": "Procedure is not eligible for child-wait repair"}
        repaired_metadata = {**metadata, "waiting_for_children": canonical_boundary}
        mutation = """
          mutation RepairWaitingProcedure($input: UpdateProcedureInput!, $condition: ModelProcedureConditionInput) {
            updateProcedure(input: $input, condition: $condition) { id status accountId metadata }
          }
        """
        repaired = client.execute(mutation, {
            "input": {"id": procedure_id, "status": "WAITING_FOR_CHILDREN", "metadata": json.dumps(repaired_metadata)},
            "condition": {"and": [
                {"status": {"eq": "RUNNING"}},
                {"metadata": {"eq": json.dumps(metadata)}},
            ]},
        }).get("updateProcedure")
        if not isinstance(repaired, dict) or repaired.get("status") != "WAITING_FOR_CHILDREN":
            return {"resumed": False, "status": status, "reason": "Procedure child-wait repair was not accepted"}
        procedure = repaired
        metadata = _json_object(procedure.get("metadata"))

    task_waiting = (
        parent_task.get("status") == "WAITING_FOR_CHILDREN"
        and parent_task.get("dispatchStatus") == "WAITING_FOR_CHILDREN"
    )
    if not task_waiting:
        if (
            parent_task.get("status") != "RUNNING"
            or parent_task.get("dispatchStatus")
            not in {"DISPATCHING", "DISPATCHED", "LOCAL"}
        ):
            return {
                "resumed": False,
                "status": status,
                "reason": "Exclusive parent Task is not in a repairable active state",
            }
        repaired_task_metadata = {
            **parent_task_metadata,
            "dispatch_policy": "resume_once",
            "waiting_for_children": canonical_boundary,
        }
        mutation = """
          mutation RepairWaitingParentTask($input: UpdateTaskInput!, $condition: ModelTaskConditionInput) {
            updateTask(input: $input, condition: $condition) { id accountId status dispatchStatus target command metadata }
          }
        """
        repaired = client.execute(mutation, {
            "input": {
                "id": parent_task_id,
                "status": "WAITING_FOR_CHILDREN",
                "dispatchStatus": "WAITING_FOR_CHILDREN",
                "metadata": json.dumps(repaired_task_metadata),
            },
            "condition": {"and": [
                {"status": {"eq": parent_task.get("status")}},
                {"dispatchStatus": {"eq": parent_task.get("dispatchStatus")}},
                {"metadata": {"eq": json.dumps(parent_task_metadata)}},
            ]},
        }).get("updateTask")
        if not isinstance(repaired, dict) or repaired.get("dispatchStatus") != "WAITING_FOR_CHILDREN":
            return {"resumed": False, "status": status, "reason": "Parent Task child-wait repair was not accepted"}
        parent_task = repaired
        parent_task_metadata = _json_object(parent_task.get("metadata"))

    if (
        procedure.get("status") != "WAITING_FOR_CHILDREN"
        or parent_task.get("status") != "WAITING_FOR_CHILDREN"
        or parent_task.get("dispatchStatus") != "WAITING_FOR_CHILDREN"
        or _json_object(procedure.get("metadata")).get("waiting_for_children") != canonical_boundary
        or parent_task_metadata.get("waiting_for_children") != canonical_boundary
    ):
        return {"resumed": False, "status": status, "reason": "Exclusive parent wait boundary is not corroborated"}

    from plexus.cli.procedure.tactus_adapters.external_children import (
        OptimizerExternalChildResolver,
    )
    resolved = OptimizerExternalChildResolver(
        backend=backend, account_id=account_id,
    )(checkpoint_request)
    snapshots = resolved.get("children") if isinstance(resolved, dict) else None
    if not isinstance(snapshots, list) or not any(row.get("terminal") is True for row in snapshots if isinstance(row, dict)):
        return {
            "resumed": False,
            "status": status,
            "reason": "Still waiting for an optimizer child to finish",
        }

    mutation = """
        mutation RearmWaitingParent(
            $input: UpdateTaskInput!
            $condition: ModelTaskConditionInput
        ) {
            updateTask(input: $input, condition: $condition) {
                id
                status
                dispatchStatus
            }
        }
    """
    try:
        updated = client.execute(mutation, {
            "input": {"id": parent_task_id, "dispatchStatus": "PENDING"},
            "condition": {"and": [
                {"status": {"eq": "WAITING_FOR_CHILDREN"}},
                {"dispatchStatus": {"eq": "WAITING_FOR_CHILDREN"}},
                {"metadata": {"eq": json.dumps(parent_task_metadata)}},
            ]},
        }).get("updateTask")
    except Exception as exc:
        logger.info(
            "Parent task %s was not rearmed (duplicate or racing recovery tick): %s",
            parent_task_id,
            exc,
        )
        return {
            "resumed": False,
            "status": status,
            "reason": "Parent resume was already claimed or is no longer eligible",
        }
    if not isinstance(updated, dict) or updated.get("dispatchStatus") != "PENDING":
        return {
            "resumed": False,
            "status": status,
            "reason": "Parent resume was already claimed or is no longer eligible",
        }
    return {
        "resumed": True,
        "status": "PENDING",
        "message": "Procedure resume scheduled after child completion",
    }


def _resume_after_time_due(
    client,
    procedure: Dict[str, Any],
    *,
    checkpoint_request: Dict[str, Any] | None = None,
    now: datetime | None = None,
) -> Dict[str, Any]:
    """Repair and conditionally rearm one exact native continuation."""
    status = "WAITING_FOR_TIME"
    procedure_id = procedure.get("id")
    account_id = procedure.get("accountId")
    if not isinstance(procedure_id, str) or not procedure_id or not isinstance(account_id, str) or not account_id:
        return {"resumed": False, "status": status, "reason": "Scheduled continuation identity is incomplete"}

    raw_procedure_metadata = procedure.get("metadata")
    metadata = _json_object(raw_procedure_metadata)
    runtime = metadata.get("runtime")
    expected_run_id = runtime.get("tactus_run_id") if isinstance(runtime, dict) else None
    checkpoint_request = checkpoint_request or _load_pending_time_wait_request(
        client, procedure_id, expected_run_id=expected_run_id,
    )
    checkpoint_request = canonical_time_wait_request(checkpoint_request)
    if checkpoint_request is None:
        return {"resumed": False, "status": status, "reason": "Scheduled-continuation checkpoint is missing or malformed"}

    boundary = metadata.get("waiting_for_time")
    parent_task_id = (
        boundary.get("parent_task_id")
        if isinstance(boundary, dict)
        else runtime.get("task_id") if isinstance(runtime, dict) else None
    )
    expected_boundary = {
        "procedure_id": procedure_id,
        "parent_task_id": parent_task_id,
        "request": checkpoint_request,
    }
    if (
        procedure.get("status") not in {status, "RUNNING"}
        or not isinstance(parent_task_id, str)
        or not parent_task_id
        or (boundary is not None and boundary != expected_boundary)
    ):
        return {"resumed": False, "status": status, "reason": "Scheduled-continuation Procedure boundary does not match checkpoint"}

    backend = _optimizer_backend(client)
    parent_task = backend.get_task(parent_task_id)
    if not isinstance(parent_task, dict):
        return {"resumed": False, "status": status, "reason": "Scheduled-continuation parent Task was not found"}
    raw_task_metadata = parent_task.get("metadata")
    task_metadata = _json_object(raw_task_metadata)
    task_updated_at = parent_task.get("updatedAt")
    if (
        parent_task.get("accountId") != account_id
        or parent_task.get("target") not in {f"procedure/{procedure_id}", f"procedure/run/{procedure_id}"}
        or parent_task.get("command") != f"procedure run {procedure_id}"
        or task_metadata.get("procedure_id") != procedure_id
        or not isinstance(task_updated_at, str)
        or not task_updated_at
    ):
        return {"resumed": False, "status": status, "reason": "Scheduled-continuation Task boundary does not match checkpoint"}

    if procedure.get("status") == "RUNNING":
        repaired_metadata = {**metadata, "waiting_for_time": expected_boundary}
        mutation = """
          mutation RepairWaitingTimeProcedure(
            $input: UpdateProcedureInput!
            $condition: ModelProcedureConditionInput
          ) {
            updateProcedure(input: $input, condition: $condition) {
              id status accountId metadata
            }
          }
        """
        try:
            repaired = client.execute(mutation, {
                "input": {
                    "id": procedure_id,
                    "status": status,
                    "metadata": json.dumps(repaired_metadata),
                },
                "condition": {"and": [
                    {"status": {"eq": "RUNNING"}},
                    {"metadata": {"eq": _stored_json_value(raw_procedure_metadata, metadata)}},
                ]},
            }).get("updateProcedure")
        except Exception as exc:
            logger.info(
                "Scheduled continuation Procedure %s was not repaired: %s",
                procedure_id,
                exc,
            )
            return {"resumed": False, "status": status, "reason": "Scheduled continuation Procedure repair was already claimed or is no longer eligible"}
        if not isinstance(repaired, dict) or repaired.get("status") != status:
            return {"resumed": False, "status": status, "reason": "Scheduled continuation Procedure repair was not accepted"}
        procedure = repaired
        raw_procedure_metadata = repaired.get("metadata")
        metadata = _json_object(raw_procedure_metadata)

    task_is_waiting = (
        parent_task.get("status") == status
        and parent_task.get("dispatchStatus") == status
    )
    if not task_is_waiting:
        if (
            parent_task.get("status") != "RUNNING"
            or parent_task.get("dispatchStatus") not in {"DISPATCHING", "DISPATCHED", "LOCAL"}
        ):
            return {"resumed": False, "status": status, "reason": "Scheduled-continuation Task is not in a repairable active state"}
        repaired_task_metadata = {
            **task_metadata,
            "dispatch_policy": "resume_once",
            "waiting_for_time": expected_boundary,
        }
        mutation = """
          mutation RepairWaitingTimeTask(
            $input: UpdateTaskInput!
            $condition: ModelTaskConditionInput
          ) {
            updateTask(input: $input, condition: $condition) {
              id accountId status dispatchStatus target command metadata updatedAt
            }
          }
        """
        try:
            repaired = client.execute(mutation, {
                "input": {
                    "id": parent_task_id,
                    "status": status,
                    "dispatchStatus": status,
                    "workerNodeId": None,
                    "completedAt": None,
                    "metadata": json.dumps(repaired_task_metadata),
                },
                "condition": {"and": [
                    {"status": {"eq": parent_task.get("status")}},
                    {"dispatchStatus": {"eq": parent_task.get("dispatchStatus")}},
                    {"updatedAt": {"eq": task_updated_at}},
                ]},
            }).get("updateTask")
        except Exception as exc:
            logger.info(
                "Scheduled continuation Task %s was not repaired: %s",
                parent_task_id,
                exc,
            )
            return {"resumed": False, "status": status, "reason": "Scheduled continuation Task repair was already claimed or is no longer eligible"}
        if (
            not isinstance(repaired, dict)
            or repaired.get("status") != status
            or repaired.get("dispatchStatus") != status
        ):
            return {"resumed": False, "status": status, "reason": "Scheduled continuation Task repair was not accepted"}
        parent_task = repaired
        raw_task_metadata = repaired.get("metadata")
        task_metadata = _json_object(raw_task_metadata)
        task_updated_at = repaired.get("updatedAt")

    if (
        procedure.get("status") != status
        or _json_object(procedure.get("metadata")).get("waiting_for_time") != expected_boundary
        or parent_task.get("status") != status
        or parent_task.get("dispatchStatus") != status
        or task_metadata.get("dispatch_policy") != "resume_once"
        or task_metadata.get("waiting_for_time") != expected_boundary
        or not isinstance(task_updated_at, str)
        or not task_updated_at
    ):
        return {"resumed": False, "status": status, "reason": "Scheduled-continuation wait boundary is not corroborated"}

    if not time_wait_is_due(checkpoint_request, now=now):
        return {"resumed": False, "status": status, "reason": "Scheduled continuation is not due"}

    mutation = """
        mutation RearmWaitingTimeParent(
            $input: UpdateTaskInput!
            $condition: ModelTaskConditionInput
        ) {
            updateTask(input: $input, condition: $condition) {
                id
                status
                dispatchStatus
            }
        }
    """
    try:
        updated = client.execute(mutation, {
            "input": {
                "id": parent_task_id,
                "status": "PENDING",
                "dispatchStatus": "PENDING",
                "workerNodeId": None,
            },
            "condition": {"and": [
                {"status": {"eq": status}},
                {"dispatchStatus": {"eq": status}},
                {"updatedAt": {"eq": task_updated_at}},
            ]},
        }).get("updateTask")
    except Exception as exc:
        logger.info(
            "Scheduled continuation task %s was not rearmed (duplicate or racing tick): %s",
            parent_task_id,
            exc,
        )
        return {"resumed": False, "status": status, "reason": "Scheduled continuation was already claimed or is no longer eligible"}
    if (
        not isinstance(updated, dict)
        or updated.get("status") != "PENDING"
        or updated.get("dispatchStatus") != "PENDING"
    ):
        return {"resumed": False, "status": status, "reason": "Scheduled continuation was already claimed or is no longer eligible"}
    return {
        "resumed": True,
        "status": "PENDING",
        "message": "Procedure resume scheduled at its due time",
    }


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
                accountId
                metadata
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

    if status == 'WAITING_FOR_CHILDREN':
        return _resume_after_child_completion(client, procedure)

    if status == 'WAITING_FOR_TIME':
        return _resume_after_time_due(client, procedure)

    # A Tactus checkpoint may be durable immediately before the indexed
    # Procedure wait status. Repair only that exact one-sided window.
    if status == 'RUNNING':
        procedure_metadata = _json_object(procedure.get("metadata"))
        runtime = procedure_metadata.get("runtime")
        expected_run_id = runtime.get("tactus_run_id") if isinstance(runtime, dict) else None
        checkpoint_request = _load_pending_external_child_request(
            client, procedure_id, expected_run_id=expected_run_id,
        )
        if checkpoint_request:
            return _resume_after_child_completion(
                client, procedure, checkpoint_request=checkpoint_request,
            )
        checkpoint_request = _load_pending_time_wait_request(
            client, procedure_id, expected_run_id=expected_run_id,
        )
        if checkpoint_request:
            return _resume_after_time_due(
                client, procedure, checkpoint_request=checkpoint_request,
            )

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

    try:
        # Replay through the same local task-tracked path as the initial run so
        # the Procedure, Task, stages, and compact output artifact are finalized
        # consistently after the human boundary.
        import asyncio
        from plexus.cli.shared.experiment_runner import run_procedure_with_task_tracking

        account_id = procedure.get("accountId")
        if not account_id:
            account_id = client._resolve_account_id()
        run_result = asyncio.run(
            run_procedure_with_task_tracking(
                procedure_id=procedure_id,
                client=client,
                account_id=account_id,
            )
        )

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
            - complete: bool - Whether every requested status was exhaustively scanned
            - found: int - Number of waiting procedures found
            - resumed: int - Number successfully resumed
            - resumed_ids: List[str] - IDs of resumed procedures
    """
    # Query both durable suspension states. Child waits are rearmed only when
    # an exact referenced child is terminal; human waits retain their response
    # gate and local task-tracked replay behavior.
    query = """
        query ListWaitingProcedures(
            $status: String!
            $limit: Int
            $nextToken: String
        ) {
            listProcedures(
                filter: {
                    status: {eq: $status}
                }
                limit: $limit
                nextToken: $nextToken
            ) {
                items {
                    id
                    waitingOnMessageId
                }
                nextToken
            }
        }
    """

    procedures: List[Dict[str, Any]] = []
    for waiting_status in (
        "WAITING_FOR_HUMAN",
        "WAITING_FOR_CHILDREN",
        "WAITING_FOR_TIME",
        "RUNNING",
    ):
        next_token: Optional[str] = None
        seen_tokens = set()
        try:
            while True:
                variables: Dict[str, Any] = {
                    "status": waiting_status,
                    "limit": _PROCEDURE_SCAN_PAGE_SIZE,
                }
                if next_token is not None:
                    variables["nextToken"] = next_token

                result = client.execute(query, variables)
                if not isinstance(result, dict):
                    raise RuntimeError("procedure page response is not an object")
                page = result.get("listProcedures")
                if not isinstance(page, dict):
                    raise RuntimeError("procedure page payload is missing")
                items = page.get("items")
                if not isinstance(items, list):
                    raise RuntimeError("procedure page items are missing or malformed")
                if any(
                    not isinstance(item, dict)
                    or not isinstance(item.get("id"), str)
                    or not item.get("id")
                    for item in items
                ):
                    raise RuntimeError("procedure page contains a malformed identity")
                procedures.extend(items)

                raw_next_token = page.get("nextToken")
                if raw_next_token in (None, ""):
                    break
                if not isinstance(raw_next_token, str):
                    raise RuntimeError("procedure page has a malformed pagination token")
                if raw_next_token in seen_tokens:
                    raise RuntimeError("procedure scan returned a repeated pagination token")
                seen_tokens.add(raw_next_token)
                next_token = raw_next_token
        except Exception as exc:
            logger.error(
                "Procedure recovery scan failed closed for status %s: %s",
                waiting_status,
                exc,
            )
            return {
                "complete": False,
                "found": len(procedures),
                "resumed": 0,
                "resumed_ids": [],
                "failure": {
                    "status": waiting_status,
                    "reason": str(exc),
                },
            }

    # A procedure can move between active statuses during a multi-query scan.
    # Preserve first-seen order and never attempt to claim the same parent twice.
    unique_procedures = []
    seen_procedure_ids = set()
    for procedure in procedures:
        procedure_id = procedure["id"]
        if procedure_id in seen_procedure_ids:
            continue
        seen_procedure_ids.add(procedure_id)
        unique_procedures.append(procedure)
    procedures = unique_procedures

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
        'complete': True,
        'found': len(procedures),
        'resumed': resumed_count,
        'resumed_ids': resumed_ids
    }
