"""
Core cost analysis for ScoreResults.

This module provides a reusable analyzer that loads ScoreResult records over a
time range (default 7 days) using GSIs and computes aggregate cost metrics.

It is designed to be shared by CLI commands, MCP tools, and ReportBlocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json


def _parse_decimal(value: Any) -> Decimal:
    try:
        if isinstance(value, Decimal):
            return value
        if value is None:
            return Decimal("0")
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _ensure_dict(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _extract_cost(sr: Dict[str, Any]) -> Dict[str, Any]:
    # Prefer explicit top-level cost if present; otherwise metadata.cost
    cost_val = sr.get("cost")
    cost_dict = _ensure_dict(cost_val)
    if not cost_dict:
        meta = _ensure_dict(sr.get("metadata")) or {}
        cost_dict = _ensure_dict(meta.get("cost")) or {}
    return cost_dict


def _extract_tokens(cost: Dict[str, Any]) -> Tuple[int, int, int]:
    return (
        int(cost.get("prompt_tokens", 0) or 0),
        int(cost.get("completion_tokens", 0) or 0),
        int(cost.get("cached_tokens", 0) or 0),
    )


@dataclass
class CostGroupTotals:
    count: int = 0
    total_cost: Decimal = Decimal("0")
    input_cost: Decimal = Decimal("0")
    output_cost: Decimal = Decimal("0")
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    llm_calls: int = 0

    def add(self, cost: Dict[str, Any]) -> None:
        self.count += 1
        self.total_cost += _parse_decimal(cost.get("total_cost"))
        self.input_cost += _parse_decimal(cost.get("input_cost"))
        self.output_cost += _parse_decimal(cost.get("output_cost"))
        pt, ct, cct = _extract_tokens(cost)
        self.prompt_tokens += pt
        self.completion_tokens += ct
        self.cached_tokens += cct
        self.llm_calls += int(cost.get("llm_calls", 0) or 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_tokens": self.cached_tokens,
            "llm_calls": self.llm_calls,
            "input_cost": str(self.input_cost),
            "output_cost": str(self.output_cost),
            "total_cost": str(self.total_cost),
        }


class ScoreResultCostAnalyzer:
    """
    Loads ScoreResults for a time range and computes cost aggregates.

    Filters:
      - account_id (required in practice; resolve via CLI utils)
      - optional scorecard_id
      - optional score_id
      - days (default 7)
    """

    # Single-entry module-level cache
    _LAST_CACHE_KEY: Optional[Tuple[str, int, Optional[str], Optional[str]]] = None
    _LAST_CACHE_RESULTS: Optional[List[Dict[str, Any]]] = None

    def __init__(
        self,
        client: Any,
        account_id: str,
        days: int = 7,
        hours: Optional[int] = 1,
        scorecard_id: Optional[str] = None,
        score_id: Optional[str] = None,
    ) -> None:
        self.client = client
        self.account_id = account_id
        self.days = days
        self.hours = hours
        self.scorecard_id = scorecard_id
        self.score_id = score_id
        self._loaded: bool = False
        self._results: List[Dict[str, Any]] = []

    @classmethod
    def clear_cache(cls) -> None:
        cls._LAST_CACHE_KEY = None
        cls._LAST_CACHE_RESULTS = None

    @property
    def time_window(self) -> Tuple[datetime, datetime]:
        end_time = datetime.now(timezone.utc)
        if self.hours is not None:
            start_time = end_time - timedelta(hours=max(1, int(self.hours)))
        else:
            start_time = end_time - timedelta(days=max(1, int(self.days)))
        return start_time, end_time

    def _query_name_and_body(self) -> Tuple[str, str, Dict[str, Any]]:
        start_time, end_time = self.time_window
        variables: Dict[str, Any] = {
            "startTime": start_time.isoformat(),
            "endTime": end_time.isoformat(),
            "limit": 1000,
        }

        # Choose best GSI depending on filters
        if self.score_id:
            query_name = "listScoreResultByScoreIdAndUpdatedAt"
            query = f"""
            query GetScoreResultsByScore($scoreId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {{
              {query_name}(
                scoreId: $scoreId,
                updatedAt: {{ between: [$startTime, $endTime] }},
                nextToken: $nextToken,
                limit: $limit
              ) {{
                items {{
                  id value itemId accountId scorecardId scoreId code type createdAt updatedAt
                  score {{ id name }}
                  cost
                  metadata
                }}
                nextToken
              }}
            }}
            """
            variables["scoreId"] = self.score_id
            return query_name, query, variables

        if self.scorecard_id:
            query_name = "listScoreResultByScorecardIdAndUpdatedAt"
            query = f"""
            query GetScoreResultsByScorecard($scorecardId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {{
              {query_name}(
                scorecardId: $scorecardId,
                updatedAt: {{ between: [$startTime, $endTime] }},
                nextToken: $nextToken,
                limit: $limit
              ) {{
                items {{
                  id value itemId accountId scorecardId scoreId code type createdAt updatedAt
                  score {{ id name }}
                  cost
                  metadata
                }}
                nextToken
              }}
            }}
            """
            variables["scorecardId"] = self.scorecard_id
            return query_name, query, variables

        # Default: account + updatedAt window
        query_name = "listScoreResultByAccountIdAndUpdatedAt"
        query = f"""
        query GetScoreResultsByAccount($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {{
          {query_name}(
            accountId: $accountId,
            updatedAt: {{ between: [$startTime, $endTime] }},
            nextToken: $nextToken,
            limit: $limit
          ) {{
            items {{
              id value itemId accountId scorecardId scoreId code type createdAt updatedAt
              score {{ id name }}
              cost
              metadata
            }}
            nextToken
          }}
        }}
        """
        variables["accountId"] = self.account_id
        return query_name, query, variables

    def load(self) -> None:
        """Load ScoreResults into memory using GSI-backed pagination with single-entry cache."""
        # Check cache first
        cache_key = (self.account_id, int(self.days), self.scorecard_id, self.score_id, int(self.hours) if self.hours is not None else None)
        if (
            ScoreResultCostAnalyzer._LAST_CACHE_KEY == cache_key
            and ScoreResultCostAnalyzer._LAST_CACHE_RESULTS is not None
        ):
            self._results = list(ScoreResultCostAnalyzer._LAST_CACHE_RESULTS)
            self._loaded = True
            return

        _, query, variables = self._query_name_and_body()
        next_token: Optional[str] = None
        results: List[Dict[str, Any]] = []

        page = 0
        while True:
            vars_with_token = dict(variables)
            if next_token:
                vars_with_token["nextToken"] = next_token
            data = self.client.execute(query, vars_with_token)
            # Pull the one field we asked for
            top_key = next(k for k in data.keys() if k.startswith("listScoreResult"))
            page_items = data.get(top_key, {}).get("items", [])
            results.extend(page_items)
            next_token = data.get(top_key, {}).get("nextToken")
            page += 1
            if not next_token:
                break

        self._results = results
        self._loaded = True
        # Update cache
        ScoreResultCostAnalyzer._LAST_CACHE_KEY = cache_key
        ScoreResultCostAnalyzer._LAST_CACHE_RESULTS = list(results)

    def list_raw(self) -> List[Dict[str, Any]]:
        if not self._loaded:
            self.load()
        return self._results

    def summarize(self) -> Dict[str, Any]:
        if not self._loaded:
            self.load()

        groups: Dict[Tuple[str, str], CostGroupTotals] = {}
        names: Dict[Tuple[str, str], str] = {}
        totals = CostGroupTotals()

        for sr in self._results:
            cost = _extract_cost(sr)
            if not cost:
                continue
            key = (str(sr.get("scorecardId")), str(sr.get("scoreId")))
            if key not in groups:
                groups[key] = CostGroupTotals()
            groups[key].add(cost)
            totals.add(cost)
            # Capture score name when available
            score_obj = sr.get("score") or {}
            score_name = score_obj.get("name")
            if score_name:
                names[key] = score_name

        group_list: List[Dict[str, Any]] = []
        for (scorecard_id, score_id), agg in groups.items():
            group_list.append({
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "scoreName": names.get((scorecard_id, score_id)),
                **agg.to_dict(),
            })

        return {
            "accountId": self.account_id,
            "days": self.days,
            "hours": self.hours,
            "filters": {"scorecardId": self.scorecard_id, "scoreId": self.score_id},
            "totals": totals.to_dict(),
            "groups": sorted(group_list, key=lambda g: (g["scorecardId"], g["scoreId"]))
        }

    # ----------------------
    # Statistical aggregation
    # ----------------------
    @staticmethod
    def _median(values: List[Decimal]) -> Decimal:
        if not values:
            return Decimal("0")
        n = len(values)
        s = sorted(values)
        mid = n // 2
        if n % 2 == 1:
            return s[mid]
        return (s[mid - 1] + s[mid]) / Decimal("2")

    @staticmethod
    def _percentile(values: List[Decimal], p: float) -> Decimal:
        if not values:
            return Decimal("0")
        s = sorted(values)
        k = (len(s) - 1) * p
        f = int(k)
        c = f + 1
        if c >= len(s):
            return s[-1]
        d0 = s[f] * Decimal(c - k)
        d1 = s[c] * Decimal(k - f)
        return d0 + d1

    @staticmethod
    def _stddev(values: List[Decimal]) -> Decimal:
        if not values:
            return Decimal("0")
        n = len(values)
        if n == 1:
            return Decimal("0")
        mean = sum(values, start=Decimal("0")) / Decimal(n)
        var = sum((x - mean) * (x - mean) for x in values) / Decimal(n)  # population stddev
        # Avoid negative variance from floating Decimal oddities
        if var < 0:
            var = Decimal("0")
        # sqrt for Decimal: use exponent ** 0.5 via float fallback for stability on typical magnitudes
        try:
            return var.sqrt()  # Decimal sqrt available if context precision sufficient
        except Exception:
            import math
            return _parse_decimal(math.sqrt(float(var)))

    def analyze(self, group_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute headline and box-plot friendly metrics.

        group_by:
          - None: overall only
          - "scorecard": per scorecardId
          - "score": per scoreId
          - "scorecard_score": (scorecardId, scoreId)
        """
        if not self._loaded:
            self.load()

        # Collect values
        overall_values: List[Decimal] = []  # total_cost per result
        overall_calls: List[Decimal] = []   # llm_calls per result
        by_scorecard: Dict[str, List[Decimal]] = {}
        by_score: Dict[str, List[Decimal]] = {}
        by_pair: Dict[Tuple[str, str], List[Decimal]] = {}
        by_scorecard_calls: Dict[str, List[Decimal]] = {}
        by_score_calls: Dict[str, List[Decimal]] = {}
        by_pair_calls: Dict[Tuple[str, str], List[Decimal]] = {}
        score_name_index: Dict[str, str] = {}

        for sr in self._results:
            cost = _extract_cost(sr)
            if not cost:
                continue
            total = _parse_decimal(cost.get("total_cost"))
            calls = _parse_decimal(cost.get("llm_calls", 0))
            overall_values.append(total)
            overall_calls.append(calls)

            sc_id = str(sr.get("scorecardId"))
            s_id = str(sr.get("scoreId"))
            # Record score name when available
            try:
                score_obj = sr.get("score") or {}
                s_name = score_obj.get("name")
                if s_id and s_name and s_id not in score_name_index:
                    score_name_index[s_id] = s_name
            except Exception:
                pass
            if group_by in ("scorecard", "scorecard_score"):
                by_scorecard.setdefault(sc_id, []).append(total)
                by_scorecard_calls.setdefault(sc_id, []).append(calls)
            if group_by in ("score", "scorecard_score"):
                by_score.setdefault(s_id, []).append(total)
                by_score_calls.setdefault(s_id, []).append(calls)
            if group_by == "scorecard_score":
                by_pair.setdefault((sc_id, s_id), []).append(total)
                by_pair_calls.setdefault((sc_id, s_id), []).append(calls)

        def build_stats(values: List[Decimal]) -> Dict[str, Any]:
            n = len(values)
            total_cost = sum(values, start=Decimal("0"))
            avg = (total_cost / Decimal(n)) if n else Decimal("0")
            std = self._stddev(values)
            med = self._median(values)
            q1 = self._percentile(values, 0.25)
            q3 = self._percentile(values, 0.75)
            iqr = q3 - q1
            vmin = min(values) if values else Decimal("0")
            vmax = max(values) if values else Decimal("0")
            return {
                "count": n,
                "total_cost": str(total_cost),
                "average_cost": str(avg),
                "stddev_cost": str(std),
                "median_cost": str(med),
                "q1_cost": str(q1),
                "q3_cost": str(q3),
                "iqr_cost": str(iqr),
                "min_cost": str(vmin),
                "max_cost": str(vmax),
            }

        headline = build_stats(overall_values)
        # Add calls distribution metrics with _calls suffix
        def build_calls(values: List[Decimal]) -> Dict[str, Any]:
            n = len(values)
            total = sum(values, start=Decimal("0"))
            avg = (total / Decimal(n)) if n else Decimal("0")
            std = self._stddev(values)
            med = self._median(values)
            q1 = self._percentile(values, 0.25)
            q3 = self._percentile(values, 0.75)
            iqr = q3 - q1
            vmin = min(values) if values else Decimal("0")
            vmax = max(values) if values else Decimal("0")
            return {
                "total_calls": str(total),
                "average_calls": str(avg),
                "stddev_calls": str(std),
                "median_calls": str(med),
                "q1_calls": str(q1),
                "q3_calls": str(q3),
                "iqr_calls": str(iqr),
                "min_calls": str(vmin),
                "max_calls": str(vmax),
            }

        headline.update(build_calls(overall_calls))

        groups: List[Dict[str, Any]] = []
        if group_by == "scorecard":
            for sc_id, vals in by_scorecard.items():
                entry = {"group": {"scorecardId": sc_id}}
                entry.update(build_stats(vals))
                entry.update(build_calls(by_scorecard_calls.get(sc_id, [])))
                groups.append(entry)
        elif group_by == "score":
            for s_id, vals in by_score.items():
                entry = {"group": {"scoreId": s_id}}
                entry.update(build_stats(vals))
                entry.update(build_calls(by_score_calls.get(s_id, [])))
                groups.append(entry)
        elif group_by == "scorecard_score":
            for (sc_id, s_id), vals in by_pair.items():
                entry = {"group": {"scorecardId": sc_id, "scoreId": s_id}}
                entry.update(build_stats(vals))
                entry.update(build_calls(by_pair_calls.get((sc_id, s_id), [])))
                groups.append(entry)

        return {
            "accountId": self.account_id,
            "days": self.days,
            "hours": self.hours,
            "filters": {"scorecardId": self.scorecard_id, "scoreId": self.score_id},
            "headline": headline,
            "groups": groups,
            "scoreNameIndex": score_name_index,
        }


