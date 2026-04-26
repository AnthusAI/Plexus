from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .models import EvidenceSnippet, RubricEvidencePack


class RubricMemoryCitation(BaseModel):
    """Stable citation handle for official rubric authority or corpus evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: Literal["official_rubric", "corpus_evidence"]
    excerpt: str = Field(min_length=1)
    source_uri: Optional[str] = None
    scope_level: str = "unknown"
    source_timestamp: Optional[datetime] = None
    authority_level: str = "unknown"
    score_version_id: str = Field(min_length=1)
    evidence_classification: str = "unknown"


class RubricMemoryCitationContext(BaseModel):
    """Human-readable rubric-memory context plus machine-readable citations."""

    model_config = ConfigDict(extra="forbid")

    markdown_context: str
    citation_index: list[RubricMemoryCitation] = Field(default_factory=list)
    machine_context: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)

    def citation_ids(self) -> set[str]:
        return {citation.id for citation in self.citation_index}


class RubricMemoryCitationValidation(BaseModel):
    """Non-blocking diagnostics for citation use by an LLM consumer."""

    model_config = ConfigDict(extra="forbid")

    supplied_ids: list[str] = Field(default_factory=list)
    valid_ids: list[str] = Field(default_factory=list)
    missing_ids: list[str] = Field(default_factory=list)
    unused_ids: list[str] = Field(default_factory=list)
    omitted_citations: bool = False
    warnings: list[str] = Field(default_factory=list)


class RubricMemoryCitationFormatter:
    """Convert a RubricEvidencePack into deterministic citation context."""

    def __init__(self, *, max_excerpt_characters: int = 900):
        self.max_excerpt_characters = max_excerpt_characters

    def from_pack(self, pack: RubricEvidencePack) -> RubricMemoryCitationContext:
        citations = self._citations(pack)
        machine_context = self._machine_context(pack, citations)
        markdown = self._markdown_context(pack, citations, machine_context)
        return RubricMemoryCitationContext(
            markdown_context=markdown,
            citation_index=citations,
            machine_context=machine_context,
            diagnostics=[],
        )

    def _citations(self, pack: RubricEvidencePack) -> list[RubricMemoryCitation]:
        citations = [
            RubricMemoryCitation(
                id=f"rubric:{self._short_hash(pack.score_version_id)}",
                kind="official_rubric",
                excerpt=self._excerpt(pack.rubric_reading),
                source_uri=f"score-version:{pack.score_version_id}",
                scope_level="official_rubric",
                authority_level="official",
                score_version_id=pack.score_version_id,
                evidence_classification=pack.evidence_classification.value,
            )
        ]
        citations.extend(
            self._snippet_citations(
                pack.supporting_evidence,
                pack=pack,
                prefix="support",
            )
        )
        citations.extend(
            self._snippet_citations(
                pack.conflicting_evidence,
                pack=pack,
                prefix="conflict",
            )
        )
        return citations

    def _snippet_citations(
        self,
        snippets: Sequence[EvidenceSnippet],
        *,
        pack: RubricEvidencePack,
        prefix: str,
    ) -> list[RubricMemoryCitation]:
        result: list[RubricMemoryCitation] = []
        for index, snippet in enumerate(snippets, 1):
            stable_material = "|".join(
                [
                    pack.score_version_id,
                    prefix,
                    snippet.source_uri,
                    snippet.scope_level,
                    snippet.evidence_classification.value,
                    " ".join(snippet.snippet_text.split())[:400],
                ]
            )
            result.append(
                RubricMemoryCitation(
                    id=f"{prefix}:{index:02d}:{self._short_hash(stable_material)}",
                    kind="corpus_evidence",
                    excerpt=self._excerpt(snippet.snippet_text),
                    source_uri=snippet.source_uri,
                    scope_level=snippet.scope_level,
                    source_timestamp=snippet.source_timestamp,
                    authority_level=snippet.authority_level,
                    score_version_id=pack.score_version_id,
                    evidence_classification=snippet.evidence_classification.value,
                )
            )
        return result

    def _markdown_context(
        self,
        pack: RubricEvidencePack,
        citations: Sequence[RubricMemoryCitation],
        machine_context: dict[str, Any],
    ) -> str:
        lines = [
            "# Rubric Memory Citation Context",
            "",
            "## Authority",
            f"- Score version authority: `{pack.score_version_id}`",
            f"- Overall classification: `{pack.evidence_classification.value}`",
            f"- Confidence: `{pack.confidence.value}`",
            "- Official rubric authority is canonical; corpus evidence may explain history, interpretation, stale areas, or gaps but does not override the rubric by itself.",
            "",
            "## Rubric Reading",
            f"{pack.rubric_reading.strip()} [{citations[0].id}]",
            "",
            "## Chronological Policy Memory",
            "This section is sorted oldest to newest. Use it for policy evolution, not relevance ranking.",
        ]
        history = sorted(
            pack.history_of_change,
            key=lambda event: (
                event.source_timestamp is None,
                event.source_timestamp.isoformat() if event.source_timestamp else "",
                event.source_uri,
            ),
        )
        if not history:
            lines.append("- No dated policy-memory evidence was retrieved.")
        else:
            for event in history:
                timestamp = self._timestamp(event.source_timestamp)
                lines.append(
                    f"- {timestamp} `{event.scope_level}` `{event.evidence_classification.value}`: "
                    f"{self._excerpt(event.summary, 360)} Source: {event.source_uri}"
                )

        lines.extend(
            [
                "",
                "## Citation Index",
                "Use these exact citation IDs when making policy claims from this context.",
            ]
        )
        for citation in citations:
            timestamp = self._timestamp(citation.source_timestamp)
            lines.append(
                f"- `{citation.id}` `{citation.kind}` `{citation.scope_level}` "
                f"`{citation.evidence_classification}` {timestamp}: "
                f"{citation.excerpt}"
            )
            if citation.source_uri:
                lines.append(f"  Source: {citation.source_uri}")

        lines.extend(
            [
                "",
                "## Machine Context JSON",
                "```json",
                json.dumps(machine_context, sort_keys=True, separators=(",", ":")),
                "```",
            ]
        )
        return "\n".join(lines) + "\n"

    def _machine_context(
        self,
        pack: RubricEvidencePack,
        citations: Sequence[RubricMemoryCitation],
    ) -> dict[str, Any]:
        return {
            "score_version_id": pack.score_version_id,
            "evidence_classification": pack.evidence_classification.value,
            "confidence": pack.confidence.value,
            "confidence_inputs": pack.confidence_inputs.model_dump(mode="json"),
            "evidence_counts": {
                "supporting": len(pack.supporting_evidence),
                "conflicting_or_stale": len(pack.conflicting_evidence),
                "history": len(pack.history_of_change),
                "citations": len(citations),
            },
            "citation_index": [
                citation.model_dump(mode="json") for citation in citations
            ],
            "open_questions": list(pack.open_questions),
        }

    def _excerpt(self, text: str, limit: int | None = None) -> str:
        max_chars = limit or self.max_excerpt_characters
        collapsed = " ".join(str(text or "").split())
        if len(collapsed) <= max_chars:
            return collapsed
        return collapsed[:max_chars].rstrip() + "..."

    def _timestamp(self, timestamp: datetime | None) -> str:
        return timestamp.isoformat() if timestamp else "undated"

    def _short_hash(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def validate_rubric_memory_citations(
    supplied_ids: Iterable[str] | None,
    context: RubricMemoryCitationContext | dict[str, Any] | None,
    *,
    require_citation: bool = False,
) -> RubricMemoryCitationValidation:
    supplied = [str(value).strip() for value in (supplied_ids or []) if str(value).strip()]
    available_ids = _available_citation_ids(context)
    valid = [citation_id for citation_id in supplied if citation_id in available_ids]
    missing = [citation_id for citation_id in supplied if citation_id not in available_ids]
    unused = sorted(available_ids - set(valid))
    omitted = require_citation and bool(available_ids) and not supplied
    warnings: list[str] = []
    if missing:
        warnings.append(
            "Missing rubric-memory citation IDs: " + ", ".join(missing)
        )
    if omitted:
        warnings.append("Rubric-memory context was supplied but no citation IDs were returned.")
    return RubricMemoryCitationValidation(
        supplied_ids=supplied,
        valid_ids=valid,
        missing_ids=missing,
        unused_ids=unused,
        omitted_citations=omitted,
        warnings=warnings,
    )


def _available_citation_ids(
    context: RubricMemoryCitationContext | dict[str, Any] | None,
) -> set[str]:
    if context is None:
        return set()
    if isinstance(context, RubricMemoryCitationContext):
        return context.citation_ids()
    raw_index = (
        context.get("citation_index")
        or context.get("citations")
        or context.get("machine_context", {}).get("citation_index")
        or []
    )
    ids = set()
    for raw in raw_index:
        if isinstance(raw, dict) and raw.get("id"):
            ids.add(str(raw["id"]))
        elif isinstance(raw, str):
            ids.add(raw)
    return ids
