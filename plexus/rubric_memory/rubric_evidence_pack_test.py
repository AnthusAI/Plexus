from __future__ import annotations

from types import SimpleNamespace
from typing import Sequence

import pytest

from plexus.rubric_memory import (
    BiblicusRubricEvidenceRetriever,
    ConfidenceInputs,
    ConfidenceLevel,
    EvidenceClassification,
    EvidenceSnippet,
    RubricAuthorityResolver,
    RubricEvidencePack,
    RubricEvidencePackRequest,
    RubricEvidencePackService,
    RubricHistoryEvent,
    TactusRubricEvidenceSynthesizer,
)


def _request() -> RubricEvidencePackRequest:
    return RubricEvidencePackRequest(
        scorecard_identifier="Scorecard A",
        score_identifier="Score A",
        score_version_id="score-version-1",
        rubric_text="Official rubric: approve when the caller asks for billing help.",
        score_code="graph: {}",
        transcript_text="Caller asks about a billing question.",
        model_value="No",
        model_explanation="No billing request detected.",
        feedback_value="Yes",
        feedback_comment="The caller explicitly asked for billing help.",
    )


class _StaticRetriever:
    def __init__(self, evidence: Sequence[EvidenceSnippet]):
        self.evidence = list(evidence)

    async def retrieve(
        self, _request: RubricEvidencePackRequest
    ) -> Sequence[EvidenceSnippet]:
        return self.evidence


class _CapturingSynthesizer:
    def __init__(self, confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM):
        self.confidence = confidence
        self.evidence: list[EvidenceSnippet] = []
        self.history: list[RubricHistoryEvent] = []
        self.confidence_inputs: ConfidenceInputs | None = None

    async def synthesize(
        self,
        *,
        request: RubricEvidencePackRequest,
        evidence: Sequence[EvidenceSnippet],
        history: Sequence[RubricHistoryEvent],
        confidence_inputs: ConfidenceInputs,
    ) -> RubricEvidencePack:
        self.evidence = list(evidence)
        self.history = list(history)
        self.confidence_inputs = confidence_inputs
        conflicting = [
            snippet
            for snippet in evidence
            if snippet.evidence_classification
            in {
                EvidenceClassification.RUBRIC_CONFLICTING,
                EvidenceClassification.POSSIBLE_STALE_RUBRIC,
            }
        ]
        supporting = [snippet for snippet in evidence if snippet not in conflicting]
        return RubricEvidencePack(
            score_version_id="synthesizer-version-is-overridden",
            rubric_reading=f"The official rubric for {request.score_version_id} is authoritative.",
            evidence_classification=EvidenceClassification.RUBRIC_SUPPORTED,
            supporting_evidence=supporting,
            conflicting_evidence=conflicting,
            history_of_change=list(history),
            likely_reason_for_disagreement="The model missed an explicit policy cue.",
            confidence=self.confidence,
            confidence_inputs=confidence_inputs,
            open_questions=[],
        )


def _snippet(
    text: str,
    *,
    source_uri: str,
    scope_level: str,
    authority_level: str = "medium",
    source_timestamp: str | None = None,
    retrieval_score: float = 0.5,
    evidence_classification: EvidenceClassification = (
        EvidenceClassification.HISTORICAL_CONTEXT
    ),
) -> EvidenceSnippet:
    return EvidenceSnippet(
        snippet_text=text,
        source_uri=source_uri,
        scope_level=scope_level,
        source_type="meeting_notes",
        authority_level=authority_level,
        source_timestamp=source_timestamp,
        retrieval_score=retrieval_score,
        policy_concepts=["billing"],
        evidence_classification=evidence_classification,
    )


def test_tactus_synthesizer_extracts_done_last_call_reason():
    synthesizer = TactusRubricEvidenceSynthesizer()
    raw_call = (
        "{'name': 'done', 'args': {'reason': '{\"score_version_id\": "
        "\"version-1\"}'}, 'result': '<Lua table at 0x123>'}"
    )

    assert synthesizer._extract_done_reason(raw_call) == (
        '{"score_version_id": "version-1"}'
    )


def test_tactus_synthesizer_extracts_finish_pack_json():
    synthesizer = TactusRubricEvidenceSynthesizer()
    raw_call = (
        "{'name': 'finish', 'args': {'pack_json': '{\"score_version_id\": "
        "\"version-1\"}'}, 'result': '<Lua table at 0x123>'}"
    )

    assert synthesizer._extract_done_reason(raw_call) == (
        '{"score_version_id": "version-1"}'
    )


@pytest.mark.asyncio
async def test_pack_includes_score_version_and_clamps_sparse_confidence():
    synthesizer = _CapturingSynthesizer(confidence=ConfidenceLevel.HIGH)
    service = RubricEvidencePackService(
        retriever=_StaticRetriever([]),
        synthesizer=synthesizer,
    )

    pack = await service.generate(_request())

    assert pack.score_version_id == "score-version-1"
    assert pack.confidence == ConfidenceLevel.LOW
    assert pack.confidence_inputs.score_version_id == "score-version-1"
    assert pack.confidence_inputs.total_evidence_count == 0


@pytest.mark.asyncio
async def test_score_specific_evidence_ranks_ahead_of_scorecard_shared_evidence():
    scorecard_snippet = _snippet(
        "Scorecard-wide billing discussion.",
        source_uri="notes/scorecard.md",
        scope_level="scorecard",
        retrieval_score=0.99,
    )
    score_snippet = _snippet(
        "Score-specific billing exception.",
        source_uri="notes/score.md",
        scope_level="score",
        retrieval_score=0.10,
    )
    synthesizer = _CapturingSynthesizer()
    service = RubricEvidencePackService(
        retriever=_StaticRetriever([scorecard_snippet, score_snippet]),
        synthesizer=synthesizer,
    )

    await service.generate(_request())

    assert [snippet.source_uri for snippet in synthesizer.evidence] == [
        "notes/score.md",
        "notes/scorecard.md",
    ]


@pytest.mark.asyncio
async def test_scorecard_shared_evidence_is_available_without_score_local_evidence():
    synthesizer = _CapturingSynthesizer()
    service = RubricEvidencePackService(
        retriever=_StaticRetriever(
            [
                _snippet(
                    "Shared policy meeting note.",
                    source_uri="notes/shared.md",
                    scope_level="scorecard",
                )
            ]
        ),
        synthesizer=synthesizer,
    )

    pack = await service.generate(_request())

    assert [snippet.source_uri for snippet in synthesizer.evidence] == ["notes/shared.md"]
    assert pack.confidence_inputs.score_scope_evidence_count == 0
    assert pack.confidence_inputs.scorecard_scope_evidence_count == 1


@pytest.mark.asyncio
async def test_history_of_change_is_chronological():
    synthesizer = _CapturingSynthesizer()
    service = RubricEvidencePackService(
        retriever=_StaticRetriever(
            [
                _snippet(
                    "Newer discussion.",
                    source_uri="notes/new.md",
                    scope_level="score",
                    source_timestamp="2026-03-01T00:00:00Z",
                ),
                _snippet(
                    "Older discussion.",
                    source_uri="notes/old.md",
                    scope_level="score",
                    source_timestamp="2026-01-01T00:00:00Z",
                ),
            ]
        ),
        synthesizer=synthesizer,
    )

    pack = await service.generate(_request())

    assert [event.source_uri for event in synthesizer.history] == [
        "notes/old.md",
        "notes/new.md",
    ]
    assert [event.source_uri for event in pack.history_of_change] == [
        "notes/old.md",
        "notes/new.md",
    ]


@pytest.mark.asyncio
async def test_low_authority_corpus_conflict_is_reported_without_overriding_rubric():
    conflict = _snippet(
        "An old chat claimed billing help should not count.",
        source_uri="chat/old-policy.md",
        scope_level="score",
        authority_level="low",
        evidence_classification=EvidenceClassification.POSSIBLE_STALE_RUBRIC,
    )
    synthesizer = _CapturingSynthesizer(confidence=ConfidenceLevel.HIGH)
    service = RubricEvidencePackService(
        retriever=_StaticRetriever([conflict]),
        synthesizer=synthesizer,
    )

    pack = await service.generate(_request())

    assert pack.evidence_classification == EvidenceClassification.RUBRIC_SUPPORTED
    assert [snippet.source_uri for snippet in pack.conflicting_evidence] == [
        "chat/old-policy.md"
    ]
    assert pack.confidence == ConfidenceLevel.LOW
    assert pack.confidence_inputs.low_authority_evidence_count == 1
    assert pack.confidence_inputs.conflicting_or_stale_evidence_count == 1


@pytest.mark.asyncio
async def test_authority_resolver_translates_guidelines_to_rubric_boundary():
    class _Client:
        def __init__(self):
            self.calls: list[str] = []
            self.context = SimpleNamespace(account_id="account-1")

        def execute(self, query, variables):
            self.calls.append(query)
            if "GetScoreChampion" in query:
                assert variables == {"id": "score-1"}
                return {"getScore": {"championVersionId": "version-1"}}
            if "GetScoreVersionRubricAuthority" in query:
                assert variables == {"id": "version-1"}
                return {
                    "getScoreVersion": {
                        "guidelines": " Current official rubric. ",
                        "configuration": "score code",
                    }
                }
            raise AssertionError("unexpected query")

    authority = await RubricAuthorityResolver(_Client()).resolve("score-1")

    assert authority.score_version_id == "version-1"
    assert authority.rubric_text == "Current official rubric."
    assert authority.score_code == "score code"
    assert not hasattr(authority, "guidelines")


@pytest.mark.asyncio
async def test_biblicus_retriever_can_reuse_same_raw_source_folder(tmp_path):
    source_file = tmp_path / "billing-note.md"
    source_file.write_text(
        """---
scope_level: score
source_type: meeting_notes
authority_level: high
source_timestamp: "2026-02-01T00:00:00Z"
policy_concepts:
  - billing
---
Billing help should count when the caller directly asks for it.
""",
        encoding="utf-8",
    )

    first = BiblicusRubricEvidenceRetriever(tmp_path, max_total_items=1)
    second = BiblicusRubricEvidenceRetriever(tmp_path, max_total_items=1)

    first_evidence = await first.retrieve(_request())
    second_evidence = await second.retrieve(_request())

    assert first_evidence[0].scope_level == "score"
    assert second_evidence[0].scope_level == "score"
    assert not (tmp_path / "metadata").exists()
