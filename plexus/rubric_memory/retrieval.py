from __future__ import annotations

import asyncio
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Protocol, Sequence
from urllib.parse import unquote, urlparse

from .local_corpus import LocalRubricMemoryCorpusResolver, LocalRubricMemorySource
from .models import EvidenceClassification, EvidenceSnippet, RubricEvidencePackRequest
from .preparation import (
    PreparedRubricMemoryCorpus,
    RubricMemoryCorpusSource,
    RubricMemoryPreparedCorpusManager,
)
from .query_planner import RubricMemoryQueryPlan, RubricMemoryQueryPlanner
from .s3_corpus import S3RubricMemoryCorpusResolver


class RubricEvidenceRetriever(Protocol):
    async def retrieve(
        self, request: RubricEvidencePackRequest
    ) -> Sequence[EvidenceSnippet]:
        """Return candidate evidence snippets for the disputed item."""


class BiblicusRubricEvidenceRetriever:
    """Retrieve rubric-memory evidence from one prepared Biblicus corpus."""

    _SOURCE_POLICY_ANCHORS = {
        "required to confirm",
        "must confirm",
        "must verify",
        "verify each",
        "confirm medication",
        "medication name",
        "form/dosage",
        "for all medications",
    }

    def __init__(
        self,
        corpus_root: str | Path | None = None,
        *,
        corpus_sources: Sequence[RubricMemoryCorpusSource] | None = None,
        retriever_id: str = "scan",
        max_total_items: int = 16,
        maximum_total_characters: int = 60000,
        source_window_characters: int = 6000,
        query_planner: RubricMemoryQueryPlanner | None = None,
        prepared_corpus_manager: RubricMemoryPreparedCorpusManager | None = None,
    ):
        if (corpus_root is None) == (corpus_sources is None):
            raise ValueError(
                "Provide exactly one of corpus_root or corpus_sources."
            )
        if corpus_sources is None:
            self.corpus_sources = [
                LocalRubricMemorySource(
                    root=Path(corpus_root).resolve(),
                    scope_level="unknown",
                )
            ]
        else:
            self.corpus_sources = list(corpus_sources)
        self.retriever_id = retriever_id
        self.max_total_items = max_total_items
        self.maximum_total_characters = maximum_total_characters
        self.source_window_characters = source_window_characters
        self.query_planner = query_planner or RubricMemoryQueryPlanner()
        self.prepared_corpus_manager = (
            prepared_corpus_manager or RubricMemoryPreparedCorpusManager()
        )
        self.last_query_plan: RubricMemoryQueryPlan | None = None
        self.last_prepared_corpus: PreparedRubricMemoryCorpus | None = None
        self._knowledge_base: Any | None = None

    @classmethod
    def from_local_score(
        cls,
        *,
        scorecard_name: str,
        score_name: str,
        retriever_id: str = "scan",
        max_total_items: int = 16,
        maximum_total_characters: int = 60000,
        source_window_characters: int = 6000,
        prepared_corpus_manager: RubricMemoryPreparedCorpusManager | None = None,
    ) -> "BiblicusRubricEvidenceRetriever":
        paths = LocalRubricMemoryCorpusResolver().resolve(
            scorecard_name=scorecard_name,
            score_name=score_name,
        )
        return cls(
            corpus_sources=paths.sources,
            retriever_id=retriever_id,
            max_total_items=max_total_items,
            maximum_total_characters=maximum_total_characters,
            source_window_characters=source_window_characters,
            prepared_corpus_manager=prepared_corpus_manager,
        )

    @classmethod
    def from_score(
        cls,
        *,
        scorecard_name: str,
        score_name: str,
        retriever_id: str = "scan",
        max_total_items: int = 16,
        maximum_total_characters: int = 60000,
        source_window_characters: int = 6000,
        prepared_corpus_manager: RubricMemoryPreparedCorpusManager | None = None,
        s3_client: Any | None = None,
    ) -> "BiblicusRubricEvidenceRetriever":
        paths = S3RubricMemoryCorpusResolver(s3_client=s3_client).resolve(
            scorecard_name=scorecard_name,
            score_name=score_name,
        )
        return cls(
            corpus_sources=paths.sources,
            retriever_id=retriever_id,
            max_total_items=max_total_items,
            maximum_total_characters=maximum_total_characters,
            source_window_characters=source_window_characters,
            prepared_corpus_manager=prepared_corpus_manager,
        )

    async def retrieve(
        self, request: RubricEvidencePackRequest
    ) -> Sequence[EvidenceSnippet]:
        return await asyncio.to_thread(self._retrieve_sync, request)

    def _retrieve_sync(
        self, request: RubricEvidencePackRequest
    ) -> list[EvidenceSnippet]:
        from biblicus.models import QueryBudget

        query_budget = QueryBudget(
            max_total_items=self.max_total_items,
            maximum_total_characters=self.maximum_total_characters,
            max_items_per_source=None,
        )
        if self._knowledge_base is None:
            self.last_prepared_corpus = self.prepared_corpus_manager.prepare(
                corpus_sources=self.corpus_sources,
                retriever_id=self.retriever_id,
            )
            self._knowledge_base = self._open_prepared_knowledge_base(
                self.last_prepared_corpus.corpus_root,
                query_budget=query_budget,
            )

        query_plan = self.query_planner.plan(request)
        self.last_query_plan = query_plan
        result = self._knowledge_base.query(
            query_plan.expanded_query_text,
            budget=query_budget,
        )
        return [
            self._expand_snippet_from_source(self._map_evidence(evidence), query_plan)
            for evidence in result.evidence
        ]

    def _open_prepared_knowledge_base(self, corpus_root: Path, *, query_budget: Any) -> Any:
        from biblicus.corpus import Corpus
        from biblicus.knowledge_base import KnowledgeBase, KnowledgeBaseDefaults
        from biblicus.retrievers import get_retriever

        corpus = Corpus.open(corpus_root)
        snapshot_id = corpus.latest_snapshot_id
        if snapshot_id is None:
            snapshot = get_retriever(self.retriever_id).build_snapshot(
                corpus,
                configuration_name="Knowledge base",
                configuration={},
            )
        else:
            snapshot = corpus.load_snapshot(snapshot_id)
        return KnowledgeBase(
            corpus=corpus,
            retriever_id=self.retriever_id,
            snapshot=snapshot,
            defaults=KnowledgeBaseDefaults(
                retriever_id=self.retriever_id,
                query_budget=query_budget,
            ),
            _temp_dir=None,
        )

    def _build_query_text(self, request: RubricEvidencePackRequest) -> str:
        query_plan = self.query_planner.plan(request)
        self.last_query_plan = query_plan
        return query_plan.expanded_query_text

    def _map_evidence(self, evidence: Any) -> EvidenceSnippet:
        metadata = getattr(evidence, "metadata", None) or {}
        source_uri = self._metadata_optional_text(metadata, "source_uri") or str(
            getattr(evidence, "source_uri", "") or ""
        ).strip()
        snippet_text = str(getattr(evidence, "text", "") or "").strip()
        if not source_uri:
            source_uri = str(getattr(evidence, "item_id", "") or "").strip()
        if not snippet_text:
            raise ValueError(f"Biblicus evidence from {source_uri} did not include text.")

        return EvidenceSnippet(
            snippet_text=snippet_text,
            source_uri=source_uri,
            scope_level=self._metadata_text(metadata, "scope_level", "scope"),
            source_type=self._metadata_text(
                metadata,
                "source_type",
                default=str(getattr(evidence, "media_type", "") or "unknown"),
            ),
            authority_level=self._metadata_text(
                metadata, "authority_level", "authority"
            ),
            source_timestamp=self._metadata_datetime(
                metadata, "source_timestamp", "timestamp", "date"
            ),
            author=self._metadata_optional_text(metadata, "author", "speaker"),
            retrieval_score=float(getattr(evidence, "score", 0.0) or 0.0),
            policy_concepts=self._metadata_list(
                metadata, "policy_concepts", "concepts"
            ),
            evidence_classification=self._metadata_classification(metadata),
        )

    def _expand_snippet_from_source(
        self,
        snippet: EvidenceSnippet,
        query_plan: RubricMemoryQueryPlan,
    ) -> EvidenceSnippet:
        source_path = self._source_uri_to_path(snippet.source_uri)
        if source_path is None or not source_path.is_file():
            return snippet
        try:
            source_text = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return snippet
        source_text = self._strip_markdown_frontmatter(source_text)
        expanded_text = self._best_source_window(
            source_text,
            query_plan,
            original_snippet=snippet.snippet_text,
        )
        if not expanded_text or expanded_text == snippet.snippet_text:
            return snippet
        return snippet.model_copy(update={"snippet_text": expanded_text})

    def _source_uri_to_path(self, source_uri: str) -> Path | None:
        parsed = urlparse(source_uri)
        if parsed.scheme == "file":
            return Path(unquote(parsed.path))
        if parsed.scheme != "s3" or self.last_prepared_corpus is None:
            return None
        bucket_name = parsed.netloc
        key = unquote(parsed.path.lstrip("/"))
        for index, source in enumerate(self.last_prepared_corpus.sources):
            if source.get("source_type") != "s3":
                continue
            if source.get("bucket_name") != bucket_name:
                continue
            prefix = str(source.get("prefix") or "")
            if not key.startswith(prefix):
                continue
            relative = key[len(prefix) :]
            if not relative:
                continue
            scope_level = str(source.get("scope_level") or "unknown")
            return self.last_prepared_corpus.corpus_root / (
                f"{index:02d}-{scope_level}"
            ) / relative
        return None

    def _strip_markdown_frontmatter(self, text: str) -> str:
        if not text.startswith("---\n"):
            return text
        frontmatter_end = text.find("\n---\n", 4)
        if frontmatter_end < 0:
            return text
        return text[frontmatter_end + len("\n---\n") :]

    def _best_source_window(
        self,
        source_text: str,
        query_plan: RubricMemoryQueryPlan,
        *,
        original_snippet: str,
    ) -> str:
        if len(source_text) <= self.source_window_characters:
            return source_text.strip()

        lower_text = source_text.lower()
        anchors = self._window_anchors(lower_text, query_plan)
        if not anchors:
            return original_snippet

        best_score = self._window_score(original_snippet, query_plan)
        best_window = original_snippet
        half_window = self.source_window_characters // 2
        for anchor in anchors:
            start = max(0, anchor - half_window)
            end = min(len(source_text), start + self.source_window_characters)
            start = max(0, end - self.source_window_characters)
            window = source_text[start:end].strip()
            score = self._window_score(window, query_plan)
            if score > best_score:
                best_score = score
                best_window = window
        return best_window

    def _window_anchors(
        self,
        lower_text: str,
        query_plan: RubricMemoryQueryPlan,
    ) -> list[int]:
        anchors: list[int] = []
        search_terms = [
            phrase.lower()
            for phrase in query_plan.retrieval_phrases
            if len(phrase) >= 4
        ]
        search_terms.extend(
            token.lower()
            for token in query_plan.important_tokens
            if len(token) >= 4
        )
        search_terms.extend(self._SOURCE_POLICY_ANCHORS)
        for term in search_terms:
            start = 0
            while True:
                index = lower_text.find(term, start)
                if index < 0:
                    break
                anchors.append(index)
                start = index + max(len(term), 1)
        return sorted(set(anchors))

    def _window_score(
        self,
        text: str,
        query_plan: RubricMemoryQueryPlan,
    ) -> int:
        lower = text.lower()
        score = 0
        for phrase in query_plan.retrieval_phrases:
            normalized = phrase.lower()
            if len(normalized) < 4:
                continue
            hits = lower.count(normalized)
            if hits:
                score += hits * (10 + len(normalized.split()))
        for token in query_plan.important_tokens:
            normalized = token.lower()
            if len(normalized) < 4:
                continue
            hits = lower.count(normalized)
            if hits:
                score += min(hits, 8)
        for anchor in self._SOURCE_POLICY_ANCHORS:
            hits = lower.count(anchor)
            if hits:
                score += hits * 25
        return score

    def _metadata_text(
        self, metadata: dict[str, Any], *keys: str, default: str = "unknown"
    ) -> str:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return default

    def _metadata_optional_text(
        self, metadata: dict[str, Any], *keys: str
    ) -> str | None:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _metadata_datetime(
        self, metadata: dict[str, Any], *keys: str
    ) -> datetime | None:
        for key in keys:
            parsed = self._parse_datetime(metadata.get(key))
            if parsed is not None:
                return parsed
        return None

    def _metadata_list(self, metadata: dict[str, Any], *keys: str) -> list[str]:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            if isinstance(value, str) and value.strip():
                return [item.strip() for item in value.split(",") if item.strip()]
        return []

    def _metadata_classification(
        self, metadata: dict[str, Any]
    ) -> EvidenceClassification:
        raw_value = metadata.get("evidence_classification")
        if isinstance(raw_value, str) and raw_value.strip():
            return EvidenceClassification(raw_value.strip())
        return EvidenceClassification.HISTORICAL_CONTEXT

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        if not isinstance(value, str) or not value.strip():
            return None

        normalized = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed_date = date.fromisoformat(normalized)
                return datetime.combine(parsed_date, time.min)
            except ValueError:
                return None
