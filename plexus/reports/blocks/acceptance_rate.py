from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .feedback_rates_base import FeedbackRatesBase


class AcceptanceRate(FeedbackRatesBase):
    """
    Report block that measures item-level and score-result-level acceptance rates.
    """

    DEFAULT_NAME = "Acceptance Rate"
    DEFAULT_DESCRIPTION = "Item-level and score-result-level acceptance metrics"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        try:
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

                items.append(
                    {
                        "item_id": row["item_id"],
                        "item_accepted": not item_corrected,
                        "total_score_results": item_total,
                        "accepted_score_results": item_accepted_score_results,
                        "corrected_score_results": row["corrected_score_results"],
                        "score_result_acceptance_rate": item_score_result_acceptance_rate,
                        "score_results": row["score_results"],
                    }
                )

            totals = dataset["totals"]
            total_items = totals["total_items"]
            total_score_results = totals["total_score_results"]
            accepted_score_results = totals["uncorrected_score_results"]
            summary = {
                "total_items": total_items,
                "accepted_items": accepted_items,
                "corrected_items": corrected_items,
                "item_acceptance_rate": (accepted_items / total_items) if total_items else 0.0,
                "total_score_results": total_score_results,
                "accepted_score_results": accepted_score_results,
                "corrected_score_results": totals["corrected_score_results"],
                "score_result_acceptance_rate": (
                    accepted_score_results / total_score_results if total_score_results else 0.0
                ),
            }

            output = {
                "report_type": "acceptance_rate",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scope": dataset["scope"],
                "scorecard_id": dataset["scorecard_id"],
                "scorecard_name": dataset["scorecard_name"],
                "score_id": dataset["score_id"],
                "score_name": dataset["score_name"],
                "distinct_score_ids": dataset["distinct_score_ids"],
                "date_range": dataset["date_range"],
                "summary": summary,
                "items": items,
                "raw_counts": dataset["raw_counts"],
            }
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating AcceptanceRate: {exc}", level="ERROR")
            return {"error": str(exc), "items": []}, self._get_log_string()
