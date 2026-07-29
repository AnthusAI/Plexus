"""Thin CLI adapters for the shared optimization decision service."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterable, Mapping, Tuple

import click


OPERATIONS: Tuple[str, ...] = (
    "rank",
    "assess",
    "diagnose",
    "run",
    "review",
    "summary",
)
@click.group(name="optimization")
def optimization() -> None:
    """Rank, assess, diagnose, run, review, and summarize optimizations."""


def _add_operation(name: str) -> Callable[[Callable[..., None]], click.Command]:
    """Register one uniform JSON-in/JSON-out decision command."""

    def decorate(function: Callable[..., None]) -> click.Command:
        command = optimization.command(name=name)(function)
        command = click.option(
            "--input",
            "input_value",
            default="{}",
            show_default=True,
            help="JSON object, @path/to/input.json, or - for standard input.",
        )(command)
        command = click.option(
            "--option",
            "option_values",
            multiple=True,
            metavar="KEY=JSON_VALUE",
            help="Override or add a typed request field.",
        )(command)
        command = click.option(
            "--persist/--no-persist",
            default=False,
            show_default=True,
            help="Persist the returned packet through artifact persistence.",
        )(command)
        return command

    return decorate


def _operation_command(operation: str) -> click.Command:
    @_add_operation(operation)
    def command(input_value: str, option_values: Iterable[str], persist: bool) -> None:
        payload = _load_request_payload(input_value)
        payload.update(_parse_options(option_values))
        # This explicit default is part of the public contract: read commands
        # make no writes unless persistence is requested.
        payload["persist"] = persist
        try:
            result = dispatch_optimization_operation(operation, payload)
        except (RuntimeError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        if persist:
            try:
                _persist_returned_packet(result, payload)
            except (RuntimeError, ValueError) as exc:
                raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(result, indent=2, sort_keys=True, default=str))

    return command


# Decorators execute at import time to make all subcommands discoverable through
# `plexus optimization --help` without importing optimization business logic.
for _operation in OPERATIONS:
    _operation_command(_operation)


def dispatch_optimization_operation(operation: str, payload: Dict[str, Any]) -> Any:
    """Resolve the single shared decision dispatcher lazily."""
    if operation not in OPERATIONS:
        raise ValueError(f"Unsupported optimization operation: {operation}")

    try:
        from plexus.optimization.decision import (
            dispatch_optimization_operation as shared_dispatcher,
        )
    except ImportError as exc:
        raise RuntimeError(
            "The shared optimization decision dispatcher is unavailable."
        ) from exc

    if operation == "run":
        limits = _validate_run_limits(payload)
        dispatch_payload, freshness_rejections = _prepare_live_run_request(
            payload, limits_valid=bool(limits.get("valid"))
        )
        result = shared_dispatcher(operation, dispatch_payload)
        result = _merge_freshness_rejections(result, freshness_rejections)
        return _dispatch_approved_optimizer_targets(result)
    if operation == "review":
        procedure_id = str(payload.get("procedure_id") or "")
        # A public review cannot accept caller-supplied `terminal`, safety, or
        # improvement booleans.  Those values have to come from the indexed
        # optimizer manifest plus its terminal evaluation evidence.
        payload = {
            **payload,
            "evidence": (
                _load_indexed_optimizer_review_evidence(procedure_id)
                if procedure_id
                else {
                    "terminal": False,
                    "incomplete": True,
                    "error": "procedure_id is required for indexed optimizer review",
                }
            ),
        }
    return shared_dispatcher(operation, payload)


def _dispatch_approved_optimizer_targets(
    validation_result: Any,
) -> Dict[str, Any]:
    """Launch only the targets accepted by the shared stale/approval gate."""
    if not isinstance(validation_result, dict):
        raise RuntimeError("Optimization run validation returned a non-object result.")

    accepted_targets = validation_result.get("accepted_targets") or []
    if not accepted_targets:
        return {**validation_result, "dispatches": []}

    run_limits = validation_result.get("run_limits")
    if not isinstance(run_limits, Mapping) or run_limits.get("valid") is not True:
        raise RuntimeError("Optimization run was accepted without valid core run limits.")
    limits = dict(run_limits.get("limits") or {})
    launch_arguments = [
        {
            "scorecard": _required_target_value(target, "scorecard_id"),
            "score": _required_target_value(target, "score_id"),
            **limits,
        }
        for target in accepted_targets
    ]
    results = _launch_with_bounded_concurrency(
        launch_arguments,
        max_concurrency=limits["max_concurrency"],
    )
    dispatches = [
        {
            "target": {
                "scorecard_id": arguments["scorecard"],
                "score_id": arguments["score"],
            },
            **result,
        }
        for arguments, result in zip(launch_arguments, results)
    ]
    failed_count = sum(row["status"] == "failed" for row in dispatches)
    return {
        **validation_result,
        "dispatches": dispatches,
        "dispatch_coverage": {
            "target_count": len(dispatches),
            "dispatched_count": len(dispatches) - failed_count,
            "failed_count": failed_count,
            "complete": failed_count == 0,
        },
    }


def _validate_run_limits(request: Mapping[str, Any]) -> Dict[str, Any]:
    """Use the one exported policy validator; the CLI owns no numeric policy."""
    from plexus.optimization.decision import validate_run_limits

    return validate_run_limits(request)


def _prepare_live_run_request(
    request: Mapping[str, Any], *, limits_valid: bool
) -> tuple[Dict[str, Any], list[dict[str, Any]]]:
    """Replace caller freshness inputs with a target-scoped live recheck."""
    prepared = dict(request)
    if request.get("approved") is not True or not limits_valid:
        return prepared, []

    _fingerprints, evidence_by_target, failures = _refresh_live_target_freshness(
        request
    )
    rejected = list(failures)
    failed_keys = {
        (
            str(item.get("target", {}).get("scorecard_id") or ""),
            str(item.get("target", {}).get("score_id") or ""),
        )
        for item in failures
        if isinstance(item.get("target"), Mapping)
    }
    fresh_targets: list[dict[str, Any]] = []
    current_fingerprints: dict[str, str] = {}
    for source in request.get("targets") or []:
        if not isinstance(source, Mapping):
            continue
        target = dict(source)
        key = (str(target.get("scorecard_id") or ""), str(target.get("score_id") or ""))
        current = evidence_by_target.get(key)
        if key in failed_keys or current is None:
            continue
        if (
            target.get("champion_version") not in (None, current["champion_version"])
            or target.get("feedback_watermark")
            not in (None, current["feedback_watermark"])
        ):
            # Preserve the target for the shared validator, which can then
            # report `stale_assessment` rather than treating the batch as
            # empty.  This marker is never caller-controlled.
            fresh_targets.append(target)
            current_fingerprints[f"{key[0]}:{key[1]}"] = "live-evidence-changed"
            continue
        fresh_targets.append(target)
        fingerprint = _recomputed_assessment_fingerprint(target)
        if fingerprint:
            current_fingerprints[f"{key[0]}:{key[1]}"] = fingerprint

    # Never trust current_fingerprints passed in the request.  The shared core
    # gate sees only fingerprints recomputed from the embedded assessment
    # packet after live champion/watermark evidence is confirmed unchanged.
    prepared["targets"] = fresh_targets
    prepared["current_fingerprints"] = current_fingerprints
    return prepared, rejected


def _recomputed_assessment_fingerprint(target: Mapping[str, Any]) -> str | None:
    """Return the canonical embedded-assessment fingerprint, if present."""
    assessment = target.get("assessment")
    if not isinstance(assessment, Mapping):
        return None
    evidence = assessment.get("evidence")
    if not isinstance(evidence, Mapping):
        return None
    from plexus.optimization.decision import evidence_fingerprint

    return evidence_fingerprint({
        "account_id": assessment.get("account_id"),
        "scope": assessment.get("scope") or {},
        "window": assessment.get("window") or {},
        "policy_version": assessment.get("policy_version"),
        "champion_version": assessment.get("champion_version"),
        "feedback_watermark": assessment.get("feedback_watermark"),
        "evidence": dict(evidence),
    })


def _merge_freshness_rejections(
    result: Any, freshness_rejections: Iterable[Mapping[str, Any]]
) -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise RuntimeError("Optimization run validation returned a non-object result.")
    extra = [dict(item) for item in freshness_rejections]
    if not extra:
        return result
    rejected = [*extra, *list(result.get("rejected") or [])]
    blockers = [*list(result.get("blockers") or []), *(str(item.get("reason")) for item in extra)]
    evidence = dict(result.get("evidence") or {})
    evidence["rejected"] = rejected
    evidence["accepted_targets"] = list(result.get("accepted_targets") or [])
    return {
        **result,
        "accepted": False,
        "rejected": rejected,
        "blockers": list(dict.fromkeys(blockers)),
        "primary_next_action": "resolve_batch_rejections",
        "evidence": evidence,
    }


def _refresh_live_target_freshness(
    request: Mapping[str, Any],
) -> tuple[dict[str, str], dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """Read live evidence with the same target-scoped semantics as runtime."""
    targets = [dict(target) for target in request.get("targets") or [] if isinstance(target, Mapping)]
    account_id = request.get("account_id")
    if not isinstance(account_id, str) or not account_id.strip():
        return {}, {}, [
            {
                "target": target,
                "reason": "freshness_check_failed",
                "error": "account_id is required for live optimization freshness",
            }
            for target in targets
        ]
    from plexus.cli.shared.client_utils import create_client
    from plexus.optimization.orchestration import refresh_target_freshness

    client = create_client()
    if client is None:
        return {}, {}, [
            {
                "target": target,
                "reason": "freshness_check_failed",
                "error": "could not create dashboard client",
            }
            for target in targets
        ]
    return refresh_target_freshness(
        targets,
        read_score_info=lambda scorecard_id, score_id: _read_live_score_info(
            client, scorecard_id, score_id
        ),
        read_feedback_latest=lambda scorecard_id, score_id: _read_live_feedback_watermark(
            client, account_id, scorecard_id, score_id
        ),
    )


def _read_live_score_info(client: Any, scorecard_id: str, score_id: str) -> Mapping[str, Any]:
    del scorecard_id  # score IDs are opaque and globally resolvable by the API.
    result = client.execute(
        """
        query OptimizationLiveScore($scoreId: ID!) {
            getScore(id: $scoreId) {
                id
                championVersionId
                updatedAt
                versions(sortDirection: DESC, limit: 1) {
                    items { id createdAt }
                }
            }
        }
        """,
        {"scoreId": score_id},
    )
    score = result.get("getScore") if isinstance(result, Mapping) else None
    if not isinstance(score, Mapping):
        raise RuntimeError("score read returned no score")
    return score


def _read_live_feedback_watermark(
    client: Any, account_id: str, scorecard_id: str, score_id: str
) -> Mapping[str, Any]:
    query = """
        query OptimizationLatestFeedback(
            $accountId: String!,
            $condition: ModelFeedbackItemByAccountScorecardScoreEditedAtCompositeKeyConditionInput,
            $nextToken: String
        ) {
            listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
                accountId: $accountId,
                scorecardIdScoreIdEditedAt: $condition,
                limit: 1000,
                nextToken: $nextToken,
                sortDirection: DESC
            ) { items { editedAt updatedAt } nextToken }
        }
        """
    variables = {
        "accountId": account_id,
        "condition": {
            "between": [
                {"scorecardId": scorecard_id, "scoreId": score_id, "editedAt": "1970-01-01T00:00:00Z"},
                {"scorecardId": scorecard_id, "scoreId": score_id, "editedAt": "9999-12-31T23:59:59Z"},
            ]
        },
        "nextToken": None,
    }
    latest: str | None = None
    while True:
        result = client.execute(query, variables)
        records = (
            result.get("listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt", {})
            if isinstance(result, Mapping)
            else {}
        )
        if not isinstance(records, Mapping):
            raise RuntimeError("feedback watermark read returned invalid data")
        for item in records.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            watermark = item.get("updatedAt") or item.get("editedAt")
            if watermark and (latest is None or str(watermark) > latest):
                latest = str(watermark)
        next_token = records.get("nextToken")
        if not next_token:
            break
        variables["nextToken"] = next_token
    if latest is None:
        raise RuntimeError("feedback watermark read returned no feedback")
    return {"latest_feedback_updated_at": latest}


def _load_indexed_optimizer_review_evidence(procedure_id: str) -> Dict[str, Any]:
    """Load existing indexed optimizer output, never reconstructing a manifest."""
    try:
        from plexus.cli.shared.client_utils import create_client

        client = create_client()
        if client is None:
            raise RuntimeError("could not create dashboard client")
        indexed = _create_optimizer_results_service(client).summarize_optimizer_procedure(
            procedure_id
        )
        return _normalize_indexed_optimizer_review(
            indexed,
            procedure_id,
            read_evaluation=_read_evaluation_for_review,
        )
    except Exception as exc:  # noqa: BLE001 - review must fail closed on missing artifacts
        return {
            "terminal": False,
            "incomplete": True,
            "artifacts_complete": False,
            "rca_complete": False,
            "class_specific_metrics": False,
            "prediction_collapse": True,
            "measurable_safe_improvement": False,
            "procedure_id": procedure_id,
            "review_load_error": str(exc),
        }


def _create_optimizer_results_service(client: Any) -> Any:
    """Small injectable seam around the existing indexed-results service."""
    from plexus.cli.shared.optimizer_results import OptimizerResultsService

    return OptimizerResultsService(client)


def _normalize_indexed_optimizer_review(
    indexed: Mapping[str, Any],
    procedure_id: str,
    *,
    read_evaluation: Callable[[str], Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Use the shared conservative review adapter; never infer missing proof."""
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    if read_evaluation is None:
        read_evaluation = lambda _evaluation_id: {}
    return build_indexed_optimizer_review_evidence(
        indexed,
        procedure_id=procedure_id,
        read_evaluation=read_evaluation,
    )


def _read_evaluation_for_review(evaluation_id: str) -> Mapping[str, Any]:
    from plexus.Evaluation import Evaluation

    return Evaluation.get_evaluation_info(evaluation_id)


def _required_target_value(target: Any, key: str) -> str:
    if not isinstance(target, Mapping):
        raise RuntimeError("Accepted optimization target must be an object.")
    value = target.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Accepted optimization target is missing {key}.")
    return value


def _launch_with_bounded_concurrency(
    launch_arguments: list[Dict[str, Any]], *, max_concurrency: int
) -> list[Dict[str, Any]]:
    """Dispatch every accepted target, never cancelling a legitimate launch."""
    def launch(arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {
                "status": "dispatched",
                "result": _launch_optimizer_procedure(arguments),
            }
        except Exception as exc:  # noqa: BLE001 - preserve per-target coverage
            return {"status": "failed", "error": str(exc)}

    if max_concurrency == 1 or len(launch_arguments) == 1:
        return [launch(arguments) for arguments in launch_arguments]
    with ThreadPoolExecutor(max_workers=min(max_concurrency, len(launch_arguments))) as executor:
        # executor.map preserves target order and the context manager waits for
        # already started launches before propagating a dispatch failure.
        return list(executor.map(launch, launch_arguments))


def _launch_optimizer_procedure(arguments: Dict[str, Any]) -> Any:
    """Use the existing asynchronous optimizer entry point; do not emulate it."""
    try:
        from MCP.tools.tactus_runtime.execute import _default_procedure_optimize
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "Optimization launch is unavailable: the existing procedure optimizer entry point could not be loaded."
        ) from exc
    return _default_procedure_optimize(arguments)


def _load_request_payload(value: str) -> Dict[str, Any]:
    source = value
    if value == "-":
        source = sys.stdin.read()
    elif value.startswith("@"):
        path = value[1:]
        try:
            with open(path, encoding="utf-8") as input_file:
                source = input_file.read()
        except OSError as exc:
            raise click.BadParameter(f"Could not read input file '{path}': {exc}") from exc
    try:
        payload = json.loads(source)
    except json.JSONDecodeError as exc:
        raise click.BadParameter(f"Invalid JSON input: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise click.BadParameter("Input must be a JSON object.")
    return payload


def _parse_options(values: Iterable[str]) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise click.BadParameter("Options must use KEY=JSON_VALUE.", param_hint="--option")
        key, raw_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise click.BadParameter("Option key may not be empty.", param_hint="--option")
        try:
            parsed[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed[key] = raw_value
    return parsed


def _persist_returned_packet(result: Any, request: Dict[str, Any]) -> None:
    """Persist the exact returned packet only when the caller explicitly asks."""
    if not isinstance(result, dict):
        raise RuntimeError("Optimization persistence requires a JSON-object decision packet.")
    account_id = request.get("account_id") or result.get("account_id")
    if not isinstance(account_id, str) or not account_id.strip():
        raise click.ClickException(
            "--persist requires account_id in the request or returned decision packet."
        )

    # Lazy imports guarantee that ordinary CLI reads do not initialize a
    # dashboard client or the persistence dependency stack.
    from plexus.cli.shared.client_utils import create_client
    from plexus.optimization.persistence import persist_decision_packet

    persist_decision_packet(
        result,
        client=create_client(),
        account_id=account_id,
        persist=True,
    )
