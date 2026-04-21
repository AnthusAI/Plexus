from __future__ import annotations

from datetime import timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from plexus.dashboard.api.models.feedback_item import FeedbackItem

from .feedback_alignment_timeline import FeedbackAlignmentTimeline


class FeedbackVolumeTimeline(FeedbackAlignmentTimeline):
    """
    Report block for visualizing feedback-item volume over time.

    Supports:
    - scorecard only: all scores on the scorecard
    - scorecard + score/score_id: single-score mode

    Bucket policy matches FeedbackAlignmentTimeline so volume charts can share
    the same time-window controls and report-level parameters.
    """

    DEFAULT_NAME = "Feedback Volume Timeline"
    DEFAULT_DESCRIPTION = "Feedback item volume over time"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []

        try:
            scorecard_identifier = self._get_param("scorecard")
            if not scorecard_identifier:
                raise ValueError("'scorecard' is required in block configuration.")

            score_identifier = self._get_param("score_id") or self._get_param("score")
            if score_identifier is not None:
                score_identifier = str(score_identifier).strip() or None

            bucket_type = str(self._get_param("bucket_type") or "trailing_7d").strip().lower()
            requested_bucket_count = self._get_param("bucket_count")
            bucket_count = int(requested_bucket_count) if requested_bucket_count is not None else 12
            timezone_name = str(self._get_param("timezone") or "UTC").strip()
            week_start = str(self._get_param("week_start") or "monday").strip().lower()
            show_bucket_details = self._parse_bool(self._get_param("show_bucket_details"), default=False)

            if bucket_type not in self.TRAILING_BUCKET_DAYS and bucket_type not in self.CALENDAR_BUCKET_TYPES:
                supported = sorted(list(self.TRAILING_BUCKET_DAYS.keys()) + list(self.CALENDAR_BUCKET_TYPES))
                raise ValueError(
                    f"Unsupported bucket_type '{bucket_type}'. Supported values: {supported}"
                )
            if week_start not in self.WEEK_START_INDEX:
                raise ValueError("'week_start' must be either 'monday' or 'sunday'.")

            try:
                tzinfo = ZoneInfo(timezone_name)
            except Exception as exc:
                raise ValueError(f"Invalid timezone '{timezone_name}': {exc}") from exc

            has_explicit_window = self._has_explicit_window()
            if has_explicit_window:
                window_start_utc, window_end_utc = self._resolve_window_utc()
                window_start_local = window_start_utc.astimezone(tzinfo)
                window_end_local = window_end_utc.astimezone(tzinfo)
                if window_end_local <= window_start_local:
                    raise ValueError("Resolved time window must have end > start.")

                buckets = self._build_exact_window_buckets(
                    start_local=window_start_local,
                    end_local=window_end_local,
                    bucket_type=bucket_type,
                    week_start=week_start,
                )
                window_mode = "exact_window"
                complete_only = False
                if requested_bucket_count is not None:
                    self._log(
                        "Ignoring 'bucket_count' because an explicit window was provided (days/start_date/end_date).",
                        level="INFO",
                    )
                range_start_utc = window_start_utc
                range_end_query_utc = window_end_utc
                date_range_end_utc = window_end_utc
            else:
                if bucket_count <= 0:
                    raise ValueError("'bucket_count' must be a positive integer.")
                now_local = self._now_utc().astimezone(tzinfo)
                buckets = self._build_buckets(
                    now_local=now_local,
                    bucket_type=bucket_type,
                    bucket_count=bucket_count,
                    week_start=week_start,
                )
                window_mode = "historical_complete"
                complete_only = True
                range_start_utc = buckets[0].start_local.astimezone(timezone.utc)
                range_end_query_utc = (
                    buckets[-1].end_local.astimezone(timezone.utc) - timedelta(microseconds=1)
                )
                date_range_end_utc = buckets[-1].end_local.astimezone(timezone.utc)

            if not buckets:
                raise ValueError("No time buckets were generated.")

            scorecard = await self._resolve_scorecard(str(scorecard_identifier))
            scores_to_analyze = await self._resolve_scores_for_mode(
                scorecard_id=scorecard.id,
                score_identifier=score_identifier,
            )

            scope = "single_score" if score_identifier else "scorecard_all_scores"
            bucket_policy = {
                "bucket_type": bucket_type,
                "bucket_count": len(buckets),
                "requested_bucket_count": bucket_count,
                "bucket_count_ignored": bool(has_explicit_window and requested_bucket_count is not None),
                "timezone": timezone_name,
                "week_start": week_start,
                "complete_only": complete_only,
                "window_mode": window_mode,
            }

            points = [
                self._empty_point(bucket=bucket, bucket_index=index)
                for index, bucket in enumerate(buckets)
            ]

            if not scores_to_analyze:
                return {
                    "report_type": "feedback_volume_timeline",
                    "block_title": self.DEFAULT_NAME,
                    "block_description": self.DEFAULT_DESCRIPTION,
                    "scope": scope,
                    "scorecard_id": scorecard.id,
                    "scorecard_name": scorecard.name,
                    "score_id": None,
                    "score_name": None,
                    "show_bucket_details": show_bucket_details,
                    "bucket_policy": bucket_policy,
                    "buckets": self._serialize_buckets(buckets),
                    "points": points,
                    "summary": self._summarize_points(points),
                    "date_range": {
                        "start": range_start_utc.isoformat(),
                        "end": date_range_end_utc.isoformat(),
                    },
                    "message": "No scores found for the requested scope.",
                }, self._get_log_string()

            resolved_score_id = scores_to_analyze[0]["score_id"] if scope == "single_score" else None
            resolved_score_name = scores_to_analyze[0]["score_name"] if scope == "single_score" else None

            self._log(
                f"Running FeedbackVolumeTimeline for scorecard '{scorecard.name}' "
                f"with {len(scores_to_analyze)} score(s), bucket_type={bucket_type}, "
                f"bucket_count={len(buckets)}, window_mode={window_mode}"
            )

            total_feedback_items_retrieved = 0
            for score_info in scores_to_analyze:
                feedback_items = await self._fetch_feedback_items_for_score(
                    scorecard_id=scorecard.id,
                    score_id=score_info["score_id"],
                    start_date=range_start_utc,
                    end_date=range_end_query_utc,
                )
                total_feedback_items_retrieved += len(feedback_items)

                for feedback_item in feedback_items:
                    edited_at = (
                        getattr(feedback_item, "editedAt", None)
                        or getattr(feedback_item, "updatedAt", None)
                        or getattr(feedback_item, "createdAt", None)
                    )
                    if not edited_at:
                        continue
                    if edited_at.tzinfo is None:
                        edited_at = edited_at.replace(tzinfo=timezone.utc)
                    edited_local = edited_at.astimezone(tzinfo)
                    bucket_index = self._find_bucket_index(edited_local, buckets)
                    if bucket_index is None:
                        continue

                    self._accumulate_feedback_item(points[bucket_index], feedback_item)

            output: Dict[str, Any] = {
                "report_type": "feedback_volume_timeline",
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scope": scope,
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "score_id": resolved_score_id,
                "score_name": resolved_score_name,
                "show_bucket_details": show_bucket_details,
                "bucket_policy": bucket_policy,
                "buckets": self._serialize_buckets(buckets),
                "points": points,
                "summary": self._summarize_points(points),
                "date_range": {
                    "start": range_start_utc.isoformat(),
                    "end": date_range_end_utc.isoformat(),
                },
                "total_feedback_items_retrieved": total_feedback_items_retrieved,
                "message": (
                    f"Processed {len(scores_to_analyze)} score(s) across "
                    f"{len(buckets)} bucket(s) in {window_mode} mode."
                ),
            }
            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating FeedbackVolumeTimeline: {exc}", level="ERROR")
            return {"error": str(exc), "points": []}, self._get_log_string()

    def _empty_point(self, *, bucket: Any, bucket_index: int) -> Dict[str, Any]:
        return {
            "bucket_index": bucket_index,
            "label": bucket.label,
            "start": bucket.start_local.astimezone(timezone.utc).isoformat(),
            "end": bucket.end_local.astimezone(timezone.utc).isoformat(),
            "feedback_items_total": 0,
            "feedback_items_valid": 0,
            "feedback_items_unchanged": 0,
            "feedback_items_changed": 0,
            "feedback_items_invalid_or_unclassified": 0,
        }

    def _accumulate_feedback_item(self, point: Dict[str, Any], feedback_item: FeedbackItem) -> None:
        point["feedback_items_total"] += 1

        raw_invalid = getattr(feedback_item, "isInvalid", False)
        if isinstance(raw_invalid, bool):
            is_invalid = raw_invalid
        elif isinstance(raw_invalid, (int, str)):
            is_invalid = self._parse_bool(raw_invalid, default=False)
        else:
            is_invalid = False

        initial_value = getattr(feedback_item, "initialAnswerValue", None)
        final_value = getattr(feedback_item, "finalAnswerValue", None)
        if is_invalid or initial_value is None or final_value is None:
            point["feedback_items_invalid_or_unclassified"] += 1
            return

        point["feedback_items_valid"] += 1
        if str(final_value) != str(initial_value):
            point["feedback_items_changed"] += 1
        else:
            point["feedback_items_unchanged"] += 1

    def _summarize_points(self, points: List[Dict[str, Any]]) -> Dict[str, int]:
        return {
            "feedback_items_total": sum(point["feedback_items_total"] for point in points),
            "feedback_items_valid": sum(point["feedback_items_valid"] for point in points),
            "feedback_items_unchanged": sum(point["feedback_items_unchanged"] for point in points),
            "feedback_items_changed": sum(point["feedback_items_changed"] for point in points),
            "feedback_items_invalid_or_unclassified": sum(
                point["feedback_items_invalid_or_unclassified"] for point in points
            ),
        }
