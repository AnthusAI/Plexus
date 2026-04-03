import json
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import yaml

from plexus.CustomLogging import logging
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.task import Task
from plexus.data.FeedbackItems import FeedbackItems

from plexus.cli.dataset.datasets import (
    _create_associated_dataset_datasource_version,
    _fetch_score_name,
    _fetch_score_champion_version,
    _upload_dataset_parquet,
)


def _fetch_scorecard_account_id(client: PlexusDashboardClient, scorecard_id: str) -> str:
    result = client.execute(
        """
        query GetScorecardAccount($id: ID!) {
            getScorecard(id: $id) {
                id
                accountId
            }
        }
        """,
        {"id": scorecard_id},
    )
    account_id = (result.get("getScorecard") or {}).get("accountId")
    if not account_id:
        raise ValueError(f"Scorecard accountId is missing for scorecard {scorecard_id}.")
    return account_id


def resolve_score_valid_classes_from_champion_yaml(
    *,
    client: PlexusDashboardClient,
    score_id: str,
) -> List[str]:
    score_result = client.execute(
        """
        query GetScoreChampionVersion($id: ID!) {
            getScore(id: $id) {
                id
                championVersionId
            }
        }
        """,
        {"id": score_id},
    )
    score_data = score_result.get("getScore") or {}
    champion_version_id = score_data.get("championVersionId")
    if not champion_version_id:
        raise ValueError(f"No champion version configured for score {score_id}.")

    version_result = client.execute(
        """
        query GetScoreVersionConfiguration($id: ID!) {
            getScoreVersion(id: $id) {
                id
                configuration
            }
        }
        """,
        {"id": champion_version_id},
    )
    version_data = version_result.get("getScoreVersion") or {}
    configuration_text = version_data.get("configuration")
    if not configuration_text:
        raise ValueError(
            f"Champion score version {champion_version_id} has no configuration for score {score_id}."
        )

    try:
        parsed = yaml.safe_load(configuration_text)
    except Exception as exc:
        raise ValueError(
            f"Champion score configuration is invalid YAML for score {score_id}: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"Champion score configuration must be a mapping for score {score_id}.")

    valid_classes: List[str] = []
    seen = set()

    def add_class(value: Any):
        if isinstance(value, bool):
            candidate = "Yes" if value else "No"
        elif isinstance(value, str):
            candidate = value.strip()
        else:
            return
        if not candidate or candidate in seen:
            return
        seen.add(candidate)
        valid_classes.append(candidate)

    classes_section = parsed.get("classes")
    if isinstance(classes_section, list):
        for class_def in classes_section:
            if isinstance(class_def, dict):
                add_class(class_def.get("name"))

    graph_nodes = parsed.get("graph")
    if isinstance(graph_nodes, list):
        for node in graph_nodes:
            if not isinstance(node, dict):
                continue
            node_classes = node.get("valid_classes")
            if isinstance(node_classes, list):
                for node_class in node_classes:
                    add_class(node_class)

    if not valid_classes:
        raise ValueError(
            f"No valid classes found in champion score YAML for score {score_id}."
        )

    return valid_classes


def _is_qualifying_feedback_item(
    feedback_item: FeedbackItem,
    *,
    scorecard_id: str,
    score_id: str,
) -> bool:
    if feedback_item.scorecardId != scorecard_id or feedback_item.scoreId != score_id:
        return False
    if not (feedback_item.finalAnswerValue or "").strip():
        return False
    item = getattr(feedback_item, "item", None)
    if item is None:
        return False
    if not getattr(item, "id", None):
        return False
    # Text is required by evaluation dataset rows.
    if not (getattr(item, "text", None) or ""):
        return False
    return True


def collect_qualifying_feedback_items(
    *,
    client: PlexusDashboardClient,
    account_id: str,
    scorecard_id: str,
    score_id: str,
    max_items: int,
    days: Optional[int],
) -> List[FeedbackItem]:
    if max_items <= 0:
        raise ValueError("--max-items must be greater than 0.")
    if days is not None and days <= 0:
        raise ValueError("--days must be greater than 0 when provided.")

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days) if days is not None else datetime(1970, 1, 1, tzinfo=timezone.utc)
    end = now + timedelta(minutes=5)

    query = """
    query ListFeedbackItemsByGSI(
        $accountId: String!,
        $composite_sk_condition: ModelFeedbackItemByAccountScorecardScoreEditedAtCompositeKeyConditionInput,
        $limit: Int,
        $nextToken: String,
        $sortDirection: ModelSortDirection
    ) {
        listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
            accountId: $accountId,
            scorecardIdScoreIdEditedAt: $composite_sk_condition,
            limit: $limit,
            nextToken: $nextToken,
            sortDirection: $sortDirection
        ) {
            items {
                id
                accountId
                scorecardId
                scoreId
                itemId
                cacheKey
                initialAnswerValue
                finalAnswerValue
                initialCommentValue
                finalCommentValue
                editCommentValue
                editedAt
                editorName
                isAgreement
                isInvalid
                createdAt
                updatedAt
                item {
                    id
                    identifiers
                    externalId
                    description
                    text
                    metadata
                    createdAt
                    updatedAt
                }
            }
            nextToken
        }
    }
    """

    variables: Dict[str, Any] = {
        "accountId": account_id,
        "composite_sk_condition": {
            "between": [
                {
                    "scorecardId": scorecard_id,
                    "scoreId": score_id,
                    "editedAt": start.isoformat(),
                },
                {
                    "scorecardId": scorecard_id,
                    "scoreId": score_id,
                    "editedAt": end.isoformat(),
                },
            ]
        },
        "limit": 100,
        "nextToken": None,
        "sortDirection": "DESC",
    }

    qualifying_items: List[FeedbackItem] = []
    while len(qualifying_items) < max_items:
        response = client.execute(query, variables)
        result_data = response.get("listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt") or {}
        items_data = result_data.get("items") or []
        if not items_data:
            break

        for item_dict in items_data:
            feedback_item = FeedbackItem.from_dict(item_dict, client=client)
            if _is_qualifying_feedback_item(
                feedback_item,
                scorecard_id=scorecard_id,
                score_id=score_id,
            ):
                qualifying_items.append(feedback_item)
                if len(qualifying_items) >= max_items:
                    break

        next_token = result_data.get("nextToken")
        if not next_token:
            break
        variables["nextToken"] = next_token

    # Deterministic ordering by newest editedAt, then stable ID tie-break.
    qualifying_items.sort(
        key=lambda item: (
            str(getattr(item, "editedAt", "") or ""),
            str(item.id or ""),
        ),
        reverse=True,
    )
    return qualifying_items[:max_items]


def build_associated_dataset_from_feedback_window(
    *,
    client: PlexusDashboardClient,
    scorecard_id: str,
    score_id: str,
    max_items: int = 100,
    days: Optional[int] = None,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    score_name = _fetch_score_name(client, score_id)
    account_id = _fetch_scorecard_account_id(client, scorecard_id)

    task: Optional[Task] = None
    if task_id:
        task = Task.get_by_id(task_id, client)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        worker_id = f"{socket.gethostname()}-{os.getpid()}"
        task.update(
            status="RUNNING",
            dispatchStatus="DISPATCHED",
            startedAt=datetime.now(timezone.utc).isoformat(),
            workerNodeId=worker_id,
            errorMessage=None,
            error=None,
        )

    try:
        feedback_items = collect_qualifying_feedback_items(
            client=client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            max_items=max_items,
            days=days,
        )
        if not feedback_items:
            raise ValueError("No qualifying feedback items found for dataset curation.")

        selected_feedback_ids = [item.id for item in feedback_items if item.id]
        row_builder = FeedbackItems(scorecard=scorecard_id, score=score_id)
        dataframe = row_builder._create_dataset_rows(feedback_items, score_name)
        if dataframe.empty:
            raise ValueError("Associated dataset curation produced zero rows.")

        if "feedback_item_id" in dataframe.columns:
            dataframe = dataframe.sort_values(by="feedback_item_id", kind="stable").reset_index(drop=True)

        _data_source_id, data_source_version_id = _create_associated_dataset_datasource_version(
            client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            score_name=score_name,
            source_report_block_id="score.dataset-curate",
            eligibility_rule="latest qualifying feedback labels",
            feedback_item_ids=selected_feedback_ids,
        )

        dataset_input: Dict[str, Any] = {
            "name": f"Associated Dataset - {score_name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            "description": "Associated dataset curated from recent qualifying feedback.",
            "accountId": account_id,
            "scorecardId": scorecard_id,
            "scoreId": score_id,
            "dataSourceVersionId": data_source_version_id,
        }

        champion_version_id = _fetch_score_champion_version(client, score_id)
        if champion_version_id:
            dataset_input["scoreVersionId"] = champion_version_id

        create_dataset_result = client.execute(
            """
            mutation CreateDataSet($input: CreateDataSetInput!) {
                createDataSet(input: $input) {
                    id
                    name
                    scoreId
                    scorecardId
                    dataSourceVersionId
                }
            }
            """,
            {"input": dataset_input},
        )
        dataset_record = create_dataset_result.get("createDataSet") or {}
        dataset_id = dataset_record.get("id")
        if not dataset_id:
            raise ValueError("Failed to create DataSet record.")

        s3_key = _upload_dataset_parquet(
            dataframe=dataframe,
            account_id=account_id,
            dataset_id=dataset_id,
        )
        client.execute(
            """
            mutation UpdateDataSet($input: UpdateDataSetInput!) {
                updateDataSet(input: $input) {
                    id
                    file
                }
            }
            """,
            {"input": {"id": dataset_id, "file": s3_key}},
        )

        result_payload: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "requested_max_items": max_items,
            "qualifying_found": len(selected_feedback_ids),
            "rows_written": int(len(dataframe)),
            "score_id": score_id,
            "scorecard_id": scorecard_id,
            "s3_key": s3_key,
        }

        if task:
            task.update(
                status="COMPLETED",
                completedAt=datetime.now(timezone.utc).isoformat(),
                output=json.dumps(result_payload),
                errorMessage=None,
                error=None,
            )
        return result_payload
    except Exception as exc:
        if task:
            task.update(
                status="FAILED",
                completedAt=datetime.now(timezone.utc).isoformat(),
                errorMessage=str(exc),
                error=str(exc),
            )
        raise
