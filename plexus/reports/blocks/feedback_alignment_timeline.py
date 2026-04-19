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

    Bucket policy supports trailing complete windows and calendar-aligned complete windows.
    """

    DEFAULT_NAME = "Feedback Alignment Timeline"
    DEFAULT_DESCRIPTION = "Alignment metrics over complete historical time buckets"

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
            scorecard_identifier = self.config.get("scorecard")
            if not scorecard_identifier:
                raise ValueError("'scorecard' is required in block configuration.")

            score_identifier = (
                self.config.get("score_id")
                or self.config.get("score")
                or self.params.get("score_id")
                or self.params.get("score")
                or self.params.get("param_score_id")
                or self.params.get("param_score")
            )
            if score_identifier is not None:
                score_identifier = str(score_identifier).strip() or None

            bucket_type = str(self.config.get("bucket_type", "trailing_7d")).strip().lower()
            bucket_count = int(self.config.get("bucket_count", 12))
            timezone_name = str(self.config.get("timezone", "UTC")).strip()
            week_start = str(self.config.get("week_start", "monday")).strip().lower()

            if bucket_type not in self.TRAILING_BUCKET_DAYS and bucket_type not in self.CALENDAR_BUCKET_TYPES:
                supported = sorted(list(self.TRAILING_BUCKET_DAYS.keys()) + list(self.CALENDAR_BUCKET_TYPES))
                raise ValueError(
                    f"Unsupported bucket_type '{bucket_type}'. Supported values: {supported}"
                )
            if bucket_count <= 0:
                raise ValueError("'bucket_count' must be a positive integer.")
            if week_start not in self.WEEK_START_INDEX:
                raise ValueError("'week_start' must be either 'monday' or 'sunday'.")

            try:
                tzinfo = ZoneInfo(timezone_name)
            except Exception as exc:
                raise ValueError(f"Invalid timezone '{timezone_name}': {exc}") from exc

            now_local = self._now_utc().astimezone(tzinfo)
            buckets = self._build_buckets(
                now_local=now_local,
                bucket_type=bucket_type,
                bucket_count=bucket_count,
                week_start=week_start,
            )
            if not buckets:
                raise ValueError("No time buckets were generated.")

            range_start_utc = buckets[0].start_local.astimezone(timezone.utc)
            # Query end is inclusive in FeedbackItem utility query; subtract 1 microsecond to stay inside last bucket.
            range_end_query_utc = (
                buckets[-1].end_local.astimezone(timezone.utc) - timedelta(microseconds=1)
            )

            scorecard = await self._resolve_scorecard(str(scorecard_identifier))
            scores_to_analyze = await self._resolve_scores_for_mode(
                scorecard_id=scorecard.id,
                score_identifier=score_identifier,
            )
            if not scores_to_analyze:
                return {
                    "mode": "single_score" if score_identifier else "all_scores",
                    "block_title": self.DEFAULT_NAME,
                    "block_description": self.DEFAULT_DESCRIPTION,
                    "scorecard_id": scorecard.id,
                    "scorecard_name": scorecard.name,
                    "bucket_policy": {
                        "bucket_type": bucket_type,
                        "bucket_count": bucket_count,
                        "timezone": timezone_name,
                        "week_start": week_start,
                        "complete_only": True,
                    },
                    "buckets": self._serialize_buckets(buckets),
                    "overall": {"score_id": "overall", "score_name": "Overall", "points": []},
                    "scores": [],
                    "message": "No scores found for the requested scope.",
                }, self._get_log_string()

            self._log(
                f"Running FeedbackAlignmentTimeline for scorecard '{scorecard.name}' "
                f"with {len(scores_to_analyze)} score(s), bucket_type={bucket_type}, bucket_count={bucket_count}"
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
                "bucket_policy": {
                    "bucket_type": bucket_type,
                    "bucket_count": bucket_count,
                    "timezone": timezone_name,
                    "week_start": week_start,
                    "complete_only": True,
                },
                "buckets": self._serialize_buckets(buckets),
                "overall": {
                    "score_id": "overall",
                    "score_name": "Overall",
                    "points": overall_points,
                },
                "scores": score_series,
                "date_range": {
                    "start": buckets[0].start_local.astimezone(timezone.utc).isoformat(),
                    "end": buckets[-1].end_local.astimezone(timezone.utc).isoformat(),
                },
                "total_feedback_items_retrieved": total_feedback_items_retrieved,
                "message": (
                    f"Processed {len(score_series)} score(s) across "
                    f"{len(buckets)} complete bucket(s)."
                ),
            }

            # In single-score mode, "overall" and selected score should represent the same series.
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
