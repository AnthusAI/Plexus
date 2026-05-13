"""Shared feedback-item explanation generation and cache persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from plexus.bedrock_models import CLAUDE_HAIKU_45_MODEL_ID

logger = logging.getLogger(__name__)

EXPLANATION_CACHE_METADATA_KEY = "feedback_item_explanations"
EXPLANATION_PROMPT_VERSION = "v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_BEDROCK_MODEL = CLAUDE_HAIKU_45_MODEL_ID
DEFAULT_HEURISTIC_MODEL = "feedback-item-explainer-v1"
DEFAULT_EXPLANATION_TOTAL_TIMEOUT_SECONDS = 24 * 60 * 60
DEFAULT_EXPLANATION_ATTEMPT_TIMEOUT_SECONDS = 300.0
DEFAULT_EXPLANATION_RETRY_INITIAL_BACKOFF_SECONDS = 2.0
DEFAULT_EXPLANATION_RETRY_MAX_BACKOFF_SECONDS = 60.0
_RETRYABLE_HTTP_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_NON_RETRYABLE_HTTP_STATUS_CODES = {400, 401, 403, 404, 422}
_RETRYABLE_ERROR_CODE_TOKENS = {
    "throttling",
    "toomanyrequests",
    "ratelimit",
    "requesttimeout",
    "timeout",
    "serviceunavailable",
    "internalserver",
    "temporarilyunavailable",
    "modeltimeout",
    "modelnotready",
}
_NON_RETRYABLE_ERROR_CODE_TOKENS = {
    "accessdenied",
    "authentication",
    "unauthorized",
    "forbidden",
    "invalidapi",
    "invalidrequest",
    "validation",
    "modelnotfound",
}
_RETRYABLE_EXCEPTION_NAME_TOKENS = (
    "timeout",
    "connection",
    "connect",
    "temporar",
    "serviceunavailable",
    "ratelimit",
    "throttl",
)
_NON_RETRYABLE_MESSAGE_TOKENS = (
    "invalid api key",
    "incorrect api key",
    "authentication",
    "unauthorized",
    "forbidden",
    "access denied",
    "model not found",
    "unknown model",
    "invalid model",
)
_RETRYABLE_PARSE_MESSAGE_TOKENS = (
    "json",
    "parse",
    "decode",
    "schema",
    "missing explanation",
    "must be a json object",
    "no usable response",
    "empty response",
)


@dataclass
class FeedbackItemExplanationTimeoutError(RuntimeError):
    provider: str
    model: str
    attempt_count: int
    elapsed_seconds: float
    last_error_type: str
    last_error_message: str
    feedback_item_id: Optional[str] = None

    @property
    def diagnostics(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "attempt_count": self.attempt_count,
            "elapsed_seconds": self.elapsed_seconds,
            "last_error_type": self.last_error_type,
            "last_error_message": self.last_error_message,
            "feedback_item_id": self.feedback_item_id,
        }

    def __str__(self) -> str:
        details = (
            f"provider={self.provider} model={self.model} attempts={self.attempt_count} "
            f"elapsed_seconds={self.elapsed_seconds:.3f} last_error_type={self.last_error_type}"
        )
        if self.feedback_item_id:
            details += f" feedback_item_id={self.feedback_item_id}"
        return f"Feedback explanation generation timed out after retries ({details})."


def _load_float_env(name: str, default: float, *, minimum: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %s.", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%s is below minimum %s; using default %s.", name, value, minimum, default)
        return default
    return value


def _get_status_code(exc: BaseException) -> Optional[int]:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    if response is not None:
        response_status = getattr(response, "status_code", None)
        if isinstance(response_status, int):
            return response_status
        if isinstance(response, dict):
            metadata = response.get("ResponseMetadata", {}) or {}
            metadata_status = metadata.get("HTTPStatusCode")
            if isinstance(metadata_status, int):
                return metadata_status
    return None


def _extract_error_code(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error", {}) or {}
        code = error.get("Code")
        if code:
            return str(code).strip()
    code_attr = getattr(exc, "code", None)
    if code_attr:
        return str(code_attr).strip()
    return ""


def _is_retryable_parse_error(exc: BaseException) -> bool:
    if isinstance(exc, json.JSONDecodeError):
        return True
    if not isinstance(exc, ValueError):
        return False
    message = str(exc).lower()
    return any(token in message for token in _RETRYABLE_PARSE_MESSAGE_TOKENS)


def _is_non_retryable_message(exc: BaseException) -> bool:
    message = str(exc).lower()
    if not message:
        return False
    return any(token in message for token in _NON_RETRYABLE_MESSAGE_TOKENS)


def _is_retryable_generation_error(exc: BaseException) -> bool:
    if isinstance(exc, asyncio.TimeoutError):
        return True
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, ConnectionError):
        return True
    if _is_retryable_parse_error(exc):
        return True

    status_code = _get_status_code(exc)
    if status_code in _RETRYABLE_HTTP_STATUS_CODES:
        return True
    if status_code in _NON_RETRYABLE_HTTP_STATUS_CODES:
        return False

    error_code = _extract_error_code(exc).replace(" ", "").lower()
    if error_code:
        if any(token in error_code for token in _NON_RETRYABLE_ERROR_CODE_TOKENS):
            return False
        if any(token in error_code for token in _RETRYABLE_ERROR_CODE_TOKENS):
            return True

    if _is_non_retryable_message(exc):
        return False

    type_name = type(exc).__name__.lower()
    if any(token in type_name for token in _RETRYABLE_EXCEPTION_NAME_TOKENS):
        return True

    return False


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


def _resolve_provider_and_model(provider: Optional[str], model: Optional[str]) -> Tuple[str, str]:
    requested = (provider or "auto").strip().lower()
    if requested not in {"auto", "openai", "bedrock", "heuristic", "local"}:
        raise ValueError(
            "feedback explanation provider must be one of: auto, openai, bedrock, heuristic"
        )

    if requested == "auto":
        if os.getenv("OPENAI_API_KEY"):
            return "openai", model or DEFAULT_OPENAI_MODEL
        if os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE") or os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE"):
            return "bedrock", model or DEFAULT_BEDROCK_MODEL
        return "heuristic", model or DEFAULT_HEURISTIC_MODEL

    if requested in {"heuristic", "local"}:
        return "heuristic", model or DEFAULT_HEURISTIC_MODEL
    if requested == "openai":
        return "openai", model or DEFAULT_OPENAI_MODEL
    return "bedrock", model or DEFAULT_BEDROCK_MODEL


def _invoke_openai_explanation_model(
    prompt: str,
    model: str,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
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
        timeout=timeout_seconds,
    )
    return _parse_json_object(response.output_text)


def _invoke_bedrock_explanation_model(
    prompt: str,
    model: str,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    import boto3
    from botocore.config import Config as BotoConfig

    client_kwargs: Dict[str, Any] = {"region_name": os.getenv("AWS_REGION") or "us-east-1"}
    if timeout_seconds is not None:
        bounded_timeout = max(1.0, float(timeout_seconds))
        client_kwargs["config"] = BotoConfig(
            connect_timeout=min(10.0, bounded_timeout),
            read_timeout=bounded_timeout,
        )

    bedrock = boto3.client("bedrock-runtime", **client_kwargs)
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


def _build_feedback_explanation_timeout_error(
    *,
    provider: str,
    model: str,
    attempt_count: int,
    started_at: float,
    last_error: BaseException,
    feedback_item_id: Optional[str],
) -> FeedbackItemExplanationTimeoutError:
    elapsed = max(0.0, time.monotonic() - started_at)
    return FeedbackItemExplanationTimeoutError(
        provider=provider,
        model=model,
        attempt_count=attempt_count,
        elapsed_seconds=elapsed,
        last_error_type=type(last_error).__name__,
        last_error_message=str(last_error),
        feedback_item_id=feedback_item_id,
    )


async def _invoke_model_explanation_with_retry(
    *,
    provider: str,
    model: str,
    prompt: str,
    feedback_item_id: Optional[str],
) -> Dict[str, Any]:
    total_timeout_seconds = _load_float_env(
        "PLEXUS_FEEDBACK_EXPLANATION_TOTAL_TIMEOUT_SECONDS",
        float(DEFAULT_EXPLANATION_TOTAL_TIMEOUT_SECONDS),
        minimum=1e-3,
    )
    attempt_timeout_seconds = _load_float_env(
        "PLEXUS_FEEDBACK_EXPLANATION_ATTEMPT_TIMEOUT_SECONDS",
        DEFAULT_EXPLANATION_ATTEMPT_TIMEOUT_SECONDS,
        minimum=1e-3,
    )
    initial_backoff_seconds = _load_float_env(
        "PLEXUS_FEEDBACK_EXPLANATION_RETRY_INITIAL_BACKOFF_SECONDS",
        DEFAULT_EXPLANATION_RETRY_INITIAL_BACKOFF_SECONDS,
        minimum=0.0,
    )
    max_backoff_seconds = _load_float_env(
        "PLEXUS_FEEDBACK_EXPLANATION_RETRY_MAX_BACKOFF_SECONDS",
        DEFAULT_EXPLANATION_RETRY_MAX_BACKOFF_SECONDS,
        minimum=0.0,
    )
    if max_backoff_seconds < initial_backoff_seconds:
        max_backoff_seconds = initial_backoff_seconds

    started_at = time.monotonic()
    deadline = started_at + total_timeout_seconds
    attempt_count = 0
    sleep_seconds = initial_backoff_seconds
    last_error: Optional[BaseException] = None

    while True:
        now = time.monotonic()
        remaining_budget = deadline - now
        if remaining_budget <= 0 and last_error is not None:
            raise _build_feedback_explanation_timeout_error(
                provider=provider,
                model=model,
                attempt_count=attempt_count,
                started_at=started_at,
                last_error=last_error,
                feedback_item_id=feedback_item_id,
            ) from last_error
        if remaining_budget <= 0:
            raise FeedbackItemExplanationTimeoutError(
                provider=provider,
                model=model,
                attempt_count=attempt_count,
                elapsed_seconds=max(0.0, time.monotonic() - started_at),
                last_error_type="TimeoutError",
                last_error_message="Deadline exceeded before any provider attempts completed.",
                feedback_item_id=feedback_item_id,
            )

        attempt_count += 1
        per_attempt_timeout = min(attempt_timeout_seconds, max(1e-3, remaining_budget))
        try:
            if provider == "openai":
                payload = await asyncio.wait_for(
                    asyncio.to_thread(
                        _invoke_openai_explanation_model,
                        prompt,
                        model,
                        per_attempt_timeout,
                    ),
                    timeout=per_attempt_timeout + 1.0,
                )
            else:
                payload = await asyncio.wait_for(
                    asyncio.to_thread(
                        _invoke_bedrock_explanation_model,
                        prompt,
                        model,
                        per_attempt_timeout,
                    ),
                    timeout=per_attempt_timeout + 1.0,
                )
            explanation = str(payload.get("explanation") or "").strip()
            if not explanation:
                raise ValueError("Model response missing explanation text")
            return payload
        except Exception as exc:
            last_error = exc
            retryable = _is_retryable_generation_error(exc)
            if not retryable:
                logger.error(
                    "Feedback explanation generation failed with a non-retryable error for "
                    "feedback_item_id=%s provider=%s model=%s attempt=%s: %s: %s",
                    feedback_item_id,
                    provider,
                    model,
                    attempt_count,
                    type(exc).__name__,
                    exc,
                )
                raise

            remaining_budget = deadline - time.monotonic()
            if remaining_budget <= 0:
                raise _build_feedback_explanation_timeout_error(
                    provider=provider,
                    model=model,
                    attempt_count=attempt_count,
                    started_at=started_at,
                    last_error=exc,
                    feedback_item_id=feedback_item_id,
                ) from exc

            jitter = 0.0
            if sleep_seconds > 0:
                jitter = random.uniform(0.0, min(1.0, sleep_seconds * 0.2))
            wait_seconds = min(remaining_budget, sleep_seconds + jitter)
            logger.warning(
                "Feedback explanation generation retryable failure for feedback_item_id=%s provider=%s model=%s "
                "(attempt %s, remaining %.1fs): %s: %s. Retrying in %.2fs.",
                feedback_item_id,
                provider,
                model,
                attempt_count,
                max(0.0, remaining_budget),
                type(exc).__name__,
                exc,
                max(0.0, wait_seconds),
            )
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            sleep_seconds = min(max_backoff_seconds, max(initial_backoff_seconds, sleep_seconds * 2))


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
    resolved_provider, resolved_model = _resolve_provider_and_model(provider, model)

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
        generated_payload = await _invoke_model_explanation_with_retry(
            provider=resolved_provider,
            model=resolved_model,
            prompt=prompt,
            feedback_item_id=getattr(feedback_item, "id", None),
        )

    explanation = str(generated_payload.get("explanation") or "").strip()
    if not explanation:
        raise ValueError("Generated feedback explanation payload is missing explanation text")

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
