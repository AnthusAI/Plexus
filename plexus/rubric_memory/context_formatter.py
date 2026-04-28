from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from .models import EvidenceSnippet, RubricEvidencePack, RubricHistoryEvent


class RubricEvidencePackContextFormatter:
    """Render a rubric evidence pack as deterministic sub-agent context."""

    def __init__(self, *, max_snippet_characters: int = 1400):
        self.max_snippet_characters = max_snippet_characters

    def format(self, pack: RubricEvidencePack) -> str:
        sections = [
            "# Rubric Evidence Pack Context",
            self._authority_summary(pack),
            self._section("Rubric Reading", pack.rubric_reading),
            self._history_section(pack.history_of_change),
            self._evidence_section(
                "Ranked Supporting Evidence",
                pack.supporting_evidence,
            ),
            self._evidence_section(
                "Conflicting or Stale Evidence",
                pack.conflicting_evidence,
            ),
            self._open_questions_section(pack.open_questions),
            self._machine_context_section(pack),
        ]
        return "\n\n".join(section for section in sections if section.strip()) + "\n"

    def _authority_summary(self, pack: RubricEvidencePack) -> str:
        return "\n".join(
            [
                "## Authority Summary",
                f"- Score version authority: `{pack.score_version_id}`",
                f"- Evidence classification: `{pack.evidence_classification.value}`",
                f"- Confidence: `{pack.confidence.value}`",
                f"- Supporting evidence count: {len(pack.supporting_evidence)}",
                f"- Conflicting or stale evidence count: {len(pack.conflicting_evidence)}",
                f"- Chronological memory event count: {len(pack.history_of_change)}",
            ]
        )

    def _section(self, title: str, body: str) -> str:
        return f"## {title}\n{body.strip()}"

    def _history_section(self, events: Sequence[RubricHistoryEvent]) -> str:
        lines = [
            "## Chronological Policy Memory",
            (
                "This section is sorted oldest to newest. Use it for policy "
                "evolution, not relevance ranking."
            ),
        ]
        if not events:
            lines.append("- No dated policy-memory evidence was retrieved.")
            return "\n".join(lines)

        for index, event in enumerate(sorted(events, key=self._history_sort_key), 1):
            timestamp = self._timestamp(event.source_timestamp)
            lines.extend(
                [
                    (
                        f"{index}. {timestamp} - `{event.scope_level}` - "
                        f"`{event.evidence_classification.value}`"
                    ),
                    f"   Source: {event.source_uri}",
                    f"   Summary: {self._excerpt(event.summary)}",
                ]
            )
        return "\n".join(lines)

    def _evidence_section(
        self,
        title: str,
        evidence: Sequence[EvidenceSnippet],
    ) -> str:
        lines = [
            f"## {title}",
            (
                "This section preserves retrieval/ranking order. Do not infer "
                "chronology from this ordering."
            ),
        ]
        if not evidence:
            lines.append("- None.")
            return "\n".join(lines)

        for index, snippet in enumerate(evidence, 1):
            timestamp = self._timestamp(snippet.source_timestamp)
            lines.extend(
                [
                    (
                        f"{index}. `{snippet.scope_level}` - "
                        f"`{snippet.evidence_classification.value}` - "
                        f"{timestamp} - score {snippet.retrieval_score:g}"
                    ),
                    f"   Source: {snippet.source_uri}",
                    f"   Authority: `{snippet.authority_level}`; type: `{snippet.source_type}`",
                    f"   Snippet: {self._excerpt(snippet.snippet_text)}",
                ]
            )
        return "\n".join(lines)

    def _open_questions_section(self, questions: Sequence[str]) -> str:
        lines = ["## Open Questions"]
        if not questions:
            lines.append("- None.")
            return "\n".join(lines)
        lines.extend(f"- {question.strip()}" for question in questions if question.strip())
        return "\n".join(lines)

    def _machine_context_section(self, pack: RubricEvidencePack) -> str:
        return (
            "## Machine Context JSON\n"
            "```json\n"
            + json.dumps(self._machine_context(pack), indent=2, sort_keys=True)
            + "\n```"
        )

    def _machine_context(self, pack: RubricEvidencePack) -> dict[str, Any]:
        return {
            "score_version_id": pack.score_version_id,
            "evidence_classification": pack.evidence_classification.value,
            "confidence": pack.confidence.value,
            "evidence_counts": {
                "supporting": len(pack.supporting_evidence),
                "conflicting_or_stale": len(pack.conflicting_evidence),
                "chronological_events": len(pack.history_of_change),
            },
            "confidence_inputs": pack.confidence_inputs.model_dump(mode="json"),
            "supporting_evidence_provenance": [
                self._snippet_provenance(snippet)
                for snippet in pack.supporting_evidence
            ],
            "conflicting_evidence_provenance": [
                self._snippet_provenance(snippet)
                for snippet in pack.conflicting_evidence
            ],
            "chronological_policy_memory_provenance": [
                self._history_provenance(event)
                for event in sorted(pack.history_of_change, key=self._history_sort_key)
            ],
            "open_questions": list(pack.open_questions),
        }

    def _snippet_provenance(self, snippet: EvidenceSnippet) -> dict[str, Any]:
        return {
            "source_uri": snippet.source_uri,
            "scope_level": snippet.scope_level,
            "source_type": snippet.source_type,
            "authority_level": snippet.authority_level,
            "source_timestamp": self._timestamp_or_none(snippet.source_timestamp),
            "author": snippet.author,
            "retrieval_score": snippet.retrieval_score,
            "policy_concepts": list(snippet.policy_concepts),
            "evidence_classification": snippet.evidence_classification.value,
        }

    def _history_provenance(self, event: RubricHistoryEvent) -> dict[str, Any]:
        return {
            "source_uri": event.source_uri,
            "scope_level": event.scope_level,
            "authority_level": event.authority_level,
            "source_timestamp": self._timestamp_or_none(event.source_timestamp),
            "evidence_classification": event.evidence_classification.value,
        }

    def _history_sort_key(self, event: RubricHistoryEvent) -> tuple[bool, str, str]:
        timestamp = event.source_timestamp
        timestamp_key = timestamp.isoformat() if timestamp else ""
        return (timestamp is None, timestamp_key, event.source_uri)

    def _timestamp(self, timestamp: datetime | None) -> str:
        return self._timestamp_or_none(timestamp) or "undated"

    def _timestamp_or_none(self, timestamp: datetime | None) -> str | None:
        return timestamp.isoformat() if timestamp else None

    def _excerpt(self, text: str) -> str:
        collapsed = " ".join(str(text or "").split())
        if len(collapsed) <= self.max_snippet_characters:
            return collapsed
        return collapsed[: self.max_snippet_characters].rstrip() + "..."
