from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from plexus.cli.shared.identifier_resolution import resolve_item_reference
from .reinforcement_helpers import fetch_item_identifiers

from .base import BaseReportBlock
from .feedback_scope_resolver import (
    list_scores_for_scorecard,
    resolve_score_for_scorecard,
    resolve_scorecard,
)


@dataclass(frozen=True)
class _ResolvedScoreScope:
    score_id: str
    score_name: str


@dataclass(frozen=True)
class _ResolvedItem:
    input_identifier: str
    item_id: str
    resolution_source: Optional[str]
    order_index: int
    item_identifiers: Optional[List[Dict[str, str]]] = None


class ScoreResultsReport(BaseReportBlock):
    DEFAULT_NAME = "Score Results Report"
    DEFAULT_DESCRIPTION = "Prediction results for requested item identifiers"
    MAX_PREDICTION_CONCURRENCY = 4

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        try:
            scorecard_identifier_raw = self._get_param("scorecard")
            if not scorecard_identifier_raw:
                raise ValueError("'scorecard' is required.")
            scorecard_identifier = str(scorecard_identifier_raw).strip()
            if not scorecard_identifier:
                raise ValueError("'scorecard' is required.")

            score_identifier_raw = self._get_param("score") or self._get_param("score_id")
            score_identifier = (
                str(score_identifier_raw).strip()
                if score_identifier_raw is not None and str(score_identifier_raw).strip()
                else None
            )

            input_ids = self._parse_ids()
            scorecard = await self._resolve_scorecard(scorecard_identifier)
            scores_to_analyze = await self._resolve_scores_for_mode(
                scorecard_id=scorecard.id,
                score_identifier=score_identifier,
            )
            if not scores_to_analyze:
                raise ValueError("No scores found for the requested scope.")

            account_id = await self._resolve_account_id(scorecard.id)
            resolved_items, unresolved_identifiers = await self._resolve_items(
                input_ids=input_ids,
                account_id=account_id,
            )

            self._log(
                f"Running ScoreResultsReport for scorecard '{scorecard.name}' with "
                f"{len(scores_to_analyze)} score(s), {len(input_ids)} input identifiers, "
                f"{len(resolved_items)} resolved item(s), {len(unresolved_identifiers)} unresolved."
            )

            per_score_results: Dict[str, List[Dict[str, Any]]] = {
                scope.score_id: [] for scope in scores_to_analyze
            }
            failed_predictions: List[Dict[str, Any]] = []

            if resolved_items:
                semaphore = asyncio.Semaphore(self.MAX_PREDICTION_CONCURRENCY)
                tasks = [
                    self._run_prediction_for_item_score_guarded(
                        semaphore=semaphore,
                        scorecard_identifier=scorecard_identifier,
                        score_scope=score_scope,
                        item=item,
                    )
                    for item in resolved_items
                    for score_scope in scores_to_analyze
                ]
                prediction_results = await asyncio.gather(*tasks)
            else:
                prediction_results = []

            for score_id, result_entry, failed_entry in prediction_results:
                per_score_results.setdefault(score_id, []).append(result_entry)
                if failed_entry:
                    failed_predictions.append(failed_entry)

            for score_id, rows in per_score_results.items():
                rows.sort(
                    key=lambda row: (
                        int(row.get("_order_index", 0)),
                        str(row.get("input_identifier") or ""),
                    )
                )
                for row in rows:
                    row.pop("_order_index", None)

            score_outputs: List[Dict[str, Any]] = []
            for scope in scores_to_analyze:
                score_outputs.append(
                    {
                        "score_id": scope.score_id,
                        "score_name": scope.score_name,
                        "results": per_score_results.get(scope.score_id, []),
                    }
                )

            total_predictions = sum(len(score.get("results") or []) for score in score_outputs)
            failed_prediction_count = len(failed_predictions)
            success_prediction_count = max(total_predictions - failed_prediction_count, 0)
            mode = "single_score" if score_identifier else "scorecard_all_scores"

            output: Dict[str, Any] = {
                "report_type": "score_results_report",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scope": mode,
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "score_id": scores_to_analyze[0].score_id if mode == "single_score" else None,
                "score_name": scores_to_analyze[0].score_name if mode == "single_score" else None,
                "ids": input_ids,
                "summary": {
                    "input_identifier_count": len(input_ids),
                    "resolved_item_count": len(resolved_items),
                    "unresolved_identifier_count": len(unresolved_identifiers),
                    "scores_analyzed": len(scores_to_analyze),
                    "total_predictions": total_predictions,
                    "successful_predictions": success_prediction_count,
                    "failed_predictions": failed_prediction_count,
                },
                "scores": score_outputs,
                "unresolved_identifiers": unresolved_identifiers,
                "failed_predictions": failed_predictions,
            }
            output = self._to_json_safe(output)
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating ScoreResultsReport: {exc}", level="ERROR")
            return {
                "report_type": "score_results_report",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "error": str(exc),
                "scores": [],
            }, self._get_log_string()

    def _to_json_safe(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): self._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._to_json_safe(v) for v in value]
        try:
            json.dumps(value)
            return value
        except Exception:
            return str(value)

    def _get_param(self, name: str) -> Any:
        if name in self.config and self.config.get(name) is not None:
            return self.config.get(name)
        if name in self.params and self.params.get(name) is not None:
            return self.params.get(name)
        param_name = f"param_{name}"
        if param_name in self.params and self.params.get(param_name) is not None:
            return self.params.get(param_name)
        return None

    def _parse_ids(self) -> List[str]:
        raw_ids = self._get_param("ids")
        raw_id_flags = self._get_param("id")
        parts: List[str] = []

        def _add(value: Any) -> None:
            if value is None:
                return
            if isinstance(value, (list, tuple, set)):
                for entry in value:
                    _add(entry)
                return
            text = str(value).strip()
            if not text:
                return
            if "," in text:
                for piece in text.split(","):
                    normalized = piece.strip()
                    if normalized:
                        parts.append(normalized)
                return
            parts.append(text)

        _add(raw_ids)
        _add(raw_id_flags)

        deduped: List[str] = []
        seen: set[str] = set()
        for identifier in parts:
            if identifier in seen:
                continue
            seen.add(identifier)
            deduped.append(identifier)

        if not deduped:
            raise ValueError("At least one item identifier is required via 'ids' or 'id'.")
        return deduped

    async def _resolve_scorecard(self, scorecard_identifier: str) -> Any:
        return await resolve_scorecard(self.api_client, scorecard_identifier)

    async def _resolve_scores_for_mode(
        self,
        *,
        scorecard_id: str,
        score_identifier: Optional[str],
    ) -> List[_ResolvedScoreScope]:
        if score_identifier:
            score = await resolve_score_for_scorecard(
                self.api_client,
                scorecard_id,
                score_identifier,
            )
            return [_ResolvedScoreScope(score_id=score.id, score_name=score.name)]

        scores = await list_scores_for_scorecard(self.api_client, scorecard_id)
        return [
            _ResolvedScoreScope(score_id=score.id, score_name=score.name)
            for score in scores
        ]

    async def _resolve_account_id(self, scorecard_id: str) -> str:
        account_id = (
            self._get_param("account_id")
            or self._get_param("param_account_id")
            or getattr(self.api_client, "account_id", None)
        )
        if account_id:
            return str(account_id)

        query = """
        query GetScorecardAccountForScoreResultsReport($id: ID!) {
            getScorecard(id: $id) {
                id
                accountId
            }
        }
        """
        result = await asyncio.to_thread(self.api_client.execute, query, {"id": scorecard_id})
        account_id = ((result or {}).get("getScorecard") or {}).get("accountId")
        if not account_id:
            raise ValueError("Could not resolve account_id required for item identifier resolution.")
        return str(account_id)

    async def _resolve_items(
        self,
        *,
        input_ids: List[str],
        account_id: str,
    ) -> Tuple[List[_ResolvedItem], List[Dict[str, Any]]]:
        resolved: List[_ResolvedItem] = []
        unresolved: List[Dict[str, Any]] = []
        for order_index, identifier in enumerate(input_ids):
            try:
                resolved_ref = await asyncio.to_thread(
                    resolve_item_reference,
                    self.api_client,
                    identifier,
                    account_id,
                )
                if not resolved_ref:
                    unresolved.append(
                        {
                            "input_identifier": identifier,
                            "status": "unresolved",
                            "error": "No item found for identifier.",
                        }
                    )
                    continue

                item_id, source = resolved_ref
                item_identifiers = await fetch_item_identifiers(self.api_client, str(item_id))
                resolved.append(
                    _ResolvedItem(
                        input_identifier=identifier,
                        item_id=str(item_id),
                        resolution_source=str(source) if source is not None else None,
                        order_index=order_index,
                        item_identifiers=item_identifiers,
                    )
                )
            except Exception as exc:
                unresolved.append(
                    {
                        "input_identifier": identifier,
                        "status": "unresolved",
                        "error": str(exc),
                    }
                )
        return resolved, unresolved

    async def _run_prediction_for_item_score_guarded(
        self,
        *,
        semaphore: asyncio.Semaphore,
        scorecard_identifier: str,
        score_scope: _ResolvedScoreScope,
        item: _ResolvedItem,
    ) -> Tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]:
        async with semaphore:
            return await self._run_prediction_for_item_score(
                scorecard_identifier=scorecard_identifier,
                score_scope=score_scope,
                item=item,
            )

    async def _run_prediction_for_item_score(
        self,
        *,
        scorecard_identifier: str,
        score_scope: _ResolvedScoreScope,
        item: _ResolvedItem,
    ) -> Tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]:
        from plexus.cli.prediction.predictions import (
            persist_prediction_score_result,
            predict_score_with_individual_loading,
            select_sample,
        )

        base_result = {
            "input_identifier": item.input_identifier,
            "resolved_item_id": item.item_id,
            "item_identifiers": item.item_identifiers,
            "resolution_source": item.resolution_source,
            "score_id": score_scope.score_id,
            "score_name": score_scope.score_name,
            "_order_index": item.order_index,
        }
        try:
            sample_row, used_item_id = await asyncio.to_thread(
                select_sample,
                scorecard_identifier,
                score_scope.score_name,
                item.item_id,
                False,
            )
            scorecard_instance, prediction_result, costs = await predict_score_with_individual_loading(
                scorecard_identifier=scorecard_identifier,
                score_name=score_scope.score_name,
                sample_row=sample_row,
                used_item_id=used_item_id,
                no_cache=False,
                yaml_only=False,
                specific_version=None,
            )

            if not prediction_result or getattr(prediction_result, "value", None) is None:
                raise ValueError("Prediction returned no value.")

            trace = getattr(prediction_result, "trace", None)
            metadata = getattr(prediction_result, "metadata", None)
            if trace is None and isinstance(metadata, dict):
                trace = metadata.get("trace")
            explanation = (
                getattr(prediction_result, "explanation", None)
                or (metadata.get("explanation") if isinstance(metadata, dict) else "")
                or ""
            )

            score_result = await asyncio.to_thread(
                persist_prediction_score_result,
                scorecard_instance=scorecard_instance,
                scorecard_identifier=scorecard_identifier,
                score_name=score_scope.score_name,
                item_id=used_item_id,
                prediction=prediction_result,
                costs=costs,
                trace=trace,
            )
            result = {
                **base_result,
                "status": "success",
                "score_result_id": getattr(score_result, "id", None),
                "value": getattr(prediction_result, "value", None),
                "explanation": explanation,
                "cost": costs,
                "trace": trace,
                "error": None,
            }
            return score_scope.score_id, result, None
        except Exception as exc:
            result = {
                **base_result,
                "status": "failed",
                "score_result_id": None,
                "value": None,
                "explanation": None,
                "cost": None,
                "trace": None,
                "error": str(exc),
            }
            failed_entry = {
                "input_identifier": item.input_identifier,
                "resolved_item_id": item.item_id,
                "score_id": score_scope.score_id,
                "score_name": score_scope.score_name,
                "error": str(exc),
            }
            self._log(
                f"Prediction failed for item '{item.input_identifier}' ({item.item_id}) "
                f"score '{score_scope.score_name}': {exc}",
                level="WARNING",
            )
            return score_scope.score_id, result, failed_entry
