from __future__ import annotations

import asyncio
import json
import re
import shutil
from datetime import date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol, Sequence
from urllib.parse import unquote, urlparse

from .local_corpus import LocalRubricMemoryCorpusResolver, LocalRubricMemorySource
from .models import EvidenceClassification, EvidenceSnippet, RubricEvidencePackRequest
from .query_planner import RubricMemoryQueryPlan, RubricMemoryQueryPlanner


class RubricEvidenceRetriever(Protocol):
    async def retrieve(
        self, request: RubricEvidencePackRequest
    ) -> Sequence[EvidenceSnippet]:
        """Return candidate evidence snippets for the disputed item."""


class BiblicusRubricEvidenceRetriever:
    """Retrieve rubric-memory evidence from one local Biblicus corpus folder."""

    _SIDECAR_SUFFIX = ".biblicus.yml"
    _DATE_FOLDER_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
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

    _BIBLICUS_DERIVED_DIRS = {
        ".biblicus",
        "analysis",
        "extracted",
        "graph",
        "metadata",
        "retrieval",
    }

    def __init__(
        self,
        corpus_root: str | Path | None = None,
        *,
        corpus_sources: Sequence[LocalRubricMemorySource] | None = None,
        retriever_id: str = "scan",
        max_total_items: int = 16,
        maximum_total_characters: int = 60000,
        source_window_characters: int = 6000,
        query_planner: RubricMemoryQueryPlanner | None = None,
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
            self.corpus_sources = [
                LocalRubricMemorySource(
                    root=source.root.resolve(),
                    scope_level=source.scope_level,
                )
                for source in corpus_sources
            ]
        self.retriever_id = retriever_id
        self.max_total_items = max_total_items
        self.maximum_total_characters = maximum_total_characters
        self.source_window_characters = source_window_characters
        self.query_planner = query_planner or RubricMemoryQueryPlanner()
        self.last_query_plan: RubricMemoryQueryPlan | None = None
        self._knowledge_base: Any | None = None
        self._temp_dir: TemporaryDirectory[str] | None = None

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
        )

    async def retrieve(
        self, request: RubricEvidencePackRequest
    ) -> Sequence[EvidenceSnippet]:
        return await asyncio.to_thread(self._retrieve_sync, request)

    def _retrieve_sync(
        self, request: RubricEvidencePackRequest
    ) -> list[EvidenceSnippet]:
        from biblicus.knowledge_base import KnowledgeBase
        from biblicus.models import QueryBudget

        if self._knowledge_base is None:
            working_root = self._create_working_corpus_source()
            self._knowledge_base = KnowledgeBase.from_folder(
                working_root,
                retriever_id=self.retriever_id,
                query_budget=QueryBudget(
                    max_total_items=self.max_total_items,
                    maximum_total_characters=self.maximum_total_characters,
                    max_items_per_source=None,
                ),
            )

        query_plan = self.query_planner.plan(request)
        self.last_query_plan = query_plan
        result = self._knowledge_base.query(
            query_plan.expanded_query_text,
            budget=QueryBudget(
                max_total_items=self.max_total_items,
                maximum_total_characters=self.maximum_total_characters,
                max_items_per_source=None,
            ),
        )
        return [
            self._expand_snippet_from_source(self._map_evidence(evidence), query_plan)
            for evidence in result.evidence
        ]

    def _create_working_corpus_source(self) -> Path:
        self._temp_dir = TemporaryDirectory(prefix="plexus-rubric-memory-")
        working_root = Path(self._temp_dir.name) / "corpus"
        working_root.mkdir(parents=True, exist_ok=True)
        (working_root / ".biblicusignore").write_text(
            "*.biblicus.yml\n**/*.biblicus.yml\n",
            encoding="utf-8",
        )

        def ignore_derived(directory: str, names: list[str]) -> list[str]:
            return [name for name in names if name in self._BIBLICUS_DERIVED_DIRS]

        for index, source in enumerate(self.corpus_sources):
            self._validate_source(source)
            destination = working_root / f"{index:02d}-{source.scope_level}"
            shutil.copytree(source.root, destination, ignore=ignore_derived)
            self._write_temp_metadata_sidecars(source, destination)
        return working_root

    def _validate_source(self, source: LocalRubricMemorySource) -> None:
        if not source.root.exists():
            raise FileNotFoundError(
                f"Rubric memory knowledge-base folder does not exist: {source.root}"
            )
        if not source.root.is_dir():
            raise NotADirectoryError(
                f"Rubric memory knowledge-base path is not a directory: {source.root}"
            )

    def _write_temp_metadata_sidecars(
        self,
        source: LocalRubricMemorySource,
        destination_root: Path,
    ) -> None:
        for copied_path in sorted(destination_root.rglob("*")):
            if not copied_path.is_file():
                continue
            if copied_path.name.endswith(self._SIDECAR_SUFFIX):
                continue
            relative_path = copied_path.relative_to(destination_root)
            original_path = source.root / relative_path
            metadata: dict[str, Any] = {
                "scope_level": source.scope_level,
                "source_uri": original_path.resolve().as_uri(),
            }
            source_timestamp = self._infer_source_timestamp(relative_path)
            if source_timestamp is not None:
                metadata["source_timestamp"] = source_timestamp.isoformat()
            copied_path.with_name(
                copied_path.name + self._SIDECAR_SUFFIX
            ).write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def _infer_source_timestamp(self, relative_path: Path) -> datetime | None:
        for part in reversed(relative_path.parts[:-1]):
            if not self._DATE_FOLDER_PATTERN.match(part):
                continue
            try:
                return datetime.combine(date.fromisoformat(part), time.min)
            except ValueError:
                return None
        return None

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
        if parsed.scheme != "file":
            return None
        return Path(unquote(parsed.path))

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
