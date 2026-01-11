from typing import Any, Dict, Optional, Tuple, List
import logging
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import asyncio

from plexus.dashboard.api.models.scorecard import Scorecard

from .base import BaseReportBlock
from . import feedback_utils

logger = logging.getLogger(__name__)


class CostAnalysis(BaseReportBlock):
    """
    ReportBlock: Cost analysis over ScoreResults with summary or detail outputs.

    Config:
      - scorecard (optional): id/key/name/externalId (any identifier)
          - Use "all" to analyze all scorecards in the account
      - score (optional): id/key/name/externalId (resolved within scorecard when provided)
      - hours (int, default 1): preferred time window
      - days (int, default 0): used when hours not provided
      - start_date (str, optional): YYYY-MM-DD or ISO8601 (overrides hours/days)
      - end_date (str, optional): YYYY-MM-DD or ISO8601 (overrides hours/days)
      - limit (int, optional): max cost-bearing ScoreResults to include
      - group_by (str|None): None | 'scorecard' | 'score' | 'scorecard_score'
      - mode (str): 'summary' (default) or 'detail'
      - breakdown (bool): when summary mode, include grouped summaries
    """

    DEFAULT_NAME = "Cost Analysis"
    DEFAULT_DESCRIPTION = "ScoreResult cost metrics and breakdowns"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        output_data: Optional[Dict[str, Any]] = None
        try:
            self._log("Starting CostAnalysis block generation.")
            cfg = self.config or {}

            # Parameters with defaults
            hours = self._parse_optional_int(cfg, "hours", default=1)
            days = int(cfg.get("days", 0) or 0)
            scorecard_identifier = cfg.get("scorecard")
            score_identifier = cfg.get("score")
            group_by = cfg.get("group_by")
            mode = (cfg.get("mode") or "summary").lower()
            breakdown = bool(cfg.get("breakdown", False))
            limit = self._parse_optional_int(cfg, "limit", default=None)
            concurrency = self._parse_optional_int(cfg, "concurrency", default=4)
            start_time, end_time = self._resolve_time_window(
                cfg, hours=hours, days=days
            )

            # Create Analyzer
            from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

            client = self.api_client

            # Special mode: all scorecards in the account
            if scorecard_identifier and str(scorecard_identifier).lower() == "all":
                return await self._generate_all_scorecards_cost_analysis(
                    client=client,
                    analyzer_cls=ScoreResultCostAnalyzer,
                    hours=hours,
                    days=days,
                    start_time=start_time,
                    end_time=end_time,
                    max_items=limit,
                    concurrency=concurrency,
                )

            # Resolve scorecard any-identifier to ID and name (optional)
            resolved_scorecard_id = None
            resolved_scorecard_name = None
            if scorecard_identifier:
                try:
                    # Reuse CLI resolver for consistency if available
                    from plexus.cli.scorecard.scorecards import (
                        resolve_scorecard_identifier,
                    )

                    resolved_scorecard_id = resolve_scorecard_identifier(
                        client, str(scorecard_identifier)
                    )
                except Exception as e:
                    self._log(f"Resolver error for scorecard: {e}", level="WARNING")
                    resolved_scorecard_id = None

                if not resolved_scorecard_id:
                    # Fallback: treat as externalId via Scorecard API model
                    try:
                        sc_obj = await self._to_thread(
                            Scorecard.get_by_external_id,
                            external_id=str(scorecard_identifier),
                            client=client,
                        )
                        if sc_obj:
                            resolved_scorecard_id = sc_obj.id
                            resolved_scorecard_name = sc_obj.name
                    except Exception as e:
                        self._log(
                            f"Fallback scorecard externalId lookup failed: {e}",
                            level="WARNING",
                        )
                else:
                    # Fetch name
                    try:
                        sc_obj = await self._to_thread(
                            Scorecard.get_by_id, id=resolved_scorecard_id, client=client
                        )
                        if sc_obj:
                            resolved_scorecard_name = sc_obj.name
                    except Exception:
                        pass

                if not resolved_scorecard_id:
                    return {
                        "error": f"Scorecard not found: {scorecard_identifier}"
                    }, "\n".join(self.log_messages)

            # Resolve score any-identifier within scorecard
            resolved_score_id = None
            if resolved_scorecard_id and score_identifier:
                # Query scorecard scores and match by various keys
                query = f"""
                query GetScorecardForCost {{
                  getScorecard(id: "{resolved_scorecard_id}") {{
                    sections {{
                      items {{
                        scores {{
                          items {{ id name key externalId }}
                        }}
                      }}
                    }}
                  }}
                }}
                """
                try:
                    resp = await self._to_thread(client.execute, query)
                    sc_data = resp.get("getScorecard") or {}
                    for section in (sc_data.get("sections", {}) or {}).get(
                        "items", []
                    ) or []:
                        for s in (section.get("scores", {}) or {}).get(
                            "items", []
                        ) or []:
                            name = s.get("name") or ""
                            if (
                                s.get("id") == score_identifier
                                or name.lower() == str(score_identifier).lower()
                                or s.get("key") == score_identifier
                                or s.get("externalId") == score_identifier
                                or str(score_identifier).lower() in name.lower()
                            ):
                                resolved_score_id = s.get("id")
                                break
                        if resolved_score_id:
                            break
                except Exception as e:
                    self._log(f"Score resolution error: {e}", level="WARNING")
                if not resolved_score_id:
                    return {
                        "error": f"Score not found in scorecard {scorecard_identifier}: {score_identifier}"
                    }, "\n".join(self.log_messages)

            account_id = self._resolve_account_id()

            analyzer = ScoreResultCostAnalyzer(
                client=client,
                account_id=account_id
                or "",  # accountId required for account-level queries
                days=days,
                hours=hours,
                start_time=start_time,
                end_time=end_time,
                max_items=limit,
                scorecard_id=resolved_scorecard_id or scorecard_identifier,
                score_id=resolved_score_id or score_identifier,
            )

            # Choose a sensible default grouping if breakdown requested but no group_by provided
            effective_group_by = group_by
            if breakdown and not effective_group_by:
                if (resolved_scorecard_id or scorecard_identifier) and not (
                    resolved_score_id or score_identifier
                ):
                    # At scorecard level → default to per-score breakdown
                    effective_group_by = "score"
                elif not (resolved_scorecard_id or scorecard_identifier) and not (
                    resolved_score_id or score_identifier
                ):
                    # Global level → default to per-scorecard breakdown
                    effective_group_by = "scorecard"
                else:
                    # Already at most-granular level → no further breakdown
                    effective_group_by = None

            analysis = analyzer.analyze(group_by=effective_group_by)

            def pick_summary(head: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "average_cost": head.get("average_cost"),
                    "count": head.get("count"),
                    "total_cost": head.get("total_cost"),
                    "average_calls": head.get("average_calls"),
                }

            if mode == "summary":
                result: Dict[str, Any] = {
                    "block_title": self.DEFAULT_NAME,
                    "block_description": self.DEFAULT_DESCRIPTION,
                    "scorecardName": resolved_scorecard_name,
                    "summary": pick_summary(analysis.get("headline", {})),
                    "itemAnalysis": self._compute_item_analysis(
                        results=analyzer.list_raw(),
                        total_cost_str=(analysis.get("headline") or {}).get(
                            "total_cost"
                        ),
                        total_calls_str=(analysis.get("headline") or {}).get(
                            "total_calls"
                        ),
                    ),
                    "window": {
                        "hours": analysis.get("hours"),
                        "days": analysis.get("days"),
                    },
                    "filters": analysis.get("filters"),
                }

                if breakdown and effective_group_by:
                    name_index = analysis.get("scoreNameIndex", {})
                    groups_out = []
                    for g in analysis.get("groups", []):
                        label = dict(g.get("group", {}))
                        if "scoreId" in label:
                            sid = label["scoreId"]
                            if sid in name_index:
                                label["scoreName"] = name_index[sid]
                        groups_out.append(
                            {
                                "group": label,
                                **pick_summary(g),
                                **self._pick_distribution_numbers(g),
                            }
                        )

                    # Sort by highest average cost
                    def sort_key_cost(item):
                        try:
                            return Decimal(item.get("average_cost") or "0")
                        except Exception:
                            return Decimal("0")

                    groups_out.sort(key=sort_key_cost, reverse=True)
                    result["groups"] = groups_out

                output_data = result
            else:
                # detail mode: return full analysis, include scorecardName
                detail = {**analysis}
                detail["block_title"] = self.DEFAULT_NAME
                detail["block_description"] = self.DEFAULT_DESCRIPTION
                if resolved_scorecard_name:
                    detail["scorecardName"] = resolved_scorecard_name
                output_data = detail

            summary_log = (
                f"Cost analysis completed (mode={mode}, breakdown={breakdown})."
            )
            detailed_log = "\n".join(self.log_messages) if self.log_messages else ""
            return output_data, summary_log + (
                "\n" + detailed_log if detailed_log else ""
            )

        except Exception as e:
            logger.exception(f"Error in CostAnalysis ReportBlock: {e}")
            return {"error": str(e)}, "\n".join(self.log_messages)

    def _resolve_account_id(self) -> Optional[str]:
        account_id = self.params.get("account_id")
        if not account_id and getattr(self.api_client, "context", None):
            account_id = getattr(self.api_client.context, "account_id", None)
        return str(account_id) if account_id else None

    def _parse_optional_int(
        self, cfg: Dict[str, Any], key: str, default: Optional[int]
    ) -> Optional[int]:
        """
        Allows explicit null in YAML to mean None.
        - missing key -> default
        - key present but null -> None
        - 0 -> treated as default (to avoid accidental 0h windows)
        """
        if key in cfg and cfg.get(key) is None:
            return None
        raw = cfg.get(key, default)
        if raw is None:
            return None
        try:
            val = int(raw)
        except Exception:
            return default
        if val <= 0:
            return default
        return val

    def _resolve_time_window(
        self,
        cfg: Dict[str, Any],
        *,
        hours: Optional[int],
        days: int,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        start_date_str = cfg.get("start_date")
        end_date_str = cfg.get("end_date")
        if not start_date_str and not end_date_str:
            return None, None

        def parse_dt(value: str, *, is_end: bool) -> datetime:
            # Accept YYYY-MM-DD or full ISO strings.
            value = str(value).strip()
            dt: datetime
            try:
                dt = datetime.fromisoformat(value)
            except Exception:
                dt = datetime.strptime(value, "%Y-%m-%d")
                if is_end:
                    dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                else:
                    dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        end_time = (
            parse_dt(end_date_str, is_end=True)
            if end_date_str
            else datetime.now(timezone.utc)
        )
        if start_date_str:
            start_time = parse_dt(start_date_str, is_end=False)
        else:
            # If only end_date provided, infer start from hours/days.
            if hours is not None:
                start_time = end_time - timedelta(hours=max(1, int(hours)))
            else:
                start_time = end_time - timedelta(days=max(1, int(days)))
        return start_time, end_time

    def _compute_item_analysis(
        self,
        *,
        results: List[Dict[str, Any]],
        total_cost_str: Optional[str],
        total_calls_str: Optional[str],
    ) -> Dict[str, Any]:
        from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

        item_ids = set()
        for sr in results:
            cost = ScoreResultCostAnalyzer.extract_cost(sr)
            if cost:
                item_id = sr.get("itemId")
                if item_id:
                    item_ids.add(str(item_id))

        item_count = len(item_ids)
        total_cost = self._safe_decimal(total_cost_str)
        total_calls = self._safe_decimal(total_calls_str)
        avg_cost = (total_cost / Decimal(item_count)) if item_count else Decimal("0")
        avg_calls = (total_calls / Decimal(item_count)) if item_count else Decimal("0")

        return {
            "count": item_count,
            "total_cost": float(total_cost),
            "average_cost": float(avg_cost),
            "average_calls": float(avg_calls),
        }

    def _pick_distribution_numbers(self, group_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Decimal-ish string stats to numbers for charts.
        CostAnalysisDisplay expects numeric min/q1/median/q3/max values.
        """
        return {
            "min_cost": self._safe_float(group_stats.get("min_cost")),
            "q1_cost": self._safe_float(group_stats.get("q1_cost")),
            "median_cost": self._safe_float(group_stats.get("median_cost")),
            "q3_cost": self._safe_float(group_stats.get("q3_cost")),
            "max_cost": self._safe_float(group_stats.get("max_cost")),
        }

    def _safe_decimal(self, value: Any) -> Decimal:
        try:
            if value is None:
                return Decimal("0")
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _safe_float(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(Decimal(str(value)))
        except Exception:
            return 0.0

    async def _generate_all_scorecards_cost_analysis(
        self,
        *,
        client: Any,
        analyzer_cls: Any,
        hours: Optional[int],
        days: int,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        max_items: Optional[int],
        concurrency: Optional[int],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self._log("Starting CostAnalysis all-scorecards mode")

        account_id = self._resolve_account_id()
        if not account_id:
            msg = "Could not determine account_id for all-scorecards cost analysis"
            self._log(f"ERROR: {msg}", level="ERROR")
            return {
                "mode": "all_scorecards",
                "error": msg,
                "scorecards": [],
            }, "\n".join(self.log_messages)

        scorecards = await feedback_utils.fetch_all_scorecards(client, account_id)
        if not scorecards:
            msg = "No scorecards found for this account"
            self._log(f"ERROR: {msg}", level="ERROR")
            return {
                "mode": "all_scorecards",
                "error": msg,
                "scorecards": [],
            }, "\n".join(self.log_messages)

        effective_limit = max_items
        if effective_limit is None:
            self._log(
                "No per-scorecard limit set; scanning the full time range for each scorecard (may take a while)"
            )
        else:
            self._log(
                f"Using up to {effective_limit} cost-bearing ScoreResults per scorecard"
            )

        effective_concurrency = 4
        if concurrency is not None:
            try:
                effective_concurrency = max(1, min(int(concurrency), 16))
            except Exception:
                effective_concurrency = 4
        self._log(f"Parallelism: up to {effective_concurrency} scorecards at a time")

        def pick_summary(head: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "average_cost": head.get("average_cost"),
                "count": head.get("count"),
                "total_cost": head.get("total_cost"),
                "average_calls": head.get("average_calls"),
            }

        sem = asyncio.Semaphore(effective_concurrency)
        total = len(scorecards)

        async def analyze_one(idx: int, sc: Any) -> Tuple[int, Dict[str, Any], str]:
            sc_id = str(sc.id)
            async with sem:
                analyzer = analyzer_cls(
                    client=client,
                    account_id=account_id,
                    days=days,
                    hours=hours,
                    start_time=start_time,
                    end_time=end_time,
                    max_items=effective_limit,
                    scorecard_id=sc_id,
                )

                analysis = await self._to_thread(analyzer.analyze, group_by="score")
                headline = analysis.get("headline", {}) or {}
                summary = pick_summary(headline)
                item_analysis = self._compute_item_analysis(
                    results=analyzer.list_raw(),
                    total_cost_str=headline.get("total_cost"),
                    total_calls_str=headline.get("total_calls"),
                )

                name_index = analysis.get("scoreNameIndex", {}) or {}
                groups_out: List[Dict[str, Any]] = []
                for g in analysis.get("groups", []) or []:
                    grp = dict(g.get("group", {}) or {})
                    sid = grp.get("scoreId")
                    groups_out.append(
                        {
                            "group": {"scoreId": sid, "scoreName": name_index.get(sid)},
                            **pick_summary(g),
                            **self._pick_distribution_numbers(g),
                        }
                    )

                groups_out.sort(
                    key=lambda x: self._safe_decimal(x.get("average_cost")),
                    reverse=True,
                )

                entry = {
                    "scorecard_id": sc_id,
                    "scorecard_name": sc.name,
                    "scorecard_external_id": getattr(sc, "externalId", None),
                    "block_title": self.DEFAULT_NAME,
                    "block_description": self.DEFAULT_DESCRIPTION,
                    "summary": summary,
                    "itemAnalysis": item_analysis,
                    "groups": groups_out,
                    "window": {"hours": hours, "days": days},
                    "filters": {"scorecardId": sc_id},
                }

                msg = (
                    f"[{idx}/{total}] Completed '{sc.name}': total_cost={summary.get('total_cost')}, "
                    f"avg_item_cost={item_analysis.get('average_cost')}, items={item_analysis.get('count')}, scores={len(groups_out)}"
                )
                return idx, entry, msg

        tasks: List["asyncio.Task[Any]"] = []
        for idx, sc in enumerate(scorecards, 1):
            sc_id = str(sc.id)
            self._log(
                f"=== [{idx}/{total}] Queued '{sc.name}' (ID: {sc_id}, External ID: {getattr(sc, 'externalId', None)}) ==="
            )
            tasks.append(asyncio.create_task(analyze_one(idx, sc)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        scorecard_entries: List[Dict[str, Any]] = []
        for r in sorted(
            results, key=lambda x: x[0] if isinstance(x, tuple) and x else 10**9
        ):
            if isinstance(r, Exception):
                self._log(f"ERROR: scorecard cost analysis failed: {r}", level="ERROR")
                continue
            idx, entry, msg = r
            scorecard_entries.append(entry)
            self._log(msg)

        # Default order: highest total cost first (scorecards with no data fall to end)
        scorecard_entries.sort(
            key=lambda e: self._safe_decimal(
                (e.get("summary") or {}).get("total_cost")
            ),
            reverse=True,
        )
        for i, entry in enumerate(scorecard_entries, 1):
            entry["rank"] = i

        # Compute an effective date range for display
        if start_time is None and end_time is None:
            end_time_eff = datetime.now(timezone.utc)
            if hours is not None:
                start_time_eff = end_time_eff - timedelta(hours=max(1, int(hours)))
            else:
                start_time_eff = end_time_eff - timedelta(days=max(1, int(days)))
        else:
            start_time_eff = start_time or datetime.now(timezone.utc)
            end_time_eff = end_time or datetime.now(timezone.utc)

        with_data = sum(
            1
            for e in scorecard_entries
            if int((e.get("summary") or {}).get("count") or 0) > 0
        )
        without_data = len(scorecard_entries) - with_data

        output_data = {
            "mode": "all_scorecards",
            "total_scorecards_analyzed": len(scorecard_entries),
            "total_scorecards_with_data": with_data,
            "total_scorecards_without_data": without_data,
            "date_range": {
                "start": start_time_eff.isoformat(),
                "end": end_time_eff.isoformat(),
            },
            "window": {"hours": hours, "days": days},
            "limit": effective_limit,
            "scorecards": scorecard_entries,
            "message": "Analyzed costs across all scorecards (sorted by total cost desc by default).",
            "block_title": f"{self.DEFAULT_NAME} - All Scorecards",
            "block_description": f"{self.DEFAULT_DESCRIPTION} across all scorecards in the account",
        }

        return output_data, "\n".join(self.log_messages)

    async def _to_thread(self, fn, *args, **kwargs):
        import asyncio

        return await asyncio.to_thread(fn, *args, **kwargs)

    def _log(self, message: str, level: str = "INFO"):
        if level == "DEBUG":
            logger.debug(f"[CostAnalysis] {message}")
        else:
            getattr(logger, level.lower(), logger.info)(f"[CostAnalysis] {message}")
            self.log_messages.append(message)


# Example of how this block might be configured in a ReportConfiguration:
"""
```block name="All Costs"
class: CostAnalysis
scorecard: all
hours: 24
# OR use an explicit window:
# start_date: "2025-01-01"
# end_date: "2025-01-07"
```
"""
