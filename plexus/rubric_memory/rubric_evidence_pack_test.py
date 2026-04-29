from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
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
    RubricAuthority,
    RubricMemoryPreparedCorpusManager,
    RubricMemoryContextProvider,
    RubricMemoryRecentBriefingProvider,
    RubricAuthorityResolver,
    RubricEvidencePack,
    RubricEvidencePackContextFormatter,
    RubricEvidencePackRequest,
    RubricEvidencePackService,
    RubricMemoryCitationFormatter,
    RubricMemoryGatedSMEQuestion,
    RubricHistoryEvent,
    RubricMemoryQueryPlanner,
    RubricMemorySMEQuestionGateRequest,
    RubricMemorySMEQuestionGateService,
    SMEQuestionAnswerStatus,
    SMEQuestionGateAction,
    S3RubricMemoryCorpusResolver,
    S3RubricMemorySource,
    TactusRubricEvidenceSynthesizer,
    TactusRubricMemorySMEQuestionGateSynthesizer,
    candidate_agenda_items_from_markdown,
    format_gated_sme_agenda,
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


class _FakeS3Paginator:
    def __init__(self, client):
        self.client = client

    def paginate(self, **kwargs):
        yield self.client.list_objects_v2(**kwargs)


class _FakeS3Client:
    def __init__(self):
        self.objects: dict[str, dict] = {}
        self.uploads: list[tuple[str, str]] = []
        self.downloads: list[tuple[str, str]] = []

    def put_text(
        self,
        key: str,
        text: str,
        *,
        last_modified: datetime | None = None,
        etag: str | None = None,
    ) -> None:
        body = text.encode("utf-8")
        self.objects[key] = {
            "Body": body,
            "Size": len(body),
            "ETag": etag or f"etag-{len(self.objects) + 1}",
            "LastModified": (
                last_modified or datetime(2026, 4, 24, tzinfo=timezone.utc)
            ),
        }

    def get_paginator(self, operation_name: str):
        assert operation_name == "list_objects_v2"
        return _FakeS3Paginator(self)

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str,
        Delimiter: str | None = None,
    ) -> dict:
        del Bucket
        matching_keys = sorted(key for key in self.objects if key.startswith(Prefix))
        if Delimiter:
            common_prefixes = set()
            contents = []
            for key in matching_keys:
                suffix = key[len(Prefix) :]
                if Delimiter in suffix:
                    common_prefixes.add(
                        Prefix + suffix.split(Delimiter, 1)[0] + Delimiter
                    )
                else:
                    contents.append(self._content(key))
            return {
                "CommonPrefixes": [
                    {"Prefix": prefix} for prefix in sorted(common_prefixes)
                ],
                "Contents": contents,
            }
        return {"Contents": [self._content(key) for key in matching_keys]}

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        del bucket
        self.uploads.append((filename, key))
        body = Path(filename).read_bytes()
        self.objects[key] = {
            "Body": body,
            "Size": len(body),
            "ETag": f"upload-{len(self.uploads)}",
            "LastModified": datetime(2026, 4, 24, tzinfo=timezone.utc),
        }

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        del bucket
        self.downloads.append((key, filename))
        Path(filename).write_bytes(self.objects[key]["Body"])

    def _content(self, key: str) -> dict:
        obj = self.objects[key]
        return {
            "Key": key,
            "Size": obj["Size"],
            "ETag": obj["ETag"],
            "LastModified": obj["LastModified"],
        }


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
    synthesizer = TactusRubricEvidenceSynthesizer(max_tokens=16000)

    tac_source = synthesizer._load_tac_source()

    assert "max_tokens = 16000" in tac_source
    assert "{{MAX_TOKENS}}" not in tac_source


def test_tactus_synthesizer_accepts_control_characters_in_llm_json():
    raw_text = '{"score_version_id":"version-1","rubric_reading":"line 1\nline 2"}'

    parsed = json.loads(
        TactusRubricEvidenceSynthesizer()._strip_json_fence(raw_text),
        strict=False,
    )

    assert parsed["rubric_reading"] == "line 1\nline 2"


def test_sme_gate_synthesizer_accepts_control_characters_in_llm_json():
    raw_text = '{"items":[],"final_agenda_markdown":"line 1\nline 2"}'

    parsed = json.loads(
        TactusRubricMemorySMEQuestionGateSynthesizer()._strip_json_fence(raw_text),
        strict=False,
    )

    assert parsed["final_agenda_markdown"] == "line 1\nline 2"


def test_sme_gate_tactus_uses_direct_text_output_not_tool_only_completion():
    tac_source = TactusRubricMemorySMEQuestionGateSynthesizer()._load_tac_source()

    assert 'model_type = "responses"' in tac_source
    assert "output = {\n        text = field.string{required = true}," in tac_source
    assert "local result = gate_agent({ message = gate_message })" in tac_source
    assert "local function get_field(value, key)" in tac_source
    assert "return Json.encode(text)" in tac_source
    assert "finish = Tool" not in tac_source
    assert "finish.last_call" not in tac_source
    assert "You must call the finish tool" not in tac_source


def test_sme_gate_synthesizer_extracts_direct_text_output():
    raw_text = '{"items":[],"final_agenda_markdown":"(No SME decisions needed this cycle)"}'

    extracted = TactusRubricMemorySMEQuestionGateSynthesizer()._extract_text({
        "result": {"text": raw_text}
    })

    assert extracted == raw_text


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
    assert paths.prefix_knowledge_bases == []


def test_local_corpus_resolver_includes_matching_prefix_knowledge_base(
    monkeypatch,
    tmp_path,
):
    cache_root = tmp_path / "dashboard" / "scorecards"
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(cache_root))
    prefix_root = (
        cache_root
        / "SelectQuote HCS Medium-Risk"
        / "Information Accuracy.knowledge-base"
    )
    score_root = (
        cache_root
        / "SelectQuote HCS Medium-Risk"
        / "Information Accuracy- High-Pressure Tactics.knowledge-base"
    )
    prefix_root.mkdir(parents=True)
    score_root.mkdir(parents=True)

    paths = LocalRubricMemoryCorpusResolver().resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Information Accuracy: High-Pressure Tactics",
    )

    assert paths.prefix_knowledge_bases == [prefix_root]
    assert [(source.root, source.scope_level) for source in paths.sources] == [
        (paths.scorecard_knowledge_base, "scorecard"),
        (prefix_root, "prefix"),
        (paths.score_knowledge_base, "score"),
    ]


def test_local_corpus_resolver_allows_prefix_without_score_specific_folder(
    monkeypatch,
    tmp_path,
):
    cache_root = tmp_path / "dashboard" / "scorecards"
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(cache_root))
    prefix_root = (
        cache_root
        / "SelectQuote HCS Medium-Risk"
        / "Information Accuracy.knowledge-base"
    )
    prefix_root.mkdir(parents=True)

    paths = LocalRubricMemoryCorpusResolver().resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Information Accuracy: High-Pressure Tactics",
    )

    assert [(source.root, source.scope_level) for source in paths.sources] == [
        (paths.scorecard_knowledge_base, "scorecard"),
        (prefix_root, "prefix"),
    ]


def test_local_corpus_resolver_includes_prefix_for_composite_score(
    monkeypatch,
    tmp_path,
):
    cache_root = tmp_path / "dashboard" / "scorecards"
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(cache_root))
    prefix_root = (
        cache_root
        / "SelectQuote HCS Medium-Risk"
        / "Information Accuracy.knowledge-base"
    )
    prefix_root.mkdir(parents=True)

    paths = LocalRubricMemoryCorpusResolver().resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Information Accuracy (Composite)",
    )

    assert paths.prefix_knowledge_bases == [prefix_root]


def test_local_corpus_resolver_does_not_duplicate_exact_score_knowledge_base(
    monkeypatch,
    tmp_path,
):
    cache_root = tmp_path / "dashboard" / "scorecards"
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(cache_root))
    exact_root = (
        cache_root
        / "SelectQuote HCS Medium-Risk"
        / "Agent Misrepresentation.knowledge-base"
    )
    exact_root.mkdir(parents=True)

    paths = LocalRubricMemoryCorpusResolver().resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Agent Misrepresentation",
    )

    assert paths.prefix_knowledge_bases == []
    assert [source.root for source in paths.sources].count(exact_root) == 1


def test_local_corpus_resolver_treats_missing_prefix_as_optional(
    monkeypatch,
    tmp_path,
):
    cache_root = tmp_path / "dashboard" / "scorecards"
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(cache_root))

    paths = LocalRubricMemoryCorpusResolver().resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Information Accuracy: High-Pressure Tactics",
    )

    assert paths.prefix_knowledge_bases == []
    assert [source.scope_level for source in paths.sources] == ["scorecard", "score"]


def test_s3_corpus_resolver_maps_scorecard_prefix_and_score_roots(monkeypatch):
    fake_s3 = _FakeS3Client()
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/scorecard.knowledge-base/2026-04-01/source.md",
        "Scorecard memory.",
    )
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/Medication Review.knowledge-base/2026-04-10/source.md",
        "Prefix memory.",
    )
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/2026-04-24/source.md",
        "Score memory.",
    )
    monkeypatch.setenv("AMPLIFY_STORAGE_RUBRICMEMORY_BUCKET_NAME", "rubric-bucket")

    paths = S3RubricMemoryCorpusResolver(s3_client=fake_s3).resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Medication Review: Dosage",
    )

    assert paths.bucket_name == "rubric-bucket"
    assert paths.scorecard_knowledge_base_prefix == (
        "SelectQuote HCS Medium-Risk/scorecard.knowledge-base/"
    )
    assert paths.prefix_knowledge_base_prefixes == [
        "SelectQuote HCS Medium-Risk/Medication Review.knowledge-base/"
    ]
    assert paths.score_knowledge_base_prefix == (
        "SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/"
    )
    assert [source.scope_level for source in paths.sources] == [
        "scorecard",
        "prefix",
        "score",
    ]


def test_s3_corpus_resolver_requires_scorecard_and_score_prefixes(monkeypatch):
    fake_s3 = _FakeS3Client()
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/scorecard.knowledge-base/2026-04-01/source.md",
        "Scorecard memory.",
    )
    monkeypatch.setenv("AMPLIFY_STORAGE_RUBRICMEMORY_BUCKET_NAME", "rubric-bucket")

    with pytest.raises(FileNotFoundError, match="Medication Review- Dosage"):
        S3RubricMemoryCorpusResolver(s3_client=fake_s3).resolve(
            scorecard_name="SelectQuote HCS Medium-Risk",
            score_name="Medication Review: Dosage",
        )


@pytest.mark.asyncio
async def test_recent_briefing_filters_to_recent_dated_s3_sources_and_ranks_recency(
    monkeypatch,
):
    fake_s3 = _FakeS3Client()
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/scorecard.knowledge-base/2026-03-01/old.md",
        "Old scorecard policy.",
    )
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/scorecard.knowledge-base/2026-04-27/recent-scorecard.md",
        "Recent scorecard policy.",
    )
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/Medication Review.knowledge-base/2026-04-28/recent-prefix.md",
        "Recent prefix medication review policy.",
    )
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/2026-04-28/recent-score.md",
        "Recent score dosage policy.",
    )
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/unknown-date/source.md",
        "Unknown date note.",
    )
    monkeypatch.setenv("AMPLIFY_STORAGE_RUBRICMEMORY_BUCKET_NAME", "rubric-bucket")

    class _AuthorityResolver:
        def __init__(self, _api_client):
            pass

        async def resolve(self, score_id):
            assert score_id == "score-1"
            return RubricAuthority(
                score_version_id="score-version-1",
                rubric_text="Official dosage rubric.",
                score_code="classifier prompt",
            )

    class _RecentRetriever:
        created_sources = []

        def __init__(self, *, corpus_sources, **_kwargs):
            self.corpus_sources = list(corpus_sources)
            _RecentRetriever.created_sources = self.corpus_sources
            self.last_prepared_corpus = SimpleNamespace(
                status="reused",
                corpus_root="/tmp/prepared/corpus",
                fingerprint="recent-fingerprint",
            )
            self.last_query_plan = SimpleNamespace(
                retrieval_phrases=["recent policy"]
            )

        async def retrieve(self, request):
            manager = RubricMemoryPreparedCorpusManager()
            snippets = []
            for source in self.corpus_sources:
                for obj in source.objects:
                    relative_path = PurePosixPath(obj.key[len(source.prefix) :])
                    snippets.append(
                        _snippet(
                            f"{source.scope_level}: {obj.key}",
                            source_uri=f"s3://{source.bucket_name}/{obj.key}",
                            scope_level=source.scope_level,
                            source_timestamp=manager.infer_source_timestamp(
                                relative_path
                            ),
                        )
                    )
            return snippets

    monkeypatch.setattr(
        "plexus.rubric_memory.recent.RubricAuthorityResolver",
        _AuthorityResolver,
    )
    monkeypatch.setattr(
        "plexus.rubric_memory.recent.BiblicusRubricEvidenceRetriever",
        _RecentRetriever,
    )

    context = await RubricMemoryRecentBriefingProvider(
        api_client=object(),
        s3_client=fake_s3,
        reference_date=date(2026, 4, 29),
    ).retrieve_recent(
        scorecard_identifier="SelectQuote HCS Medium-Risk",
        score_identifier="Medication Review: Dosage",
        score_id="score-1",
        days=30,
    )

    assert context.machine_context["context_kind"] == "recent_briefing"
    assert context.machine_context["since"] == "2026-03-30"
    assert context.machine_context["latest_source_date"] == "2026-04-28"
    assert context.machine_context["source_counts"] == {
        "score": 1,
        "prefix": 1,
        "scorecard": 1,
        "unknown": 0,
    }
    assert context.machine_context["skipped_unknown_date_count"] == 1
    assert "2026-03-01/old.md" not in context.markdown_context
    recent_section = context.markdown_context.split("## Recent Policy Memory", 1)[1]
    assert recent_section.index("2026-04-28") < recent_section.index("2026-04-27")
    assert "`score`" in recent_section
    assert "`prefix`" in recent_section
    assert "`scorecard`" in recent_section
    assert all(
        not obj.key.endswith("unknown-date/source.md")
        for source in _RecentRetriever.created_sources
        for obj in source.objects
    )


def test_rubric_memory_prewarm_cli_reports_prepared_corpus(
    monkeypatch,
    tmp_path,
):
    import boto3

    fake_s3 = _FakeS3Client()
    monkeypatch.setattr(boto3, "client", lambda service_name: fake_s3)
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cache_root = tmp_path / "dashboard" / "scorecards"
        monkeypatch.setenv("SCORECARD_CACHE_DIR", str(cache_root))
        monkeypatch.setenv("AMPLIFY_STORAGE_RUBRICMEMORY_BUCKET_NAME", "rubric-bucket")
        paths = LocalRubricMemoryCorpusResolver().resolve(
            scorecard_name="SelectQuote HCS Medium-Risk",
            score_name="Medication Review: Dosage",
        )
        scorecard_file = (
            paths.scorecard_knowledge_base / "2026-04-01" / "scorecard.md"
        )
        prefix_file = (
            cache_root
            / "SelectQuote HCS Medium-Risk"
            / "Medication Review.knowledge-base"
            / "2026-04-10"
            / "medication-review.md"
        )
        score_file = paths.score_knowledge_base / "2026-04-24" / "dosage.md"
        scorecard_file.parent.mkdir(parents=True)
        prefix_file.parent.mkdir(parents=True)
        score_file.parent.mkdir(parents=True)
        scorecard_file.write_text("Shared medication review policy.", encoding="utf-8")
        prefix_file.write_text("Medication review policy memory.", encoding="utf-8")
        score_file.write_text("Dosage-specific policy memory.", encoding="utf-8")

        sync_result = runner.invoke(
            cli,
            [
                "rubric-memory",
                "sync",
                "--scorecard",
                "SelectQuote HCS Medium-Risk",
                "--score",
                "Medication Review: Dosage",
            ],
        )
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

    assert sync_result.exit_code == 0, sync_result.output
    assert "uploaded_file_count: 3" in sync_result.output
    assert any(
        key.endswith("Medication Review- Dosage.knowledge-base/2026-04-24/dosage.md")
        for _filename, key in fake_s3.uploads
    )
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "status: rebuilt" in first.output
    assert "status: reused" in second.output
    assert "bucket: rubric-bucket" in first.output
    assert "retriever_id: scan" in first.output
    assert "fingerprint:" in first.output
    assert "prepared_corpus_path:" in first.output
    assert "source_file_count: 3" in first.output
    assert "included_knowledge_base[scorecard]:" in first.output
    assert "included_knowledge_base[prefix]:" in first.output
    assert "included_knowledge_base[score]:" in first.output
    assert "Medication Review- Dosage.knowledge-base" in first.output
    assert "Medication Review.knowledge-base" in first.output


def test_rubric_memory_prewarm_cli_requires_s3_bucket(monkeypatch):
    runner = CliRunner()
    monkeypatch.delenv("AMPLIFY_STORAGE_RUBRICMEMORY_BUCKET_NAME", raising=False)

    result = runner.invoke(
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

    assert result.exit_code != 0
    assert "AMPLIFY_STORAGE_RUBRICMEMORY_BUCKET_NAME" in result.output


def test_rubric_memory_recent_cli_reports_markdown_and_citations(monkeypatch):
    class _FakeCitation:
        def model_dump(self, mode="json"):
            return {"id": "evidence:01:recent", "kind": "corpus_evidence"}

    class _FakeContext:
        markdown_context = "# Recent Rubric Memory Briefing\nApr 28 update\n"
        citation_index = [_FakeCitation()]
        machine_context = {"context_kind": "recent_briefing"}
        diagnostics = [{"kind": "recent_rubric_memory"}]

    class _FakeProvider:
        def __init__(self, api_client):
            self.api_client = api_client

        async def retrieve_recent(self, **kwargs):
            assert kwargs["score_id"] == "score-1"
            assert kwargs["days"] == 30
            assert kwargs["query"] == "SME update"
            return _FakeContext()

    monkeypatch.setenv("AMPLIFY_STORAGE_RUBRICMEMORY_BUCKET_NAME", "rubric-bucket")
    monkeypatch.setattr(
        "plexus.cli.rubric_memory.commands.create_client",
        lambda: object(),
    )
    monkeypatch.setattr(
        "plexus.cli.rubric_memory.commands.memoized_resolve_scorecard_identifier",
        lambda _client, _scorecard: "scorecard-1",
    )
    monkeypatch.setattr(
        "plexus.cli.rubric_memory.commands.memoized_resolve_score_identifier",
        lambda _client, _scorecard_id, _score: "score-1",
    )
    monkeypatch.setattr(
        "plexus.cli.rubric_memory.commands.RubricMemoryRecentBriefingProvider",
        _FakeProvider,
    )

    result = CliRunner().invoke(
        cli,
        [
            "rubric-memory",
            "recent",
            "--scorecard",
            "SelectQuote HCS Medium-Risk",
            "--score",
            "Medication Review: Dosage",
            "--query",
            "SME update",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["machine_context"]["context_kind"] == "recent_briefing"
    assert payload["citation_index"][0]["id"] == "evidence:01:recent"
    assert "Apr 28 update" in payload["markdown_context"]


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
                "CSAs are required to confirm Medication Name, Dosage, Prescriber, Pharmacy, and Schedule for ALL medications.",
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


def test_prepared_corpus_combines_scorecard_prefix_and_score_scopes(tmp_path):
    scorecard_root = tmp_path / "scorecard.knowledge-base"
    prefix_root = tmp_path / "Medication Review.knowledge-base"
    score_root = tmp_path / "Medication Review- Dosage.knowledge-base"
    scorecard_file = scorecard_root / "2026-04-01" / "scorecard.md"
    prefix_file = prefix_root / "2026-04-10" / "prefix.md"
    score_file = score_root / "2026-04-24" / "score.md"
    scorecard_file.parent.mkdir(parents=True)
    prefix_file.parent.mkdir(parents=True)
    score_file.parent.mkdir(parents=True)
    scorecard_file.write_text("Shared scorecard note.", encoding="utf-8")
    prefix_file.write_text("Shared medication review note.", encoding="utf-8")
    score_file.write_text("Score-local dosage note.", encoding="utf-8")

    prepared = RubricMemoryPreparedCorpusManager(
        cache_root=tmp_path / "prepared"
    ).prepare(
        corpus_sources=[
            LocalRubricMemorySource(
                root=scorecard_root,
                scope_level="scorecard",
            ),
            LocalRubricMemorySource(root=prefix_root, scope_level="prefix"),
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
    prefix_metadata = json.loads(
        (
            prepared.corpus_root
            / "01-prefix"
            / "2026-04-10"
            / "prefix.md.biblicus.yml"
        ).read_text(encoding="utf-8")
    )
    score_metadata = json.loads(
        (
            prepared.corpus_root
            / "02-score"
            / "2026-04-24"
            / "score.md.biblicus.yml"
        ).read_text(encoding="utf-8")
    )

    assert scorecard_metadata["scope_level"] == "scorecard"
    assert prefix_metadata["scope_level"] == "prefix"
    assert score_metadata["scope_level"] == "score"
    assert scorecard_metadata["source_timestamp"] == "2026-04-01T00:00:00"
    assert prefix_metadata["source_timestamp"] == "2026-04-10T00:00:00"
    assert score_metadata["source_timestamp"] == "2026-04-24T00:00:00"


def test_prepared_corpus_downloads_s3_objects_with_sidecar_metadata(
    monkeypatch,
    tmp_path,
):
    import boto3

    fake_s3 = _FakeS3Client()
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/scorecard.knowledge-base/2026-04-01/source.md",
        "S3 scorecard note.",
    )
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/2026-04-24/client/source.md",
        "S3 dosage calibration note.",
        etag="source-etag",
    )
    monkeypatch.setattr(boto3, "client", lambda service_name: fake_s3)
    source = S3RubricMemorySource(
        bucket_name="rubric-bucket",
        prefix="SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/",
        scope_level="score",
        objects=tuple(
            S3RubricMemoryCorpusResolver(
                bucket_name="rubric-bucket",
                s3_client=fake_s3,
            )
            .resolve(
                scorecard_name="SelectQuote HCS Medium-Risk",
                score_name="Medication Review: Dosage",
            )
            .sources[-1]
            .objects
        ),
    )

    prepared = RubricMemoryPreparedCorpusManager(
        cache_root=tmp_path / "prepared"
    ).prepare(corpus_sources=[source])
    copied_file = (
        prepared.corpus_root / "00-score" / "2026-04-24" / "client" / "source.md"
    )
    metadata = json.loads(
        copied_file.with_name("source.md.biblicus.yml").read_text(encoding="utf-8")
    )

    assert "S3 dosage calibration note." in copied_file.read_text(encoding="utf-8")
    assert (
        fake_s3.objects[
            "SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/2026-04-24/client/source.md"
        ]["Body"]
        == b"S3 dosage calibration note."
    )
    assert metadata["scope_level"] == "score"
    assert metadata["source_uri"] == (
        "s3://rubric-bucket/SelectQuote HCS Medium-Risk/"
        "Medication Review- Dosage.knowledge-base/2026-04-24/client/source.md"
    )
    assert metadata["bucket_name"] == "rubric-bucket"
    assert metadata["source_timestamp"] == "2026-04-24T00:00:00"
    assert prepared.sources[0]["source_type"] == "s3"
    assert prepared.source_file_count == 1


def test_prepared_corpus_rebuilds_when_s3_etag_changes(monkeypatch, tmp_path):
    import boto3

    fake_s3 = _FakeS3Client()
    fake_s3.put_text(
        "SelectQuote HCS Medium-Risk/scorecard.knowledge-base/2026-04-01/source.md",
        "S3 scorecard note.",
    )
    key = (
        "SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/"
        "2026-04-24/source.md"
    )
    fake_s3.put_text(key, "S3 dosage calibration note.", etag="etag-1")
    monkeypatch.setattr(boto3, "client", lambda service_name: fake_s3)

    resolver = S3RubricMemoryCorpusResolver(
        bucket_name="rubric-bucket",
        s3_client=fake_s3,
    )
    first_source = resolver.resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Medication Review: Dosage",
    ).sources[-1]
    manager = RubricMemoryPreparedCorpusManager(cache_root=tmp_path / "prepared")
    first = manager.prepare(corpus_sources=[first_source])

    fake_s3.put_text(key, "S3 dosage calibration note.", etag="etag-2")
    second_source = resolver.resolve(
        scorecard_name="SelectQuote HCS Medium-Risk",
        score_name="Medication Review: Dosage",
    ).sources[-1]
    second = manager.prepare(corpus_sources=[second_source])

    assert second.status == "rebuilt"
    assert second.fingerprint != first.fingerprint


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


def _sme_gate_request() -> RubricMemorySMEQuestionGateRequest:
    context = RubricMemoryCitationFormatter().from_pack(_formatter_pack())
    return RubricMemorySMEQuestionGateRequest(
        scorecard_identifier="Scorecard A",
        score_identifier="Score A",
        score_version_id="score-version-1",
        rubric_memory_context=context,
        candidate_agenda_items=candidate_agenda_items_from_markdown(
            "### Is the script enough?\n"
            "Question: Should SelectRx script details count?\n\n"
            "### Should we update the rubric?\n"
            "Question: The notes say yes but the rubric is silent."
        ),
        optimizer_context="Cycle found dosage policy uncertainty.",
    )


class _GateSynthesizer:
    def __init__(self, raw_result):
        self.raw_result = raw_result
        self.requests = []

    async def synthesize(self, *, request):
        self.requests.append(request)
        return self.raw_result


@pytest.mark.asyncio
async def test_sme_question_gate_suppresses_answered_questions():
    request = _sme_gate_request()
    citation_id = request.rubric_memory_context.citation_index[0].id
    synthesizer = _GateSynthesizer({
        "items": [
            {
                "id": request.candidate_agenda_items[0].id,
                "original_text": request.candidate_agenda_items[0].text,
                "final_text": "",
                "action": "suppress",
                "answer_status": "answered_by_rubric",
                "rationale": "The official rubric already answers this.",
                "citation_ids": [citation_id],
            }
        ],
        "final_agenda_markdown": "(No SME decisions needed this cycle)",
    })

    result = await RubricMemorySMEQuestionGateService(
        synthesizer=synthesizer
    ).gate(request)

    assert result.summary_counts["suppressed"] == 1
    assert result.summary_counts["final"] == 0
    assert result.final_agenda_markdown == "(No SME decisions needed this cycle)"
    assert result.suppressed_items[0].citation_ids == [citation_id]


@pytest.mark.asyncio
async def test_sme_question_gate_transforms_corpus_answer_into_codification_decision():
    request = _sme_gate_request()
    citation_id = next(
        citation.id
        for citation in request.rubric_memory_context.citation_index
        if citation.id.startswith("support:01:")
    )
    final_text = (
        "### Codify SelectRx script evidence\n"
        "Question: Should the rubric explicitly say that the SelectRx script "
        "supports dosage verification?"
    )
    synthesizer = _GateSynthesizer({
        "items": [
            {
                "id": request.candidate_agenda_items[1].id,
                "original_text": request.candidate_agenda_items[1].text,
                "final_text": final_text,
                "action": "transform",
                "answer_status": "answered_by_corpus",
                "rationale": "Corpus evidence answers the policy but rubric text is silent.",
                "citation_ids": [citation_id],
            }
        ],
        "final_agenda_markdown": final_text + "\nCitations: " + citation_id,
    })

    result = await RubricMemorySMEQuestionGateService(
        synthesizer=synthesizer
    ).gate(request)

    assert result.summary_counts["transformed"] == 1
    assert result.final_items[0].action == SMEQuestionGateAction.TRANSFORM
    assert result.final_items[0].answer_status == SMEQuestionAnswerStatus.ANSWERED_BY_CORPUS
    assert "explicitly say" in result.final_agenda_markdown
    assert result.final_items[0].citation_ids == [citation_id]


@pytest.mark.asyncio
async def test_sme_question_gate_keeps_conflicting_evidence_and_reports_bad_citations():
    request = _sme_gate_request()
    synthesizer = _GateSynthesizer({
        "items": [
            {
                "id": request.candidate_agenda_items[0].id,
                "original_text": request.candidate_agenda_items[0].text,
                "final_text": request.candidate_agenda_items[0].text,
                "action": "keep",
                "answer_status": "conflicting_evidence",
                "rationale": "Sources conflict and SMEs must decide which governs.",
                "citation_ids": ["missing:citation"],
            }
        ],
        "final_agenda_markdown": request.candidate_agenda_items[0].text,
    })

    result = await RubricMemorySMEQuestionGateService(
        synthesizer=synthesizer
    ).gate(request)

    assert result.summary_counts["kept"] == 1
    assert result.summary_counts["citation_warnings"] == 1
    assert result.final_items[0].citation_ids == []
    assert "Missing rubric-memory citation IDs" in result.citation_diagnostics[0]["warnings"][0]


@pytest.mark.asyncio
async def test_sme_question_gate_keeps_true_open_question():
    request = _sme_gate_request()
    citation_id = request.rubric_memory_context.citation_index[0].id
    synthesizer = _GateSynthesizer({
        "items": [
            {
                "id": request.candidate_agenda_items[0].id,
                "original_text": request.candidate_agenda_items[0].text,
                "final_text": request.candidate_agenda_items[0].text,
                "action": "keep",
                "answer_status": "true_open_question",
                "rationale": "No source answers the decision.",
                "citation_ids": [citation_id],
            }
        ],
        "final_agenda_markdown": request.candidate_agenda_items[0].text,
    })

    result = await RubricMemorySMEQuestionGateService(
        synthesizer=synthesizer
    ).gate(request)

    assert result.summary_counts["kept"] == 1
    assert result.final_items[0].answer_status == SMEQuestionAnswerStatus.TRUE_OPEN_QUESTION
    assert result.final_items[0].citation_ids == [citation_id]


def test_sme_agenda_markdown_parser_and_formatter_are_deterministic():
    markdown = (
        "## SME AGENDA\n\n"
        "### First decision\nQuestion: One?\n\n"
        "### Second decision\nQuestion: Two?"
    )

    first = candidate_agenda_items_from_markdown(markdown)
    second = candidate_agenda_items_from_markdown(markdown)

    assert [item.id for item in first] == [item.id for item in second]
    assert len(first) == 2
    assert candidate_agenda_items_from_markdown("(No SME decisions needed this cycle)") == []

    formatted = format_gated_sme_agenda([
        RubricMemoryGatedSMEQuestion(
            id="q1",
            original_text="Question?",
            final_text="Codify this?",
            action=SMEQuestionGateAction.TRANSFORM,
            answer_status=SMEQuestionAnswerStatus.PARTIALLY_ANSWERED,
            rationale="Corpus partly answers it.",
            citation_ids=["support:01:test"],
        )
    ])

    assert "Codify this?" in formatted
    assert "support:01:test" in formatted


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
        "plexus.rubric_memory.provider.BiblicusRubricEvidenceRetriever.from_score",
        lambda **_kwargs: retriever,
    )
    monkeypatch.setattr(
        "plexus.rubric_memory.provider.TactusRubricEvidenceSynthesizer",
        _CapturingSynthesizer,
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
async def test_context_provider_retrieves_item_context_without_synthesis(monkeypatch):
    class _AuthorityResolver:
        def __init__(self, _api_client):
            pass

        async def resolve(self, score_id):
            assert score_id == "score-1"
            return RubricAuthority(
                score_version_id="score-version-1",
                rubric_text="Official dosage rubric.",
                score_code="classifier prompt",
            )

    class _DiagnosticRetriever:
        def __init__(self):
            self.requests = []
            self.last_prepared_corpus = SimpleNamespace(
                status="reused",
                corpus_root="/tmp/prepared/corpus",
                fingerprint="fingerprint-1",
            )
            self.last_query_plan = SimpleNamespace(
                retrieval_phrases=["dosage verification"]
            )

        async def retrieve(self, request):
            self.requests.append(request)
            return [
                _snippet(
                    "SelectRx script says verify Medication Name, Dosage, Prescriber, Pharmacy, and Schedule.",
                    source_uri="file:///kb/selectrx.md",
                    scope_level="score",
                    source_timestamp="2026-04-01T00:00:00",
                )
            ]

    retriever = _DiagnosticRetriever()
    created_retrievers = []

    monkeypatch.setattr(
        "plexus.rubric_memory.provider.RubricAuthorityResolver",
        _AuthorityResolver,
    )
    monkeypatch.setattr(
        "plexus.rubric_memory.provider.BiblicusRubricEvidenceRetriever.from_score",
        lambda **_kwargs: created_retrievers.append(retriever) or retriever,
    )
    monkeypatch.setattr(
        "plexus.rubric_memory.provider.RubricEvidencePackService",
        lambda **_kwargs: pytest.fail("retrieval-only context must not build evidence packs"),
    )
    monkeypatch.setattr(
        "plexus.rubric_memory.provider.TactusRubricEvidenceSynthesizer",
        lambda: pytest.fail("retrieval-only context must not run Tactus synthesis"),
    )

    contexts = await RubricMemoryContextProvider(api_client=object()).retrieve_for_score_items(
        scorecard_identifier="Scorecard A",
        score_identifier="Medication Review: Dosage",
        score_id="score-1",
        item_contexts=[
            {
                "key": "item-1",
                "model_value": "No",
                "model_explanation": "Missing dosage.",
                "feedback_value": "Yes",
                "feedback_comment": "The dosage was verified.",
            },
            {
                "key": "item-2",
                "model_value": "Yes",
                "model_explanation": "Dosage verified.",
                "feedback_value": "No",
                "feedback_comment": "Multiple meds lacked dosage.",
            },
        ],
    )

    assert len(created_retrievers) == 1
    assert len(retriever.requests) == 2
    assert set(contexts) == {"item-1", "item-2"}
    context = contexts["item-1"]
    assert context.machine_context["context_kind"] == "retrieval_only"
    assert context.machine_context["evidence_counts"]["score"] == 1
    assert "SelectRx script" in context.markdown_context
    assert any(citation.id.startswith("rubric:") for citation in context.citation_index)
    assert any(citation.id.startswith("evidence:01:") for citation in context.citation_index)
    diagnostics_by_kind = {
        diagnostic["kind"]: diagnostic for diagnostic in context.diagnostics
    }
    assert diagnostics_by_kind["prepared_corpus"]["status"] == "reused"
    assert diagnostics_by_kind["query_plan"]["generated_phrase_count"] == 1


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
async def test_prefix_evidence_ranks_between_score_and_scorecard_evidence():
    scorecard_snippet = _snippet(
        "Scorecard-wide billing discussion.",
        source_uri="notes/scorecard.md",
        scope_level="scorecard",
        retrieval_score=0.99,
    )
    prefix_snippet = _snippet(
        "Information Accuracy family policy discussion.",
        source_uri="notes/prefix.md",
        scope_level="prefix",
        retrieval_score=0.10,
    )
    score_snippet = _snippet(
        "Score-specific billing exception.",
        source_uri="notes/score.md",
        scope_level="score",
        retrieval_score=0.05,
    )
    synthesizer = _CapturingSynthesizer()
    service = RubricEvidencePackService(
        retriever=_StaticRetriever([scorecard_snippet, prefix_snippet, score_snippet]),
        synthesizer=synthesizer,
    )

    pack = await service.generate(_request())

    assert [snippet.source_uri for snippet in synthesizer.evidence] == [
        "notes/score.md",
        "notes/prefix.md",
        "notes/scorecard.md",
    ]
    assert pack.confidence_inputs.prefix_scope_evidence_count == 1
    assert pack.confidence_inputs.unknown_scope_evidence_count == 0


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
