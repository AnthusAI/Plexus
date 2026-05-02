from __future__ import annotations

import asyncio
import difflib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .feedback_rates_base import FeedbackRatesBase
from .feedback_scope_resolver import list_scores_for_scorecard


class ScoreChampionVersionTimeline(FeedbackRatesBase):
    """
    Report block for visualizing score champion changes over time.

    Champion transitions are read only from ScoreVersion.metadata.championHistory.
    Older versions without championHistory are intentionally not inferred.
    """

    DEFAULT_NAME = "Score Champion Version Timeline"
    DEFAULT_DESCRIPTION = "Champion version changes and associated evaluation metrics"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []

        try:
            scorecard_identifier = self._get_param("scorecard")
            if not scorecard_identifier:
                raise ValueError("'scorecard' is required.")

            score_identifier = self._get_param("score") or self._get_param("score_id")
            include_unchanged = self._parse_bool(
                self._get_param("include_unchanged"),
                default=False,
            )
            window_start, window_end = self._resolve_window()
            if window_end <= window_start:
                raise ValueError("'end_date' must be after 'start_date'.")

            scorecard = await self._resolve_scorecard(str(scorecard_identifier))
            scores_to_analyze = await self._resolve_scores_for_mode(
                scorecard_id=scorecard.id,
                score_identifier=str(score_identifier).strip() if score_identifier else None,
            )

            self._log(
                "Running ScoreChampionVersionTimeline for "
                f"scorecard={scorecard.id} score_count={len(scores_to_analyze)} "
                f"start={window_start.isoformat()} end={window_end.isoformat()}"
            )

            score_outputs: List[Dict[str, Any]] = []
            versions_scanned = 0
            evaluations_scanned = 0
            procedure_records_scanned = 0

            for score in scores_to_analyze:
                versions = await self._fetch_score_versions(score["score_id"])
                versions_scanned += len(versions)
                version_by_id = {
                    str(version.get("id")): version
                    for version in versions
                    if str(version.get("id") or "").strip()
                }
                transitions = self._extract_in_window_transitions(
                    versions=versions,
                    score_id=score["score_id"],
                    window_start=window_start,
                    window_end=window_end,
                )
                if not include_unchanged:
                    transitions = [
                        transition
                        for transition in transitions
                        if transition.get("previous_champion_version_id")
                    ]

                if not transitions:
                    continue

                procedures = await self._fetch_optimizer_procedures_for_score(
                    score_id=score["score_id"],
                    window_start=window_start,
                    window_end=window_end,
                )
                procedure_records_scanned += len(procedures)

                points: List[Dict[str, Any]] = []
                completed_evaluations_by_id: Dict[str, Dict[str, Any]] = {}
                for point_index, transition in enumerate(transitions):
                    version_id = transition["version_id"]
                    version = version_by_id.get(version_id) or await self._fetch_score_version_by_id(version_id)
                    if version and version_id not in version_by_id:
                        version_by_id[version_id] = version

                    evaluations = await self._fetch_evaluations_for_version(version_id)
                    evaluations_scanned += len(evaluations)
                    for evaluation in self._completed_evaluations_in_window(
                        evaluations=evaluations,
                        window_start=window_start,
                        window_end=window_end,
                    ):
                        evaluation_id = str(evaluation.get("id") or "").strip()
                        if evaluation_id:
                            completed_evaluations_by_id[evaluation_id] = evaluation

                    feedback_eval = self._select_best_evaluation(evaluations, "feedback")
                    regression_eval = self._select_best_evaluation(evaluations, "accuracy")

                    points.append(
                        {
                            "point_index": point_index,
                            "label": self._transition_label(transition["entered_at"]),
                            "entered_at": transition["entered_at"].isoformat(),
                            "exited_at": transition["exited_at"].isoformat()
                            if transition.get("exited_at")
                            else None,
                            "version_id": version_id,
                            "version_note": version.get("note") if version else None,
                            "version_branch": version.get("branch") if version else None,
                            "previous_champion_version_id": transition.get("previous_champion_version_id"),
                            "next_champion_version_id": transition.get("next_champion_version_id"),
                            "transition_id": transition.get("transition_id"),
                            "feedback_evaluation_id": feedback_eval.get("id") if feedback_eval else None,
                            "feedback_metrics": self._metrics_payload(feedback_eval),
                            "regression_evaluation_id": regression_eval.get("id") if regression_eval else None,
                            "regression_metrics": self._metrics_payload(regression_eval),
                        }
                    )

                diff = await self._build_score_diff(
                    first_transition=transitions[0],
                    latest_transition=transitions[-1],
                    version_by_id=version_by_id,
                )
                optimization_summary = await self._optimization_summary(
                    procedures=procedures,
                    evaluations=list(completed_evaluations_by_id.values()),
                )

                if not self._has_reportable_score_activity(
                    points=points,
                    optimization_summary=optimization_summary,
                ):
                    continue

                score_outputs.append(
                    {
                        "score_id": score["score_id"],
                        "score_name": score["score_name"],
                        "optimization_summary": optimization_summary,
                        "sme": await self._latest_sme_info(procedures),
                        "points": points,
                        "champion_change_count": self._champion_change_count(points),
                        "new_champion_count": self._new_champion_count(points),
                        "diff": diff,
                    }
                )

            effective_window_start, effective_window_end = self._effective_display_window(
                requested_start=window_start,
                requested_end=window_end,
                score_outputs=score_outputs,
            )
            mode = "single_score" if score_identifier else "all_scores"
            output: Dict[str, Any] = {
                "report_type": "score_champion_version_timeline",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scope": mode,
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "requested_date_range": {
                    "start": window_start.isoformat(),
                    "end": window_end.isoformat(),
                },
                "date_range": {
                    "start": effective_window_start.isoformat(),
                    "end": effective_window_end.isoformat(),
                    "normalized_to_activity": effective_window_start != window_start,
                },
                "include_unchanged": include_unchanged,
                "scores": score_outputs,
                "summary": {
                    "scores_analyzed": len(scores_to_analyze),
                    "scores_with_champion_changes": sum(
                        1
                        for score in score_outputs
                        if score["champion_change_count"] > 0
                    ),
                    "scores_with_new_champions": sum(
                        1
                        for score in score_outputs
                        if score["new_champion_count"] > 0
                    ),
                    "champion_change_count": sum(
                        score["champion_change_count"] for score in score_outputs
                    ),
                    "new_champion_count": sum(
                        score["new_champion_count"] for score in score_outputs
                    ),
                    "procedure_count": sum(
                        score["optimization_summary"]["procedure_count"]
                        for score in score_outputs
                    ),
                    "evaluation_count": sum(
                        score["optimization_summary"]["evaluation_count"]
                        for score in score_outputs
                    ),
                    "score_result_count": sum(
                        score["optimization_summary"]["score_result_count"]
                        for score in score_outputs
                    ),
                    "optimization_cost": self._sum_cost_payloads(
                        score["optimization_summary"]["optimization_cost"]
                        for score in score_outputs
                    ),
                    "associated_evaluation_cost": self._sum_number(
                        score["optimization_summary"]["associated_evaluation_cost"]
                        for score in score_outputs
                    ),
                    "score_versions_scanned": versions_scanned,
                    "evaluations_scanned": evaluations_scanned,
                    "procedure_records_scanned": procedure_records_scanned,
                },
                "message": (
                    f"Found {sum(score['champion_change_count'] for score in score_outputs)} "
                    f"champion change(s) across "
                    f"{sum(1 for score in score_outputs if score['champion_change_count'] > 0)} score(s)."
                    if score_outputs
                    else "No champion version changes found in the requested time window."
                ),
            }
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating ScoreChampionVersionTimeline: {exc}", level="ERROR")
            return {
                "report_type": "score_champion_version_timeline",
                "error": str(exc),
                "scores": [],
            }, self._get_log_string()

    def _effective_display_window(
        self,
        *,
        requested_start: datetime,
        requested_end: datetime,
        score_outputs: List[Dict[str, Any]],
    ) -> Tuple[datetime, datetime]:
        entered_times: List[datetime] = []
        for score in score_outputs:
            for point in score.get("points") or []:
                entered_at = self._parse_datetime(point.get("entered_at"))
                if entered_at:
                    entered_times.append(entered_at)

        if not entered_times:
            return requested_start, requested_end

        earliest_activity = min(entered_times)
        padded_start = earliest_activity - timedelta(days=1)
        if padded_start <= requested_start:
            return requested_start, requested_end
        return padded_start, requested_end

    def _champion_change_count(self, points: List[Dict[str, Any]]) -> int:
        return sum(1 for point in points if point.get("previous_champion_version_id"))

    def _new_champion_count(self, points: List[Dict[str, Any]]) -> int:
        return sum(1 for point in points if not point.get("previous_champion_version_id"))

    def _has_reportable_score_activity(
        self,
        *,
        points: List[Dict[str, Any]],
        optimization_summary: Dict[str, Any],
    ) -> bool:
        if any(
            [
                (optimization_summary.get("procedure_count") or 0) > 0,
                (optimization_summary.get("evaluation_count") or 0) > 0,
                (optimization_summary.get("score_result_count") or 0) > 0,
            ]
        ):
            return True

        return self._champion_change_count(points) > 1

    async def _resolve_scores_for_mode(
        self,
        *,
        scorecard_id: str,
        score_identifier: Optional[str],
    ) -> List[Dict[str, str]]:
        if score_identifier:
            score = await self._resolve_score(score_identifier, scorecard_id)
            return [{"score_id": score.id, "score_name": score.name}]

        scores = await list_scores_for_scorecard(self.api_client, scorecard_id)
        return [{"score_id": score.id, "score_name": score.name} for score in scores]

    async def _fetch_score_versions(self, score_id: str) -> List[Dict[str, Any]]:
        query = """
        query ListScoreVersionsByScoreId(
            $scoreId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
            $nextToken: String
        ) {
            listScoreVersionByScoreIdAndCreatedAt(
                scoreId: $scoreId
                sortDirection: $sortDirection
                limit: $limit
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
                {
                    "scoreId": score_id,
                    "sortDirection": "DESC",
                    "limit": 100,
                    "nextToken": next_token,
                },
            )
            payload = (result or {}).get("listScoreVersionByScoreIdAndCreatedAt") or {}
            versions.extend(item for item in payload.get("items") or [] if isinstance(item, dict))
            next_token = payload.get("nextToken")
            if not next_token:
                break
        return versions

    async def _fetch_score_version_by_id(self, version_id: str) -> Optional[Dict[str, Any]]:
        query = """
        query GetScoreVersion($id: ID!) {
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
        query ListEvaluationByScoreVersionIdAndCreatedAt(
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

    async def _fetch_optimizer_procedures_for_score(
        self,
        *,
        score_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict[str, Any]]:
        query = """
        query ListProcedureByScoreIdAndUpdatedAt(
            $scoreId: String!
            $updatedAt: ModelStringKeyConditionInput
            $sortDirection: ModelSortDirection
            $limit: Int
            $nextToken: String
        ) {
            listProcedureByScoreIdAndUpdatedAt(
                scoreId: $scoreId
                updatedAt: $updatedAt
                sortDirection: $sortDirection
                limit: $limit
                nextToken: $nextToken
            ) {
                items {
                    id
                    scoreId
                    scorecardId
                    scoreVersionId
                    category
                    status
                    metadata
                    createdAt
                    updatedAt
                }
                nextToken
            }
        }
        """
        procedures: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        while True:
            result = await asyncio.to_thread(
                self.api_client.execute,
                query,
                {
                    "scoreId": score_id,
                    "updatedAt": {
                        "between": [
                            self._graphql_datetime(window_start),
                            self._graphql_datetime(window_end),
                        ]
                    },
                    "sortDirection": "DESC",
                    "limit": 100,
                    "nextToken": next_token,
                },
            )
            payload = (result or {}).get("listProcedureByScoreIdAndUpdatedAt") or {}
            procedures.extend(
                item
                for item in payload.get("items") or []
                if isinstance(item, dict) and self._is_optimizer_procedure(item)
            )
            next_token = payload.get("nextToken")
            if not next_token:
                break
        return procedures

    def _extract_in_window_transitions(
        self,
        *,
        versions: List[Dict[str, Any]],
        score_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict[str, Any]]:
        transitions: List[Dict[str, Any]] = []
        for version in versions:
            version_id = str(version.get("id") or "").strip()
            metadata = self._parse_json_object(version.get("metadata"))
            history = metadata.get("championHistory")
            if not version_id or not isinstance(history, list):
                continue

            for entry in history:
                if not isinstance(entry, dict):
                    continue
                entry_score_id = str(entry.get("scoreId") or score_id)
                entry_version_id = str(entry.get("versionId") or version_id)
                if entry_score_id != str(score_id) or entry_version_id != version_id:
                    continue

                entered_at = self._parse_datetime(entry.get("enteredAt"))
                if not entered_at:
                    continue
                if not (window_start <= entered_at <= window_end):
                    continue

                transitions.append(
                    {
                        "version_id": version_id,
                        "entered_at": entered_at,
                        "exited_at": self._parse_datetime(entry.get("exitedAt")),
                        "previous_champion_version_id": self._clean_id(
                            entry.get("previousChampionVersionId")
                        ),
                        "next_champion_version_id": self._clean_id(
                            entry.get("nextChampionVersionId")
                        ),
                        "transition_id": self._clean_id(entry.get("transitionId")),
                    }
                )

        transitions.sort(key=lambda item: (item["entered_at"], item["version_id"]))
        return transitions

    def _select_best_evaluation(
        self,
        evaluations: List[Dict[str, Any]],
        evaluation_type: str,
    ) -> Optional[Dict[str, Any]]:
        candidates = [
            evaluation
            for evaluation in evaluations
            if str(evaluation.get("type") or "").lower() == evaluation_type
            and str(evaluation.get("status") or "").upper() == "COMPLETED"
        ]
        if not candidates:
            return None

        def sort_key(evaluation: Dict[str, Any]) -> Tuple[float, datetime]:
            metrics = self._parse_metrics(evaluation)
            alignment = metrics.get("alignment")
            return (
                float(alignment) if isinstance(alignment, (int, float)) else float("-inf"),
                self._parse_datetime(evaluation.get("createdAt"))
                or datetime.min.replace(tzinfo=timezone.utc),
            )

        return max(candidates, key=sort_key)

    def _completed_evaluations_in_window(
        self,
        *,
        evaluations: List[Dict[str, Any]],
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict[str, Any]]:
        completed: List[Dict[str, Any]] = []
        for evaluation in evaluations:
            if str(evaluation.get("status") or "").upper() != "COMPLETED":
                continue
            created_at = self._parse_datetime(evaluation.get("createdAt"))
            if not created_at or not (window_start <= created_at <= window_end):
                continue
            completed.append(evaluation)
        return completed

    def _metrics_payload(self, evaluation: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not evaluation:
            return None
        metrics = self._parse_metrics(evaluation)
        return {
            "alignment": metrics.get("alignment"),
            "accuracy": metrics.get("accuracy"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "cost": metrics.get("cost"),
            "evaluation_id": evaluation.get("id"),
            "evaluation_type": evaluation.get("type"),
            "created_at": evaluation.get("createdAt"),
            "updated_at": evaluation.get("updatedAt"),
            "processed_items": evaluation.get("processedItems"),
            "total_items": evaluation.get("totalItems"),
        }

    async def _optimization_summary(
        self,
        *,
        procedures: List[Dict[str, Any]],
        evaluations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        procedure_costs = [
            await self._procedure_cost_payload(procedure)
            for procedure in procedures
        ]
        evaluation_count = len(evaluations)
        score_result_count = sum(self._evaluation_score_result_count(evaluation) for evaluation in evaluations)
        associated_evaluation_cost = self._sum_number(
            self._parse_metrics(evaluation).get("cost")
            for evaluation in evaluations
        )

        return {
            "procedure_count": len(procedures),
            "evaluation_count": evaluation_count,
            "score_result_count": score_result_count,
            "optimization_cost": self._sum_cost_payloads(procedure_costs),
            "associated_evaluation_cost": associated_evaluation_cost,
            "procedures": [
                {
                    "procedure_id": procedure.get("id"),
                    "status": procedure.get("status"),
                    "created_at": procedure.get("createdAt"),
                    "updated_at": procedure.get("updatedAt"),
                    "cost": cost,
                }
                for procedure, cost in zip(procedures, procedure_costs)
            ],
        }

    async def _latest_sme_info(self, procedures: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not procedures:
            return None

        procedure = procedures[0]
        metadata = self._parse_json_object(procedure.get("metadata"))
        state = await self._load_dashboard_state(
            metadata.get("dashboard_state") or metadata.get("state")
        )
        end_of_run_report = state.get("end_of_run_report") if isinstance(state, dict) else None
        end_of_run_report = end_of_run_report if isinstance(end_of_run_report, dict) else {}

        agenda_gated = self._text_from_sme_value(state.get("sme_agenda_gated"))
        agenda_raw = self._text_from_sme_value(state.get("sme_agenda_raw"))
        end_agenda = self._text_from_sme_value(end_of_run_report.get("sme_agenda"))
        worksheet = self._text_from_sme_value(end_of_run_report.get("sme_worksheet"))

        agenda = agenda_gated or end_agenda or agenda_raw
        available = bool(agenda or worksheet)

        return {
            "procedure_id": procedure.get("id"),
            "procedure_status": procedure.get("status"),
            "procedure_created_at": procedure.get("createdAt"),
            "procedure_updated_at": procedure.get("updatedAt"),
            "available": available,
            "agenda": agenda,
            "agenda_gated": agenda_gated,
            "agenda_raw": agenda_raw,
            "worksheet": worksheet,
            "run_summary": end_of_run_report.get("run_summary")
            if isinstance(end_of_run_report.get("run_summary"), dict)
            else None,
            "generated_at": end_of_run_report.get("generated_at"),
        }

    async def _procedure_cost_payload(self, procedure: Dict[str, Any]) -> Dict[str, Optional[float]]:
        metadata = self._parse_json_object(procedure.get("metadata"))
        dashboard_state_ref = metadata.get("dashboard_state") or metadata.get("state")
        state = await self._load_dashboard_state(dashboard_state_ref)
        costs = state.get("costs") if isinstance(state, dict) else None
        if not isinstance(costs, dict):
            return {
                "overall": None,
                "inference": None,
                "evaluation": None,
            }

        totals = costs.get("totals") if isinstance(costs.get("totals"), dict) else {}
        overall = totals.get("overall") if isinstance(totals.get("overall"), dict) else {}
        inference = totals.get("inference") if isinstance(totals.get("inference"), dict) else {}
        evaluation = totals.get("evaluation") if isinstance(totals.get("evaluation"), dict) else {}
        inference_costs = costs.get("inference") if isinstance(costs.get("inference"), dict) else {}
        evaluation_costs = costs.get("evaluation") if isinstance(costs.get("evaluation"), dict) else {}

        evaluation_incurred = self._first_finite(
            evaluation.get("incurred"),
            evaluation_costs.get("incurred_total"),
        )
        evaluation_reused = self._first_finite(
            evaluation.get("reused"),
            evaluation_costs.get("reused_total"),
        )
        evaluation_total = self._first_finite(
            evaluation.get("total"),
            evaluation_costs.get("total"),
            self._sum_optional_numbers(evaluation_incurred, evaluation_reused),
        )
        inference_total = self._first_finite(
            inference.get("total"),
            inference_costs.get("total"),
        )
        overall_incurred = self._first_finite(
            overall.get("incurred"),
            overall.get("total"),
            self._sum_optional_numbers(evaluation_incurred, inference_total),
            self._sum_optional_numbers(evaluation_total, inference_total),
        )

        return {
            "overall": overall_incurred,
            "inference": inference_total,
            "evaluation": self._first_finite(evaluation_incurred, evaluation_total),
        }

    async def _load_dashboard_state(self, dashboard_state_ref: Any) -> Dict[str, Any]:
        if not isinstance(dashboard_state_ref, dict):
            return {}
        s3_key = dashboard_state_ref.get("_s3_key")
        if not s3_key:
            return dashboard_state_ref

        bucket = str(os.getenv("AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME") or "").strip().strip('"')
        if not bucket:
            self._log("Procedure dashboard_state cost artifact could not be loaded because report block S3 bucket is not configured.", level="WARNING")
            return {}

        try:
            import boto3

            response = await asyncio.to_thread(
                boto3.client("s3").get_object,
                Bucket=bucket,
                Key=str(s3_key),
            )
            raw = await asyncio.to_thread(response["Body"].read)
            parsed = json.loads(raw.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception as exc:
            self._log(
                f"Procedure dashboard_state cost artifact could not be loaded from {s3_key}: {exc}",
                level="WARNING",
            )
            return {}

    def _is_optimizer_procedure(self, procedure: Dict[str, Any]) -> bool:
        metadata = self._parse_json_object(procedure.get("metadata"))
        return str(metadata.get("procedure_type") or "").strip().lower() == "optimizer procedure"

    def _evaluation_score_result_count(self, evaluation: Dict[str, Any]) -> int:
        processed = self._integer(evaluation.get("processedItems"))
        if processed is not None:
            return processed
        total = self._integer(evaluation.get("totalItems"))
        return total or 0

    async def _build_score_diff(
        self,
        *,
        first_transition: Dict[str, Any],
        latest_transition: Dict[str, Any],
        version_by_id: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        left_version_id = first_transition.get("previous_champion_version_id")
        right_version_id = latest_transition.get("version_id")

        left_version = (
            version_by_id.get(left_version_id)
            if left_version_id
            else None
        )
        if left_version_id and left_version is None:
            left_version = await self._fetch_score_version_by_id(left_version_id)
            if left_version:
                version_by_id[left_version_id] = left_version

        right_version = version_by_id.get(right_version_id) if right_version_id else None
        if right_version_id and right_version is None:
            right_version = await self._fetch_score_version_by_id(right_version_id)
            if right_version:
                version_by_id[right_version_id] = right_version

        if not left_version or not right_version:
            return {
                "left_version_id": left_version_id,
                "right_version_id": right_version_id,
                "configuration_diff": None,
                "guidelines_diff": None,
                "message": "Previous or latest champion version was not available for diff generation.",
            }

        return {
            "left_version_id": left_version_id,
            "left_version_note": left_version.get("note"),
            "left_version_created_at": left_version.get("createdAt"),
            "right_version_id": right_version_id,
            "right_version_note": right_version.get("note"),
            "right_version_created_at": right_version.get("createdAt"),
            "configuration_left": left_version.get("configuration") or "",
            "configuration_right": right_version.get("configuration") or "",
            "configuration_diff": self._unified_diff(
                left_version.get("configuration") or "",
                right_version.get("configuration") or "",
                fromfile=f"{left_version_id}/configuration",
                tofile=f"{right_version_id}/configuration",
            ),
            "guidelines_left": left_version.get("guidelines") or "",
            "guidelines_right": right_version.get("guidelines") or "",
            "guidelines_diff": self._unified_diff(
                left_version.get("guidelines") or "",
                right_version.get("guidelines") or "",
                fromfile=f"{left_version_id}/guidelines",
                tofile=f"{right_version_id}/guidelines",
            ),
        }

    def _parse_metrics(self, evaluation: Dict[str, Any]) -> Dict[str, Optional[float]]:
        parsed = self._parse_json_value(evaluation.get("metrics"))
        accuracy_value = self._finite_number(evaluation.get("accuracy"))

        if isinstance(parsed, list):
            values: Dict[str, Optional[float]] = {
                "accuracy": accuracy_value,
                "alignment": None,
                "precision": None,
                "recall": None,
                "cost": None,
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
                if values["cost"] is None and "cost" in name:
                    values["cost"] = number
            return values

        if isinstance(parsed, dict):
            parsed_alignment = self._first_finite(
                parsed.get("alignment"),
                parsed.get("ac1"),
                parsed.get("agreement"),
            )
            parsed_cost = self._first_finite(
                evaluation.get("cost"),
                parsed.get("cost"),
                parsed.get("total_cost"),
                parsed.get("costPerItem"),
            )
            return {
                "accuracy": accuracy_value if accuracy_value is not None else self._finite_number(parsed.get("accuracy")),
                "alignment": parsed_alignment,
                "precision": self._finite_number(parsed.get("precision")),
                "recall": self._finite_number(parsed.get("recall")),
                "cost": parsed_cost,
            }

        return {
            "accuracy": accuracy_value,
            "alignment": None,
            "precision": None,
            "recall": None,
            "cost": self._finite_number(evaluation.get("cost")),
        }

    def _unified_diff(self, left: str, right: str, *, fromfile: str, tofile: str) -> str:
        diff_lines = difflib.unified_diff(
            left.splitlines(),
            right.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
        return "\n".join(diff_lines)

    def _transition_label(self, entered_at: datetime) -> str:
        return entered_at.strftime("%Y-%m-%d")

    def _parse_json_object(self, value: Any) -> Dict[str, Any]:
        parsed = self._parse_json_value(value)
        return parsed if isinstance(parsed, dict) else {}

    def _parse_json_value(self, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return json.loads(stripped)
            except Exception:
                return None
        return value

    def _text_from_sme_value(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, dict):
            text = value.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
            structured = value.get("structured")
            if isinstance(structured, (dict, list)) and structured:
                return json.dumps(structured, indent=2, default=str)
        return None

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
        if number != number or number in (float("inf"), float("-inf")):
            return None
        return number

    def _first_finite(self, *values: Any) -> Optional[float]:
        for value in values:
            number = self._finite_number(value)
            if number is not None:
                return number
        return None

    def _integer(self, value: Any) -> Optional[int]:
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_bool(self, value: Any, *, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "no", "n", "off"}:
                return False
        return default

    def _sum_number(self, values: Any) -> Optional[float]:
        total = 0.0
        found = False
        for value in values:
            number = self._finite_number(value)
            if number is None:
                continue
            total += number
            found = True
        return total if found else None

    def _sum_optional_numbers(self, *values: Any) -> Optional[float]:
        return self._sum_number(values)

    def _sum_cost_payloads(self, payloads: Any) -> Dict[str, Optional[float]]:
        rows = list(payloads)
        if not rows:
            return {
                "overall": None,
                "inference": None,
                "evaluation": None,
            }

        def sum_cost_field(field: str) -> float:
            return self._sum_number(row.get(field) for row in rows if isinstance(row, dict)) or 0.0

        return {
            "overall": sum_cost_field("overall"),
            "inference": sum_cost_field("inference"),
            "evaluation": sum_cost_field("evaluation"),
        }

    def _graphql_datetime(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _clean_id(self, value: Any) -> Optional[str]:
        value_str = str(value or "").strip()
        return value_str or None
