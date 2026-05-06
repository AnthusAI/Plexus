from __future__ import annotations

import asyncio
import difflib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseReportBlock
from .feedback_scope_resolver import (
    list_scores_for_scorecard,
    resolve_score_for_scorecard,
    resolve_scorecard,
)


@dataclass(frozen=True)
class _ResolvedScoreHistoryScope:
    score_id: str
    score_name: str
    champion_version_id: Optional[str]


class ScorecardHistory(BaseReportBlock):
    """
    Report block summarizing featured ScoreVersion changes over a date window.

    Scope:
    - scorecard only: all scores on the scorecard
    - scorecard + score/score_id: a single score on the scorecard
    """

    DEFAULT_NAME = "Scorecard History"
    DEFAULT_DESCRIPTION = "Featured score-version changes and champion promotion status"
    DEFAULT_DAYS = 30
    SUMMARY_DIFF_CHAR_LIMIT = 1500
    PER_SCORE_SUMMARY_BATCH_SIZE = 4
    PER_SCORE_SUMMARY_BATCH_PAYLOAD_CHAR_LIMIT = 45000
    REQUIRED_SUMMARY_SECTION_HEADINGS = (
        "What changed",
        "Guideline / rubric changes",
        "Scoring behavior changes",
        "Questions for SMEs / stakeholders",
        "Rollout and evidence",
    )

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []

        try:
            scorecard_identifier = self._get_param("scorecard")
            if not scorecard_identifier:
                raise ValueError("'scorecard' is required.")

            score_identifier = self._get_param("score") or self._get_param("score_id")
            if score_identifier is not None:
                score_identifier = str(score_identifier).strip() or None

            window_start, window_end = self._resolve_window_utc()
            scorecard = await self._resolve_scorecard(str(scorecard_identifier))
            scores_to_analyze = await self._resolve_scores_for_mode(
                scorecard_id=scorecard.id,
                score_identifier=score_identifier,
            )

            self._log(
                f"Running ScorecardHistory for scorecard '{scorecard.name}' "
                f"with {len(scores_to_analyze)} score(s), "
                f"start={window_start.isoformat()}, end={window_end.isoformat()}"
            )

            score_outputs: List[Dict[str, Any]] = []
            summary_inputs: List[Dict[str, Any]] = []

            for score_scope in scores_to_analyze:
                versions = await self._fetch_versions_for_score(score_scope.score_id)
                versions_by_id = {
                    str(version.get("id")): version
                    for version in versions
                    if version.get("id")
                }
                included_versions = self._select_featured_versions(
                    versions=versions,
                    start_date=window_start,
                    end_date=window_end,
                )

                if not included_versions:
                    continue

                version_entries: List[Dict[str, Any]] = []
                for version in included_versions:
                    entry = await self._build_version_entry(
                        score_scope=score_scope,
                        version=version,
                        versions_by_id=versions_by_id,
                        start_date=window_start,
                        end_date=window_end,
                    )
                    version_entries.append(entry)

                champion_version_count = sum(
                    1 for entry in version_entries if entry["champion_status"]["is_champion_related"]
                )
                score_output = {
                    "score_id": score_scope.score_id,
                    "score_name": score_scope.score_name,
                    "featured_version_count": len(version_entries),
                    "champion_version_count": champion_version_count,
                    "versions": version_entries,
                }
                window_diff = self._build_score_window_diff(
                    versions=versions,
                    included_versions=included_versions,
                )
                if window_diff:
                    score_output["window_diff"] = window_diff
                performance = await self._build_score_performance(
                    versions=versions,
                    included_versions=included_versions,
                )
                if performance:
                    score_output["performance"] = performance
                sme_question_context = await self._build_score_sme_question_context(
                    score_id=score_scope.score_id,
                    version_entries=version_entries,
                )
                if sme_question_context:
                    score_output["sme_question_context"] = sme_question_context
                score_outputs.append(score_output)
                summary_inputs.append(self._build_score_summary_input(score_output))

            mode = "single_score" if score_identifier else "scorecard_all_scores"
            featured_version_count = sum(score["featured_version_count"] for score in score_outputs)
            champion_version_count = sum(score["champion_version_count"] for score in score_outputs)
            guideline_change_count = sum(
                1
                for score in score_outputs
                for version in score.get("versions", [])
                if version.get("diffs", {}).get("guidelines", {}).get("has_changes")
            )
            code_change_count = sum(
                1
                for score in score_outputs
                for version in score.get("versions", [])
                if version.get("diffs", {}).get("code", {}).get("has_changes")
            )
            champion_coverage = self._champion_coverage(
                featured_version_count=featured_version_count,
                champion_version_count=champion_version_count,
            )
            if not score_outputs:
                summary_payload = self._empty_summary()
            else:
                summary_payload = await self._generate_summary_payload(
                    scorecard_name=scorecard.name,
                    mode=mode,
                    start_date=window_start,
                    end_date=window_end,
                    featured_version_count=featured_version_count,
                    champion_version_count=champion_version_count,
                    guideline_change_count=guideline_change_count,
                    code_change_count=code_change_count,
                    scores_changed_count=len(score_outputs),
                    champion_coverage=champion_coverage,
                    score_summaries=summary_inputs,
                )
                per_score_summaries = await self._generate_per_score_summaries_batched(
                    scorecard_name=scorecard.name,
                    mode=mode,
                    start_date=window_start,
                    end_date=window_end,
                    score_summaries=summary_inputs,
                )
                for score_output in score_outputs:
                    score_output["summary"] = per_score_summaries[score_output["score_id"]].strip()

            output: Dict[str, Any] = {
                "report_type": "scorecard_history",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scope": mode,
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "score_id": scores_to_analyze[0].score_id if mode == "single_score" and scores_to_analyze else None,
                "score_name": scores_to_analyze[0].score_name if mode == "single_score" and scores_to_analyze else None,
                "date_range": {
                    "start": window_start.isoformat(),
                    "end": window_end.isoformat(),
                },
                "summary": {
                    "text": str(summary_payload.get("overall_summary") or "").strip(),
                    "champion_coverage": champion_coverage,
                    "featured_version_count": featured_version_count,
                    "champion_version_count": champion_version_count,
                    "scores_changed_count": len(score_outputs),
                },
                "scores": score_outputs,
            }

            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating ScorecardHistory: {exc}", level="ERROR")
            return {
                "report_type": "scorecard_history",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "error": str(exc),
                "scores": [],
            }, self._get_log_string()

    def _get_param(self, name: str) -> Any:
        if name in self.config and self.config.get(name) is not None:
            return self.config.get(name)
        if name in self.params and self.params.get(name) is not None:
            return self.params.get(name)
        param_name = f"param_{name}"
        if param_name in self.params and self.params.get(param_name) is not None:
            return self.params.get(param_name)
        return None

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _parse_dt(self, value: Any, *, is_end: bool) -> datetime:
        value_str = str(value).strip()
        date_only = len(value_str) == 10 and value_str[4] == "-" and value_str[7] == "-"
        try:
            dt = datetime.fromisoformat(value_str.replace("Z", "+00:00"))
            if date_only:
                if is_end:
                    dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                else:
                    dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        except Exception:
            dt = datetime.strptime(value_str, "%Y-%m-%d")
            if is_end:
                dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            else:
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _resolve_window_utc(self) -> Tuple[datetime, datetime]:
        start_date_raw = self._get_param("start_date")
        end_date_raw = self._get_param("end_date")
        days_raw = self._get_param("days")

        if (start_date_raw and not end_date_raw) or (end_date_raw and not start_date_raw):
            raise ValueError("Both 'start_date' and 'end_date' are required when specifying explicit date windows.")
        if days_raw is not None and start_date_raw and end_date_raw:
            raise ValueError("Use either 'days' or 'start_date'+'end_date', not both.")

        if start_date_raw and end_date_raw:
            start_date = self._parse_dt(start_date_raw, is_end=False)
            end_date = self._parse_dt(end_date_raw, is_end=True)
        else:
            days = int(days_raw) if days_raw is not None else self.DEFAULT_DAYS
            if days <= 0:
                raise ValueError("'days' must be a positive integer.")
            end_date = self._now_utc()
            start_date = end_date - timedelta(days=days)

        if end_date <= start_date:
            raise ValueError("'end_date' must be after 'start_date'.")
        return start_date, end_date

    async def _resolve_scorecard(self, scorecard_identifier: str) -> Any:
        return await resolve_scorecard(self.api_client, scorecard_identifier)

    async def _resolve_scores_for_mode(
        self,
        *,
        scorecard_id: str,
        score_identifier: Optional[str],
    ) -> List[_ResolvedScoreHistoryScope]:
        if score_identifier:
            score = await resolve_score_for_scorecard(
                self.api_client,
                scorecard_id,
                score_identifier,
            )
            champion_version_id = await self._fetch_champion_version_id(score.id)
            return [
                _ResolvedScoreHistoryScope(
                    score_id=score.id,
                    score_name=score.name,
                    champion_version_id=champion_version_id,
                )
            ]

        scores = await list_scores_for_scorecard(self.api_client, scorecard_id)
        scopes: List[_ResolvedScoreHistoryScope] = []
        for score in scores:
            scopes.append(
                _ResolvedScoreHistoryScope(
                    score_id=score.id,
                    score_name=score.name,
                    champion_version_id=await self._fetch_champion_version_id(score.id),
                )
            )
        return scopes

    async def _fetch_champion_version_id(self, score_id: str) -> Optional[str]:
        query = """
        query GetScoreChampionVersionForHistory($id: ID!) {
            getScore(id: $id) {
                id
                championVersionId
            }
        }
        """
        result = await asyncio.to_thread(self.api_client.execute, query, {"id": score_id})
        score_data = (result or {}).get("getScore") or {}
        value = score_data.get("championVersionId")
        return str(value).strip() if value else None

    async def _fetch_versions_for_score(self, score_id: str) -> List[Dict[str, Any]]:
        query = """
        query ListScoreVersionsForScorecardHistory($scoreId: String!, $nextToken: String) {
            listScoreVersionByScoreIdAndCreatedAt(
                scoreId: $scoreId,
                sortDirection: ASC,
                limit: 100,
                nextToken: $nextToken
            ) {
                items {
                    id
                    scoreId
                    configuration
                    guidelines
                    isFeatured
                    note
                    branch
                    parentVersionId
                    metadata
                    createdAt
                    updatedAt
                }
                nextToken
            }
        }
        """

        versions: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        while True:
            result = await asyncio.to_thread(
                self.api_client.execute,
                query,
                {"scoreId": score_id, "nextToken": next_token},
            )
            page = (result or {}).get("listScoreVersionByScoreIdAndCreatedAt") or {}
            versions.extend(item for item in page.get("items") or [] if isinstance(item, dict))
            next_token = page.get("nextToken")
            if not next_token:
                break
        return versions

    async def _fetch_score_version_by_id(self, version_id: str) -> Optional[Dict[str, Any]]:
        query = """
        query GetScoreVersionForScorecardHistory($id: ID!) {
            getScoreVersion(id: $id) {
                id
                scoreId
                configuration
                guidelines
                isFeatured
                note
                branch
                parentVersionId
                metadata
                createdAt
                updatedAt
            }
        }
        """
        result = await asyncio.to_thread(self.api_client.execute, query, {"id": version_id})
        version = (result or {}).get("getScoreVersion")
        return version if isinstance(version, dict) else None

    async def _fetch_evaluations_for_version(self, score_version_id: str) -> List[Dict[str, Any]]:
        query = """
        query ListEvaluationsForScorecardHistory(
            $scoreVersionId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
            $nextToken: String
        ) {
            listEvaluationByScoreVersionIdAndCreatedAt(
                scoreVersionId: $scoreVersionId
                sortDirection: $sortDirection
                limit: $limit
                nextToken: $nextToken
            ) {
                items {
                    id
                    type
                    status
                    createdAt
                    updatedAt
                    parameters
                    scoreId
                    scoreVersionId
                    accuracy
                    processedItems
                    totalItems
                    metrics
                    cost
                    taskId
                }
                nextToken
            }
        }
        """
        evaluations: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        while True:
            result = await asyncio.to_thread(
                self.api_client.execute,
                query,
                {
                    "scoreVersionId": score_version_id,
                    "sortDirection": "DESC",
                    "limit": 100,
                    "nextToken": next_token,
                },
            )
            payload = (result or {}).get("listEvaluationByScoreVersionIdAndCreatedAt") or {}
            evaluations.extend(item for item in payload.get("items") or [] if isinstance(item, dict))
            next_token = payload.get("nextToken")
            if not next_token:
                break
        return evaluations

    async def _fetch_procedures_for_version(self, score_version_id: str, *, limit: int = 5) -> List[Dict[str, Any]]:
        query = """
        query ListProceduresForScorecardHistory(
            $scoreVersionId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
            $nextToken: String
        ) {
            listProcedureByScoreVersionIdAndUpdatedAt(
                scoreVersionId: $scoreVersionId
                sortDirection: $sortDirection
                limit: $limit
                nextToken: $nextToken
            ) {
                items {
                    id
                    name
                    status
                    metadata
                    scoreVersionId
                    createdAt
                    updatedAt
                }
                nextToken
            }
        }
        """
        result = await asyncio.to_thread(
            self.api_client.execute,
            query,
            {
                "scoreVersionId": score_version_id,
                "sortDirection": "DESC",
                "limit": limit,
                "nextToken": None,
            },
        )
        if not isinstance(result, dict):
            return []
        payload = result.get("listProcedureByScoreVersionIdAndUpdatedAt") or {}
        if not isinstance(payload, dict):
            return []
        return [item for item in payload.get("items") or [] if isinstance(item, dict)]

    async def _fetch_procedures_for_score(self, score_id: str, *, limit: int = 12) -> List[Dict[str, Any]]:
        query = """
        query ListProceduresForScorecardHistoryScore(
            $scoreId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
            $nextToken: String
        ) {
            listProcedureByScoreIdAndUpdatedAt(
                scoreId: $scoreId
                sortDirection: $sortDirection
                limit: $limit
                nextToken: $nextToken
            ) {
                items {
                    id
                    name
                    status
                    metadata
                    scoreId
                    scoreVersionId
                    createdAt
                    updatedAt
                }
                nextToken
            }
        }
        """
        result = await asyncio.to_thread(
            self.api_client.execute,
            query,
            {
                "scoreId": score_id,
                "sortDirection": "DESC",
                "limit": limit,
                "nextToken": None,
            },
        )
        if not isinstance(result, dict):
            return []
        payload = result.get("listProcedureByScoreIdAndUpdatedAt") or {}
        if not isinstance(payload, dict):
            return []
        return [item for item in payload.get("items") or [] if isinstance(item, dict)]

    def _select_featured_versions(
        self,
        *,
        versions: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        selected = [
            version for version in versions
            if self._is_featured(version) and self._in_window(version.get("createdAt"), start_date, end_date)
        ]
        selected.sort(key=lambda version: self._to_dt(version.get("createdAt")).timestamp())
        return selected

    def _select_predecessor_version(
        self,
        *,
        versions: List[Dict[str, Any]],
        first_included_version: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        first_created_at = self._to_dt(first_included_version.get("createdAt"))
        predecessors = [
            version
            for version in versions
            if version.get("id") != first_included_version.get("id")
            and self._to_dt(version.get("createdAt")) < first_created_at
        ]
        if not predecessors:
            return None
        return max(predecessors, key=lambda version: self._to_dt(version.get("createdAt")).timestamp())

    def _is_featured(self, version: Dict[str, Any]) -> bool:
        return str(version.get("isFeatured") or "").strip().lower() == "true"

    def _in_window(self, value: Any, start_date: datetime, end_date: datetime) -> bool:
        dt = self._to_dt(value)
        return start_date <= dt <= end_date

    def _to_dt(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            raise ValueError(f"Expected datetime-compatible value, got {type(value).__name__}.")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    async def _build_version_entry(
        self,
        *,
        score_scope: _ResolvedScoreHistoryScope,
        version: Dict[str, Any],
        versions_by_id: Dict[str, Dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        version_id = str(version.get("id") or "").strip()
        parent_version_id = str(version.get("parentVersionId") or "").strip() or None
        parent_version = versions_by_id.get(parent_version_id or "")
        if parent_version_id and not parent_version:
            parent_version = await self._fetch_score_version_by_id(parent_version_id)

        champion_promotions = self._champion_promotions_in_window(
            version=version,
            start_date=start_date,
            end_date=end_date,
        )
        is_current_champion = version_id == score_scope.champion_version_id
        is_champion_related = is_current_champion or bool(champion_promotions)

        return {
            "version_id": version_id,
            "score_id": score_scope.score_id,
            "note": version.get("note") or "",
            "branch": version.get("branch"),
            "created_at": version.get("createdAt"),
            "updated_at": version.get("updatedAt"),
            "parent_version_id": parent_version_id,
            "champion_status": {
                "is_current_champion": is_current_champion,
                "is_champion_related": is_champion_related,
                "promotions_in_window": champion_promotions,
            },
            "diffs": {
                "code": self._build_diff_payload(
                    parent_version=parent_version,
                    version=version,
                    field="configuration",
                    original_label="Parent Code",
                    modified_label="Version Code",
                ),
                "guidelines": self._build_diff_payload(
                    parent_version=parent_version,
                    version=version,
                    field="guidelines",
                    original_label="Parent Guidelines",
                    modified_label="Version Guidelines",
                ),
            },
        }

    def _champion_promotions_in_window(
        self,
        *,
        version: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        metadata = self._parse_json_object(version.get("metadata"))
        history = metadata.get("championHistory")
        if not isinstance(history, list):
            return []

        promotions = []
        for entry in history:
            if not isinstance(entry, dict):
                continue
            entered_at = entry.get("enteredAt")
            if not entered_at or not self._in_window(entered_at, start_date, end_date):
                continue
            promotions.append({
                "entered_at": entered_at,
                "exited_at": entry.get("exitedAt"),
                "previous_champion_version_id": entry.get("previousChampionVersionId"),
                "next_champion_version_id": entry.get("nextChampionVersionId"),
                "transition_id": entry.get("transitionId"),
            })
        promotions.sort(key=lambda entry: self._to_dt(entry["entered_at"]).timestamp())
        return promotions

    def _build_diff_payload(
        self,
        *,
        parent_version: Optional[Dict[str, Any]],
        version: Dict[str, Any],
        field: str,
        original_label: str,
        modified_label: str,
    ) -> Dict[str, Any]:
        original = str((parent_version or {}).get(field) or "")
        modified = str(version.get(field) or "")
        return {
            "original_version_id": (parent_version or {}).get("id"),
            "modified_version_id": version.get("id"),
            "original_label": original_label,
            "modified_label": modified_label,
            "original": original,
            "modified": modified,
            "unified_diff": self._build_unified_diff(
                original,
                modified,
                fromfile=f"{(parent_version or {}).get('id') or 'none'}/{field}",
                tofile=f"{version.get('id')}/{field}",
            ),
            "has_changes": original != modified,
        }

    def _build_unified_diff(self, original: str, modified: str, *, fromfile: str, tofile: str) -> str:
        return "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile=fromfile,
                tofile=tofile,
            )
        )

    def _build_score_window_diff(
        self,
        *,
        versions: List[Dict[str, Any]],
        included_versions: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not included_versions:
            return None

        baseline_version = self._select_predecessor_version(
            versions=versions,
            first_included_version=included_versions[0],
        )
        latest_version = included_versions[-1]
        if not baseline_version:
            return None

        return {
            "baseline_version_id": baseline_version.get("id"),
            "latest_version_id": latest_version.get("id"),
            "baseline_created_at": baseline_version.get("createdAt"),
            "latest_created_at": latest_version.get("createdAt"),
            "code": self._build_diff_payload(
                parent_version=baseline_version,
                version=latest_version,
                field="configuration",
                original_label="Pre-window Code",
                modified_label="Latest Code",
            ),
            "guidelines": self._build_diff_payload(
                parent_version=baseline_version,
                version=latest_version,
                field="guidelines",
                original_label="Pre-window Guidelines",
                modified_label="Latest Guidelines",
            ),
        }

    async def _build_score_performance(
        self,
        *,
        versions: List[Dict[str, Any]],
        included_versions: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not included_versions:
            return None

        current_version = included_versions[-1]
        current_version_id = str(current_version.get("id") or "").strip()
        if not current_version_id:
            return None

        baseline_version = self._select_predecessor_version(
            versions=versions,
            first_included_version=included_versions[0],
        )
        baseline_version_id = str((baseline_version or {}).get("id") or "").strip() or None

        current_evaluations = await self._fetch_evaluations_for_version(current_version_id)
        baseline_evaluations = (
            await self._fetch_evaluations_for_version(baseline_version_id)
            if baseline_version_id
            else []
        )

        feedback_eval = self._select_best_evaluation(current_evaluations, "feedback")
        feedback_baseline_eval = self._select_best_evaluation(baseline_evaluations, "feedback")
        regression_eval = self._select_best_evaluation(
            current_evaluations,
            "accuracy",
            require_dataset=True,
        )
        regression_dataset_id = self._evaluation_dataset_id(regression_eval)
        regression_baseline_eval = (
            self._select_best_evaluation(
                baseline_evaluations,
                "accuracy",
                require_dataset=True,
                dataset_id=regression_dataset_id,
            )
            if regression_dataset_id
            else None
        )

        performance: Dict[str, Any] = {
            "current_version_id": current_version_id,
            "baseline_version_id": baseline_version_id,
        }
        feedback_payload = self._performance_kind_payload(
            current_eval=feedback_eval,
            baseline_eval=feedback_baseline_eval,
        )
        if feedback_payload:
            performance["recent_feedback"] = feedback_payload

        regression_payload = self._performance_kind_payload(
            current_eval=regression_eval,
            baseline_eval=regression_baseline_eval,
        )
        if regression_payload:
            performance["regression"] = regression_payload

        return performance if any(key in performance for key in ("recent_feedback", "regression")) else None

    def _performance_kind_payload(
        self,
        *,
        current_eval: Optional[Dict[str, Any]],
        baseline_eval: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        current = self._metrics_payload(current_eval)
        if not current:
            return None
        payload = {"current": current}
        baseline = self._metrics_payload(baseline_eval)
        if baseline:
            payload["baseline"] = baseline
        return payload

    def _select_best_evaluation(
        self,
        evaluations: List[Dict[str, Any]],
        evaluation_type: str,
        *,
        require_dataset: bool = False,
        dataset_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        for evaluation in evaluations:
            if str(evaluation.get("type") or "").lower() != evaluation_type:
                continue
            if str(evaluation.get("status") or "").upper() != "COMPLETED":
                continue
            evaluation_dataset_id = self._evaluation_dataset_id(evaluation)
            if require_dataset and not evaluation_dataset_id:
                continue
            if dataset_id and evaluation_dataset_id != dataset_id:
                continue
            candidates.append(evaluation)

        if not candidates:
            return None

        def sort_key(evaluation: Dict[str, Any]) -> Tuple[float, datetime]:
            metrics = self._parse_metrics(evaluation)
            alignment = metrics.get("alignment")
            return (
                float(alignment) if isinstance(alignment, (int, float)) else float("-inf"),
                self._parse_datetime(evaluation.get("createdAt")) or datetime.min.replace(tzinfo=timezone.utc),
            )

        return max(candidates, key=sort_key)

    def _metrics_payload(self, evaluation: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not evaluation:
            return None

        metrics = {
            key: value
            for key, value in self._parse_metrics(evaluation).items()
            if key in ("alignment", "accuracy", "precision", "recall") and value is not None
        }
        if not metrics:
            return None

        payload: Dict[str, Any] = {
            "evaluation_id": evaluation.get("id"),
            "evaluation_type": evaluation.get("type"),
            "created_at": evaluation.get("createdAt"),
            "updated_at": evaluation.get("updatedAt"),
            "processed_items": evaluation.get("processedItems"),
            "total_items": evaluation.get("totalItems"),
            "metrics": metrics,
        }
        dataset_id = self._evaluation_dataset_id(evaluation)
        if dataset_id:
            payload["dataset_id"] = dataset_id
        root_cause_topics = self._extract_root_cause_topics(evaluation)
        if root_cause_topics:
            payload["root_cause_topics"] = root_cause_topics
        return payload

    def _extract_root_cause_topics(self, evaluation: Dict[str, Any], *, limit: int = 5) -> List[Dict[str, Any]]:
        parameters = self._parse_json_object(evaluation.get("parameters"))
        root_cause = parameters.get("root_cause")
        if not isinstance(root_cause, dict):
            return []

        topics = root_cause.get("topics")
        if not isinstance(topics, list):
            return []

        extracted: List[Dict[str, Any]] = []
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            label = (
                topic.get("label")
                or topic.get("name")
                or topic.get("title")
                or topic.get("topic")
            )
            summary = (
                topic.get("summary")
                or topic.get("description")
                or topic.get("explanation")
                or topic.get("root_cause")
            )
            item_count = topic.get("item_count") or topic.get("count") or topic.get("n")
            entry = {
                key: value
                for key, value in {
                    "label": str(label).strip() if label else None,
                    "summary": self._limit_text(str(summary).strip()) if summary else None,
                    "item_count": item_count,
                }.items()
                if value not in (None, "")
            }
            if entry:
                extracted.append(entry)
            if len(extracted) >= limit:
                break
        return extracted

    def _evaluation_dataset_id(self, evaluation: Optional[Dict[str, Any]]) -> Optional[str]:
        if not evaluation:
            return None

        for value in (evaluation.get("dataSetId"), evaluation.get("datasetId")):
            if value:
                return str(value).strip()

        parameters = self._parse_json_object(evaluation.get("parameters"))
        for key in ("dataset_id", "dataSetId", "datasetId"):
            value = parameters.get(key)
            if value:
                return str(value).strip()
        return None

    def _parse_metrics(self, evaluation: Dict[str, Any]) -> Dict[str, Optional[float]]:
        parsed = self._parse_json_value(evaluation.get("metrics"))
        accuracy_value = self._finite_number(evaluation.get("accuracy"))

        if isinstance(parsed, list):
            values: Dict[str, Optional[float]] = {
                "accuracy": accuracy_value,
                "alignment": None,
                "precision": None,
                "recall": None,
            }
            for metric in parsed:
                if not isinstance(metric, dict):
                    continue
                name = str(metric.get("name") or metric.get("label") or "").lower()
                number = self._finite_number(metric.get("value"))
                if number is None:
                    continue
                if values["accuracy"] is None and "accuracy" in name:
                    values["accuracy"] = number
                if values["alignment"] is None and ("alignment" in name or "ac1" in name):
                    values["alignment"] = number
                if values["precision"] is None and "precision" in name:
                    values["precision"] = number
                if values["recall"] is None and "recall" in name:
                    values["recall"] = number
            return values

        if isinstance(parsed, dict):
            return {
                "accuracy": accuracy_value if accuracy_value is not None else self._finite_number(parsed.get("accuracy")),
                "alignment": self._first_finite(
                    parsed.get("alignment"),
                    parsed.get("ac1"),
                    parsed.get("agreement"),
                ),
                "precision": self._finite_number(parsed.get("precision")),
                "recall": self._finite_number(parsed.get("recall")),
            }

        return {
            "accuracy": accuracy_value,
            "alignment": None,
            "precision": None,
            "recall": None,
        }

    def _build_score_summary_input(self, score_output: Dict[str, Any]) -> Dict[str, Any]:
        versions = []
        for version in score_output["versions"]:
            code_diff = str(version["diffs"]["code"]["unified_diff"] or "")
            guidelines_diff = str(version["diffs"]["guidelines"]["unified_diff"] or "")
            versions.append({
                "version_id": version["version_id"],
                "created_at": version["created_at"],
                "note": version["note"],
                "is_current_champion": version["champion_status"]["is_current_champion"],
                "promotions_in_window": version["champion_status"]["promotions_in_window"],
                "code_diff": self._limit_text(code_diff),
                "guidelines_diff": self._limit_text(guidelines_diff),
            })
        guideline_change_count = sum(
            1
            for version in score_output.get("versions") or []
            if version.get("diffs", {}).get("guidelines", {}).get("has_changes")
        )
        code_change_count = sum(
            1
            for version in score_output.get("versions") or []
            if version.get("diffs", {}).get("code", {}).get("has_changes")
        )
        return {
            "score_id": score_output["score_id"],
            "score_name": score_output["score_name"],
            "featured_version_count": score_output["featured_version_count"],
            "champion_version_count": score_output["champion_version_count"],
            "champion_coverage": self._champion_coverage(
                featured_version_count=int(score_output.get("featured_version_count") or 0),
                champion_version_count=int(score_output.get("champion_version_count") or 0),
            ),
            "guideline_change_count": guideline_change_count,
            "code_change_count": code_change_count,
            "sme_question_context": score_output.get("sme_question_context") or [],
            "evaluation_context": self._build_score_evaluation_context(score_output),
            "versions": versions,
        }

    async def _build_score_sme_question_context(
        self,
        *,
        score_id: str,
        version_entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        contexts: List[Dict[str, Any]] = []
        seen_texts = set()
        version_ids = {
            str(version.get("version_id") or "").strip()
            for version in version_entries
            if version.get("version_id")
        }
        procedures_by_id: Dict[str, Dict[str, Any]] = {}
        for version in sorted(version_entries, key=lambda entry: str(entry.get("created_at") or ""), reverse=True):
            version_id = str(version.get("version_id") or "").strip()
            if not version_id:
                continue
            procedures = await self._fetch_procedures_for_version(version_id, limit=3)
            for procedure in procedures:
                if procedure.get("id"):
                    procedures_by_id[str(procedure["id"])] = procedure
                self._append_procedure_sme_contexts(
                    contexts=contexts,
                    seen_texts=seen_texts,
                    procedure=procedure,
                    version_id=version_id,
                )
                if len(contexts) >= 8:
                    return contexts

        score_procedures = await self._fetch_procedures_for_score(score_id, limit=12)
        for procedure in score_procedures:
            if procedure.get("id") and str(procedure["id"]) in procedures_by_id:
                continue
            procedure_version_id = str(procedure.get("scoreVersionId") or "").strip()
            metadata_text = json.dumps(self._parse_json_object(procedure.get("metadata")), default=str)
            related_version_id = procedure_version_id if procedure_version_id in version_ids else None
            if not related_version_id:
                related_version_id = next((version_id for version_id in version_ids if version_id in metadata_text), None)
            self._append_procedure_sme_contexts(
                contexts=contexts,
                seen_texts=seen_texts,
                procedure=procedure,
                version_id=related_version_id,
            )
            if len(contexts) >= 8:
                return contexts
        return contexts

    def _append_procedure_sme_contexts(
        self,
        *,
        contexts: List[Dict[str, Any]],
        seen_texts: set,
        procedure: Dict[str, Any],
        version_id: Optional[str],
    ) -> None:
        for text in self._extract_procedure_sme_texts(procedure):
            normalized = re.sub(r"\s+", " ", text).strip().lower()
            if not normalized or normalized in seen_texts:
                continue
            seen_texts.add(normalized)
            contexts.append({
                "version_id": version_id,
                "procedure_id": procedure.get("id"),
                "procedure_name": procedure.get("name"),
                "procedure_status": procedure.get("status"),
                "procedure_updated_at": procedure.get("updatedAt"),
                "text": self._limit_text(text),
            })
            if len(contexts) >= 8:
                return

    def _extract_procedure_sme_texts(self, procedure: Dict[str, Any]) -> List[str]:
        metadata = self._parse_json_object(procedure.get("metadata"))
        state = self._load_procedure_state_from_metadata(metadata)
        texts: List[str] = []

        def add_text(value: Any) -> None:
            text = self._extract_text_value(value)
            if not text:
                return
            lower = text.lower()
            if "not available" in lower or "no sme decisions needed" in lower:
                return
            texts.append(text)

        for root in (state, metadata):
            if not isinstance(root, dict):
                continue
            end_report = root.get("end_of_run_report")
            if isinstance(end_report, dict):
                sme_agenda = end_report.get("sme_agenda")
                if isinstance(sme_agenda, dict):
                    add_text(sme_agenda.get("text"))
                else:
                    add_text(sme_agenda)
                sme_worksheet = end_report.get("sme_worksheet")
                if isinstance(sme_worksheet, dict):
                    add_text(sme_worksheet.get("text"))

            add_text(root.get("sme_agenda_gated"))
            add_text(root.get("sme_agenda"))

            cycle_insights = root.get("cycle_insights")
            if isinstance(cycle_insights, list):
                for insight in reversed(cycle_insights):
                    if not isinstance(insight, dict):
                        continue
                    add_text(insight.get("sme_agenda"))
                    add_text(insight.get("sme_worksheet"))
                    if len(texts) >= 6:
                        break

        return texts[:6]

    def _load_procedure_state_from_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        state_ref = metadata.get("dashboard_state") or metadata.get("state") or {}
        if isinstance(state_ref, dict) and "_s3_key" in state_ref:
            try:
                from plexus.cli.shared.optimizer_results import (
                    _download_json_from_s3_key,
                    _resolve_report_block_bucket_name,
                )

                bucket_name = _resolve_report_block_bucket_name()
                if not bucket_name:
                    return {}
                return _download_json_from_s3_key(bucket_name=bucket_name, key=str(state_ref["_s3_key"]))
            except Exception as exc:
                self._log(f"Could not load procedure state from S3 for SME questions: {exc}", level="WARNING")
                return {}
        return state_ref if isinstance(state_ref, dict) else {}

    def _extract_text_value(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("text", "markdown", "content", "summary"):
                text = self._extract_text_value(value.get(key))
                if text:
                    return text
        return ""

    def _build_score_evaluation_context(self, score_output: Dict[str, Any]) -> Dict[str, Any]:
        performance = score_output.get("performance") or {}
        contexts: Dict[str, Any] = {}
        for key in ("recent_feedback", "regression"):
            current = (performance.get(key) or {}).get("current") or {}
            entry = {
                field: current.get(field)
                for field in (
                    "evaluation_id",
                    "evaluation_type",
                    "created_at",
                    "dataset_id",
                    "processed_items",
                    "total_items",
                    "metrics",
                    "root_cause_topics",
                )
                if current.get(field) not in (None, "", [], {})
            }
            if entry:
                contexts[key] = entry
        return contexts

    def _limit_text(self, text: str) -> str:
        if len(text) <= self.SUMMARY_DIFF_CHAR_LIMIT:
            return text
        return text[: self.SUMMARY_DIFF_CHAR_LIMIT] + "\n[diff truncated for summary prompt]"

    async def _generate_summary_payload(
        self,
        *,
        scorecard_name: str,
        mode: str,
        start_date: datetime,
        end_date: datetime,
        featured_version_count: int,
        champion_version_count: int,
        guideline_change_count: int,
        code_change_count: int,
        scores_changed_count: int,
        champion_coverage: str,
        score_summaries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        prompt_payload = {
            "scorecard_name": scorecard_name,
            "scope": mode,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "overall_counts": {
                "scores_changed_count": scores_changed_count,
                "featured_version_count": featured_version_count,
                "champion_version_count": champion_version_count,
                "guideline_change_count": guideline_change_count,
                "code_change_count": code_change_count,
                "champion_coverage": champion_coverage,
            },
            "scores": score_summaries,
        }
        prompt = (
            "Summarize the featured score-version history below for stakeholders and SMEs.\n"
            "The JSON object must contain exactly one key named overall_summary.\n"
            "The value of overall_summary must be a single Markdown string containing categorized bullet lists, not paragraphs.\n"
            "Write in plain stakeholder language: describe what the score now expects or treats differently, not how the implementation changed.\n"
            "Focus first on rubric, policy, and guidelines meaning. These are the changes SMEs and client stakeholders need to understand.\n"
            "Also include code/prompt-only changes, but translate them into high-level scoring behavior terms.\n"
            "Avoid technical implementation terms unless they are unavoidable: do not mention YAML, nodes, classifiers, data classes, external IDs, parent versions, diff mechanics, or prompt internals.\n"
            "Do not list every version. Combine related same-score changes into one bullet when they represent the same stakeholder-level change.\n"
            "Keep the whole summary short enough to use at the start of a client meeting: normally 6 to 10 nested bullets total.\n"
            "Inside the Markdown string, use these exact top-level bullets in this order:\n"
            "- **What changed**\n"
            "- **Guideline / rubric changes**\n"
            "- **Scoring behavior changes**\n"
            "- **Questions for SMEs / stakeholders**\n"
            "- **Rollout and evidence**\n"
            "Under **What changed**, give the fastest plain-language summary of the important changes across the scorecard.\n"
            "Under **Guideline / rubric changes**, summarize changed SME-facing decision rules. If overall_counts.guideline_change_count is greater than 0, do not say no rubric wording changed; summarize the rubric meaning of those changes.\n"
            "Only say no rubric wording changed when overall_counts.guideline_change_count is exactly 0.\n"
            "Under **Scoring behavior changes**, summarize important code/prompt-only behavior changes in stakeholder terms, such as what the score is stricter about, more permissive about, or now handles more consistently.\n"
            "Under **Questions for SMEs / stakeholders**, list 2 to 5 concrete rubric-clarification questions that would help improve future scoring.\n"
            "Use each score's sme_question_context first; it comes from optimizer procedure SME agendas and worksheets linked to the score versions.\n"
            "When sme_question_context is absent or thin, derive concise questions from evaluation_context.root_cause_topics, version notes, and diffs.\n"
            "Only include questions that require SME or stakeholder policy judgment. Do not include engineering tasks, model tuning tasks, metric interpretation, or requests to inspect YAML.\n"
            "Phrase every item as a question. Keep each question short enough to read aloud in a meeting.\n"
            "Under **Rollout and evidence**, use overall_counts.champion_coverage exactly when describing promotion coverage: all, none, or some. Do not infer a different coverage from the narrative notes.\n"
            "Mention evaluation evidence only when the supplied data supports it.\n"
            "Use score names so readers can tell which area changed, but do not include version IDs.\n"
            "Use version notes as the source of per-version intent and use diffs only to clarify the plain-language change.\n"
            "Do not write filler like 'this got better' unless the supplied evaluation data supports it.\n"
            "The response must be valid JSON, not Python dict syntax. Use double quotes for every key and string.\n"
            "The first character of the response must be { and the last character must be }.\n"
            "Return only strict JSON with exactly this shape:\n"
            "{\n"
            '  "overall_summary": "- **What changed**\\n  - ...\\n- **Guideline / rubric changes**\\n  - ...\\n- **Scoring behavior changes**\\n  - ...\\n- **Questions for SMEs / stakeholders**\\n  - ...\\n- **Rollout and evidence**\\n  - ..."\n'
            "}\n\n"
            f"History data:\n{json.dumps(prompt_payload, indent=2, sort_keys=False)}"
        )
        system_prompt = (
            "You write concise stakeholder-facing scorecard change summaries for client and SME meetings. "
            "Prioritize rubric meaning and operational impact over technical implementation detail. "
            "Do not invent score versions, dates, promotions, or outcomes not present in the data."
        )
        raw_response = await self._run_tac_inference(prompt, system_prompt=system_prompt)
        return self._parse_summary_response(raw_response)

    async def _generate_per_score_summary_payload(
        self,
        *,
        scorecard_name: str,
        mode: str,
        start_date: datetime,
        end_date: datetime,
        score_summaries: List[Dict[str, Any]],
    ) -> Optional[str]:
        prompt_payload = {
            "scorecard_name": scorecard_name,
            "scope": mode,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "scores": score_summaries,
        }
        prompt = (
            "Generate one stakeholder-facing summary per score from the score history JSON below.\n"
            "Return strict JSON with exactly one key named per_score_summaries.\n"
            "per_score_summaries must be an object keyed by score_id.\n"
            "Include every provided score_id exactly once; do not add extra keys.\n"
            "Each value must be a non-empty Markdown string and must use these exact top-level bullets in this order:\n"
            "- **What changed**\n"
            "- **Guideline / rubric changes**\n"
            "- **Scoring behavior changes**\n"
            "- **Questions for SMEs / stakeholders**\n"
            "- **Rollout and evidence**\n"
            "Write in stakeholder language, not engineering language.\n"
            "Do not mention implementation internals such as YAML, prompt wiring, nodes, data classes, parent versions, or diff mechanics.\n"
            "Focus on rubric meaning, behavioral impact, and SME clarification questions.\n"
            "Use score-specific evidence from version notes, diffs, champion context, evaluation context, and SME question context.\n"
            "In the narrative, do not include version IDs.\n"
            "Under **Questions for SMEs / stakeholders**, include 2 to 5 concise policy questions.\n"
            "If no rubric wording changed for a score, state that explicitly under **Guideline / rubric changes**.\n"
            "Under **Rollout and evidence**, mention champion_coverage for that score and include evaluation evidence only if present.\n"
            "The response must be valid JSON with double quotes for all keys and strings.\n"
            "Return only JSON in this shape:\n"
            "{\n"
            '  "per_score_summaries": {\n'
            '    "<score_id>": "- **What changed**\\n  - ...\\n- **Guideline / rubric changes**\\n  - ...\\n- **Scoring behavior changes**\\n  - ...\\n- **Questions for SMEs / stakeholders**\\n  - ...\\n- **Rollout and evidence**\\n  - ..."\n'
            "  }\n"
            "}\n\n"
            f"Score history data:\n{json.dumps(prompt_payload, indent=2, sort_keys=False)}"
        )
        system_prompt = (
            "You write concise score-by-score summaries for SME and stakeholder meetings. "
            "Prioritize rubric meaning, policy clarity, and operational impact. "
            "Do not invent facts, scores, promotions, or evaluation outcomes."
        )
        return await self._run_tac_inference(prompt, system_prompt=system_prompt)

    def _per_score_summary_payload_size(
        self,
        *,
        scorecard_name: str,
        mode: str,
        start_date: datetime,
        end_date: datetime,
        score_summaries: List[Dict[str, Any]],
    ) -> int:
        payload = {
            "scorecard_name": scorecard_name,
            "scope": mode,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "scores": score_summaries,
        }
        return len(json.dumps(payload, indent=2, sort_keys=False))

    def _build_per_score_summary_batches(
        self,
        *,
        scorecard_name: str,
        mode: str,
        start_date: datetime,
        end_date: datetime,
        score_summaries: List[Dict[str, Any]],
    ) -> List[List[Dict[str, Any]]]:
        if not score_summaries:
            return []

        batches: List[List[Dict[str, Any]]] = []
        current_batch: List[Dict[str, Any]] = []
        for score_summary in score_summaries:
            candidate_batch = current_batch + [score_summary]
            payload_size = self._per_score_summary_payload_size(
                scorecard_name=scorecard_name,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                score_summaries=candidate_batch,
            )
            exceeds_count = len(candidate_batch) > self.PER_SCORE_SUMMARY_BATCH_SIZE
            exceeds_payload = payload_size > self.PER_SCORE_SUMMARY_BATCH_PAYLOAD_CHAR_LIMIT

            if current_batch and (exceeds_count or exceeds_payload):
                batches.append(current_batch)
                current_batch = [score_summary]
                single_payload_size = self._per_score_summary_payload_size(
                    scorecard_name=scorecard_name,
                    mode=mode,
                    start_date=start_date,
                    end_date=end_date,
                    score_summaries=current_batch,
                )
                if single_payload_size > self.PER_SCORE_SUMMARY_BATCH_PAYLOAD_CHAR_LIMIT:
                    score_id = str(score_summary.get("score_id") or "")
                    self._log(
                        f"Single score summary payload exceeds char limit for score '{score_id}' "
                        f"({single_payload_size} > {self.PER_SCORE_SUMMARY_BATCH_PAYLOAD_CHAR_LIMIT}).",
                        level="WARNING",
                    )
                continue

            current_batch = candidate_batch

        if current_batch:
            batches.append(current_batch)
        return batches

    async def _generate_per_score_summaries_batched(
        self,
        *,
        scorecard_name: str,
        mode: str,
        start_date: datetime,
        end_date: datetime,
        score_summaries: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        expected_score_ids = [str(score.get("score_id") or "").strip() for score in score_summaries]
        expected_score_ids = [score_id for score_id in expected_score_ids if score_id]
        initial_batches = self._build_per_score_summary_batches(
            scorecard_name=scorecard_name,
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            score_summaries=score_summaries,
        )
        self._log(
            f"Generating per-score summaries in {len(initial_batches)} initial batch(es) "
            f"for {len(expected_score_ids)} score(s)."
        )

        merged_summaries: Dict[str, str] = {}
        for index, batch in enumerate(initial_batches, start=1):
            parsed_batch = await self._generate_per_score_batch_with_adaptive_split(
                scorecard_name=scorecard_name,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                batch_score_summaries=batch,
                batch_label=f"{index}/{len(initial_batches)}",
            )

            duplicate_ids = sorted(set(merged_summaries.keys()) & set(parsed_batch.keys()))
            if duplicate_ids:
                raise ValueError(
                    "LLM per-score summary response included duplicate score ids across batches: "
                    + ", ".join(duplicate_ids)
                )
            merged_summaries.update(parsed_batch)

        expected_set = set(expected_score_ids)
        merged_set = set(merged_summaries.keys())
        missing_ids = sorted(expected_set - merged_set)
        extra_ids = sorted(merged_set - expected_set)
        if missing_ids:
            raise ValueError(
                "LLM per-score summary merged response missing score ids: "
                + ", ".join(missing_ids)
            )
        if extra_ids:
            raise ValueError(
                "LLM per-score summary merged response included unexpected score ids: "
                + ", ".join(extra_ids)
            )

        return merged_summaries

    async def _generate_per_score_batch_with_adaptive_split(
        self,
        *,
        scorecard_name: str,
        mode: str,
        start_date: datetime,
        end_date: datetime,
        batch_score_summaries: List[Dict[str, Any]],
        batch_label: str,
    ) -> Dict[str, str]:
        queue: List[List[Dict[str, Any]]] = [batch_score_summaries]
        parsed_output: Dict[str, str] = {}
        attempt = 0

        while queue:
            segment = queue.pop(0)
            attempt += 1
            segment_ids = [str(score.get("score_id") or "").strip() for score in segment]
            segment_ids = [score_id for score_id in segment_ids if score_id]
            self._log(
                f"Per-score summary batch {batch_label} attempt {attempt} "
                f"(scores={len(segment_ids)} ids={','.join(segment_ids)})"
            )

            raw_payload = await self._generate_per_score_summary_payload(
                scorecard_name=scorecard_name,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                score_summaries=segment,
            )
            try:
                parsed_segment = self._parse_per_score_summary_response(
                    raw_payload,
                    expected_score_ids=segment_ids,
                )
            except Exception as exc:
                if len(segment_ids) > 1:
                    midpoint = len(segment) // 2
                    left_segment = segment[:midpoint]
                    right_segment = segment[midpoint:]
                    self._log(
                        f"Per-score summary batch {batch_label} attempt {attempt} failed; "
                        f"splitting segment into sizes {len(left_segment)} and {len(right_segment)}. "
                        f"Failure: {exc}",
                        level="WARNING",
                    )
                    queue = [left_segment, right_segment] + queue
                    continue
                raise ValueError(
                    f"LLM per-score summary batch {batch_label} failed "
                    f"for score ids {', '.join(segment_ids)}: {exc}"
                ) from exc

            duplicate_ids = sorted(set(parsed_output.keys()) & set(parsed_segment.keys()))
            if duplicate_ids:
                raise ValueError(
                    f"LLM per-score summary batch {batch_label} produced duplicate score ids "
                    f"within split retries: {', '.join(duplicate_ids)}"
                )
            parsed_output.update(parsed_segment)

        expected_segment_ids = [
            str(score.get("score_id") or "").strip()
            for score in batch_score_summaries
            if str(score.get("score_id") or "").strip()
        ]
        expected_segment_set = set(expected_segment_ids)
        parsed_segment_set = set(parsed_output.keys())
        missing_ids = sorted(expected_segment_set - parsed_segment_set)
        extra_ids = sorted(parsed_segment_set - expected_segment_set)
        if missing_ids:
            raise ValueError(
                f"LLM per-score summary batch {batch_label} merged response missing score ids: "
                + ", ".join(missing_ids)
            )
        if extra_ids:
            raise ValueError(
                f"LLM per-score summary batch {batch_label} merged response included unexpected score ids: "
                + ", ".join(extra_ids)
            )

        return parsed_output

    def _parse_summary_response(self, raw_response: Optional[str]) -> Dict[str, Any]:
        if not raw_response or not raw_response.strip():
            raise ValueError("LLM summary response was empty.")

        text = raw_response.strip()
        fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
        if fenced_match:
            text = fenced_match.group(1).strip()

        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM summary response must be a JSON object.")
        if not isinstance(parsed.get("overall_summary"), str):
            raise ValueError("LLM summary response missing 'overall_summary'.")
        return parsed

    def _parse_per_score_summary_response(
        self,
        raw_response: Optional[str],
        *,
        expected_score_ids: List[str],
    ) -> Dict[str, str]:
        if not raw_response or not raw_response.strip():
            raise ValueError("LLM per-score summary response was empty.")

        text = raw_response.strip()
        fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
        if fenced_match:
            text = fenced_match.group(1).strip()

        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM per-score summary response must be a JSON object.")
        per_score_summaries = parsed.get("per_score_summaries")
        if not isinstance(per_score_summaries, dict):
            raise ValueError("LLM per-score summary response missing 'per_score_summaries'.")

        expected_ids = {str(score_id) for score_id in expected_score_ids}
        returned_ids = {str(score_id) for score_id in per_score_summaries.keys()}
        missing_ids = sorted(expected_ids - returned_ids)
        extra_ids = sorted(returned_ids - expected_ids)
        if missing_ids:
            raise ValueError(f"LLM per-score summary response missing score ids: {', '.join(missing_ids)}")
        if extra_ids:
            raise ValueError(f"LLM per-score summary response included unexpected score ids: {', '.join(extra_ids)}")

        output: Dict[str, str] = {}
        for score_id in expected_ids:
            summary = per_score_summaries.get(score_id)
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError(f"LLM per-score summary missing non-empty markdown for score id '{score_id}'.")
            self._validate_required_summary_sections(summary, label=f"score '{score_id}'")
            output[score_id] = summary.strip()
        return output

    def _validate_required_summary_sections(self, summary_markdown: str, *, label: str) -> None:
        for heading in self.REQUIRED_SUMMARY_SECTION_HEADINGS:
            pattern = rf"(?m)^\s*-\s*\*\*{re.escape(heading)}\*\*\s*$"
            if not re.search(pattern, summary_markdown):
                raise ValueError(
                    f"LLM summary for {label} is missing required section heading '**{heading}**'."
                )

    def _parse_json_object(self, value: Any) -> Dict[str, Any]:
        parsed = self._parse_json_value(value)
        return parsed if isinstance(parsed, dict) else {}

    def _parse_json_value(self, value: Any) -> Any:
        if isinstance(value, str) and value.strip():
            try:
                return json.loads(value)
            except Exception:
                return None
        return value

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str) and value.strip():
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _finite_number(self, value: Any) -> Optional[float]:
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _first_finite(self, *values: Any) -> Optional[float]:
        for value in values:
            number = self._finite_number(value)
            if number is not None:
                return number
        return None

    async def _run_tac_inference(self, user_message: str, system_prompt: str = "") -> Optional[str]:
        try:
            provider = str(self._get_param("summary_llm_provider") or "openai")
            model = str(self._get_param("summary_llm_model") or "gpt-4o-mini")
            if provider.lower() == "openai":
                return await self._run_openai_json_inference(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    model=model,
                )

            from tactus.adapters.memory import MemoryStorage
            from tactus.core.runtime import TactusRuntime

            model_lower = model.lower()
            is_reasoning = any(token in model_lower for token in ("gpt-5", "o3", "o4"))
            tac_name = "single_turn_inference_reasoning.tac" if is_reasoning else "single_turn_inference.tac"
            tac_path = os.path.join(os.path.dirname(__file__), "..", "procedures", tac_name)

            with open(tac_path) as tac_file:
                tac_source = (
                    tac_file.read()
                    .replace("{{PROVIDER}}", provider)
                    .replace("{{MODEL}}", model)
                )

            runtime = TactusRuntime(
                procedure_id="scorecard_history_summary_inference",
                storage_backend=MemoryStorage(),
                openai_api_key=os.environ.get("OPENAI_API_KEY"),
            )
            result = await runtime.execute(
                tac_source,
                context={"user_message": user_message, "system_prompt": system_prompt},
                format="lua",
            )

            procedure_output = result.get("result", result) if isinstance(result, dict) else result
            text = self._extract_tactus_text(procedure_output)
            return text.strip() or None
        except Exception as exc:
            raise RuntimeError(f"LLM summary generation failed: {exc}") from exc

    async def _run_openai_json_inference(self, *, user_message: str, system_prompt: str, model: str) -> Optional[str]:
        def _invoke() -> str:
            from openai import OpenAI

            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=4096,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            content = response.choices[0].message.content if response.choices else ""
            return str(content or "").strip()

        return await asyncio.to_thread(_invoke)

    def _extract_tactus_text(self, value: Any, *, depth: int = 0) -> str:
        if value is None or depth > 8:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            if isinstance(value.get("overall_summary"), str):
                return json.dumps(value)
            for key in ("reason", "text", "output", "content", "message", "response", "result"):
                extracted = self._extract_tactus_text(value.get(key), depth=depth + 1)
                if extracted:
                    return extracted
            for nested in value.values():
                extracted = self._extract_tactus_text(nested, depth=depth + 1)
                if extracted:
                    return extracted
            return ""
        if isinstance(value, list):
            for item in value:
                extracted = self._extract_tactus_text(item, depth=depth + 1)
                if extracted:
                    return extracted
            return ""
        return ""

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            "overall_summary": "No featured score versions were created in the requested time window.",
        }

    def _champion_coverage(self, *, featured_version_count: int, champion_version_count: int) -> str:
        if featured_version_count == 0 or champion_version_count == 0:
            return "none"
        if featured_version_count == champion_version_count:
            return "all"
        return "some"
