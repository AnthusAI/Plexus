from __future__ import annotations

from typing import Any, Optional

from .authority import RubricAuthorityResolver
from .citations import (
    RubricMemoryCitationContext,
    RubricMemoryCitationFormatter,
)
from .local_corpus import LocalRubricMemoryCorpusResolver
from .models import RubricEvidencePackRequest
from .retrieval import BiblicusRubricEvidenceRetriever
from .service import RubricEvidencePackService
from .synthesis import TactusRubricEvidenceSynthesizer


class RubricMemoryContextProvider:
    """Shared service that produces citation-ready rubric-memory context."""

    def __init__(
        self,
        *,
        api_client: Any,
        citation_formatter: Optional[RubricMemoryCitationFormatter] = None,
    ):
        self.api_client = api_client
        self.citation_formatter = citation_formatter or RubricMemoryCitationFormatter()
        self.last_diagnostics: list[dict[str, Any]] = []

    async def generate_for_score_item(
        self,
        *,
        scorecard_identifier: str,
        score_identifier: str,
        score_id: str,
        transcript_text: str = "",
        model_value: str = "",
        model_explanation: str = "",
        feedback_value: str = "",
        feedback_comment: str = "",
        topic_hint: str | None = None,
    ) -> RubricMemoryCitationContext:
        authority = await RubricAuthorityResolver(self.api_client).resolve(score_id)
        request = RubricEvidencePackRequest(
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
            score_version_id=authority.score_version_id,
            rubric_text=authority.rubric_text,
            score_code=authority.score_code,
            transcript_text=transcript_text,
            model_value=model_value,
            model_explanation=model_explanation,
            feedback_value=feedback_value,
            feedback_comment=feedback_comment,
            topic_hint=topic_hint,
        )
        return await self.generate_for_request(request)

    async def generate_for_request(
        self,
        request: RubricEvidencePackRequest,
    ) -> RubricMemoryCitationContext:
        retriever = BiblicusRubricEvidenceRetriever.from_local_score(
            scorecard_name=request.scorecard_identifier,
            score_name=request.score_identifier,
        )
        service = RubricEvidencePackService(
            retriever=retriever,
            synthesizer=TactusRubricEvidenceSynthesizer(),
        )
        pack = await service.generate(request)
        context = self.citation_formatter.from_pack(pack)
        diagnostics = [
            {
                "kind": "rubric_memory_generation",
                "score_version_id": pack.score_version_id,
                "evidence_counts": context.machine_context.get("evidence_counts", {}),
            }
        ]
        if retriever.last_prepared_corpus:
            diagnostics.append(
                {
                    "kind": "prepared_corpus",
                    "status": retriever.last_prepared_corpus.status,
                    "path": str(retriever.last_prepared_corpus.corpus_root),
                    "fingerprint": retriever.last_prepared_corpus.fingerprint,
                }
            )
        if retriever.last_query_plan:
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

    def local_corpus_status(
        self,
        *,
        scorecard_identifier: str,
        score_identifier: str,
    ) -> dict[str, Any]:
        paths = LocalRubricMemoryCorpusResolver().resolve(
            scorecard_name=scorecard_identifier,
            score_name=score_identifier,
        )
        roots = [
            {
                "scope_level": source.scope_level,
                "path": str(source.root),
                "exists": source.root.exists(),
            }
            for source in paths.sources
        ]
        return {
            "available": all(root["exists"] for root in roots),
            "roots": roots,
        }
