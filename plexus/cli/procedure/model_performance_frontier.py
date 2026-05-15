from __future__ import annotations

import copy
import csv
import io
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping

from ruamel.yaml import YAML


ROOT_MODEL_FIELDS = (
    "model_provider",
    "model_name",
    "base_model_name",
    "reasoning_effort",
    "verbosity",
    "temperature",
    "max_tokens",
)

TACTUS_ROOT_RUNTIME_FIELDS = (
    "reasoning_effort",
    "verbosity",
)

TACTUS_CLASSIFY_FIELDS = (
    "temperature",
)

TACTUS_PROVIDER_ALIASES = {
    "ChatOpenAI": "openai",
    "OpenAI": "openai",
}


@dataclass(frozen=True)
class FrontierVariant:
    label: str
    yaml_content: str
    is_current: bool
    model_provider: Any = None
    model_name: Any = None
    base_model_name: Any = None
    reasoning_effort: Any = None
    verbosity: Any = None
    temperature: Any = None
    max_tokens: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "yaml_content": self.yaml_content,
            "is_current": self.is_current,
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "base_model_name": self.base_model_name,
            "reasoning_effort": self.reasoning_effort,
            "verbosity": self.verbosity,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml


def _load_yaml(yaml_content: str) -> Any:
    if not isinstance(yaml_content, str) or not yaml_content.strip():
        raise ValueError("yaml_content is required")
    return _yaml().load(yaml_content)


def _dump_yaml(data: Any) -> str:
    stream = io.StringIO()
    _yaml().dump(data, stream)
    return stream.getvalue()


def _semantic_key(data: Any) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): normalize(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        return value

    return json.dumps(normalize(data), sort_keys=True, default=str, separators=(",", ":"))


def _plain_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return _plain_value(json.loads(stripped))
            except json.JSONDecodeError:
                return value
        return value
    if isinstance(value, Mapping):
        converted = {key: _plain_value(item) for key, item in value.items()}
        numeric_keys = [key for key in converted if isinstance(key, int)]
        if numeric_keys and len(numeric_keys) == len(converted):
            keys = sorted(numeric_keys)
            if keys == list(range(1, len(keys) + 1)):
                return [converted[index] for index in keys]
        return converted
    if isinstance(value, list | tuple):
        return [_plain_value(item) for item in value]
    items = getattr(value, "items", None)
    if callable(items):
        pairs = [(key, _plain_value(item)) for key, item in items()]
        if pairs and all(isinstance(key, int) for key, _ in pairs):
            keys = sorted(key for key, _ in pairs)
            if keys == list(range(1, len(keys) + 1)):
                by_key = dict(pairs)
                return [by_key[index] for index in keys]
        return {key: item for key, item in pairs}
    return value


def _variant_label(model: Mapping[str, Any], parameter_set: Mapping[str, Any]) -> str:
    model_label = model.get("label") or model.get("model_name") or "model"
    parameter_label = parameter_set.get("label") or "default"
    if str(parameter_label).strip().lower() in {"", "default"}:
        return str(model_label)
    return f"{model_label} / {parameter_label}"


def _tokenize_path(path: str) -> list[Any]:
    tokens: list[Any] = []
    for raw_part in str(path).split("."):
        if not raw_part:
            raise ValueError(f"Invalid empty path segment in {path!r}")
        part = raw_part
        while "[" in part:
            prefix, rest = part.split("[", 1)
            if prefix:
                tokens.append(prefix)
            index_text, suffix = rest.split("]", 1)
            if not index_text.isdigit():
                raise ValueError(f"Only numeric list indexes are supported in override path {path!r}")
            tokens.append(int(index_text))
            part = suffix
        if part:
            tokens.append(int(part) if part.isdigit() else part)
    return tokens


def apply_override(data: Any, path: str, value: Any) -> None:
    tokens = _tokenize_path(path)
    if not tokens:
        raise ValueError("Override path must not be empty")

    current = data
    for token in tokens[:-1]:
        if isinstance(token, int):
            if not isinstance(current, list):
                raise ValueError(f"Path {path!r} expected a list before index {token}")
            current = current[token]
        else:
            if not isinstance(current, Mapping):
                raise ValueError(f"Path {path!r} expected a mapping before key {token!r}")
            current = current[token]

    last = tokens[-1]
    if isinstance(last, int):
        if not isinstance(current, list):
            raise ValueError(f"Path {path!r} expected a list before index {last}")
        current[last] = value
    else:
        if not isinstance(current, Mapping):
            raise ValueError(f"Path {path!r} expected a mapping before key {last!r}")
        current[last] = value


def _extract_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    fields = {field: data.get(field) for field in ROOT_MODEL_FIELDS}
    if str(data.get("class") or "") == "TactusScore":
        tactus_model = _find_tactus_default_model(data.get("code") or "")
        if tactus_model:
            provider, model_name = _split_tactus_model_id(tactus_model)
            fields["model_provider"] = fields["model_provider"] or provider
            fields["model_name"] = fields["model_name"] or model_name
            fields["base_model_name"] = fields["base_model_name"] or model_name
    return fields


def _split_tactus_model_id(model_id: str) -> tuple[str | None, str]:
    if "/" not in model_id:
        return None, model_id
    provider, model_name = model_id.split("/", 1)
    return provider or None, model_name


def _compose_tactus_model_id(model: Mapping[str, Any], *, current_model_id: str | None = None) -> str | None:
    model_name = model.get("model_name")
    provider = model.get("model_provider")
    if model_name is None:
        return None
    model_name_text = str(model_name)
    if "/" in model_name_text:
        return model_name_text

    current_provider = None
    if current_model_id:
        current_provider, _ = _split_tactus_model_id(current_model_id)
    provider_text = str(provider) if provider is not None else current_provider
    provider_text = TACTUS_PROVIDER_ALIASES.get(provider_text, provider_text)
    return f"{provider_text}/{model_name_text}" if provider_text else model_name_text


def _find_tactus_default_model(code: str) -> str | None:
    if not isinstance(code, str):
        return None
    match = re.search(r'(?m)^([ \t]*)default_model[ \t]*(?:\([ \t]*)?["\']([^"\']+)["\'][ \t]*\)?[ \t]*', code)
    if match:
        return match.group(2)
    match = re.search(r'ClassifyProcedure\s*\{(?P<body>.*?)\n\s*\}', code, flags=re.S)
    if not match:
        return None
    model_match = re.search(r'(?m)^([ \t]*)model\s*=\s*["\']([^"\']+)["\']', match.group("body"))
    return model_match.group(2) if model_match else None


def _replace_or_insert_tactus_default_model(code: str, model_id: str) -> str:
    pattern = re.compile(r'(?m)^([ \t]*)default_model[ \t]*(?:\([ \t]*)?["\']([^"\']+)["\'][ \t]*\)?[ \t]*')
    if pattern.search(code):
        return pattern.sub(lambda match: f'{match.group(1)}default_model "{model_id}"', code, count=1)

    classify_pattern = re.compile(r'(ClassifyProcedure\s*\{(?P<body>.*?)\n\s*\})', flags=re.S)
    classify_match = classify_pattern.search(code)
    if classify_match:
        block = classify_match.group(1)
        model_pattern = re.compile(r'(?m)^([ \t]*)model\s*=\s*["\']([^"\']+)["\']')
        if model_pattern.search(block):
            updated_block = model_pattern.sub(
                lambda match: f'{match.group(1)}model = "{model_id}"',
                block,
                count=1,
            )
            return code[: classify_match.start()] + updated_block + code[classify_match.end() :]

    return f'default_model "{model_id}"\n\n{code}'


def _format_tactus_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    return json.dumps(str(value))


def _replace_or_insert_classify_field(code: str, field: str, value: Any) -> str:
    classify_pattern = re.compile(r'ClassifyProcedure\s*\{(?P<body>.*?)\n(?P<indent>[ \t]*)\}', flags=re.S)
    match = classify_pattern.search(code)
    if not match:
        raise ValueError(f"TactusScore code must define ClassifyProcedure before setting {field!r}")
    block = match.group(0)
    value_text = _format_tactus_value(value)
    field_pattern = re.compile(rf'(?m)^([ \t]*){re.escape(field)}\s*=\s*[^,\n]+,?')
    if field_pattern.search(block):
        updated_block = field_pattern.sub(
            lambda field_match: f"{field_match.group(1)}{field} = {value_text},",
            block,
            count=1,
        )
        return code[: match.start()] + updated_block + code[match.end() :]

    body = match.group("body")
    non_empty_lines = [line for line in body.splitlines() if line.strip()]
    indent = re.match(r"([ \t]*)", non_empty_lines[0]).group(1) if non_empty_lines else "  "
    insert_at = match.start("body")
    return code[:insert_at] + f"\n{indent}{field} = {value_text}," + code[insert_at:]


def _apply_tactus_variant(
    candidate: MutableMapping[str, Any],
    model: Mapping[str, Any],
    parameter_set: Mapping[str, Any],
) -> None:
    current_model_id = _find_tactus_default_model(candidate.get("code") or "")
    model_id = _compose_tactus_model_id(model, current_model_id=current_model_id)
    if model_id:
        candidate["code"] = _replace_or_insert_tactus_default_model(candidate.get("code") or "", model_id)

    for field in TACTUS_ROOT_RUNTIME_FIELDS:
        if field in parameter_set and parameter_set[field] is not None:
            candidate[field] = parameter_set[field]

    for field in TACTUS_CLASSIFY_FIELDS:
        if field in parameter_set and parameter_set[field] is not None:
            candidate["code"] = _replace_or_insert_classify_field(
                candidate.get("code") or "",
                field,
                parameter_set[field],
            )


def build_variants(
    yaml_content: str,
    candidate_matrix: Mapping[str, Any],
    *,
    include_current: bool | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic, de-duplicated score YAML variants.

    The normal matrix only mutates score-root model fields. Node-level or other
    targeted edits are allowed only through explicit `extra_overrides` paths.
    """

    base = _load_yaml(yaml_content)
    if not isinstance(base, Mapping):
        raise ValueError("Score YAML must parse to a mapping")

    matrix = _plain_value(candidate_matrix or {})
    if not isinstance(matrix, Mapping):
        raise ValueError("candidate_matrix must be an object or JSON object string")
    models = matrix.get("models") or []
    models = _plain_value(models)
    if not isinstance(models, list) or not models:
        raise ValueError("candidate_matrix.models must be a non-empty array")
    parameter_sets = matrix.get("parameter_sets") or [{"label": "default"}]
    parameter_sets = _plain_value(parameter_sets)
    if not isinstance(parameter_sets, list) or not parameter_sets:
        raise ValueError("candidate_matrix.parameter_sets must be a non-empty array when provided")

    resolved_include_current = matrix.get("include_current", True) if include_current is None else include_current

    variants: list[FrontierVariant] = []
    seen: set[str] = set()

    if resolved_include_current:
        key = _semantic_key(base)
        seen.add(key)
        variants.append(
            FrontierVariant(
                label="current",
                yaml_content=yaml_content,
                is_current=True,
                **_extract_fields(base),
            )
        )

    for model in models:
        model = _plain_value(model)
        if not isinstance(model, Mapping):
            raise ValueError("Each model candidate must be an object")
        for parameter_set in parameter_sets:
            parameter_set = _plain_value(parameter_set)
            if not isinstance(parameter_set, Mapping):
                raise ValueError("Each parameter set must be an object")

            candidate = copy.deepcopy(base)
            if str(candidate.get("class") or "") == "TactusScore":
                _apply_tactus_variant(candidate, model, parameter_set)
            else:
                for field in ("model_provider", "model_name", "base_model_name"):
                    if field in model and model[field] is not None:
                        candidate[field] = model[field]
                if "model_name" in model and "base_model_name" not in model and "base_model_name" in candidate:
                    candidate["base_model_name"] = model["model_name"]
                for field in ("reasoning_effort", "verbosity", "temperature", "max_tokens"):
                    if field in parameter_set and parameter_set[field] is not None:
                        candidate[field] = parameter_set[field]
            extra_overrides = parameter_set.get("extra_overrides") or {}
            extra_overrides = _plain_value(extra_overrides)
            if not isinstance(extra_overrides, Mapping):
                raise ValueError("parameter_set.extra_overrides must be an object when provided")
            for path, value in extra_overrides.items():
                apply_override(candidate, str(path), value)

            key = _semantic_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            variants.append(
                FrontierVariant(
                    label=_variant_label(model, parameter_set),
                    yaml_content=_dump_yaml(candidate),
                    is_current=False,
                    **_extract_fields(candidate),
                )
            )

    return [variant.as_dict() for variant in variants]


def _metric_value(evaluation: Mapping[str, Any] | None, name: str) -> float | None:
    if not evaluation:
        return None
    metrics = evaluation.get("metrics") or []
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except Exception:
            metrics = []
    target = name.lower()
    for metric in metrics or []:
        if not isinstance(metric, Mapping):
            continue
        metric_name = str(metric.get("name") or metric.get("label") or "").lower()
        if target not in metric_name and not (target == "alignment" and "ac1" in metric_name):
            continue
        value = metric.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    for key in (name, name.lower(), "ac1" if name.lower() == "alignment" else None):
        if key and isinstance(evaluation.get(key), (int, float)) and not isinstance(evaluation.get(key), bool):
            return float(evaluation[key])
    return None


def _cost(evaluation: Mapping[str, Any] | None) -> float | None:
    if not evaluation:
        return None
    for key in ("cost", "total_cost", "totalCost"):
        value = evaluation.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
    return None


def _processed(evaluation: Mapping[str, Any] | None) -> int | None:
    if not evaluation:
        return None
    for key in ("processed_items", "processedItems", "total_items", "totalItems"):
        value = evaluation.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def build_result_row(
    variant: Mapping[str, Any],
    *,
    feedback_evaluation: Mapping[str, Any] | None,
    regression_evaluation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    feedback_cost = _cost(feedback_evaluation) or 0.0
    regression_cost = _cost(regression_evaluation) or 0.0
    feedback_items = _processed(feedback_evaluation) or 0
    regression_items = _processed(regression_evaluation) or 0
    total_items = feedback_items + regression_items
    total_cost = feedback_cost + regression_cost
    cost_axis = (total_cost / total_items) if total_items > 0 else None

    return {
        "label": variant.get("label"),
        "is_current": bool(variant.get("is_current")),
        "score_version_id": variant.get("score_version_id") or variant.get("version_id"),
        "model_provider": variant.get("model_provider"),
        "model_name": variant.get("model_name"),
        "base_model_name": variant.get("base_model_name"),
        "reasoning_effort": variant.get("reasoning_effort"),
        "verbosity": variant.get("verbosity"),
        "temperature": variant.get("temperature"),
        "max_tokens": variant.get("max_tokens"),
        "feedback_evaluation_id": (feedback_evaluation or {}).get("evaluation_id") or (feedback_evaluation or {}).get("id"),
        "regression_evaluation_id": (regression_evaluation or {}).get("evaluation_id") or (regression_evaluation or {}).get("id"),
        "feedback_metrics": {
            "alignment": _metric_value(feedback_evaluation, "Alignment"),
            "accuracy": _metric_value(feedback_evaluation, "Accuracy"),
            "precision": _metric_value(feedback_evaluation, "Precision"),
            "recall": _metric_value(feedback_evaluation, "Recall"),
        },
        "regression_metrics": {
            "alignment": _metric_value(regression_evaluation, "Alignment"),
            "accuracy": _metric_value(regression_evaluation, "Accuracy"),
            "precision": _metric_value(regression_evaluation, "Precision"),
            "recall": _metric_value(regression_evaluation, "Recall"),
        },
        "feedback_cost": feedback_cost if feedback_evaluation else None,
        "regression_cost": regression_cost if regression_evaluation else None,
        "total_cost": total_cost if (feedback_evaluation or regression_evaluation) else None,
        "processed_items": total_items,
        "cost_axis": cost_axis,
        "accuracy_axis": _metric_value(feedback_evaluation, "Alignment"),
        "status": "error"
        if (feedback_evaluation or {}).get("error") or (regression_evaluation or {}).get("error")
        else "completed",
        "error": (feedback_evaluation or {}).get("error") or (regression_evaluation or {}).get("error"),
    }


def mark_pareto_frontier(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    materialized = [dict(row) for row in rows]
    for row in materialized:
        row["is_pareto_frontier"] = False
        cost = row.get("cost_axis")
        accuracy = row.get("accuracy_axis")
        if not isinstance(cost, (int, float)) or not isinstance(accuracy, (int, float)):
            continue
        dominated = False
        for other in materialized:
            if other is row:
                continue
            other_cost = other.get("cost_axis")
            other_accuracy = other.get("accuracy_axis")
            if not isinstance(other_cost, (int, float)) or not isinstance(other_accuracy, (int, float)):
                continue
            no_worse = other_cost <= cost and other_accuracy >= accuracy
            strictly_better = other_cost < cost or other_accuracy > accuracy
            if no_worse and strictly_better:
                dominated = True
                break
        row["is_pareto_frontier"] = not dominated
    return materialized


def render_artifacts(rows: Iterable[Mapping[str, Any]], *, title: str = "Model Performance Frontier") -> dict[str, str]:
    rows_with_frontier = mark_pareto_frontier(rows)
    json_payload = json.dumps({"title": title, "rows": rows_with_frontier}, indent=2, sort_keys=True, default=str)

    csv_stream = io.StringIO()
    fieldnames = [
        "label",
        "model_provider",
        "model_name",
        "base_model_name",
        "reasoning_effort",
        "verbosity",
        "temperature",
        "max_tokens",
        "accuracy_axis",
        "cost_axis",
        "total_cost",
        "processed_items",
        "is_current",
        "is_pareto_frontier",
        "feedback_evaluation_id",
        "regression_evaluation_id",
        "score_version_id",
        "status",
    ]
    writer = csv.DictWriter(csv_stream, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows_with_frontier:
        writer.writerow(row)

    points = []
    finite_rows = [
        row for row in rows_with_frontier
        if isinstance(row.get("cost_axis"), (int, float))
        and isinstance(row.get("accuracy_axis"), (int, float))
        and row["cost_axis"] > 0
    ]
    min_cost = min((row["cost_axis"] for row in finite_rows), default=0.000001)
    max_cost = max((row["cost_axis"] for row in finite_rows), default=1.0)
    min_acc = min((row["accuracy_axis"] for row in finite_rows), default=0.0)
    max_acc = max((row["accuracy_axis"] for row in finite_rows), default=1.0)
    if math.isclose(min_cost, max_cost):
        max_cost = min_cost * 10
    if math.isclose(min_acc, max_acc):
        max_acc = min_acc + 1

    for row in finite_rows:
        log_min = math.log10(min_cost)
        log_max = math.log10(max_cost)
        x = 60 + ((math.log10(row["cost_axis"]) - log_min) / (log_max - log_min)) * 500
        y = 330 - ((row["accuracy_axis"] - min_acc) / (max_acc - min_acc)) * 260
        color = "#2563eb" if row.get("is_pareto_frontier") else "#64748b"
        label = str(row.get("label") or "")
        points.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"><title>{label}</title></circle>'
            f'<text x="{x + 8:.1f}" y="{y + 4:.1f}" font-size="11">{_html_escape(label)}</text>'
        )

    html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>{_html_escape(title)}</title></head>
<body>
<h1>{_html_escape(title)}</h1>
<svg width="640" height="380" role="img" aria-label="{_html_escape(title)}">
  <line x1="60" y1="330" x2="590" y2="330" stroke="#334155"/>
  <line x1="60" y1="40" x2="60" y2="330" stroke="#334155"/>
  <text x="250" y="370" font-size="13">Cost per evaluated item (log scale)</text>
  <text x="12" y="185" font-size="13" transform="rotate(-90 12 185)">Feedback AC1</text>
  {''.join(points)}
</svg>
</body>
</html>
"""

    return {
        "frontier.json": json_payload,
        "frontier.csv": csv_stream.getvalue(),
        "frontier.html": html,
    }


def compact_report_envelope(*, artifact_paths: list[str], rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows_list = list(rows)
    return {
        "status": "ok",
        "output_compacted": True,
        "artifact_count": len(artifact_paths),
        "attached_files": artifact_paths,
        "preview": {
            "row_count": len(rows_list),
            "frontier_count": sum(1 for row in rows_list if row.get("is_pareto_frontier")),
        },
    }


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
