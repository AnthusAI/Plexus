import json
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import yaml

from plexus.CustomLogging import logging
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.dashboard.api.models.report_configuration import ReportConfiguration
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.task import Task
from plexus.data.FeedbackItems import FeedbackItems
from plexus.reports.s3_utils import download_report_block_file
from plexus.reports.service import generate_report_with_parameters

from plexus.cli.dataset.datasets import (
    _create_associated_dataset_datasource_version,
    _fetch_feedback_item_with_item,
    _fetch_score_name,
    _fetch_score_champion_version,
    _persist_dataset_file_reference,
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


AUTO_VETTED_REPORT_CONFIG_NAME = "Auto: Vetted Associated Dataset Curation"
AUTO_VETTED_REPORT_CONFIG_DESCRIPTION = (
    "Auto-managed aligned guideline-vetting report configuration used as evidence for "
    "vetted associated dataset curation."
)
AUTO_VETTED_POOL_MULTIPLIER = 5
AUTO_VETTED_POOL_ABSOLUTE_CAP = 2000


def _render_auto_vetted_report_configuration_markdown(
    *,
    scorecard_id: str,
    score_id: str,
    days: int,
    vetting_pool_limit: int,
) -> str:
    if vetting_pool_limit <= 0:
        raise ValueError("vetting_pool_limit must be greater than 0.")
    return (
        "# Auto-managed report configuration for vetted associated dataset curation.\n\n"
        "```block name=\"Aligned Vetted Feedback\"\n"
        "class: FeedbackContradictions\n"
        f"scorecard: \"{scorecard_id}\"\n"
        f"score: \"{score_id}\"\n"
        "mode: aligned\n"
        f"days: {days}\n"
        f"max_feedback_items: {vetting_pool_limit}\n"
        "max_concurrent: 20\n"
        "num_topics: 8\n"
        "```\n"
    )


def _ensure_auto_vetted_report_configuration(
    *,
    client: PlexusDashboardClient,
    account_id: str,
    scorecard_id: str,
    score_id: str,
    days: int,
    vetting_pool_limit: int,
) -> ReportConfiguration:
    configuration_markdown = _render_auto_vetted_report_configuration_markdown(
        scorecard_id=scorecard_id,
        score_id=score_id,
        days=days,
        vetting_pool_limit=vetting_pool_limit,
    )
    existing = ReportConfiguration.get_by_name(
        AUTO_VETTED_REPORT_CONFIG_NAME,
        account_id,
        client=client,
    )
    if not existing:
        return ReportConfiguration.create(
            client=client,
            name=AUTO_VETTED_REPORT_CONFIG_NAME,
            accountId=account_id,
            description=AUTO_VETTED_REPORT_CONFIG_DESCRIPTION,
            configuration=configuration_markdown,
        )
    if (
        existing.configuration != configuration_markdown
        or (existing.description or "") != AUTO_VETTED_REPORT_CONFIG_DESCRIPTION
    ):
        return existing.update(
            client=client,
            name=AUTO_VETTED_REPORT_CONFIG_NAME,
            accountId=account_id,
            description=AUTO_VETTED_REPORT_CONFIG_DESCRIPTION,
            configuration=configuration_markdown,
        )
    return existing


def _parse_feedback_contradictions_block_output(content: str) -> Dict[str, Any]:
    json_text = "\n".join(line for line in content.splitlines() if not line.startswith("#"))
    parsed = json.loads(json_text)
    if not isinstance(parsed, dict):
        raise ValueError("FeedbackContradictions output payload must be an object.")
    return parsed


def _load_feedback_contradictions_output_from_block(block: ReportBlock) -> Dict[str, Any]:
    block_output = block.output
    if not isinstance(block_output, dict):
        raise ValueError(
            f"Report block {block.id} output must be compact attachment metadata."
        )
    attachment_path = block_output.get("output_attachment")
    if not attachment_path:
        raise ValueError(
            f"Report block {block.id} is missing output_attachment."
        )
    output_content, _ = download_report_block_file(attachment_path)
    return _parse_feedback_contradictions_block_output(output_content)


def _run_aligned_vetting_report(
    *,
    client: PlexusDashboardClient,
    report_configuration_id: str,
    account_id: str,
) -> Dict[str, Any]:
    report_id, first_block_error, report_task_id = generate_report_with_parameters(
        config_id=report_configuration_id,
        parameters={},
        account_id=account_id,
        client=client,
        trigger="score_dataset_curate_vetted",
    )
    if not report_id:
        raise ValueError("Report run did not return a report_id.")
    if first_block_error:
        raise ValueError(
            f"Aligned vetting report failed (report_id={report_id}): {first_block_error}"
        )

    blocks = ReportBlock.list_by_report_id(report_id=report_id, client=client, limit=100, max_items=100)
    aligned_block = next((block for block in blocks if block.type == "FeedbackContradictions"), None)
    if not aligned_block:
        raise ValueError(
            f"Report {report_id} does not contain a FeedbackContradictions block."
        )

    output_payload = _load_feedback_contradictions_output_from_block(aligned_block)
    if output_payload.get("error"):
        raise ValueError(
            f"FeedbackContradictions block {aligned_block.id} failed: {output_payload.get('error')}"
        )
    if str(output_payload.get("mode", "")).strip().lower() != "aligned":
        raise ValueError(
            f"FeedbackContradictions block {aligned_block.id} is not in aligned mode."
        )

    eligible_items = output_payload.get("eligible_associated_feedback_items")
    if not isinstance(eligible_items, list):
        raise ValueError(
            "Aligned report output is missing eligible_associated_feedback_items."
        )
    return {
        "report_id": report_id,
        "report_task_id": report_task_id,
        "report_block_id": aligned_block.id,
        "eligible_items": eligible_items,
        "eligible_count": len(eligible_items),
        "total_items_analyzed": int(output_payload.get("total_items_analyzed") or 0),
        "eligibility_rule": output_payload.get("eligibility_rule") or "unanimous non-contradiction",
    }


def resolve_score_valid_classes_from_score_yaml(
    *,
    client: PlexusDashboardClient,
    score_id: str,
    score_version_id: Optional[str] = None,
) -> List[str]:
    details = _resolve_score_final_classes_from_yaml_details(
        client=client,
        score_id=score_id,
        score_version_id=score_version_id,
    )
    return details["classes"]


def _resolve_score_final_classes_from_yaml_details(
    *,
    client: PlexusDashboardClient,
    score_id: str,
    score_version_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_score_version_id = score_version_id
    if not resolved_score_version_id:
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
        resolved_score_version_id = champion_version_id

    version_result = client.execute(
        """
        query GetScoreVersionConfiguration($id: ID!) {
            getScoreVersion(id: $id) {
                id
                configuration
            }
        }
        """,
        {"id": resolved_score_version_id},
    )
    version_data = version_result.get("getScoreVersion") or {}
    configuration_text = version_data.get("configuration")
    if not configuration_text:
        raise ValueError(
            f"Score version {resolved_score_version_id} has no configuration for score {score_id}."
        )

    try:
        parsed = yaml.safe_load(configuration_text)
    except Exception as exc:
        raise ValueError(
            f"Score configuration is invalid YAML for score {score_id} (version {resolved_score_version_id}): {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            f"Score configuration must be a mapping for score {score_id} (version {resolved_score_version_id})."
        )

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

    validation_classes = (
        ((parsed.get("parameters") or {}).get("validation") or {}).get("value") or {}
    ).get("valid_classes")
    if isinstance(validation_classes, list):
        for class_name in validation_classes:
            add_class(class_name)
    if valid_classes:
        return {
            "classes": valid_classes,
            "source": "parameters.validation.value.valid_classes",
            "score_version_id": resolved_score_version_id,
        }

    classes_section = parsed.get("classes")
    if isinstance(classes_section, list):
        for class_def in classes_section:
            if isinstance(class_def, dict):
                add_class(class_def.get("name"))
    if valid_classes:
        return {
            "classes": valid_classes,
            "source": "classes[].name",
            "score_version_id": resolved_score_version_id,
        }

    graph_nodes = parsed.get("graph")
    final_node = graph_nodes[-1] if isinstance(graph_nodes, list) and graph_nodes else None
    if isinstance(final_node, dict):
        node_classes = final_node.get("valid_classes")
        if isinstance(node_classes, list):
            for node_class in node_classes:
                add_class(node_class)
        if valid_classes:
            return {
                "classes": valid_classes,
                "source": "graph[-1].valid_classes",
                "score_version_id": resolved_score_version_id,
            }

        node_conditions = final_node.get("conditions")
        if isinstance(node_conditions, list):
            for condition in node_conditions:
                if not isinstance(condition, dict):
                    continue
                condition_output = condition.get("output")
                if not isinstance(condition_output, dict):
                    continue
                add_class(condition_output.get("value"))
        if valid_classes:
            return {
                "classes": valid_classes,
                "source": "graph[-1].conditions[].output.value",
                "score_version_id": resolved_score_version_id,
            }

        if final_node.get("class") == "LogicalClassifier":
            code_text = final_node.get("code")
            if isinstance(code_text, str) and code_text.strip():
                for match in re.findall(r'value\s*=\s*["\']([^"\']+)["\']', code_text):
                    add_class(match)
        if valid_classes:
            return {
                "classes": valid_classes,
                "source": "graph[-1].LogicalClassifier.code",
                "score_version_id": resolved_score_version_id,
            }

    if not valid_classes:
        raise ValueError(
            "No final output classes found in score YAML for "
            f"score {score_id} (version {resolved_score_version_id}). "
            "Checked: parameters.validation.value.valid_classes, classes[].name, "
            "graph[-1].valid_classes, graph[-1].conditions[].output.value, "
            "graph[-1].LogicalClassifier.code."
        )
    return {
        "classes": valid_classes,
        "source": "unknown",
        "score_version_id": resolved_score_version_id,
    }


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


def _normalize_label(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _compute_label_distribution(feedback_items: List[FeedbackItem]) -> Dict[str, int]:
    distribution: Dict[str, int] = {}
    for item in feedback_items:
        label = _normalize_label(getattr(item, "finalAnswerValue", ""))
        if not label:
            continue
        distribution[label] = distribution.get(label, 0) + 1
    return dict(sorted(distribution.items(), key=lambda pair: pair[0]))


def _select_balanced_feedback_items(
    *,
    all_qualifying_items: List[FeedbackItem],
    class_list: List[str],
    max_items: int,
) -> List[FeedbackItem]:
    if max_items <= 0:
        raise ValueError("--max-items must be greater than 0.")
    if not class_list:
        raise ValueError("Class list is required for balancing.")

    known_classes = [_normalize_label(label) for label in class_list if _normalize_label(label)]
    if not known_classes:
        raise ValueError("Class list is required for balancing.")

    buckets: Dict[str, List[FeedbackItem]] = {label: [] for label in known_classes}
    for item in all_qualifying_items:
        label = _normalize_label(getattr(item, "finalAnswerValue", ""))
        if label in buckets:
            buckets[label].append(item)

    selected: List[FeedbackItem] = []
    selected_ids = set()
    bucket_indices = {label: 0 for label in known_classes}

    made_progress = True
    while len(selected) < max_items and made_progress:
        made_progress = False
        for label in known_classes:
            bucket = buckets[label]
            index = bucket_indices[label]
            if index >= len(bucket):
                continue
            item = bucket[index]
            bucket_indices[label] = index + 1
            item_key = str(getattr(item, "id", "")) or f"idx-{len(selected)}"
            if item_key in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item_key)
            made_progress = True
            if len(selected) >= max_items:
                break

    if len(selected) < max_items:
        for item in all_qualifying_items:
            item_key = str(getattr(item, "id", "")) or f"idx-fill-{len(selected)}"
            if item_key in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item_key)
            if len(selected) >= max_items:
                break

    return selected[:max_items]


def collect_qualifying_feedback_items(
    *,
    client: PlexusDashboardClient,
    account_id: str,
    scorecard_id: str,
    score_id: str,
    max_items: int,
    days: Optional[int],
    stop_at_max: bool = True,
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
    while True:
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
                if stop_at_max and len(qualifying_items) >= max_items:
                    break

        if stop_at_max and len(qualifying_items) >= max_items:
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
    if stop_at_max:
        return qualifying_items[:max_items]
    return qualifying_items


def _ordered_unique_feedback_ids(vetted_feedback_items: List[Dict[str, Any]]) -> List[str]:
    ordered_ids: List[str] = []
    seen = set()
    for row in vetted_feedback_items:
        if not isinstance(row, dict):
            continue
        feedback_item_id = str(row.get("feedback_item_id") or "").strip()
        if not feedback_item_id or feedback_item_id in seen:
            continue
        seen.add(feedback_item_id)
        ordered_ids.append(feedback_item_id)
    return ordered_ids


def build_associated_dataset_from_vetted_feedback_items(
    *,
    client: PlexusDashboardClient,
    scorecard_id: str,
    score_id: str,
    vetted_feedback_items: List[Dict[str, Any]],
    max_items: int = 100,
    class_source_score_version_id: Optional[str] = None,
    report_id: str,
    report_block_id: str,
    eligibility_rule: str = "unanimous non-contradiction",
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    if max_items <= 0:
        raise ValueError("--max-items must be greater than 0.")
    ordered_feedback_item_ids = _ordered_unique_feedback_ids(vetted_feedback_items)
    if not ordered_feedback_item_ids:
        raise ValueError("No eligible vetted feedback item IDs were provided.")

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
        all_vetted_items: List[FeedbackItem] = []
        missing_ids: List[str] = []
        mismatched_ids: List[str] = []
        invalid_ids: List[str] = []
        for feedback_item_id in ordered_feedback_item_ids:
            feedback_item = _fetch_feedback_item_with_item(client, feedback_item_id)
            if feedback_item is None:
                missing_ids.append(feedback_item_id)
                continue
            if feedback_item.scorecardId != scorecard_id or feedback_item.scoreId != score_id:
                mismatched_ids.append(feedback_item_id)
                continue
            if not _is_qualifying_feedback_item(
                feedback_item,
                scorecard_id=scorecard_id,
                score_id=score_id,
            ):
                invalid_ids.append(feedback_item_id)
                continue
            all_vetted_items.append(feedback_item)

        if missing_ids:
            raise ValueError(f"Vetted feedback items not found: {', '.join(missing_ids)}")
        if mismatched_ids:
            raise ValueError(
                "Vetted feedback items do not match requested scorecard/score: "
                + ", ".join(mismatched_ids)
            )
        if invalid_ids:
            raise ValueError(
                "Vetted feedback items are missing required fields for dataset rows: "
                + ", ".join(invalid_ids)
            )
        if not all_vetted_items:
            raise ValueError("No valid vetted feedback items remain after validation.")

        class_resolution_details = _resolve_score_final_classes_from_yaml_details(
            client=client,
            score_id=score_id,
            score_version_id=class_source_score_version_id,
        )
        class_list_used = class_resolution_details["classes"]
        class_resolution_source = class_resolution_details["source"]
        resolved_score_version_used = class_resolution_details["score_version_id"]

        observed_label_set = sorted(
            {
                _normalize_label(getattr(item, "finalAnswerValue", ""))
                for item in all_vetted_items
                if _normalize_label(getattr(item, "finalAnswerValue", ""))
            }
        )
        class_label_overlap = sorted(set(class_list_used).intersection(set(observed_label_set)))
        min_required_overlap = 1 if max_items <= 1 else 2
        if len(class_label_overlap) < min_required_overlap:
            raise ValueError(
                "Insufficient class/label overlap for balancing vetted items. "
                f"score_id={score_id}, score_version_id={resolved_score_version_used}, "
                f"resolved_final_classes={class_list_used}, observed_label_set={observed_label_set}, "
                f"class_label_overlap={class_label_overlap}, required_overlap={min_required_overlap}."
            )

        seed_items = all_vetted_items[:max_items]
        feedback_items = _select_balanced_feedback_items(
            all_qualifying_items=all_vetted_items,
            class_list=class_list_used,
            max_items=max_items,
        )
        selected_feedback_ids = [item.id for item in feedback_items if item.id]

        row_builder = FeedbackItems(scorecard=scorecard_id, score=score_id)
        dataframe = row_builder._create_dataset_rows(feedback_items, score_name)
        if dataframe.empty:
            raise ValueError("Associated dataset curation produced zero rows from vetted items.")
        if "feedback_item_id" in dataframe.columns:
            dataframe = dataframe.sort_values(by="feedback_item_id", kind="stable").reset_index(drop=True)

        class_distribution_before = _compute_label_distribution(seed_items)
        class_distribution_after = _compute_label_distribution(feedback_items)

        _data_source_id, data_source_version_id = _create_associated_dataset_datasource_version(
            client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            score_name=score_name,
            source_report_block_id=report_block_id,
            eligibility_rule=eligibility_rule,
            feedback_item_ids=selected_feedback_ids,
            dataset_stats={
                "row_count": int(len(dataframe)),
                "label_distribution": class_distribution_after,
                "class_list_used": class_list_used,
                "class_resolution_source": class_resolution_source,
                "resolved_final_classes": class_list_used,
                "observed_label_set": observed_label_set,
                "class_label_overlap": class_label_overlap,
                "curation_policy": "balanced_vetted_feedback_labels",
                "balance_applied": True,
                "class_distribution_before": class_distribution_before,
                "class_distribution_after": class_distribution_after,
                "vetted_eligible_count": len(all_vetted_items),
                "selected_vetted_count": len(feedback_items),
                "source_report_id": report_id,
                "source_report_block_id": report_block_id,
            },
        )

        dataset_input: Dict[str, Any] = {
            "name": f"Associated Dataset - {score_name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            "description": "Associated dataset curated from vetted aligned feedback.",
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
        _persist_dataset_file_reference(
            client=client,
            dataset_id=dataset_id,
            s3_key=s3_key,
        )

        result_payload: Dict[str, Any] = {
            "report_id": report_id,
            "report_block_id": report_block_id,
            "dataset_id": dataset_id,
            "requested_max_items": max_items,
            "vetted_eligible_count": len(all_vetted_items),
            "selected_vetted_count": len(feedback_items),
            "rows_written": int(len(dataframe)),
            "score_id": score_id,
            "scorecard_id": scorecard_id,
            "s3_key": s3_key,
            "balance_applied": True,
            "class_list_used": class_list_used,
            "class_resolution_source": class_resolution_source,
            "resolved_final_classes": class_list_used,
            "observed_label_set": observed_label_set,
            "class_label_overlap": class_label_overlap,
            "class_distribution_before": class_distribution_before,
            "class_distribution_after": class_distribution_after,
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


def build_associated_dataset_from_vetted_report(
    *,
    client: PlexusDashboardClient,
    scorecard_id: str,
    score_id: str,
    max_items: int = 100,
    days: int = 180,
    class_source_score_version_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    if days <= 0:
        raise ValueError("--days must be greater than 0.")
    if max_items <= 0:
        raise ValueError("--max-items must be greater than 0.")

    vetting_pool_limit = max_items
    max_vetting_pool_limit = min(
        max(max_items, max_items * AUTO_VETTED_POOL_MULTIPLIER),
        AUTO_VETTED_POOL_ABSOLUTE_CAP,
    )
    account_id = _fetch_scorecard_account_id(client, scorecard_id)
    report_run: Optional[Dict[str, Any]] = None
    report_config: Optional[ReportConfiguration] = None
    attempts = 0
    attempted_pool_limits: List[int] = []

    while True:
        attempts += 1
        attempted_pool_limits.append(vetting_pool_limit)
        report_config = _ensure_auto_vetted_report_configuration(
            client=client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            days=days,
            vetting_pool_limit=vetting_pool_limit,
        )
        report_run = _run_aligned_vetting_report(
            client=client,
            report_configuration_id=report_config.id,
            account_id=account_id,
        )
        eligible_count = int(report_run.get("eligible_count") or 0)
        total_items_analyzed = int(report_run.get("total_items_analyzed") or 0)
        if eligible_count >= max_items:
            break
        if total_items_analyzed < vetting_pool_limit:
            # Source is exhausted inside the requested lookback window.
            break
        if vetting_pool_limit >= max_vetting_pool_limit:
            break
        next_limit = min(max_vetting_pool_limit, vetting_pool_limit * 2)
        if next_limit <= vetting_pool_limit:
            break
        vetting_pool_limit = next_limit

    if not report_run or not report_config:
        raise ValueError("Unable to run aligned vetting report.")

    eligible_items = report_run["eligible_items"]
    if not eligible_items:
        raise ValueError(
            f"Aligned vetting report produced zero eligible items (report_id={report_run['report_id']})."
        )

    dataset_result = build_associated_dataset_from_vetted_feedback_items(
        client=client,
        scorecard_id=scorecard_id,
        score_id=score_id,
        vetted_feedback_items=eligible_items,
        max_items=max_items,
        class_source_score_version_id=class_source_score_version_id,
        report_id=report_run["report_id"],
        report_block_id=report_run["report_block_id"],
        eligibility_rule=report_run["eligibility_rule"],
        task_id=task_id,
    )
    dataset_result["report_configuration_id"] = report_config.id
    dataset_result["report_task_id"] = report_run["report_task_id"]
    dataset_result["vetted_pool_limit"] = vetting_pool_limit
    dataset_result["vetted_pool_attempts"] = attempts
    dataset_result["vetted_pool_attempted_limits"] = attempted_pool_limits
    dataset_result["vetted_pool_max_limit"] = max_vetting_pool_limit
    return dataset_result


def build_associated_dataset_from_feedback_window(
    *,
    client: PlexusDashboardClient,
    scorecard_id: str,
    score_id: str,
    max_items: int = 100,
    days: Optional[int] = None,
    balance: bool = True,
    class_source_score_version_id: Optional[str] = None,
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
        all_qualifying_items = collect_qualifying_feedback_items(
            client=client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            max_items=max_items,
            days=days,
            stop_at_max=not balance,
        )
        if not all_qualifying_items:
            raise ValueError("No qualifying feedback items found for dataset curation.")

        seed_items = all_qualifying_items[:max_items]
        class_list_used: List[str] = []
        class_resolution_source: Optional[str] = None
        resolved_score_version_used: Optional[str] = None
        observed_label_set = sorted({
            _normalize_label(getattr(item, "finalAnswerValue", ""))
            for item in all_qualifying_items
            if _normalize_label(getattr(item, "finalAnswerValue", ""))
        })
        class_label_overlap: List[str] = []
        if balance:
            class_resolution_details = _resolve_score_final_classes_from_yaml_details(
                client=client,
                score_id=score_id,
                score_version_id=class_source_score_version_id,
            )
            class_list_used = class_resolution_details["classes"]
            class_resolution_source = class_resolution_details["source"]
            resolved_score_version_used = class_resolution_details["score_version_id"]
            class_label_overlap = sorted(set(class_list_used).intersection(set(observed_label_set)))
            min_required_overlap = 1 if max_items <= 1 else 2
            if len(class_label_overlap) < min_required_overlap:
                raise ValueError(
                    "Insufficient class/label overlap for balancing. "
                    f"score_id={score_id}, score_version_id={resolved_score_version_used}, "
                    f"resolved_final_classes={class_list_used}, observed_label_set={observed_label_set}, "
                    f"class_label_overlap={class_label_overlap}, required_overlap={min_required_overlap}."
                )
            feedback_items = _select_balanced_feedback_items(
                all_qualifying_items=all_qualifying_items,
                class_list=class_list_used,
                max_items=max_items,
            )
        else:
            feedback_items = seed_items

        selected_feedback_ids = [item.id for item in feedback_items if item.id]
        row_builder = FeedbackItems(scorecard=scorecard_id, score=score_id)
        dataframe = row_builder._create_dataset_rows(feedback_items, score_name)
        if dataframe.empty:
            raise ValueError("Associated dataset curation produced zero rows.")

        if "feedback_item_id" in dataframe.columns:
            dataframe = dataframe.sort_values(by="feedback_item_id", kind="stable").reset_index(drop=True)

        class_distribution_before = _compute_label_distribution(seed_items)
        class_distribution_after = _compute_label_distribution(feedback_items)

        _data_source_id, data_source_version_id = _create_associated_dataset_datasource_version(
            client,
            account_id=account_id,
            scorecard_id=scorecard_id,
            score_id=score_id,
            score_name=score_name,
            source_report_block_id="score.dataset-curate",
            eligibility_rule="latest qualifying feedback labels",
            feedback_item_ids=selected_feedback_ids,
            dataset_stats={
                "row_count": int(len(dataframe)),
                "label_distribution": class_distribution_after,
                "class_list_used": class_list_used,
                "class_resolution_source": class_resolution_source,
                "resolved_final_classes": class_list_used,
                "observed_label_set": observed_label_set,
                "class_label_overlap": class_label_overlap,
                "curation_policy": "balanced_latest_feedback_labels" if balance else "latest_feedback_labels",
                "balance_applied": balance,
                "class_distribution_before": class_distribution_before,
                "class_distribution_after": class_distribution_after,
            },
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
        _persist_dataset_file_reference(
            client=client,
            dataset_id=dataset_id,
            s3_key=s3_key,
        )

        result_payload: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "requested_max_items": max_items,
            "qualifying_found": len(all_qualifying_items),
            "rows_written": int(len(dataframe)),
            "score_id": score_id,
            "scorecard_id": scorecard_id,
            "s3_key": s3_key,
            "balance_applied": balance,
            "class_list_used": class_list_used,
            "class_resolution_source": class_resolution_source,
            "resolved_final_classes": class_list_used,
            "observed_label_set": observed_label_set,
            "class_label_overlap": class_label_overlap,
            "class_distribution_before": class_distribution_before,
            "class_distribution_after": class_distribution_after,
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
