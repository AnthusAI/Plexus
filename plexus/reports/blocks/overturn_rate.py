from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .feedback_rates_base import FeedbackRatesBase


class OverturnRate(FeedbackRatesBase):
    """
    Report block that measures score-result overturn behavior from feedback edits.
    """

    DEFAULT_NAME = "Overturn Rate"
    DEFAULT_DESCRIPTION = "Per-item and corpus-level overturn rates from feedback edits"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        try:
            dataset = await self._prepare_rate_dataset()
            output = {
                "report_type": "overturn_rate",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scorecard_id": dataset["scorecard_id"],
                "scorecard_name": dataset["scorecard_name"],
                "score_id": dataset["score_id"],
                "score_name": dataset["score_name"],
                "date_range": dataset["date_range"],
                "summary": dataset["totals"],
                "items": dataset["items"],
                "raw_counts": dataset["raw_counts"],
            }
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating OverturnRate: {exc}", level="ERROR")
            return {"error": str(exc), "items": []}, self._get_log_string()
