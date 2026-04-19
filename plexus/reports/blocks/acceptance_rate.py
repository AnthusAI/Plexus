from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .feedback_rates_base import FeedbackRatesBase


class AcceptanceRate(FeedbackRatesBase):
    """
    Report block that measures item-level and score-result-level acceptance rates.
    """

    DEFAULT_NAME = "Acceptance Rate"

    DEFAULT_DESCRIPTION = "Score result acceptance metrics"

    # 0 means "no cap" in CLI/config and is normalized to unlimited here.
    DEFAULT_MAX_ITEMS = 0

    def _coerce_bool(self, value: Any, *, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off"}:
            return False
        return default

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        try:
            include_item_acceptance_rate = self._coerce_bool(
                self._get_param("include_item_acceptance_rate"),
                default=False,
            )
            max_items_raw = self._get_param("max_items")
            max_items = (
                int(max_items_raw)
                if max_items_raw is not None and str(max_items_raw).strip() != ""
                else self.DEFAULT_MAX_ITEMS
            )
            if max_items < 0:
                raise ValueError("'max_items' must be >= 0.")
            dataset = await self._prepare_rate_dataset()
            items: List[Dict[str, Any]] = []
            accepted_items = 0
            corrected_items = 0

            for row in dataset["items"]:
                item_corrected = row["corrected_score_results"] > 0
                if item_corrected:
                    corrected_items += 1
                else:
                    accepted_items += 1

                item_total = row["total_score_results"]
                item_accepted_score_results = row["uncorrected_score_results"]
                item_score_result_acceptance_rate = (
                    item_accepted_score_results / item_total if item_total else 0.0
                )

                item_output: Dict[str, Any] = {
                    "item_id": row["item_id"],
                    "item_external_id": row.get("item_external_id"),
                    "item_created_at": row.get("item_created_at"),
                    "item_updated_at": row.get("item_updated_at"),
                    "item_identifiers": row.get("item_identifiers"),
                    "total_score_results": item_total,
                    "accepted_score_results": item_accepted_score_results,
                    "corrected_score_results": row["corrected_score_results"],
                    "feedback_items_total": row.get("feedback_items_total", 0),
                    "feedback_items_valid": row.get("feedback_items_valid", 0),
                    "feedback_scores_with_feedback_count": row.get("feedback_scores_with_feedback_count", 0),
                    "score_result_acceptance_rate": item_score_result_acceptance_rate,
                    "score_results": row["score_results"],
                }
                if include_item_acceptance_rate:
                    item_output["item_accepted"] = not item_corrected
                items.append(item_output)

            items_total = len(items)
            if max_items == 0:
                items_out = items
            else:
                items_out = items[:max_items]

            totals = dataset["totals"]
            total_items = totals["total_items"]
            total_score_results = totals["total_score_results"]
            accepted_score_results = totals["uncorrected_score_results"]
            summary: Dict[str, Any] = {
                "total_score_results": total_score_results,
                "accepted_score_results": accepted_score_results,
                "corrected_score_results": totals["corrected_score_results"],
                "score_result_acceptance_rate": (
                    accepted_score_results / total_score_results if total_score_results else 0.0
                ),
                "feedback_items_total": totals.get("feedback_items_total", 0),
                "feedback_items_valid": totals.get("feedback_items_valid", 0),
                "feedback_items_changed": totals.get("feedback_items_changed", 0),
                "score_results_with_feedback": totals.get("score_results_with_feedback", 0),
            }
            if include_item_acceptance_rate:
                summary.update(
                    {
                        "total_items": total_items,
                        "accepted_items": accepted_items,
                        "corrected_items": corrected_items,
                        "item_acceptance_rate": (accepted_items / total_items) if total_items else 0.0,
                    }
                )

            output = {
                "report_type": "acceptance_rate",
                "block_title": self.DEFAULT_NAME,
                "block_description": (
                    "Item-level and score-result-level acceptance metrics"
                    if include_item_acceptance_rate
                    else self.DEFAULT_DESCRIPTION
                ),
                "include_item_acceptance_rate": include_item_acceptance_rate,
                "scope": dataset["scope"],
                "scorecard_id": dataset["scorecard_id"],
                "scorecard_name": dataset["scorecard_name"],
                "score_id": dataset["score_id"],
                "score_name": dataset["score_name"],
                "distinct_score_ids": dataset["distinct_score_ids"],
                "date_range": dataset["date_range"],
                "summary": summary,
                "items": items_out,
                "max_items": max_items,
                "items_total": items_total,
                "items_returned": len(items_out),
                "items_truncated": len(items_out) < items_total,
                "raw_counts": dataset["raw_counts"],
            }
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating AcceptanceRate: {exc}", level="ERROR")
            return {"error": str(exc), "items": []}, self._get_log_string()
