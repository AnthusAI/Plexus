from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .models import RubricEvidencePackRequest


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}

_POLICY_KEYWORDS = {
    "all",
    "confirm",
    "confirmed",
    "current",
    "currently",
    "discontinued",
    "dosage",
    "dose",
    "exclude",
    "excluded",
    "fail",
    "failed",
    "missing",
    "must",
    "no longer",
    "pass",
    "passed",
    "prescribed",
    "required",
    "review",
    "schedule",
    "strength",
    "still taking",
    "taking",
    "verify",
    "verified",
}


@dataclass(frozen=True)
class RubricMemoryQueryPlan:
    expanded_query_text: str
    retrieval_phrases: list[str]
    important_tokens: list[str]


class RubricMemoryQueryPlanner:
    """Build runtime retrieval hints from existing rubric/item context."""

    def __init__(self, *, max_phrases: int = 80):
        self.max_phrases = max_phrases

    def plan(self, request: RubricEvidencePackRequest) -> RubricMemoryQueryPlan:
        phrases = self._build_phrases(request)
        important_tokens = self._important_tokens(phrases)
        expanded_query_text = self._build_query_text(request, phrases)
        return RubricMemoryQueryPlan(
            expanded_query_text=expanded_query_text,
            retrieval_phrases=phrases,
            important_tokens=important_tokens,
        )

    def _build_phrases(self, request: RubricEvidencePackRequest) -> list[str]:
        candidates: list[str] = []
        candidates.extend(self._score_name_phrases(request.score_identifier))
        if request.topic_hint:
            candidates.extend(self._phrase_chunks(request.topic_hint))

        candidates.extend(self._policy_lines(request.rubric_text))
        candidates.extend(self._policy_lines(request.score_code))
        candidates.extend(self._quoted_phrases(request.score_code))
        candidates.extend(self._policy_lines(request.model_explanation))
        candidates.extend(self._policy_lines(request.feedback_comment))
        candidates.extend(self._policy_lines(request.transcript_text))
        candidates.extend(
            self._entity_context_phrases(
                request.transcript_text,
                self._entity_terms(
                    request.model_explanation,
                    request.feedback_comment,
                    request.topic_hint or "",
                ),
            )
        )

        return self._dedupe_phrases(candidates)[: self.max_phrases]

    def _build_query_text(
        self,
        request: RubricEvidencePackRequest,
        phrases: list[str],
    ) -> str:
        parts = [
            f"scorecard: {request.scorecard_identifier}",
            f"score: {request.score_identifier}",
            f"score version: {request.score_version_id}",
            f"topic: {request.topic_hint}" if request.topic_hint else "",
            f"model classification: {request.model_value}",
            f"feedback classification: {request.feedback_value}",
            f"feedback comment: {request.feedback_comment}",
            f"model explanation: {request.model_explanation}",
            "runtime retrieval phrases:\n" + "\n".join(phrases) if phrases else "",
            f"transcript excerpt: {request.transcript_text[:4000]}",
            f"rubric excerpt: {request.rubric_text[:3000]}",
        ]
        return "\n\n".join(part for part in parts if part.strip())

    def _score_name_phrases(self, score_name: str) -> list[str]:
        parts = [
            part.strip()
            for part in re.split(r"[:>/\\-]+", score_name)
            if part.strip()
        ]
        phrases = [score_name.strip(), *parts]
        for left, right in zip(parts, parts[1:]):
            phrases.append(f"{left} {right}")
        return phrases

    def _policy_lines(self, text: str) -> list[str]:
        phrases: list[str] = []
        for raw_line in text.splitlines():
            line = self._clean_phrase(raw_line)
            if not line:
                continue
            if raw_line.lstrip().startswith(("#", "-", "*")):
                phrases.extend(self._phrase_chunks(line))
                continue
            if self._contains_policy_keyword(line):
                phrases.extend(self._phrase_chunks(line))
        return phrases

    def _quoted_phrases(self, text: str) -> list[str]:
        quoted = re.findall(r"['\"]([^'\"]{4,160})['\"]", text)
        return [
            phrase
            for value in quoted
            for phrase in self._phrase_chunks(value)
        ]

    def _entity_terms(self, *texts: str) -> list[str]:
        combined = "\n".join(texts)
        candidates = re.findall(r"\b[A-Za-z][A-Za-z-]{3,}\b", combined)
        return self._dedupe_phrases(
            candidate
            for candidate in candidates
            if candidate.lower() not in _STOPWORDS
        )

    def _entity_context_phrases(
        self,
        text: str,
        entity_terms: Iterable[str],
    ) -> list[str]:
        lower_text = text.lower()
        phrases: list[str] = []
        for entity in entity_terms:
            lower_entity = entity.lower()
            start = lower_text.find(lower_entity)
            if start < 0:
                continue
            context_start = max(0, start - 160)
            context_end = min(len(text), start + len(entity) + 160)
            phrases.extend(self._phrase_chunks(text[context_start:context_end]))
        return phrases

    def _phrase_chunks(self, text: str) -> list[str]:
        cleaned = self._clean_phrase(text)
        if not cleaned:
            return []
        chunks: list[str] = []
        for chunk in re.split(r"[.;|()\[\]{}]+", cleaned):
            chunk = self._clean_phrase(chunk)
            if not chunk:
                continue
            words = self._words(chunk)
            if len(words) < 2:
                if self._contains_policy_keyword(chunk):
                    chunks.append(chunk)
                continue
            if len(words) <= 8:
                chunks.append(chunk)
                continue
            for index in range(0, len(words), 6):
                window = words[index:index + 8]
                if len(window) >= 2:
                    chunks.append(" ".join(window))
        return chunks

    def _dedupe_phrases(self, phrases: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for phrase in phrases:
            cleaned = self._clean_phrase(phrase)
            if not cleaned:
                continue
            normalized = cleaned.lower()
            if normalized in seen:
                continue
            if self._too_generic(cleaned):
                continue
            seen.add(normalized)
            deduped.append(cleaned)
        return deduped

    def _important_tokens(self, phrases: Iterable[str]) -> list[str]:
        tokens: list[str] = []
        for phrase in phrases:
            tokens.extend(self._words(phrase))
        tokens.extend(keyword for keyword in _POLICY_KEYWORDS if " " not in keyword)
        return self._dedupe_phrases(
            token
            for token in tokens
            if len(token) >= 4 and token.lower() not in _STOPWORDS
        )[:120]

    def _too_generic(self, phrase: str) -> bool:
        words = self._words(phrase)
        if not words:
            return True
        if len(words) == 1:
            return words[0] in _STOPWORDS
        non_stopwords = [word for word in words if word not in _STOPWORDS]
        if len(non_stopwords) < 2 and not self._contains_policy_keyword(phrase):
            return True
        return False

    def _contains_policy_keyword(self, text: str) -> bool:
        lower = text.lower()
        return any(keyword in lower for keyword in _POLICY_KEYWORDS)

    def _words(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _clean_phrase(self, phrase: str) -> str:
        cleaned = re.sub(r"\s+", " ", phrase).strip(" \t\r\n-*:;,.#")
        return cleaned[:240]
