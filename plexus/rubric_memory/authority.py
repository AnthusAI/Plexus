from __future__ import annotations

import asyncio
from typing import Any

from .models import RubricAuthority


class RubricAuthorityError(RuntimeError):
    """Raised when official ScoreVersion rubric authority cannot be resolved."""


class RubricAuthorityResolver:
    """
    Resolve the canonical rubric and score code from the champion ScoreVersion.

    Plexus storage still names the rubric field ``guidelines``. This class is the
    storage adapter boundary: callers receive ``rubric_text`` and do not need to
    know about the legacy field name.
    """

    def __init__(self, api_client: Any):
        self.api_client = api_client

    async def resolve(self, score_id: str) -> RubricAuthority:
        score_result = await asyncio.to_thread(
            self.api_client.execute,
            """
            query GetScoreChampion($id: ID!) {
                getScore(id: $id) {
                    championVersionId
                }
            }
            """,
            {"id": score_id},
        )
        champion_id = (score_result or {}).get("getScore", {}).get("championVersionId")
        if not champion_id:
            raise RubricAuthorityError(
                f"Score {score_id} does not have a champion ScoreVersion."
            )

        return await self.resolve_score_version(champion_id)

    async def resolve_score_version(self, score_version_id: str) -> RubricAuthority:
        version_result = await asyncio.to_thread(
            self.api_client.execute,
            """
            query GetScoreVersionRubricAuthority($id: ID!) {
                getScoreVersion(id: $id) {
                    guidelines
                    configuration
                }
            }
            """,
            {"id": score_version_id},
        )
        score_version = (version_result or {}).get("getScoreVersion") or {}
        rubric_text = (score_version.get("guidelines") or "").strip()
        if not rubric_text:
            raise RubricAuthorityError(
                f"ScoreVersion {score_version_id} does not contain rubric text."
            )

        return RubricAuthority(
            score_version_id=score_version_id,
            rubric_text=rubric_text,
            score_code=score_version.get("configuration") or "",
        )
