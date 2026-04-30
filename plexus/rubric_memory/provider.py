from __future__ import annotations

from typing import Any, Optional, Sequence

from .authority import RubricAuthorityResolver
from .citations import (
    RubricMemoryCitationContext,
    RubricMemoryCitationFormatter,
)
from .models import RubricEvidencePackRequest
from .models import RubricAuthority
from .retrieval import BiblicusRubricEvidenceRetriever
from .service import RubricEvidencePackService
from .s3_corpus import S3RubricMemoryCorpusResolver
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
        score_version_id: str | None = None,
        transcript_text: str = "",
        model_value: str = "",
        model_explanation: str = "",
        feedback_value: str = "",
        feedback_comment: str = "",
        topic_hint: str | None = None,
    ) -> RubricMemoryCitationContext:
        authority_resolver = RubricAuthorityResolver(self.api_client)
        authority = (
            await authority_resolver.resolve_score_version(score_version_id)
            if score_version_id
            else await authority_resolver.resolve(score_id)
        )
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

    async def retrieve_for_score_item(
        self,
        *,
        scorecard_identifier: str,
        score_identifier: str,
        score_id: str,
        score_version_id: str | None = None,
        transcript_text: str = "",
        model_value: str = "",
        model_explanation: str = "",
        feedback_value: str = "",
        feedback_comment: str = "",
        topic_hint: str | None = None,
    ) -> RubricMemoryCitationContext:
        contexts = await self.retrieve_for_score_items(
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
            score_id=score_id,
            score_version_id=score_version_id,
            item_contexts=[
                {
                    "key": "item",
                    "transcript_text": transcript_text,
                    "model_value": model_value,
                    "model_explanation": model_explanation,
                    "feedback_value": feedback_value,
                    "feedback_comment": feedback_comment,
                    "topic_hint": topic_hint or "",
                }
            ],
        )
        return contexts["item"]

    async def retrieve_for_score_items(
        self,
        *,
        scorecard_identifier: str,
        score_identifier: str,
        score_id: str,
        item_contexts: Sequence[dict[str, str]],
        score_version_id: str | None = None,
        topic_hint: str | None = None,
    ) -> dict[str, RubricMemoryCitationContext]:
        """Retrieve citation context for existing LLM consumers without synthesis."""
        authority_resolver = RubricAuthorityResolver(self.api_client)
        authority = (
            await authority_resolver.resolve_score_version(score_version_id)
            if score_version_id
            else await authority_resolver.resolve(score_id)
        )
        retriever = BiblicusRubricEvidenceRetriever.from_score(
            scorecard_name=scorecard_identifier,
            score_name=score_identifier,
        )
        contexts: dict[str, RubricMemoryCitationContext] = {}
        diagnostics: list[dict[str, Any]] = []
        for item_context in item_contexts:
            key = item_context["key"]
            request = self._request_from_item_context(
                authority=authority,
                scorecard_identifier=scorecard_identifier,
                score_identifier=score_identifier,
                item_context=item_context,
                topic_hint=topic_hint,
            )
            evidence = list(await retriever.retrieve(request))
            context = self.citation_formatter.from_retrieved_evidence(
                request=request,
                evidence=evidence,
            )
            item_diagnostics = self._retrieval_diagnostics(
                retriever=retriever,
                score_version_id=authority.score_version_id,
                evidence_count=len(evidence),
            )
            diagnostics.extend(item_diagnostics)
            contexts[key] = context.model_copy(update={"diagnostics": item_diagnostics})
        self.last_diagnostics = diagnostics
        return contexts

    async def generate_for_request(
        self,
        request: RubricEvidencePackRequest,
    ) -> RubricMemoryCitationContext:
        retriever = BiblicusRubricEvidenceRetriever.from_score(
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

    def _request_from_item_context(
        self,
        *,
        authority: RubricAuthority,
        scorecard_identifier: str,
        score_identifier: str,
        item_context: dict[str, str],
        topic_hint: str | None,
    ) -> RubricEvidencePackRequest:
        return RubricEvidencePackRequest(
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
            score_version_id=authority.score_version_id,
            rubric_text=authority.rubric_text,
            score_code=authority.score_code,
            transcript_text=item_context.get("transcript_text", ""),
            model_value=item_context.get("model_value", ""),
            model_explanation=item_context.get("model_explanation", ""),
            feedback_value=item_context.get("feedback_value", ""),
            feedback_comment=item_context.get("feedback_comment", ""),
            topic_hint=item_context.get("topic_hint") or topic_hint,
        )

    def _retrieval_diagnostics(
        self,
        *,
        retriever: BiblicusRubricEvidenceRetriever,
        score_version_id: str,
        evidence_count: int,
    ) -> list[dict[str, Any]]:
        diagnostics = [
            {
                "kind": "rubric_memory_retrieval_context",
                "score_version_id": score_version_id,
                "evidence_count": evidence_count,
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
        return diagnostics

    def local_corpus_status(
        self,
        *,
        scorecard_identifier: str,
        score_identifier: str,
    ) -> dict[str, Any]:
        paths = S3RubricMemoryCorpusResolver().resolve(
            scorecard_name=scorecard_identifier,
            score_name=score_identifier,
        )
        roots = [
            {
                "scope_level": source.scope_level,
                "path": f"s3://{source.bucket_name}/{source.prefix}",
                "exists": bool(source.objects),
            }
            for source in paths.sources
        ]
        return {
            "available": all(root["exists"] for root in roots),
            "roots": roots,
        }
