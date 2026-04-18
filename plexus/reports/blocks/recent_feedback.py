from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import feedback_utils
from .feedback_rates_base import FeedbackRatesBase


class RecentFeedback(FeedbackRatesBase):
    """
    Report block that lists recently collected feedback rows for a scorecard/score.
    """

    DEFAULT_NAME = "Recent Feedback"
    DEFAULT_DESCRIPTION = "Recent feedback activity in the selected window"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        try:
            scorecard_identifier = self._get_param("scorecard")
            if not scorecard_identifier:
                raise ValueError("'scorecard' is required.")

            score_identifier = self._get_param("score") or self._get_param("score_id")
            max_items_raw = self._get_param("max_feedback_items")
            max_items = int(max_items_raw) if max_items_raw is not None else 500
            if max_items <= 0:
                raise ValueError("'max_feedback_items' must be a positive integer.")

            account_id = self._resolve_account_id()
            start_date, end_date = self._resolve_window()
            scorecard = await self._resolve_scorecard(str(scorecard_identifier))

            resolved_score_id: Optional[str] = None
            resolved_score_name: Optional[str] = None
            score_name_by_id: Dict[str, str] = {}
            score_ids_for_fetch: List[str] = []

            if score_identifier:
                score = await self._resolve_score(str(score_identifier), scorecard.id)
                resolved_score_id = score.id
                resolved_score_name = score.name
                score_ids_for_fetch = [score.id]
                score_name_by_id[score.id] = score.name
            else:
                score_info_rows = await feedback_utils.fetch_scores_for_scorecard(
                    self.api_client, scorecard.id
                )
                for score_info in score_info_rows:
                    sid = str(score_info.get("plexus_score_id") or "").strip()
                    if not sid:
                        continue
                    score_ids_for_fetch.append(sid)
                    score_name_by_id[sid] = str(score_info.get("plexus_score_name") or sid)

            self._log(
                f"Fetching recent feedback for scorecard={scorecard.id} "
                f"score={resolved_score_id or 'all'} start={start_date.isoformat()} end={end_date.isoformat()}"
            )
            feedback_items = await self._fetch_feedback_items_window(
                account_id=account_id,
                scorecard_id=scorecard.id,
                start_date=start_date,
                end_date=end_date,
                score_id=resolved_score_id,
                score_ids=None if resolved_score_id else score_ids_for_fetch,
            )

            # Sort newest-first and apply result cap.
            feedback_items.sort(
                key=lambda row: self._to_dt(
                    row.get("editedAt") or row.get("updatedAt") or row.get("createdAt")
                ),
                reverse=True,
            )
            feedback_items = feedback_items[:max_items]

            rows: List[Dict[str, Any]] = []
            invalid_count = 0
            overturned_count = 0
            distinct_item_ids: set[str] = set()
            distinct_score_ids: set[str] = set()

            for item in feedback_items:
                item_id = str(item.get("itemId") or "")
                score_id = str(item.get("scoreId") or "")
                initial_value = item.get("initialAnswerValue")
                final_value = item.get("finalAnswerValue")
                is_invalid = bool(item.get("isInvalid"))
                overturned = (
                    final_value is not None
                    and initial_value is not None
                    and str(final_value) != str(initial_value)
                )

                if item_id:
                    distinct_item_ids.add(item_id)
                if score_id:
                    distinct_score_ids.add(score_id)
                if is_invalid:
                    invalid_count += 1
                if overturned:
                    overturned_count += 1

                rows.append(
                    {
                        "feedback_item_id": item.get("id"),
                        "item_id": item_id,
                        "score_id": score_id,
                        "score_name": score_name_by_id.get(score_id),
                        "initial_value": initial_value,
                        "final_value": final_value,
                        "overturned": overturned,
                        "is_invalid": is_invalid,
                        "edited_at": item.get("editedAt"),
                        "edit_comment": item.get("editCommentValue")
                        or item.get("finalCommentValue"),
                    }
                )

            total_feedback_items = len(rows)
            upheld_count = total_feedback_items - overturned_count
            output = {
                "report_type": "recent_feedback",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scope": "single_score" if resolved_score_id else "scorecard_all_scores",
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "score_id": resolved_score_id,
                "score_name": resolved_score_name,
                "distinct_score_ids": sorted(distinct_score_ids),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "summary": {
                    "total_feedback_items": total_feedback_items,
                    "overturned_feedback_items": overturned_count,
                    "upheld_feedback_items": upheld_count,
                    "invalid_feedback_items": invalid_count,
                    "distinct_items_count": len(distinct_item_ids),
                    "distinct_score_count": len(distinct_score_ids),
                },
                "items": rows,
                "raw_counts": {
                    "raw_feedback_items_scanned": len(feedback_items),
                },
            }
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating RecentFeedback: {exc}", level="ERROR")
            return {"error": str(exc), "items": []}, self._get_log_string()
