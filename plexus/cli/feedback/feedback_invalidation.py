"""Shared single-item feedback invalidation helpers for CLI and MCP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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


def list_invalid_feedback_items_for_score(
    *,
    client,
    scorecard_identifier: str,
    score_identifier: str,
    account_id: Optional[str] = None,
    limit: int = 500,
    days: Optional[int] = None,
) -> Dict[str, Any]:
    """List invalidated feedback items for one score."""
    resolved_account_id = account_id or resolve_account_id_for_command(client, None)
    if not resolved_account_id:
        raise FeedbackInvalidationError(
            "Unable to resolve the account ID required to list invalidated feedback.",
            code="account_resolution_failed",
        )

    resolved_scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
    if not resolved_scorecard_id:
        raise FeedbackInvalidationError(
            f"Scorecard '{scorecard_identifier}' was not found.",
            code="scorecard_not_found",
        )

    resolved_score_id = resolve_score_identifier(
        client, resolved_scorecard_id, score_identifier
    )
    if not resolved_score_id:
        raise FeedbackInvalidationError(
            f"Score '{score_identifier}' was not found in scorecard '{scorecard_identifier}'.",
            code="score_not_found",
        )

    now = datetime.now(timezone.utc)
    window_start = (
        now - timedelta(days=days)
        if days is not None
        else datetime(1970, 1, 1, tzinfo=timezone.utc)
    )
    window_end = now + timedelta(minutes=5)

    query = """
    query ListFeedbackItemsByScoreEditedWindow(
        $accountId: String!,
        $composite_sk_condition: ModelFeedbackItemByAccountScorecardScoreEditedAtCompositeKeyConditionInput,
        $limit: Int,
        $nextToken: String,
        $sortDirection: ModelSortDirection
    ) {
        listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
            accountId: $accountId,
            scorecardIdScoreIdEditedAt: $composite_sk_condition,
            limit: $limit,
            nextToken: $nextToken,
            sortDirection: $sortDirection
        ) {
            items {
                id
                accountId
                scorecardId
                scoreId
                itemId
                cacheKey
                initialAnswerValue
                finalAnswerValue
                initialCommentValue
                finalCommentValue
                editCommentValue
                editedAt
                editorName
                isAgreement
                isInvalid
                createdAt
                updatedAt
            }
            nextToken
        }
    }
    """

    items: List[FeedbackItem] = []
    next_token = None
    while True:
        variables = {
            "accountId": resolved_account_id,
            "composite_sk_condition": {
                "between": [
                    {
                        "scorecardId": resolved_scorecard_id,
                        "scoreId": resolved_score_id,
                        "editedAt": window_start.isoformat(),
                    },
                    {
                        "scorecardId": resolved_scorecard_id,
                        "scoreId": resolved_score_id,
                        "editedAt": window_end.isoformat(),
                    },
                ]
            },
            "limit": limit,
            "nextToken": next_token,
            "sortDirection": "DESC",
        }
        response = client.execute(query=query, variables=variables)
        if not isinstance(response, dict):
            raise FeedbackInvalidationError(
                f"Unexpected feedback query response type: {type(response).__name__}",
                code="feedback_query_failed",
            )
        if response.get("errors"):
            raise FeedbackInvalidationError(
                f"GraphQL feedback query failed: {response['errors']}",
                code="feedback_query_failed",
                details={"errors": response["errors"]},
            )
        page = (
            response.get(
                "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt"
            )
            or {}
        )
        batch = [
            FeedbackItem.from_dict(item_data, client=client)
            for item_data in page.get("items", [])
            if (item_data or {}).get("isInvalid") is True
        ]
        items.extend(batch)
        next_token = page.get("nextToken")
        if not next_token:
            break

    return {
        "scorecard_identifier": scorecard_identifier,
        "score_identifier": score_identifier,
        "account_id": resolved_account_id,
        "scorecard_id": resolved_scorecard_id,
        "score_id": resolved_score_id,
        "window_start": window_start.isoformat().replace("+00:00", "Z"),
        "window_end": window_end.isoformat().replace("+00:00", "Z"),
        "count": len(items),
        "feedback_items": [serialize_feedback_item(item) for item in items],
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


def reinstate_feedback_item(
    *,
    client,
    identifier: str,
    scorecard_identifier: Optional[str] = None,
    score_identifier: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark exactly one feedback item valid again and return structured result data."""
    target = resolve_feedback_item_for_invalidation(
        client=client,
        identifier=identifier,
        scorecard_identifier=scorecard_identifier,
        score_identifier=score_identifier,
        account_id=account_id,
    )
    feedback_item: FeedbackItem = target["feedback_item"]

    if not feedback_item.isInvalid:
        return {
            "status": "already_valid",
            "updated": False,
            "already_invalid": False,
            "resolution": target["resolution"],
            "feedback_item": serialize_feedback_item(feedback_item),
        }

    updated_item = FeedbackItem.reinstate(client, feedback_item.id)
    if not updated_item:
        raise FeedbackInvalidationError(
            f"Failed to reinstate feedback item '{feedback_item.id}'.",
            code="mutation_failed",
            details={
                "requested_identifier": identifier,
                "feedback_item_id": feedback_item.id,
            },
        )

    return {
        "status": "reinstated",
        "updated": True,
        "already_invalid": True,
        "resolution": target["resolution"],
        "feedback_item": serialize_feedback_item(updated_item),
    }


def reinstate_invalid_feedback_items_for_score(
    *,
    client,
    scorecard_identifier: str,
    score_identifier: str,
    dry_run: bool = True,
    account_id: Optional[str] = None,
    days: Optional[int] = None,
) -> Dict[str, Any]:
    """Reinstate all currently invalidated feedback items for one score."""
    inventory = list_invalid_feedback_items_for_score(
        client=client,
        scorecard_identifier=scorecard_identifier,
        score_identifier=score_identifier,
        account_id=account_id,
        days=days,
    )

    if dry_run:
        return {
            "status": "dry_run",
            "updated_count": 0,
            "failed_count": 0,
            "inventory": inventory,
            "results": [],
        }

    results: List[Dict[str, Any]] = []
    for item in inventory["feedback_items"]:
        try:
            result = reinstate_feedback_item(
                client=client,
                identifier=item["id"],
                scorecard_identifier=scorecard_identifier,
                score_identifier=score_identifier,
                account_id=inventory["account_id"],
            )
            results.append(result)
        except FeedbackInvalidationError as exc:
            results.append(
                {
                    "status": "failed",
                    "updated": False,
                    "error": str(exc),
                    "code": exc.code,
                    "feedback_item": item,
                }
            )

    updated_count = sum(1 for result in results if result.get("updated"))
    failed_count = sum(1 for result in results if result.get("status") == "failed")
    return {
        "status": "completed" if failed_count == 0 else "completed_with_errors",
        "updated_count": updated_count,
        "failed_count": failed_count,
        "inventory": inventory,
        "results": results,
    }
