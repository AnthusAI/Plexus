from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Sequence

import pytest
from click.testing import CliRunner

from plexus.cli.shared.CommandLineInterface import cli
from plexus.rubric_memory import (
    BiblicusRubricEvidenceRetriever,
    ConfidenceInputs,
    ConfidenceLevel,
    EvidenceClassification,
    EvidenceSnippet,
    LocalRubricMemoryCorpusResolver,
    LocalRubricMemorySource,
    RubricMemoryPreparedCorpusManager,
    RubricMemoryContextProvider,
    RubricAuthorityResolver,
    RubricEvidencePack,
    RubricEvidencePackContextFormatter,
    RubricEvidencePackRequest,
    RubricEvidencePackService,
    RubricMemoryCitationFormatter,
    RubricHistoryEvent,
    RubricMemoryQueryPlanner,
    TactusRubricEvidenceSynthesizer,
    validate_rubric_memory_citations,
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


class _EmptyEvidenceSynthesizer:
    async def synthesize(
        self,
        *,
        request: RubricEvidencePackRequest,
        evidence: Sequence[EvidenceSnippet],
        history: Sequence[RubricHistoryEvent],
        confidence_inputs: ConfidenceInputs,
    ) -> RubricEvidencePack:
        return RubricEvidencePack(
            score_version_id=request.score_version_id,
            rubric_reading="The official rubric is authoritative.",
            evidence_classification=EvidenceClassification.RUBRIC_SUPPORTED,
            supporting_evidence=[],
            conflicting_evidence=[],
            history_of_change=list(history),
            likely_reason_for_disagreement="The model missed a policy cue.",
            confidence=confidence_inputs.suggested_confidence,
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


def _history_event(
    summary: str,
    *,
    source_uri: str,
    source_timestamp: str,
    scope_level: str = "score",
) -> RubricHistoryEvent:
    return RubricHistoryEvent(
        source_timestamp=source_timestamp,
        source_uri=source_uri,
        scope_level=scope_level,
        authority_level="medium",
        summary=summary,
        evidence_classification=EvidenceClassification.HISTORICAL_CONTEXT,
    )


def _formatter_pack() -> RubricEvidencePack:
    return RubricEvidencePack(
        score_version_id="score-version-1",
        rubric_reading="Official rubric says current medication dosage must be verified.",
        evidence_classification=EvidenceClassification.RUBRIC_SUPPORTED,
        supporting_evidence=[
            _snippet(
                "Newer but highest-ranked supporting evidence.",
                source_uri="notes/new-ranked-first.md",
                scope_level="score",
                authority_level="high",
                source_timestamp="2026-04-21T00:00:00",
                retrieval_score=99.0,
            ),
            _snippet(
                "Older lower-ranked supporting evidence.",
                source_uri="notes/older-ranked-second.md",
                scope_level="scorecard",
                source_timestamp="2026-02-24T00:00:00",
                retrieval_score=10.0,
            ),
        ],
        conflicting_evidence=[
            _snippet(
                "Old stale policy.",
                source_uri="notes/stale.md",
                scope_level="scorecard",
                source_timestamp="2026-03-01T00:00:00",
                evidence_classification=(
                    EvidenceClassification.POSSIBLE_STALE_RUBRIC
                ),
            )
        ],
        history_of_change=[
            _history_event(
                "Newest policy discussion.",
                source_uri="notes/history-new.md",
                source_timestamp="2026-04-21T00:00:00",
            ),
            _history_event(
                "Oldest policy discussion.",
                source_uri="notes/history-old.md",
                source_timestamp="2026-02-24T00:00:00",
            ),
        ],
        likely_reason_for_disagreement="The model counted a non-current medication.",
        confidence=ConfidenceLevel.HIGH,
        confidence_inputs=ConfidenceInputs(
            score_version_id="score-version-1",
            total_evidence_count=3,
            score_scope_evidence_count=1,
            scorecard_scope_evidence_count=2,
            unknown_scope_evidence_count=0,
            high_authority_evidence_count=1,
            low_authority_evidence_count=0,
            conflicting_or_stale_evidence_count=1,
            chronological_evidence_count=2,
            suggested_confidence=ConfidenceLevel.HIGH,
        ),
        open_questions=["Confirm whether stale note has been superseded."],
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


def test_tactus_synthesizer_rejects_finish_without_pack_json():
    synthesizer = TactusRubricEvidenceSynthesizer()
    raw_call = "{'name': 'finish', 'args': {}, 'result': '<Lua table at 0x123>'}"

    with pytest.raises(ValueError, match="finish without pack_json"):
        synthesizer._extract_done_reason(raw_call)


def test_tactus_synthesizer_loads_configured_token_budget():
    synthesizer = TactusRubricEvidenceSynthesizer(max_tokens=12000)

    tac_source = synthesizer._load_tac_source()

    assert "max_tokens = 12000" in tac_source
    assert "{{MAX_TOKENS}}" not in tac_source


def test_local_corpus_resolver_uses_score_yaml_stem(monkeypatch, tmp_path):
    cache_root = tmp_path / "dashboard" / "scorecards"
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(cache_root))

    paths = LocalRubricMemoryCorpusResolver().resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Medication Review: Dosage",
    )

    assert paths.scorecard_root == cache_root / "SelectQuote HCS Medium-Risk"
    assert paths.score_knowledge_base == (
        cache_root
        / "SelectQuote HCS Medium-Risk"
        / "Medication Review- Dosage.knowledge-base"
    )
    assert paths.scorecard_knowledge_base == (
        cache_root
        / "SelectQuote HCS Medium-Risk"
        / "scorecard.knowledge-base"
    )


def test_rubric_memory_prewarm_cli_reports_prepared_corpus(
    monkeypatch,
    tmp_path,
):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cache_root = tmp_path / "dashboard" / "scorecards"
        monkeypatch.setenv("SCORECARD_CACHE_DIR", str(cache_root))
        paths = LocalRubricMemoryCorpusResolver().resolve(
            scorecard_name="SelectQuote HCS Medium-Risk",
            score_name="Medication Review: Dosage",
        )
        scorecard_file = (
            paths.scorecard_knowledge_base / "2026-04-01" / "scorecard.md"
        )
        score_file = paths.score_knowledge_base / "2026-04-24" / "dosage.md"
        scorecard_file.parent.mkdir(parents=True)
        score_file.parent.mkdir(parents=True)
        scorecard_file.write_text("Shared medication review policy.", encoding="utf-8")
        score_file.write_text("Dosage-specific policy memory.", encoding="utf-8")

        first = runner.invoke(
            cli,
            [
                "rubric-memory",
                "prewarm",
                "--scorecard",
                "SelectQuote HCS Medium-Risk",
                "--score",
                "Medication Review: Dosage",
            ],
        )
        second = runner.invoke(
            cli,
            [
                "rubric-memory",
                "prewarm",
                "--scorecard",
                "SelectQuote HCS Medium-Risk",
                "--score",
                "Medication Review: Dosage",
            ],
        )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "status: rebuilt" in first.output
    assert "status: reused" in second.output
    assert "retriever_id: scan" in first.output
    assert "fingerprint:" in first.output
    assert "prepared_corpus_path:" in first.output
    assert "source_file_count: 2" in first.output
    assert "Medication Review- Dosage.knowledge-base" in first.output


def test_query_planner_derives_retrieval_phrases_from_request():
    request = RubricEvidencePackRequest(
        scorecard_identifier="SelectQuote HCS Medium-Risk",
        score_identifier="Medication Review: Dosage",
        score_version_id="version-1",
        rubric_text=(
            "The agent must verify dosage for current medications. "
            "Completed short-course medications should be excluded."
        ),
        score_code=(
            "prompt: 'Confirm Medication Name, Dosage, Prescriber, "
            "Pharmacy, and Schedule for all medications'"
        ),
        transcript_text=(
            "The agent verified dofetilide 500 microgram and confirmed "
            "doxycycline was a 7-day supply."
        ),
        model_explanation="Doxycycline and dofetilide dosage were not verified.",
        feedback_comment="All dosages verified for medications taken.",
    )

    plan = RubricMemoryQueryPlanner(max_phrases=80).plan(request)
    phrases = " | ".join(plan.retrieval_phrases).lower()

    assert "medication review" in phrases
    assert "dosage" in phrases
    assert "current medications" in phrases
    assert "completed short-course medications" in phrases
    assert "medication name" in phrases
    assert "dofetilide" in phrases
    assert "doxycycline" in phrases
    assert len(plan.retrieval_phrases) <= 80
    assert "runtime retrieval phrases:" in plan.expanded_query_text


def test_context_formatter_includes_summary_and_machine_context():
    context = RubricEvidencePackContextFormatter().format(_formatter_pack())

    assert "# Rubric Evidence Pack Context" in context
    assert "Score version authority: `score-version-1`" in context
    assert "Evidence classification: `rubric_supported`" in context
    assert "Confidence: `high`" in context
    assert "Official rubric says current medication dosage must be verified." in context
    assert "Confirm whether stale note has been superseded." in context
    assert "## Machine Context JSON" in context
    assert '"supporting": 2' in context
    assert '"conflicting_or_stale": 1' in context


def test_context_formatter_sorts_history_without_reranking_evidence():
    context = RubricEvidencePackContextFormatter().format(_formatter_pack())

    history_old_index = context.index("notes/history-old.md")
    history_new_index = context.index("notes/history-new.md")
    ranked_new_index = context.index("notes/new-ranked-first.md")
    ranked_old_index = context.index("notes/older-ranked-second.md")

    assert history_old_index < history_new_index
    assert ranked_new_index < ranked_old_index
    assert "Use it for policy evolution, not relevance ranking." in context
    assert "Do not infer chronology from this ordering." in context


def test_context_formatter_retains_source_provenance():
    context = RubricEvidencePackContextFormatter().format(_formatter_pack())
    machine_json = context.split("```json\n", 1)[1].split("\n```", 1)[0]
    machine_context = json.loads(machine_json)

    provenance = machine_context["supporting_evidence_provenance"][0]
    assert provenance["source_uri"] == "notes/new-ranked-first.md"
    assert provenance["scope_level"] == "score"
    assert provenance["source_timestamp"] == "2026-04-21T00:00:00"
    assert provenance["authority_level"] == "high"
    assert provenance["evidence_classification"] == "historical_context"
    assert machine_context["confidence_inputs"]["score_version_id"] == (
        "score-version-1"
    )


def test_source_window_expansion_finds_policy_section(tmp_path):
    source_file = tmp_path / "selectrx-script.md"
    source_file.write_text(
        "\n".join(
            [
                "Agent Script for SelectRx",
                "",
                "Introduction & Presentation",
                "Medication packets are helpful for customers.",
                *["General introductory text." for _ in range(120)],
                "Step 4 - Patient Care",
                "Verify each medication that comes up for Review ESI Meds.",
                "CSAs are required to confirm Medication Name, Dosage, "
                "Prescriber, Pharmacy, and Schedule for ALL medications.",
                "Ask whether the member is still taking each medication.",
                "If the medication is no longer prescribed, mark it appropriately.",
            ]
        ),
        encoding="utf-8",
    )
    request = RubricEvidencePackRequest(
        scorecard_identifier="SelectQuote HCS Medium-Risk",
        score_identifier="Medication Review: Dosage",
        score_version_id="version-1",
        rubric_text=(
            "The agent must verify current medication dosage and schedule. "
            "No longer prescribed medications are excluded."
        ),
        score_code=(
            "Confirm Medication Name, Dosage, Prescriber, Pharmacy, and Schedule."
        ),
        transcript_text="The call discussed whether medications were still taking.",
        model_explanation="Medication dosage was missed.",
        feedback_comment="All dosages verified for medications taken.",
    )
    query_plan = RubricMemoryQueryPlanner().plan(request)
    retriever = BiblicusRubricEvidenceRetriever(
        corpus_root=tmp_path,
        source_window_characters=1200,
    )
    header_snippet = EvidenceSnippet(
        snippet_text="Agent Script for SelectRx\n\nIntroduction & Presentation",
        source_uri=source_file.resolve().as_uri(),
        scope_level="score",
        source_type="text/markdown",
        authority_level="unknown",
        retrieval_score=1.0,
    )

    expanded = retriever._expand_snippet_from_source(header_snippet, query_plan)

    assert "Medication Name, Dosage, Prescriber" in expanded.snippet_text
    assert "Introduction & Presentation" not in expanded.snippet_text
    assert expanded.source_uri == header_snippet.source_uri
    assert expanded.scope_level == header_snippet.scope_level


def test_prepared_corpus_infers_date_folder_metadata_without_touching_raw_source(
    tmp_path,
):
    score_root = tmp_path / "Medication Review- Dosage.knowledge-base"
    source_file = score_root / "2026-04-24" / "client" / "source.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Dosage calibration note.", encoding="utf-8")

    prepared = RubricMemoryPreparedCorpusManager(
        cache_root=tmp_path / "prepared"
    ).prepare(
        corpus_sources=[LocalRubricMemorySource(root=score_root, scope_level="score")]
    )
    copied_file = (
        prepared.corpus_root / "00-score" / "2026-04-24" / "client" / "source.md"
    )
    sidecar = copied_file.with_name("source.md.biblicus.yml")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))

    assert prepared.status == "rebuilt"
    assert prepared.source_file_count == 1
    assert metadata["scope_level"] == "score"
    assert metadata["source_uri"] == source_file.resolve().as_uri()
    assert metadata["source_timestamp"] == "2026-04-24T00:00:00"
    assert source_file.with_name("source.md.biblicus.yml").exists() is False


def test_prepared_corpus_leaves_unknown_date_without_timestamp(tmp_path):
    score_root = tmp_path / "Medication Review- Dosage.knowledge-base"
    source_file = score_root / "unknown-date" / "source.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Undated dosage note.", encoding="utf-8")

    prepared = RubricMemoryPreparedCorpusManager(
        cache_root=tmp_path / "prepared"
    ).prepare(
        corpus_sources=[LocalRubricMemorySource(root=score_root, scope_level="score")]
    )
    sidecar = (
        prepared.corpus_root
        / "00-score"
        / "unknown-date"
        / "source.md.biblicus.yml"
    )
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))

    assert metadata["scope_level"] == "score"
    assert "source_timestamp" not in metadata


def test_prepared_corpus_combines_scorecard_and_score_scopes(tmp_path):
    scorecard_root = tmp_path / "scorecard.knowledge-base"
    score_root = tmp_path / "Medication Review- Dosage.knowledge-base"
    scorecard_file = scorecard_root / "2026-04-01" / "scorecard.md"
    score_file = score_root / "2026-04-24" / "score.md"
    scorecard_file.parent.mkdir(parents=True)
    score_file.parent.mkdir(parents=True)
    scorecard_file.write_text("Shared scorecard note.", encoding="utf-8")
    score_file.write_text("Score-local dosage note.", encoding="utf-8")

    prepared = RubricMemoryPreparedCorpusManager(
        cache_root=tmp_path / "prepared"
    ).prepare(
        corpus_sources=[
            LocalRubricMemorySource(
                root=scorecard_root,
                scope_level="scorecard",
            ),
            LocalRubricMemorySource(root=score_root, scope_level="score"),
        ]
    )

    scorecard_metadata = json.loads(
        (
            prepared.corpus_root
            / "00-scorecard"
            / "2026-04-01"
            / "scorecard.md.biblicus.yml"
        ).read_text(encoding="utf-8")
    )
    score_metadata = json.loads(
        (
            prepared.corpus_root
            / "01-score"
            / "2026-04-24"
            / "score.md.biblicus.yml"
        ).read_text(encoding="utf-8")
    )

    assert scorecard_metadata["scope_level"] == "scorecard"
    assert score_metadata["scope_level"] == "score"
    assert scorecard_metadata["source_timestamp"] == "2026-04-01T00:00:00"
    assert score_metadata["source_timestamp"] == "2026-04-24T00:00:00"


def test_prepared_corpus_rejects_missing_knowledge_base_folder(tmp_path):
    missing_root = tmp_path / "missing.knowledge-base"

    with pytest.raises(FileNotFoundError, match="knowledge-base folder"):
        RubricMemoryPreparedCorpusManager(cache_root=tmp_path / "prepared").prepare(
            corpus_sources=[
                LocalRubricMemorySource(root=missing_root, scope_level="score")
            ]
        )


def test_prepared_corpus_reuses_matching_fingerprint(tmp_path):
    score_root = tmp_path / "Medication Review- Dosage.knowledge-base"
    source_file = score_root / "2026-04-24" / "source.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Dosage calibration note.", encoding="utf-8")
    manager = RubricMemoryPreparedCorpusManager(cache_root=tmp_path / "prepared")

    first = manager.prepare(
        corpus_sources=[LocalRubricMemorySource(root=score_root, scope_level="score")]
    )
    second = manager.prepare(
        corpus_sources=[LocalRubricMemorySource(root=score_root, scope_level="score")]
    )

    assert first.status == "rebuilt"
    assert second.status == "reused"
    assert second.fingerprint == first.fingerprint
    assert second.corpus_root == first.corpus_root


def test_prepared_corpus_rebuilds_when_source_file_changes(tmp_path):
    score_root = tmp_path / "Medication Review- Dosage.knowledge-base"
    source_file = score_root / "2026-04-24" / "source.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("Dosage calibration note.", encoding="utf-8")
    manager = RubricMemoryPreparedCorpusManager(cache_root=tmp_path / "prepared")

    first = manager.prepare(
        corpus_sources=[LocalRubricMemorySource(root=score_root, scope_level="score")]
    )
    source_file.write_text("Dosage calibration note with new content.", encoding="utf-8")
    second = manager.prepare(
        corpus_sources=[LocalRubricMemorySource(root=score_root, scope_level="score")]
    )

    assert second.status == "rebuilt"
    assert second.fingerprint != first.fingerprint


@pytest.mark.asyncio
async def test_biblicus_retriever_preserves_inferred_date_and_scope(tmp_path):
    source_root = tmp_path / "Medication Review- Dosage.knowledge-base"
    source_file = source_root / "2026-04-24" / "source.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        "Dosage policy memory: verify current medication strengths.",
        encoding="utf-8",
    )
    retriever = BiblicusRubricEvidenceRetriever(
        corpus_sources=[
            LocalRubricMemorySource(root=source_root, scope_level="score")
        ],
        max_total_items=5,
        prepared_corpus_manager=RubricMemoryPreparedCorpusManager(
            cache_root=tmp_path / "prepared"
        ),
    )

    evidence = await retriever.retrieve(
        RubricEvidencePackRequest(
            scorecard_identifier="SelectQuote HCS Medium-Risk",
            score_identifier="Medication Review: Dosage",
            score_version_id="version-1",
            rubric_text="Verify medication dosage.",
            topic_hint="dosage medication strengths",
        )
    )

    assert len(evidence) == 1
    assert retriever.last_prepared_corpus is not None
    assert retriever.last_prepared_corpus.status == "rebuilt"
    assert evidence[0].scope_level == "score"
    assert evidence[0].source_timestamp.isoformat() == "2026-04-24T00:00:00"
    assert evidence[0].source_uri == source_file.resolve().as_uri()


def test_citation_formatter_includes_official_and_corpus_citations():
    context = RubricMemoryCitationFormatter().from_pack(_formatter_pack())

    citation_ids = context.citation_ids()
    assert any(citation_id.startswith("rubric:") for citation_id in citation_ids)
    assert any(citation_id.startswith("support:01:") for citation_id in citation_ids)
    assert any(citation_id.startswith("conflict:01:") for citation_id in citation_ids)
    assert "Score version authority: `score-version-1`" in context.markdown_context
    assert "Citation Index" in context.markdown_context
    assert context.machine_context["evidence_counts"] == {
        "supporting": 2,
        "conflicting_or_stale": 1,
        "history": 2,
        "citations": 4,
    }


def test_citation_ids_are_stable_and_retain_provenance():
    first = RubricMemoryCitationFormatter().from_pack(_formatter_pack())
    second = RubricMemoryCitationFormatter().from_pack(_formatter_pack())

    assert [citation.id for citation in first.citation_index] == [
        citation.id for citation in second.citation_index
    ]
    supporting = next(
        citation
        for citation in first.citation_index
        if citation.id.startswith("support:01:")
    )
    assert supporting.source_uri == "notes/new-ranked-first.md"
    assert supporting.scope_level == "score"
    assert supporting.source_timestamp.isoformat() == "2026-04-21T00:00:00"
    assert supporting.authority_level == "high"
    assert supporting.evidence_classification == "historical_context"


def test_citation_validation_reports_missing_and_omitted_without_failing():
    context = RubricMemoryCitationFormatter().from_pack(_formatter_pack())
    valid_id = context.citation_index[0].id

    validation = validate_rubric_memory_citations(
        [valid_id, "missing:1"],
        context,
    )
    assert validation.valid_ids == [valid_id]
    assert validation.missing_ids == ["missing:1"]
    assert validation.warnings

    omitted = validate_rubric_memory_citations([], context, require_citation=True)
    assert omitted.omitted_citations is True
    assert "no citation IDs" in omitted.warnings[0]


@pytest.mark.asyncio
async def test_context_provider_records_prepared_corpus_and_query_plan_diagnostics(monkeypatch):
    class _DiagnosticRetriever(_StaticRetriever):
        def __init__(self):
            super().__init__(
                [
                    _snippet(
                        "Retrieved score-specific policy memory.",
                        source_uri="notes/policy.md",
                        scope_level="score",
                    )
                ]
            )
            self.last_prepared_corpus = SimpleNamespace(
                status="reused",
                corpus_root="/tmp/prepared/corpus",
                fingerprint="fingerprint-1",
            )
            self.last_query_plan = SimpleNamespace(
                retrieval_phrases=["dosage verification", "current medication"]
            )

    retriever = _DiagnosticRetriever()

    monkeypatch.setattr(
        "plexus.rubric_memory.provider.BiblicusRubricEvidenceRetriever.from_local_score",
        lambda **_kwargs: retriever,
    )
    monkeypatch.setattr(
        "plexus.rubric_memory.provider.TactusRubricEvidenceSynthesizer",
        lambda: _CapturingSynthesizer(),
    )

    context = await RubricMemoryContextProvider(api_client=object()).generate_for_request(
        _request()
    )

    diagnostics_by_kind = {
        diagnostic["kind"]: diagnostic for diagnostic in context.diagnostics
    }
    assert diagnostics_by_kind["prepared_corpus"]["status"] == "reused"
    assert diagnostics_by_kind["prepared_corpus"]["fingerprint"] == "fingerprint-1"
    assert diagnostics_by_kind["query_plan"]["generated_phrase_count"] == 2
    assert diagnostics_by_kind["query_plan"]["generated_phrases"] == [
        "dosage verification",
        "current medication",
    ]


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
async def test_service_attaches_evidence_when_synthesizer_leaves_lists_empty():
    supporting = _snippet(
        "Current dosage policy.",
        source_uri="notes/supporting.md",
        scope_level="score",
    )
    conflicting = _snippet(
        "Old conflicting policy.",
        source_uri="notes/conflicting.md",
        scope_level="score",
        evidence_classification=EvidenceClassification.POSSIBLE_STALE_RUBRIC,
    )
    service = RubricEvidencePackService(
        retriever=_StaticRetriever([supporting, conflicting]),
        synthesizer=_EmptyEvidenceSynthesizer(),
    )

    pack = await service.generate(_request())

    assert [snippet.source_uri for snippet in pack.supporting_evidence] == [
        "notes/supporting.md"
    ]
    assert [snippet.source_uri for snippet in pack.conflicting_evidence] == [
        "notes/conflicting.md"
    ]


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
