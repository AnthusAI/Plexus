from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import time

from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard

from .base import BaseReportBlock
from .identifier_utils import looks_like_uuid


class FeedbackRatesBase(BaseReportBlock):
    """
    Shared helpers for feedback-oriented rate reports built from ScoreResult + FeedbackItem.
    """

    DEFAULT_DAYS = 30
    DEFAULT_FETCH_SHARD_DAYS = 30
    DEFAULT_FETCH_SHARD_CONCURRENCY = 4
    DEFAULT_FETCH_MAX_INFLIGHT_PROCESS = 8

    def _get_param(self, name: str) -> Any:
        return self.config.get(name) or self.params.get(name) or self.params.get(f"param_{name}")

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

    def _resolve_window(self) -> Tuple[datetime, datetime]:
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
            end_date = datetime.now(tz=timezone.utc)
            start_date = end_date - timedelta(days=days)

        if end_date < start_date:
            raise ValueError("'end_date' must be on or after 'start_date'.")
        return start_date, end_date

    def _resolve_account_id(self) -> str:
        account_id = self.params.get("account_id")
        if not account_id and hasattr(self.api_client, "context") and self.api_client.context:
            account_id = self.api_client.context.account_id
        if not account_id and hasattr(self.api_client, "account_id"):
            account_id = self.api_client.account_id
        if not account_id:
            raise ValueError("Could not resolve account_id.")
        return str(account_id)

    def _resolve_fetch_options(self) -> Tuple[int, int, int]:
        shard_days_raw = self._get_param("fetch_shard_days")
        shard_concurrency_raw = self._get_param("fetch_shard_concurrency")
        max_inflight_raw = self._get_param("fetch_max_inflight_process")

        shard_days = (
            int(shard_days_raw)
            if shard_days_raw is not None and str(shard_days_raw).strip() != ""
            else self.DEFAULT_FETCH_SHARD_DAYS
        )
        shard_concurrency = (
            int(shard_concurrency_raw)
            if shard_concurrency_raw is not None and str(shard_concurrency_raw).strip() != ""
            else self.DEFAULT_FETCH_SHARD_CONCURRENCY
        )
        max_inflight_process = (
            int(max_inflight_raw)
            if max_inflight_raw is not None and str(max_inflight_raw).strip() != ""
            else self.DEFAULT_FETCH_MAX_INFLIGHT_PROCESS
        )

        if shard_days <= 0:
            raise ValueError("'fetch_shard_days' must be a positive integer.")
        if shard_concurrency <= 0:
            raise ValueError("'fetch_shard_concurrency' must be a positive integer.")
        if max_inflight_process <= 0:
            raise ValueError("'fetch_max_inflight_process' must be a positive integer.")
        return shard_days, shard_concurrency, max_inflight_process

    def _to_dt(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(normalized)
            except ValueError:
                return datetime.min.replace(tzinfo=timezone.utc)
        else:
            return datetime.min.replace(tzinfo=timezone.utc)

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _is_production_result(self, result: Dict[str, Any]) -> bool:
        return (
            not result.get("evaluationId")
            and str(result.get("type") or "").lower() == "prediction"
            and str(result.get("status") or "").upper() == "COMPLETED"
            and str(result.get("code") or "") == "200"
        )

    async def _resolve_scorecard(self, scorecard_identifier: str) -> Scorecard:
        scorecard = None
        if looks_like_uuid(scorecard_identifier):
            try:
                scorecard = await asyncio.to_thread(
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
                    scorecard = await asyncio.to_thread(lookup, client=self.api_client, **kwargs)
                    if scorecard:
                        break
                except Exception:
                    continue
        if not scorecard:
            raise ValueError(f"Scorecard not found for identifier '{scorecard_identifier}'.")
        return scorecard

    async def _resolve_score(self, score_identifier: str, scorecard_id: str) -> Score:
        score = None
        if looks_like_uuid(score_identifier):
            try:
                score = await asyncio.to_thread(
                    Score.get_by_id,
                    id=score_identifier,
                    client=self.api_client,
                )
            except Exception:
                score = None
        if not score:
            for lookup, kwargs in [
                (Score.get_by_name, {"name": score_identifier, "scorecard_id": scorecard_id}),
                (Score.get_by_key, {"key": score_identifier, "scorecard_id": scorecard_id}),
                (Score.get_by_external_id, {"external_id": score_identifier, "scorecard_id": scorecard_id}),
            ]:
                try:
                    score = await asyncio.to_thread(lookup, client=self.api_client, **kwargs)
                    if score:
                        break
                except Exception:
                    continue
        if not score:
            raise ValueError(
                f"Score not found for identifier '{score_identifier}' on scorecard '{scorecard_id}'."
            )
        return score

    async def _fetch_score_results_window(
        self,
        *,
        account_id: str,
        scorecard_id: str,
        start_date: datetime,
        end_date: datetime,
        score_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        shard_days, shard_concurrency, max_inflight_process = self._resolve_fetch_options()
        shards = self._build_time_shards(start_date=start_date, end_date=end_date, shard_days=shard_days)
        if not shards:
            return []
        shard_count = len(shards)

        self._log(
            "Fetching score results with sharded scan "
            f"(shards={shard_count}, shard_days={shard_days}, "
            f"shard_concurrency={shard_concurrency}, max_inflight_process={max_inflight_process})"
        )

        started = time.perf_counter()
        semaphore = asyncio.Semaphore(shard_concurrency)
        shard_results: List[List[Dict[str, Any]]] = [[] for _ in range(shard_count)]

        async def _run_shard(shard_index: int, shard_start: datetime, shard_end: datetime) -> None:
            async with semaphore:
                shard_started = time.perf_counter()
                rows = await self._fetch_score_results_shard(
                    account_id=account_id,
                    scorecard_id=scorecard_id,
                    score_id=score_id,
                    shard_start=shard_start,
                    shard_end=shard_end,
                    shard_index=shard_index,
                    shard_count=shard_count,
                    max_inflight_process=max_inflight_process,
                )
                shard_results[shard_index] = rows
                self._log(
                    f"[score-results] shard {shard_index + 1}/{shard_count} "
                    f"completed rows={len(rows)} elapsed={time.perf_counter() - shard_started:.2f}s"
                )

        await asyncio.gather(
            *[
                _run_shard(shard_index=idx, shard_start=window[0], shard_end=window[1])
                for idx, window in enumerate(shards)
            ]
        )

        merged_rows: List[Dict[str, Any]] = []
        for rows in shard_results:
            if rows:
                merged_rows.extend(rows)

        deduped_rows = self._dedupe_score_results_by_id(merged_rows)
        self._log(
            "[score-results] complete "
            f"(raw_kept={len(merged_rows)}, deduped={len(deduped_rows)}, "
            f"elapsed={time.perf_counter() - started:.2f}s)"
        )
        return deduped_rows

    def _build_time_shards(
        self,
        *,
        start_date: datetime,
        end_date: datetime,
        shard_days: int,
    ) -> List[Tuple[datetime, datetime]]:
        if end_date <= start_date:
            return []
        shards: List[Tuple[datetime, datetime]] = []
        cursor = start_date
        while cursor < end_date:
            shard_end = min(cursor + timedelta(days=shard_days), end_date)
            shards.append((cursor, shard_end))
            cursor = shard_end
        return shards

    async def _filter_score_results_page(
        self,
        *,
        raw_items: List[Dict[str, Any]],
        account_id: str,
        scorecard_id: str,
    ) -> List[Dict[str, Any]]:
        return [
            item
            for item in raw_items
            if str(item.get("accountId") or "") == str(account_id)
            and str(item.get("scorecardId") or "") == str(scorecard_id)
        ]

    async def _fetch_score_results_shard(
        self,
        *,
        account_id: str,
        scorecard_id: str,
        score_id: Optional[str],
        shard_start: datetime,
        shard_end: datetime,
        shard_index: int,
        shard_count: int,
        max_inflight_process: int,
    ) -> List[Dict[str, Any]]:
        kept_rows: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        seen_tokens: set[str] = set()
        query_name = "listScoreResultByScorecardIdAndUpdatedAt"
        query = f"""
        query ListScoreResultsByScorecardAndUpdatedAt(
            $scorecardId: String!,
            $startTime: String!,
            $endTime: String!,
            $filter: ModelScoreResultFilterInput,
            $limit: Int,
            $nextToken: String
        ) {{
            {query_name}(
                scorecardId: $scorecardId,
                updatedAt: {{ between: [$startTime, $endTime] }},
                filter: $filter,
                sortDirection: DESC,
                limit: $limit,
                nextToken: $nextToken
            ) {{
                items {{
                    id
                    value
                    itemId
                    accountId
                    scorecardId
                    scoreId
                    evaluationId
                    type
                    status
                    code
                    createdAt
                    updatedAt
                    score {{
                        id
                        name
                    }}
                    item {{
                        id
                        externalId
                        createdAt
                        updatedAt
                        identifiers
                        itemIdentifiers {{
                            items {{
                                name
                                value
                                url
                                position
                            }}
                        }}
                    }}
                }}
                nextToken
            }}
        }}
        """

        page_num = 0
        raw_total = 0
        kept_total = 0
        process_queue: List[Tuple[int, asyncio.Task[List[Dict[str, Any]]], int]] = []

        async def _drain_oldest() -> None:
            nonlocal kept_total
            queued_page_num, task, queued_raw_count = process_queue.pop(0)
            filtered_items = await task
            kept_total += len(filtered_items)
            if filtered_items:
                kept_rows.extend(filtered_items)
            self._log(
                f"[score-results] shard {shard_index + 1}/{shard_count} processed page "
                f"{queued_page_num} kept={len(filtered_items)} raw={queued_raw_count}"
            )

        while True:
            variables: Dict[str, Any] = {
                "scorecardId": str(scorecard_id),
                "startTime": shard_start.isoformat(),
                "endTime": shard_end.isoformat(),
                "limit": 500,
                "nextToken": next_token,
            }
            filter_input: Dict[str, Any] = {"accountId": {"eq": str(account_id)}}
            if score_id:
                filter_input["scoreId"] = {"eq": str(score_id)}
            variables["filter"] = filter_input

            page_num += 1
            self._log(
                f"[score-results] shard {shard_index + 1}/{shard_count} fetch page {page_num} "
                f"(nextToken={'set' if next_token else 'none'})"
            )
            try:
                response = await asyncio.to_thread(self.api_client.execute, query, variables)
            except Exception as exc:
                self._log(
                    f"[score-results] ERROR shard {shard_index + 1}/{shard_count} "
                    f"fetch page {page_num}: {exc}",
                    level="ERROR",
                )
                break
            payload = response.get(query_name) or {}
            raw_items = payload.get("items") or []
            raw_count = len(raw_items)
            raw_total += raw_count
            process_queue.append(
                (
                    page_num,
                    asyncio.create_task(
                        self._filter_score_results_page(
                            raw_items=raw_items,
                            account_id=account_id,
                            scorecard_id=scorecard_id,
                        )
                    ),
                    raw_count,
                )
            )
            while len(process_queue) >= max_inflight_process:
                await _drain_oldest()

            next_token = payload.get("nextToken")
            self._log(
                f"[score-results] shard {shard_index + 1}/{shard_count} fetched page {page_num} "
                f"raw={raw_count}, nextToken={'set' if next_token else 'none'}"
            )
            if not next_token:
                break
            if next_token in seen_tokens:
                self._log(
                    f"[score-results] shard {shard_index + 1}/{shard_count} "
                    "detected repeated pagination token; stopping pagination.",
                    level="WARNING",
                )
                break
            seen_tokens.add(next_token)

        while process_queue:
            await _drain_oldest()

        self._log(
            f"[score-results] shard {shard_index + 1}/{shard_count} summary "
            f"(pages={page_num}, kept={kept_total}, raw={raw_total})"
        )
        return kept_rows

    def _dedupe_score_results_by_id(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        latest_by_id: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            existing = latest_by_id.get(row_id)
            if existing is None:
                latest_by_id[row_id] = row
                continue
            row_ts = self._to_dt(row.get("updatedAt") or row.get("createdAt"))
            existing_ts = self._to_dt(existing.get("updatedAt") or existing.get("createdAt"))
            if row_ts >= existing_ts:
                latest_by_id[row_id] = row

        deduped_rows = list(latest_by_id.values())
        deduped_rows.sort(
            key=lambda row: (
                self._to_dt(row.get("updatedAt") or row.get("createdAt")),
                str(row.get("id") or ""),
            ),
            reverse=True,
        )
        return deduped_rows

    async def _fetch_feedback_items_window(
        self,
        *,
        account_id: str,
        scorecard_id: str,
        start_date: datetime,
        end_date: datetime,
        score_id: Optional[str],
        score_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        async def _fetch_for_score(target_score_id: str) -> List[Dict[str, Any]]:
            query_name = "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt"
            query = f"""
            query ListFeedbackItemsByCompositeEditedAt(
                $accountId: String!,
                $compositeCondition: ModelFeedbackItemByAccountScorecardScoreEditedAtCompositeKeyConditionInput,
                $limit: Int,
                $nextToken: String,
                $sortDirection: ModelSortDirection
            ) {{
                {query_name}(
                    accountId: $accountId,
                    scorecardIdScoreIdEditedAt: $compositeCondition,
                    limit: $limit,
                    nextToken: $nextToken,
                    sortDirection: $sortDirection
                ) {{
                    items {{
                        id
                        scorecardId
                        scoreId
                        itemId
                        initialAnswerValue
                        finalAnswerValue
                        editCommentValue
                        finalCommentValue
                        isInvalid
                        editedAt
                        createdAt
                        updatedAt
                    }}
                    nextToken
                }}
            }}
            """
            score_items: List[Dict[str, Any]] = []
            next_token: Optional[str] = None
            seen_tokens: set[str] = set()

            while True:
                variables = {
                    "accountId": str(account_id),
                    "compositeCondition": {
                        "between": [
                            {
                                "scorecardId": str(scorecard_id),
                                "scoreId": str(target_score_id),
                                "editedAt": start_date.isoformat(),
                            },
                            {
                                "scorecardId": str(scorecard_id),
                                "scoreId": str(target_score_id),
                                "editedAt": end_date.isoformat(),
                            },
                        ]
                    },
                    "sortDirection": "DESC",
                    "limit": 500,
                    "nextToken": next_token,
                }
                self._log(
                    f"Fetching feedback page (score_id={target_score_id}, "
                    f"nextToken={'set' if next_token else 'none'})"
                )
                response = await asyncio.to_thread(self.api_client.execute, query, variables)
                payload = response.get(query_name) or {}
                items = payload.get("items") or []
                if items:
                    score_items.extend(items)

                next_token = payload.get("nextToken")
                self._log(
                    f"Feedback page returned {len(items)} items for score_id={target_score_id}, "
                    f"nextToken={'set' if next_token else 'none'}"
                )
                if not next_token:
                    break
                if next_token in seen_tokens:
                    self._log(
                        f"Detected repeated pagination token for feedback items (score_id={target_score_id}); "
                        "stopping pagination.",
                        level="WARNING",
                    )
                    break
                seen_tokens.add(next_token)

            return score_items

        if score_id:
            return await _fetch_for_score(str(score_id))

        normalized_score_ids = sorted(
            {
                str(sid).strip()
                for sid in (score_ids or [])
                if str(sid).strip()
            }
        )
        if not normalized_score_ids:
            self._log("No score IDs available for scorecard-wide feedback fetch; skipping feedback query.")
            return []

        semaphore = asyncio.Semaphore(6)

        async def _bounded_fetch(target_score_id: str) -> List[Dict[str, Any]]:
            async with semaphore:
                return await _fetch_for_score(target_score_id)

        self._log(
            f"Fetching scorecard-wide feedback via composite index fanout across {len(normalized_score_ids)} scores."
        )
        grouped_results = await asyncio.gather(*[_bounded_fetch(sid) for sid in normalized_score_ids])

        merged_by_id: Dict[str, Dict[str, Any]] = {}
        for score_items in grouped_results:
            for item in score_items:
                item_id = str(item.get("id") or "").strip()
                if not item_id:
                    continue
                existing = merged_by_id.get(item_id)
                if existing is None:
                    merged_by_id[item_id] = item
                    continue
                existing_ts = self._to_dt(existing.get("editedAt") or existing.get("updatedAt") or existing.get("createdAt"))
                current_ts = self._to_dt(item.get("editedAt") or item.get("updatedAt") or item.get("createdAt"))
                if current_ts >= existing_ts:
                    merged_by_id[item_id] = item

        all_items = list(merged_by_id.values())
        self._log(
            f"Merged scorecard-wide feedback results to {len(all_items)} unique feedback items "
            f"from {sum(len(items) for items in grouped_results)} raw records."
        )
        return all_items

    async def _prepare_rate_dataset(self) -> Dict[str, Any]:
        scorecard_identifier = self._get_param("scorecard")
        if not scorecard_identifier:
            raise ValueError("'scorecard' is required.")

        score_identifier = self._get_param("score") or self._get_param("score_id")
        account_id = self._resolve_account_id()
        start_date, end_date = self._resolve_window()
        scorecard = await self._resolve_scorecard(str(scorecard_identifier))

        resolved_score_id: Optional[str] = None
        resolved_score_name: Optional[str] = None
        if score_identifier:
            score = await self._resolve_score(str(score_identifier), scorecard.id)
            resolved_score_id = score.id
            resolved_score_name = score.name

        self._log(
            f"Fetching score results window for scorecard={scorecard.id} "
            f"score={resolved_score_id or 'all'} start={start_date.isoformat()} end={end_date.isoformat()}"
        )
        raw_score_results = await self._fetch_score_results_window(
            account_id=account_id,
            scorecard_id=scorecard.id,
            start_date=start_date,
            end_date=end_date,
            score_id=resolved_score_id,
        )
        self._log(f"Fetched {len(raw_score_results)} raw score results in window")

        latest_results_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for result in raw_score_results:
            if not self._is_production_result(result):
                continue

            item_id = str(result.get("itemId") or "").strip()
            score_id = str(result.get("scoreId") or "").strip()
            if not item_id or not score_id:
                continue
            if resolved_score_id and score_id != resolved_score_id:
                continue

            key = (item_id, score_id)
            ts = self._to_dt(result.get("updatedAt") or result.get("createdAt"))
            existing = latest_results_by_key.get(key)
            if existing is None or ts >= existing["_timestamp"]:
                latest_results_by_key[key] = {
                    **result,
                    "_timestamp": ts,
                }

        filtered_results = list(latest_results_by_key.values())
        distinct_score_ids = sorted(
            {
                str(result.get("scoreId"))
                for result in filtered_results
                if str(result.get("scoreId") or "").strip()
            }
        )
        self._log(
            f"Fetching feedback items window for scorecard={scorecard.id} "
            f"score={resolved_score_id or 'all'} start={start_date.isoformat()} end={end_date.isoformat()}"
        )
        feedback_items = await self._fetch_feedback_items_window(
            account_id=account_id,
            scorecard_id=scorecard.id,
            start_date=start_date,
            end_date=end_date,
            score_id=resolved_score_id,
            score_ids=None if resolved_score_id else distinct_score_ids,
        )
        self._log(f"Fetched {len(feedback_items)} raw feedback items in window")

        feedback_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
        grouped_feedback: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for item in feedback_items:
            item_id = str(item.get("itemId") or "").strip()
            score_id = str(item.get("scoreId") or "").strip()
            if not item_id or not score_id:
                continue
            key = (item_id, score_id)
            grouped_feedback.setdefault(key, []).append(item)

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

        per_item: Dict[str, Dict[str, Any]] = {}
        corrected_total = 0
        uncorrected_total = 0

        for result in filtered_results:
            item_id = str(result.get("itemId"))
            score_id = str(result.get("scoreId"))
            key = (item_id, score_id)
            feedback = feedback_by_key.get(key)
            feedback_stats = feedback_stats_by_key.get(key) or {"total": 0, "valid": 0}
            predicted_value = str(result.get("value"))
            final_value = feedback.get("finalAnswerValue") if feedback else None

            corrected = final_value is not None and str(final_value) != predicted_value
            if corrected:
                corrected_total += 1
            else:
                uncorrected_total += 1

            item_bucket = per_item.setdefault(
                item_id,
                {
                    "item_id": item_id,
                    "item_external_id": None,
                    "item_created_at": None,
                    "item_updated_at": None,
                    "item_identifiers": None,
                    "total_score_results": 0,
                    "corrected_score_results": 0,
                    "uncorrected_score_results": 0,
                    "feedback_items_total": 0,
                    "feedback_items_valid": 0,
                    "feedback_items_changed": 0,
                    "feedback_scores_with_feedback": set(),
                    "score_results": [],
                },
            )
            item_bucket["total_score_results"] += 1
            if corrected:
                item_bucket["corrected_score_results"] += 1
            else:
                item_bucket["uncorrected_score_results"] += 1
            item_bucket["feedback_items_total"] += int(feedback_stats.get("total") or 0)
            item_bucket["feedback_items_valid"] += int(feedback_stats.get("valid") or 0)
            item_bucket["feedback_items_changed"] += int(feedback_stats.get("changed") or 0)
            if int(feedback_stats.get("total") or 0) > 0:
                item_bucket["feedback_scores_with_feedback"].add(score_id)

            item_obj = result.get("item") if isinstance(result.get("item"), dict) else None
            if item_obj:
                if item_bucket.get("item_external_id") is None:
                    item_bucket["item_external_id"] = item_obj.get("externalId")
                item_created_at = item_obj.get("createdAt")
                if item_created_at and item_bucket.get("item_created_at") is None:
                    item_bucket["item_created_at"] = item_created_at
                item_updated_at = item_obj.get("updatedAt")
                if item_updated_at:
                    existing_item_updated_at = item_bucket.get("item_updated_at")
                    if (
                        existing_item_updated_at is None
                        or self._to_dt(item_updated_at) > self._to_dt(existing_item_updated_at)
                    ):
                        item_bucket["item_updated_at"] = item_updated_at
                if item_bucket.get("item_identifiers") is None:
                    item_identifiers_payload = None
                    item_identifiers_conn = item_obj.get("itemIdentifiers")
                    if isinstance(item_identifiers_conn, dict):
                        item_identifiers_payload = item_identifiers_conn.get("items")
                    if item_identifiers_payload:
                        item_bucket["item_identifiers"] = item_identifiers_payload
                    else:
                        legacy_identifiers = item_obj.get("identifiers")
                        if legacy_identifiers:
                            item_bucket["item_identifiers"] = legacy_identifiers

            item_bucket["score_results"].append(
                {
                    "score_result_id": result.get("id"),
                    "score_id": score_id,
                    "score_name": ((result.get("score") or {}).get("name") if isinstance(result.get("score"), dict) else None),
                    "predicted_value": predicted_value,
                    "feedback_items_total": int(feedback_stats.get("total") or 0),
                    "feedback_items_valid": int(feedback_stats.get("valid") or 0),
                    "feedback_items_changed": int(feedback_stats.get("changed") or 0),
                    "feedback_initial_value": feedback.get("initialAnswerValue") if feedback else None,
                    "feedback_final_value": final_value,
                    "corrected": corrected,
                }
            )

        items = sorted(per_item.values(), key=lambda row: row["item_id"])
        for item in items:
            total = item["total_score_results"]
            item["correction_rate"] = (item["corrected_score_results"] / total) if total else 0.0
            feedback_scores = item.get("feedback_scores_with_feedback") or set()
            if isinstance(feedback_scores, set):
                item["feedback_scores_with_feedback_count"] = len(feedback_scores)
                item["feedback_scores_with_feedback"] = sorted(feedback_scores)
            else:
                item["feedback_scores_with_feedback_count"] = 0
                item["feedback_scores_with_feedback"] = []

        total_score_results = len(filtered_results)
        total_items = len(items)
        total_feedback_items = sum(stats["total"] for stats in feedback_stats_by_key.values()) if feedback_stats_by_key else 0
        total_feedback_items_valid = (
            sum(stats["valid"] for stats in feedback_stats_by_key.values()) if feedback_stats_by_key else 0
        )
        total_feedback_items_changed = (
            sum(stats["changed"] for stats in feedback_stats_by_key.values()) if feedback_stats_by_key else 0
        )
        score_results_with_feedback = (
            sum(1 for stats in feedback_stats_by_key.values() if int(stats.get("total") or 0) > 0)
            if feedback_stats_by_key
            else 0
        )

        return {
            "scope": "single_score" if resolved_score_id else "scorecard_all_scores",
            "scorecard_id": scorecard.id,
            "scorecard_name": scorecard.name,
            "score_id": resolved_score_id,
            "score_name": resolved_score_name,
            "distinct_score_ids": distinct_score_ids,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "totals": {
                "total_items": total_items,
                "total_score_results": total_score_results,
                "distinct_score_count": len(distinct_score_ids),
                "corrected_score_results": corrected_total,
                "uncorrected_score_results": uncorrected_total,
                "corpus_correction_rate": (corrected_total / total_score_results) if total_score_results else 0.0,
                "feedback_items_total": total_feedback_items,
                "feedback_items_valid": total_feedback_items_valid,
                "feedback_items_changed": total_feedback_items_changed,
                "score_results_with_feedback": score_results_with_feedback,
            },
            "items": items,
            "raw_counts": {
                "raw_score_results_scanned": len(raw_score_results),
                "raw_feedback_items_scanned": len(feedback_items),
            },
        }
