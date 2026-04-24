"""
Continuation service for procedure continuation and branching.

Provides high-level helpers used by both the CLI commands and MCP tools:

  prepare_continuation(client, procedure_id, additional_cycles, hint)
      Updates YAML params and clears checkpoints so the optimizer resumes
      from where it left off when re-dispatched.

  prepare_branch(client, source_id, cycle, additional_cycles, hint, name)
      Creates a new Procedure record with cloned state truncated to cycle N,
      ready to run from cycle N+1.

Neither function dispatches the procedure run — callers are responsible for
invoking ProcedureService.run_experiment or run_experiment_with_task_tracking
after calling these functions.
"""

import json
import logging
import yaml
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_LOAD_PROCEDURE_QUERY = """
    query GetProcedure($id: ID!) {
        getProcedure(id: $id) {
            id
            code
            accountId
            name
            scorecardId
            scoreId
        }
    }
"""

_UPDATE_PROCEDURE_CODE_MUTATION = """
    mutation UpdateProcedureCode($id: ID!, $code: String!) {
        updateProcedure(input: {
            id: $id
            code: $code
        }) {
            id
        }
    }
"""

_CREATE_PROCEDURE_MUTATION = """
    mutation CreateProcedure($input: CreateProcedureInput!) {
        createProcedure(input: $input) {
            id
            accountId
        }
    }
"""


def _load_procedure(client, procedure_id: str) -> Dict[str, Any]:
    """Load procedure record. Raises ValueError if not found."""
    result = client.execute(_LOAD_PROCEDURE_QUERY, {'id': procedure_id})
    procedure = result.get('getProcedure')
    if not procedure:
        raise ValueError(f"Procedure {procedure_id} not found")
    return procedure


def _count_completed_cycles(client, procedure_id: str) -> int:
    """Return the number of completed optimizer cycles stored in State."""
    from plexus.cli.procedure.tactus_adapters.storage import PlexusStorageAdapter
    storage = PlexusStorageAdapter(client, procedure_id)
    iterations = storage.state_get(procedure_id, 'iterations') or []
    return len(iterations) if isinstance(iterations, (list, tuple)) else 0


def _parse_json_object(value: Any) -> Dict[str, Any]:
    """Best-effort parse of JSON-like object payloads."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _update_yaml_params(code: str, max_iterations: int, hint: Optional[str]) -> str:
    """Parse YAML, update params, return serialised YAML string."""
    try:
        parsed = yaml.safe_load(code) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Could not parse procedure YAML: {exc}") from exc

    params = parsed.get('params') or {}

    # Update max_iterations
    if 'max_iterations' in params:
        params['max_iterations']['value'] = max_iterations
    else:
        params['max_iterations'] = {'type': 'int', 'required': False, 'value': max_iterations}

    # Update hint
    if hint is not None and hint.strip():
        if 'hint' in params:
            params['hint']['value'] = hint.strip()
        else:
            params['hint'] = {'type': 'string', 'required': False, 'value': hint.strip()}
    elif 'hint' in params:
        # Clear any previous hint so it doesn't bleed across runs
        params['hint'].pop('value', None)

    parsed['params'] = params
    return yaml.dump(parsed, default_flow_style=False, allow_unicode=True, width=10000)


def build_continuation_context(
    client,
    procedure_id: str,
    *,
    max_iterations: int,
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Reconstruct optimizer context for continue/branch redispatches.

    Continuation runs do not get the original CLI `context` automatically. Recover it
    from the best available sources, in increasing confidence order:
      1) procedure YAML resolved params
      2) existing task metadata.run_parameters
      3) recent baseline evaluation parameters
      4) preserved optimizer State / procedure identifiers
    """
    from plexus.cli.procedure.tactus_adapters.storage import PlexusStorageAdapter
    from plexus.cli.shared.experiment_runner import (
        _extract_run_parameters_from_procedure_yaml,
        _find_existing_task_for_procedure,
    )
    from plexus.dashboard.api.models.task import Task

    procedure = _load_procedure(client, procedure_id)
    context: Dict[str, Any] = _extract_run_parameters_from_procedure_yaml(procedure.get("code"))

    task_id = _find_existing_task_for_procedure(procedure_id, procedure.get("accountId"), client)
    if task_id:
        task = Task.get_by_id(task_id, client)
        if task:
            task_metadata = _parse_json_object(getattr(task, "metadata", None))
            run_parameters = task_metadata.get("run_parameters")
            if isinstance(run_parameters, dict):
                context.update(run_parameters)

    storage = PlexusStorageAdapter(client, procedure_id)
    recent_baseline_id = storage.state_get(procedure_id, "recent_baseline_id")
    if recent_baseline_id:
        evaluation_result = client.execute(
            """
            query GetEvaluation($id: ID!) {
                getEvaluation(id: $id) {
                    id
                    parameters
                }
            }
            """,
            {"id": recent_baseline_id},
        )
        evaluation = (evaluation_result or {}).get("getEvaluation") or {}
        evaluation_params = _parse_json_object(evaluation.get("parameters"))
        if "days" in evaluation_params:
            context["days"] = evaluation_params.get("days")
        if "requested_max_items" in evaluation_params:
            context["max_samples"] = evaluation_params.get("requested_max_items")
        elif "max_items" in evaluation_params and "max_samples" not in context:
            context["max_samples"] = evaluation_params.get("max_items")
        if "sampling_mode" in evaluation_params:
            context["sampling_mode"] = evaluation_params.get("sampling_mode")

    scorecard_id = storage.state_get(procedure_id, "scorecard_id") or procedure.get("scorecardId")
    score_id = storage.state_get(procedure_id, "score_id") or procedure.get("scoreId")
    scorecard_name = storage.state_get(procedure_id, "scorecard_name")
    score_name = storage.state_get(procedure_id, "score_name")

    if scorecard_id:
        context["scorecard"] = scorecard_id
    elif scorecard_name and "scorecard" not in context:
        context["scorecard"] = scorecard_name

    if score_id:
        context["score"] = score_id
    elif score_name and "score" not in context:
        context["score"] = score_name

    context["max_iterations"] = max_iterations
    if hint is not None and hint.strip():
        context["hint"] = hint.strip()

    return context


def prepare_continuation(
    client,
    procedure_id: str,
    additional_cycles: int = 3,
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prepare a completed procedure for continuation.

    Steps:
    1. Load current YAML from procedure.code
    2. Count completed cycles from S3 State
    3. Update params.max_iterations.value = completed + additional_cycles
    4. Optionally update params.hint.value
    5. Save updated YAML back to procedure.code via GraphQL
    6. Clear checkpoints only (preserve State) via reset_checkpoints_only

    Returns dict with:
        procedure_id, completed_cycles, additional_cycles, new_max_iterations,
        hint_applied (bool)
    """
    from plexus.cli.procedure.reset_service import reset_checkpoints_only

    procedure = _load_procedure(client, procedure_id)
    code = procedure.get('code') or ''
    if not code:
        raise ValueError(f"Procedure {procedure_id} has no YAML code to update")

    completed_cycles = _count_completed_cycles(client, procedure_id)
    new_max_iterations = completed_cycles + additional_cycles

    logger.info(
        "Preparing continuation for %s: %d completed cycles + %d additional = %d total",
        procedure_id, completed_cycles, additional_cycles, new_max_iterations,
    )

    updated_code = _update_yaml_params(code, new_max_iterations, hint)

    client.execute(_UPDATE_PROCEDURE_CODE_MUTATION, {
        'id': procedure_id,
        'code': updated_code,
    })
    logger.info("Saved updated YAML to procedure %s", procedure_id)

    reset_checkpoints_only(client, procedure_id)
    logger.info("Checkpoints cleared for procedure %s (State preserved)", procedure_id)

    return {
        'procedure_id': procedure_id,
        'completed_cycles': completed_cycles,
        'additional_cycles': additional_cycles,
        'new_max_iterations': new_max_iterations,
        'hint_applied': bool(hint and hint.strip()),
    }


def prepare_branch(
    client,
    source_id: str,
    cycle: int,
    additional_cycles: int = 3,
    hint: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new procedure branched from source_id after cycle N.

    Steps:
    1. Load source procedure YAML + accountId
    2. Update YAML params: max_iterations = cycle + additional_cycles, hint
    3. Create new Procedure record via GraphQL
    4. Clone State from source to new procedure, truncated to cycle N
       (new procedure gets empty checkpoints → optimizer starts fresh from cycle N+1)

    Returns dict with:
        source_id, target_id, cycle, additional_cycles, new_max_iterations,
        target_name, hint_applied (bool)
    """
    from plexus.cli.procedure.reset_service import clone_state_for_branch

    source = _load_procedure(client, source_id)
    code = source.get('code') or ''
    account_id = source.get('accountId')
    if not account_id:
        raise ValueError(f"Source procedure {source_id} has no accountId")

    new_max_iterations = cycle + additional_cycles
    updated_code = _update_yaml_params(code, new_max_iterations, hint)

    branch_name = name or (
        f"{source.get('name') or 'Procedure'} (branch from cycle {cycle})"
    )

    # Create new Procedure record
    create_vars: Dict[str, Any] = {
        'accountId': account_id,
        'name': branch_name,
        'code': updated_code,
        'featured': False,
    }
    if source.get('scorecardId'):
        create_vars['scorecardId'] = source['scorecardId']
    if source.get('scoreId'):
        create_vars['scoreId'] = source['scoreId']

    create_result = client.execute(_CREATE_PROCEDURE_MUTATION, {'input': create_vars})
    new_procedure = create_result.get('createProcedure')
    if not new_procedure:
        raise ValueError("Failed to create branch procedure record")
    target_id = new_procedure['id']

    logger.info("Created branch procedure %s from %s (cycle %d)", target_id, source_id, cycle)

    # Clone state truncated to cycle N
    clone_result = clone_state_for_branch(client, source_id, target_id, cycle)
    logger.info(
        "Cloned %d iterations from %s to %s",
        clone_result['iterations_copied'], source_id, target_id,
    )

    return {
        'source_id': source_id,
        'target_id': target_id,
        'cycle': cycle,
        'additional_cycles': additional_cycles,
        'new_max_iterations': new_max_iterations,
        'target_name': branch_name,
        'hint_applied': bool(hint and hint.strip()),
    }
