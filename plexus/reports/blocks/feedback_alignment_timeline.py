from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard

from . import feedback_utils
from .base import BaseReportBlock
from .identifier_utils import looks_like_uuid


@dataclass(frozen=True)
class _TimeBucket:
    start_local: datetime
    end_local: datetime
    label: str


class FeedbackAlignmentTimeline(BaseReportBlock):
    """
    Report block for visualizing feedback alignment change over time.

    Supports:
    - scorecard only: all scores on the scorecard
    - scorecard + score/score_id: single-score mode

    Bucket policy supports:
    - complete historical buckets (default when no explicit window is provided)
    - exact-window buckets (when days or start_date/end_date is provided)
    """

    DEFAULT_NAME = "Feedback Alignment Timeline"
    DEFAULT_DESCRIPTION = "Alignment metrics over time"
    DEFAULT_DAYS = 30

    TRAILING_BUCKET_DAYS: Dict[str, int] = {
        "trailing_1d": 1,
        "trailing_7d": 7,
        "trailing_14d": 14,
        "trailing_30d": 30,
    }
    CALENDAR_BUCKET_TYPES = {"calendar_day", "calendar_week", "calendar_biweek", "calendar_month"}
    WEEK_START_INDEX = {"monday": 0, "sunday": 6}

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
                # Feedback item query uses inclusive bounds.
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
                # Query end is inclusive; subtract 1 microsecond to remain in the last bucket.
                range_end_query_utc = (
                    buckets[-1].end_local.astimezone(timezone.utc) - timedelta(microseconds=1)
                )
                date_range_end_utc = buckets[-1].end_local.astimezone(timezone.utc)

            if not buckets:
                raise ValueError("No time buckets were generated.")

            effective_bucket_count = len(buckets)
            scorecard = await self._resolve_scorecard(str(scorecard_identifier))
            scores_to_analyze = await self._resolve_scores_for_mode(
                scorecard_id=scorecard.id,
                score_identifier=score_identifier,
            )

            bucket_policy = {
                "bucket_type": bucket_type,
                "bucket_count": effective_bucket_count,
                "requested_bucket_count": bucket_count,
                "bucket_count_ignored": bool(has_explicit_window and requested_bucket_count is not None),
                "timezone": timezone_name,
                "week_start": week_start,
                "complete_only": complete_only,
                "window_mode": window_mode,
            }

            if not scores_to_analyze:
                return {
                    "mode": "single_score" if score_identifier else "all_scores",
                    "block_title": self.DEFAULT_NAME,
                    "block_description": self.DEFAULT_DESCRIPTION,
                    "scorecard_id": scorecard.id,
                    "scorecard_name": scorecard.name,
                    "show_bucket_details": show_bucket_details,
                    "bucket_policy": bucket_policy,
                    "buckets": self._serialize_buckets(buckets),
                    "overall": {"score_id": "overall", "score_name": "Overall", "points": []},
                    "scores": [],
                    "message": "No scores found for the requested scope.",
                    "date_range": {
                        "start": range_start_utc.isoformat(),
                        "end": date_range_end_utc.isoformat(),
                    },
                }, self._get_log_string()

            self._log(
                f"Running FeedbackAlignmentTimeline for scorecard '{scorecard.name}' "
                f"with {len(scores_to_analyze)} score(s), bucket_type={bucket_type}, "
                f"bucket_count={effective_bucket_count}, window_mode={window_mode}"
            )

            overall_bucket_items: List[List[FeedbackItem]] = [[] for _ in buckets]
            score_series: List[Dict[str, Any]] = []
            total_feedback_items_retrieved = 0

            for score_info in scores_to_analyze:
                score_id = score_info["score_id"]
                score_name = score_info["score_name"]
                feedback_items = await self._fetch_feedback_items_for_score(
                    scorecard_id=scorecard.id,
                    score_id=score_id,
                    start_date=range_start_utc,
                    end_date=range_end_query_utc,
                )
                total_feedback_items_retrieved += len(feedback_items)

                per_bucket_items: List[List[FeedbackItem]] = [[] for _ in buckets]
                for feedback_item in feedback_items:
                    edited_at = feedback_item.editedAt
                    if not edited_at:
                        continue
                    if edited_at.tzinfo is None:
                        edited_at = edited_at.replace(tzinfo=timezone.utc)
                    edited_local = edited_at.astimezone(tzinfo)

                    bucket_index = self._find_bucket_index(edited_local, buckets)
                    if bucket_index is None:
                        continue

                    per_bucket_items[bucket_index].append(feedback_item)
                    overall_bucket_items[bucket_index].append(feedback_item)

                points = [
                    self._build_point(bucket, index, self._calculate_alignment_metrics(items))
                    for index, (bucket, items) in enumerate(zip(buckets, per_bucket_items))
                ]
                score_series.append(
                    {
                        "score_id": score_id,
                        "score_name": score_name,
                        "points": points,
                    }
                )

            overall_points = [
                self._build_point(bucket, index, self._calculate_alignment_metrics(items))
                for index, (bucket, items) in enumerate(zip(buckets, overall_bucket_items))
            ]

            mode = "single_score" if score_identifier else "all_scores"
            output: Dict[str, Any] = {
                "mode": mode,
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "show_bucket_details": show_bucket_details,
                "bucket_policy": bucket_policy,
                "buckets": self._serialize_buckets(buckets),
                "overall": {
                    "score_id": "overall",
                    "score_name": "Overall",
                    "points": overall_points,
                },
                "scores": score_series,
                "date_range": {
                    "start": range_start_utc.isoformat(),
                    "end": date_range_end_utc.isoformat(),
                },
                "total_feedback_items_retrieved": total_feedback_items_retrieved,
                "message": (
                    f"Processed {len(score_series)} score(s) across "
                    f"{len(buckets)} bucket(s) in {window_mode} mode."
                ),
            }

            # In single-score mode, "overall" and selected score represent the same series.
            if mode == "single_score" and score_series:
                output["overall"] = {
                    "score_id": score_series[0]["score_id"],
                    "score_name": score_series[0]["score_name"],
                    "points": score_series[0]["points"],
                }

            return output, self._get_log_string()
        except Exception as exc:
            self._log(f"ERROR generating FeedbackAlignmentTimeline: {exc}", level="ERROR")
            return {"error": str(exc), "scores": []}, self._get_log_string()

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_param(self, name: str) -> Any:
        if name in self.config and self.config.get(name) is not None:
            return self.config.get(name)
        if name in self.params and self.params.get(name) is not None:
            return self.params.get(name)
        param_name = f"param_{name}"
        if param_name in self.params and self.params.get(param_name) is not None:
            return self.params.get(param_name)
        return None

    def _parse_bool(self, value: Any, *, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        value_str = str(value).strip().lower()
        if value_str in {"1", "true", "yes", "y", "on"}:
            return True
        if value_str in {"0", "false", "no", "n", "off"}:
            return False
        return default

    def _has_explicit_window(self) -> bool:
        return any(
            self._get_param(name) is not None
            for name in ("days", "start_date", "end_date")
        )

    def _parse_dt(self, value: Any, *, is_end: bool) -> datetime:
        value_str = str(value).strip()
        date_only = (
            len(value_str) == 10
            and value_str[4] == "-"
            and value_str[7] == "-"
        )
        try:
            dt = datetime.fromisoformat(value_str)
            if date_only:
                if is_end:
                    dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                else:
                    dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        except Exception:
            dt = datetime.strptime(value_str, "%Y-%m-%d")
            if is_end:
                dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            else:
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _resolve_window_utc(self) -> Tuple[datetime, datetime]:
        start_date_raw = self._get_param("start_date")
        end_date_raw = self._get_param("end_date")
        days_raw = self._get_param("days")

        if (start_date_raw and not end_date_raw) or (end_date_raw and not start_date_raw):
            raise ValueError("Both 'start_date' and 'end_date' are required when specifying explicit date windows.")
        if days_raw is not None and start_date_raw and end_date_raw:
            raise ValueError("Use either 'days' or 'start_date'+'end_date', not both.")

        if start_date_raw and end_date_raw:
            start_date = self._parse_dt(start_date_raw, is_end=False)
            end_date = self._parse_dt(end_date_raw, is_end=True)
        else:
            days = int(days_raw) if days_raw is not None else self.DEFAULT_DAYS
            if days <= 0:
                raise ValueError("'days' must be a positive integer.")
            end_date = self._now_utc()
            start_date = end_date - timedelta(days=days)

        if end_date <= start_date:
            raise ValueError("'end_date' must be after 'start_date'.")
        return start_date, end_date

    async def _resolve_scorecard(self, scorecard_identifier: str) -> Scorecard:
        scorecard = None
        if looks_like_uuid(scorecard_identifier):
            try:
                scorecard = await self._to_thread(
                    Scorecard.get_by_id,
                    id=scorecard_identifier,
                    client=self.api_client,
                )
            except Exception:
                scorecard = None
        if not scorecard:
            for lookup, kwargs in [
                (Scorecard.get_by_key, {"key": scorecard_identifier}),
                (Scorecard.get_by_name, {"name": scorecard_identifier}),
                (Scorecard.get_by_external_id, {"external_id": scorecard_identifier}),
            ]:
                try:
                    scorecard = await self._to_thread(lookup, client=self.api_client, **kwargs)
                    if scorecard:
                        break
                except Exception:
                    continue
        if not scorecard:
            raise ValueError(f"Scorecard not found for identifier '{scorecard_identifier}'.")
        return scorecard

    async def _resolve_scores_for_mode(
        self,
        scorecard_id: str,
        score_identifier: Optional[str],
    ) -> List[Dict[str, str]]:
        if score_identifier:
            is_uuid_like = looks_like_uuid(score_identifier)
            if is_uuid_like:
                score = await self._to_thread(
                    Score.get_by_id,
                    id=score_identifier,
                    client=self.api_client,
                )
                if score:
                    resolved_scorecard_id = await self._fetch_scorecard_id_for_section_id(score.sectionId)
                    if resolved_scorecard_id != scorecard_id:
                        raise ValueError(
                            f"Score '{score_identifier}' does not belong to scorecard '{scorecard_id}'."
                        )
            else:
                score = None
                for lookup, kwargs in [
                    (Score.get_by_name, {"name": score_identifier, "scorecard_id": scorecard_id}),
                    (Score.get_by_key, {"key": score_identifier, "scorecard_id": scorecard_id}),
                    (Score.get_by_external_id, {"external_id": score_identifier, "scorecard_id": scorecard_id}),
                ]:
                    try:
                        score = await self._to_thread(lookup, client=self.api_client, **kwargs)
                        if score:
                            break
                    except Exception:
                        continue
            if not score:
                raise ValueError(
                    f"Score not found for identifier '{score_identifier}' on scorecard '{scorecard_id}'."
                )
            return [{"score_id": score.id, "score_name": score.name}]

        return await self._fetch_all_scores_for_scorecard(scorecard_id)

    async def _fetch_scorecard_id_for_section_id(self, section_id: str) -> str:
        query = """
        query GetSectionForScore($sectionId: ID!) {
            getSection(id: $sectionId) {
                scorecardId
            }
        }
        """
        result = await self._to_thread(self.api_client.execute, query, {"sectionId": section_id})
        section = (result or {}).get("getSection") or {}
        resolved_scorecard_id = section.get("scorecardId")
        if not resolved_scorecard_id:
            raise ValueError(f"Could not resolve scorecard for section '{section_id}'.")
        return str(resolved_scorecard_id)

    async def _fetch_all_scores_for_scorecard(self, scorecard_id: str) -> List[Dict[str, str]]:
        query = """
        query GetScorecardScores($scorecardId: ID!) {
            getScorecard(id: $scorecardId) {
                sections {
                    items {
                        id
                        scores {
                            items {
                                id
                                name
                                order
                            }
                        }
                    }
                }
            }
        }
        """
        result = await self._to_thread(self.api_client.execute, query, {"scorecardId": scorecard_id})
        scorecard_data = (result or {}).get("getScorecard") or {}

        raw_scores: List[Dict[str, Any]] = []
        sections = (scorecard_data.get("sections") or {}).get("items") or []
        for section_index, section in enumerate(sections):
            scores = (section.get("scores") or {}).get("items") or []
            for score_index, score in enumerate(scores):
                score_id = score.get("id")
                if not score_id:
                    continue
                raw_scores.append(
                    {
                        "score_id": score_id,
                        "score_name": score.get("name") or score_id,
                        "section_order": section_index,
                        "score_order": score.get("order", score_index),
                    }
                )

        raw_scores.sort(key=lambda item: (item["section_order"], item["score_order"]))
        return [{"score_id": s["score_id"], "score_name": s["score_name"]} for s in raw_scores]

    async def _fetch_feedback_items_for_score(
        self,
        scorecard_id: str,
        score_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[FeedbackItem]:
        account_id = self._resolve_account_id()
        return await feedback_utils.fetch_feedback_items_for_score(
            api_client=self.api_client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            start_date=start_date,
            end_date=end_date,
        )

    def _resolve_account_id(self) -> str:
        account_id = self.params.get("account_id")
        if not account_id and hasattr(self.api_client, "context") and self.api_client.context:
            account_id = self.api_client.context.account_id
        if not account_id and hasattr(self.api_client, "account_id"):
            account_id = self.api_client.account_id
        if not account_id:
            raise ValueError("Could not resolve account_id for FeedbackItem queries.")
        return str(account_id)

    async def _to_thread(self, fn, *args, **kwargs):
        import asyncio

        return await asyncio.to_thread(fn, *args, **kwargs)

    def _build_buckets(
        self,
        now_local: datetime,
        bucket_type: str,
        bucket_count: int,
        week_start: str,
    ) -> List[_TimeBucket]:
        day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

        if bucket_type in self.TRAILING_BUCKET_DAYS:
            days = self.TRAILING_BUCKET_DAYS[bucket_type]
            duration = timedelta(days=days)
            anchor = day_start
            first_start = anchor - (duration * bucket_count)
            return [
                _TimeBucket(
                    start_local=first_start + (duration * i),
                    end_local=first_start + (duration * (i + 1)),
                    label=(first_start + (duration * i)).strftime("%Y-%m-%d"),
                )
                for i in range(bucket_count)
            ]

        if bucket_type == "calendar_day":
            duration = timedelta(days=1)
            anchor = day_start
            first_start = anchor - (duration * bucket_count)
            return [
                _TimeBucket(
                    start_local=first_start + (duration * i),
                    end_local=first_start + (duration * (i + 1)),
                    label=(first_start + (duration * i)).strftime("%Y-%m-%d"),
                )
                for i in range(bucket_count)
            ]

        if bucket_type == "calendar_week":
            week_start_index = self.WEEK_START_INDEX[week_start]
            offset = (day_start.weekday() - week_start_index) % 7
            current_period_start = day_start - timedelta(days=offset)
            duration = timedelta(days=7)
            first_start = current_period_start - (duration * bucket_count)
            return [
                _TimeBucket(
                    start_local=first_start + (duration * i),
                    end_local=first_start + (duration * (i + 1)),
                    label=(first_start + (duration * i)).strftime("%Y-%m-%d"),
                )
                for i in range(bucket_count)
            ]

        if bucket_type == "calendar_biweek":
            week_start_index = self.WEEK_START_INDEX[week_start]
            offset = (day_start.weekday() - week_start_index) % 7
            current_week_start = day_start - timedelta(days=offset)
            epoch = day_start.replace(year=1970, month=1, day=5 if week_start == "monday" else 4)
            weeks_since_epoch = int((current_week_start - epoch).days // 7)
            current_period_start = epoch + timedelta(weeks=(weeks_since_epoch // 2) * 2)
            duration = timedelta(days=14)
            first_start = current_period_start - (duration * bucket_count)
            return [
                _TimeBucket(
                    start_local=first_start + (duration * i),
                    end_local=first_start + (duration * (i + 1)),
                    label=(first_start + (duration * i)).strftime("%Y-%m-%d"),
                )
                for i in range(bucket_count)
            ]

        if bucket_type == "calendar_month":
            current_month_start = day_start.replace(day=1)
            first_start = self._shift_months(current_month_start, -bucket_count)
            buckets: List[_TimeBucket] = []
            for i in range(bucket_count):
                start_local = self._shift_months(first_start, i)
                end_local = self._shift_months(first_start, i + 1)
                buckets.append(
                    _TimeBucket(
                        start_local=start_local,
                        end_local=end_local,
                        label=start_local.strftime("%Y-%m"),
                    )
                )
            return buckets

        raise ValueError(f"Unhandled bucket_type '{bucket_type}'.")

    def _build_exact_window_buckets(
        self,
        *,
        start_local: datetime,
        end_local: datetime,
        bucket_type: str,
        week_start: str,
    ) -> List[_TimeBucket]:
        if start_local.tzinfo is None:
            start_local = start_local.replace(tzinfo=timezone.utc)
        if end_local.tzinfo is None:
            end_local = end_local.replace(tzinfo=timezone.utc)

        if end_local <= start_local:
            return []

        if bucket_type in self.TRAILING_BUCKET_DAYS:
            duration = timedelta(days=self.TRAILING_BUCKET_DAYS[bucket_type])
            buckets: List[_TimeBucket] = []
            current_start = start_local
            while current_start < end_local:
                current_end = min(current_start + duration, end_local)
                buckets.append(
                    _TimeBucket(
                        start_local=current_start,
                        end_local=current_end,
                        label=current_start.strftime("%Y-%m-%d"),
                    )
                )
                current_start = current_end
            return buckets

        period_start = self._calendar_period_start(start_local, bucket_type, week_start)
        buckets = []
        while period_start < end_local:
            period_end = self._advance_calendar_period(period_start, bucket_type)
            clipped_start = max(period_start, start_local)
            clipped_end = min(period_end, end_local)
            if clipped_start < clipped_end:
                buckets.append(
                    _TimeBucket(
                        start_local=clipped_start,
                        end_local=clipped_end,
                        label=self._calendar_period_label(period_start, bucket_type),
                    )
                )
            period_start = period_end

        return buckets

    def _calendar_period_start(
        self,
        value: datetime,
        bucket_type: str,
        week_start: str,
    ) -> datetime:
        day_start = value.replace(hour=0, minute=0, second=0, microsecond=0)

        if bucket_type == "calendar_day":
            return day_start

        if bucket_type == "calendar_week":
            week_start_index = self.WEEK_START_INDEX[week_start]
            offset = (day_start.weekday() - week_start_index) % 7
            return day_start - timedelta(days=offset)

        if bucket_type == "calendar_biweek":
            week_start_index = self.WEEK_START_INDEX[week_start]
            offset = (day_start.weekday() - week_start_index) % 7
            current_week_start = day_start - timedelta(days=offset)
            epoch_day = 5 if week_start == "monday" else 4
            epoch = day_start.replace(year=1970, month=1, day=epoch_day)
            weeks_since_epoch = int((current_week_start - epoch).days // 7)
            return epoch + timedelta(weeks=(weeks_since_epoch // 2) * 2)

        if bucket_type == "calendar_month":
            return day_start.replace(day=1)

        raise ValueError(f"Unsupported calendar bucket type '{bucket_type}'.")

    def _advance_calendar_period(self, period_start: datetime, bucket_type: str) -> datetime:
        if bucket_type == "calendar_day":
            return period_start + timedelta(days=1)
        if bucket_type == "calendar_week":
            return period_start + timedelta(days=7)
        if bucket_type == "calendar_biweek":
            return period_start + timedelta(days=14)
        if bucket_type == "calendar_month":
            return self._shift_months(period_start, 1)
        raise ValueError(f"Unsupported calendar bucket type '{bucket_type}'.")

    def _calendar_period_label(self, period_start: datetime, bucket_type: str) -> str:
        if bucket_type == "calendar_month":
            return period_start.strftime("%Y-%m")
        return period_start.strftime("%Y-%m-%d")

    def _shift_months(self, value: datetime, months: int) -> datetime:
        month_index = (value.month - 1) + months
        year = value.year + (month_index // 12)
        month = (month_index % 12) + 1
        return value.replace(year=year, month=month, day=1)

    def _find_bucket_index(self, edited_local: datetime, buckets: List[_TimeBucket]) -> Optional[int]:
        for index, bucket in enumerate(buckets):
            if bucket.start_local <= edited_local < bucket.end_local:
                return index
        return None

    def _calculate_alignment_metrics(self, items: List[FeedbackItem]) -> Dict[str, Any]:
        paired_initial: List[str] = []
        paired_final: List[str] = []

        for item in items:
            if item.initialAnswerValue is None or item.finalAnswerValue is None:
                continue
            paired_initial.append(str(item.initialAnswerValue))
            paired_final.append(str(item.finalAnswerValue))

        item_count = len(paired_initial)
        if item_count == 0:
            return {
                "ac1": None,
                "accuracy": None,
                "item_count": 0,
                "agreements": 0,
                "mismatches": 0,
            }

        agreements = sum(1 for initial, final in zip(paired_initial, paired_final) if initial == final)
        mismatches = item_count - agreements
        accuracy = (agreements / item_count) * 100

        ac1: Optional[float] = None
        try:
            calculator = GwetAC1()
            metric_input = Metric.Input(reference=paired_final, predictions=paired_initial)
            ac1 = calculator.calculate(metric_input).value
        except Exception as exc:
            self._log(f"Warning: AC1 calculation failed for bucket with {item_count} items: {exc}", level="WARNING")

        return {
            "ac1": ac1,
            "accuracy": accuracy,
            "item_count": item_count,
            "agreements": agreements,
            "mismatches": mismatches,
        }

    def _build_point(self, bucket: _TimeBucket, index: int, metrics: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "bucket_index": index,
            "label": bucket.label,
            "start": bucket.start_local.astimezone(timezone.utc).isoformat(),
            "end": bucket.end_local.astimezone(timezone.utc).isoformat(),
            "ac1": metrics["ac1"],
            "accuracy": metrics["accuracy"],
            "item_count": metrics["item_count"],
            "agreements": metrics["agreements"],
            "mismatches": metrics["mismatches"],
        }

    def _serialize_buckets(self, buckets: List[_TimeBucket]) -> List[Dict[str, Any]]:
        return [
            {
                "bucket_index": index,
                "label": bucket.label,
                "start": bucket.start_local.astimezone(timezone.utc).isoformat(),
                "end": bucket.end_local.astimezone(timezone.utc).isoformat(),
            }
            for index, bucket in enumerate(buckets)
        ]
