from __future__ import annotations

from typing import Any, Mapping

from plexus.cli.procedure.model_performance_frontier import (
    _extract_fields,
    _load_yaml,
    build_variants,
)


SUPPORTED_SCORE_CLASSES = {"LangGraphScore", "TactusScore"}


def _target_value(target: Mapping[str, Any], key: str) -> Any:
    value = target.get(key)
    return value if value not in ("", None) else None


def plan_score_retarget(
    *,
    yaml_content: str,
    target: Mapping[str, Any],
) -> dict[str, Any]:
    """Plan a single score model retarget using frontier variant generation."""

    if not isinstance(target, Mapping):
        raise ValueError("target must be an object")

    model_name = _target_value(target, "model_name")
    if not model_name:
        raise ValueError("target.model_name is required")

    parsed = _load_yaml(yaml_content)
    if not isinstance(parsed, Mapping):
        raise ValueError("Score YAML must parse to a mapping")

    score_class = str(parsed.get("class") or "")
    if score_class not in SUPPORTED_SCORE_CLASSES:
        raise ValueError(
            f"Unsupported score class {score_class!r}; supported classes are "
            "LangGraphScore and TactusScore."
        )

    if score_class == "TactusScore":
        model_provider = (
            _target_value(target, "tactus_model_provider")
            or _target_value(target, "model_provider")
            or "openai"
        )
    else:
        current_fields = _extract_fields(parsed)
        model_provider = (
            _target_value(target, "langgraph_model_provider")
            or _target_value(target, "model_provider")
            or current_fields.get("model_provider")
            or "ChatOpenAI"
        )

    parameter_set: dict[str, Any] = {"label": "target"}
    for key in ("reasoning_effort", "verbosity", "temperature", "max_tokens"):
        value = _target_value(target, key)
        if value is not None:
            parameter_set[key] = value
    if isinstance(target.get("extra_overrides"), Mapping):
        parameter_set["extra_overrides"] = dict(target["extra_overrides"])

    plan = build_variants(
        yaml_content,
        {
            "include_current": True,
            "models": [
                {
                    "label": str(model_name),
                    "model_provider": model_provider,
                    "model_name": model_name,
                }
            ],
            "parameter_sets": [parameter_set],
        },
    )
    changed_variants = [variant for variant in plan if not variant.get("is_current")]
    current = next((variant for variant in plan if variant.get("is_current")), None)

    if not changed_variants:
        return {
            "changed": False,
            "score_class": score_class,
            "current": current,
            "target": dict(target),
            "message": "Score already matches target model configuration.",
        }

    candidate = changed_variants[0]
    return {
        "changed": True,
        "score_class": score_class,
        "current": current,
        "target": dict(target),
        "candidate": candidate,
        "yaml_content": candidate["yaml_content"],
        "message": "Retargeted score YAML planned.",
    }
