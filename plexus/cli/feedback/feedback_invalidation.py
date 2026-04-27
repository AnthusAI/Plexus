"""Shared single-item feedback invalidation helpers for CLI and MCP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.cli.shared.identifier_resolution import (
    resolve_item_reference,
    resolve_score_identifier,
    resolve_scorecard_identifier,
)
from plexus.dashboard.api.models.feedback_item import FeedbackItem


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def serialize_feedback_item(item: FeedbackItem) -> Dict[str, Any]:
    """Return a stable dictionary representation for CLI/MCP output."""
    return {
        "id": item.id,
        "account_id": item.accountId,
        "scorecard_id": item.scorecardId,
        "score_id": item.scoreId,
        "item_id": item.itemId,
        "cache_key": item.cacheKey,
        "initial_answer_value": item.initialAnswerValue,
        "final_answer_value": item.finalAnswerValue,
        "initial_comment_value": item.initialCommentValue,
        "final_comment_value": item.finalCommentValue,
        "edit_comment_value": item.editCommentValue,
        "is_agreement": item.isAgreement,
        "is_invalid": item.isInvalid,
        "editor_name": item.editorName,
        "edited_at": _serialize_datetime(item.editedAt),
        "created_at": _serialize_datetime(item.createdAt),
        "updated_at": _serialize_datetime(item.updatedAt),
    }


def _list_feedback_items_for_item(client, item_id: str) -> List[FeedbackItem]:
    items: List[FeedbackItem] = []
    next_token = None
    while True:
        batch, next_token = FeedbackItem.list(
            client=client,
            filter={"itemId": {"eq": item_id}},
            limit=200,
            next_token=next_token,
            fields=FeedbackItem.GRAPHQL_BASE_FIELDS,
        )
        items.extend(batch)
        if not next_token:
            break
    return items


def _candidate_summary(item: FeedbackItem) -> Dict[str, Any]:
    return {
        "feedback_item_id": item.id,
        "scorecard_id": item.scorecardId,
        "score_id": item.scoreId,
        "item_id": item.itemId,
        "cache_key": item.cacheKey,
        "initial_answer_value": item.initialAnswerValue,
        "final_answer_value": item.finalAnswerValue,
        "is_invalid": item.isInvalid,
    }


@dataclass
class FeedbackInvalidationError(Exception):
    """Structured error for resolution/mutation failures."""

    message: str
    code: str = "feedback_invalidation_error"
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return self.message


def _format_ambiguity_message(identifier: str, candidates: List[Dict[str, Any]]) -> str:
    lines = [
        f"Identifier '{identifier}' resolved to multiple feedback items.",
        "Re-run with --scorecard <scorecardId> and --score <scoreId> to target exactly one item.",
        "Candidates:",
    ]
    for candidate in candidates:
        lines.append(
            "  - "
            f"feedback_item_id={candidate['feedback_item_id']} "
            f"scorecard_id={candidate['scorecard_id']} "
            f"score_id={candidate['score_id']} "
            f"item_id={candidate['item_id']} "
            f"is_invalid={candidate['is_invalid']}"
        )
    return "\n".join(lines)


def resolve_feedback_item_for_invalidation(
    *,
    client,
    identifier: str,
    scorecard_identifier: Optional[str] = None,
    score_identifier: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve a single feedback item to invalidate or raise a structured error."""
    if score_identifier and not scorecard_identifier:
        raise FeedbackInvalidationError(
            "--score requires --scorecard so the command can resolve the intended score deterministically.",
            code="score_requires_scorecard",
        )

    direct_feedback_item = FeedbackItem.get(
        identifier,
        client=client,
        fields=FeedbackItem.GRAPHQL_BASE_FIELDS,
    )
    if direct_feedback_item:
        feedback_items = [direct_feedback_item]
        resolution_method = "feedback_item_id"
        resolved_item_id = direct_feedback_item.itemId
    else:
        resolved_account_id = account_id or resolve_account_id_for_command(client, None)
        if not resolved_account_id:
            raise FeedbackInvalidationError(
                "Unable to resolve the account ID required to search item identifiers.",
                code="account_resolution_failed",
            )

        resolved_item = resolve_item_reference(client, identifier, resolved_account_id)
        if not resolved_item:
            raise FeedbackInvalidationError(
                f"Unable to resolve '{identifier}' as a feedback item ID, item ID, item externalId, or item identifier value.",
                code="identifier_not_found",
            )

        resolved_item_id, resolution_method = resolved_item
        feedback_items = _list_feedback_items_for_item(client, resolved_item_id)
        if not feedback_items:
            raise FeedbackInvalidationError(
                f"Resolved item '{resolved_item_id}' from '{identifier}', but found no feedback items attached to that item.",
                code="no_feedback_for_item",
                details={
                    "requested_identifier": identifier,
                    "resolved_item_id": resolved_item_id,
                    "resolution_method": resolution_method,
                },
            )

    resolved_scorecard_id = None
    if scorecard_identifier:
        resolved_scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
        if not resolved_scorecard_id:
            raise FeedbackInvalidationError(
                f"Scorecard '{scorecard_identifier}' was not found.",
                code="scorecard_not_found",
            )
        feedback_items = [
            item for item in feedback_items if item.scorecardId == resolved_scorecard_id
        ]

    resolved_score_id = None
    if score_identifier:
        resolved_score_id = resolve_score_identifier(
            client, resolved_scorecard_id, score_identifier
        )
        if not resolved_score_id:
            raise FeedbackInvalidationError(
                f"Score '{score_identifier}' was not found in scorecard '{scorecard_identifier}'.",
                code="score_not_found",
            )
        feedback_items = [item for item in feedback_items if item.scoreId == resolved_score_id]

    if not feedback_items:
        raise FeedbackInvalidationError(
            f"No feedback item matched '{identifier}' after applying the requested filters.",
            code="feedback_item_not_found",
            details={
                "requested_identifier": identifier,
                "scorecard_identifier": scorecard_identifier,
                "score_identifier": score_identifier,
            },
        )

    if len(feedback_items) > 1:
        candidates = [_candidate_summary(item) for item in feedback_items]
        raise FeedbackInvalidationError(
            _format_ambiguity_message(identifier, candidates),
            code="ambiguous_feedback_items",
            details={"candidates": candidates},
        )

    return {
        "feedback_item": feedback_items[0],
        "resolution": {
            "requested_identifier": identifier,
            "method": resolution_method,
            "resolved_item_id": resolved_item_id,
            "scorecard_filter": resolved_scorecard_id,
            "score_filter": resolved_score_id,
        },
    }


def invalidate_feedback_item(
    *,
    client,
    identifier: str,
    scorecard_identifier: Optional[str] = None,
    score_identifier: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Invalidate exactly one feedback item and return structured result data."""
    target = resolve_feedback_item_for_invalidation(
        client=client,
        identifier=identifier,
        scorecard_identifier=scorecard_identifier,
        score_identifier=score_identifier,
        account_id=account_id,
    )
    feedback_item: FeedbackItem = target["feedback_item"]

    if feedback_item.isInvalid:
        return {
            "status": "already_invalid",
            "updated": False,
            "already_invalid": True,
            "resolution": target["resolution"],
            "feedback_item": serialize_feedback_item(feedback_item),
        }

    updated_item = FeedbackItem.invalidate(client, feedback_item.id)
    if not updated_item:
        raise FeedbackInvalidationError(
            f"Failed to invalidate feedback item '{feedback_item.id}'.",
            code="mutation_failed",
            details={
                "requested_identifier": identifier,
                "feedback_item_id": feedback_item.id,
            },
        )

    return {
        "status": "invalidated",
        "updated": True,
        "already_invalid": False,
        "resolution": target["resolution"],
        "feedback_item": serialize_feedback_item(updated_item),
    }
