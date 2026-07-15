"""Dependency snapshot helpers for computed score consistency.

These helpers keep dependency consistency concerns outside Score.predict. They
record exactly which child results a computed score used so audits can compare
that snapshot with current persisted dependency results.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SNAPSHOT_SCHEMA_VERSION = "dependency_snapshot_v1"
DEPENDENCY_SOURCE_PERSISTED = "persisted_score_result"
DEPENDENCY_SOURCE_IN_MEMORY = "in_memory_dependency"


@dataclass
class DependencySnapshot:
    """A normalized dependency snapshot for one computed score execution."""

    dependencies: List[Dict[str, Any]]
    missing_dependencies: List[Dict[str, Any]] = field(default_factory=list)
    schema_version: str = SNAPSHOT_SCHEMA_VERSION

    @property
    def complete(self) -> bool:
        return not self.missing_dependencies

    @property
    def hash(self) -> str:
        return stable_hash({
            "schema_version": self.schema_version,
            "dependencies": self.dependencies,
            "missing_dependencies": self.missing_dependencies,
        })

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hash": self.hash,
            "complete": self.complete,
            "dependencies": self.dependencies,
            "missing_dependencies": self.missing_dependencies,
        }


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return {}
    return value if isinstance(value, dict) else {}


def excerpt(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated {len(text) - limit} chars]"


def isoformat(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.isoformat()
    return str(value)


def get_score_config(scorecard_instance: Any, score_name: str) -> Optional[Dict[str, Any]]:
    registry = getattr(scorecard_instance, "score_registry", None)
    if registry is not None:
        try:
            config = registry.get_properties(score_name)
            if config:
                return dict(config)
        except Exception:
            logging.debug("Could not read score config for %s from registry", score_name, exc_info=True)

    for config in getattr(scorecard_instance, "scores", []) or []:
        if not isinstance(config, dict):
            continue
        if score_name in {config.get("name"), config.get("key"), config.get("id"), config.get("externalId")}:
            return dict(config)
    return None


def get_dependency_names(score_config: Optional[Dict[str, Any]]) -> List[str]:
    if not score_config:
        return []
    depends_on = score_config.get("depends_on")
    if isinstance(depends_on, dict):
        return [str(name) for name in depends_on.keys()]
    if isinstance(depends_on, list):
        return [str(name) for name in depends_on]
    return []


def get_target_dependencies(scorecard_instance: Any, target_score_name: str) -> List[Dict[str, Any]]:
    target_config = get_score_config(scorecard_instance, target_score_name)
    dependencies = []
    for dependency_name in get_dependency_names(target_config):
        dependency_config = get_score_config(scorecard_instance, dependency_name) or {"name": dependency_name}
        dependencies.append(dependency_config)
    return dependencies


def score_version_id(score_config: Optional[Dict[str, Any]]) -> Optional[str]:
    if not score_config:
        return None
    for key in ("scoreVersionId", "version", "championVersionId", "version_id"):
        value = score_config.get(key)
        if value:
            return str(value)
    return None


def dependency_entry_from_result(
    *,
    score_config: Dict[str, Any],
    result: Any,
    source: str,
    score_result_id: Optional[str] = None,
    created_at: Any = None,
    updated_at: Any = None,
) -> Dict[str, Any]:
    metadata = getattr(result, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    explanation = getattr(result, "explanation", None) or metadata.get("explanation")
    return {
        "score_id": str(score_config.get("id") or getattr(getattr(result, "parameters", None), "id", "") or ""),
        "score_name": score_config.get("name") or getattr(getattr(result, "parameters", None), "name", None),
        "score_key": score_config.get("key") or getattr(getattr(result, "parameters", None), "key", None),
        "score_external_id": score_config.get("externalId"),
        "score_result_id": score_result_id or getattr(result, "id", None),
        "score_version_id": score_version_id(score_config) or getattr(result, "scoreVersionId", None),
        "value": getattr(result, "value", None),
        "explanation_excerpt": excerpt(explanation),
        "explanation_hash": stable_hash(explanation) if explanation else None,
        "created_at": isoformat(created_at or getattr(result, "createdAt", None)),
        "updated_at": isoformat(updated_at or getattr(result, "updatedAt", None)),
        "source": source,
    }


def snapshot_from_in_memory_results(
    *,
    scorecard_instance: Any,
    target_score_name: str,
    score_results: Dict[str, Any],
) -> DependencySnapshot:
    dependencies = []
    missing = []
    for dependency_config in get_target_dependencies(scorecard_instance, target_score_name):
        dependency_id = str(dependency_config.get("id") or "")
        dependency_name = dependency_config.get("name")
        result = unwrap_result_entry(score_results.get(dependency_id))
        if result is None:
            for candidate in score_results.values():
                candidate = unwrap_result_entry(candidate)
                params = getattr(candidate, "parameters", None)
                if getattr(params, "name", None) == dependency_name:
                    result = candidate
                    break
        if result is None or result == "SKIPPED":
            missing.append({
                "score_id": dependency_id,
                "score_name": dependency_name,
                "score_key": dependency_config.get("key"),
                "source": DEPENDENCY_SOURCE_IN_MEMORY,
                "reason": "missing_in_memory_dependency",
            })
            continue
        dependencies.append(
            dependency_entry_from_result(
                score_config=dependency_config,
                result=result,
                source=DEPENDENCY_SOURCE_IN_MEMORY,
            )
        )
    return DependencySnapshot(dependencies=dependencies, missing_dependencies=missing)


def unwrap_result_entry(entry: Any) -> Any:
    """Normalize Scorecard result-map entries to their actual Score.Result value."""

    if isinstance(entry, dict):
        return entry.get("result")
    if isinstance(entry, list):
        return entry[0] if entry else None
    return entry


def result_from_persisted_score_result(score_result: Any, score_config: Dict[str, Any]) -> Score.Result:
    from plexus.scores.Score import Score

    metadata = getattr(score_result, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    explanation = getattr(score_result, "explanation", None) or metadata.get("explanation")
    return Score.Result(
        value=getattr(score_result, "value", None),
        explanation=explanation,
        parameters=Score.Parameters(
            name=score_config.get("name"),
            id=score_config.get("id"),
            key=score_config.get("key"),
        ),
        metadata={
            **metadata,
            "dependency_source": DEPENDENCY_SOURCE_PERSISTED,
            "score_result_id": getattr(score_result, "id", None),
        },
    )


async def fetch_persisted_dependency_snapshot(
    *,
    client: Any,
    item_id: str,
    account_id: Optional[str],
    dependency_configs: Sequence[Dict[str, Any]],
    result_type: str = "prediction",
) -> Tuple[DependencySnapshot, List[Score.Result]]:
    """Fetch latest persisted ScoreResults for dependency configs."""

    from plexus.dashboard.api.models.score_result import ScoreResult

    dependencies = []
    missing = []
    results = []

    for dependency_config in dependency_configs:
        dependency_id = dependency_config.get("id")
        dependency_name = dependency_config.get("name")
        if not dependency_id:
            missing.append({
                "score_id": None,
                "score_name": dependency_name,
                "score_key": dependency_config.get("key"),
                "source": DEPENDENCY_SOURCE_PERSISTED,
                "reason": "dependency_score_id_missing",
            })
            continue

        score_result = await asyncio.to_thread(
            ScoreResult.find_by_cache_key,
            client=client,
            item_id=item_id,
            type=result_type,
            score_id=str(dependency_id),
            account_id=account_id,
        )
        if not score_result:
            missing.append({
                "score_id": str(dependency_id),
                "score_name": dependency_name,
                "score_key": dependency_config.get("key"),
                "source": DEPENDENCY_SOURCE_PERSISTED,
                "reason": "persisted_dependency_missing",
            })
            continue

        dependencies.append(
            dependency_entry_from_result(
                score_config=dependency_config,
                result=score_result,
                source=DEPENDENCY_SOURCE_PERSISTED,
                score_result_id=getattr(score_result, "id", None),
                created_at=getattr(score_result, "createdAt", None),
                updated_at=getattr(score_result, "updatedAt", None),
            )
        )
        results.append(result_from_persisted_score_result(score_result, dependency_config))

    return DependencySnapshot(dependencies=dependencies, missing_dependencies=missing), results


def merge_snapshot_into_trace(
    trace: Optional[Dict[str, Any]],
    *,
    snapshot: Optional[DependencySnapshot],
) -> Optional[Dict[str, Any]]:
    if snapshot is None:
        return trace
    trace_data = dict(trace or {})
    trace_data[SNAPSHOT_SCHEMA_VERSION] = snapshot.as_dict()
    return trace_data


def extract_dependency_snapshot(value: Any) -> Optional[Dict[str, Any]]:
    data = json_object(value)
    snapshot = data.get(SNAPSHOT_SCHEMA_VERSION)
    return snapshot if isinstance(snapshot, dict) else None


def dependency_snapshot_from_score_result(score_result: Any) -> Optional[Dict[str, Any]]:
    trace_snapshot = extract_dependency_snapshot(getattr(score_result, "trace", None))
    if trace_snapshot:
        return trace_snapshot
    return extract_dependency_snapshot(getattr(score_result, "metadata", None))


def dependency_configs_from_snapshot(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    dependency_configs = []
    for dependency in snapshot.get("dependencies") or []:
        if not isinstance(dependency, dict):
            continue
        dependency_configs.append({
            "id": dependency.get("score_id"),
            "name": dependency.get("score_name"),
            "key": dependency.get("score_key"),
            "externalId": dependency.get("score_external_id"),
            "scoreVersionId": dependency.get("score_version_id"),
        })
    return dependency_configs


async def check_score_result_dependency_snapshot_current(
    *,
    score_result: Any,
    client: Any,
    item_id: str,
    account_id: Optional[str],
) -> Dict[str, Any]:
    """Compare a cached computed result's stored dependency snapshot to current persisted dependencies."""

    stored_snapshot = dependency_snapshot_from_score_result(score_result)
    if not stored_snapshot:
        return {
            "has_dependency_snapshot": False,
            "matches": True,
            "reason": "no_dependency_snapshot",
        }

    stored_hash = stored_snapshot.get("hash")
    if not stored_hash:
        stored_hash = stable_hash({
            "schema_version": stored_snapshot.get("schema_version", SNAPSHOT_SCHEMA_VERSION),
            "dependencies": stored_snapshot.get("dependencies") or [],
            "missing_dependencies": stored_snapshot.get("missing_dependencies") or [],
        })

    dependency_configs = dependency_configs_from_snapshot(stored_snapshot)
    if not dependency_configs:
        return {
            "has_dependency_snapshot": True,
            "matches": False,
            "reason": "dependency_snapshot_has_no_dependencies",
            "snapshot_hash": stored_hash,
            "current_snapshot_hash": None,
        }

    current_snapshot, _ = await fetch_persisted_dependency_snapshot(
        client=client,
        item_id=item_id,
        account_id=account_id,
        dependency_configs=dependency_configs,
    )
    matches = current_snapshot.complete and current_snapshot.hash == stored_hash
    reason = None
    if not current_snapshot.complete:
        reason = "current_dependency_missing"
    elif current_snapshot.hash != stored_hash:
        reason = "dependency_snapshot_changed_after_write"

    return {
        "has_dependency_snapshot": True,
        "matches": matches,
        "reason": reason,
        "snapshot_hash": stored_hash,
        "current_snapshot_hash": current_snapshot.hash,
        "complete": current_snapshot.complete,
        "schema_version": stored_snapshot.get("schema_version", SNAPSHOT_SCHEMA_VERSION),
    }
