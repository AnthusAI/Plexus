from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from plexus.analysis.metrics import GwetAC1
from plexus.analysis.metrics.metric import Metric
from plexus.dashboard.api.models.feedback_item import FeedbackItem

from . import feedback_utils
from .base import BaseReportBlock
from .feedback_scope_resolver import (
    ResolvedScoreRef,
    list_scores_for_scorecard,
    resolve_score_for_scorecard,
    resolve_scorecard,
)


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
    DEFAULT_ROLLING_MIN_ITEMS = 100
    ROLLING_LOOKBACK_START_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)

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
            include_score_identifiers = self._parse_score_filter_values(self._get_param("include_scores"))
            exclude_score_identifiers = self._parse_score_filter_values(self._get_param("exclude_scores"))
            has_score_filter = bool(include_score_identifiers or exclude_score_identifiers)
            if score_identifier and has_score_filter:
                raise ValueError("'score'/'score_id' cannot be combined with 'include_scores' or 'exclude_scores'.")

            bucket_type = str(self._get_param("bucket_type") or "trailing_7d").strip().lower()
            requested_bucket_count = self._get_param("bucket_count")
            bucket_count = int(requested_bucket_count) if requested_bucket_count is not None else 12
            timezone_name = str(self._get_param("timezone") or "UTC").strip()
            week_start = str(self._get_param("week_start") or "monday").strip().lower()
            show_bucket_details = self._parse_bool(self._get_param("show_bucket_details"), default=False)
            rolling_min_items = int(self._get_param("rolling_min_items") or self.DEFAULT_ROLLING_MIN_ITEMS)

            if bucket_type not in self.TRAILING_BUCKET_DAYS and bucket_type not in self.CALENDAR_BUCKET_TYPES:
                supported = sorted(list(self.TRAILING_BUCKET_DAYS.keys()) + list(self.CALENDAR_BUCKET_TYPES))
                raise ValueError(
                    f"Unsupported bucket_type '{bucket_type}'. Supported values: {supported}"
                )
            if week_start not in self.WEEK_START_INDEX:
                raise ValueError("'week_start' must be either 'monday' or 'sunday'.")
            if rolling_min_items <= 0:
                raise ValueError("'rolling_min_items' must be a positive integer.")

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
            score_filter: Optional[Dict[str, Any]] = None
            if has_score_filter:
                scores_to_analyze, score_filter = await self._resolve_scores_with_filters(
                    scorecard_id=scorecard.id,
                    include_score_identifiers=include_score_identifiers,
                    exclude_score_identifiers=exclude_score_identifiers,
                )
            else:
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
            sample_policy = self._build_sample_policy(
                rolling_min_items=rolling_min_items,
                bucket_type=bucket_type,
            )

            if not scores_to_analyze:
                output = {
                    "mode": "single_score" if score_identifier else "all_scores",
                    "block_title": self.DEFAULT_NAME,
                    "block_description": self.DEFAULT_DESCRIPTION,
                    "scorecard_id": scorecard.id,
                    "scorecard_name": scorecard.name,
                    "show_bucket_details": show_bucket_details,
                    "bucket_policy": bucket_policy,
                    "sample_policy": sample_policy,
                    "buckets": self._serialize_buckets(buckets),
                    "overall": {"score_id": "overall", "score_name": "Overall", "points": []},
                    "scores": [],
                    "message": "No scores found for the requested scope.",
                    "date_range": {
                        "start": range_start_utc.isoformat(),
                        "end": date_range_end_utc.isoformat(),
                    },
                    "fetched_feedback_items": 0,
                    "ignored_invalid_feedback_items": 0,
                    "analyzed_feedback_items": 0,
                    "total_feedback_items_retrieved": 0,
                }
                if score_filter is not None:
                    output["score_filter"] = score_filter
                return output, self._get_log_string()

            self._log(
                f"Running FeedbackAlignmentTimeline for scorecard '{scorecard.name}' "
                f"with {len(scores_to_analyze)} score(s), bucket_type={bucket_type}, "
                f"bucket_count={effective_bucket_count}, window_mode={window_mode}"
            )

            score_series: List[Dict[str, Any]] = []
            total_feedback_items_retrieved = 0
            fetched_feedback_items = 0
            ignored_invalid_feedback_items = 0
            overall_metric_items: List[FeedbackItem] = []

            for score_info in scores_to_analyze:
                score_id = score_info["score_id"]
                score_name = score_info["score_name"]
                self._last_feedback_fetch_stats = None
                feedback_items = await self._fetch_feedback_items_for_score(
                    scorecard_id=scorecard.id,
                    score_id=score_id,
                    start_date=self.ROLLING_LOOKBACK_START_UTC,
                    end_date=range_end_query_utc,
                )
                fetch_stats = getattr(self, "_last_feedback_fetch_stats", None)
                if not isinstance(fetch_stats, dict):
                    fetch_stats = {
                        "fetched_total": len(feedback_items),
                        "ignored_invalid": 0,
                        "analyzed_total": len(feedback_items),
                    }
                fetched_feedback_items += fetch_stats["fetched_total"]
                ignored_invalid_feedback_items += fetch_stats["ignored_invalid"]
                total_feedback_items_retrieved += fetch_stats["analyzed_total"]
                metric_items = self._prepare_metric_items(feedback_items)
                overall_metric_items.extend(metric_items)

                points = self._build_rolling_points(
                    buckets=buckets,
                    metric_items=metric_items,
                    tzinfo=tzinfo,
                    rolling_min_items=rolling_min_items,
                )
                score_series.append(
                    {
                        "score_id": score_id,
                        "score_name": score_name,
                        "points": points,
                    }
                )

            overall_points = self._build_rolling_points(
                buckets=buckets,
                metric_items=self._prepare_metric_items(overall_metric_items),
                tzinfo=tzinfo,
                rolling_min_items=rolling_min_items,
            )

            mode = "single_score" if score_identifier else "all_scores"
            output: Dict[str, Any] = {
                "mode": mode,
                "block_title": self.DEFAULT_NAME,
                "block_description": self.DEFAULT_DESCRIPTION,
                "scorecard_id": scorecard.id,
                "scorecard_name": scorecard.name,
                "show_bucket_details": show_bucket_details,
                "bucket_policy": bucket_policy,
                "sample_policy": sample_policy,
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
                "fetched_feedback_items": fetched_feedback_items,
                "ignored_invalid_feedback_items": ignored_invalid_feedback_items,
                "analyzed_feedback_items": total_feedback_items_retrieved,
                "total_feedback_items_retrieved": total_feedback_items_retrieved,
                "message": (
                    f"Processed {len(score_series)} score(s) across "
                    f"{len(buckets)} bucket(s) in {window_mode} mode."
                ),
            }
            if score_filter is not None:
                output["score_filter"] = score_filter

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

    def _parse_score_filter_values(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        if isinstance(value, (list, tuple, set)):
            values: List[str] = []
            for item in value:
                values.extend(self._parse_score_filter_values(item))
            return values
        stripped = str(value).strip()
        return [stripped] if stripped else []

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

    async def _resolve_scorecard(self, scorecard_identifier: str) -> Any:
        return await resolve_scorecard(self.api_client, scorecard_identifier)

    async def _resolve_scores_for_mode(
        self,
        scorecard_id: str,
        score_identifier: Optional[str],
    ) -> List[Dict[str, str]]:
        if score_identifier:
            score = await resolve_score_for_scorecard(
                self.api_client,
                scorecard_id,
                score_identifier,
            )
            return [{"score_id": score.id, "score_name": score.name}]

        scores = await list_scores_for_scorecard(self.api_client, scorecard_id)
        return [{"score_id": score.id, "score_name": score.name} for score in scores]

    async def _resolve_scores_with_filters(
        self,
        *,
        scorecard_id: str,
        include_score_identifiers: List[str],
        exclude_score_identifiers: List[str],
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        score_refs = await list_scores_for_scorecard(self.api_client, scorecard_id)
        if include_score_identifiers:
            included_refs = self._resolve_score_filter_identifiers(
                score_refs,
                include_score_identifiers,
                scorecard_id=scorecard_id,
                filter_name="include_scores",
            )
        else:
            included_refs = list(score_refs)

        excluded_refs = self._resolve_score_filter_identifiers(
            score_refs,
            exclude_score_identifiers,
            scorecard_id=scorecard_id,
            filter_name="exclude_scores",
        )
        excluded_ids = {score.id for score in excluded_refs}
        final_refs = [score for score in included_refs if score.id not in excluded_ids]

        return (
            [{"score_id": score.id, "score_name": score.name} for score in final_refs],
            {
                "requested_include_scores": include_score_identifiers,
                "requested_exclude_scores": exclude_score_identifiers,
                "resolved_included_scores": self._serialize_score_refs(final_refs),
                "resolved_excluded_scores": self._serialize_score_refs(excluded_refs),
            },
        )

    def _resolve_score_filter_identifiers(
        self,
        score_refs: List[ResolvedScoreRef],
        identifiers: List[str],
        *,
        scorecard_id: str,
        filter_name: str,
    ) -> List[ResolvedScoreRef]:
        resolved: List[ResolvedScoreRef] = []
        seen_ids = set()
        for identifier in identifiers:
            score_ref = self._find_score_ref(score_refs, identifier)
            if score_ref is None:
                raise ValueError(
                    f"{filter_name} identifier '{identifier}' did not match any score on scorecard '{scorecard_id}'."
                )
            if score_ref.id in seen_ids:
                continue
            resolved.append(score_ref)
            seen_ids.add(score_ref.id)
        return resolved

    def _find_score_ref(self, score_refs: List[ResolvedScoreRef], identifier: str) -> Optional[ResolvedScoreRef]:
        normalized = str(identifier).strip()
        if not normalized:
            return None

        for score_ref in score_refs:
            if normalized in {
                score_ref.id,
                score_ref.name,
                score_ref.key or "",
                score_ref.external_id or "",
            }:
                return score_ref

        folded = normalized.casefold()
        matches = [
            score_ref
            for score_ref in score_refs
            if folded
            in {
                score_ref.id.casefold(),
                score_ref.name.casefold(),
                (score_ref.key or "").casefold(),
                (score_ref.external_id or "").casefold(),
            }
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(f"{score.name} ({score.id})" for score in matches)
            raise ValueError(f"Score filter identifier '{identifier}' matched multiple scores: {names}.")
        return None

    def _serialize_score_refs(self, score_refs: List[ResolvedScoreRef]) -> List[Dict[str, str]]:
        return [{"score_id": score.id, "score_name": score.name} for score in score_refs]

    async def _fetch_feedback_items_for_score(
        self,
        scorecard_id: str,
        score_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[FeedbackItem]:
        account_id = self._resolve_account_id()
        items, stats = await feedback_utils.fetch_feedback_items_for_score_with_stats(
            api_client=self.api_client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            start_date=start_date,
            end_date=end_date,
            exclude_invalid=True,
        )
        self._last_feedback_fetch_stats = stats
        return items

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

    def _build_sample_policy(self, *, rolling_min_items: int, bucket_type: str) -> Dict[str, Any]:
        return {
            "metric": "Gwet AC1 over stored feedback answer pairs",
            "bucket_type": bucket_type,
            "rolling_min_items": rolling_min_items,
            "lookback": "unbounded",
            "bucket_timestamp": "FeedbackItem.editedAt",
            "prediction_value": "FeedbackItem.initialAnswerValue",
            "reference_value": "FeedbackItem.finalAnswerValue",
            "explanation": (
                "Each chart measures how often stored production score answers agreed with "
                "the final human correction recorded in feedback. Buckets are based on "
                "feedback edit time, not call time or score-version release time. Each point "
                "first uses feedback edited inside the bucket. If the bucket has fewer than "
                f"{rolling_min_items} feedback records, older feedback is added until the sample "
                f"reaches {rolling_min_items} records or no earlier feedback exists. Lookback "
                "records only stabilize sparse buckets; each point still ends at that bucket's "
                "end date. Feedback items marked invalid are excluded before analysis. "
                "This is not a replay or backtest of historical champion versions."
            ),
        }

    def _prepare_metric_items(self, items: List[FeedbackItem]) -> List[FeedbackItem]:
        metric_items = [
            item
            for item in items
            if item.editedAt is not None
            and item.initialAnswerValue is not None
            and item.finalAnswerValue is not None
        ]
        return sorted(metric_items, key=self._edited_at_utc)

    def _edited_at_utc(self, item: FeedbackItem) -> datetime:
        edited_at = item.editedAt
        if edited_at is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if edited_at.tzinfo is None:
            edited_at = edited_at.replace(tzinfo=timezone.utc)
        return edited_at.astimezone(timezone.utc)

    def _edited_at_local(self, item: FeedbackItem, tzinfo: ZoneInfo) -> datetime:
        return self._edited_at_utc(item).astimezone(tzinfo)

    def _build_rolling_points(
        self,
        *,
        buckets: List[_TimeBucket],
        metric_items: List[FeedbackItem],
        tzinfo: ZoneInfo,
        rolling_min_items: int,
    ) -> List[Dict[str, Any]]:
        points: List[Dict[str, Any]] = []
        sorted_items = self._prepare_metric_items(metric_items)

        for index, bucket in enumerate(buckets):
            bucket_items = [
                item
                for item in sorted_items
                if bucket.start_local <= self._edited_at_local(item, tzinfo) < bucket.end_local
            ]
            bucket_item_count = len(bucket_items)
            if bucket_item_count >= rolling_min_items:
                sample_items = bucket_items
            else:
                eligible_items = [
                    item
                    for item in sorted_items
                    if self._edited_at_local(item, tzinfo) < bucket.end_local
                ]
                sample_items = eligible_items[-rolling_min_items:]

            lookback_item_count = max(0, len(sample_items) - bucket_item_count)
            sample_dates = [self._edited_at_utc(item) for item in sample_items]
            sample_start = min(sample_dates).isoformat() if sample_dates else None
            sample_end = max(sample_dates).isoformat() if sample_dates else None
            metrics = self._calculate_alignment_metrics(sample_items)
            sample_metadata = {
                "bucket_item_count": bucket_item_count,
                "sample_item_count": metrics["item_count"],
                "lookback_item_count": lookback_item_count,
                "sample_start": sample_start,
                "sample_end": sample_end,
                "sample_extended": lookback_item_count > 0,
                "sample_underfilled": metrics["item_count"] < rolling_min_items,
            }
            points.append(self._build_point(bucket, index, metrics, sample_metadata=sample_metadata))

        return points

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

    def _build_point(
        self,
        bucket: _TimeBucket,
        index: int,
        metrics: Dict[str, Any],
        *,
        sample_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        point = {
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
        if sample_metadata:
            point.update(sample_metadata)
        return point

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
