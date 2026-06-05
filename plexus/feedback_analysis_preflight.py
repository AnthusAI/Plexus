"""Shared preflight validation for feedback-backed analysis paths."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class FeedbackAnalysisPreflightError(RuntimeError):
    """Typed hard-failure for feedback analysis prerequisites."""

    error_code: str
    root_cause: str
    scorecard_id: Optional[str] = None
    score_id: Optional[str] = None
    score_version_id: Optional[str] = None

    @property
    def diagnostics(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "scorecard_id": self.scorecard_id,
            "score_id": self.score_id,
            "score_version_id": self.score_version_id,
            "root_cause": self.root_cause,
        }

    def __str__(self) -> str:
        return json.dumps(self.diagnostics, sort_keys=True)


@dataclass
class FeedbackAnalysisPreflightResult:
    scorecard_id: str
    score_id: str
    score_version_id: str
    score_version_configuration: Any
    score_guidelines_text: str


def _raise_preflight(
    *,
    error_code: str,
    root_cause: str,
    scorecard_id: Optional[str],
    score_id: Optional[str],
    score_version_id: Optional[str],
) -> None:
    raise FeedbackAnalysisPreflightError(
        error_code=error_code,
        root_cause=root_cause,
        scorecard_id=scorecard_id,
        score_id=score_id,
        score_version_id=score_version_id,
    )


def _has_non_empty_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return len(value) > 0
    return True


def _coerce_guidelines_text(guidelines: Any, configuration: Any) -> str:
    if isinstance(guidelines, str) and guidelines.strip():
        return guidelines
    if isinstance(guidelines, (dict, list)) and guidelines:
        return json.dumps(guidelines, sort_keys=True)
    if isinstance(configuration, str) and configuration.strip():
        return configuration
    if isinstance(configuration, (dict, list)) and configuration:
        return json.dumps(configuration, sort_keys=True)
    return ""


async def validate_feedback_analysis_preflight(
    *,
    api_client: Any,
    scorecard_id: str,
    score_id: str,
    score_version_id: Optional[str],
    require_version_configuration: bool = True,
    require_guidelines_text: bool = True,
) -> FeedbackAnalysisPreflightResult:
    """
    Validate core dependencies before feedback-backed analysis starts.

    Raises FeedbackAnalysisPreflightError on any failed prerequisite.
    """
    normalized_scorecard_id = str(scorecard_id or "").strip()
    normalized_score_id = str(score_id or "").strip()
    normalized_score_version_id = str(score_version_id or "").strip() or None

    if not normalized_scorecard_id:
        _raise_preflight(
            error_code="SCORECARD_UNRESOLVED",
            root_cause="scorecard_id is required but missing.",
            scorecard_id=None,
            score_id=normalized_score_id or None,
            score_version_id=normalized_score_version_id,
        )
    if not normalized_score_id:
        _raise_preflight(
            error_code="SCORE_UNRESOLVED",
            root_cause="score_id is required but missing.",
            scorecard_id=normalized_scorecard_id,
            score_id=None,
            score_version_id=normalized_score_version_id,
        )

    scorecard_query = """
    query GetScorecardPreflight($id: ID!) {
      getScorecard(id: $id) {
        id
      }
    }
    """
    try:
        scorecard_response = await asyncio.to_thread(
            api_client.execute,
            scorecard_query,
            {"id": normalized_scorecard_id},
        )
    except Exception as exc:
        _raise_preflight(
            error_code="SCORECARD_LOOKUP_FAILED",
            root_cause=f"Failed to resolve scorecard: {exc}",
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=normalized_score_version_id,
        )

    scorecard_payload = (scorecard_response or {}).get("getScorecard")
    if not scorecard_payload:
        _raise_preflight(
            error_code="SCORECARD_NOT_FOUND",
            root_cause=f"Scorecard {normalized_scorecard_id} could not be loaded.",
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=normalized_score_version_id,
        )

    score_query = """
    query GetScorePreflight($id: ID!) {
      getScore(id: $id) {
        id
        scorecardId
        championVersionId
      }
    }
    """
    try:
        score_response = await asyncio.to_thread(
            api_client.execute,
            score_query,
            {"id": normalized_score_id},
        )
    except Exception as exc:
        _raise_preflight(
            error_code="SCORE_LOOKUP_FAILED",
            root_cause=f"Failed to resolve score: {exc}",
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=normalized_score_version_id,
        )

    score_payload = (score_response or {}).get("getScore")
    if not score_payload:
        _raise_preflight(
            error_code="SCORE_NOT_FOUND",
            root_cause=f"Score {normalized_score_id} could not be loaded.",
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=normalized_score_version_id,
        )
    if str(score_payload.get("scorecardId") or "").strip() != normalized_scorecard_id:
        _raise_preflight(
            error_code="SCORE_NOT_IN_SCORECARD",
            root_cause=(
                f"Score {normalized_score_id} does not belong to scorecard {normalized_scorecard_id}."
            ),
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=normalized_score_version_id,
        )

    effective_score_version_id = normalized_score_version_id or str(
        score_payload.get("championVersionId") or ""
    ).strip()
    if not effective_score_version_id:
        _raise_preflight(
            error_code="SCORE_VERSION_UNRESOLVED",
            root_cause=(
                "No score version was provided and the score has no championVersionId. "
                "Set --version explicitly or assign a champion version."
            ),
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=normalized_score_version_id,
        )

    score_version_query = """
    query GetScoreVersionPreflight($id: ID!) {
      getScoreVersion(id: $id) {
        id
        scoreId
        guidelines
        configuration
      }
    }
    """
    try:
        score_version_response = await asyncio.to_thread(
            api_client.execute,
            score_version_query,
            {"id": effective_score_version_id},
        )
    except Exception as exc:
        _raise_preflight(
            error_code="SCORE_VERSION_LOOKUP_FAILED",
            root_cause=f"Failed to resolve score version: {exc}",
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=effective_score_version_id,
        )

    score_version_payload = (score_version_response or {}).get("getScoreVersion")
    if not score_version_payload:
        _raise_preflight(
            error_code="SCORE_VERSION_NOT_FOUND",
            root_cause=f"ScoreVersion {effective_score_version_id} could not be loaded.",
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=effective_score_version_id,
        )

    version_score_id = str(score_version_payload.get("scoreId") or "").strip()
    if version_score_id and version_score_id != normalized_score_id:
        _raise_preflight(
            error_code="SCORE_VERSION_MISMATCH",
            root_cause=(
                f"ScoreVersion {effective_score_version_id} belongs to score {version_score_id}, "
                f"expected {normalized_score_id}."
            ),
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=effective_score_version_id,
        )

    configuration = score_version_payload.get("configuration")
    guidelines = score_version_payload.get("guidelines")
    if require_version_configuration and not _has_non_empty_payload(configuration):
        _raise_preflight(
            error_code="SCORE_VERSION_CONFIGURATION_MISSING",
            root_cause=(
                f"ScoreVersion {effective_score_version_id} has no configuration payload. "
                "Republish or repair this score version before running feedback analysis."
            ),
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=effective_score_version_id,
        )

    guidelines_text = _coerce_guidelines_text(guidelines, configuration)
    if require_guidelines_text and not guidelines_text.strip():
        _raise_preflight(
            error_code="SCORE_GUIDELINES_MISSING",
            root_cause=(
                f"ScoreVersion {effective_score_version_id} returned empty guidelines/configuration text."
            ),
            scorecard_id=normalized_scorecard_id,
            score_id=normalized_score_id,
            score_version_id=effective_score_version_id,
        )

    return FeedbackAnalysisPreflightResult(
        scorecard_id=normalized_scorecard_id,
        score_id=normalized_score_id,
        score_version_id=effective_score_version_id,
        score_version_configuration=configuration,
        score_guidelines_text=guidelines_text,
    )
