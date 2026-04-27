import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from plexus.cli.evaluation.evaluations import load_scorecard_from_api
from plexus.cli.shared.identifier_resolution import (
    resolve_item_identifier,
    resolve_score_identifier,
    resolve_scorecard_identifier,
)
from plexus.dashboard.api.models.item import Item as PlexusItem


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_metadata(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _resolve_scorecard_and_score(
    *,
    client,
    scorecard_identifier: str,
    score_identifier: str,
) -> Tuple[str, str, Dict[str, Any]]:
    scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
    if not scorecard_id:
        raise ValueError(f"Scorecard not found: {scorecard_identifier}")

    score_id = resolve_score_identifier(client, scorecard_id, score_identifier)
    if not score_id:
        raise ValueError(
            f"Score not found in scorecard {scorecard_identifier}: {score_identifier}"
        )

    query = """
    query GetScorecardForScoreVersionTest($id: ID!) {
      getScorecard(id: $id) {
        id
        name
        sections {
          items {
            id
            name
            scorecardId
            scores {
              items {
                id
                name
                key
                externalId
                championVersionId
              }
            }
          }
        }
      }
    }
    """
    response = client.execute(query, {"id": scorecard_id}) or {}
    scorecard_data = response.get("getScorecard")
    if not scorecard_data:
        raise ValueError(f"Unable to fetch scorecard data for: {scorecard_identifier}")

    selected_score: Optional[Dict[str, Any]] = None
    for section in scorecard_data.get("sections", {}).get("items", []) or []:
        for score in section.get("scores", {}).get("items", []) or []:
            if score.get("id") == score_id:
                selected_score = score
                break
        if selected_score:
            break

    if not selected_score:
        raise ValueError(
            f"Resolved score ID {score_id} is missing from scorecard {scorecard_id}"
        )

    return scorecard_id, score_id, selected_score


def _sample_recent_feedback_item_ids(
    *,
    client,
    account_id: str,
    scorecard_id: str,
    score_id: str,
    days: int,
    desired_count: int,
) -> List[str]:
    cutoff = _utc_now() - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    now_iso = _utc_now().isoformat()

    query = """
    query ListFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
      $accountId: String!,
      $scorecardIdScoreIdEditedAt: ModelFeedbackItemByAccountScorecardScoreEditedAtCompositeKeyConditionInput,
      $limit: Int,
      $nextToken: String,
      $sortDirection: ModelSortDirection
    ) {
      listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
        accountId: $accountId,
        scorecardIdScoreIdEditedAt: $scorecardIdScoreIdEditedAt,
        limit: $limit,
        nextToken: $nextToken,
        sortDirection: $sortDirection
      ) {
        items {
          itemId
        }
        nextToken
      }
    }
    """

    next_token = None
    collected: List[str] = []
    seen = set()

    # Keep bounded pagination to avoid unbounded scans in giant accounts.
    for _ in range(20):
        variables = {
            "accountId": account_id,
            "scorecardIdScoreIdEditedAt": {
                "between": [
                    {
                        "scorecardId": scorecard_id,
                        "scoreId": score_id,
                        "editedAt": cutoff_iso,
                    },
                    {
                        "scorecardId": scorecard_id,
                        "scoreId": score_id,
                        "editedAt": now_iso,
                    },
                ]
            },
            "limit": 250,
            "nextToken": next_token,
            "sortDirection": "DESC",
        }
        response = client.execute(query, variables) or {}
        payload = (
            response.get("listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt")
            or {}
        )
        for item in payload.get("items", []) or []:
            item_id = item.get("itemId")
            if item_id and item_id not in seen:
                seen.add(item_id)
                collected.append(item_id)
        next_token = payload.get("nextToken")
        if not next_token:
            break
        if len(collected) >= max(desired_count * 10, desired_count):
            break

    if len(collected) <= desired_count:
        return collected
    return random.sample(collected, desired_count)


def _sample_recent_scorecard_item_ids(
    *,
    client,
    scorecard_id: str,
    days: int,
    desired_count: int,
) -> List[str]:
    cutoff = _utc_now() - timedelta(days=days)
    query = """
    query ListScoreResultByScorecardId(
      $scorecardId: String!,
      $limit: Int,
      $nextToken: String
    ) {
      listScoreResultByScorecardId(
        scorecardId: $scorecardId,
        limit: $limit,
        nextToken: $nextToken
      ) {
        items {
          itemId
          createdAt
        }
        nextToken
      }
    }
    """

    next_token = None
    collected: List[str] = []
    seen = set()

    for _ in range(20):
        response = client.execute(
            query,
            {"scorecardId": scorecard_id, "limit": 500, "nextToken": next_token},
        ) or {}
        payload = response.get("listScoreResultByScorecardId") or {}
        items = payload.get("items", []) or []

        for result in items:
            created_at = _parse_iso_timestamp(result.get("createdAt"))
            if created_at and created_at < cutoff:
                continue
            item_id = result.get("itemId")
            if item_id and item_id not in seen:
                seen.add(item_id)
                collected.append(item_id)

        next_token = payload.get("nextToken")
        if not next_token:
            break
        if len(collected) >= max(desired_count * 10, desired_count):
            break

    if len(collected) <= desired_count:
        return collected
    return random.sample(collected, desired_count)


async def _predict_single_item(
    *,
    client,
    scorecard_instance,
    resolved_score_name: str,
    target_result_id: Optional[str],
    score_name_for_output: str,
    item_id: str,
) -> Dict[str, Any]:
    item_query = """
    query GetItemForScoreVersionTest($id: ID!) {
      getItem(id: $id) {
        id
        text
        description
        metadata
        attachedFiles
        externalId
        identifiers
        accountId
        evaluationId
        scoreId
        createdAt
        updatedAt
        isEvaluation
        createdByType
      }
    }
    """
    item_response = client.execute(item_query, {"id": item_id}) or {}
    item_data = item_response.get("getItem")
    if not item_data:
        return {
            "item_id": item_id,
            "passed": False,
            "error": "item_not_found",
            "message": f"Item not found: {item_id}",
        }

    text = item_data.get("text") or item_data.get("description") or ""
    if not text:
        return {
            "item_id": item_id,
            "passed": False,
            "error": "missing_item_text",
            "message": f"Item has no text/description: {item_id}",
        }

    metadata = _normalize_metadata(item_data.get("metadata"))

    try:
        item_obj = PlexusItem.from_dict(item_data, client)
    except Exception:
        item_obj = None

    try:
        results = await scorecard_instance.score_entire_text(
            text=text,
            metadata=metadata,
            modality=None,
            subset_of_score_names=[resolved_score_name],
            item=item_obj,
        )
    except Exception as exc:
        return {
            "item_id": item_id,
            "passed": False,
            "error": "prediction_exception",
            "message": str(exc),
            "score": {
                "name": score_name_for_output,
                "value": "ERROR",
                "explanation": f"Failed to execute prediction: {exc}",
                "cost": {},
                "error_details": {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            },
        }

    score_result = None
    if isinstance(results, dict):
        if target_result_id and target_result_id in results:
            score_result = results[target_result_id]
        elif resolved_score_name in results:
            score_result = results[resolved_score_name]
        elif len(results) == 1:
            score_result = list(results.values())[0]

    if score_result is None:
        return {
            "item_id": item_id,
            "passed": False,
            "error": "missing_score_result",
            "message": f"No score result returned for {resolved_score_name}",
        }

    value = getattr(score_result, "value", None)
    explanation = (
        getattr(score_result, "explanation", None)
        or (
            score_result.metadata.get("explanation", "")
            if getattr(score_result, "metadata", None)
            else ""
        )
    )
    cost = getattr(score_result, "cost", None) or (
        score_result.metadata.get("cost", {})
        if getattr(score_result, "metadata", None)
        else {}
    )
    trace = getattr(score_result, "trace", None) or (
        score_result.metadata.get("trace")
        if getattr(score_result, "metadata", None)
        else None
    )

    passed = value is not None and str(value).upper() != "ERROR"
    payload: Dict[str, Any] = {
        "item_id": item_id,
        "passed": passed,
        "score": {
            "name": score_name_for_output,
            "value": value,
            "explanation": explanation,
            "cost": cost or {},
        },
    }
    if trace is not None:
        payload["score"]["trace"] = trace
    if getattr(score_result, "metadata", None):
        payload["score"]["metadata"] = score_result.metadata
    if not passed:
        payload["error"] = "invalid_score_result"
        payload["message"] = f"Prediction failed mechanically with value={value}"
    return payload


async def run_score_version_test(
    *,
    client,
    scorecard_identifier: str,
    score_identifier: str,
    version: Optional[str] = None,
    samples: int = 3,
    item_identifiers: Optional[Sequence[str]] = None,
    days: int = 90,
) -> Dict[str, Any]:
    if samples <= 0:
        raise ValueError("samples must be a positive integer")

    account_id = client._resolve_account_id()
    if not account_id:
        raise ValueError("Unable to resolve default account ID")

    scorecard_id, score_id, score_data = _resolve_scorecard_and_score(
        client=client,
        scorecard_identifier=scorecard_identifier,
        score_identifier=score_identifier,
    )

    target_version_id = version or score_data.get("championVersionId")
    if not target_version_id:
        raise ValueError("Unable to resolve score version for testing")

    explicit_ids = [s.strip() for s in (item_identifiers or []) if s and s.strip()]
    resolved_items: List[str] = []
    selection_source = "explicit_items"
    selection_error: Optional[Tuple[str, str]] = None

    if explicit_ids:
        seen = set()
        for raw in explicit_ids:
            resolved = resolve_item_identifier(client, raw, account_id)
            if not resolved:
                selection_error = (
                    "invalid_item_identifier",
                    f"Unable to resolve item identifier: {raw}",
                )
                break
            if resolved not in seen:
                seen.add(resolved)
                resolved_items.append(resolved)
    else:
        desired = samples
        selection_source = "recent_feedback_items"
        resolved_items = _sample_recent_feedback_item_ids(
            client=client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            days=days,
            desired_count=desired,
        )
        if not resolved_items:
            selection_source = "recent_scorecard_items"
            resolved_items = _sample_recent_scorecard_item_ids(
                client=client,
                scorecard_id=scorecard_id,
                days=days,
                desired_count=desired,
            )

        if len(resolved_items) < desired:
            if len(resolved_items) == 0:
                selection_error = (
                    "no_samples_found",
                    f"No candidate items found in the last {days} days.",
                )
            else:
                selection_error = (
                    "selection_shortfall",
                    f"Found {len(resolved_items)} samples but {desired} required.",
                )

    scorecard_instance = None
    resolved_score_name = str(score_data.get("name") or score_identifier)
    target_result_id: Optional[str] = None
    prediction_results: List[Dict[str, Any]] = []

    if not selection_error:
        scorecard_instance = load_scorecard_from_api(
            scorecard_identifier=scorecard_identifier,
            score_names=[score_identifier],
            use_cache=False,
            specific_version=target_version_id,
        )
        # Resolve canonical score name for subset execution and result matching.
        for score_config in getattr(scorecard_instance, "scores", []) or []:
            if (
                str(score_config.get("id")) == str(score_id)
                or score_config.get("name") == score_identifier
                or score_config.get("key") == score_identifier
                or str(score_config.get("externalId")) == str(score_identifier)
            ):
                resolved_score_name = score_config.get("name") or resolved_score_name
                break
        try:
            _, name_to_id = scorecard_instance.build_dependency_graph([resolved_score_name])
            target_result_id = name_to_id.get(resolved_score_name)
        except Exception:
            target_result_id = None

        prediction_results = list(
            await asyncio.gather(
                *[
                    _predict_single_item(
                        client=client,
                        scorecard_instance=scorecard_instance,
                        resolved_score_name=resolved_score_name,
                        target_result_id=target_result_id,
                        score_name_for_output=resolved_score_name,
                        item_id=item_id,
                    )
                    for item_id in resolved_items
                ]
            )
        )

    passed = False
    failure_code = None
    message = "Score version mechanical test passed."
    if selection_error:
        failure_code, message = selection_error
    else:
        failed_predictions = [p for p in prediction_results if not p.get("passed")]
        if failed_predictions:
            failure_code = "prediction_failure"
            message = (
                f"{len(failed_predictions)} of {len(prediction_results)} predictions failed."
            )
        else:
            passed = True

    return {
        "success": True,
        "passed": passed,
        "failure_code": failure_code,
        "message": message,
        "scorecard_id": scorecard_id,
        "score_id": score_id,
        "score_version_id": target_version_id,
        "requested_samples": samples,
        "selected_samples": len(resolved_items),
        "selection_source": selection_source,
        "item_ids": resolved_items,
        "predictions": prediction_results,
        "failures": [p for p in prediction_results if not p.get("passed")],
    }


def run_score_version_test_sync(**kwargs: Any) -> Dict[str, Any]:
    return asyncio.run(run_score_version_test(**kwargs))
