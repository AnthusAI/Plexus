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

    DEFAULT_MODEL = "gpt-5-mini"
    VALID_STATUSES = {"consistent", "potential_conflict", "inconclusive"}

    def __init__(
        self,
        *,
        invoke_model: Optional[Callable[[str, str], str]] = None,
        model: str = DEFAULT_MODEL,
    ):
        self._invoke_model = invoke_model or self._invoke_openai
        self._model = model

    def generate(self, request: ScoreRubricConsistencyRequest) -> ScoreRubricConsistencyResult:
        prompt = self._build_prompt(request)
        raw_text = self._invoke_model(prompt, self._model)
        try:
            parsed = self._parse_response(raw_text)
        except json.JSONDecodeError:
            repair_prompt = (
                f"{prompt}\n\nYour prior response was not valid JSON:\n"
                f"{_truncate(raw_text or '(empty response)', 1000)}\n\n"
                "Return ONLY valid JSON with exactly these keys: status, paragraph."
            )
            raw_text = self._invoke_model(repair_prompt, self._model)
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

    def _invoke_openai(self, prompt: str, model: str) -> str:
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(override=False)
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.responses.create(
            model=model,
            reasoning={"effort": "low"},
            input=[{"role": "user", "content": prompt}],
            max_output_tokens=2000,
        )
        return (response.output_text or "").strip()


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
