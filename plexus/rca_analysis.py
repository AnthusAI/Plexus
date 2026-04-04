#!/usr/bin/env python3
"""
Shared RCA analysis utilities for score result investigation.

Used by both the feedback evaluation RCA pipeline (Evaluation.py)
and the on-demand plexus_score_result_investigate MCP tool.
"""
import json
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

MISCLASSIFICATION_CATEGORIES = (
    "score_configuration_problem",
    "information_gap",
    "guideline_gap_requires_sme",
    "mechanical_malfunction",
)

MISCLASSIFICATION_EXCLUDED_ANALYSES = (
    "feedback_label_contradictions",
    "label_inconsistency_audit",
)

MISCLASSIFICATION_LABEL_PROVENANCE_SOURCES = (
    "feedback_final_answer_value",
    "score_result_label",
    "imported_example_label",
)

MECHANICAL_SUBTYPES = (
    "missing_labels",
    "runtime_error",
    "parse_or_schema_error",
    "invalid_output_class",
    "unknown_mechanical",
)

PRIMARY_NEXT_ACTIONS = (
    "bug_investigation",
    "data_remediation",
    "sme_guideline_clarification",
    "score_configuration_optimization",
)

MISCLASSIFICATION_CATEGORY_LABELS = {
    "score_configuration_problem": "Score configuration",
    "information_gap": "Information gap",
    "guideline_gap_requires_sme": "SME guideline gap",
    "mechanical_malfunction": "Mechanical malfunction",
}


def _excerpt(text: str, max_chars: int = 500) -> str:
    if not text:
        return ""
    value = str(text).strip()
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}..."


def _normalize_label(value: Any) -> str:
    return str(value or "").strip()


def _parse_iso_timestamp(value: str) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return 0.0


def resolve_final_output_classes_from_yaml_text(score_yaml_configuration: str) -> dict:
    """
    Resolve final output classes from score YAML using the canonical final-output order:
    1) parameters.validation.value.valid_classes
    2) classes[].name
    3) graph[-1].valid_classes
    4) graph[-1].conditions[].output.value
    5) graph[-1].LogicalClassifier.code (Score.Result(value="..."))
    """
    if not isinstance(score_yaml_configuration, str) or not score_yaml_configuration.strip():
        raise ValueError("Score YAML configuration is empty.")

    try:
        parsed = yaml.safe_load(score_yaml_configuration)
    except Exception as exc:
        raise ValueError(f"Score YAML configuration is invalid: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Score YAML configuration must be a mapping.")

    valid_classes: List[str] = []
    seen = set()

    def add_class(raw_value: Any):
        value = _normalize_label(raw_value)
        if not value or value in seen:
            return
        seen.add(value)
        valid_classes.append(value)

    validation_classes = (
        ((parsed.get("parameters") or {}).get("validation") or {}).get("value") or {}
    ).get("valid_classes")
    if isinstance(validation_classes, list):
        for class_name in validation_classes:
            add_class(class_name)
    if valid_classes:
        return {
            "classes": valid_classes,
            "source": "parameters.validation.value.valid_classes",
        }

    classes_section = parsed.get("classes")
    if isinstance(classes_section, list):
        for class_def in classes_section:
            if isinstance(class_def, dict):
                add_class(class_def.get("name"))
    if valid_classes:
        return {
            "classes": valid_classes,
            "source": "classes[].name",
        }

    graph_nodes = parsed.get("graph")
    final_node = graph_nodes[-1] if isinstance(graph_nodes, list) and graph_nodes else None
    if isinstance(final_node, dict):
        node_classes = final_node.get("valid_classes")
        if isinstance(node_classes, list):
            for class_name in node_classes:
                add_class(class_name)
        if valid_classes:
            return {
                "classes": valid_classes,
                "source": "graph[-1].valid_classes",
            }

        node_conditions = final_node.get("conditions")
        if isinstance(node_conditions, list):
            for condition in node_conditions:
                if not isinstance(condition, dict):
                    continue
                output = condition.get("output")
                if not isinstance(output, dict):
                    continue
                add_class(output.get("value"))
        if valid_classes:
            return {
                "classes": valid_classes,
                "source": "graph[-1].conditions[].output.value",
            }

        if final_node.get("class") == "LogicalClassifier":
            code_text = final_node.get("code")
            if isinstance(code_text, str) and code_text.strip():
                for match in re.findall(r'value\s*=\s*["\']([^"\']+)["\']', code_text):
                    add_class(match)
        if valid_classes:
            return {
                "classes": valid_classes,
                "source": "graph[-1].LogicalClassifier.code",
            }

    raise ValueError(
        "No final output classes found in score YAML. Checked: "
        "parameters.validation.value.valid_classes, classes[].name, "
        "graph[-1].valid_classes, graph[-1].conditions[].output.value, "
        "graph[-1].LogicalClassifier.code."
    )


def get_misclassification_item_scope_evidence_contract() -> dict:
    """Return the item-scope evidence contract for misclassification classification."""
    return {
        "available_at_item_scope": [
            "feedback_item_id",
            "item_id",
            "predicted_value",
            "correct_value",
            "score_explanation",
            "edit_comment",
            "initial_comment",
            "final_comment",
            "guidelines_text",
            "score_yaml_configuration",
            "transcript_text",
            "metadata_snapshot",
        ],
        "cannot_infer_at_item_scope": [
            "global_feedback_label_consistency",
            "cross-item_guideline_conflict_rate",
            "systemic_prediction_mode_collapse",
            "organization_policy_change_history",
        ],
    }


def get_misclassification_classifier_output_contract() -> dict:
    """Return the per-item classifier output contract for misclassification analysis."""
    return {
        "required_fields": [
            "primary_category",
            "rationale",
            "confidence",
            "evidence_snippets",
        ],
        "conditional_fields": [
            "mechanical_subtype",
            "mechanical_details",
        ],
        "field_contracts": {
            "primary_category": {
                "type": "enum",
                "allowed_values": list(MISCLASSIFICATION_CATEGORIES),
            },
            "rationale": {
                "type": "string",
                "max_sentences": 3,
            },
            "confidence": {
                "type": "enum",
                "allowed_values": ["high", "medium", "low"],
            },
            "evidence_snippets": {
                "type": "array",
                "min_items": 1,
                "item_schema": {
                    "required_fields": ["source", "quote_or_fact"],
                    "source_allowed_values": [
                        "edit_comment",
                        "score_explanation",
                        "guidelines",
                        "score_yaml",
                        "transcript",
                        "metadata",
                    ],
                },
            },
            "mechanical_subtype": {
                "type": "enum_or_null",
                "allowed_values": list(MECHANICAL_SUBTYPES),
                "presence_rule": "required when primary_category=mechanical_malfunction",
            },
            "mechanical_details": {
                "type": "string_or_null",
                "max_chars": 200,
                "presence_rule": "required when primary_category=mechanical_malfunction",
            },
        },
    }


def get_misclassification_item_context_contract() -> dict:
    """Return the canonical per-item context/provenance contract for classification."""
    return {
        "required_sections": [
            "identifiers",
            "prediction",
            "label_provenance",
            "feedback_context",
            "score_context",
            "item_context",
            "source_availability",
            "audit_metadata",
        ],
        "label_provenance_sources": list(MISCLASSIFICATION_LABEL_PROVENANCE_SOURCES),
        "feedback_context_presence_rule": (
            "feedback_context_present is true when any of edit_comment_excerpt, "
            "initial_comment_excerpt, or final_comment_excerpt is non-empty."
        ),
        "persisted_audit_metadata_required": [
            "identifiers.feedback_item_id",
            "identifiers.item_id",
            "identifiers.score_id",
            "identifiers.scorecard_id",
            "identifiers.score_version_id",
            "label_provenance.source",
            "source_availability",
            "score_context.resolved_final_classes",
            "score_context.class_resolution_source",
        ],
    }


def build_misclassification_item_context(
    *,
    feedback_item_id: str,
    item_id: str,
    score_id: str,
    scorecard_id: str,
    score_version_id: str,
    predicted_value: str,
    correct_value: str,
    score_explanation: str,
    edit_comment: str,
    initial_comment: str,
    final_comment: str,
    score_guidelines_text: str,
    score_yaml_configuration: str,
    scorecard_guidance_text: str,
    transcript_text: str,
    metadata_snapshot: str,
    label_provenance_source: str,
    resolved_final_classes: Optional[List[str]] = None,
    class_resolution_source: str = "",
) -> dict:
    """Build standardized item context/provenance payload for misclassification analysis."""
    if label_provenance_source not in MISCLASSIFICATION_LABEL_PROVENANCE_SOURCES:
        raise ValueError(
            f"Unsupported label_provenance_source '{label_provenance_source}'. "
            f"Allowed values: {MISCLASSIFICATION_LABEL_PROVENANCE_SOURCES}"
        )

    edit_comment_excerpt = _excerpt(edit_comment)
    initial_comment_excerpt = _excerpt(initial_comment)
    final_comment_excerpt = _excerpt(final_comment)
    feedback_context_present = bool(
        edit_comment_excerpt or initial_comment_excerpt or final_comment_excerpt
    )

    return {
        "identifiers": {
            "feedback_item_id": feedback_item_id or "",
            "item_id": item_id or "",
            "score_id": score_id or "",
            "scorecard_id": scorecard_id or "",
            "score_version_id": score_version_id or "",
        },
        "prediction": {
            "predicted_value": predicted_value or "",
            "correct_value": correct_value or "",
            "score_explanation_excerpt": _excerpt(score_explanation, 700),
        },
        "label_provenance": {
            "source": label_provenance_source,
            "feedback_context_present": feedback_context_present,
        },
        "feedback_context": {
            "edit_comment_excerpt": edit_comment_excerpt,
            "initial_comment_excerpt": initial_comment_excerpt,
            "final_comment_excerpt": final_comment_excerpt,
        },
        "score_context": {
            "guidelines_excerpt": _excerpt(score_guidelines_text, 700),
            "score_yaml_excerpt": _excerpt(score_yaml_configuration, 700),
            "scorecard_guidance_excerpt": _excerpt(scorecard_guidance_text, 700),
            "resolved_final_classes": [
                _normalize_label(class_name)
                for class_name in (resolved_final_classes or [])
                if _normalize_label(class_name)
            ],
            "class_resolution_source": _normalize_label(class_resolution_source),
        },
        "item_context": {
            "transcript_excerpt": _excerpt(transcript_text, 700),
            "metadata_snapshot_excerpt": _excerpt(metadata_snapshot, 700),
        },
        "source_availability": {
            "has_score_explanation": bool(score_explanation),
            "has_feedback_comments": feedback_context_present,
            "has_score_guidelines": bool(score_guidelines_text),
            "has_score_yaml_configuration": bool(score_yaml_configuration),
            "has_scorecard_guidance": bool(scorecard_guidance_text),
            "has_transcript_text": bool(transcript_text),
            "has_metadata_snapshot": bool(metadata_snapshot),
        },
        "audit_metadata": {
            "persisted_fields": get_misclassification_item_context_contract()[
                "persisted_audit_metadata_required"
            ]
        },
    }


def classify_misclassification_item(item_context: dict) -> dict:
    """Classify one misclassification using the standardized item context payload."""
    availability = item_context.get("source_availability", {})
    prediction = item_context.get("prediction", {})
    feedback_context = item_context.get("feedback_context", {})
    score_context = item_context.get("score_context", {})

    predicted_value = (prediction.get("predicted_value") or "").strip()
    correct_value = (prediction.get("correct_value") or "").strip()
    score_explanation = (prediction.get("score_explanation_excerpt") or "").strip()
    edit_comment = (feedback_context.get("edit_comment_excerpt") or "").strip()
    final_comment = (feedback_context.get("final_comment_excerpt") or "").strip()
    transcript_excerpt = (item_context.get("item_context", {}).get("transcript_excerpt") or "").strip()

    searchable_feedback = f"{edit_comment}\n{final_comment}".lower()
    searchable_explanation = score_explanation.lower()

    resolved_final_classes = [
        _normalize_label(class_name)
        for class_name in (score_context.get("resolved_final_classes") or [])
        if _normalize_label(class_name)
    ]
    valid_class_set = set(resolved_final_classes)

    evidence = []

    def _add_evidence(source: str, quote_or_fact: str):
        if quote_or_fact:
            evidence.append({
                "source": source,
                "quote_or_fact": _excerpt(quote_or_fact, 260),
            })

    mechanical_subtype = None
    mechanical_details = None

    # Mechanical failures should be detected first and only via strict execution/failure signals.
    if not predicted_value or not correct_value:
        missing_fields = []
        if not predicted_value:
            missing_fields.append("predicted_value")
        if not correct_value:
            missing_fields.append("correct_value")
        mechanical_subtype = "missing_labels"
        mechanical_details = f"missing_fields={','.join(missing_fields)}"
        _add_evidence("score_explanation", score_explanation or "Prediction labels missing.")
    else:
        parse_or_schema_markers = (
            "parser error",
            "parse error",
            "failed to parse",
            "schema validation",
            "schema mismatch",
            "jsondecodeerror",
            "json decode error",
            "validationerror",
            "pydantic validation",
            "output parser",
        )
        runtime_markers = (
            "exception",
            "traceback",
            "timeout",
            "runtime error",
        )

        parse_marker = next(
            (marker for marker in parse_or_schema_markers if marker in searchable_explanation),
            None,
        )
        runtime_marker = next(
            (marker for marker in runtime_markers if marker in searchable_explanation),
            None,
        )

        if parse_marker:
            mechanical_subtype = "parse_or_schema_error"
            mechanical_details = f"marker={parse_marker}"
            _add_evidence("score_explanation", score_explanation)
        elif runtime_marker:
            mechanical_subtype = "runtime_error"
            mechanical_details = f"marker={runtime_marker}"
            _add_evidence("score_explanation", score_explanation)
        elif valid_class_set and predicted_value not in valid_class_set:
            mechanical_subtype = "invalid_output_class"
            mechanical_details = (
                f"predicted_value='{predicted_value}' not_in_resolved_valid_classes={sorted(valid_class_set)}"
            )
            _add_evidence("score_explanation", score_explanation or predicted_value)
            _add_evidence("score_yaml", f"Resolved valid classes: {sorted(valid_class_set)}")

    if mechanical_subtype:
        if mechanical_subtype == "parse_or_schema_error":
            rationale = "Parser/schema failure indicators are present in score execution output."
        elif mechanical_subtype == "invalid_output_class":
            rationale = "Predicted output class is outside the resolved final label set."
        else:
            rationale = "Execution-level failure indicators are present in the score output path."
        return {
            "primary_category": "mechanical_malfunction",
            "rationale": rationale,
            "confidence": "high",
            "mechanical_subtype": mechanical_subtype,
            "mechanical_details": mechanical_details or "mechanical_failure_detected",
            "evidence_snippets": evidence or [{"source": "score_explanation", "quote_or_fact": "Execution failure indicators found."}],
        }

    # Information gap: transcript/metadata insufficiency for correct determination.
    if (
        not availability.get("has_transcript_text")
        or any(
            marker in searchable_feedback
            for marker in (
                "transcript",
                "inaudible",
                "cannot hear",
                "could not hear",
                "redacted",
                "missing audio",
                "not in transcript",
            )
        )
    ):
        _add_evidence("edit_comment", edit_comment or final_comment)
        _add_evidence("transcript", transcript_excerpt or "Transcript context unavailable.")
        return {
            "primary_category": "information_gap",
            "rationale": "Available evidence indicates missing or degraded source information for reliable classification.",
            "confidence": "medium",
            "mechanical_subtype": None,
            "mechanical_details": None,
            "evidence_snippets": evidence or [{"source": "transcript", "quote_or_fact": "Transcript context unavailable or insufficient."}],
        }

    # Guideline gap: comments point to ambiguity/policy decision rather than execution.
    if any(
        marker in searchable_feedback
        for marker in (
            "guideline",
            "unclear",
            "ambiguous",
            "policy",
            "sme",
            "needs clarification",
            "not addressed",
        )
    ) or not availability.get("has_score_guidelines"):
        _add_evidence("edit_comment", edit_comment or final_comment)
        _add_evidence("guidelines", score_context.get("guidelines_excerpt", "Guidelines were unavailable."))
        return {
            "primary_category": "guideline_gap_requires_sme",
            "rationale": "The misclassification appears to depend on rubric ambiguity or missing policy detail.",
            "confidence": "medium",
            "mechanical_subtype": None,
            "mechanical_details": None,
            "evidence_snippets": evidence or [{"source": "guidelines", "quote_or_fact": "Guidelines unavailable or ambiguous for this case."}],
        }

    # Default bucket for model/score logic behavior.
    _add_evidence("score_explanation", score_explanation)
    _add_evidence("score_yaml", score_context.get("score_yaml_excerpt", "Score configuration context available."))
    return {
        "primary_category": "score_configuration_problem",
        "rationale": "Evidence points to score logic/prompt behavior rather than missing information or policy ambiguity.",
        "confidence": "medium",
        "mechanical_subtype": None,
        "mechanical_details": None,
        "evidence_snippets": evidence or [{"source": "score_yaml", "quote_or_fact": "Score configuration is the primary fix surface for this item."}],
    }


def build_misclassification_analysis_summary(
    topics: list,
    *,
    max_category_summary_items: int = 20,
) -> dict:
    """Build structured triage output including topic/category summaries and next-action guidance."""
    max_items_used = max(1, int(max_category_summary_items or 20))
    item_classifications: List[Dict[str, Any]] = []
    category_totals = {category: 0 for category in MISCLASSIFICATION_CATEGORIES}
    mechanical_subtype_totals = {subtype: 0 for subtype in MECHANICAL_SUBTYPES}
    predicted_values: List[str] = []
    missing_transcript_count = 0
    topic_category_breakdown: List[Dict[str, Any]] = []
    topic_hierarchy_rows: List[Dict[str, Any]] = []

    def _sorted_category_counts(category_counts: Dict[str, int]) -> Dict[str, int]:
        return {category: int(category_counts.get(category, 0)) for category in MISCLASSIFICATION_CATEGORIES}

    for topic in topics or []:
        topic_id = topic.get("topic_id")
        topic_label = topic.get("label", "")
        topic_member_count = int(topic.get("member_count") or 0)
        topic_counts = {category: 0 for category in MISCLASSIFICATION_CATEGORIES}

        for ex in topic.get("exemplars", []) or []:
            classification = ex.get("misclassification_classification") or {}
            context = ex.get("misclassification_item_context") or {}
            identifiers = context.get("identifiers", {})
            prediction = context.get("prediction", {})
            availability = context.get("source_availability", {})

            category = classification.get("primary_category")
            if category in category_totals:
                category_totals[category] += 1
                topic_counts[category] += 1

            if not availability.get("has_transcript_text"):
                missing_transcript_count += 1

            predicted_value = _normalize_label(prediction.get("predicted_value"))
            if predicted_value:
                predicted_values.append(predicted_value)

            mechanical_subtype = classification.get("mechanical_subtype")
            if mechanical_subtype in mechanical_subtype_totals:
                mechanical_subtype_totals[mechanical_subtype] += 1

            item_classifications.append({
                "topic_id": topic_id,
                "topic_label": topic_label,
                "feedback_item_id": identifiers.get("feedback_item_id", ""),
                "item_id": identifiers.get("item_id", ""),
                "timestamp": ex.get("timestamp") or "",
                "primary_category": category or "",
                "confidence": classification.get("confidence", ""),
                "rationale": classification.get("rationale", ""),
                "evidence_snippets": classification.get("evidence_snippets", []),
                "mechanical_subtype": mechanical_subtype,
                "mechanical_details": classification.get("mechanical_details"),
            })

        topic_total = sum(topic_counts.values())
        if topic_total > 0:
            majority = max(
                MISCLASSIFICATION_CATEGORIES,
                key=lambda key: (topic_counts.get(key, 0), -MISCLASSIFICATION_CATEGORIES.index(key)),
            )
            purity = topic_counts.get(majority, 0) / topic_total
        else:
            majority = ""
            purity = 0.0
        topic_category_breakdown.append({
            "topic_id": topic_id,
            "topic_label": topic_label,
            "member_count": topic_member_count or topic_total,
            "category_counts": _sorted_category_counts(topic_counts),
            "topic_primary_category": majority,
            "topic_category_purity": round(purity, 4),
        })
        topic_hierarchy_rows.append({
            "topic_id": topic_id,
            "topic_label": topic_label,
            "member_count": topic_member_count or topic_total,
            "category_counts": _sorted_category_counts(topic_counts),
            "topic_primary_category": majority,
            "topic_category_purity": round(purity, 4),
            "topic_payload": topic,
        })

    total_items = len(item_classifications)
    category_shares = {
        category: (category_totals[category] / total_items if total_items else 0.0)
        for category in MISCLASSIFICATION_CATEGORIES
    }

    red_flags = []
    if total_items >= 3 and len(set(predicted_values)) == 1 and predicted_values:
        red_flags.append({
            "flag": "prediction_mode_collapse",
            "severity": "high",
            "message": (
                "All analyzed misclassifications share the same predicted class, "
                "suggesting potential classifier collapse."
            ),
        })

    mechanical_count = category_totals.get("mechanical_malfunction", 0)
    if mechanical_count > 0:
        has_runtime_like = (
            mechanical_subtype_totals.get("runtime_error", 0) > 0
            or mechanical_subtype_totals.get("parse_or_schema_error", 0) > 0
            or mechanical_subtype_totals.get("missing_labels", 0) > 0
        )
        red_flags.append({
            "flag": "mechanical_failures_present",
            "severity": "high" if has_runtime_like or category_shares["mechanical_malfunction"] >= 0.5 else "medium",
            "message": f"{mechanical_count} item(s) classified as mechanical malfunction.",
        })
    if mechanical_subtype_totals.get("invalid_output_class", 0) > 0:
        red_flags.append({
            "flag": "invalid_output_class_present",
            "severity": "high",
            "message": (
                f"{mechanical_subtype_totals['invalid_output_class']} item(s) produced "
                "an output class outside the resolved valid class set."
            ),
        })

    if total_items > 0 and (missing_transcript_count / total_items) >= 0.5:
        red_flags.append({
            "flag": "low_transcript_coverage",
            "severity": "medium",
            "message": "At least half of analyzed items were missing transcript context.",
        })

    def _sort_items_for_summary(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            items,
            key=lambda item: (
                -_parse_iso_timestamp(item.get("timestamp", "")),
                str(item.get("feedback_item_id") or item.get("item_id") or ""),
            ),
        )

    def _collect_representative_evidence(items: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
        evidence_rows = []
        seen_quotes = set()
        for item in items:
            snippets = item.get("evidence_snippets") or []
            for snippet in snippets:
                quote = _normalize_label((snippet or {}).get("quote_or_fact"))
                source = _normalize_label((snippet or {}).get("source"))
                if not quote or quote in seen_quotes:
                    continue
                seen_quotes.add(quote)
                evidence_rows.append({
                    "feedback_item_id": item.get("feedback_item_id", ""),
                    "item_id": item.get("item_id", ""),
                    "source": source,
                    "quote_or_fact": _excerpt(quote, 220),
                })
                break
            if len(evidence_rows) >= limit:
                break
        return evidence_rows

    def _build_top_patterns(category: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pattern_counter = Counter()
        for item in items:
            if category == "mechanical_malfunction":
                key = _normalize_label(item.get("mechanical_subtype")) or "unknown_mechanical"
            else:
                rationale = _normalize_label(item.get("rationale"))
                key = rationale.split(".", 1)[0].strip().lower() if rationale else "unspecified_pattern"
            pattern_counter[key] += 1
        top = []
        for pattern, count in pattern_counter.most_common(3):
            top.append({"pattern": pattern, "count": int(count)})
        return top

    category_summaries = {}
    category_hierarchy = []
    for category in MISCLASSIFICATION_CATEGORIES:
        items_in_category = _sort_items_for_summary(
            [item for item in item_classifications if item.get("primary_category") == category]
        )
        sampled_items = items_in_category[:max_items_used]
        top_patterns = _build_top_patterns(category, sampled_items)
        representative_evidence = _collect_representative_evidence(sampled_items)
        item_count = len(items_in_category)
        if category == "mechanical_malfunction":
            subtype_rows = [
                f"{subtype}:{mechanical_subtype_totals.get(subtype, 0)}"
                for subtype in MECHANICAL_SUBTYPES
                if mechanical_subtype_totals.get(subtype, 0) > 0
            ]
            summary_text = (
                f"{item_count} item(s) classified as mechanical malfunction. "
                f"Subtype totals: {', '.join(subtype_rows) if subtype_rows else 'none'}."
            )
        else:
            summary_text = (
                f"{item_count} item(s) classified as {category.replace('_', ' ')}. "
                f"Top recurring patterns: "
                f"{', '.join(pattern['pattern'] for pattern in top_patterns) if top_patterns else 'none'}."
            )
        category_summaries[category] = {
            "category_summary_text": summary_text,
            "top_patterns": top_patterns,
            "representative_evidence": representative_evidence,
            "item_count": item_count,
        }

        category_topics = []
        for topic_row in sorted(
            [row for row in topic_hierarchy_rows if row.get("topic_primary_category") == category],
            key=lambda row: (
                -(row.get("member_count") or 0),
                str(row.get("topic_label") or ""),
            ),
        ):
            topic_payload = topic_row.get("topic_payload") or {}
            exemplars = topic_payload.get("exemplars") or []
            topic_examples = []
            for ex in exemplars:
                if not isinstance(ex, dict):
                    continue
                classification = ex.get("misclassification_classification") or {}
                topic_examples.append({
                    "feedback_item_id": (
                        ex.get("feedback_item_id")
                        or (ex.get("misclassification_item_context") or {}).get("identifiers", {}).get("feedback_item_id")
                        or ""
                    ),
                    "item_id": (
                        ex.get("item_id")
                        or (ex.get("misclassification_item_context") or {}).get("identifiers", {}).get("item_id")
                        or ""
                    ),
                    "identifiers": ex.get("identifiers") or [],
                    "text": ex.get("text", ""),
                    "timestamp": ex.get("timestamp", ""),
                    "initial_answer_value": ex.get("initial_answer_value"),
                    "final_answer_value": ex.get("final_answer_value"),
                    "score_explanation": ex.get("score_explanation"),
                    "detailed_cause": ex.get("detailed_cause"),
                    "suggested_fix": ex.get("suggested_fix"),
                    "misclassification_classification": classification,
                    "mechanical_subtype": classification.get("mechanical_subtype"),
                    "mechanical_details": classification.get("mechanical_details"),
                })

            category_topics.append({
                "topic_id": topic_row.get("topic_id"),
                "label": topic_row.get("topic_label", ""),
                "member_count": topic_row.get("member_count", 0),
                "topic_category_purity": topic_row.get("topic_category_purity", 0.0),
                "category_counts": topic_row.get("category_counts", {}),
                "detailed_explanation": topic_payload.get("detailed_explanation"),
                "improvement_suggestion": topic_payload.get("improvement_suggestion"),
                "score_fix_candidate_count": topic_payload.get("score_fix_candidate_count"),
                "examples": topic_examples,
            })

        category_hierarchy.append({
            "category_key": category,
            "category_label": MISCLASSIFICATION_CATEGORY_LABELS.get(
                category, category.replace("_", " ")
            ),
            "item_count": item_count,
            "share": round(category_shares.get(category, 0.0), 4),
            "summary_text": summary_text,
            "top_patterns": top_patterns,
            "mechanical_subtype_totals": (
                {
                    subtype: int(mechanical_subtype_totals.get(subtype, 0))
                    for subtype in MECHANICAL_SUBTYPES
                    if mechanical_subtype_totals.get(subtype, 0) > 0
                }
                if category == "mechanical_malfunction"
                else {}
            ),
            "topics": category_topics,
        })

    high_severity_mechanical_flag = any(
        flag.get("severity") == "high"
        and flag.get("flag") in {"mechanical_failures_present", "invalid_output_class_present"}
        for flag in red_flags
    )

    reasons = []
    if high_severity_mechanical_flag or category_shares["mechanical_malfunction"] >= 0.5:
        primary_next_action_key = "bug_investigation"
        reasons.append("Mechanical malfunction indicators dominate or include high-severity failures.")
    elif category_shares["information_gap"] >= 0.5:
        primary_next_action_key = "data_remediation"
        reasons.append("Information-gap share is at least 50% of misclassifications.")
    elif (
        category_shares["guideline_gap_requires_sme"] >= 0.35
        and category_shares["score_configuration_problem"] < 0.35
    ):
        primary_next_action_key = "sme_guideline_clarification"
        reasons.append("Guideline-gap share is high while score-configuration share is low.")
    else:
        primary_next_action_key = "score_configuration_optimization"
        reasons.append("Score-configuration problems remain the most actionable fix surface.")

    if primary_next_action_key == "bug_investigation":
        next_action_confidence = "high"
        optimization_applicability = {
            "status": "blocked",
            "reason": "Mechanical malfunction signals indicate execution reliability issues that should be fixed first.",
        }
    elif primary_next_action_key in {"data_remediation", "sme_guideline_clarification"}:
        next_action_confidence = "medium"
        optimization_applicability = {
            "status": "limited",
            "reason": "Score-configuration changes may help partially, but dominant issues are outside pure score logic.",
        }
    else:
        next_action_confidence = "medium"
        optimization_applicability = {
            "status": "applicable",
            "reason": "Misclassification mix supports direct score-configuration optimization.",
        }

    predominant_category = ""
    if total_items > 0:
        predominant_category = max(
            MISCLASSIFICATION_CATEGORIES,
            key=lambda key: (category_totals[key], -MISCLASSIFICATION_CATEGORIES.index(key)),
        )

    return {
        "pipeline_stage_order": [
            "item_classification",
            "topic_modeling",
            "topic_category_assignment",
            "category_recursive_summarization",
            "evaluation_red_flags",
            "final_recommendation",
        ],
        "item_classifications": item_classifications,
        "topic_category_breakdown": topic_category_breakdown,
        "category_hierarchy": category_hierarchy,
        "category_totals": category_totals,
        "category_shares": {k: round(v, 4) for k, v in category_shares.items()},
        "category_summaries": category_summaries,
        "mechanical_subtype_totals": mechanical_subtype_totals,
        "primary_next_action": {
            "action": primary_next_action_key,
            "confidence": next_action_confidence,
            "reasons": reasons,
        },
        "optimization_applicability": optimization_applicability,
        "max_category_summary_items_used": max_items_used,
        "overall_assessment": {
            "total_items": total_items,
            "predominant_category": predominant_category,
            "score_fix_candidate_items": category_totals.get("score_configuration_problem", 0),
        },
        "evaluation_red_flags": red_flags,
    }


def build_misclassification_classification_contract() -> dict:
    """Build the full operator-facing misclassification taxonomy/evidence contract."""
    return {
        "categories": list(MISCLASSIFICATION_CATEGORIES),
        "mechanical_subtypes": list(MECHANICAL_SUBTYPES),
        "primary_next_actions": list(PRIMARY_NEXT_ACTIONS),
        "excluded_analyses": list(MISCLASSIFICATION_EXCLUDED_ANALYSES),
        "item_scope_evidence": get_misclassification_item_scope_evidence_contract(),
        "item_classifier_output": get_misclassification_classifier_output_contract(),
        "item_context_contract": get_misclassification_item_context_contract(),
    }


def analyze_score_result(
    transcript: str,
    predicted: str,
    correct: str,
    explanation: str,
    topic_label: str = "Score result investigation",
    score_guidelines: str = "",
    score_yaml_code: str = "",
    feedback_context: str = "",
) -> tuple:
    """
    Run a two-turn Bedrock Haiku conversation to analyze a misclassification.

    Returns (detailed_cause, suggested_fix):
      - detailed_cause: why the AI prediction was wrong (2-4 sentences)
      - suggested_fix: one concrete score code change to prevent this error

    Args:
        transcript: Call transcript text
        predicted: The AI's predicted value
        correct: The correct/human-labeled value
        explanation: The AI's reasoning for its prediction
        topic_label: Topic or cluster context label
        score_guidelines: Score guidelines text (truncated to 2000 chars)
        score_yaml_code: Score YAML configuration (truncated to 4000 chars)
        feedback_context: Additional context about reviewer feedback
    """
    import boto3

    system = (
        "You are an expert quality analyst reviewing AI scoring errors on customer calls."
    )

    turn1_prompt = (
        f"Topic context: {topic_label}\n"
        f"AI predicted: {predicted}\n"
        f"Correct answer: {correct}\n"
        f"AI reasoning: {(explanation or '')[:400]}\n"
    )
    if feedback_context:
        turn1_prompt += f"{feedback_context}\n"
    turn1_prompt += "\n"
    if score_guidelines:
        turn1_prompt += f"Score guidelines:\n{score_guidelines[:2000]}\n\n"
    if score_yaml_code:
        turn1_prompt += f"Score configuration:\n```yaml\n{score_yaml_code[:4000]}\n```\n\n"
    turn1_prompt += (
        f"Call transcript:\n{transcript[:6000]}\n\n"
        "Write a single concise paragraph (2-4 sentences) explaining specifically why "
        "the AI prediction was wrong. Focus on what was said or not said in the "
        "transcript that makes the correct answer clear."
    )

    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")

        def _haiku_call(messages: list, max_tokens: int) -> str:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
            })
            resp = client.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            return json.loads(resp["body"].read())["content"][0]["text"].strip()

        messages = [{"role": "user", "content": turn1_prompt}]
        detailed_cause = _haiku_call(messages, max_tokens=200)

        messages.append({"role": "assistant", "content": detailed_cause})
        messages.append({"role": "user", "content": (
            "Based on this specific error and the score configuration above, "
            "suggest one concrete change to the score code that would prevent "
            "this specific misclassification. Be specific and brief (1-2 sentences)."
        )})
        suggested_fix = _haiku_call(messages, max_tokens=150)

        return detailed_cause, suggested_fix
    except Exception as exc:
        logger.warning("analyze_score_result failed: %s", exc)
        return "", ""


def build_feedback_context(
    feedback_comment: str = "",
    feedback_initial: str = "",
    feedback_final: str = "",
    predicted_value: str = "",
) -> str:
    """
    Build a feedback context string for the analysis prompt that handles
    the confusing case where a reviewer "agreed" with the production result
    but the evaluation produced a different result.

    Returns a string to include in the analysis prompt.
    """
    parts = []
    if feedback_comment:
        parts.append(f"Reviewer comment: {feedback_comment[:300]}")
    if feedback_initial and feedback_initial != feedback_final:
        parts.append(f"Original production value: {feedback_initial}")
        parts.append(f"Reviewer corrected to: {feedback_final}")
    elif feedback_initial and feedback_initial == feedback_final:
        parts.append(
            f"Note: Reviewer AGREED with original production value '{feedback_initial}'. "
            f"The evaluation produced '{predicted_value}' which differs from the agreed-upon "
            f"correct value '{feedback_final}'. The reviewer comment may refer to the original "
            f"production result, not the evaluation result."
        )
    return "\n".join(parts)
