"""Feedback integrity diagnostics for missing score references."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class FeedbackIntegrityWindow:
    start_at: Optional[datetime]
    end_at: Optional[datetime]


def _iso_or_none(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


async def _fetch_feedback_score_refs(
    *,
    api_client: Any,
    account_id: str,
    window: FeedbackIntegrityWindow,
    limit: Optional[int] = None,
) -> List[Dict[str, str]]:
    query = """
    query ListFeedbackIntegrityItems(
      $filter: ModelFeedbackItemFilterInput
      $limit: Int
      $nextToken: String
    ) {
      listFeedbackItems(filter: $filter, limit: $limit, nextToken: $nextToken) {
        items {
          id
          scorecardId
          scoreId
        }
        nextToken
      }
    }
    """
    edited_filter: Dict[str, Any] = {}
    if window.start_at and window.end_at:
        edited_filter["between"] = [_iso_or_none(window.start_at), _iso_or_none(window.end_at)]
    elif window.start_at:
        edited_filter["ge"] = _iso_or_none(window.start_at)
    elif window.end_at:
        edited_filter["le"] = _iso_or_none(window.end_at)

    filter_payload: Dict[str, Any] = {"accountId": {"eq": str(account_id)}}
    if edited_filter:
        filter_payload["editedAt"] = edited_filter

    records: List[Dict[str, str]] = []
    next_token: Optional[str] = None
    hard_limit = max(1, int(limit)) if limit is not None else None

    while True:
        page_size = 1000
        if hard_limit is not None:
            remaining = hard_limit - len(records)
            if remaining <= 0:
                break
            page_size = min(page_size, remaining)

        response = await asyncio.to_thread(
            api_client.execute,
            query,
            {"filter": filter_payload, "limit": page_size, "nextToken": next_token},
        )
        payload = (response or {}).get("listFeedbackItems") or {}
        for item in payload.get("items") or []:
            score_id = str(item.get("scoreId") or "").strip()
            scorecard_id = str(item.get("scorecardId") or "").strip()
            if not score_id:
                continue
            records.append(
                {
                    "scorecard_id": scorecard_id or "unknown",
                    "score_id": score_id,
                }
            )
            if hard_limit is not None and len(records) >= hard_limit:
                break

        if hard_limit is not None and len(records) >= hard_limit:
            break
        next_token = payload.get("nextToken")
        if not next_token:
            break

    return records


async def _resolve_existing_score_ids(
    *,
    api_client: Any,
    score_ids: Set[str],
    max_concurrent: int = 24,
) -> Set[str]:
    query = """
    query GetScoreIntegrity($id: ID!) {
      getScore(id: $id) {
        id
      }
    }
    """
    sem = asyncio.Semaphore(max(1, max_concurrent))
    existing: Set[str] = set()

    async def fetch_one(score_id: str) -> None:
        async with sem:
            try:
                response = await asyncio.to_thread(api_client.execute, query, {"id": score_id})
                score = (response or {}).get("getScore")
                if score and str(score.get("id") or "").strip():
                    existing.add(score_id)
            except Exception:
                # Treat lookup failures as unresolved references for diagnostics.
                return

    await asyncio.gather(*[fetch_one(score_id) for score_id in sorted(score_ids)])
    return existing


async def collect_feedback_score_integrity(
    *,
    api_client: Any,
    account_id: str,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Report feedback references that point to missing Score rows.

    Returns counts by scorecard/score plus overall percentage impact.
    """
    window = FeedbackIntegrityWindow(start_at=start_at, end_at=end_at)
    refs = await _fetch_feedback_score_refs(
        api_client=api_client,
        account_id=account_id,
        window=window,
        limit=limit,
    )

    total = len(refs)
    if total == 0:
        return {
            "account_id": account_id,
            "window": {"start_at": _iso_or_none(start_at), "end_at": _iso_or_none(end_at)},
            "feedback_total": 0,
            "distinct_score_ids_in_feedback": 0,
            "existing_score_ids": 0,
            "missing_score_ids": 0,
            "orphaned_feedback_items": 0,
            "orphaned_percentage": 0.0,
            "orphaned_by_scorecard_score": [],
        }

    distinct_score_ids = {row["score_id"] for row in refs}
    existing_score_ids = await _resolve_existing_score_ids(
        api_client=api_client,
        score_ids=distinct_score_ids,
    )
    missing_score_ids = distinct_score_ids.difference(existing_score_ids)

    orphaned_counter: Counter[Tuple[str, str]] = Counter()
    for row in refs:
        if row["score_id"] in missing_score_ids:
            orphaned_counter[(row["scorecard_id"], row["score_id"])] += 1

    orphaned_feedback_items = sum(orphaned_counter.values())
    orphaned_percentage = (orphaned_feedback_items / total) * 100.0 if total else 0.0
    grouped = [
        {
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "feedback_count": count,
            "percentage_of_feedback": round((count / total) * 100.0, 4),
        }
        for (scorecard_id, score_id), count in orphaned_counter.most_common()
    ]

    return {
        "account_id": account_id,
        "window": {"start_at": _iso_or_none(start_at), "end_at": _iso_or_none(end_at)},
        "feedback_total": total,
        "distinct_score_ids_in_feedback": len(distinct_score_ids),
        "existing_score_ids": len(existing_score_ids),
        "missing_score_ids": len(missing_score_ids),
        "orphaned_feedback_items": orphaned_feedback_items,
        "orphaned_percentage": round(orphaned_percentage, 4),
        "orphaned_score_ids": sorted(missing_score_ids),
        "orphaned_by_scorecard_score": grouped,
    }
