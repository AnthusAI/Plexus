from __future__ import annotations

import asyncio
import json
import re
import shutil
from datetime import date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol, Sequence

from .local_corpus import LocalRubricMemoryCorpusResolver, LocalRubricMemorySource
from .models import EvidenceClassification, EvidenceSnippet, RubricEvidencePackRequest


class RubricEvidenceRetriever(Protocol):
    async def retrieve(
        self, request: RubricEvidencePackRequest
    ) -> Sequence[EvidenceSnippet]:
        """Return candidate evidence snippets for the disputed item."""


class BiblicusRubricEvidenceRetriever:
    """Retrieve rubric-memory evidence from one local Biblicus corpus folder."""

    _SIDECAR_SUFFIX = ".biblicus.yml"
    _DATE_FOLDER_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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
        max_total_items: int = 12,
        maximum_total_characters: int = 12000,
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
        self._knowledge_base: Any | None = None
        self._temp_dir: TemporaryDirectory[str] | None = None

    @classmethod
    def from_local_score(
        cls,
        *,
        scorecard_name: str,
        score_name: str,
        retriever_id: str = "scan",
        max_total_items: int = 12,
        maximum_total_characters: int = 12000,
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

        result = self._knowledge_base.query(
            self._build_query_text(request),
            budget=QueryBudget(
                max_total_items=self.max_total_items,
                maximum_total_characters=self.maximum_total_characters,
                max_items_per_source=None,
            ),
        )
        return [self._map_evidence(evidence) for evidence in result.evidence]

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
        parts = [
            f"scorecard: {request.scorecard_identifier}",
            f"score: {request.score_identifier}",
            f"score version: {request.score_version_id}",
            f"topic: {request.topic_hint}" if request.topic_hint else "",
            f"model classification: {request.model_value}",
            f"feedback classification: {request.feedback_value}",
            f"feedback comment: {request.feedback_comment}",
            f"model explanation: {request.model_explanation}",
            f"transcript excerpt: {request.transcript_text[:4000]}",
            f"rubric excerpt: {request.rubric_text[:3000]}",
        ]
        return "\n\n".join(part for part in parts if part.strip())

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
