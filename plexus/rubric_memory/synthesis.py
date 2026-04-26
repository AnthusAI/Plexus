from __future__ import annotations

import json
import os
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
        provider: str = "bedrock",
        model: str = "anthropic.claude-3-haiku-20240307-v1:0",
        procedure_id: str = "rubric_evidence_pack_synthesis",
    ):
        self.provider = provider
        self.model = model
        self.procedure_id = procedure_id

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
            "response_schema": RubricEvidencePack.model_json_schema(),
        }
        runtime = TactusRuntime(
            procedure_id=self.procedure_id,
            storage_backend=MemoryStorage(),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        result = await runtime.execute(
            tac_source,
            context={
                "synthesis_input_json": json.dumps(payload, ensure_ascii=False),
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
        return tac_template.replace("{{PROVIDER}}", self.provider).replace(
            "{{MODEL}}", self.model
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
        if not text:
            raise ValueError("Rubric evidence synthesis returned empty output.")
        if "<lua table at " in text.lower():
            raise ValueError("Rubric evidence synthesis returned a Lua table pointer.")
        return text

    def _strip_json_fence(self, text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("Rubric evidence synthesis returned an invalid JSON fence.")
        return "\n".join(lines[1:-1]).strip()
