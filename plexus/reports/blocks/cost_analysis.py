from typing import Any, Dict, Optional, Tuple, List
import logging
from decimal import Decimal

from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.report_block import ReportBlock

from .base import BaseReportBlock

logger = logging.getLogger(__name__)


class CostAnalysis(BaseReportBlock):
    """
    ReportBlock: Cost analysis over ScoreResults with summary or detail outputs.

    Config:
      - scorecard (optional): id/key/name/externalId (any identifier)
      - score (optional): id/key/name/externalId (resolved within scorecard when provided)
      - hours (int, default 1): preferred time window
      - days (int, default 0): used when hours not provided
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
            hours = int(cfg.get("hours", 1) or 1)
            days = int(cfg.get("days", 0) or 0)
            scorecard_identifier = cfg.get("scorecard")
            score_identifier = cfg.get("score")
            group_by = cfg.get("group_by")
            mode = (cfg.get("mode") or "summary").lower()
            breakdown = bool(cfg.get("breakdown", False))

            # Create Analyzer
            from plexus.costs.cost_analysis import ScoreResultCostAnalyzer

            client = self.api_client

            # Resolve scorecard any-identifier to ID and name (optional)
            resolved_scorecard_id = None
            resolved_scorecard_name = None
            if scorecard_identifier:
                try:
                    # Reuse CLI resolver for consistency if available
                    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
                    resolved_scorecard_id = resolve_scorecard_identifier(client, str(scorecard_identifier))
                except Exception as e:
                    self._log(f"Resolver error for scorecard: {e}", level="WARNING")
                    resolved_scorecard_id = None

                if not resolved_scorecard_id:
                    # Fallback: treat as externalId via Scorecard API model
                    try:
                        sc_obj = await self._to_thread(Scorecard.get_by_external_id, external_id=str(scorecard_identifier), client=client)
                        if sc_obj:
                            resolved_scorecard_id = sc_obj.id
                            resolved_scorecard_name = sc_obj.name
                    except Exception as e:
                        self._log(f"Fallback scorecard externalId lookup failed: {e}", level="WARNING")
                else:
                    # Fetch name
                    try:
                        sc_obj = await self._to_thread(Scorecard.get_by_id, id=resolved_scorecard_id, client=client)
                        if sc_obj:
                            resolved_scorecard_name = sc_obj.name
                    except Exception:
                        pass

                if not resolved_scorecard_id:
                    return {"error": f"Scorecard not found: {scorecard_identifier}"}, "\n".join(self.log_messages)

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
                    sc_data = resp.get('getScorecard') or {}
                    for section in (sc_data.get('sections', {}) or {}).get('items', []) or []:
                        for s in (section.get('scores', {}) or {}).get('items', []) or []:
                            name = s.get('name') or ''
                            if (
                                s.get('id') == score_identifier or
                                name.lower() == str(score_identifier).lower() or
                                s.get('key') == score_identifier or
                                s.get('externalId') == score_identifier or
                                str(score_identifier).lower() in name.lower()
                            ):
                                resolved_score_id = s.get('id')
                                break
                        if resolved_score_id:
                            break
                except Exception as e:
                    self._log(f"Score resolution error: {e}", level="WARNING")
                if not resolved_score_id:
                    return {"error": f"Score not found in scorecard {scorecard_identifier}: {score_identifier}"}, "\n".join(self.log_messages)

            analyzer = ScoreResultCostAnalyzer(
                client=client,
                account_id="",  # accountId not required for scorecard/score filtered GSIs
                days=days,
                hours=hours,
                scorecard_id=resolved_scorecard_id or scorecard_identifier,
                score_id=resolved_score_id or score_identifier,
            )

            # Choose a sensible default grouping if breakdown requested but no group_by provided
            effective_group_by = group_by
            if breakdown and not effective_group_by:
                if (resolved_scorecard_id or scorecard_identifier) and not (resolved_score_id or score_identifier):
                    # At scorecard level → default to per-score breakdown
                    effective_group_by = "score"
                elif not (resolved_scorecard_id or scorecard_identifier) and not (resolved_score_id or score_identifier):
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
                    "window": {"hours": analysis.get("hours"), "days": analysis.get("days")},
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
                        groups_out.append({
                            "group": label,
                            **pick_summary(g)
                        })
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

            summary_log = f"Cost analysis completed (mode={mode}, breakdown={breakdown})."
            detailed_log = "\n".join(self.log_messages) if self.log_messages else ""
            return output_data, summary_log + ("\n" + detailed_log if detailed_log else "")

        except Exception as e:
            logger.exception(f"Error in CostAnalysis ReportBlock: {e}")
            return {"error": str(e)}, "\n".join(self.log_messages)

    async def _to_thread(self, fn, *args, **kwargs):
        import asyncio
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _log(self, message: str, level: str = "INFO"):
        if level == "DEBUG":
            logger.debug(f"[CostAnalysis] {message}")
        else:
            getattr(logger, level.lower(), logger.info)(f"[CostAnalysis] {message}")
            self.log_messages.append(message)


