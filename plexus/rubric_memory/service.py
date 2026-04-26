from __future__ import annotations

from collections import OrderedDict
from typing import Sequence

from .models import (
    ConfidenceInputs,
    ConfidenceLevel,
    EvidenceClassification,
    EvidenceSnippet,
    RubricEvidencePack,
    RubricEvidencePackRequest,
    RubricHistoryEvent,
)
from .retrieval import RubricEvidenceRetriever
from .synthesis import RubricEvidenceSynthesizer


_CONFIDENCE_ORDER = {
    ConfidenceLevel.LOW: 0,
    ConfidenceLevel.MEDIUM: 1,
    ConfidenceLevel.HIGH: 2,
}


class RubricEvidencePackService:
    """
    Generate rubric evidence packs from official rubric authority and corpus evidence.

    Python owns retrieval, provenance, dedupe, chronology, confidence policy, and
    final response shaping. The synthesizer is responsible only for interpreting
    the shaped evidence into prose and structured labels.
    """

    def __init__(
        self,
        *,
        retriever: RubricEvidenceRetriever,
        synthesizer: RubricEvidenceSynthesizer,
    ):
        self.retriever = retriever
        self.synthesizer = synthesizer

    async def generate(
        self, request: RubricEvidencePackRequest
    ) -> RubricEvidencePack:
        evidence = self._dedupe_and_rank(await self.retriever.retrieve(request))
        history = self._build_history(evidence)
        confidence_inputs = self._build_confidence_inputs(
            request.score_version_id, evidence
        )

        pack = await self.synthesizer.synthesize(
            request=request,
            evidence=evidence,
            history=history,
            confidence_inputs=confidence_inputs,
        )
        return self._shape_response(request, pack, confidence_inputs)

    def _shape_response(
        self,
        request: RubricEvidencePackRequest,
        pack: RubricEvidencePack,
        confidence_inputs: ConfidenceInputs,
    ) -> RubricEvidencePack:
        confidence = self._clamp_confidence(
            pack.confidence, confidence_inputs.suggested_confidence
        )
        history = sorted(
            pack.history_of_change,
            key=lambda event: self._history_sort_key(
                event.source_timestamp, event.source_uri
            ),
        )
        return pack.model_copy(
            update={
                "score_version_id": request.score_version_id,
                "confidence": confidence,
                "confidence_inputs": confidence_inputs,
                "history_of_change": history,
            }
        )

    def _dedupe_and_rank(
        self, evidence: Sequence[EvidenceSnippet]
    ) -> list[EvidenceSnippet]:
        deduped: OrderedDict[tuple[str, str], EvidenceSnippet] = OrderedDict()
        for snippet in evidence:
            key = (
                " ".join(snippet.snippet_text.lower().split()),
                snippet.source_uri.lower(),
            )
            existing = deduped.get(key)
            if existing is None or self._rank_key(snippet) < self._rank_key(existing):
                deduped[key] = snippet
        return sorted(deduped.values(), key=self._rank_key)

    def _rank_key(self, snippet: EvidenceSnippet) -> tuple[int, int, float, str]:
        return (
            self._scope_rank(snippet.scope_level),
            self._authority_rank(snippet.authority_level),
            -snippet.retrieval_score,
            snippet.source_uri,
        )

    def _scope_rank(self, scope_level: str) -> int:
        normalized = scope_level.strip().lower().replace("_", "-")
        if normalized in {"score", "score-specific", "score-local"}:
            return 0
        if normalized in {"scorecard", "scorecard-shared", "scorecard-level"}:
            return 1
        return 2

    def _authority_rank(self, authority_level: str) -> int:
        normalized = authority_level.strip().lower().replace("_", "-")
        if normalized in {"official", "high"}:
            return 0
        if normalized in {"medium", "reviewed"}:
            return 1
        if normalized in {"low", "informal"}:
            return 2
        return 3

    def _build_history(
        self, evidence: Sequence[EvidenceSnippet]
    ) -> list[RubricHistoryEvent]:
        events = [
            RubricHistoryEvent(
                source_timestamp=snippet.source_timestamp,
                source_uri=snippet.source_uri,
                scope_level=snippet.scope_level,
                authority_level=snippet.authority_level,
                summary=snippet.snippet_text[:600],
                evidence_classification=snippet.evidence_classification,
            )
            for snippet in evidence
            if snippet.source_timestamp is not None
        ]
        return sorted(
            events,
            key=lambda event: self._history_sort_key(
                event.source_timestamp, event.source_uri
            ),
        )

    def _history_sort_key(
        self, timestamp: object | None, source_uri: str
    ) -> tuple[bool, str, str]:
        timestamp_key = timestamp.isoformat() if hasattr(timestamp, "isoformat") else ""
        return (timestamp is None, timestamp_key, source_uri)

    def _build_confidence_inputs(
        self, score_version_id: str, evidence: Sequence[EvidenceSnippet]
    ) -> ConfidenceInputs:
        score_scope_count = sum(
            1 for snippet in evidence if self._scope_rank(snippet.scope_level) == 0
        )
        scorecard_scope_count = sum(
            1 for snippet in evidence if self._scope_rank(snippet.scope_level) == 1
        )
        unknown_scope_count = len(evidence) - score_scope_count - scorecard_scope_count
        high_authority_count = sum(
            1 for snippet in evidence if self._authority_rank(snippet.authority_level) == 0
        )
        low_authority_count = sum(
            1 for snippet in evidence if self._authority_rank(snippet.authority_level) >= 2
        )
        conflicting_or_stale_count = sum(
            1
            for snippet in evidence
            if snippet.evidence_classification
            in {
                EvidenceClassification.RUBRIC_CONFLICTING,
                EvidenceClassification.POSSIBLE_STALE_RUBRIC,
            }
        )
        chronological_count = sum(
            1 for snippet in evidence if snippet.source_timestamp is not None
        )

        return ConfidenceInputs(
            score_version_id=score_version_id,
            total_evidence_count=len(evidence),
            score_scope_evidence_count=score_scope_count,
            scorecard_scope_evidence_count=scorecard_scope_count,
            unknown_scope_evidence_count=unknown_scope_count,
            high_authority_evidence_count=high_authority_count,
            low_authority_evidence_count=low_authority_count,
            conflicting_or_stale_evidence_count=conflicting_or_stale_count,
            chronological_evidence_count=chronological_count,
            suggested_confidence=self._suggest_confidence(
                total_count=len(evidence),
                score_scope_count=score_scope_count,
                scorecard_scope_count=scorecard_scope_count,
                chronological_count=chronological_count,
            ),
        )

    def _suggest_confidence(
        self,
        *,
        total_count: int,
        score_scope_count: int,
        scorecard_scope_count: int,
        chronological_count: int,
    ) -> ConfidenceLevel:
        if total_count < 2:
            return ConfidenceLevel.LOW
        if score_scope_count == 0:
            return (
                ConfidenceLevel.MEDIUM
                if scorecard_scope_count >= 2
                else ConfidenceLevel.LOW
            )
        if total_count >= 3 and chronological_count >= 2:
            return ConfidenceLevel.HIGH
        return ConfidenceLevel.MEDIUM

    def _clamp_confidence(
        self, model_confidence: ConfidenceLevel, suggested_confidence: ConfidenceLevel
    ) -> ConfidenceLevel:
        if (
            _CONFIDENCE_ORDER[model_confidence]
            <= _CONFIDENCE_ORDER[suggested_confidence]
        ):
            return model_confidence
        return suggested_confidence
