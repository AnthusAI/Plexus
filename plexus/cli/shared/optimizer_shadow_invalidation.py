from __future__ import annotations

import hashlib
import json
from io import StringIO
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ruamel.yaml import YAML


OPTIMIZER_SHADOW_INVALID_FIELD = "optimizer_shadow_invalid_feedback_item_ids"


def build_shadow_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.map_indent = 2
    yaml.sequence_indent = 4
    yaml.sequence_dash_offset = 2

    def literal_presenter(dumper, data):
        if isinstance(data, str) and "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.representer.add_representer(str, literal_presenter)
    return yaml


def normalize_shadow_invalid_feedback_item_ids(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, Sequence):
        raw_values = list(value)
    else:
        return []

    normalized: List[str] = []
    seen = set()
    for raw in raw_values:
        item_id = str(raw or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        normalized.append(item_id)
    normalized.sort()
    return normalized


def parse_score_yaml_text(config_text: str) -> Any:
    yaml = build_shadow_yaml()
    return yaml.load(config_text or "")


def extract_shadow_invalid_feedback_item_ids_from_mapping(config: Mapping[str, Any]) -> List[str]:
    return normalize_shadow_invalid_feedback_item_ids(
        config.get(OPTIMIZER_SHADOW_INVALID_FIELD)
    )


def extract_shadow_invalid_feedback_item_ids_from_yaml_text(config_text: str) -> List[str]:
    parsed = parse_score_yaml_text(config_text)
    if not isinstance(parsed, Mapping):
        return []
    return extract_shadow_invalid_feedback_item_ids_from_mapping(parsed)


def normalize_shadow_invalid_field_in_yaml_text(config_text: str) -> Tuple[str, List[str]]:
    yaml = build_shadow_yaml()
    parsed = yaml.load(config_text or "")
    if not isinstance(parsed, dict):
        raise ValueError("Score configuration must be a YAML mapping.")

    normalized_ids = extract_shadow_invalid_feedback_item_ids_from_mapping(parsed)
    if normalized_ids:
        parsed[OPTIMIZER_SHADOW_INVALID_FIELD] = normalized_ids
    else:
        parsed.pop(OPTIMIZER_SHADOW_INVALID_FIELD, None)

    rendered = StringIO()
    yaml.dump(parsed, rendered)
    return rendered.getvalue(), normalized_ids


def build_feedback_target_hash(
    *,
    score_version_id: Optional[str],
    days: Optional[int],
    shadow_invalid_feedback_item_ids: Sequence[str],
) -> str:
    payload = {
        "score_version_id": str(score_version_id or ""),
        "days": int(days) if days is not None else None,
        "shadow_invalid_feedback_item_ids": normalize_shadow_invalid_feedback_item_ids(
            shadow_invalid_feedback_item_ids
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_score_version_configuration(
    client,
    *,
    score_id: str,
    score_version_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_score_version_id = score_version_id
    if not resolved_score_version_id:
        score_result = client.execute(
            """
            query GetScoreChampionVersion($id: ID!) {
                getScore(id: $id) {
                    id
                    championVersionId
                }
            }
            """,
            {"id": score_id},
        )
        score_data = score_result.get("getScore") or {}
        champion_version_id = score_data.get("championVersionId")
        if not champion_version_id:
            raise ValueError(f"No champion version configured for score {score_id}.")
        resolved_score_version_id = champion_version_id

    version_result = client.execute(
        """
        query GetScoreVersionConfiguration($id: ID!) {
            getScoreVersion(id: $id) {
                id
                configuration
            }
        }
        """,
        {"id": resolved_score_version_id},
    )
    version_data = version_result.get("getScoreVersion") or {}
    configuration_text = version_data.get("configuration")
    if not configuration_text:
        raise ValueError(
            f"Score version {resolved_score_version_id} has no configuration for score {score_id}."
        )
    return {
        "score_version_id": resolved_score_version_id,
        "configuration": configuration_text,
    }


def resolve_score_version_shadow_invalidation_metadata(
    client,
    *,
    score_id: str,
    score_version_id: Optional[str] = None,
    days: Optional[int] = None,
) -> Dict[str, Any]:
    resolved = resolve_score_version_configuration(
        client,
        score_id=score_id,
        score_version_id=score_version_id,
    )
    shadow_invalid_feedback_item_ids = extract_shadow_invalid_feedback_item_ids_from_yaml_text(
        resolved["configuration"]
    )
    return {
        **resolved,
        "optimizer_shadow_invalid_feedback_item_ids": shadow_invalid_feedback_item_ids,
        "feedback_target_hash": build_feedback_target_hash(
            score_version_id=resolved["score_version_id"],
            days=days,
            shadow_invalid_feedback_item_ids=shadow_invalid_feedback_item_ids,
        ),
    }
