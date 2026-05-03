#!/usr/bin/env python3
"""
Cost analysis tools for Plexus MCP Server
"""
import logging
from typing import Dict, Any, Union, Optional
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_cost_analysis_tools(mcp: FastMCP):
    """Register cost analysis tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_cost_analysis(
        days: Union[int, float, str] = 0,
        hours: Union[int, float, str] = 1,
        scorecard: Optional[str] = None,
        score: Optional[str] = None,
        group_by: Optional[str] = None,
        mode: str = "summary",
        breakdown: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Cost analysis over a time window (default last 1 hour).
        Returns headline metrics (average, stddev, median, quartiles) and optional grouped breakdowns.

        group_by can be: null, "scorecard", "score", or "scorecard_score".
        """
        try:
            # Parse window params (prefer hours when provided)
            try:
                days = int(float(str(days)))
            except (ValueError, TypeError):
                days = 0
            try:
                hours = int(float(str(hours)))
            except (ValueError, TypeError):
                hours = 1

            from plexus.cli.shared.client_utils import create_client as create_dashboard_client
            from plexus.cli.report.utils import resolve_account_id_for_command
            from plexus.costs.cost_analysis import ScoreResultCostAnalyzer
            # Import resolve_scorecard_identifier from the main server module  
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            mcp_dir = os.path.dirname(os.path.dirname(current_dir))
            sys.path.insert(0, mcp_dir)
            from plexus_fastmcp_server import resolve_scorecard_identifier
            
            client = create_dashboard_client()
            account_id = resolve_account_id_for_command(client, None)

            # Resolve scorecard identifier if provided (accept id/key/name/externalId)
            resolved_scorecard_id = None
            resolved_scorecard_name = None
            if scorecard:
                try:
                    resolved_scorecard_id = resolve_scorecard_identifier(client, scorecard)
                except Exception:
                    resolved_scorecard_id = None
                if not resolved_scorecard_id:
                    return {"success": False, "error": f"Scorecard not found: {scorecard}"}
                # Fetch scorecard name for display
                try:
                    scq = f"""
                    query GetScorecardName {{
                      getScorecard(id: "{resolved_scorecard_id}") {{ id name }}
                    }}
                    """
                    scq_resp = client.execute(scq)
                    scd = scq_resp.get('getScorecard') or {}
                    resolved_scorecard_name = scd.get('name')
                except Exception:
                    resolved_scorecard_name = None

            # Resolve score id if both scorecard and score are provided
            resolved_score_id = None
            if resolved_scorecard_id and score:
                scorecard_query = f"""
                query GetScorecardForCostAnalysis {{
                    getScorecard(id: "{resolved_scorecard_id}") {{
                        id
                        name
                        sections {{
                            items {{
                                scores {{
                                    items {{
                                        id
                                        name
                                        key
                                        externalId
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
                """
                try:
                    sc_resp = client.execute(scorecard_query)
                except Exception as e:
                    return {"success": False, "error": f"Scorecard query failed: {e}"}
                sc_data = sc_resp.get('getScorecard') or {}
                for section in (sc_data.get('sections', {}) or {}).get('items', []) or []:
                    for s in (section.get('scores', {}) or {}).get('items', []) or []:
                        name = s.get('name') or ''
                        if (
                            s.get('id') == score or
                            name.lower() == str(score).lower() or
                            s.get('key') == score or
                            s.get('externalId') == score or
                            str(score).lower() in name.lower()
                        ):
                            resolved_score_id = s.get('id')
                            break
                    if resolved_score_id:
                        break
                if not resolved_score_id:
                    return {"success": False, "error": f"Score not found in scorecard {scorecard}: {score}"}

            analyzer = ScoreResultCostAnalyzer(
                client=client,
                account_id=account_id,
                days=days,
                hours=hours,
                scorecard_id=resolved_scorecard_id or scorecard,
                score_id=resolved_score_id or score,
            )
            analysis = analyzer.analyze(group_by=group_by)

            # Build summary-first view, with optional breakdowns and names
            def pick_summary(head: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "average_cost": head.get("average_cost"),
                    "count": head.get("count"),
                    "total_cost": head.get("total_cost"),
                    "average_calls": head.get("average_calls"),
                }

            if mode == "summary":
                result: Dict[str, Any] = {
                    "success": True,
                    "accountId": analysis.get("accountId"),
                    "days": analysis.get("days"),
                    "hours": analysis.get("hours"),
                    "filters": analysis.get("filters"),
                    "summary": pick_summary(analysis.get("headline", {})),
                }
                if resolved_scorecard_id:
                    result["scorecardName"] = resolved_scorecard_name
                if breakdown and group_by in ("score", "scorecard", "scorecard_score"):
                    name_index = analysis.get("scoreNameIndex", {})
                    groups_out = []
                    for g in analysis.get("groups", []):
                        label = dict(g.get("group", {}))
                        # Attach human-friendly names when grouping by score
                        if "scoreId" in label:
                            sid = label["scoreId"]
                            if sid in name_index:
                                label["scoreName"] = name_index[sid]
                        groups_out.append({
                            "group": label,
                            **pick_summary(g)
                        })
                    # Sort by highest average cost first (desc)
                    from decimal import Decimal
                    def sort_key_cost(item):
                        try:
                            return Decimal(item.get("average_cost") or "0")
                        except Exception:
                            return Decimal("0")
                    groups_out.sort(key=sort_key_cost, reverse=True)
                    result["groups"] = groups_out
                return result

            # detail mode: include full analysis payload and scorecard name if resolved
            detail = {"success": True, **analysis}
            if resolved_scorecard_id:
                detail["scorecardName"] = resolved_scorecard_name
            return detail
        except Exception as e:
            logger.error(f"[MCP] Error in plexus_cost_analysis: {e}")
            return {"success": False, "error": str(e)}