"""Shared feedback-item explanation generation and cache persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from plexus.bedrock_models import CLAUDE_HAIKU_45_MODEL_ID

logger = logging.getLogger(__name__)

EXPLANATION_CACHE_METADATA_KEY = "feedback_item_explanations"
EXPLANATION_PROMPT_VERSION = "v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_BEDROCK_MODEL = CLAUDE_HAIKU_45_MODEL_ID
DEFAULT_HEURISTIC_MODEL = "feedback-item-explainer-v1"


def _coerce_metadata_dict(raw_metadata: Any) -> Dict[str, Any]:
    if isinstance(raw_metadata, dict):
        return dict(raw_metadata)
    if isinstance(raw_metadata, str) and raw_metadata.strip():
        try:
            parsed = json.loads(raw_metadata)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _cache_entry_key(provider: str, model: str) -> str:
    return f"{(provider or '').strip().lower()}::{(model or '').strip()}"


def _parse_json_object(text: str) -> Dict[str, Any]:
    payload = (text or "").strip()
    if "```" in payload:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", payload)
        if fenced:
            payload = fenced.group(1).strip()
    object_match = re.search(r"\{[\s\S]*\}", payload)
    if object_match:
        payload = object_match.group(0)
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("Explanation model response must be a JSON object")
    return parsed


def _build_feedback_item_explanation_prompt(context: Dict[str, Any]) -> str:
    return (
        "You are analyzing one feedback correction to explain what the feedback means.\\n"
        "Use all context fields below, then produce one concise ground-truth explanation.\\n\\n"
        "Context:\\n"
        f"- Initial AI value: {context.get('initial_answer_value', '')!r}\\n"
        f"- Final reviewer value: {context.get('final_answer_value', '')!r}\\n"
        f"- Predicted value for this evaluation: {context.get('predicted_value', '')!r}\\n"
        f"- Correct value for this evaluation: {context.get('correct_value', '')!r}\\n"
        f"- Reviewer edit comment: {context.get('edit_comment', '')!r}\\n"
        f"- Initial reviewer comment: {context.get('initial_comment', '')!r}\\n"
        f"- Final reviewer comment: {context.get('final_comment', '')!r}\\n"
        f"- Original production explanation: {context.get('original_explanation', '')!r}\\n"
        f"- Current score explanation: {context.get('score_explanation', '')!r}\\n"
        f"- Score guidelines: {context.get('score_guidelines_text', '')[:8000]!r}\\n"
        f"- Scorecard guidance: {context.get('scorecard_guidance_text', '')[:4000]!r}\\n"
        f"- Transcript / item text: {context.get('transcript_text', '')[:12000]!r}\\n"
        f"- Item metadata snapshot: {context.get('item_metadata_snapshot', '')[:4000]!r}\\n\\n"
        "Return ONLY valid JSON with exactly these keys:\\n"
        "{\\n"
        '  "ground_truth_value": "string",\\n'
        '  "explanation": "1-3 sentence explanation of what this feedback item establishes as ground truth and why",\\n'
        '  "key_evidence": ["short evidence point 1", "short evidence point 2"]\\n'
        "}\\n"
        "No markdown, no prose outside JSON."
    )


def _build_heuristic_explanation(context: Dict[str, Any]) -> Dict[str, Any]:
    predicted = str(context.get("predicted_value") or context.get("initial_answer_value") or "").strip()
    correct_value = str(context.get("correct_value") or context.get("final_answer_value") or "").strip()
    initial_value = str(context.get("initial_answer_value") or "").strip()
    final_value = str(context.get("final_answer_value") or "").strip()
    reviewer_agreed = bool(initial_value and final_value and initial_value == final_value)

    ordered_sources: List[str]
    if reviewer_agreed:
        ordered_sources = [
            str(context.get("original_explanation") or "").strip(),
            str(context.get("edit_comment") or "").strip(),
            str(context.get("score_explanation") or "").strip(),
            str(context.get("final_comment") or "").strip(),
            str(context.get("initial_comment") or "").strip(),
        ]
    else:
        ordered_sources = [
            str(context.get("edit_comment") or "").strip(),
            str(context.get("final_comment") or "").strip(),
            str(context.get("original_explanation") or "").strip(),
            str(context.get("score_explanation") or "").strip(),
            str(context.get("initial_comment") or "").strip(),
        ]

    explanation = next((candidate for candidate in ordered_sources if candidate), "")
    if not explanation:
        explanation = f"Predicted '{predicted}' but the corrected ground-truth label is '{correct_value}'."

    key_evidence = [candidate for candidate in ordered_sources if candidate][:2]
    return {
        "ground_truth_value": correct_value,
        "explanation": " ".join(explanation.split()),
        "key_evidence": key_evidence,
    }


def _resolve_provider_and_model(provider: Optional[str], model: Optional[str]) -> Tuple[str, str, bool]:
    requested = (provider or "auto").strip().lower()
    if requested not in {"auto", "openai", "bedrock", "heuristic", "local"}:
        raise ValueError(
            "feedback explanation provider must be one of: auto, openai, bedrock, heuristic"
        )

    if requested == "auto":
        if os.getenv("OPENAI_API_KEY"):
            return "openai", model or DEFAULT_OPENAI_MODEL, True
        if os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE") or os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE"):
            return "bedrock", model or DEFAULT_BEDROCK_MODEL, True
        return "heuristic", model or DEFAULT_HEURISTIC_MODEL, True

    if requested in {"heuristic", "local"}:
        return "heuristic", model or DEFAULT_HEURISTIC_MODEL, False
    if requested == "openai":
        return "openai", model or DEFAULT_OPENAI_MODEL, False
    return "bedrock", model or DEFAULT_BEDROCK_MODEL, False


def _invoke_openai_explanation_model(prompt: str, model: str) -> Dict[str, Any]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for feedback explanation provider=openai")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        input=[{"role": "user", "content": prompt}],
        max_output_tokens=900,
    )
    return _parse_json_object(response.output_text)


def _invoke_bedrock_explanation_model(prompt: str, model: str) -> Dict[str, Any]:
    import boto3

    bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION") or "us-east-1")
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 900,
        "temperature": 0,
    }
    response = bedrock.invoke_model(
        modelId=model,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    raw = json.loads(response["body"].read())
    text_chunks = [
        (block.get("text") or "").strip()
        for block in raw.get("content", [])
        if block.get("type") == "text"
    ]
    text = "\n".join(chunk for chunk in text_chunks if chunk)
    return _parse_json_object(text)


def _read_cached_entry(metadata: Dict[str, Any], provider: str, model: str) -> Optional[Dict[str, Any]]:
    envelope = metadata.get(EXPLANATION_CACHE_METADATA_KEY)
    if not isinstance(envelope, dict):
        return None
    entries = envelope.get("entries")
    if not isinstance(entries, dict):
        return None
    candidate = entries.get(_cache_entry_key(provider, model))
    if isinstance(candidate, dict):
        return candidate
    return None


def _store_cache_entry(metadata: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(metadata)
    envelope = merged.get(EXPLANATION_CACHE_METADATA_KEY)
    if not isinstance(envelope, dict):
        envelope = {}
    entries = envelope.get("entries")
    if not isinstance(entries, dict):
        entries = {}

    entries[_cache_entry_key(entry.get("provider", ""), entry.get("model", ""))] = entry
    envelope["entries"] = entries
    envelope["updated_at"] = entry.get("generated_at")
    merged[EXPLANATION_CACHE_METADATA_KEY] = envelope
    return merged


async def get_or_generate_feedback_item_explanation(
    *,
    feedback_item: Any,
    api_client: Optional[Any],
    predicted_value: str,
    correct_value: str,
    score_explanation: str,
    original_explanation: str,
    score_guidelines_text: str,
    scorecard_guidance_text: str,
    transcript_text: str,
    item_metadata_snapshot: str,
    initial_comment: str,
    final_comment: str,
    provider: Optional[str] = "auto",
    model: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Get cached feedback-item explanation or generate and persist it."""
    resolved_provider, resolved_model, provider_was_auto = _resolve_provider_and_model(provider, model)

    metadata = _coerce_metadata_dict(getattr(feedback_item, "metadata", None))
    if not force_refresh:
        cached_entry = _read_cached_entry(metadata, resolved_provider, resolved_model)
        if cached_entry and cached_entry.get("explanation"):
            return {
                "provider": cached_entry.get("provider", resolved_provider),
                "model": cached_entry.get("model", resolved_model),
                "ground_truth_value": cached_entry.get("ground_truth_value", correct_value),
                "explanation": cached_entry.get("explanation", ""),
                "key_evidence": cached_entry.get("key_evidence", []),
                "cache_hit": True,
                "generated_at": cached_entry.get("generated_at"),
            }

    context = {
        "feedback_item_id": getattr(feedback_item, "id", None),
        "item_id": getattr(feedback_item, "itemId", None),
        "initial_answer_value": getattr(feedback_item, "initialAnswerValue", "") or "",
        "final_answer_value": getattr(feedback_item, "finalAnswerValue", "") or "",
        "predicted_value": predicted_value or "",
        "correct_value": correct_value or "",
        "edit_comment": getattr(feedback_item, "editCommentValue", "") or "",
        "initial_comment": initial_comment or "",
        "final_comment": final_comment or "",
        "original_explanation": original_explanation or "",
        "score_explanation": score_explanation or "",
        "score_guidelines_text": score_guidelines_text or "",
        "scorecard_guidance_text": scorecard_guidance_text or "",
        "transcript_text": transcript_text or "",
        "item_metadata_snapshot": item_metadata_snapshot or "",
    }

    generation_mode = "model"
    provider_used = resolved_provider
    model_used = resolved_model

    if resolved_provider == "heuristic":
        generated_payload = _build_heuristic_explanation(context)
        generation_mode = "heuristic"
    else:
        prompt = _build_feedback_item_explanation_prompt(context)
        try:
            if resolved_provider == "openai":
                generated_payload = await asyncio.to_thread(
                    _invoke_openai_explanation_model,
                    prompt,
                    resolved_model,
                )
            else:
                generated_payload = await asyncio.to_thread(
                    _invoke_bedrock_explanation_model,
                    prompt,
                    resolved_model,
                )
        except Exception as exc:
            if not provider_was_auto:
                raise
            logger.warning(
                "Feedback explanation model call failed for feedback_item_id=%s (%s:%s): %s. "
                "Using heuristic generation for this item.",
                getattr(feedback_item, "id", "unknown"),
                resolved_provider,
                resolved_model,
                exc,
            )
            generated_payload = _build_heuristic_explanation(context)
            provider_used = "heuristic"
            model_used = DEFAULT_HEURISTIC_MODEL
            generation_mode = "heuristic"

    explanation = str(generated_payload.get("explanation") or "").strip()
    if not explanation:
        generated_payload = _build_heuristic_explanation(context)
        explanation = generated_payload["explanation"]
        if provider_used != "heuristic":
            generation_mode = "heuristic"
            provider_used = "heuristic"
            model_used = DEFAULT_HEURISTIC_MODEL

    ground_truth_value = (
        str(generated_payload.get("ground_truth_value") or "").strip()
        or str(context.get("correct_value") or "").strip()
        or str(getattr(feedback_item, "finalAnswerValue", "") or "").strip()
    )

    key_evidence = generated_payload.get("key_evidence")
    if not isinstance(key_evidence, list):
        key_evidence = []

    generated_at = datetime.now(timezone.utc).isoformat()
    entry = {
        "provider": provider_used,
        "model": model_used,
        "prompt_version": EXPLANATION_PROMPT_VERSION,
        "ground_truth_value": ground_truth_value,
        "explanation": explanation,
        "key_evidence": key_evidence[:3],
        "generated_at": generated_at,
        "generation_mode": generation_mode,
    }

    updated_metadata = _store_cache_entry(metadata, entry)
    setattr(feedback_item, "metadata", updated_metadata)

    if api_client and getattr(feedback_item, "id", None):
        from plexus.dashboard.api.models.feedback_item import FeedbackItem

        updated_item = await asyncio.to_thread(
            FeedbackItem._update_feedback_item,
            api_client,
            feedback_item.id,
            {"metadata": updated_metadata},
        )
        if updated_item is not None and getattr(updated_item, "metadata", None) is not None:
            setattr(feedback_item, "metadata", updated_item.metadata)

    return {
        "provider": provider_used,
        "model": model_used,
        "ground_truth_value": ground_truth_value,
        "explanation": explanation,
        "key_evidence": entry["key_evidence"],
        "cache_hit": False,
        "generated_at": generated_at,
    }


async def hydrate_feedback_item_explanations(
    *,
    feedback_items: List[Any],
    api_client: Optional[Any],
    score_results_by_item_id: Optional[Dict[str, Dict[str, Any]]] = None,
    score_results_by_feedback_id: Optional[Dict[str, Dict[str, Any]]] = None,
    original_explanations_by_feedback_id: Optional[Dict[str, str]] = None,
    transcript_by_item_id: Optional[Dict[str, str]] = None,
    item_metadata_snapshot_by_item_id: Optional[Dict[str, str]] = None,
    score_guidelines_text: str = "",
    scorecard_guidance_text: str = "",
    provider: Optional[str] = "auto",
    model: Optional[str] = None,
    max_concurrent: int = 8,
) -> Dict[str, Dict[str, Any]]:
    """Hydrate explanation cache for each feedback item and return explanation payloads."""
    sem = asyncio.Semaphore(max(1, max_concurrent))
    results: Dict[str, Dict[str, Any]] = {}

    async def hydrate_one(item: Any) -> None:
        async with sem:
            score_payload = {}
            if score_results_by_feedback_id:
                score_payload = score_results_by_feedback_id.get(getattr(item, "id", ""), {}) or {}
            if not score_payload and score_results_by_item_id:
                score_payload = score_results_by_item_id.get(getattr(item, "itemId", ""), {}) or {}

            predicted_value = (
                str(score_payload.get("value") or "").strip()
                or str(getattr(item, "initialAnswerValue", "") or "").strip()
            )
            correct_value = (
                str(score_payload.get("human_label") or "").strip()
                or str(getattr(item, "finalAnswerValue", "") or "").strip()
            )

            explanation_payload = await get_or_generate_feedback_item_explanation(
                feedback_item=item,
                api_client=api_client,
                predicted_value=predicted_value,
                correct_value=correct_value,
                score_explanation=str(score_payload.get("explanation") or "").strip(),
                original_explanation=(original_explanations_by_feedback_id or {}).get(getattr(item, "id", ""), ""),
                score_guidelines_text=score_guidelines_text,
                scorecard_guidance_text=scorecard_guidance_text,
                transcript_text=(transcript_by_item_id or {}).get(getattr(item, "itemId", ""), ""),
                item_metadata_snapshot=(item_metadata_snapshot_by_item_id or {}).get(getattr(item, "itemId", ""), ""),
                initial_comment=str(getattr(item, "initialCommentValue", "") or "").strip(),
                final_comment=str(getattr(item, "finalCommentValue", "") or "").strip(),
                provider=provider,
                model=model,
            )
            if getattr(item, "id", None):
                results[item.id] = explanation_payload

    await asyncio.gather(*[hydrate_one(item) for item in feedback_items])
    return results
