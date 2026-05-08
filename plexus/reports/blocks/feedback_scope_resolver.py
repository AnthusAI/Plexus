from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, List, Optional

from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard

from .identifier_utils import looks_like_uuid


@dataclass(frozen=True)
class ResolvedScoreRef:
    id: str
    name: str
    key: Optional[str] = None
    external_id: Optional[str] = None


def _casefold_identifier(value: str) -> str:
    return str(value or "").strip().casefold()


def _client_account_id(api_client: Any) -> Optional[str]:
    context = getattr(api_client, "context", None)
    account_id = getattr(context, "account_id", None)
    if isinstance(account_id, str) and account_id.strip():
        return account_id.strip()
    account_key = getattr(context, "account_key", None)
    if isinstance(account_key, str) and account_key.strip() and hasattr(api_client, "_resolve_account_id"):
        try:
            return str(api_client._resolve_account_id())
        except Exception:
            return None
    return None


async def _find_scorecard_by_case_insensitive_name(
    api_client,
    scorecard_name: str,
    *,
    account_id: Optional[str] = None,
) -> Optional[Scorecard]:
    normalized_name = _casefold_identifier(scorecard_name)
    if not normalized_name:
        return None

    filter_arg = {}
    scoped_account_id = account_id or _client_account_id(api_client)
    if scoped_account_id:
        filter_arg = {"accountId": {"eq": scoped_account_id}}

    query = """
    query ListScorecardsForCaseInsensitiveName(
        $filter: ModelScorecardFilterInput
        $limit: Int
        $nextToken: String
    ) {
        listScorecards(filter: $filter, limit: $limit, nextToken: $nextToken) {
            items {
                id
                name
                key
                externalId
                accountId
                description
            }
            nextToken
        }
    }
    """
    matches: List[Scorecard] = []
    next_token = None
    while True:
        result = await asyncio.to_thread(
            api_client.execute,
            query,
            {"filter": filter_arg or None, "limit": 1000, "nextToken": next_token},
        )
        page = result.get("listScorecards") or {}
        for row in page.get("items") or []:
            if _casefold_identifier(row.get("name")) == normalized_name:
                matches.append(Scorecard.from_dict(row, api_client))
        next_token = page.get("nextToken")
        if not next_token:
            break

    if not matches:
        return None
    if len(matches) > 1:
        match_ids = ", ".join(f"{match.name} ({match.id})" for match in matches)
        raise ValueError(
            f"Scorecard name '{scorecard_name}' matched multiple scorecards case-insensitively: {match_ids}."
        )
    return matches[0]


async def resolve_scorecard(
    api_client,
    scorecard_identifier: str,
    *,
    account_id: Optional[str] = None,
) -> Scorecard:
    scorecard = None
    if looks_like_uuid(scorecard_identifier):
        try:
            scorecard = await asyncio.to_thread(
                Scorecard.get_by_id,
                id=scorecard_identifier,
                client=api_client,
            )
        except Exception:
            scorecard = None
    if not scorecard:
        for lookup, kwargs in [
            (Scorecard.get_by_key, {"key": scorecard_identifier}),
            (Scorecard.get_by_name, {"name": scorecard_identifier}),
            (Scorecard.get_by_external_id, {"external_id": scorecard_identifier}),
        ]:
            try:
                scorecard = await asyncio.to_thread(lookup, client=api_client, **kwargs)
                if scorecard:
                    break
            except Exception:
                continue
    if not scorecard:
        scorecard = await _find_scorecard_by_case_insensitive_name(
            api_client,
            scorecard_identifier,
            account_id=account_id,
        )
    if not scorecard:
        raise ValueError(f"Scorecard not found for identifier '{scorecard_identifier}'.")
    return scorecard


async def list_scores_for_scorecard(api_client, scorecard_id: str) -> List[ResolvedScoreRef]:
    query = """
    query GetScorecardScores($scorecardId: ID!) {
        getScorecard(id: $scorecardId) {
            sections {
                items {
                    id
                    scores {
                        items {
                            id
                            name
                            key
                            externalId
                            order
                        }
                    }
                }
            }
        }
    }
    """

    result = await asyncio.to_thread(api_client.execute, query, {"scorecardId": scorecard_id})
    scorecard_data = (result or {}).get("getScorecard") or {}

    scores_with_order = []
    sections = ((scorecard_data.get("sections") or {}).get("items") or [])
    for section_index, section in enumerate(sections):
        raw_scores = ((section.get("scores") or {}).get("items") or [])
        for score_index, score_item in enumerate(raw_scores):
            score_id = str(score_item.get("id") or "").strip()
            score_name = str(score_item.get("name") or "").strip()
            if not score_id or not score_name:
                continue
            sort_order = score_item.get("order", score_index)
            scores_with_order.append(
                (
                    section_index,
                    sort_order if sort_order is not None else score_index,
                    ResolvedScoreRef(
                        id=score_id,
                        name=score_name,
                        key=str(score_item.get("key") or "").strip() or None,
                        external_id=str(score_item.get("externalId") or "").strip() or None,
                    ),
                )
            )

    scores_with_order.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scores_with_order]


async def resolve_score_for_scorecard(
    api_client,
    scorecard_id: str,
    score_identifier: str,
) -> ResolvedScoreRef:
    normalized_identifier = str(score_identifier).strip()
    if not normalized_identifier:
        raise ValueError("Score identifier is required.")

    scores_for_scorecard = await list_scores_for_scorecard(api_client, scorecard_id)
    by_id = {entry.id: entry for entry in scores_for_scorecard}

    if looks_like_uuid(normalized_identifier):
        score_obj = None
        try:
            score_obj = await asyncio.to_thread(
                Score.get_by_id,
                id=normalized_identifier,
                client=api_client,
            )
        except Exception:
            score_obj = None

        if not score_obj:
            raise ValueError(
                f"Score not found for identifier '{normalized_identifier}' on scorecard '{scorecard_id}'."
            )

        in_scope = by_id.get(str(score_obj.id))
        if not in_scope:
            raise ValueError(
                f"Score '{normalized_identifier}' does not belong to scorecard '{scorecard_id}'."
            )
        return in_scope

    for entry in scores_for_scorecard:
        if normalized_identifier in {
            entry.id,
            entry.name,
            entry.key or "",
            entry.external_id or "",
        }:
            return entry

    raise ValueError(
        f"Score not found for identifier '{normalized_identifier}' on scorecard '{scorecard_id}'."
    )
