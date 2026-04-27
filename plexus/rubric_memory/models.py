from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceClassification(str, Enum):
    RUBRIC_SUPPORTED = "rubric_supported"
    RUBRIC_CONFLICTING = "rubric_conflicting"
    RUBRIC_GAP = "rubric_gap"
    HISTORICAL_CONTEXT = "historical_context"
    POSSIBLE_STALE_RUBRIC = "possible_stale_rubric"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RubricEvidencePackRequest(BaseModel):
    """Inputs needed to explain one disputed classification."""

    model_config = ConfigDict(extra="forbid")

    scorecard_identifier: str = Field(min_length=1)
    score_identifier: str = Field(min_length=1)
    score_version_id: str = Field(min_length=1)
    rubric_text: str = Field(min_length=1)
    score_code: str = ""
    transcript_text: str = ""
    model_value: str = ""
    model_explanation: str = ""
    feedback_value: str = ""
    feedback_comment: str = ""
    topic_hint: Optional[str] = None

    @field_validator(
        "scorecard_identifier",
        "score_identifier",
        "score_version_id",
        "rubric_text",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field cannot be blank")
        return stripped


class EvidenceSnippet(BaseModel):
    """Corpus evidence with provenance retained from Biblicus retrieval."""

    model_config = ConfigDict(extra="forbid")

    snippet_text: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    scope_level: str = "unknown"
    source_type: str = "unknown"
    authority_level: str = "unknown"
    source_timestamp: Optional[datetime] = None
    author: Optional[str] = None
    retrieval_score: float = 0.0
    policy_concepts: list[str] = Field(default_factory=list)
    evidence_classification: EvidenceClassification = (
        EvidenceClassification.HISTORICAL_CONTEXT
    )

    @field_validator(
        "snippet_text",
        "source_uri",
        "scope_level",
        "source_type",
        "authority_level",
    )
    @classmethod
    def _strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field cannot be blank")
        return stripped

    @field_validator("policy_concepts")
    @classmethod
    def _strip_policy_concepts(cls, value: list[str]) -> list[str]:
        return [concept.strip() for concept in value if concept and concept.strip()]


class RubricHistoryEvent(BaseModel):
    """Chronological policy-memory event derived from corpus evidence."""

    model_config = ConfigDict(extra="forbid")

    source_timestamp: Optional[datetime] = None
    source_uri: str = Field(min_length=1)
    scope_level: str = "unknown"
    authority_level: str = "unknown"
    summary: str = Field(min_length=1)
    evidence_classification: EvidenceClassification = (
        EvidenceClassification.HISTORICAL_CONTEXT
    )


class ConfidenceInputs(BaseModel):
    """Deterministic inputs used by Python to constrain confidence."""

    model_config = ConfigDict(extra="forbid")

    score_version_id: str = Field(min_length=1)
    total_evidence_count: int = Field(ge=0)
    score_scope_evidence_count: int = Field(ge=0)
    prefix_scope_evidence_count: int = Field(default=0, ge=0)
    scorecard_scope_evidence_count: int = Field(ge=0)
    unknown_scope_evidence_count: int = Field(ge=0)
    high_authority_evidence_count: int = Field(ge=0)
    low_authority_evidence_count: int = Field(ge=0)
    conflicting_or_stale_evidence_count: int = Field(ge=0)
    chronological_evidence_count: int = Field(ge=0)
    suggested_confidence: ConfidenceLevel


class RubricEvidencePack(BaseModel):
    """Structured answer for one disputed classification."""

    model_config = ConfigDict(extra="forbid")

    score_version_id: str = Field(min_length=1)
    rubric_reading: str = Field(min_length=1)
    evidence_classification: EvidenceClassification
    supporting_evidence: list[EvidenceSnippet] = Field(default_factory=list)
    conflicting_evidence: list[EvidenceSnippet] = Field(default_factory=list)
    history_of_change: list[RubricHistoryEvent] = Field(default_factory=list)
    likely_reason_for_disagreement: str = Field(min_length=1)
    confidence: ConfidenceLevel
    confidence_inputs: ConfidenceInputs
    open_questions: list[str] = Field(default_factory=list)


class RubricAuthority(BaseModel):
    """Storage-boundary projection of ScoreVersion authority into rubric terms."""

    model_config = ConfigDict(extra="forbid")

    score_version_id: str = Field(min_length=1)
    rubric_text: str = Field(min_length=1)
    score_code: str = ""
