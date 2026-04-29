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

from plexus.rubric_memory import validate_rubric_memory_citations
import yaml

logger = logging.getLogger(__name__)

RCA_OPENAI_MODEL = "gpt-5-mini"
RCA_OPENAI_REASONING_EFFORT = "low"
RCA_MIN_OUTPUT_TOKENS = 1000


def _invoke_rca_openai_text(
    *,
    system: str,
    messages: list[dict[str, str]],
    max_output_tokens: int,
    call_site: str = "rca_openai_text",
) -> str:
    """Invoke the RCA standard OpenAI model and return plain response text."""
    from dotenv import load_dotenv
    from openai import OpenAI
    from plexus.cli.procedure.logging_utils import capture_llm_context_for_agent

    load_dotenv(override=False)
    client = OpenAI()
    current_messages = list(messages)
    last_empty = False
    for attempt in range(2):
        capture_llm_context_for_agent(
            "RCA",
            [{"role": "system", "content": system}, *current_messages],
            call_site=call_site if attempt == 0 else f"{call_site}_retry_empty",
        )
        response = client.responses.create(
            model=RCA_OPENAI_MODEL,
            instructions=system,
            input=current_messages,
            reasoning={"effort": RCA_OPENAI_REASONING_EFFORT},
            # GPT-5 output tokens include reasoning tokens. RCA prompts need a
            # small visible schema, but too-small budgets can be exhausted by
            # reasoning before any output_text is emitted.
            max_output_tokens=max(max_output_tokens, RCA_MIN_OUTPUT_TOKENS),
        )
        text = (getattr(response, "output_text", "") or "").strip()
        if text:
            return text
        last_empty = True
        current_messages = [
            *current_messages,
            {
                "role": "user",
                "content": (
                    "Your previous response was empty. Return the requested "
                    "structured text exactly in the specified format."
                ),
            },
        ]
    if last_empty:
        raise ValueError(f"{RCA_OPENAI_MODEL} returned an empty response")
    raise ValueError(f"{RCA_OPENAI_MODEL} returned no usable response")


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
    "missing_required_context",
    "runtime_error",
    "parse_or_schema_error",
    "invalid_output_class",
    "rca_analysis_failure",
    "unknown_mechanical",
)

PRIMARY_INPUT_MODALITIES = (
    "text",
    "audio",
    "image",
    "video",
    "structured",
    "mixed",
    "unknown",
)

CONFIG_FIXABILITY_OPTIONS = (
    "likely_fixable",
    "blocked_by_input",
    "blocked_by_mechanical",
    "needs_sme_clarification",
)

MISCLASSIFICATION_EVIDENCE_FLAG_KEYS = (
    "external_information_missing_or_degraded",
    "guideline_or_policy_ambiguity",
    "missing_required_context_due_system",
    "runtime_or_parsing_failure",
    "invalid_output_class_signal",
    "preprocessing_evidence_loss",
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


def _excerpt(text: str, max_chars: int = 50000) -> str:
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
        # YAML parses Yes/No/True/False as booleans; convert back to strings
        if isinstance(raw_value, bool):
            raw_value = "Yes" if raw_value else "No"
        value = _normalize_label(raw_value)
        if not value or value in seen:
            return
        seen.add(value)
        valid_classes.append(value)

    # Check top-level valid_classes (used by TactusScore YAML format)
    top_level_classes = parsed.get("valid_classes")
    if isinstance(top_level_classes, list):
        for class_name in top_level_classes:
            add_class(class_name)
    if valid_classes:
        return {
            "classes": valid_classes,
            "source": "valid_classes",
        }

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
            "primary_input_text",
            "primary_input_modality",
            "metadata_snapshot",
            "rubric_memory_citation_context",
        ],
        "cannot_infer_at_item_scope": [
            "global_feedback_label_consistency",
            "cross-item_guideline_conflict_rate",
            "systemic_prediction_mode_collapse",
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
            "evidence_flags",
            "rationale_paragraph",
            "evidence_quote",
            "config_fixability",
            "citation_ids",
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
                        "primary_input",
                        "metadata",
                        "rubric_memory",
                    ],
                },
            },
            "evidence_flags": {
                "type": "object",
                "required_fields": list(MISCLASSIFICATION_EVIDENCE_FLAG_KEYS),
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
            "rationale_paragraph": {
                "type": "string",
                "max_sentences": 5,
                "description": "Short explanatory paragraph grounded in item evidence.",
            },
            "evidence_quote": {
                "type": "string",
                "max_chars": 260,
                "description": "Single strongest quote/fact supporting the category decision.",
            },
            "config_fixability": {
                "type": "enum",
                "allowed_values": list(CONFIG_FIXABILITY_OPTIONS),
            },
            "citation_ids": {
                "type": "array",
                "description": "Rubric-memory citation IDs used by the classification, when supplied.",
            },
        },
    }


def get_misclassification_explainer_output_contract() -> dict:
    """Return contract for per-item triage explainer output."""
    return {
        "required_fields": [
            "rationale_paragraph",
            "evidence_quote",
            "config_fixability",
            "citation_ids",
        ],
        "field_contracts": {
            "rationale_paragraph": {
                "type": "string",
                "max_sentences": 5,
            },
            "evidence_quote": {
                "type": "string",
                "max_chars": 260,
            },
            "config_fixability": {
                "type": "enum",
                "allowed_values": list(CONFIG_FIXABILITY_OPTIONS),
            },
            "citation_ids": {
                "type": "array",
                "description": "Rubric-memory citation IDs used by the explanation, when supplied.",
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
            "rubric_memory",
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
            "item_context.primary_input_modality",
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
    primary_input_text: str,
    primary_input_modality: str,
    metadata_snapshot: str,
    label_provenance_source: str,
    resolved_final_classes: Optional[List[str]] = None,
    class_resolution_source: str = "",
    primary_input_fetch_error: bool = False,
    missing_required_context_keys: Optional[List[str]] = None,
    processed_input_text: str = "",
    processors_config_summary: str = "",
    rubric_memory_context: Optional[Dict[str, Any]] = None,
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
    normalized_modality = _normalize_label(primary_input_modality).lower() or "unknown"
    if normalized_modality not in PRIMARY_INPUT_MODALITIES:
        normalized_modality = "unknown"
    normalized_missing_context_keys = [
        _normalize_label(value)
        for value in (missing_required_context_keys or [])
        if _normalize_label(value)
    ]
    preprocessing_changed_input = bool(
        processed_input_text
        and primary_input_text
        and processed_input_text.strip() != primary_input_text.strip()
    )
    citation_index = []
    if isinstance(rubric_memory_context, dict):
        citation_index = (
            rubric_memory_context.get("citation_index")
            or rubric_memory_context.get("citations")
            or rubric_memory_context.get("machine_context", {}).get("citation_index")
            or []
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
            "score_explanation": _excerpt(score_explanation),
        },
        "label_provenance": {
            "source": label_provenance_source,
            "feedback_context_present": feedback_context_present,
        },
        "feedback_context": {
            "edit_comment": edit_comment_excerpt,
            "initial_comment": initial_comment_excerpt,
            "final_comment": final_comment_excerpt,
        },
        "score_context": {
            "guidelines": _excerpt(score_guidelines_text),
            "score_yaml_configuration": _excerpt(score_yaml_configuration),
            "scorecard_guidance": _excerpt(scorecard_guidance_text),
            "resolved_final_classes": [
                _normalize_label(class_name)
                for class_name in (resolved_final_classes or [])
                if _normalize_label(class_name)
            ],
            "class_resolution_source": _normalize_label(class_resolution_source),
        },
        "item_context": {
            "raw_input_text": _excerpt(primary_input_text),
            "raw_input_text_description": (
                "The ORIGINAL input text before any preprocessing. "
                "Compare against processed_input_text to see what the "
                "preprocessor pipeline removed or changed."
            ),
            "processed_input_text": _excerpt(processed_input_text) if processed_input_text else "",
            "processed_input_text_description": (
                "The text AFTER the preprocessor pipeline ran — this is what the "
                "classification LLM actually saw. If critical evidence exists in "
                "raw_input_text but NOT here, the preprocessor removed it. "
                "That would be a score_configuration_problem in the preprocessing config."
                if processed_input_text else
                "No preprocessor pipeline was applied (or processed text unavailable). "
                "The LLM saw the raw input text directly."
            ),
            "processors_applied": processors_config_summary or "none",
            "preprocessing_changed_input": preprocessing_changed_input,
            "primary_input_modality": normalized_modality,
            "metadata_snapshot": _excerpt(metadata_snapshot),
        },
        "source_availability": {
            "has_score_explanation": bool(score_explanation),
            "has_feedback_comments": feedback_context_present,
            "has_score_guidelines": bool(score_guidelines_text),
            "has_score_yaml_configuration": bool(score_yaml_configuration),
            "has_scorecard_guidance": bool(scorecard_guidance_text),
            "has_primary_input": bool(primary_input_text),
            "has_processed_input": bool(processed_input_text),
            "has_metadata_snapshot": bool(metadata_snapshot),
            "primary_input_fetch_error": bool(primary_input_fetch_error),
            "missing_required_context_keys": normalized_missing_context_keys,
            "has_rubric_memory": bool(citation_index),
        },
        "rubric_memory": rubric_memory_context or {},
        "audit_metadata": {
            "persisted_fields": get_misclassification_item_context_contract()[
                "persisted_audit_metadata_required"
            ]
        },
    }


def _compact_context_for_triage(item_context: dict) -> dict:
    """Build a compact version of item context for the evidence-flag triage call.

    Evidence extraction only needs key triage signals — not the full transcript,
    full YAML, or full guidelines (which can be 50KB+ combined and would inflate
    the Bedrock request to an unmanageable size). The explanation call gets the
    full context via explain_misclassification_item_classification().
    """
    pred = item_context.get("prediction", {})
    fb = item_context.get("feedback_context", {})
    sc = item_context.get("score_context", {})
    ic = item_context.get("item_context", {})
    avail = item_context.get("source_availability", {})
    rubric_memory = item_context.get("rubric_memory", {}) or {}
    citation_index = rubric_memory.get("citation_index") or []
    return {
        "identifiers": item_context.get("identifiers", {}),
        "prediction": {
            "predicted_value": pred.get("predicted_value", ""),
            "correct_value": pred.get("correct_value", ""),
            # First 800 chars of explanation — enough to detect mechanical failures
            "score_explanation": _excerpt(pred.get("score_explanation", ""), 800),
        },
        "label_provenance": item_context.get("label_provenance", {}),
        "feedback_context": {
            # Full feedback comments — these are the most important triage signals
            "edit_comment": fb.get("edit_comment", ""),
            "initial_comment": fb.get("initial_comment", ""),
            "final_comment": fb.get("final_comment", ""),
        },
        "score_context": {
            # Short excerpts — enough to check if guidelines exist and spot ambiguity
            "guidelines": _excerpt(sc.get("guidelines", ""), 1200),
            "score_yaml_configuration": _excerpt(sc.get("score_yaml_configuration", ""), 800),
            "scorecard_guidance": _excerpt(sc.get("scorecard_guidance", ""), 400),
            "resolved_final_classes": sc.get("resolved_final_classes", []),
            "class_resolution_source": sc.get("class_resolution_source", ""),
        },
        "item_context": {
            # Key preprocessing comparison — truncated but enough to detect evidence loss
            "raw_input_text": _excerpt(ic.get("raw_input_text", ""), 1500),
            "raw_input_text_description": ic.get("raw_input_text_description", ""),
            "processed_input_text": _excerpt(ic.get("processed_input_text", ""), 1500),
            "processed_input_text_description": ic.get("processed_input_text_description", ""),
            "processors_applied": ic.get("processors_applied", "none"),
            "preprocessing_changed_input": ic.get("preprocessing_changed_input", False),
            "primary_input_modality": ic.get("primary_input_modality", "unknown"),
            "metadata_snapshot": _excerpt(ic.get("metadata_snapshot", ""), 400),
        },
        "rubric_memory": {
            "available": bool(citation_index),
            "markdown_context": _excerpt(rubric_memory.get("markdown_context", ""), 2400),
            "citation_index": citation_index[:12],
            "diagnostics": (rubric_memory.get("diagnostics") or [])[:5],
        },
        "source_availability": avail,
    }


def extract_misclassification_evidence_flags(
    *,
    item_context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract item-level triage evidence flags from full context (including feedback comments).

    The returned flags are inputs to deterministic category assignment.
    """
    system = (
        "You extract evidence flags for misclassification triage. "
        "Focus on explicit evidence in the provided context. "
        "Use modality-agnostic language."
    )
    rca_cookbook = (
        "Common root causes to check for:\n"
        "1. PREPROCESSING_EVIDENCE_LOSS: A preprocessor (e.g., RelevantWindowsTranscriptFilter) "
        "removed transcript lines containing the evidence needed for correct classification. "
        "Check: Does raw_input_text contain evidence supporting the correct answer that is "
        "absent from processed_input_text? If preprocessing_changed_input is true, compare carefully.\n"
        "2. PHONETIC_TRANSCRIPTION_ERROR: Speech-to-text mangled a proper noun (school name, "
        "product name, acronym) into a phonetically similar common word. The LLM couldn't "
        "match it to the expected term.\n"
        "3. KEYWORD_GAP: A RelevantWindowsTranscriptFilter is configured with keywords that "
        "don't cover a synonym or variant used in this transcript. Relevant content was "
        "filtered out because the keyword list was incomplete.\n"
        "4. TEMPORAL_ORDERING_LOSS: The transcript format (sentences/paragraphs) collapsed "
        "word-level timing. The LLM couldn't determine which response followed which prompt.\n"
        "5. SPEAKER_FILTER_ERROR: A speaker filter removed the wrong speaker's lines, or "
        "speaker channels were swapped.\n"
        "6. GUIDELINE_PROMPT_MISMATCH: Classification guidelines describe a policy not "
        "reflected in the LLM prompts (system_message/user_message).\n"
        "7. AMBIGUOUS_BOUNDARY: The item genuinely sits on the classification boundary and "
        "the guidelines don't clearly define which class applies to this specific pattern.\n"
    )
    prompt = (
        "Return exactly eight lines in this exact format:\n"
        "FLAG_EXTERNAL_INFORMATION_GAP: <true|false>\n"
        "FLAG_GUIDELINE_GAP: <true|false>\n"
        "FLAG_SYSTEM_MISSING_CONTEXT: <true|false>\n"
        "FLAG_RUNTIME_OR_PARSER_FAILURE: <true|false>\n"
        "FLAG_INVALID_OUTPUT_CLASS: <true|false>\n"
        "FLAG_PREPROCESSING_EVIDENCE_LOSS: <true|false>\n"
        "BEST_EVIDENCE_SOURCE: <edit_comment|score_explanation|guidelines|score_yaml|primary_input|processed_input|metadata|rubric_memory|none>\n"
        "BEST_EVIDENCE_QUOTE: <short supporting quote/fact>\n\n"
        "Interpretation rules:\n"
        "- EXTERNAL_INFORMATION_GAP=true only when evidence says source evidence is degraded/insufficient externally "
        "(e.g., transcription omissions, redaction, inaudible sections).\n"
        "- GUIDELINE_GAP=true when feedback indicates rubric/policy ambiguity or missing policy detail.\n"
        "- SYSTEM_MISSING_CONTEXT=true when required input/context appears missing due system/pipeline/contract issues "
        "(including missing metadata fields).\n"
        "- RUNTIME_OR_PARSER_FAILURE=true only for explicit runtime/parser/schema failures.\n"
        "- INVALID_OUTPUT_CLASS=true only when output class appears invalid/out-of-schema.\n"
        "- PREPROCESSING_EVIDENCE_LOSS=true when item_context.preprocessing_changed_input is true AND "
        "the raw_input_text contains evidence relevant to the correct classification that is absent "
        "from processed_input_text. This means the preprocessor pipeline removed critical evidence. "
        "If preprocessing_changed_input is false or processed_input_text is empty, set this to false.\n"
        "- If multiple flags could apply, set all that are supported by explicit evidence.\n\n"
        f"{rca_cookbook}\n"
        f"Item context JSON:\n{json.dumps(_compact_context_for_triage(item_context), ensure_ascii=True)}\n"
    )

    def _parse_flag_text(text: str) -> Dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Invalid evidence flag output: empty response")

        kv: Dict[str, str] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            kv[key.strip().upper()] = value.strip()

        required = (
            "FLAG_EXTERNAL_INFORMATION_GAP",
            "FLAG_GUIDELINE_GAP",
            "FLAG_SYSTEM_MISSING_CONTEXT",
            "FLAG_RUNTIME_OR_PARSER_FAILURE",
            "FLAG_INVALID_OUTPUT_CLASS",
            "FLAG_PREPROCESSING_EVIDENCE_LOSS",
            "BEST_EVIDENCE_SOURCE",
            "BEST_EVIDENCE_QUOTE",
        )
        missing = [key for key in required if key not in kv]
        if missing:
            raise ValueError(
                f"Invalid evidence flag output: missing keys {missing}. Raw output: {text[:500]}"
            )

        def _parse_bool(value: str, key: str) -> bool:
            low = str(value or "").strip().lower()
            if low in {"true", "yes"}:
                return True
            if low in {"false", "no"}:
                return False
            raise ValueError(f"Invalid boolean for {key}: {value}")

        raw_source = _normalize_label(kv["BEST_EVIDENCE_SOURCE"]).lower()
        source = normalize_best_evidence_source(raw_source)
        allowed_sources = {
            "edit_comment",
            "score_explanation",
            "guidelines",
            "score_yaml",
            "primary_input",
            "processed_input",
            "metadata",
            "rubric_memory",
            "none",
        }
        if source not in allowed_sources:
            raise ValueError(f"Invalid BEST_EVIDENCE_SOURCE: {raw_source}")

        return {
            "external_information_missing_or_degraded": _parse_bool(
                kv["FLAG_EXTERNAL_INFORMATION_GAP"],
                "FLAG_EXTERNAL_INFORMATION_GAP",
            ),
            "guideline_or_policy_ambiguity": _parse_bool(
                kv["FLAG_GUIDELINE_GAP"],
                "FLAG_GUIDELINE_GAP",
            ),
            "missing_required_context_due_system": _parse_bool(
                kv["FLAG_SYSTEM_MISSING_CONTEXT"],
                "FLAG_SYSTEM_MISSING_CONTEXT",
            ),
            "runtime_or_parsing_failure": _parse_bool(
                kv["FLAG_RUNTIME_OR_PARSER_FAILURE"],
                "FLAG_RUNTIME_OR_PARSER_FAILURE",
            ),
            "invalid_output_class_signal": _parse_bool(
                kv["FLAG_INVALID_OUTPUT_CLASS"],
                "FLAG_INVALID_OUTPUT_CLASS",
            ),
            "preprocessing_evidence_loss": _parse_bool(
                kv["FLAG_PREPROCESSING_EVIDENCE_LOSS"],
                "FLAG_PREPROCESSING_EVIDENCE_LOSS",
            ),
            "best_evidence_source": source,
            "best_evidence_quote": _excerpt(kv["BEST_EVIDENCE_QUOTE"], 260),
        }

    messages = [{"role": "user", "content": prompt}]
    last_error: Optional[Exception] = None
    for attempt in range(2):
        text = _invoke_rca_openai_text(
            system=system,
            messages=messages,
            max_output_tokens=320,
            call_site="rca_evidence_flags" if attempt == 0 else "rca_evidence_flags_repair",
        )
        try:
            return _parse_flag_text(text)
        except ValueError as exc:
            last_error = exc
            if attempt == 1:
                break
            messages = [
                *messages,
                {"role": "assistant", "content": text[:1000]},
                {
                    "role": "user",
                    "content": (
                        "Your previous response did not match the required eight-line schema. "
                        "Return exactly the eight requested lines and no extra prose."
                    ),
                },
            ]
    raise last_error or ValueError("Invalid evidence flag output")


def normalize_best_evidence_source(raw_source: str) -> str:
    normalized = _normalize_label(raw_source).lower()
    source_aliases = {
        "score_context": "score_yaml",
        "score_yaml_configuration": "score_yaml",
        "score_guidelines": "guidelines",
        "guideline": "guidelines",
        "guidelines_excerpt": "guidelines",
        "input": "primary_input",
        "primary_input_excerpt": "primary_input",
        "raw_input_text": "primary_input",
        "transcript": "primary_input",
        "processed_input": "processed_input",
        "processed_input_text": "processed_input",
        "prediction": "score_explanation",
        "model_output": "score_explanation",
        "model_prediction": "score_explanation",
        "score_output": "score_explanation",
        "feedback_context": "edit_comment",
        "feedback_comment": "edit_comment",
        "feedback_comments": "edit_comment",
        "reviewer_comment": "edit_comment",
        "edit_comment_excerpt": "edit_comment",
        "final_comment_excerpt": "edit_comment",
        "initial_comment_excerpt": "edit_comment",
        "metadata_snapshot": "metadata",
        "metadata_snapshot_excerpt": "metadata",
        "rubric_memory_context": "rubric_memory",
        "citation_context": "rubric_memory",
    }
    if normalized.startswith("feedback_comment"):
        return "edit_comment"
    if normalized.startswith("reviewer_comment"):
        return "edit_comment"
    return source_aliases.get(normalized, normalized)


def _rubric_memory_citation_ids(item_context: dict, limit: int = 3) -> list[str]:
    rubric_memory = item_context.get("rubric_memory", {}) or {}
    raw_index = rubric_memory.get("citation_index") or []
    citation_ids = []
    for raw in raw_index:
        if isinstance(raw, dict) and raw.get("id"):
            citation_ids.append(str(raw["id"]))
    return citation_ids[:limit]


def rubric_memory_state_from_item_context(item_context: dict) -> dict:
    """Return compact rubric-memory availability/provenance state for RCA artifacts."""
    rubric_memory = (item_context or {}).get("rubric_memory", {}) or {}
    citation_index = rubric_memory.get("citation_index") or []
    diagnostics = rubric_memory.get("diagnostics") or []
    return {
        "rubric_memory_available": bool(citation_index),
        "citation_index_count": len(citation_index),
        "rubric_memory_diagnostics": diagnostics,
    }


def build_rca_analysis_failure_details(stage: str, exc: BaseException) -> dict:
    """Build a serializable RCA item-stage failure diagnostic."""
    return {
        "failed_stage": _normalize_label(stage) or "unknown",
        "exception_type": exc.__class__.__name__,
        "message": _excerpt(str(exc), 1000),
    }


def build_rca_analysis_failure_classification(
    *,
    item_context: dict,
    stage: str,
    exc: BaseException,
    evidence_flags: Optional[Dict[str, Any]] = None,
) -> dict:
    """Preserve an RCA item as a mechanical failure row when RCA analysis itself fails."""
    failure = build_rca_analysis_failure_details(stage, exc)
    citation_ids = _rubric_memory_citation_ids(item_context)
    citation_validation = validate_rubric_memory_citations(
        citation_ids,
        (item_context or {}).get("rubric_memory"),
        require_citation=False,
    )
    return {
        "primary_category": "mechanical_malfunction",
        "rationale": (
            "RCA item analysis failed before a reliable triage classification could be produced."
        ),
        "confidence": "high",
        "mechanical_subtype": "rca_analysis_failure",
        "mechanical_details": (
            f"failed_stage={failure['failed_stage']}; "
            f"exception_type={failure['exception_type']}; "
            f"message={failure['message']}"
        ),
        "information_gap_subtype": None,
        "evidence_snippets": [
            {
                "source": "metadata",
                "quote_or_fact": (
                    f"RCA analysis failed at {failure['failed_stage']}: "
                    f"{failure['exception_type']}: {failure['message']}"
                ),
            }
        ],
        "evidence_flags": evidence_flags or {},
        "rationale_paragraph": (
            "RCA item analysis failed before this item could be categorized. "
            "The item is preserved for debugging instead of being dropped."
        ),
        "evidence_quote": (
            f"{failure['failed_stage']}: {failure['exception_type']}: {failure['message']}"
        ),
        "config_fixability": "blocked_by_mechanical",
        "citation_ids": citation_validation.valid_ids,
        "citation_validation": citation_validation.model_dump(mode="json"),
        "rca_failure": failure,
    }


def classify_misclassification_item(item_context: dict, evidence_flags: Dict[str, Any]) -> dict:
    """Classify one misclassification using standardized context and extracted evidence flags."""
    availability = item_context.get("source_availability", {})
    prediction = item_context.get("prediction", {})
    feedback_context = item_context.get("feedback_context", {})
    score_context = item_context.get("score_context", {})

    predicted_value = (prediction.get("predicted_value") or "").strip()
    correct_value = (prediction.get("correct_value") or "").strip()
    score_explanation = (prediction.get("score_explanation") or prediction.get("score_explanation_excerpt") or "").strip()
    edit_comment = (feedback_context.get("edit_comment") or feedback_context.get("edit_comment_excerpt") or "").strip()
    final_comment = (feedback_context.get("final_comment") or feedback_context.get("final_comment_excerpt") or "").strip()
    primary_input_excerpt = (
        item_context.get("item_context", {}).get("raw_input_text")
        or item_context.get("item_context", {}).get("primary_input_excerpt")
        or ""
    ).strip()
    primary_input_modality = (
        item_context.get("item_context", {}).get("primary_input_modality") or "unknown"
    ).strip()
    missing_required_context_keys = [
        _normalize_label(value)
        for value in (availability.get("missing_required_context_keys") or [])
        if _normalize_label(value)
    ]
    has_primary_input = bool(availability.get("has_primary_input"))
    has_metadata_snapshot = bool(availability.get("has_metadata_snapshot"))
    primary_input_fetch_error = bool(availability.get("primary_input_fetch_error"))

    searchable_feedback = f"{edit_comment}\n{final_comment}".lower()
    searchable_explanation = score_explanation.lower()

    resolved_final_classes = [
        _normalize_label(class_name)
        for class_name in (score_context.get("resolved_final_classes") or [])
        if _normalize_label(class_name)
    ]
    valid_class_set = set(resolved_final_classes)
    if not isinstance(evidence_flags, dict):
        raise ValueError("evidence_flags must be a dictionary.")
    normalized_flags = {
        key: bool(evidence_flags.get(key))
        for key in MISCLASSIFICATION_EVIDENCE_FLAG_KEYS
    }
    best_evidence_source = _normalize_label(evidence_flags.get("best_evidence_source"))
    best_evidence_quote = _normalize_label(evidence_flags.get("best_evidence_quote"))

    evidence = []
    rubric_memory_citation_ids = _rubric_memory_citation_ids(item_context)

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
            marker_value = parse_marker
            mechanical_details = f"marker={marker_value}"
            _add_evidence("score_explanation", score_explanation or marker_value)
        elif runtime_marker or normalized_flags["runtime_or_parsing_failure"]:
            mechanical_subtype = "runtime_error"
            marker_value = runtime_marker or "llm_signal_runtime_or_parsing_failure"
            mechanical_details = f"marker={marker_value}"
            _add_evidence("score_explanation", score_explanation or marker_value)
        else:
            missing_context_markers = (
                "missing metadata",
                "metadata missing",
                "required metadata",
                "context key missing",
                "failed to fetch",
                "no input payload",
                "input unavailable",
            )
            missing_context_marker = next(
                (
                    marker
                    for marker in missing_context_markers
                    if marker in searchable_explanation or marker in searchable_feedback
                ),
                None,
            )
            objective_missing_context_signal = bool(
                missing_required_context_keys
                or primary_input_fetch_error
                or (
                    missing_context_marker
                    and (
                        not has_primary_input
                        or not has_metadata_snapshot
                        or "metadata" in missing_context_marker
                        or "context" in missing_context_marker
                    )
                )
                or (
                    normalized_flags["missing_required_context_due_system"]
                    and (not has_primary_input or primary_input_fetch_error)
                )
            )
            if objective_missing_context_signal:
                mechanical_subtype = "missing_required_context"
                context_bits = []
                if missing_required_context_keys:
                    context_bits.append(
                        f"missing_required_context_keys={','.join(missing_required_context_keys)}"
                    )
                if primary_input_fetch_error:
                    context_bits.append("primary_input_fetch_error=true")
                if missing_context_marker:
                    context_bits.append(f"marker={missing_context_marker}")
                mechanical_details = "; ".join(context_bits) or "missing_required_context_detected"
                if missing_context_marker:
                    _add_evidence("score_explanation", score_explanation)
                if normalized_flags["missing_required_context_due_system"] and best_evidence_quote:
                    _add_evidence(best_evidence_source or "edit_comment", best_evidence_quote)
                if missing_required_context_keys:
                    _add_evidence(
                        "metadata",
                        f"Missing required context keys: {', '.join(missing_required_context_keys)}",
                    )
                if not has_primary_input:
                    _add_evidence(
                        "primary_input",
                        "Primary input artifact unavailable while score required context.",
                    )
            elif (
                (valid_class_set and predicted_value.lower() not in {v.lower() for v in valid_class_set})
                or normalized_flags["invalid_output_class_signal"]
            ):
                mechanical_subtype = "invalid_output_class"
                mechanical_details = (
                    f"predicted_value='{predicted_value}' not_in_resolved_valid_classes={sorted(valid_class_set)}"
                )
                _add_evidence("score_explanation", score_explanation or predicted_value)
                _add_evidence("score_yaml", f"Resolved valid classes: {sorted(valid_class_set)}")
                if normalized_flags["invalid_output_class_signal"] and best_evidence_quote:
                    _add_evidence(best_evidence_source or "score_explanation", best_evidence_quote)

    if mechanical_subtype:
        if mechanical_subtype == "parse_or_schema_error":
            rationale = "Parser/schema failure indicators are present in score execution output."
        elif mechanical_subtype == "invalid_output_class":
            rationale = "Predicted output class is outside the resolved final label set."
        elif mechanical_subtype == "missing_required_context":
            rationale = "Required model input/context was unavailable due pipeline or contract issues."
        else:
            rationale = "Execution-level failure indicators are present in the score output path."
        return {
            "primary_category": "mechanical_malfunction",
            "rationale": rationale,
            "confidence": "high",
            "mechanical_subtype": mechanical_subtype,
            "mechanical_details": mechanical_details or "mechanical_failure_detected",
            "information_gap_subtype": None,
            "evidence_snippets": evidence or [{"source": "score_explanation", "quote_or_fact": "Execution failure indicators found."}],
            "evidence_flags": normalized_flags,
            "citation_ids": rubric_memory_citation_ids if best_evidence_source == "rubric_memory" else [],
        }

    # Information gap: externally missing/degraded source evidence for correct determination.
    # Evidence from feedback comments is represented via LLM-derived flags, not keyword heuristics.
    if (
        not has_primary_input
        or normalized_flags["external_information_missing_or_degraded"]
    ):
        _add_evidence("edit_comment", edit_comment or final_comment)
        if normalized_flags["external_information_missing_or_degraded"] and best_evidence_quote:
            _add_evidence(best_evidence_source or "edit_comment", best_evidence_quote)
        _add_evidence(
            "primary_input",
            primary_input_excerpt
            or f"Primary input artifact unavailable (modality={primary_input_modality or 'unknown'}).",
        )
        return {
            "primary_category": "information_gap",
            "rationale": "Available evidence indicates missing or degraded source information for reliable classification.",
            "confidence": "medium",
            "mechanical_subtype": None,
            "mechanical_details": None,
            "evidence_snippets": evidence or [{"source": "primary_input", "quote_or_fact": "Primary input context unavailable or insufficient."}],
            "information_gap_subtype": (
                "missing_primary_input" if not has_primary_input else "degraded_primary_input"
            ),
            "evidence_flags": normalized_flags,
            "citation_ids": rubric_memory_citation_ids if best_evidence_source == "rubric_memory" else [],
        }

    # Guideline gap: ambiguity/policy signals should come from explicit LLM evidence flags.
    if normalized_flags["guideline_or_policy_ambiguity"] or not availability.get("has_score_guidelines"):
        _add_evidence("edit_comment", edit_comment or final_comment)
        if normalized_flags["guideline_or_policy_ambiguity"] and best_evidence_quote:
            _add_evidence(best_evidence_source or "edit_comment", best_evidence_quote)
        _add_evidence("guidelines", score_context.get("guidelines", score_context.get("guidelines_excerpt", "Guidelines were unavailable.")))
        return {
            "primary_category": "guideline_gap_requires_sme",
            "rationale": "The misclassification appears to depend on rubric ambiguity or missing policy detail.",
            "confidence": "medium",
            "mechanical_subtype": None,
            "mechanical_details": None,
            "information_gap_subtype": None,
            "evidence_snippets": evidence or [{"source": "guidelines", "quote_or_fact": "Guidelines unavailable or ambiguous for this case."}],
            "evidence_flags": normalized_flags,
            "citation_ids": rubric_memory_citation_ids,
        }

    # Preprocessing evidence loss: the preprocessor pipeline removed evidence critical for
    # correct classification. This is a score_configuration_problem (preprocessing is config-fixable).
    if normalized_flags.get("preprocessing_evidence_loss"):
        item_ctx = item_context.get("item_context", {})
        processors_applied = item_ctx.get("processors_applied", "unknown")
        _add_evidence("score_yaml", f"Preprocessing pipeline: {processors_applied}")
        if best_evidence_quote:
            _add_evidence(best_evidence_source or "primary_input", best_evidence_quote)
        _add_evidence("score_explanation", score_explanation)
        return {
            "primary_category": "score_configuration_problem",
            "rationale": (
                "The preprocessor pipeline removed content from the input that contained evidence "
                "relevant to the correct classification. This is a score configuration issue — "
                "the preprocessing config (e.g., keyword list, filter settings) needs adjustment."
            ),
            "confidence": "high",
            "mechanical_subtype": "preprocessing_evidence_loss",
            "mechanical_details": f"processors_applied={processors_applied}",
            "information_gap_subtype": None,
            "evidence_snippets": evidence or [{"source": "score_yaml", "quote_or_fact": f"Preprocessor config needs review: {processors_applied}"}],
            "evidence_flags": normalized_flags,
            "citation_ids": rubric_memory_citation_ids if best_evidence_source == "rubric_memory" else [],
        }

    # Default bucket for model/score logic behavior.
    _add_evidence("score_explanation", score_explanation)
    _add_evidence("score_yaml", score_context.get("score_yaml_configuration", score_context.get("score_yaml_excerpt", "Score configuration context available.")))
    return {
        "primary_category": "score_configuration_problem",
        "rationale": "Evidence points to score logic/prompt behavior rather than missing information or policy ambiguity.",
        "confidence": "medium",
        "mechanical_subtype": None,
        "mechanical_details": None,
        "information_gap_subtype": None,
        "evidence_snippets": evidence or [{"source": "score_yaml", "quote_or_fact": "Score configuration is the primary fix surface for this item."}],
        "evidence_flags": normalized_flags,
        "citation_ids": rubric_memory_citation_ids if best_evidence_source == "rubric_memory" else [],
    }


def explain_misclassification_item_classification(
    *,
    item_context: Dict[str, Any],
    classification: Dict[str, Any],
) -> Dict[str, str]:
    """
    Generate a short, operator-focused explanation for an assigned misclassification category.
    Raises ValueError when the LLM output is invalid.
    """
    system = (
        "You explain misclassification triage decisions for AI evaluations. "
        "Use neutral, modality-agnostic language. Call transcripts are only one possible example."
    )
    rca_cookbook = (
        "Common root causes to reference when writing your explanation:\n"
        "1. PREPROCESSING_EVIDENCE_LOSS: A preprocessor (e.g., RelevantWindowsTranscriptFilter) "
        "removed transcript lines containing critical evidence. Check preprocessing_changed_input "
        "and compare raw_input_text vs processed_input_text.\n"
        "2. PHONETIC_TRANSCRIPTION_ERROR: Speech-to-text mangled a proper noun (school/product name) "
        "into a phonetically similar common word the LLM couldn't recognize.\n"
        "3. KEYWORD_GAP: RelevantWindowsTranscriptFilter keyword list is missing a synonym used in "
        "this transcript — the relevant content was filtered out.\n"
        "4. TEMPORAL_ORDERING_LOSS: Sentence/paragraph transcript format collapsed word-level timing, "
        "making it impossible to tell which response followed which prompt.\n"
        "5. SPEAKER_FILTER_ERROR: A speaker filter removed the wrong speaker's lines.\n"
        "6. GUIDELINE_PROMPT_MISMATCH: Guidelines describe a policy absent from the LLM prompts.\n"
        "7. AMBIGUOUS_BOUNDARY: Item sits on the classification boundary; guidelines don't clearly "
        "define which class applies to this specific pattern.\n"
    )
    prompt = (
        "You are given normalized item context and an assigned category decision.\n"
        "Return exactly four lines in this exact format:\n"
        "RATIONALE_PARAGRAPH: <short paragraph, 2-4 sentences>\n"
        "EVIDENCE_QUOTE: <one concrete quote/fact>\n"
        "CONFIG_FIXABILITY: <one of "
        f"{', '.join(CONFIG_FIXABILITY_OPTIONS)}>\n"
        "CITATION_IDS: <comma-separated rubric-memory citation IDs used, or empty>\n\n"
        "Rules:\n"
        "- Do not change the assigned category decision.\n"
        "- If failure is execution/system/context contract related, use blocked_by_mechanical.\n"
        "- If source evidence is genuinely insufficient/degraded, use blocked_by_input.\n"
        "- If policy ambiguity dominates, use needs_sme_clarification.\n"
        "- If score logic/prompt adjustment is the likely fix, use likely_fixable.\n"
        "- If preprocessing_evidence_loss flag is true: explain specifically what the preprocessor "
        "removed and why that removal caused the misclassification. Reference the processors_applied "
        "field and the difference between raw_input_text and processed_input_text.\n\n"
        "- If rubric_memory.citation_index is available and you make a policy-memory claim, include "
        "the exact citation IDs in CITATION_IDS.\n\n"
        f"{rca_cookbook}\n"
        f"Item context JSON:\n{json.dumps(item_context, ensure_ascii=True)}\n\n"
        f"Deterministic classification JSON:\n{json.dumps(classification, ensure_ascii=True)}\n"
    )
    def _parse_explainer_text(raw_text: str) -> Dict[str, Any]:
        line_map = {}
        for line in str(raw_text or "").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            line_map[_normalize_label(key).upper()] = _normalize_label(value)

        rationale_paragraph = line_map.get("RATIONALE_PARAGRAPH", "")
        evidence_quote = line_map.get("EVIDENCE_QUOTE", "")
        config_fixability = line_map.get("CONFIG_FIXABILITY", "")
        citation_ids = [
            value.strip()
            for value in re.split(r"[,\\s]+", line_map.get("CITATION_IDS", ""))
            if value.strip()
        ]

        if not rationale_paragraph:
            raise ValueError(f"Triage explainer output missing RATIONALE_PARAGRAPH: {raw_text}")
        if not evidence_quote:
            raise ValueError(f"Triage explainer output missing EVIDENCE_QUOTE: {raw_text}")
        if config_fixability not in CONFIG_FIXABILITY_OPTIONS:
            raise ValueError(
                f"Triage explainer output has invalid config_fixability '{config_fixability}'. "
                f"Allowed: {CONFIG_FIXABILITY_OPTIONS}. Raw output: {raw_text}"
            )
        citation_validation = validate_rubric_memory_citations(
            citation_ids,
            item_context.get("rubric_memory"),
            require_citation=bool(item_context.get("rubric_memory", {}).get("citation_index")),
        )
        return {
            "rationale_paragraph": _excerpt(rationale_paragraph, 320),
            "evidence_quote": _excerpt(evidence_quote, 180),
            "config_fixability": config_fixability,
            "citation_ids": citation_validation.valid_ids,
            "citation_validation": citation_validation.model_dump(mode="json"),
        }

    messages = [{"role": "user", "content": prompt}]
    last_error: Optional[Exception] = None
    for attempt in range(2):
        raw_text = _invoke_rca_openai_text(
            system=system,
            messages=messages,
            max_output_tokens=320,
            call_site="rca_triage_explainer" if attempt == 0 else "rca_triage_explainer_repair",
        )
        try:
            return _parse_explainer_text(raw_text)
        except ValueError as exc:
            last_error = exc
            if attempt == 1:
                break
            messages = [
                *messages,
                {"role": "assistant", "content": raw_text[:1000]},
                {
                    "role": "user",
                    "content": (
                        "Your previous response did not match the required four-line schema. "
                        "Return exactly RATIONALE_PARAGRAPH, EVIDENCE_QUOTE, CONFIG_FIXABILITY, "
                        "and CITATION_IDS lines with no extra prose."
                    ),
                },
            ]
    raise last_error or ValueError("Invalid triage explainer output")


def build_misclassification_analysis_summary(
    topics: list,
    *,
    item_classifications_all: List[Dict[str, Any]],
    analysis_scope: Optional[Dict[str, Any]] = None,
    max_category_summary_items: int = 20,
) -> dict:
    """Build structured triage output including topic/category summaries and next-action guidance."""
    max_items_used = max(1, int(max_category_summary_items or 20))
    if not isinstance(item_classifications_all, list):
        raise ValueError("item_classifications_all must be a list.")

    item_classifications: List[Dict[str, Any]] = []
    category_totals = {category: 0 for category in MISCLASSIFICATION_CATEGORIES}
    mechanical_subtype_totals = {subtype: 0 for subtype in MECHANICAL_SUBTYPES}
    predicted_values: List[str] = []
    missing_primary_input_count = 0
    missing_required_context_count = 0
    topic_category_breakdown: List[Dict[str, Any]] = []
    topic_hierarchy_rows: List[Dict[str, Any]] = []

    def _sorted_category_counts(category_counts: Dict[str, int]) -> Dict[str, int]:
        return {category: int(category_counts.get(category, 0)) for category in MISCLASSIFICATION_CATEGORIES}

    for raw in item_classifications_all:
        context = raw.get("misclassification_item_context") or {}
        availability = context.get("source_availability", {})
        rubric_state = rubric_memory_state_from_item_context(context)
        row = {
            "topic_id": raw.get("topic_id"),
            "topic_label": raw.get("topic_label", ""),
            "feedback_item_id": raw.get("feedback_item_id", ""),
            "item_id": raw.get("item_id", ""),
            "timestamp": raw.get("timestamp") or "",
            "predicted_value": raw.get("predicted_value", ""),
            "correct_value": raw.get("correct_value", ""),
            "primary_category": raw.get("primary_category", ""),
            "confidence": raw.get("confidence", ""),
            "rationale_short": raw.get("rationale_short", ""),
            "rationale_full": raw.get("rationale_full", ""),
            "evidence_snippets": raw.get("evidence_snippets", []),
            "triage_evidence_flags": (
                raw.get("triage_evidence_flags")
                or raw.get("evidence_flags")
                or {}
            ),
            "mechanical_subtype": raw.get("mechanical_subtype"),
            "mechanical_details": raw.get("mechanical_details"),
            "information_gap_subtype": raw.get("information_gap_subtype"),
            "rationale_paragraph": raw.get("rationale_paragraph", ""),
            "evidence_quote": raw.get("evidence_quote", ""),
            "config_fixability": raw.get("config_fixability", ""),
            "citation_ids": raw.get("citation_ids", []),
            "citation_validation": raw.get("citation_validation", {}),
            "rubric_memory_available": bool(rubric_state["rubric_memory_available"]),
            "citation_index_count": int(rubric_state["citation_index_count"]),
            "rubric_memory_diagnostics": rubric_state["rubric_memory_diagnostics"],
            "rca_failure": raw.get("rca_failure"),
            "rca_failures": raw.get("rca_failures", []),
            "has_primary_input": bool(availability.get("has_primary_input")),
            "missing_required_context": bool(availability.get("missing_required_context_keys")),
            "detailed_cause": raw.get("detailed_cause"),
            "suggested_fix": raw.get("suggested_fix"),
        }
        item_classifications.append(row)

        category = row.get("primary_category")
        if category in category_totals:
            category_totals[category] += 1

        if context and not availability.get("has_primary_input"):
            missing_primary_input_count += 1
        if context and (availability.get("missing_required_context_keys") or []):
            missing_required_context_count += 1

        predicted_value = _normalize_label(row.get("predicted_value"))
        if predicted_value:
            predicted_values.append(predicted_value)

        mechanical_subtype = row.get("mechanical_subtype")
        if mechanical_subtype in mechanical_subtype_totals:
            mechanical_subtype_totals[mechanical_subtype] += 1

    item_classifications = sorted(
        item_classifications,
        key=lambda item: (
            -_parse_iso_timestamp(item.get("timestamp", "")),
            str(item.get("feedback_item_id") or item.get("item_id") or ""),
        ),
    )

    topic_item_map: Dict[str, List[Dict[str, Any]]] = {}
    for row in item_classifications:
        topic_id = row.get("topic_id")
        if topic_id is None:
            continue
        topic_item_map.setdefault(str(topic_id), []).append(row)

    for topic in topics or []:
        topic_id = topic.get("topic_id")
        topic_label = topic.get("label", "")
        topic_member_count = int(topic.get("member_count") or 0)
        topic_counts = {category: 0 for category in MISCLASSIFICATION_CATEGORIES}
        assigned_rows = topic_item_map.get(str(topic_id), [])
        for row in assigned_rows:
            category = row.get("primary_category")
            if category in topic_counts:
                topic_counts[category] += 1

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

    if total_items > 0 and (missing_primary_input_count / total_items) >= 0.5:
        red_flags.append({
            "flag": "low_primary_input_coverage",
            "severity": "medium",
            "message": "At least half of analyzed items were missing primary input context.",
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
                rationale = _normalize_label(item.get("rationale_full") or item.get("rationale_short"))
                key = rationale.split(".", 1)[0].strip().lower() if rationale else "unspecified_pattern"
            pattern_counter[key] += 1
        top = []
        for pattern, count in pattern_counter.most_common(3):
            top.append({"pattern": pattern, "count": int(count)})
        return top

    category_summaries = {}
    category_hierarchy = []
    category_diagnostics: Dict[str, Dict[str, Any]] = {}
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
            exemplar_ids = []
            for ex in topic_payload.get("exemplars", []) or []:
                if not isinstance(ex, dict):
                    continue
                feedback_item_id = (
                    ex.get("feedback_item_id")
                    or (ex.get("misclassification_item_context") or {}).get("identifiers", {}).get("feedback_item_id")
                    or ""
                )
                item_id = (
                    ex.get("item_id")
                    or (ex.get("misclassification_item_context") or {}).get("identifiers", {}).get("item_id")
                    or ""
                )
                exemplar_ids.append({
                    "feedback_item_id": feedback_item_id,
                    "item_id": item_id,
                })

            category_topics.append({
                "topic_id": topic_row.get("topic_id"),
                "label": topic_row.get("topic_label", ""),
                "member_count": topic_row.get("member_count", 0),
                "topic_category_purity": topic_row.get("topic_category_purity", 0.0),
                "category_counts": topic_row.get("category_counts", {}),
                "score_fix_candidate_count": topic_payload.get("score_fix_candidate_count"),
                "example_item_ids": exemplar_ids,
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

        if category == "information_gap":
            missing_or_degraded_signals = 0
            missing_required_context_signals = 0
            for item in items_in_category:
                flags = item.get("triage_evidence_flags") or {}
                if item.get("missing_required_context") or bool(
                    flags.get("missing_required_context_due_system")
                ):
                    missing_required_context_signals += 1
                snippets = item.get("evidence_snippets") or []
                has_missing_signal = any(
                    _normalize_label((snippet or {}).get("source")).lower() == "primary_input"
                    and any(
                        marker in _normalize_label((snippet or {}).get("quote_or_fact")).lower()
                        for marker in (
                            "unavailable",
                            "missing",
                            "not available",
                            "insufficient",
                            "degraded",
                            "redacted",
                        )
                    )
                    for snippet in snippets
                ) or not bool(item.get("has_primary_input")) or bool(
                    flags.get("external_information_missing_or_degraded")
                )
                if has_missing_signal:
                    missing_or_degraded_signals += 1
            missing_or_degraded_share = (
                missing_or_degraded_signals / item_count if item_count else 0.0
            )
            missing_required_context_share = (
                missing_required_context_signals / item_count if item_count else 0.0
            )
            category_diagnostics["information_gap"] = {
                "item_count": item_count,
                "missing_or_degraded_primary_input_count": missing_or_degraded_signals,
                "missing_or_degraded_primary_input_share": round(missing_or_degraded_share, 4),
                "missing_required_context_count": missing_required_context_signals,
                "missing_required_context_share": round(missing_required_context_share, 4),
                "diagnostic_summary": (
                    f"{missing_or_degraded_signals}/{item_count} information-gap item(s) include "
                    "missing/degraded primary-input evidence; "
                    f"{missing_required_context_signals}/{item_count} include missing required context signals."
                    if item_count
                    else "No information-gap items in this run."
                ),
            }

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

    inferred_scope = {
        "candidate_items_total": total_items,
        "classified_items_total": total_items,
        "texts_analyzed_total": total_items,
        "topics_found": len(topics or []),
        "topic_assignment_scope": "exemplar_only",
        "topic_assignment_unavailable_count": len(
            [item for item in item_classifications if item.get("topic_id") is None]
        ),
    }
    if analysis_scope:
        for key, value in analysis_scope.items():
            if value is not None:
                inferred_scope[key] = value

    return {
        "pipeline_stage_order": [
            "item_classification",
            "topic_modeling",
            "topic_category_assignment",
            "category_recursive_summarization",
            "evaluation_red_flags",
            "final_recommendation",
        ],
        "analysis_scope": inferred_scope,
        "item_classifications_all": item_classifications,
        "topic_category_breakdown": topic_category_breakdown,
        "category_hierarchy": category_hierarchy,
        "category_totals": category_totals,
        "category_shares": {k: round(v, 4) for k, v in category_shares.items()},
        "category_diagnostics": category_diagnostics,
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
        "item_explainer_output": get_misclassification_explainer_output_contract(),
        "item_context_contract": get_misclassification_item_context_contract(),
    }


def analyze_score_result(
    primary_input: str,
    predicted: str,
    correct: str,
    explanation: str,
    topic_label: str = "Score result investigation",
    score_guidelines: str = "",
    score_yaml_code: str = "",
    feedback_context: str = "",
) -> tuple:
    """
    Run a two-turn GPT-5 mini conversation to analyze a misclassification.

    Returns (detailed_cause, suggested_fix):
      - detailed_cause: why the AI prediction was wrong (2-4 sentences)
      - suggested_fix: one concrete score code change to prevent this error

    Args:
        primary_input: Primary input artifact text/context excerpt
        predicted: The AI's predicted value
        correct: The correct/human-labeled value
        explanation: The AI's reasoning for its prediction
        topic_label: Topic or cluster context label
        score_guidelines: Score guidelines text (truncated to 2000 chars)
        score_yaml_code: Score YAML configuration (truncated to 4000 chars)
        feedback_context: Additional context about reviewer feedback
    """
    system = (
        "You are an expert quality analyst reviewing AI scoring errors across domains and modalities."
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
        "Primary input artifact (for example: transcript text, document text, extracted OCR, or "
        "serialized structured input):\n"
        f"{primary_input[:6000]}\n\n"
        "Write a single concise paragraph (2-4 sentences) explaining specifically why "
        "the AI prediction was wrong. Focus on what evidence was present, absent, or degraded "
        "in the provided input artifact and why the correct label follows."
    )

    try:
        messages = [{"role": "user", "content": turn1_prompt}]
        detailed_cause = _invoke_rca_openai_text(
            system=system,
            messages=messages,
            max_output_tokens=200,
            call_site="rca_score_result_detailed_cause",
        )

        messages.append({"role": "assistant", "content": detailed_cause})
        messages.append({"role": "user", "content": (
            "Based on this specific error and the score configuration above, "
            "suggest one concrete change to the score code that would prevent "
            "this specific misclassification. Be specific and brief (1-2 sentences)."
        )})
        suggested_fix = _invoke_rca_openai_text(
            system=system,
            messages=messages,
            max_output_tokens=150,
            call_site="rca_score_result_suggested_fix",
        )

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
