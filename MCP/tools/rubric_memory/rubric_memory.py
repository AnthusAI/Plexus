#!/usr/bin/env python3
"""MCP tools for rubric-memory evidence packs."""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _fetch_score_result_context(client, score_result_id: str) -> dict:
    query = """
    query GetScoreResultForRubricMemory($id: ID!) {
        getScoreResult(id: $id) {
            id
            value
            explanation
            itemId
            feedbackItemId
            scoreId
        }
    }
    """
    response = client.execute(query, {"id": score_result_id})
    score_result = (response or {}).get("getScoreResult")
    if not score_result:
        raise ValueError(f"ScoreResult '{score_result_id}' not found.")
    return {
        "score_result_id": score_result.get("id"),
        "score_id": score_result.get("scoreId"),
        "item_id": score_result.get("itemId"),
        "feedback_item_id": score_result.get("feedbackItemId"),
        "model_value": score_result.get("value") or "",
        "model_explanation": score_result.get("explanation") or "",
    }


def _fetch_feedback_item_context(client, feedback_item_id: str) -> dict:
    query = """
    query GetFeedbackItemForRubricMemory($id: ID!) {
        getFeedbackItem(id: $id) {
            id
            scoreId
            scorecardId
            itemId
            initialAnswerValue
            finalAnswerValue
            initialCommentValue
            finalCommentValue
            editCommentValue
            item {
                id
                text
            }
        }
    }
    """
    response = client.execute(query, {"id": feedback_item_id})
    feedback_item = (response or {}).get("getFeedbackItem")
    if not feedback_item:
        raise ValueError(f"FeedbackItem '{feedback_item_id}' not found.")
    item = feedback_item.get("item") or {}
    comment_parts = [
        feedback_item.get("editCommentValue") or "",
        feedback_item.get("finalCommentValue") or "",
        feedback_item.get("initialCommentValue") or "",
    ]
    feedback_comment = "\n".join(part for part in comment_parts if part).strip()
    return {
        "feedback_item_id": feedback_item.get("id"),
        "score_id": feedback_item.get("scoreId"),
        "scorecard_id": feedback_item.get("scorecardId"),
        "item_id": feedback_item.get("itemId") or item.get("id"),
        "transcript_text": item.get("text") or "",
        "feedback_value": feedback_item.get("finalAnswerValue") or "",
        "feedback_comment": feedback_comment,
        "initial_answer_value": feedback_item.get("initialAnswerValue") or "",
    }


def _merge_context_value(explicit_value: str, fetched_value: str) -> str:
    return explicit_value if explicit_value else fetched_value


def _coerce_json_object(value, *, field_name: str) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"{field_name} must be a JSON object.")


def _coerce_lua_array(value):
    """Convert Lua/MCP table arrays encoded as numeric-key dicts into lists."""
    if isinstance(value, dict):
        numeric_items = []
        for key, item in value.items():
            key_text = str(key)
            if not key_text.isdigit():
                return value
            numeric_items.append((int(key_text), item))
        return [item for _, item in sorted(numeric_items)]
    return value


def _coerce_citation_context(value, *, field_name: str) -> dict:
    """Extract the canonical citation context from MCP wrapper or raw context input."""
    obj = _coerce_json_object(value, field_name=field_name)
    return {
        "markdown_context": obj.get("markdown_context") or "",
        "citation_index": _coerce_lua_array(obj.get("citation_index") or []),
        "machine_context": obj.get("machine_context") or {},
        "diagnostics": _coerce_lua_array(obj.get("diagnostics") or []),
    }


def register_rubric_memory_tools(server):
    """Register rubric-memory tools."""

    @server.tool()
    async def plexus_rubric_memory_evidence_pack(
        scorecard_identifier: str,
        score_identifier: str,
        score_id: Optional[str] = None,
        score_version_id: Optional[str] = None,
        transcript_text: str = "",
        model_value: str = "",
        model_explanation: str = "",
        feedback_value: str = "",
        feedback_comment: str = "",
        topic_hint: Optional[str] = None,
        feedback_item_id: Optional[str] = None,
        score_result_id: Optional[str] = None,
        synthesize: bool = False,
    ) -> str:
        """
        Generate rubric-memory citation context for a disputed score item.

        The official champion ScoreVersion rubric is the policy authority. Local
        `.knowledge-base` corpus evidence is supporting historical context.
        By default this returns retrieval-only citation context for use as LLM input.
        Set synthesize=true only for full RubricEvidencePack drill-through analysis.
        """
        try:
            from shared.utils import create_dashboard_client
            from plexus.cli.shared.direct_identifier_resolution import (
                direct_resolve_score_identifier,
                direct_resolve_scorecard_identifier,
            )
            from plexus.rubric_memory import RubricMemoryContextProvider

            client = create_dashboard_client()
            resolved_score_id = score_id
            fetched_context = {}
            if score_result_id:
                fetched_context.update(
                    _fetch_score_result_context(client, score_result_id)
                )
                if not feedback_item_id:
                    feedback_item_id = fetched_context.get("feedback_item_id")
            if feedback_item_id:
                fetched_context.update(
                    {
                        key: value
                        for key, value in _fetch_feedback_item_context(
                            client,
                            feedback_item_id,
                        ).items()
                        if value
                    }
                )
            if not resolved_score_id:
                resolved_score_id = fetched_context.get("score_id")
            if not resolved_score_id:
                scorecard_id = direct_resolve_scorecard_identifier(
                    client,
                    scorecard_identifier,
                )
                if not scorecard_id:
                    raise ValueError(f"Could not resolve scorecard: {scorecard_identifier}")
                resolved_score_id = direct_resolve_score_identifier(
                    client,
                    scorecard_id,
                    score_identifier,
                )
            if not resolved_score_id:
                raise ValueError(
                    f"Could not resolve score '{score_identifier}' in scorecard '{scorecard_identifier}'."
                )

            provider = RubricMemoryContextProvider(api_client=client)
            context_method = (
                provider.generate_for_score_item
                if synthesize
                else provider.retrieve_for_score_item
            )
            context = await context_method(
                scorecard_identifier=scorecard_identifier,
                score_identifier=score_identifier,
                score_id=resolved_score_id,
                score_version_id=score_version_id,
                transcript_text=_merge_context_value(
                    transcript_text,
                    fetched_context.get("transcript_text", ""),
                ),
                model_value=_merge_context_value(
                    model_value,
                    fetched_context.get("model_value", ""),
                ),
                model_explanation=_merge_context_value(
                    model_explanation,
                    fetched_context.get("model_explanation", ""),
                ),
                feedback_value=_merge_context_value(
                    feedback_value,
                    fetched_context.get("feedback_value", ""),
                ),
                feedback_comment=_merge_context_value(
                    feedback_comment,
                    fetched_context.get("feedback_comment", ""),
                ),
                topic_hint=topic_hint,
            )
            return json.dumps(
                {
                    "success": True,
                    "synthesized": bool(synthesize),
                    "score_id": resolved_score_id,
                    "feedback_item_id": feedback_item_id,
                    "score_result_id": score_result_id,
                    "item_id": fetched_context.get("item_id"),
                    "markdown_context": context.markdown_context,
                    "citation_index": [
                        citation.model_dump(mode="json")
                        for citation in context.citation_index
                    ],
                    "machine_context": context.machine_context,
                    "diagnostics": context.diagnostics,
                },
                default=str,
            )
        except Exception as exc:
            logger.warning("plexus_rubric_memory_evidence_pack failed: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})

    @server.tool()
    async def plexus_rubric_memory_recent_entries(
        scorecard_identifier: str,
        score_identifier: str,
        score_id: Optional[str] = None,
        score_version_id: Optional[str] = None,
        query: str = "",
        days: int = 30,
        since: Optional[str] = None,
        limit: int = 16,
    ) -> str:
        """
        Retrieve recent rubric-memory citation context for one score.

        Use this before optimization or SME-question drafting to find recent
        score, prefix, and scorecard knowledge-base entries that may require
        guideline updates or feedback curation before prompt/code optimization.
        """
        try:
            from shared.utils import create_dashboard_client
            from plexus.cli.shared.direct_identifier_resolution import (
                direct_resolve_score_identifier,
                direct_resolve_scorecard_identifier,
            )
            from plexus.rubric_memory import RubricMemoryRecentBriefingProvider

            client = create_dashboard_client()
            resolved_score_id = score_id
            if not resolved_score_id:
                scorecard_id = direct_resolve_scorecard_identifier(
                    client,
                    scorecard_identifier,
                )
                if not scorecard_id:
                    raise ValueError(f"Could not resolve scorecard: {scorecard_identifier}")
                resolved_score_id = direct_resolve_score_identifier(
                    client,
                    scorecard_id,
                    score_identifier,
                )
            if not resolved_score_id:
                raise ValueError(
                    f"Could not resolve score '{score_identifier}' in scorecard '{scorecard_identifier}'."
                )

            context = await RubricMemoryRecentBriefingProvider(
                api_client=client,
            ).retrieve_recent(
                scorecard_identifier=scorecard_identifier,
                score_identifier=score_identifier,
                score_id=resolved_score_id,
                score_version_id=score_version_id,
                query=query,
                days=days,
                since=since,
                limit=limit,
            )
            return json.dumps(
                {
                    "success": True,
                    "score_id": resolved_score_id,
                    "markdown_context": context.markdown_context,
                    "citation_index": [
                        citation.model_dump(mode="json")
                        for citation in context.citation_index
                    ],
                    "machine_context": context.machine_context,
                    "diagnostics": context.diagnostics,
                },
                default=str,
            )
        except Exception as exc:
            logger.warning("plexus_rubric_memory_recent_entries failed: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})

    @server.tool()
    async def plexus_rubric_memory_sme_question_gate(
        scorecard_identifier: str,
        score_identifier: str,
        score_version_id: str,
        candidate_agenda_markdown: str,
        rubric_memory_context: dict | str,
        optimizer_context: str = "",
    ) -> str:
        """
        Gate proposed SME agenda questions against rubric-memory citations.

        The gate suppresses questions already answered by official rubric/corpus
        evidence and transforms corpus-supported gaps into rubric codification
        decisions.
        """
        try:
            from plexus.rubric_memory import (
                RubricMemoryCitationContext,
                RubricMemorySMEQuestionGateRequest,
                RubricMemorySMEQuestionGateService,
                candidate_agenda_items_from_markdown,
            )

            context = RubricMemoryCitationContext.model_validate(
                _coerce_citation_context(
                    rubric_memory_context,
                    field_name="rubric_memory_context",
                )
            )
            candidate_items = candidate_agenda_items_from_markdown(
                candidate_agenda_markdown,
            )
            request = RubricMemorySMEQuestionGateRequest(
                scorecard_identifier=scorecard_identifier,
                score_identifier=score_identifier,
                score_version_id=score_version_id,
                rubric_memory_context=context,
                candidate_agenda_items=candidate_items,
                optimizer_context=optimizer_context,
            )
            result = await RubricMemorySMEQuestionGateService().gate(request)
            return json.dumps(
                {
                    "success": True,
                    **result.model_dump(mode="json"),
                },
                default=str,
            )
        except Exception as exc:
            logger.warning("plexus_rubric_memory_sme_question_gate failed: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})
