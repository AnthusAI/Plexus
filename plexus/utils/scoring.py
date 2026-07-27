import asyncio
import logging
import traceback
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING
from plexus.utils.dependency_snapshots import (
    fetch_persisted_dependency_snapshot,
    get_dependency_names,
    get_target_dependencies,
    merge_snapshot_into_trace,
    score_version_id,
    unwrap_result_entry,
)
from plexus.utils.score_result_timestamps import extract_score_result_timestamps

try:
    import boto3
except ModuleNotFoundError:
    boto3 = None

try:
    from plexus.dashboard.api.models.scorecard import Scorecard as ScorecardModel
    from plexus.dashboard.api.models.score import Score as ScoreModel
    from plexus.dashboard.api.models.score_result import ScoreResult
except Exception:
    ScorecardModel = None
    ScoreModel = None
    ScoreResult = None

try:
    from plexus.utils.score_result_s3_utils import upload_score_result_log_file, upload_score_result_trace_file
except Exception:
    upload_score_result_log_file = None
    upload_score_result_trace_file = None

if TYPE_CHECKING:
    from plexus.dashboard.api.client import PlexusDashboardClient
# Import Item model for upsert functionality
try:
    from plexus.dashboard.api.models.item import Item
    PLEXUS_ITEM_AVAILABLE = True
except ImportError:
    PLEXUS_ITEM_AVAILABLE = False
DEPENDENCY_UNMET_MESSAGE = "Question is not applicable due to unmet dependency conditions"


@dataclass
class SingleScoreExecutionOutcome:
    """Result envelope for single-score execution with dependency handling."""

    result: Optional[Any]
    dependency_unmet: bool
    score_results: Dict[str, Any]
    dependency_snapshot: Optional[Any] = None
    current_dependency_snapshot: Optional[Any] = None
    used_persisted_dependencies: bool = False

async def get_plexus_client():
    """Get the Plexus Dashboard client for API operations."""
    from plexus.dashboard.api.client import PlexusDashboardClient
    return PlexusDashboardClient()

# Send message to standard scoring request queue
async def send_message_to_standard_scoring_request_queue(scoring_job_id: str):
    """Send message to AWS SQS queue with scoring_job_id"""
    try:
        if boto3 is None:
            raise RuntimeError("boto3 is required for SQS operations")
        client = boto3.client('sqs')
        await asyncio.to_thread(client.send_message,
            QueueUrl=os.getenv('PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL'),
            MessageBody=json.dumps({'scoring_job_id': scoring_job_id})
        )
    except Exception as e:
        logging.error(f"Failed to send message to scoring request queue: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        raise

def sanitize_metadata_for_graphql(metadata: dict) -> dict:
    """
    Sanitize metadata for GraphQL compatibility.

    Handles various data types to ensure the metadata can be safely stored in GraphQL/DynamoDB:
    - Removes problematic characters (null bytes, etc.)
    - Converts complex objects to JSON strings
    - Handles serialization errors gracefully
    
    Note: Does NOT truncate data - all metadata is preserved in full.

    Args:
        metadata: Dictionary of metadata to sanitize

    Returns:
        Sanitized metadata dictionary safe for GraphQL operations
    """
    sanitized_metadata = {}
    if metadata:
        for key, meta_value in metadata.items():
            try:
                if meta_value is None:
                    sanitized_metadata[key] = None
                elif isinstance(meta_value, bool):
                    sanitized_metadata[key] = meta_value
                elif isinstance(meta_value, (int, float)):
                    sanitized_metadata[key] = meta_value
                elif isinstance(meta_value, str):
                    # Remove problematic characters but preserve the full string
                    cleaned_str = meta_value.replace('\x00', '')
                    sanitized_metadata[key] = cleaned_str
                elif isinstance(meta_value, (dict, list)):
                    # Convert complex objects to JSON strings (preserves all data)
                    json_str = json.dumps(meta_value, default=str)
                    sanitized_metadata[key] = json_str
                else:
                    # Convert other types to string
                    str_value = str(meta_value)
                    sanitized_metadata[key] = str_value
            except Exception as e:
                logging.warning(f"Failed to sanitize metadata key '{key}': {e}")
                # Store a safe placeholder instead of skipping
                sanitized_metadata[key] = f"<serialization_error: {type(meta_value).__name__}>"

    return sanitized_metadata

async def check_if_score_is_disabled(scorecard_external_id: str, score_external_id: str, account_id: str) -> bool:
    """
    Check if a score is currently disabled by querying the API.
    
    Args:
        scorecard_external_id: The external ID of the scorecard
        score_external_id: The external ID of the score
        account_id: The DynamoDB ID of the account
        
    Returns:
        bool: True if the score is disabled, False otherwise
    """
    try:
        if not account_id:
            logging.error("No account ID provided. Cannot check if score is disabled.")
            return False
        
        client = await get_plexus_client()
        
        # Resolve scorecard ID
        scorecard_dynamo_id = await resolve_scorecard_id(scorecard_external_id, account_id, client)
        if not scorecard_dynamo_id:
            logging.warning(f"Could not resolve scorecard {scorecard_external_id} - assuming score not disabled")
            return False
        
        # Resolve score ID and get its disabled status
        resolved_score_info = await resolve_score_id(score_external_id, scorecard_dynamo_id, client)
        if not resolved_score_info:
            logging.warning(f"Could not resolve score {score_external_id} - assuming not disabled")
            return False
            
        score_dynamo_id = resolved_score_info['id']
        
        # Get the score using SDK method to check its disabled status
        score = await asyncio.to_thread(ScoreModel.get_by_id, score_dynamo_id, client)
        
        if score:
            is_disabled = getattr(score, 'isDisabled', False)
            logging.info(f"Score {score_external_id} (ID: {score_dynamo_id}) disabled status: {is_disabled}")
            return is_disabled
        else:
            logging.warning(f"Could not fetch score data for ID: {score_dynamo_id}")
            return False
            
    except Exception as e:
        logging.error(f"Error checking if score is disabled: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        # If there's an error, assume not disabled (fail open)
        return False


async def create_scorecard_instance_for_single_score(scorecard_identifier: str, score_identifier: str) -> "Optional[ScorecardModel]":
    """Create a scorecard instance optimized for a single score request."""
    try:
        logging.info(f"Creating targeted scorecard instance for scorecard: {scorecard_identifier}, score: {score_identifier}")
        
        # Import the individual functions we need for targeted loading
        from plexus.cli.shared.direct_memoized_resolvers import direct_memoized_resolve_scorecard_identifier
        from plexus.cli.shared.fetch_scorecard_structure import fetch_scorecard_structure
        from plexus.cli.shared.identify_target_scores import identify_target_scores
        from plexus.cli.shared.iterative_config_fetching import iteratively_fetch_configurations
        from plexus.Scorecard import Scorecard
        
        # Step 1: Get API client and resolve scorecard identifier
        from plexus.dashboard.api.client import PlexusDashboardClient
        client = PlexusDashboardClient()
        
        scorecard_id = await asyncio.to_thread(direct_memoized_resolve_scorecard_identifier, client, scorecard_identifier)
        if not scorecard_id:
            logging.error(f"Could not resolve scorecard identifier: {scorecard_identifier}")
            return None
            
        logging.info(f"Resolved scorecard ID: {scorecard_id}")
        
        # Step 2: Fetch minimal scorecard structure (just metadata, not full configs)
        scorecard_structure = await asyncio.to_thread(fetch_scorecard_structure, client, scorecard_id)
        if not scorecard_structure:
            logging.error(f"Could not fetch scorecard structure for ID: {scorecard_id}")
            return None
            
        # Step 3: Find the specific target score by its identifier
        # Convert the score identifier to a list for the function
        target_scores = await asyncio.to_thread(
            identify_target_scores, 
            scorecard_structure, 
            [score_identifier]  # Only the one score we want
        )
        
        if not target_scores:
            logging.error(f"Could not find score {score_identifier} in scorecard {scorecard_identifier}")
            return None
            
        logging.info(f"Identified target score: {target_scores[0]}")
        
        # Step 4: Fetch only the required configurations (target + dependencies)
        # This will do just-in-time dependency resolution
        scorecard_configs = await asyncio.to_thread(
            iteratively_fetch_configurations,
            client,
            scorecard_structure,
            target_scores,
            use_cache=False  # Always fresh for API requests
        )
        
        if not scorecard_configs:
            logging.error(f"Could not fetch configurations for score {score_identifier}")
            return None
            
        logging.info(f"Fetched {len(scorecard_configs)} score configurations (target + dependencies)")
        
        # Step 5: Create scorecard instance with only the required scores
        # Parse string configurations into dictionaries (same as in evaluations.py)
        parsed_configs = []
        from ruamel.yaml import YAML
        yaml_parser = YAML(typ='safe')
        
        for score_id, config in scorecard_configs.items():
            try:
                # If config is a string, parse it as YAML
                if isinstance(config, str):
                    parsed_config = yaml_parser.load(config)
                    # Add the score ID as an identifier if not present
                    if 'id' not in parsed_config:
                        parsed_config['id'] = score_id
                    parsed_configs.append(parsed_config)
                elif isinstance(config, dict):
                    # If already a dict, add as is
                    if 'id' not in config:
                        config['id'] = score_id
                    parsed_configs.append(config)
                else:
                    logging.warning(f"Skipping config with unexpected type: {type(config)}")
            except Exception as parse_err:
                logging.error(f"Failed to parse configuration for score {score_id}: {str(parse_err)}")
        
        scorecard_instance = await asyncio.to_thread(
            Scorecard.create_instance_from_api_data,
            scorecard_id,
            scorecard_structure, 
            parsed_configs
        )
        
        if scorecard_instance:
            logging.info(f"Successfully created targeted scorecard instance with {len(scorecard_configs)} scores")
            return scorecard_instance
        else:
            logging.error("Failed to create scorecard instance from API data")
            return None
            
    except Exception as e:
        logging.error(f"Error creating targeted scorecard instance: {str(e)}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None


def _unwrap_score_result_entry(entry: Any) -> Optional[Any]:
    """Normalize score entries so callers always handle a single result object."""
    return unwrap_result_entry(entry)


def _dependency_conditions_met_from_results(
    *,
    scorecard_instance: Any,
    target_score_id: str,
    target_score_name: str,
    dependency_configs: list[Dict[str, Any]],
    dependency_results: list[Any],
) -> bool:
    """Reuse Scorecard dependency-condition logic before direct persisted scoring."""

    if not hasattr(scorecard_instance, "build_dependency_graph") or not hasattr(
        scorecard_instance,
        "check_dependency_conditions",
    ):
        return True

    dependency_names = [
        dependency_config.get("name")
        for dependency_config in dependency_configs
        if dependency_config.get("name")
    ]
    try:
        dependency_graph, name_to_id = scorecard_instance.build_dependency_graph(
            [target_score_name, *dependency_names]
        )
        graph_target_id = str(target_score_id)
        if graph_target_id not in dependency_graph:
            graph_target_id = str(name_to_id.get(target_score_name, graph_target_id))

        results_by_score_id = {}
        for dependency_config, dependency_result in zip(dependency_configs, dependency_results):
            dependency_id = str(
                dependency_config.get("id")
                or name_to_id.get(dependency_config.get("name"))
                or ""
            )
            if dependency_id:
                results_by_score_id[dependency_id] = dependency_result

        return scorecard_instance.check_dependency_conditions(
            graph_target_id,
            dependency_graph,
            results_by_score_id,
        )
    except Exception:
        logging.warning(
            "Could not evaluate dependency conditions for persisted dependency path on '%s'; "
            "falling back to direct scoring",
            target_score_name,
            exc_info=True,
        )
        return True


def _result_metadata(result: Any) -> Dict[str, Any]:
    metadata = getattr(result, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _trace_from_result_metadata(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    trace = metadata.get("trace")
    if isinstance(trace, dict):
        return trace

    nested_metadata = metadata.get("metadata")
    if isinstance(nested_metadata, dict) and isinstance(nested_metadata.get("trace"), dict):
        return nested_metadata["trace"]

    return None


def _score_registry_properties(scorecard_instance: Any, score_name: str) -> Dict[str, Any]:
    registry = getattr(scorecard_instance, "score_registry", None)
    if registry is None:
        return {}
    try:
        return dict(registry.get_properties(score_name) or {})
    except Exception:
        logging.debug("Could not read score registry properties for %s", score_name, exc_info=True)
        return {}


async def _persist_jit_dependency_result(
    *,
    scorecard_instance: Any,
    result: Any,
    dependency_config: Dict[str, Any],
    client: Any,
    item_id: str,
    account_id: str,
    scorecard_id: str,
    scoring_job_id: str,
    external_id: str,
    requested_score_id: str,
    requested_score_name: str,
) -> str:
    value = str(result.value) if getattr(result, "value", None) is not None else None
    explanation = getattr(result, "explanation", None) or _result_metadata(result).get("explanation", "")
    if value and value.upper() == "ERROR":
        raise ValueError(
            f"JIT dependency '{dependency_config.get('name')}' returned ERROR: {explanation[:255] if explanation else 'No explanation'}"
        )

    metadata = _result_metadata(result)
    score_name = dependency_config.get("name")
    registry_props = _score_registry_properties(scorecard_instance, score_name) if score_name else {}
    score_result_id = await create_score_result(
        item_id=item_id,
        scorecard_id=scorecard_id,
        score_id=str(dependency_config.get("id")),
        account_id=account_id,
        scoring_job_id=scoring_job_id,
        external_id=external_id,
        value=value,
        explanation=explanation,
        trace_data=_trace_from_result_metadata(metadata),
        log_content=None,
        cost=metadata.get("cost"),
        start_time_seconds=getattr(result, "start_time_seconds", None),
        end_time_seconds=getattr(result, "end_time_seconds", None),
        score_version_id=score_version_id(registry_props or dependency_config),
        metadata_extra={
            "score_config_fingerprint": metadata.get("score_config_fingerprint"),
            "created_via": "jit_dependency_score_result",
            "parent_scoring_job_id": scoring_job_id,
            "requested_score_id": requested_score_id,
            "requested_score_name": requested_score_name,
        },
        client=client,
    )
    if not score_result_id:
        raise RuntimeError(f"Failed to persist JIT dependency ScoreResult for {dependency_config.get('name')}")

    await enqueue_downstream_recompute_jobs(
        client=client,
        account_id=account_id,
        item_id=item_id,
        scorecard_id=scorecard_id,
        dependency_score_id=str(dependency_config.get("id")),
        dependency_score_name=str(dependency_config.get("name")),
        source_score_result_id=score_result_id,
    )
    return score_result_id


async def ensure_persisted_dependencies(
    *,
    scorecard_instance: Any,
    text: str,
    metadata: dict,
    modality: str,
    item: Any,
    client: Any,
    item_id: str,
    account_id: str,
    scorecard_id: str,
    scoring_job_id: str,
    external_id: str,
    dependency_configs: list,
    requested_score_id: str,
    requested_score_name: str,
    active_score_ids: set,
):
    """Compute and persist missing dependencies before a computed score runs."""

    dependency_by_id = {
        str(config.get("id")): config
        for config in dependency_configs
        if config.get("id")
    }

    snapshot, results = await fetch_persisted_dependency_snapshot(
        client=client,
        item_id=item_id,
        account_id=account_id,
        dependency_configs=dependency_configs,
    )
    if snapshot.complete:
        return snapshot, results

    for missing in snapshot.missing_dependencies:
        dependency_id = str(missing.get("score_id") or "")
        dependency_config = dependency_by_id.get(dependency_id)
        if not dependency_id or dependency_config is None:
            raise RuntimeError(f"Cannot compute missing dependency without a score ID: {missing}")
        if dependency_id in active_score_ids:
            raise RuntimeError(
                f"Dependency cycle detected while computing {dependency_config.get('name')}"
            )

        single_snapshot, _ = await fetch_persisted_dependency_snapshot(
            client=client,
            item_id=item_id,
            account_id=account_id,
            dependency_configs=[dependency_config],
        )
        if single_snapshot.complete:
            continue

        dependency_name = dependency_config.get("name")
        logging.info(
            "Computing missing dependency '%s' (%s) just-in-time for requested score '%s'",
            dependency_name,
            dependency_id,
            requested_score_name,
        )
        dependency_outcome = await score_single_target_with_dependencies(
            scorecard_instance,
            text=text,
            metadata=metadata,
            modality=modality,
            item=item,
            target_score_id=dependency_id,
            target_score_name=dependency_name,
            client=client,
            item_id=item_id,
            account_id=account_id,
            scorecard_id=scorecard_id,
            scoring_job_id=scoring_job_id,
            external_id=external_id,
            requested_score_id=requested_score_id,
            requested_score_name=requested_score_name,
            _active_score_ids=active_score_ids | {dependency_id},
        )
        if dependency_outcome.dependency_unmet or dependency_outcome.result is None:
            raise RuntimeError(
                f"Dependency '{dependency_name}' could not be computed for requested score '{requested_score_name}'"
            )

        await _persist_jit_dependency_result(
            scorecard_instance=scorecard_instance,
            result=dependency_outcome.result,
            dependency_config=dependency_config,
            client=client,
            item_id=item_id,
            account_id=account_id,
            scorecard_id=scorecard_id,
            scoring_job_id=scoring_job_id,
            external_id=external_id,
            requested_score_id=requested_score_id,
            requested_score_name=requested_score_name,
        )

    snapshot, results = await fetch_persisted_dependency_snapshot(
        client=client,
        item_id=item_id,
        account_id=account_id,
        dependency_configs=dependency_configs,
    )
    if not snapshot.complete:
        raise RuntimeError(
            f"Missing dependencies remained after JIT persistence for '{requested_score_name}': {snapshot.missing_dependencies}"
        )
    return snapshot, results


async def score_single_target_with_dependencies(
    scorecard_instance,
    *,
    text: str,
    metadata: dict,
    modality: str,
    item: Any,
    target_score_id: str,
    target_score_name: str,
    client: Any = None,
    item_id: Optional[str] = None,
    account_id: Optional[str] = None,
    scorecard_id: Optional[str] = None,
    scoring_job_id: Optional[str] = None,
    external_id: Optional[str] = None,
    requested_score_id: Optional[str] = None,
    requested_score_name: Optional[str] = None,
    _active_score_ids: Optional[set] = None,
) -> SingleScoreExecutionOutcome:
    """
    Execute a single target score while preserving Scorecard dependency backfill behavior.

    Returns a structured outcome so callers can distinguish dependency-unmet from hard failures.
    """

    requested_score_id = requested_score_id or target_score_id
    requested_score_name = requested_score_name or target_score_name
    active_score_ids = set(_active_score_ids or set())
    active_score_ids.add(str(target_score_id))

    dependency_configs = get_target_dependencies(scorecard_instance, target_score_name)

    if dependency_configs and client is not None and item_id:
        persisted_snapshot, persisted_results = await fetch_persisted_dependency_snapshot(
            client=client,
            item_id=item_id,
            account_id=account_id,
            dependency_configs=dependency_configs,
        )
        if persisted_snapshot.complete:
            if not _dependency_conditions_met_from_results(
                scorecard_instance=scorecard_instance,
                target_score_id=target_score_id,
                target_score_name=target_score_name,
                dependency_configs=dependency_configs,
                dependency_results=persisted_results,
            ):
                logging.info(
                    "Persisted dependencies did not meet conditions for computed score '%s'",
                    target_score_name,
                )
                return SingleScoreExecutionOutcome(
                    result=None,
                    dependency_unmet=True,
                    score_results={target_score_id: "SKIPPED"},
                    dependency_snapshot=persisted_snapshot,
                    current_dependency_snapshot=persisted_snapshot,
                    used_persisted_dependencies=True,
                )

        else:
            if not all([account_id, scorecard_id, scoring_job_id, external_id]):
                raise RuntimeError(
                    f"Cannot compute missing dependencies for '{target_score_name}' "
                    "without ScoreResult persistence context"
                )

            logging.info(
                "Persisted dependencies incomplete for computed score '%s'; computing and persisting missing dependencies. Missing: %s",
                target_score_name,
                persisted_snapshot.missing_dependencies,
            )
            persisted_snapshot, persisted_results = await ensure_persisted_dependencies(
                scorecard_instance=scorecard_instance,
                text=text,
                metadata=metadata,
                modality=modality,
                item=item,
                client=client,
                item_id=item_id,
                account_id=account_id,
                scorecard_id=scorecard_id,
                scoring_job_id=scoring_job_id,
                external_id=external_id,
                dependency_configs=dependency_configs,
                requested_score_id=requested_score_id,
                requested_score_name=requested_score_name,
                active_score_ids=active_score_ids,
            )

            if not _dependency_conditions_met_from_results(
                scorecard_instance=scorecard_instance,
                target_score_id=target_score_id,
                target_score_name=target_score_name,
                dependency_configs=dependency_configs,
                dependency_results=persisted_results,
            ):
                logging.info(
                    "Persisted dependencies did not meet conditions for computed score '%s'",
                    target_score_name,
                )
                return SingleScoreExecutionOutcome(
                    result=None,
                    dependency_unmet=True,
                    score_results={target_score_id: "SKIPPED"},
                    dependency_snapshot=persisted_snapshot,
                    current_dependency_snapshot=persisted_snapshot,
                    used_persisted_dependencies=True,
                )

        if persisted_snapshot.complete:
            logging.info(
                "Using %s persisted dependency ScoreResult(s) for computed score '%s'",
                len(persisted_results),
                target_score_name,
            )
            direct_result = await scorecard_instance.get_score_result(
                scorecard=scorecard_instance.name() if callable(scorecard_instance.name) else scorecard_instance.name,
                score=target_score_name,
                text=text or "",
                metadata=metadata or {},
                modality=modality,
                results=persisted_results,
                item=item,
            )
            result = _unwrap_score_result_entry(direct_result)

            if result is not None and result != "SKIPPED":
                result.metadata = dict(getattr(result, "metadata", None) or {})
                result.metadata["trace"] = merge_snapshot_into_trace(
                    result.metadata.get("trace"),
                    snapshot=persisted_snapshot,
                )

            return SingleScoreExecutionOutcome(
                result=None if result == "SKIPPED" else result,
                dependency_unmet=result == "SKIPPED",
                score_results={target_score_id: result},
                dependency_snapshot=persisted_snapshot,
                current_dependency_snapshot=persisted_snapshot,
                used_persisted_dependencies=True,
            )

    try:
        score_results = await scorecard_instance.score_entire_text(
            text=text or "",
            metadata=metadata or {},
            modality=modality,
            subset_of_score_names=[target_score_name],
            item=item,
        )
    except Exception as exc:
        if exc.__class__.__name__ == "SkippedScoreException":
            return SingleScoreExecutionOutcome(
                result=None,
                dependency_unmet=True,
                score_results={},
            )
        raise

    score_results = score_results or {}
    dependency_unmet = False

    raw_entry = score_results.get(target_score_id)
    result = _unwrap_score_result_entry(raw_entry)
    if result == "SKIPPED":
        result = None
        dependency_unmet = True

    if result is None:
        for entry in score_results.values():
            normalized_entry = _unwrap_score_result_entry(entry)
            if normalized_entry == "SKIPPED":
                dependency_unmet = True
                continue

            parameters = getattr(normalized_entry, "parameters", None)
            if not parameters:
                continue

            candidate_name = getattr(parameters, "name", None)
            candidate_key = getattr(parameters, "key", None)
            if candidate_name == target_score_name or candidate_key == target_score_name:
                result = normalized_entry
                break

    if result is None and any(
        _unwrap_score_result_entry(entry) == "SKIPPED" for entry in score_results.values()
    ):
        dependency_unmet = True

    return SingleScoreExecutionOutcome(
        result=result,
        dependency_unmet=dependency_unmet,
        score_results=score_results,
        used_persisted_dependencies=False,
    )

async def resolve_scorecard_id(external_id: str, account_id: str, client) -> Optional[str]:
    """
    Resolve a scorecard external ID to its DynamoDB ID using the GSI, scoped by accountId.
    
    Args:
        external_id: The external ID of the scorecard
        account_id: The DynamoDB ID of the account
        client: The dashboard client
        
    Returns:
        The DynamoDB ID of the scorecard if found, None otherwise
    """
    try:
        if ScorecardModel is None:
            raise RuntimeError("Scorecard model is unavailable")
        # Use the Scorecard SDK method for lookup
        scorecard = await asyncio.to_thread(
            ScorecardModel.get_by_account_and_external_id,
            account_id,
            external_id,
            client
        )
        
        if scorecard:
            logging.info(f"Resolved scorecard external ID {external_id} for account {account_id} to DynamoDB ID {scorecard.id}")
            return scorecard.id
            
        logging.warning(f"Could not resolve scorecard external ID: {external_id} for account {account_id}")
        return None
    except Exception as e:
        logging.error(f"Error resolving scorecard external ID for account {account_id}: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

async def resolve_score_id(external_id: str, scorecard_dynamo_id: str, client) -> Optional[Dict[str, str]]:
    """
    Resolve a score external ID to its DynamoDB ID and name, scoped by its parent scorecard's DynamoDB ID.
    
    Args:
        external_id: The external ID of the score (e.g., "0")
        scorecard_dynamo_id: The DynamoDB ID of the parent scorecard
        client: The dashboard client
        
    Returns:
        A dictionary with 'id' (DynamoDB ID) and 'name' of the score if found, None otherwise
    """
    try:
        if ScoreModel is None:
            raise RuntimeError("Score model is unavailable")
        # Use the Score SDK method for lookup
        score_data = await asyncio.to_thread(
            ScoreModel.get_by_scorecard_and_external_id,
            scorecard_dynamo_id,
            external_id,
            client
        )
        
        if score_data:
            logging.info(f"Resolved score external ID {external_id} for scorecard {scorecard_dynamo_id} to DynamoDB ID {score_data['id']} with name {score_data['name']}")
            return {"id": score_data['id'], "name": score_data['name']}
            
        logging.warning(f"Could not resolve score external ID: {external_id} for scorecard {scorecard_dynamo_id}")
        return None
    except Exception as e:
        logging.error(f"Error resolving score external ID {external_id} for scorecard {scorecard_dynamo_id}: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

async def create_score_result(
    item_id: str,
    scorecard_id: str,
    score_id: str,
    account_id: str,
    scoring_job_id: str,
    external_id: str,
    value: str,
    explanation: str,
    trace_data: dict = None,
    log_content: str = None,
    cost: dict = None,
    start_time_seconds: Optional[float] = None,
    end_time_seconds: Optional[float] = None,
    score_version_id: Optional[str] = None,
    metadata_extra: Optional[dict] = None,
    code: str = "200",
    status: str = "COMPLETED",
    client: "PlexusDashboardClient" = None
):
    """
    Create a ScoreResult in DynamoDB for caching worker results.

    Args:
        item_id: The DynamoDB Item ID
        scorecard_id: The DynamoDB Scorecard ID
        score_id: The DynamoDB Score ID
        account_id: The DynamoDB Account ID
        scoring_job_id: The DynamoDB ScoringJob ID
        external_id: The externalId of the Item
        value: The score value
        explanation: The explanation for the score
        trace_data: Optional trace data to upload to S3
        log_content: Optional log content to upload to S3
        cost: Optional cost data
        start_time_seconds: Optional evidence start timestamp in seconds
        end_time_seconds: Optional evidence end timestamp in seconds
        score_version_id: Optional score version ID to persist with the result
        metadata_extra: Additional metadata to merge into the ScoreResult metadata
        code: ScoreResult code field
        status: ScoreResult status field
        client: The PlexusDashboardClient instance
    """
    try:
        if ScoreResult is None:
            raise RuntimeError("ScoreResult model is unavailable")
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        score_result_metadata = {
            "source": "Worker",
            "cached_at": now,
            "external_id": external_id,
            "explanation": explanation
        }
        if metadata_extra:
            score_result_metadata.update(metadata_extra)

        # Prepare cost data separately for the cost field
        cost_data = None
        if cost is not None:
            try:
                # Ensure cost is JSON-serializable
                json.dumps(cost, default=str)
                cost_data = cost
            except Exception:
                cost_data = {"raw": str(cost)}

        timestamp_source = {
            "start_time_seconds": start_time_seconds,
            "end_time_seconds": end_time_seconds,
        }
        timestamps = extract_score_result_timestamps(timestamp_source, explanation)
        timestamp_input = timestamps.as_graphql_input()

        optional_create_fields = {}
        if score_version_id:
            optional_create_fields["scoreVersionId"] = score_version_id

        # Create ScoreResult using model method
        score_result = await asyncio.to_thread(
            ScoreResult.create,
            client=client,
            value=value,
            itemId=item_id,
            accountId=account_id,
            scorecardId=scorecard_id,
            scoreId=score_id,
            scoringJobId=scoring_job_id,
            explanation=explanation,
            metadata=score_result_metadata,
            trace=trace_data,
            cost=cost_data,
            code=code,
            type="prediction",
            status=status,
            **optional_create_fields,
            **timestamp_input,
        )

        if not score_result:
            logging.error(f"Failed to create ScoreResult")
            return None

        score_result_id = score_result.id
        score_result_created_at = score_result.createdAt
        logging.info(f"✅ Created ScoreResult with ID: {score_result_id}")

        # Handle trace data and log uploads to S3
        attachment_s3_paths = []
        upload_errors = []

        # Upload trace data if available
        if trace_data:
            try:
                if upload_score_result_trace_file is None:
                    raise RuntimeError("Trace upload utility is unavailable")
                logging.info(f"🔄 Starting trace data upload to S3 for ScoreResult {score_result_id}")
                s3_path = await asyncio.to_thread(upload_score_result_trace_file, score_result_id, trace_data)
                if s3_path:
                    attachment_s3_paths.append(s3_path)
                    logging.info(f"✅ Successfully uploaded trace data to S3: {s3_path}")
                else:
                    upload_errors.append("trace: No S3 path returned")
                    logging.warning(f"⚠️ No S3 path returned from trace upload")
            except Exception as trace_error:
                error_msg = f"Error uploading trace data: {str(trace_error)}"
                upload_errors.append(f"trace: {error_msg}")
                logging.error(f"❌ {error_msg}")
                logging.error(traceback.format_exc())

        # Upload log content if available
        if log_content:
            try:
                if upload_score_result_log_file is None:
                    raise RuntimeError("Log upload utility is unavailable")
                logging.info(f"🔄 Starting log content upload to S3 for ScoreResult {score_result_id}")
                s3_path = await asyncio.to_thread(upload_score_result_log_file, score_result_id, log_content)
                if s3_path:
                    attachment_s3_paths.append(s3_path)
                    logging.info(f"✅ Successfully uploaded log content to S3: {s3_path}")
                else:
                    upload_errors.append("log: No S3 path returned")
                    logging.warning(f"⚠️ No S3 path returned from log upload")
            except Exception as log_error:
                error_msg = f"Error uploading log content: {str(log_error)}"
                upload_errors.append(f"log: {error_msg}")
                logging.error(f"❌ {error_msg}")
                logging.error(traceback.format_exc())

        # Update the ScoreResult with attachments if any were uploaded successfully
        if attachment_s3_paths:
            try:
                logging.info(f"📎 Updating ScoreResult {score_result_id} with {len(attachment_s3_paths)} attachment(s): {attachment_s3_paths}")

                # Convert createdAt to ISO string if it's a datetime object
                created_at_str = score_result_created_at.isoformat() if isinstance(score_result_created_at, datetime) else score_result_created_at
                
                # Update ScoreResult using model method
                updated_score_result = await asyncio.to_thread(
                    score_result.update,
                    attachments=attachment_s3_paths,
                    itemId=item_id,
                    scorecardId=scorecard_id,
                    scoreId=score_id,
                    createdAt=created_at_str
                )

                if updated_score_result:
                    logging.info(f"✅ Successfully updated ScoreResult with attachment")
                else:
                    error_msg = f"Failed to update ScoreResult with attachments"
                    upload_errors.append(f"update_attachments: {error_msg}")
                    logging.error(f"❌ Failed to update ScoreResult with attachment")
            except Exception as attachment_error:
                error_msg = f"Exception during ScoreResult attachment update: {str(attachment_error)}"
                upload_errors.append(f"update_attachments: {error_msg}")
                logging.error(f"❌ Error updating ScoreResult with attachment: {str(attachment_error)}")
                logging.error(traceback.format_exc())

        if upload_errors:
            logging.warning(f"⚠️ Attachment process completed with errors: {upload_errors}")
        elif trace_data or log_content:
            logging.info(f"✅ Attachment process completed successfully")

        return score_result_id

    except Exception as e:
        logging.error(f"Error creating score result: {e}")
        logging.error(traceback.format_exc())
        raise RuntimeError(f"Error creating score result: {e}") from e


async def enqueue_downstream_recompute_jobs(
    *,
    client: "PlexusDashboardClient",
    account_id: str,
    item_id: str,
    scorecard_id: str,
    dependency_score_id: str,
    dependency_score_name: str,
    source_score_result_id: Optional[str] = None,
) -> list:
    """Best-effort downstream recompute enqueue for scores depending on a fresh result."""

    try:
        from ruamel.yaml import YAML
        from plexus.cli.shared.fetch_scorecard_structure import fetch_scorecard_structure
        from plexus.cli.shared.identify_target_scores import identify_target_scores
        from plexus.cli.shared.iterative_config_fetching import iteratively_fetch_configurations
        from plexus.dashboard.api.models.scoring_job import ScoringJob

        scorecard_structure = await asyncio.to_thread(
            fetch_scorecard_structure,
            client,
            scorecard_id,
        )
        if not scorecard_structure:
            logging.warning("Could not fetch scorecard structure for downstream recompute lookup: %s", scorecard_id)
            return []

        all_scores = await asyncio.to_thread(identify_target_scores, scorecard_structure, None)
        if not all_scores:
            return []

        configurations = await asyncio.to_thread(
            iteratively_fetch_configurations,
            client,
            scorecard_structure,
            all_scores,
            False,
        )

        yaml_parser = YAML(typ="safe")
        downstream_scores = []
        for score in all_scores:
            score_id = score.get("id")
            if not score_id or str(score_id) == str(dependency_score_id):
                continue
            raw_config = configurations.get(score_id)
            if not raw_config:
                continue
            try:
                parsed_config = yaml_parser.load(raw_config) if isinstance(raw_config, str) else dict(raw_config)
            except Exception:
                logging.warning("Could not parse score config while resolving downstream recomputes: %s", score_id)
                continue
            dependency_names = get_dependency_names(parsed_config)
            if dependency_score_name in dependency_names:
                downstream_scores.append(score)

        enqueued = []
        for downstream_score in downstream_scores:
            downstream_score_id = downstream_score.get("id")
            existing = await asyncio.to_thread(
                ScoringJob.find_existing_job,
                client,
                item_id,
                scorecard_id,
                downstream_score_id,
            )
            if existing and existing.get("status") in {"PENDING", "IN_PROGRESS"}:
                logging.info(
                    "Skipping downstream recompute for %s; active job already exists: %s",
                    downstream_score_id,
                    existing,
                )
                continue

            scoring_job = await asyncio.to_thread(
                ScoringJob.create,
                client=client,
                accountId=account_id,
                scorecardId=scorecard_id,
                itemId=item_id,
                scoreId=downstream_score_id,
                parameters={},
                metadata={
                    "created_via": "dependent_score_recompute",
                    "dependency_score_id": dependency_score_id,
                    "dependency_score_name": dependency_score_name,
                    "source_score_result_id": source_score_result_id,
                    "downstream_score_name": downstream_score.get("name"),
                },
                status="PENDING",
            )
            await send_message_to_standard_scoring_request_queue(scoring_job.id)
            enqueued.append({
                "scoring_job_id": scoring_job.id,
                "score_id": downstream_score_id,
                "score_name": downstream_score.get("name"),
            })

        if enqueued:
            logging.info("Enqueued %s downstream recompute job(s): %s", len(enqueued), enqueued)
        return enqueued

    except Exception as exc:
        logging.error("Downstream recompute enqueue failed: %s", exc)
        logging.error(traceback.format_exc())
        return []


async def get_existing_score_result(report_id: str, scorecard_id: str, score_id: str, type: str, account_id: str) -> Optional[dict]:
    """
    Check if a score result already exists for the given report, scorecard, and score.
    Now uses the new ScoreResult.find_by_cache_key method for cleaner, more maintainable code.
    
    Args:
        report_id: The external ID of the report
        scorecard_id: The external ID of the scorecard
        score_id: The external ID of the score
        account_id: The DynamoDB ID of the account
    Returns:
        A dictionary with the cached result if found, None otherwise
    """
    try:
        if ScoreResult is None:
            raise RuntimeError("ScoreResult model is unavailable")
        client = await get_plexus_client()
        
        # Use Item.find_by_identifier to get the item (consistent with cache creation)
        if PLEXUS_ITEM_AVAILABLE:
            item = await asyncio.to_thread(
                Item.find_by_identifier,
                client=client,
                account_id=account_id,
                identifier_key="reportId",  # Use input key (will be mapped to "report ID" internally)
                identifier_value=report_id,
                debug=True  # Enable debug logging to verify the fix
            )
            
            if not item:
                logging.info(f"❌ No Item found with reportId: {report_id} in account: {account_id}")
                return None
            
            logging.info(f"✅ Found Item with ID: {item.id} for reportId: {report_id}")
        else:
            logging.error("Plexus Item SDK not available")
            return None
        
        # Resolve scorecard and score IDs
        # CRITICAL: We must have valid DynamoDB IDs for both scorecard and score to prevent cache pollution.
        # Previously, using external IDs as fallbacks caused incorrect cache hits where requests for 
        # non-existent scores would return cached results from completely different scores/scorecards.
        dynamo_scorecard_id = await resolve_scorecard_id(scorecard_id, account_id, client)
        if not dynamo_scorecard_id:
            logging.warning(f"Scorecard ID {scorecard_id} could not be resolved - skipping cache lookup to prevent cross-scorecard pollution")
            return None
        
        resolved_score_info = await resolve_score_id(score_id, dynamo_scorecard_id, client)
        if not resolved_score_info:
            logging.warning(f"Score ID {score_id} could not be resolved - skipping cache lookup to prevent cross-score pollution")
            return None
        
        dynamo_score_id = resolved_score_info['id']
        
        # Use the new ScoreResult.find_by_cache_key method
        cached_score_result = await asyncio.to_thread(
            ScoreResult.find_by_cache_key,
            client=client,
            item_id=item.id,
            type=type,
            score_id=dynamo_score_id,
            account_id=account_id,
        )
        
        if cached_score_result:
            logging.info(f"✅ CACHE HIT: Found cached result {cached_score_result.id} with value: {cached_score_result.value}")
            logging.info(json.dumps({
                "message_type": "cache_hit_found",
                "score_result_id": cached_score_result.id,
                "report_id": report_id,
                "scorecard_id": scorecard_id,
                "score_id": score_id,
                "item_id": item.id,
                "value": cached_score_result.value,
                "updated_at": cached_score_result.updatedAt.isoformat() if cached_score_result.updatedAt else None,
                "method": "score_result_find_by_cache_key"
            }))
            
            return {
                "value": cached_score_result.value,
                "explanation": cached_score_result.explanation or ''
            }
        else:
            logging.info(f"❌ CACHE MISS: No cached result found for item_id={item.id}, scorecard_id={dynamo_scorecard_id}, score_id={dynamo_score_id}")
            logging.info(json.dumps({
                "message_type": "cache_miss_no_result",
                "report_id": report_id,
                "scorecard_id": scorecard_id,
                "score_id": score_id,
                "item_id": item.id,
                "dynamo_scorecard_id": dynamo_scorecard_id,
                "dynamo_score_id": dynamo_score_id,
                "operation": "no_cached_score_result_found"
            }))
            
            return None
        
    except Exception as e:
        logging.error(f"Error checking for existing score result: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        logging.error(json.dumps({
            "message_type": "cache_lookup_error",
            "error": str(e),
            "report_id": report_id,
            "scorecard_id": scorecard_id,
            "score_id": score_id
        }))
        return None

async def get_text_from_item(item_id: str, client: "PlexusDashboardClient") -> str:
    """
    Get text from an Item in DynamoDB by its item_id.

    Args:
        item_id: The DynamoDB ID of the Item
        client: The PlexusDashboardClient instance

    Returns:
        The text content of the item, or None if not found
    """
    try:
        query = """
        query GetItem($id: ID!) {
            getItem(id: $id) {
                id
                text
            }
        }
        """

        variables = {"id": item_id}
        result = await asyncio.to_thread(client.execute, query, variables)

        item_data = result.get('getItem')
        if not item_data:
            logging.error(f"Item not found: {item_id}")
            return None

        return item_data.get('text')

    except Exception as e:
        logging.error(f"Error getting text from item {item_id}: {e}")
        logging.error(traceback.format_exc())
        return None

async def get_metadata_from_item(item_id: str, client: "PlexusDashboardClient") -> dict:
    """
    Get metadata from an Item in DynamoDB by its item_id.

    Args:
        item_id: The DynamoDB ID of the Item
        client: The PlexusDashboardClient instance

    Returns:
        The metadata dictionary, or empty dict if not found
    """
    try:
        query = """
        query GetItem($id: ID!) {
            getItem(id: $id) {
                id
                metadata
            }
        }
        """

        variables = {"id": item_id}
        result = await asyncio.to_thread(client.execute, query, variables)

        item_data = result.get('getItem')
        if not item_data:
            logging.error(f"Item not found: {item_id}")
            return {}

        metadata_raw = item_data.get('metadata')

        # metadata is stored as a JSON string in DynamoDB, parse it
        if isinstance(metadata_raw, str):
            try:
                return json.loads(metadata_raw)
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse metadata JSON for item {item_id}: {metadata_raw}")
                return {}
        elif isinstance(metadata_raw, dict):
            return metadata_raw
        else:
            return {}

    except Exception as e:
        logging.error(f"Error getting metadata from item {item_id}: {e}")
        logging.error(traceback.format_exc())
        return {}

async def get_external_id_from_item(item_id: str, client: "PlexusDashboardClient") -> str:
    """
    Get externalId from an Item in DynamoDB by its item_id.

    Args:
        item_id: The DynamoDB ID of the Item
        client: The PlexusDashboardClient instance

    Returns:
        The externalId of the item, or None if not found
    """
    try:
        query = """
        query GetItem($id: ID!) {
            getItem(id: $id) {
                id
                externalId
            }
        }
        """

        variables = {"id": item_id}
        result = await asyncio.to_thread(client.execute, query, variables)

        item_data = result.get('getItem')
        if not item_data:
            logging.error(f"Item not found: {item_id}")
            return None

        return item_data.get('externalId')

    except Exception as e:
        logging.error(f"Error getting externalId from item {item_id}: {e}")
        logging.error(traceback.format_exc())
        return None
