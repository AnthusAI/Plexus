"""
ActionItems ReportBlock

Post-processes a sibling FeedbackAlignment block's output and emits a prioritised,
structured list of action items for downstream classifier improvement work.

The block output (the "Code" view in the dashboard) is a JSON dict with an
`action_items` array — ready for programmatic consumption.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from plexus.reports.blocks.base import BaseReportBlock
from plexus.reports.action_items_utils import (
    collect_action_items,
    fetch_block_output,
)

logger = logging.getLogger(__name__)


class ActionItems(BaseReportBlock):
    """Generate a prioritised action-item list from a sibling FeedbackAlignment block."""

    DEFAULT_NAME = "Action Items"
    DEFAULT_DESCRIPTION = "Prioritised list of classifier improvement tasks from feedback root-cause analysis."

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        logs = []

        def _log(msg: str):
            logs.append(msg)
            logger.info(msg)

        ac1_threshold = float(self.config.get("ac1_threshold", 0.8))
        recency_days = int(self.config.get("recency_days", 30))
        source_block_name = self.config.get("source_block_name") or None

        _log(f"ActionItems: ac1_threshold={ac1_threshold}, recency_days={recency_days}")

        # ── Find the sibling FeedbackAlignment block ─────────────────────────
        fa_block = await asyncio.to_thread(
            self._find_feedback_alignment_block, source_block_name
        )
        if fa_block is None:
            msg = "No FeedbackAlignment block found in this report."
            _log(f"ERROR: {msg}")
            return {"error": msg, "action_items": [], "total_count": 0}, "\n".join(logs)

        _log(f"ActionItems: reading output from block '{fa_block.name}' ({fa_block.id})")

        # ── Fetch its output ─────────────────────────────────────────────────
        output = await asyncio.to_thread(fetch_block_output, fa_block)
        if not output:
            msg = "Could not read FeedbackAlignment block output."
            _log(f"ERROR: {msg}")
            return {"error": msg, "action_items": [], "total_count": 0}, "\n".join(logs)

        # ── Derive a human-readable scorecard name from report params ────────
        report_params = self.params or {}
        scorecard_name_hint = (
            report_params.get("param_scorecard_name")
            or report_params.get("scorecard_name")
            or fa_block.name
        )

        # ── Collect and filter action items ──────────────────────────────────
        _log("ActionItems: collecting action items…")
        items = await asyncio.to_thread(
            collect_action_items,
            output,
            ac1_threshold,
            recency_days,
            scorecard_name_hint,
        )
        _log(f"ActionItems: found {len(items)} action item(s).")

        date_range = output.get("date_range", {})
        result = {
            "action_items": items,
            "total_count": len(items),
            "date_range": date_range,
            "thresholds": {
                "ac1": ac1_threshold,
                "recency_days": recency_days,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return result, "\n".join(logs)

    def _find_feedback_alignment_block(self, source_block_name: Optional[str]):
        """Return the sibling FeedbackAlignment ReportBlock, or None."""
        from plexus.dashboard.api.models.report_block import ReportBlock

        if not self.report_block_id:
            logger.warning("ActionItems: report_block_id not set; cannot find sibling blocks.")
            return None

        # Look up our own record to get the parent reportId
        my_record = ReportBlock.get_by_id(self.report_block_id, self.api_client)
        if not my_record or not my_record.reportId:
            logger.warning(f"ActionItems: could not fetch own block record ({self.report_block_id}).")
            return None

        siblings = ReportBlock.list_by_report_id(my_record.reportId, self.api_client)

        if source_block_name:
            return next(
                (b for b in siblings if b.name == source_block_name and b.id != self.report_block_id),
                None,
            )

        # Default: first block whose type is FeedbackAlignment
        return next(
            (b for b in siblings
             if (b.type or "").lower() in ("feedbackalignment", "feedback_alignment")
             and b.id != self.report_block_id),
            None,
        )
