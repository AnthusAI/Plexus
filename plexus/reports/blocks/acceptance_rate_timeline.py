from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .feedback_rates_base import FeedbackRatesBase


@dataclass(frozen=True)
class _TimeBucket:
    start_utc: datetime
    end_utc: datetime
    label: str


class AcceptanceRateTimeline(FeedbackRatesBase):
    """
    Report block that measures score-result acceptance rate over time (bucketed).

    This is the same core metric as AcceptanceRate (score_result_acceptance_rate), but
    computed per time bucket instead of as a single aggregate.
    """

    DEFAULT_NAME = "Acceptance Rate Timeline"
    DEFAULT_DESCRIPTION = "Score result acceptance rate over time"

    TRAILING_BUCKET_DAYS: Dict[str, int] = {
        "trailing_1d": 1,
        "trailing_7d": 7,
        "trailing_14d": 14,
        "trailing_30d": 30,
    }

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        try:
            scorecard_identifier = self._get_param("scorecard")
            if not scorecard_identifier:
                raise ValueError("'scorecard' is required.")

            score_identifier = self._get_param("score") or self._get_param("score_id")
            bucket_type = str(self._get_param("bucket_type") or "trailing_7d").strip().lower()
            bucket_count_raw = self._get_param("bucket_count")
            bucket_count = int(bucket_count_raw) if bucket_count_raw is not None else 12

            if bucket_type not in self.TRAILING_BUCKET_DAYS:
                supported = sorted(self.TRAILING_BUCKET_DAYS.keys())
                raise ValueError(f"Unsupported bucket_type '{bucket_type}'. Supported values: {supported}")
            if bucket_count <= 0:
                raise ValueError("'bucket_count' must be a positive integer.")

            account_id = self._resolve_account_id()
            window_start, window_end = self._resolve_window()
            scorecard = await self._resolve_scorecard(str(scorecard_identifier))

            resolved_score_id: Optional[str] = None
            resolved_score_name: Optional[str] = None
            if score_identifier:
                score = await self._resolve_score(str(score_identifier), scorecard.id)
                resolved_score_id = score.id
                resolved_score_name = score.name

            buckets = self._build_trailing_buckets(
                start_utc=window_start,
                end_utc=window_end,
                bucket_days=self.TRAILING_BUCKET_DAYS[bucket_type],
                bucket_count=bucket_count,
            )
            if not buckets:
                raise ValueError("No buckets were generated for the requested window.")

            range_start = buckets[0].start_utc
            range_end = buckets[-1].end_utc

            self._log(
                f"Fetching score results window for scorecard={scorecard.id} "
                f"score={resolved_score_id or 'all'} start={range_start.isoformat()} end={range_end.isoformat()}"
            )
            raw_score_results = await self._fetch_score_results_window(
                account_id=account_id,
                scorecard_id=scorecard.id,
                start_date=range_start,
                end_date=range_end,
                score_id=resolved_score_id,
            )
            self._log(f"Fetched {len(raw_score_results)} raw score results in window")

            # Determine distinct score IDs for scorecard-wide feedback fetch.
            # Use only production results so we don't fanout across irrelevant IDs.
            distinct_score_ids: List[str] = []
            if not resolved_score_id:
                distinct_score_ids = sorted(
                    {
                        str(result.get("scoreId")).strip()
                        for result in raw_score_results
                        if self._is_production_result(result) and str(result.get("scoreId") or "").strip()
                    }
                )

            self._log(
                f"Fetching feedback items window for scorecard={scorecard.id} "
                f"score={resolved_score_id or 'all'} start={range_start.isoformat()} end={range_end.isoformat()}"
            )
            raw_feedback_items = await self._fetch_feedback_items_window(
                account_id=account_id,
                scorecard_id=scorecard.id,
                start_date=range_start,
                end_date=range_end,
                score_id=resolved_score_id,
                score_ids=None if resolved_score_id else distinct_score_ids,
            )
            self._log(f"Fetched {len(raw_feedback_items)} raw feedback items in window")

            points: List[Dict[str, Any]] = []
            for bucket_index, bucket in enumerate(buckets):
                metrics = self._compute_bucket_metrics(
                    bucket=bucket,
                    bucket_index=bucket_index,
                    scorecard_id=scorecard.id,
                    resolved_score_id=resolved_score_id,
                    raw_score_results=raw_score_results,
                    raw_feedback_items=raw_feedback_items,
                )
                points.append(metrics)

            total_score_results = sum(point["total_score_results"] for point in points)
            accepted_score_results = sum(point["accepted_score_results"] for point in points)
            corrected_score_results = sum(point["corrected_score_results"] for point in points)
            feedback_items_total = sum(point["feedback_items_total"] for point in points)
            feedback_items_valid = sum(point["feedback_items_valid"] for point in points)
            feedback_items_changed = sum(point["feedback_items_changed"] for point in points)
            score_results_with_feedback = sum(point["score_results_with_feedback"] for point in points)

            output: Dict[str, Any] = {
                "report_type": "acceptance_rate_timeline",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scope": "single_score" if resolved_score_id else "scorecard_all_scores",
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "score_id": resolved_score_id,
                "score_name": resolved_score_name,
                "bucket_policy": {
                    "bucket_type": bucket_type,
                    "bucket_count": bucket_count,
                    "bucket_days": self.TRAILING_BUCKET_DAYS[bucket_type],
                    "timezone": "UTC",
                },
                "buckets": [
                    {
                        "bucket_index": idx,
                        "label": b.label,
                        "start": b.start_utc.isoformat(),
                        "end": b.end_utc.isoformat(),
                    }
                    for idx, b in enumerate(buckets)
                ],
                "points": points,
                "date_range": {
                    "start": range_start.isoformat(),
                    "end": range_end.isoformat(),
                },
                "summary": {
                    "total_score_results": total_score_results,
                    "accepted_score_results": accepted_score_results,
                    "corrected_score_results": corrected_score_results,
                    "score_result_acceptance_rate": (
                        accepted_score_results / total_score_results if total_score_results else 0.0
                    ),
                    "feedback_items_total": feedback_items_total,
                    "feedback_items_valid": feedback_items_valid,
                    "feedback_items_changed": feedback_items_changed,
                    "score_results_with_feedback": score_results_with_feedback,
                },
                "raw_counts": {
                    "raw_score_results_scanned": len(raw_score_results),
                    "raw_feedback_items_scanned": len(raw_feedback_items),
                },
            }
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating AcceptanceRateTimeline: {exc}", level="ERROR")
            return {"error": str(exc), "points": []}, self._get_log_string()

    def _build_trailing_buckets(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        bucket_days: int,
        bucket_count: int,
    ) -> List[_TimeBucket]:
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)
        if end_utc.tzinfo is None:
            end_utc = end_utc.replace(tzinfo=timezone.utc)

        # Clamp bucket_count to what can fit in the requested window.
        max_possible = max(1, int(((end_utc - start_utc).total_seconds() // (bucket_days * 86400)) + 1))
        bucket_count = min(bucket_count, max_possible)

        buckets: List[_TimeBucket] = []
        current_start = start_utc
        for _ in range(bucket_count):
            if current_start >= end_utc:
                break
            current_end = min(current_start + timedelta(days=bucket_days), end_utc)
            label = current_start.date().isoformat()
            buckets.append(_TimeBucket(start_utc=current_start, end_utc=current_end, label=label))
            current_start = current_end
        return buckets

    def _in_bucket(self, ts: datetime, bucket: _TimeBucket) -> bool:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return bucket.start_utc <= ts < bucket.end_utc

    def _compute_bucket_metrics(
        self,
        *,
        bucket: _TimeBucket,
        bucket_index: int,
        scorecard_id: str,
        resolved_score_id: Optional[str],
        raw_score_results: List[Dict[str, Any]],
        raw_feedback_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        # Latest production score result per (itemId, scoreId) within the bucket.
        latest_results_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for result in raw_score_results:
            if not self._is_production_result(result):
                continue
            if str(result.get("scorecardId") or "") != str(scorecard_id):
                continue

            item_id = str(result.get("itemId") or "").strip()
            score_id = str(result.get("scoreId") or "").strip()
            if not item_id or not score_id:
                continue
            if resolved_score_id and score_id != resolved_score_id:
                continue

            ts = self._to_dt(result.get("updatedAt") or result.get("createdAt"))
            if not self._in_bucket(ts, bucket):
                continue

            key = (item_id, score_id)
            existing = latest_results_by_key.get(key)
            if existing is None or ts >= existing["_timestamp"]:
                latest_results_by_key[key] = {**result, "_timestamp": ts}

        filtered_results = list(latest_results_by_key.values())

        # Latest valid feedback item per (itemId, scoreId) within the bucket + group stats.
        grouped_feedback: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for item in raw_feedback_items:
            if str(item.get("scorecardId") or "") != str(scorecard_id):
                continue
            item_id = str(item.get("itemId") or "").strip()
            score_id = str(item.get("scoreId") or "").strip()
            if not item_id or not score_id:
                continue
            if resolved_score_id and score_id != resolved_score_id:
                continue

            edited_ts = self._to_dt(item.get("editedAt") or item.get("updatedAt") or item.get("createdAt"))
            if not self._in_bucket(edited_ts, bucket):
                continue

            grouped_feedback.setdefault((item_id, score_id), []).append(item)

        feedback_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
        feedback_stats_by_key: Dict[Tuple[str, str], Dict[str, int]] = {}
        for key, group in grouped_feedback.items():
            valid_group = [entry for entry in group if not entry.get("isInvalid")]
            changed_valid_group = [
                entry
                for entry in valid_group
                if entry.get("finalAnswerValue") is not None
                and str(entry.get("finalAnswerValue")) != str(entry.get("initialAnswerValue"))
            ]
            feedback_stats_by_key[key] = {
                "total": len(group),
                "valid": len(valid_group),
                "changed": len(changed_valid_group),
            }
            if not valid_group:
                continue
            feedback_by_key[key] = max(
                valid_group,
                key=lambda entry: self._to_dt(entry.get("editedAt") or entry.get("updatedAt") or entry.get("createdAt")),
            )

        corrected_score_results = 0
        accepted_score_results = 0
        score_results_with_feedback = 0

        for result in filtered_results:
            key = (str(result.get("itemId")), str(result.get("scoreId")))
            feedback = feedback_by_key.get(key)
            feedback_stats = feedback_stats_by_key.get(key) or {"total": 0, "valid": 0}
            if int(feedback_stats.get("total") or 0) > 0:
                score_results_with_feedback += 1

            predicted_value = str(result.get("value"))
            final_value = feedback.get("finalAnswerValue") if feedback else None
            corrected = final_value is not None and str(final_value) != predicted_value
            if corrected:
                corrected_score_results += 1
            else:
                accepted_score_results += 1

            total_score_results = len(filtered_results)
            score_result_acceptance_rate = (accepted_score_results / total_score_results) if total_score_results else 0.0

            feedback_items_total = sum(stats["total"] for stats in feedback_stats_by_key.values()) if feedback_stats_by_key else 0
            feedback_items_valid = sum(stats["valid"] for stats in feedback_stats_by_key.values()) if feedback_stats_by_key else 0
            feedback_items_changed = (
                sum(stats["changed"] for stats in feedback_stats_by_key.values()) if feedback_stats_by_key else 0
            )

        return {
            "bucket_index": bucket_index,
            "label": bucket.label,
            "start": bucket.start_utc.isoformat(),
            "end": bucket.end_utc.isoformat(),
            "total_score_results": total_score_results,
            "accepted_score_results": accepted_score_results,
            "corrected_score_results": corrected_score_results,
            "score_result_acceptance_rate": score_result_acceptance_rate,
            "feedback_items_total": feedback_items_total,
            "feedback_items_valid": feedback_items_valid,
            "feedback_items_changed": feedback_items_changed,
            "score_results_with_feedback": score_results_with_feedback,
        }
