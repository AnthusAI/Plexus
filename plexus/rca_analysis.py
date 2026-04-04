#!/usr/bin/env python3
"""
Shared RCA analysis utilities for score result investigation.

Used by both the feedback evaluation RCA pipeline (Evaluation.py)
and the on-demand plexus_score_result_investigate MCP tool.
"""
import json
import logging

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


def _excerpt(text: str, max_chars: int = 500) -> str:
    if not text:
        return ""
    value = str(text).strip()
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}..."


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

    evidence = []

    def _add_evidence(source: str, quote_or_fact: str):
        if quote_or_fact:
            evidence.append({
                "source": source,
                "quote_or_fact": _excerpt(quote_or_fact, 260),
            })

    # Mechanical failures should be detected first.
    if (not predicted_value or not correct_value) or any(
        marker in searchable_explanation
        for marker in ("error", "exception", "timeout", "failed", "traceback")
    ):
        _add_evidence("score_explanation", score_explanation or "Missing predicted/correct label values.")
        return {
            "primary_category": "mechanical_malfunction",
            "rationale": "Execution-level failure indicators are present in the score output path.",
            "confidence": "high",
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
            "evidence_snippets": evidence or [{"source": "guidelines", "quote_or_fact": "Guidelines unavailable or ambiguous for this case."}],
        }

    # Default bucket for model/score logic behavior.
    _add_evidence("score_explanation", score_explanation)
    _add_evidence("score_yaml", score_context.get("score_yaml_excerpt", "Score configuration context available."))
    return {
        "primary_category": "score_configuration_problem",
        "rationale": "Evidence points to score logic/prompt behavior rather than missing information or policy ambiguity.",
        "confidence": "medium",
        "evidence_snippets": evidence or [{"source": "score_yaml", "quote_or_fact": "Score configuration is the primary fix surface for this item."}],
    }


def build_misclassification_analysis_summary(topics: list) -> dict:
    """Build structured item classifications, totals, and evaluation-level red flags."""
    item_classifications = []
    category_totals = {category: 0 for category in MISCLASSIFICATION_CATEGORIES}
    predicted_values = []
    missing_transcript_count = 0
    mechanical_count = 0

    for topic in topics or []:
        topic_id = topic.get("topic_id")
        for ex in topic.get("exemplars", []) or []:
            classification = ex.get("misclassification_classification") or {}
            context = ex.get("misclassification_item_context") or {}
            identifiers = context.get("identifiers", {})
            prediction = context.get("prediction", {})
            availability = context.get("source_availability", {})

            category = classification.get("primary_category")
            if category in category_totals:
                category_totals[category] += 1
            if category == "mechanical_malfunction":
                mechanical_count += 1
            if not availability.get("has_transcript_text"):
                missing_transcript_count += 1

            predicted_value = prediction.get("predicted_value")
            if predicted_value:
                predicted_values.append(predicted_value)

            item_classifications.append({
                "topic_id": topic_id,
                "feedback_item_id": identifiers.get("feedback_item_id", ""),
                "item_id": identifiers.get("item_id", ""),
                "primary_category": category or "",
                "confidence": classification.get("confidence", ""),
                "rationale": classification.get("rationale", ""),
                "evidence_snippets": classification.get("evidence_snippets", []),
            })

    total_items = len(item_classifications)
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

    if mechanical_count > 0:
        red_flags.append({
            "flag": "mechanical_failures_present",
            "severity": "high" if mechanical_count >= 2 else "medium",
            "message": f"{mechanical_count} item(s) classified as mechanical malfunction.",
        })

    if total_items > 0 and (missing_transcript_count / total_items) >= 0.5:
        red_flags.append({
            "flag": "low_transcript_coverage",
            "severity": "medium",
            "message": "At least half of analyzed items were missing transcript context.",
        })

    predominant_category = ""
    if total_items > 0:
        predominant_category = max(category_totals.items(), key=lambda x: x[1])[0]

    return {
        "item_classifications": item_classifications,
        "category_totals": category_totals,
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
