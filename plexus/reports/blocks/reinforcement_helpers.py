from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


async def fetch_item_identifiers(api_client, item_id: Optional[str]) -> Optional[List[Dict[str, str]]]:
    """
    Fetch Item identifiers through the itemId/position index.

    Returns a normalized list ordered by position, or None when no identifiers
    are available.
    """
    if not api_client or not item_id:
        return None

    gql = """
    query ListIdentifiersByItemId($itemId: String!) {
        listIdentifierByItemIdAndPosition(itemId: $itemId) {
            items { name value url position }
        }
    }
    """

    try:
        result = await asyncio.to_thread(api_client.execute, gql, {"itemId": item_id})
    except Exception:
        return None

    raw = (result or {}).get("listIdentifierByItemIdAndPosition", {}).get("items") or []
    if not raw:
        return None

    return [
        {"name": item["name"], "value": item["value"], **({"url": item["url"]} if item.get("url") else {})}
        for item in sorted(raw, key=lambda x: x.get("position") or 0)
    ]


def is_normal_prediction_score_result(score_result: Dict[str, Any]) -> bool:
    """
    Heuristic for normal production ScoreResult rows.
    """
    if score_result.get("evaluationId"):
        return False

    score_type = str(score_result.get("type") or "prediction").strip().lower()
    if score_type != "prediction":
        return False

    status = str(score_result.get("status") or "COMPLETED").strip().upper()
    if status != "COMPLETED":
        return False

    code = str(score_result.get("code") or "200").strip()
    return code == "200"


def parse_iso_timestamp(value: Any) -> Optional[datetime]:
    """
    Parse ISO timestamps consistently and return UTC-aware datetimes.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
