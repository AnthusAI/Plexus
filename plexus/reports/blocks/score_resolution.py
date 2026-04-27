from __future__ import annotations

import asyncio
from typing import Optional

from plexus.dashboard.api.models.score import Score

from .identifier_utils import looks_like_uuid


_GET_SCORECARD_SECTIONS_QUERY = """
query GetScorecardSectionsForScoreResolution($id: ID!) {
    getScorecard(id: $id) {
        sections {
            items {
                id
            }
        }
    }
}
"""


async def scorecard_contains_section(
    api_client,
    scorecard_id: str,
    section_id: str,
) -> bool:
    result = await asyncio.to_thread(
        api_client.execute,
        _GET_SCORECARD_SECTIONS_QUERY,
        {"id": scorecard_id},
    )
    scorecard = (result or {}).get("getScorecard") or {}
    section_ids = {
        str(section.get("id"))
        for section in ((scorecard.get("sections") or {}).get("items") or [])
        if section.get("id")
    }
    if not section_ids:
        raise ValueError(f"Could not resolve sections for scorecard '{scorecard_id}'.")
    return str(section_id) in section_ids


async def resolve_score_for_scorecard(
    api_client,
    score_identifier: str,
    scorecard_id: str,
) -> Optional[Score]:
    if looks_like_uuid(score_identifier):
        try:
            score = await asyncio.to_thread(
                Score.get_by_id,
                id=score_identifier,
                client=api_client,
            )
        except Exception:
            score = None
        if not score:
            return None
        if not getattr(score, "sectionId", None):
            raise ValueError(
                f"Score '{score_identifier}' is missing sectionId and cannot be "
                "validated against the requested scorecard."
            )
        section_in_scorecard = await scorecard_contains_section(
            api_client,
            scorecard_id,
            str(score.sectionId),
        )
        if not section_in_scorecard:
            return None
        return score

    for lookup, kwargs in [
        (Score.get_by_name, {"name": score_identifier, "scorecard_id": scorecard_id}),
        (Score.get_by_key, {"key": score_identifier, "scorecard_id": scorecard_id}),
        (Score.get_by_external_id, {"external_id": score_identifier, "scorecard_id": scorecard_id}),
    ]:
        try:
            score = await asyncio.to_thread(lookup, client=api_client, **kwargs)
            if score:
                return score
        except Exception:
            continue

    return None
