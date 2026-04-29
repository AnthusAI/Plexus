from __future__ import annotations

from datetime import date, timedelta
from pathlib import PurePosixPath
from typing import Any, Optional, Sequence

from .authority import RubricAuthorityResolver
from .citations import RubricMemoryCitationContext, RubricMemoryCitationFormatter
from .models import EvidenceSnippet, RubricEvidencePackRequest
from .preparation import RubricMemoryPreparedCorpusManager
from .retrieval import BiblicusRubricEvidenceRetriever
from .s3_corpus import (
    S3RubricMemoryCorpusPaths,
    S3RubricMemoryCorpusResolver,
    S3RubricMemoryObject,
    S3RubricMemorySource,
)


class RubricMemoryRecentBriefingProvider:
    """Build recency-biased rubric-memory citation context for one score."""

    DEFAULT_DAYS = 30
    DEFAULT_QUERY = (
        "recent SME stakeholder policy update rubric guideline change "
        "clarification score scorecard scoring decision"
    )

    def __init__(
        self,
        *,
        api_client: Any,
        citation_formatter: Optional[RubricMemoryCitationFormatter] = None,
        prepared_corpus_manager: Optional[RubricMemoryPreparedCorpusManager] = None,
        s3_client: Any | None = None,
        reference_date: date | None = None,
    ):
        self.api_client = api_client
        self.citation_formatter = citation_formatter or RubricMemoryCitationFormatter()
        self.prepared_corpus_manager = (
            prepared_corpus_manager or RubricMemoryPreparedCorpusManager()
        )
        self.s3_client = s3_client
        self.reference_date = reference_date or date.today()
        self.last_diagnostics: list[dict[str, Any]] = []

    async def retrieve_recent(
        self,
        *,
        scorecard_identifier: str,
        score_identifier: str,
        score_id: str,
        score_version_id: str | None = None,
        query: str = "",
        days: int = DEFAULT_DAYS,
        since: date | str | None = None,
        limit: int = 16,
    ) -> RubricMemoryCitationContext:
        if days <= 0:
            raise ValueError("days must be a positive integer.")
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")

        authority_resolver = RubricAuthorityResolver(self.api_client)
        authority = (
            await authority_resolver.resolve_score_version(score_version_id)
            if score_version_id
            else await authority_resolver.resolve(score_id)
        )
        paths = S3RubricMemoryCorpusResolver(s3_client=self.s3_client).resolve(
            scorecard_name=scorecard_identifier,
            score_name=score_identifier,
        )
        since_date = self._resolve_since_date(days=days, since=since)
        filtered_sources, source_stats = self._filter_recent_sources(
            paths=paths,
            since_date=since_date,
        )
        request = RubricEvidencePackRequest(
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
            score_version_id=authority.score_version_id,
            rubric_text=authority.rubric_text,
            score_code=authority.score_code,
            topic_hint=(query.strip() if query.strip() else self.DEFAULT_QUERY),
        )

        evidence: list[EvidenceSnippet] = []
        retriever: BiblicusRubricEvidenceRetriever | None = None
        if filtered_sources:
            retriever = BiblicusRubricEvidenceRetriever(
                corpus_sources=filtered_sources,
                retriever_id="scan",
                max_total_items=limit,
                prepared_corpus_manager=self.prepared_corpus_manager,
            )
            evidence = list(await retriever.retrieve(request))
            evidence = self._rank_recent_evidence(evidence)[:limit]

        metadata = {
            "context_kind": "recent_briefing",
            "query": query.strip(),
            "days": days,
            "since": since_date.isoformat(),
            "reference_date": self.reference_date.isoformat(),
            "scorecard": scorecard_identifier,
            "score": score_identifier,
            "source_counts": source_stats["source_counts"],
            "skipped_unknown_date_count": source_stats["skipped_unknown_date_count"],
            "recent_object_count": source_stats["recent_object_count"],
            "latest_source_date": source_stats["latest_source_date"],
        }
        context = self.citation_formatter.from_recent_evidence(
            request=request,
            evidence=evidence,
            metadata=metadata,
        )
        diagnostics = [
            {
                "kind": "recent_rubric_memory",
                "score_version_id": authority.score_version_id,
                "days": days,
                "since": since_date.isoformat(),
                "recent_object_count": source_stats["recent_object_count"],
                "skipped_unknown_date_count": source_stats["skipped_unknown_date_count"],
                "source_counts": source_stats["source_counts"],
                "latest_source_date": source_stats["latest_source_date"],
            }
        ]
        if retriever and retriever.last_prepared_corpus:
            diagnostics.append(
                {
                    "kind": "prepared_corpus",
                    "status": retriever.last_prepared_corpus.status,
                    "path": str(retriever.last_prepared_corpus.corpus_root),
                    "fingerprint": retriever.last_prepared_corpus.fingerprint,
                }
            )
        if retriever and retriever.last_query_plan:
            diagnostics.append(
                {
                    "kind": "query_plan",
                    "generated_phrase_count": len(
                        retriever.last_query_plan.retrieval_phrases
                    ),
                    "generated_phrases": retriever.last_query_plan.retrieval_phrases,
                }
            )
        self.last_diagnostics = diagnostics
        return context.model_copy(update={"diagnostics": diagnostics})

    def _resolve_since_date(self, *, days: int, since: date | str | None) -> date:
        if isinstance(since, date):
            return since
        if isinstance(since, str) and since.strip():
            return date.fromisoformat(since.strip())
        return self.reference_date - timedelta(days=days)

    def _filter_recent_sources(
        self,
        *,
        paths: S3RubricMemoryCorpusPaths,
        since_date: date,
    ) -> tuple[list[S3RubricMemorySource], dict[str, Any]]:
        manager = self.prepared_corpus_manager
        filtered_sources: list[S3RubricMemorySource] = []
        source_counts = {"score": 0, "prefix": 0, "scorecard": 0, "unknown": 0}
        skipped_unknown_date_count = 0
        recent_object_count = 0
        latest_source_date: str | None = None

        for source in paths.sources:
            recent_objects: list[S3RubricMemoryObject] = []
            for obj in source.objects:
                relative_path = PurePosixPath(obj.key[len(source.prefix) :])
                source_timestamp = manager.infer_source_timestamp(relative_path)
                if source_timestamp is None:
                    skipped_unknown_date_count += 1
                    continue
                source_date = source_timestamp.date()
                if source_date < since_date:
                    continue
                recent_objects.append(obj)
                recent_object_count += 1
                scope = (
                    source.scope_level
                    if source.scope_level in source_counts
                    else "unknown"
                )
                source_counts[scope] += 1
                if latest_source_date is None or source_date.isoformat() > latest_source_date:
                    latest_source_date = source_date.isoformat()
            if recent_objects:
                filtered_sources.append(
                    S3RubricMemorySource(
                        bucket_name=source.bucket_name,
                        prefix=source.prefix,
                        scope_level=source.scope_level,
                        objects=tuple(recent_objects),
                    )
                )

        return filtered_sources, {
            "source_counts": source_counts,
            "skipped_unknown_date_count": skipped_unknown_date_count,
            "recent_object_count": recent_object_count,
            "latest_source_date": latest_source_date,
        }

    def _rank_recent_evidence(
        self,
        evidence: Sequence[EvidenceSnippet],
    ) -> list[EvidenceSnippet]:
        scope_rank = {"score": 0, "prefix": 1, "scorecard": 2}
        return sorted(
            evidence,
            key=lambda snippet: (
                snippet.source_timestamp is None,
                -(
                    snippet.source_timestamp.timestamp()
                    if snippet.source_timestamp is not None
                    else 0
                ),
                scope_rank.get(snippet.scope_level, 3),
                -snippet.retrieval_score,
                snippet.source_uri,
            ),
        )
