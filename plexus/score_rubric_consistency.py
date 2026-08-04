"""Score-version rubric consistency checks.

This module owns the lightweight preflight that asks whether the score code for a
specific ScoreVersion appears consistent with that same version's rubric text.
The result is designed to be persisted on Evaluation.parameters and displayed as
operator context before RCA.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class ScoreRubricConsistencyRequest:
    scorecard_identifier: str
    score_identifier: str
    score_version_id: str
    rubric_text: str
    score_code: str
    item_text: str = ""


@dataclass(frozen=True)
class ScoreRubricConsistencyResult:
    scorecard_identifier: str
    score_identifier: str
    score_version_id: str
    status: str
    paragraph: str
    checked_at: str
    model: str
    diagnostics: Dict[str, Any]

    def to_parameters_payload(self) -> Dict[str, Any]:
        return asdict(self)


class ScoreRubricConsistencyService:
    """Generate a concise score-code vs rubric consistency assessment."""

    DEFAULT_MODEL = "gpt-5-mini-2025-08-07"
    MAX_INPUT_TOKENS = 36_000
    MAX_OUTPUT_TOKENS = 2_000
    MAX_ATTEMPTS = 2
    VALID_STATUSES = {"consistent", "potential_conflict", "inconclusive"}

    def __init__(
        self,
        *,
        invoke_model: Optional[Callable[[str, str], str]] = None,
        model: str = DEFAULT_MODEL,
        semantic_authority: Any = None,
        openai_client_factory: Optional[Callable[[], Any]] = None,
        token_counter: Optional[Callable[[str, str], int]] = None,
        max_input_tokens: int = MAX_INPUT_TOKENS,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ):
        self._invoke_model = invoke_model
        self._model = model
        self._semantic_authority = semantic_authority
        self._openai_client_factory = openai_client_factory
        self._token_counter = token_counter or self._count_input_tokens
        self._max_input_tokens = max_input_tokens
        self._max_output_tokens = max_output_tokens
        if invoke_model is None and model != self.DEFAULT_MODEL:
            raise ValueError("rubric consistency requires the exact authorized model revision")

    def generate(self, request: ScoreRubricConsistencyRequest) -> ScoreRubricConsistencyResult:
        prompt = self._build_prompt(request)
        raw_text = self._invoke(prompt, attempt=1)
        try:
            parsed = self._parse_response(raw_text)
        except json.JSONDecodeError:
            repair_prompt = (
                f"{prompt}\n\nYour prior response was not valid JSON:\n"
                f"{_truncate(raw_text or '(empty response)', 1000)}\n\n"
                "Return ONLY valid JSON with exactly these keys: status, paragraph."
            )
            raw_text = self._invoke(repair_prompt, attempt=2)
            parsed = self._parse_response(raw_text)
        status = str(parsed.get("status") or "inconclusive").strip()
        if status not in self.VALID_STATUSES:
            status = "inconclusive"
        paragraph = _compact_paragraph(str(parsed.get("paragraph") or ""))
        if not paragraph:
            paragraph = "The consistency check did not produce a usable assessment."
            status = "inconclusive"
        return ScoreRubricConsistencyResult(
            scorecard_identifier=request.scorecard_identifier,
            score_identifier=request.score_identifier,
            score_version_id=request.score_version_id,
            status=status,
            paragraph=paragraph,
            checked_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            model=self._model,
            diagnostics={
                "rubric_characters": len(request.rubric_text or ""),
                "score_code_characters": len(request.score_code or ""),
                "item_context_characters": len(request.item_text or ""),
            },
        )

    def generate_from_api(
        self,
        *,
        client: Any,
        scorecard_identifier: str,
        score_identifier: str,
        score_id: str,
        score_version_id: str,
        item_text: str = "",
    ) -> ScoreRubricConsistencyResult:
        version = fetch_score_version_for_consistency(client, score_version_id)
        return self.generate(
            ScoreRubricConsistencyRequest(
                scorecard_identifier=scorecard_identifier,
                score_identifier=score_identifier,
                score_version_id=score_version_id,
                rubric_text=version.get("guidelines") or "",
                score_code=version.get("configuration") or "",
                item_text=item_text or "",
            )
        )

    def _build_prompt(self, request: ScoreRubricConsistencyRequest) -> str:
        item_section = ""
        if request.item_text:
            item_section = (
                "\nOptional item context for a spot-check:\n"
                f"{_truncate(request.item_text, 4000)}\n"
            )
        return (
            "You are checking one Plexus ScoreVersion before evaluation.\n"
            "Compare the score code/prompt against the rubric text stored on the same ScoreVersion.\n"
            "Identify only meaningful policy mismatches that could affect evaluation results. "
            "Do not critique style, formatting, implementation architecture, or missing tests.\n\n"
            "Evaluate the complete end-to-end decision path, including prompts, graph routing, "
            "mappings, and final outputs. An internal classifier does not need to expose every "
            "final score label when its branch mapping deliberately produces the final label; "
            "for example, a binary eligibility node may route an absent question to final NA. "
            "Do not confuse that internal label domain with the final score domain. A supplemental "
            "deterministic gate may add narrow precision checks without replacing the broader "
            "classifier prompt, so do not treat that gate as the whole policy. Evaluate all paths "
            "together. Finally, do not infer unsupported production input variants, metadata keys, "
            "or value formats. If a claimed mismatch depends on an unstated input contract, return "
            "inconclusive and explain what a human must verify.\n\n"
            "Return ONLY JSON with exactly these keys:\n"
            '  "status": one of "consistent", "potential_conflict", "inconclusive"\n'
            '  "paragraph": one short paragraph, 2-4 sentences, no headings or bullets\n\n'
            f"Scorecard: {request.scorecard_identifier}\n"
            f"Score: {request.score_identifier}\n"
            f"ScoreVersion: {request.score_version_id}\n\n"
            f"Rubric text:\n{_truncate(request.rubric_text, 12000)}\n\n"
            f"Score code/configuration:\n{_truncate(request.score_code, 16000)}\n"
            f"{item_section}"
        )

    def _parse_response(self, text: str) -> Dict[str, Any]:
        cleaned = (text or "").strip()
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
            if match:
                cleaned = match.group(1).strip()
        obj_match = re.search(r"\{[\s\S]*\}", cleaned)
        if obj_match:
            cleaned = obj_match.group(0)
        return json.loads(cleaned)

    def _invoke(self, prompt: str, *, attempt: int) -> str:
        if self._invoke_model is not None:
            return self._invoke_model(prompt, self._model)
        return self._invoke_openai_budgeted(prompt, attempt=attempt)

    def _invoke_openai_budgeted(self, prompt: str, *, attempt: int) -> str:
        from dotenv import load_dotenv
        from openai import OpenAI
        from plexus.optimization.semantic_authority import SemanticOutcomeUnknown
        from plexus.optimization.semantic_budget import SemanticUsage

        if self._semantic_authority is None:
            raise RuntimeError(
                "rubric consistency model invocation requires semantic budget authority"
            )
        request_payload = {
            "model": self._model,
            "reasoning": {"effort": "low"},
            "input": [{"role": "user", "content": prompt}],
            "max_output_tokens": self._max_output_tokens,
        }
        measured_model_tokens = self._token_counter(request_payload, self._model)
        from plexus.optimization.semantic_budget import canonical_json_bytes

        conservative_input_bound = max(
            measured_model_tokens,
            len(canonical_json_bytes(request_payload)),
        )
        if conservative_input_bound > self._max_input_tokens:
            raise ValueError("rubric consistency input exceeds max_input_tokens")
        plan = self._semantic_authority.direct_plan(
            attempt=attempt,
            max_input_tokens=self._max_input_tokens,
            max_output_tokens=self._max_output_tokens,
            request_payload=request_payload,
        )
        decision = self._semantic_authority.reserve_direct(plan)
        if decision.status == "replay":
            replay = decision.replay_payload or {}
            if replay.get("kind") != "plexus-direct-response":
                raise RuntimeError("rubric consistency replay payload is invalid")
            return str(replay.get("output_text") or "")

        load_dotenv(override=False)
        client = (
            self._openai_client_factory()
            if self._openai_client_factory is not None
            else OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=0)
        )
        try:
            response = client.responses.create(**request_payload)
        except Exception as exc:
            self._semantic_authority.unknown_direct(
                decision.reservation_id, reason=str(exc)
            )
            raise SemanticOutcomeUnknown(
                "rubric consistency provider outcome is unknown"
            ) from exc
        output_text = str(getattr(response, "output_text", "") or "").strip()
        try:
            usage = getattr(response, "usage", None)
            if usage is None:
                raise ValueError("provider response has no usage")
            input_tokens = _usage_int(usage, "input_tokens")
            output_tokens = _usage_int(usage, "output_tokens")
            details = _usage_value(usage, "input_tokens_details") or {}
            cached_tokens = _usage_int(details, "cached_tokens", default=0)
            self._semantic_authority.settle_direct(
                decision.reservation_id,
                SemanticUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=cached_tokens,
                    provider_request_id=(
                        str(getattr(response, "id", "") or "") or None
                    ),
                ),
                output_text=output_text,
            )
        except Exception as exc:
            self._semantic_authority.unknown_direct(
                decision.reservation_id, reason=str(exc)
            )
            raise SemanticOutcomeUnknown(
                "rubric consistency usage settlement is incomplete"
            ) from exc
        return output_text

    @staticmethod
    def _count_input_tokens(request_payload: Any, model: str) -> int:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
        # Canonical payload byte length is checked separately as a conservative
        # ceiling that includes Responses role/framing fields.
        input_rows = request_payload.get("input") if isinstance(request_payload, dict) else []
        prompt = "\n".join(
            str(row.get("content") or "")
            for row in input_rows or []
            if isinstance(row, dict)
        )
        return len(encoding.encode(prompt))


def fetch_score_version_for_consistency(client: Any, score_version_id: str) -> Dict[str, Any]:
    query = """
    query GetScoreVersionForRubricConsistency($id: ID!) {
        getScoreVersion(id: $id) {
            id
            configuration
            guidelines
            note
            score {
                id
                name
            }
        }
    }
    """
    result = client.execute(query, {"id": score_version_id})
    version = (result or {}).get("getScoreVersion")
    if not version:
        raise ValueError(f"ScoreVersion not found: {score_version_id}")
    return version


def merge_consistency_result_into_parameters(
    parameters: Any,
    result: ScoreRubricConsistencyResult,
) -> Dict[str, Any]:
    if isinstance(parameters, str):
        try:
            merged = json.loads(parameters) if parameters else {}
        except Exception:
            merged = {}
    elif isinstance(parameters, dict):
        merged = dict(parameters)
    else:
        merged = {}
    merged["score_rubric_consistency_check"] = result.to_parameters_payload()
    return merged


def _truncate(value: str, limit: int) -> str:
    value = value or ""
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated]"


def _compact_paragraph(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:1200]


def _usage_value(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _usage_int(value: Any, name: str, *, default: int | None = None) -> int:
    raw = _usage_value(value, name)
    if raw is None and default is not None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise ValueError(f"provider usage {name} is missing or invalid")
    return raw
