from __future__ import annotations

import ast
import hashlib
import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .citations import (
    RubricMemoryCitationContext,
    RubricMemoryCitationValidation,
    validate_rubric_memory_citations,
)


class SMEQuestionGateAction(str, Enum):
    SUPPRESS = "suppress"
    TRANSFORM = "transform"
    KEEP = "keep"


class SMEQuestionAnswerStatus(str, Enum):
    ANSWERED_BY_RUBRIC = "answered_by_rubric"
    ANSWERED_BY_CORPUS = "answered_by_corpus"
    PARTIALLY_ANSWERED = "partially_answered"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    TRUE_OPEN_QUESTION = "true_open_question"


class RubricMemorySMEQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("id", "text")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field cannot be blank")
        return stripped


class RubricMemorySMEQuestionGateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scorecard_identifier: str = Field(min_length=1)
    score_identifier: str = Field(min_length=1)
    score_version_id: str = Field(min_length=1)
    rubric_memory_context: RubricMemoryCitationContext
    candidate_agenda_items: list[RubricMemorySMEQuestion] = Field(default_factory=list)
    optimizer_context: str = ""

    @field_validator(
        "scorecard_identifier",
        "score_identifier",
        "score_version_id",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field cannot be blank")
        return stripped


class RubricMemoryGatedSMEQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    final_text: str = ""
    action: SMEQuestionGateAction
    answer_status: SMEQuestionAnswerStatus
    rationale: str = ""
    citation_ids: list[str] = Field(default_factory=list)
    citation_validation: RubricMemoryCitationValidation | None = None


class RubricMemorySMEQuestionGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_version_id: str = Field(min_length=1)
    final_agenda_markdown: str = Field(min_length=1)
    final_items: list[RubricMemoryGatedSMEQuestion] = Field(default_factory=list)
    suppressed_items: list[RubricMemoryGatedSMEQuestion] = Field(default_factory=list)
    transformed_items: list[RubricMemoryGatedSMEQuestion] = Field(default_factory=list)
    kept_items: list[RubricMemoryGatedSMEQuestion] = Field(default_factory=list)
    citation_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)


class RubricMemorySMEQuestionGateSynthesizer(Protocol):
    async def synthesize(
        self,
        *,
        request: RubricMemorySMEQuestionGateRequest,
    ) -> dict[str, Any]:
        """Classify candidate SME agenda items against rubric-memory evidence."""


class TactusRubricMemorySMEQuestionGateSynthesizer:
    """Run the repo-owned Tactus procedure for SME question gating."""

    def __init__(
        self,
        *,
        provider: str = "bedrock",
        model: str = "us.anthropic.claude-sonnet-4-6",
        procedure_id: str = "rubric_memory_sme_question_gate",
        max_tokens: int = 5000,
    ):
        self.provider = provider
        self.model = model
        self.procedure_id = procedure_id
        self.max_tokens = max_tokens

    async def synthesize(
        self,
        *,
        request: RubricMemorySMEQuestionGateRequest,
    ) -> dict[str, Any]:
        from tactus.adapters.memory import MemoryStorage
        from tactus.core.runtime import TactusRuntime

        tac_source = self._load_tac_source()
        prompt = self._build_prompt(request)
        runtime = TactusRuntime(
            procedure_id=self.procedure_id,
            storage_backend=MemoryStorage(),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        result = await runtime.execute(
            tac_source,
            context={"gate_input_json": prompt},
            format="lua",
        )
        raw_text = self._extract_text(result)
        return json.loads(self._strip_json_fence(raw_text))

    def _load_tac_source(self) -> str:
        tac_path = Path(__file__).resolve().parent / "procedures" / "sme_question_gate.tac"
        tac_template = tac_path.read_text(encoding="utf-8")
        return (
            tac_template.replace("{{PROVIDER}}", self.provider)
            .replace("{{MODEL}}", self.model)
            .replace("{{MAX_TOKENS}}", str(self.max_tokens))
        )

    def _build_prompt(self, request: RubricMemorySMEQuestionGateRequest) -> str:
        citation_index = [
            citation.model_dump(mode="json")
            for citation in request.rubric_memory_context.citation_index
        ]
        payload = {
            "scorecard_identifier": request.scorecard_identifier,
            "score_identifier": request.score_identifier,
            "score_version_id": request.score_version_id,
            "rubric_memory_markdown": request.rubric_memory_context.markdown_context,
            "citation_index": citation_index,
            "candidate_agenda_items": [
                item.model_dump(mode="json") for item in request.candidate_agenda_items
            ],
            "optimizer_context": request.optimizer_context,
            "output_contract": {
                "required_top_level_fields": [
                    "items",
                    "final_agenda_markdown",
                ],
                "item_fields": [
                    "id",
                    "original_text",
                    "final_text",
                    "action",
                    "answer_status",
                    "rationale",
                    "citation_ids",
                ],
                "actions": [action.value for action in SMEQuestionGateAction],
                "answer_statuses": [
                    status.value for status in SMEQuestionAnswerStatus
                ],
            },
        }
        return (
            "Gate proposed SME agenda items against rubric-memory evidence.\n"
            "Return only JSON matching output_contract.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
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
            raise ValueError("SME question gate synthesis returned empty output.")
        if "<lua table at " in text.lower():
            raise ValueError("SME question gate synthesis returned a Lua table pointer.")
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
        if isinstance(args, dict) and args.get("result_json"):
            return str(args["result_json"])
        return text

    def _strip_json_fence(self, text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()


class RubricMemorySMEQuestionGateService:
    """Typed, citation-validating wrapper around SME question gate synthesis."""

    def __init__(
        self,
        *,
        synthesizer: RubricMemorySMEQuestionGateSynthesizer | None = None,
    ):
        self.synthesizer = synthesizer or TactusRubricMemorySMEQuestionGateSynthesizer()

    async def gate(
        self,
        request: RubricMemorySMEQuestionGateRequest,
    ) -> RubricMemorySMEQuestionGateResult:
        raw_result = await self.synthesizer.synthesize(request=request)
        return self._shape_result(raw_result, request)

    def _shape_result(
        self,
        raw_result: dict[str, Any],
        request: RubricMemorySMEQuestionGateRequest,
    ) -> RubricMemorySMEQuestionGateResult:
        raw_items = raw_result.get("items") or []
        if not isinstance(raw_items, list):
            raise ValueError("SME question gate result field 'items' must be a list.")

        by_id = {item.id: item for item in request.candidate_agenda_items}
        shaped_items: list[RubricMemoryGatedSMEQuestion] = []
        diagnostics: list[dict[str, Any]] = []

        for index, raw_item in enumerate(raw_items, 1):
            if not isinstance(raw_item, dict):
                raise ValueError("SME question gate result item must be an object.")
            item_id = str(raw_item.get("id") or f"item-{index}").strip()
            original = by_id.get(item_id)
            original_text = str(
                raw_item.get("original_text")
                or (original.text if original else "")
                or ""
            ).strip()
            citation_ids = [
                str(value).strip()
                for value in (raw_item.get("citation_ids") or [])
                if str(value).strip()
            ]
            validation = validate_rubric_memory_citations(
                citation_ids,
                request.rubric_memory_context,
                require_citation=True,
            )
            if validation.warnings:
                diagnostics.append(
                    {
                        "item_id": item_id,
                        "warnings": validation.warnings,
                    }
                )
            shaped_items.append(
                RubricMemoryGatedSMEQuestion(
                    id=item_id,
                    original_text=original_text,
                    final_text=str(raw_item.get("final_text") or "").strip(),
                    action=SMEQuestionGateAction(raw_item.get("action")),
                    answer_status=SMEQuestionAnswerStatus(raw_item.get("answer_status")),
                    rationale=str(raw_item.get("rationale") or "").strip(),
                    citation_ids=validation.valid_ids,
                    citation_validation=validation,
                )
            )

        suppressed = [
            item for item in shaped_items
            if item.action == SMEQuestionGateAction.SUPPRESS
        ]
        transformed = [
            item for item in shaped_items
            if item.action == SMEQuestionGateAction.TRANSFORM
        ]
        kept = [
            item for item in shaped_items
            if item.action == SMEQuestionGateAction.KEEP
        ]
        final_items = transformed + kept
        final_markdown = format_gated_sme_agenda(final_items)

        return RubricMemorySMEQuestionGateResult(
            score_version_id=request.score_version_id,
            final_agenda_markdown=final_markdown,
            final_items=final_items,
            suppressed_items=suppressed,
            transformed_items=transformed,
            kept_items=kept,
            citation_diagnostics=diagnostics,
            summary_counts={
                "candidate": len(request.candidate_agenda_items),
                "final": len(final_items),
                "suppressed": len(suppressed),
                "transformed": len(transformed),
                "kept": len(kept),
                "citation_warnings": len(diagnostics),
            },
        )


def candidate_agenda_items_from_markdown(markdown: str) -> list[RubricMemorySMEQuestion]:
    """Split optimizer SME agenda Markdown into deterministic candidate items."""
    text = str(markdown or "").strip()
    if not text or "No SME decisions needed" in text:
        return []
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("### "):
            if current:
                sections.append("\n".join(current).strip())
            current = [line]
        elif current:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    sections = [section for section in sections if section]
    if not sections:
        sections = [text]
    return [
        RubricMemorySMEQuestion(
            id=f"smeq-{index:02d}-{_short_hash(section)}",
            text=section,
        )
        for index, section in enumerate(sections, 1)
    ]


def format_gated_sme_agenda(
    items: Sequence[RubricMemoryGatedSMEQuestion],
) -> str:
    visible_items = [
        item for item in items
        if item.action in {SMEQuestionGateAction.TRANSFORM, SMEQuestionGateAction.KEEP}
    ]
    if not visible_items:
        return "(No SME decisions needed this cycle)"
    lines: list[str] = []
    for item in visible_items:
        text = item.final_text or item.original_text
        lines.append(text.strip())
        if item.citation_ids:
            lines.append("Citations: " + ", ".join(item.citation_ids))
        if item.rationale:
            lines.append("Rubric memory note: " + item.rationale)
        lines.append("")
    return "\n".join(lines).strip()


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
