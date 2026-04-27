from __future__ import annotations

import json
import os
import ast
from pathlib import Path
from typing import Protocol, Sequence

from .models import (
    ConfidenceInputs,
    EvidenceSnippet,
    RubricEvidencePack,
    RubricEvidencePackRequest,
    RubricHistoryEvent,
)


class RubricEvidenceSynthesizer(Protocol):
    async def synthesize(
        self,
        *,
        request: RubricEvidencePackRequest,
        evidence: Sequence[EvidenceSnippet],
        history: Sequence[RubricHistoryEvent],
        confidence_inputs: ConfidenceInputs,
    ) -> RubricEvidencePack:
        """Interpret shaped evidence and return a structured pack."""


class TactusRubricEvidenceSynthesizer:
    """Run the repo-owned Tactus synthesis procedure for evidence packs."""

    def __init__(
        self,
        *,
        provider: str = "openai",
        model: str = "gpt-5-mini",
        procedure_id: str = "rubric_evidence_pack_synthesis",
        max_tokens: int = 12000,
    ):
        self.provider = provider
        self.model = model
        self.procedure_id = procedure_id
        self.max_tokens = max_tokens

    async def synthesize(
        self,
        *,
        request: RubricEvidencePackRequest,
        evidence: Sequence[EvidenceSnippet],
        history: Sequence[RubricHistoryEvent],
        confidence_inputs: ConfidenceInputs,
    ) -> RubricEvidencePack:
        from tactus.adapters.memory import MemoryStorage
        from tactus.core.runtime import TactusRuntime

        tac_source = self._load_tac_source()
        payload = {
            "request": request.model_dump(mode="json"),
            "evidence": [
                snippet.model_dump(mode="json") for snippet in evidence
            ],
            "chronological_evidence": [
                event.model_dump(mode="json") for event in history
            ],
            "confidence_inputs": confidence_inputs.model_dump(mode="json"),
            "output_template": {
                "score_version_id": request.score_version_id,
                "rubric_reading": "",
                "evidence_classification": "rubric_gap",
                "supporting_evidence": [],
                "conflicting_evidence": [],
                "history_of_change": [
                    event.model_dump(mode="json") for event in history
                ],
                "likely_reason_for_disagreement": "",
                "confidence": confidence_inputs.suggested_confidence.value,
                "confidence_inputs": confidence_inputs.model_dump(mode="json"),
                "open_questions": [],
            },
            "output_contract": {
                "required_top_level_fields": [
                    "score_version_id",
                    "rubric_reading",
                    "evidence_classification",
                    "supporting_evidence",
                    "conflicting_evidence",
                    "history_of_change",
                    "likely_reason_for_disagreement",
                    "confidence",
                    "confidence_inputs",
                    "open_questions",
                ],
                "evidence_classification_values": [
                    "rubric_supported",
                    "rubric_conflicting",
                    "rubric_gap",
                    "historical_context",
                    "possible_stale_rubric",
                ],
                "confidence_values": ["low", "medium", "high"],
            },
        }
        synthesis_prompt = self._build_synthesis_prompt(payload)
        runtime = TactusRuntime(
            procedure_id=self.procedure_id,
            storage_backend=MemoryStorage(),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        result = await runtime.execute(
            tac_source,
            context={
                "synthesis_input_json": synthesis_prompt,
            },
            format="lua",
        )
        raw_text = self._extract_text(result)
        parsed = json.loads(self._strip_json_fence(raw_text))
        return RubricEvidencePack.model_validate(parsed)

    def _load_tac_source(self) -> str:
        tac_path = (
            Path(__file__).resolve().parent
            / "procedures"
            / "rubric_evidence_synthesis.tac"
        )
        tac_template = tac_path.read_text(encoding="utf-8")
        return (
            tac_template.replace("{{PROVIDER}}", self.provider)
            .replace("{{MODEL}}", self.model)
            .replace("{{MAX_TOKENS}}", str(self.max_tokens))
        )

    def _build_synthesis_prompt(self, payload: dict) -> str:
        return (
            "Synthesize a RubricEvidencePack from the following context.\n\n"
            "Official rubric authority and disputed item:\n"
            f"{json.dumps(payload['request'], ensure_ascii=False, indent=2)}\n\n"
            "Retrieved corpus evidence with provenance:\n"
            f"{json.dumps(payload['evidence'], ensure_ascii=False, indent=2)}\n\n"
            "Chronological evidence events:\n"
            f"{json.dumps(payload['chronological_evidence'], ensure_ascii=False, indent=2)}\n\n"
            "Confidence inputs computed by Python:\n"
            f"{json.dumps(payload['confidence_inputs'], ensure_ascii=False, indent=2)}\n\n"
            "Use this exact JSON object shape for pack_json. Fill empty strings and "
            "choose the top-level classification based on the context. Leave "
            "supporting_evidence and conflicting_evidence empty; Python attaches "
            "retrieved provenance after synthesis:\n"
            f"{json.dumps(payload['output_template'], ensure_ascii=False, indent=2)}\n\n"
            "Allowed classifications: "
            + ", ".join(payload["output_contract"]["evidence_classification_values"])
            + ". Allowed confidence values: "
            + ", ".join(payload["output_contract"]["confidence_values"])
            + ". Do not copy raw evidence objects into the output JSON."
        )

    def _extract_text(self, result: object) -> str:
        procedure_output = result.get("result", result) if isinstance(result, dict) else result
        if isinstance(procedure_output, dict):
            raw_text = procedure_output.get("text", "")
        else:
            raw_text = str(procedure_output or "")
        if isinstance(raw_text, dict):
            raw_text = raw_text.get("reason", "") or ""
        text = str(raw_text or "").strip()
        text = self._extract_done_reason(text)
        if not text:
            raise ValueError("Rubric evidence synthesis returned empty output.")
        if "<lua table at " in text.lower():
            raise ValueError("Rubric evidence synthesis returned a Lua table pointer.")
        return text

    def _extract_done_reason(self, text: str) -> str:
        if not text.startswith("{") or "'args'" not in text:
            return text
        try:
            call = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return text
        if not isinstance(call, dict):
            return text
        args = call.get("args")
        if not isinstance(args, dict):
            return text
        reason = args.get("pack_json") or args.get("reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
        if call.get("name") == "finish":
            raise ValueError(
                "Rubric evidence synthesis called finish without pack_json."
            )
        return text

    def _strip_json_fence(self, text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("Rubric evidence synthesis returned an invalid JSON fence.")
        return "\n".join(lines[1:-1]).strip()
