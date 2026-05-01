"""
Item-related helper functions used by the execute_tactus direct handlers.

These were extracted from MCP/tools/item/items.py when that legacy tool
module was removed; the functions remain in active use by _default_item_info
and _default_item_last inside execute.py.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def _get_identifiers_for_item(item_id: str, client) -> Optional[List[Dict[str, Any]]]:
    """Fetch identifiers from the Identifier table for a given item."""
    try:
        query = """
        query ListIdentifierByItemIdAndPosition($itemId: String!) {
            listIdentifierByItemIdAndPosition(itemId: $itemId) {
                items {
                    name
                    value
                    url
                    position
                }
            }
        }
        """
        result = client.execute(query, {"itemId": item_id})
        items = result.get("listIdentifierByItemIdAndPosition", {}).get("items", [])
        if items:
            return [{"name": i["name"], "value": i["value"], "url": i.get("url")} for i in items]
        return None
    except Exception as e:
        logger.warning(f"Error fetching identifiers for item {item_id}: {e}")
        return None


async def _get_score_results_for_item(item_id: str, client) -> List[Dict[str, Any]]:
    """
    Return all score results for a specific item, sorted by updatedAt descending.
    """
    try:
        from datetime import datetime

        from plexus.dashboard.api.models.score_result import ScoreResult

        query = f"""
        query ListScoreResultByItemId($itemId: String!) {{
            listScoreResultByItemId(itemId: $itemId) {{
                items {{
                    {ScoreResult.fields()}
                    updatedAt
                    createdAt
                }}
            }}
        }}
        """

        result = client.execute(query, {"itemId": item_id})
        score_results_data = result.get("listScoreResultByItemId", {}).get("items", [])

        score_results = []
        for sr_data in score_results_data:
            score_result = ScoreResult.from_dict(sr_data, client)

            sr_dict: Dict[str, Any] = {
                "id": score_result.id,
                "value": score_result.value,
                "explanation": getattr(score_result, "explanation", None),
                "confidence": score_result.confidence,
                "correct": score_result.correct,
                "itemId": score_result.itemId,
                "scoreId": getattr(score_result, "scoreId", None),
                "scoreName": score_result.scoreName,
                "scoreVersionId": getattr(score_result, "scoreVersionId", None),
                "scorecardId": score_result.scorecardId,
                "evaluationId": score_result.evaluationId,
                "scoringJobId": getattr(score_result, "scoringJobId", None),
                "metadata": score_result.metadata,
                "trace": getattr(score_result, "trace", None),
            }

            try:
                cost_payload = None
                if isinstance(sr_data, dict) and "cost" in sr_data and sr_data["cost"] is not None:
                    cost_payload = sr_data["cost"]
                if cost_payload is None and isinstance(sr_dict.get("metadata"), dict):
                    cost_payload = sr_dict["metadata"].get("cost")
                if cost_payload is not None:
                    sr_dict["cost"] = cost_payload
            except Exception:
                pass

            for ts_field in ("updatedAt", "createdAt"):
                raw = sr_data.get(ts_field)
                if isinstance(raw, str):
                    try:
                        sr_dict[ts_field] = datetime.fromisoformat(
                            raw.replace("Z", "+00:00")
                        ).isoformat()
                    except ValueError:
                        sr_dict[ts_field] = raw
                elif raw is not None:
                    sr_dict[ts_field] = raw

            score_results.append(sr_dict)

        score_results.sort(
            key=lambda sr: sr.get("updatedAt", "1970-01-01T00:00:00"),
            reverse=True,
        )
        return score_results

    except Exception as e:
        logger.error(
            f"Error getting score results for item {item_id}: {e}", exc_info=True
        )
        return []


async def _get_feedback_items_for_item(item_id: str, client) -> List[Dict[str, Any]]:
    """
    Return all feedback items for a specific item, sorted by updatedAt descending.
    """
    try:
        from plexus.dashboard.api.models.feedback_item import FeedbackItem

        feedback_items, _ = FeedbackItem.list(
            client=client,
            filter={"itemId": {"eq": item_id}},
            limit=1000,
        )

        feedback_items_list = []
        for fi in feedback_items:
            fi_dict: Dict[str, Any] = {
                "id": fi.id,
                "accountId": fi.accountId,
                "scorecardId": fi.scorecardId,
                "scoreId": fi.scoreId,
                "itemId": fi.itemId,
                "cacheKey": fi.cacheKey,
                "initialAnswerValue": fi.initialAnswerValue,
                "finalAnswerValue": fi.finalAnswerValue,
                "initialCommentValue": fi.initialCommentValue,
                "finalCommentValue": fi.finalCommentValue,
                "editCommentValue": fi.editCommentValue,
                "isAgreement": fi.isAgreement,
                "editorName": fi.editorName,
                "editedAt": (
                    fi.editedAt.isoformat()
                    if hasattr(fi.editedAt, "isoformat") and fi.editedAt
                    else fi.editedAt
                ),
                "createdAt": (
                    fi.createdAt.isoformat()
                    if hasattr(fi.createdAt, "isoformat") and fi.createdAt
                    else fi.createdAt
                ),
                "updatedAt": (
                    fi.updatedAt.isoformat()
                    if hasattr(fi.updatedAt, "isoformat") and fi.updatedAt
                    else fi.updatedAt
                ),
            }
            feedback_items_list.append(fi_dict)

        feedback_items_list.sort(
            key=lambda fi: fi.get("updatedAt", "1970-01-01T00:00:00"),
            reverse=True,
        )
        return feedback_items_list

    except Exception as e:
        logger.error(
            f"Error getting feedback items for item {item_id}: {e}", exc_info=True
        )
        return []


def _get_item_url(item_id: str) -> str:
    """Generate a dashboard URL for an item."""
    from urllib.parse import urljoin

    base_url = os.environ.get("PLEXUS_APP_URL", "https://plexus.anth.us")
    if not base_url.endswith("/"):
        base_url += "/"
    path = f"lab/items/{item_id}".lstrip("/")
    return urljoin(base_url, path)


def _get_default_account_id() -> Optional[str]:
    """Resolve and return the default account ID for the current environment."""
    try:
        from plexus.cli.report.utils import resolve_account_id_for_command
        from plexus.cli.shared.client_utils import create_client

        client = create_client()
        if client:
            return resolve_account_id_for_command(client, None)
        return None
    except Exception as e:
        logger.warning(f"Error getting default account ID: {e}")
        return None
