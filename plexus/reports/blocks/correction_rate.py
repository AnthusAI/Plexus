from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .feedback_rates_base import FeedbackRatesBase


class CorrectionRate(FeedbackRatesBase):
    """
    Report block that measures score-result correction behavior from feedback edits.
    """

    DEFAULT_NAME = "Correction Rate"
    DEFAULT_DESCRIPTION = "Per-item and corpus-level correction rates from feedback edits"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        try:
            dataset = await self._prepare_rate_dataset()
            output = {
                "report_type": "correction_rate",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scope": dataset["scope"],
                "scorecard_id": dataset["scorecard_id"],
                "scorecard_name": dataset["scorecard_name"],
                "score_id": dataset["score_id"],
                "score_name": dataset["score_name"],
                "distinct_score_ids": dataset["distinct_score_ids"],
                "date_range": dataset["date_range"],
                "summary": dataset["totals"],
                "items": dataset["items"],
                "raw_counts": dataset["raw_counts"],
            }
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating CorrectionRate: {exc}", level="ERROR")
            return {"error": str(exc), "items": []}, self._get_log_string()
