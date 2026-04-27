"""
Build deterministic single-score reference datasets from scorecard examples.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union

import pandas as pd
from pydantic import Field, validator

from plexus.CustomLogging import logging
from plexus.data.DataCache import DataCache
from plexus.data.FeedbackItems import FeedbackItems
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
from plexus.cli.shared.client_utils import create_client
from plexus.cli.report.utils import resolve_account_id_for_command


class ScorecardExampleReferenceItems(DataCache):
    """
    Data cache that materializes deterministic reference rows from scorecard example items.
    """

    class Parameters(DataCache.Parameters):
        scorecard: Union[str, int] = Field(..., description="Scorecard identifier")
        score: Union[str, int] = Field(..., description="Score identifier")
        days: Optional[int] = Field(None, description="Optional lookback window for feedback labels")
        limit: Optional[int] = Field(None, description="Optional cap on number of example items")
        column_mappings: Optional[Dict[str, str]] = Field(None, description="Optional score-name column mappings")
        item_config: Optional[Dict] = Field(None, description="Optional item pipeline config")

        @validator("days")
        def days_must_be_positive(cls, v):
            if v is not None and v <= 0:
                raise ValueError("days must be positive")
            return v

        @validator("limit")
        def limit_must_be_positive(cls, v):
            if v is not None and v <= 0:
                raise ValueError("limit must be positive")
            return v

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.client = create_client()
        self.account_id = resolve_account_id_for_command(self.client, None)

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> datetime:
        if not value:
            return datetime.fromtimestamp(0, tz=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _resolve_identifiers(self) -> Tuple[str, str]:
        scorecard_id = resolve_scorecard_identifier(self.client, str(self.parameters.scorecard))
        if not scorecard_id:
            raise ValueError(f"Could not resolve scorecard identifier: {self.parameters.scorecard}")
        score_id = resolve_score_identifier(self.client, scorecard_id, str(self.parameters.score))
        if not score_id:
            raise ValueError(f"Could not resolve score identifier '{self.parameters.score}' within scorecard '{scorecard_id}'")
        return scorecard_id, score_id

    def _resolve_score_name(self, score_id: str) -> str:
        result = self.client.execute(
            """
            query GetScoreName($id: ID!) {
                getScore(id: $id) {
                    id
                    name
                }
            }
            """,
            {"id": score_id},
        )
        return (result.get("getScore") or {}).get("name") or str(self.parameters.score)

    def _fetch_example_item_ids(self, scorecard_id: str) -> List[str]:
        query = """
        query ListExampleItems($scorecardId: ID!, $limit: Int, $nextToken: String) {
            listScorecardExampleItemByScorecardId(scorecardId: $scorecardId, limit: $limit, nextToken: $nextToken) {
                items {
                    itemId
                    addedAt
                }
                nextToken
            }
        }
        """
        item_ids: List[str] = []
        next_token = None
        while True:
            response = self.client.execute(
                query,
                {"scorecardId": scorecard_id, "limit": 1000, "nextToken": next_token},
            )
            payload = response.get("listScorecardExampleItemByScorecardId") or {}
            for item in payload.get("items") or []:
                item_id = item.get("itemId")
                if item_id:
                    item_ids.append(item_id)
            next_token = payload.get("nextToken")
            if not next_token:
                break
        # Deterministic order.
        item_ids = sorted(set(item_ids))
        if self.parameters.limit is not None:
            item_ids = item_ids[: self.parameters.limit]
        return item_ids

    def _fetch_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        query = """
        query GetItem($id: ID!) {
            getItem(id: $id) {
                id
                externalId
                description
                text
                accountId
                scoreId
                evaluationId
                updatedAt
                createdAt
                isEvaluation
                createdByType
                identifiers
                metadata
                attachedFiles
            }
        }
        """
        response = self.client.execute(query, {"id": item_id})
        return response.get("getItem")

    def _fetch_feedback_candidates_for_item(
        self,
        scorecard_id: str,
        score_id: str,
        item_id: str,
    ) -> List[FeedbackItem]:
        query = """
        query ListFeedbackForItem($filter: ModelFeedbackItemFilterInput, $limit: Int) {
            listFeedbackItems(filter: $filter, limit: $limit) {
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
                        externalId
                        description
                        text
                        accountId
                        scoreId
                        evaluationId
                        updatedAt
                        createdAt
                        isEvaluation
                        createdByType
                        identifiers
                        metadata
                        attachedFiles
                    }
                    scoreResults {
                        items {
                            id
                            value
                            createdAt
                            updatedAt
                        }
                    }
                }
            }
        }
        """
        response = self.client.execute(
            query,
            {
                "filter": {
                    "and": [
                        {"scorecardId": {"eq": scorecard_id}},
                        {"scoreId": {"eq": score_id}},
                        {"itemId": {"eq": item_id}},
                    ]
                },
                "limit": 200,
            },
        )
        candidates: List[FeedbackItem] = []
        for item in (response.get("listFeedbackItems") or {}).get("items") or []:
            try:
                feedback_item = FeedbackItem.from_dict(item, client=self.client)
                candidates.append(feedback_item)
            except Exception:
                continue
        return candidates

    def _choose_latest_feedback_item(self, candidates: List[FeedbackItem]) -> Optional[FeedbackItem]:
        if not candidates:
            return None
        threshold = None
        if self.parameters.days is not None:
            threshold = datetime.now(timezone.utc) - timedelta(days=self.parameters.days)

        valid: List[FeedbackItem] = []
        for item in candidates:
            edited_at = item.editedAt or item.updatedAt or item.createdAt
            if threshold and edited_at and edited_at < threshold:
                continue
            valid.append(item)
        if not valid:
            return None
        return max(
            valid,
            key=lambda x: x.editedAt or x.updatedAt or x.createdAt or datetime.fromtimestamp(0, tz=timezone.utc),
        )

    def _fetch_latest_score_result_value(self, score_id: str, item_id: str) -> Optional[str]:
        query = """
        query ListScoreResultsForItem($filter: ModelScoreResultFilterInput, $limit: Int) {
            listScoreResults(filter: $filter, limit: $limit) {
                items {
                    id
                    value
                    createdAt
                    updatedAt
                }
            }
        }
        """
        response = self.client.execute(
            query,
            {
                "filter": {
                    "and": [
                        {"scoreId": {"eq": score_id}},
                        {"itemId": {"eq": item_id}},
                    ]
                },
                "limit": 200,
            },
        )
        results = (response.get("listScoreResults") or {}).get("items") or []
        if not results:
            return None
        latest = max(
            results,
            key=lambda x: self._parse_datetime(x.get("updatedAt") or x.get("createdAt")),
        )
        return latest.get("value")

    def _build_synthetic_feedback_item(
        self,
        scorecard_id: str,
        score_id: str,
        item_id: str,
    ) -> Optional[FeedbackItem]:
        item_payload = self._fetch_item_by_id(item_id)
        if not item_payload:
            return None
        item = FeedbackItem.from_dict(
            {
                "id": f"synthetic-{item_id}",
                "accountId": self.account_id,
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "itemId": item_id,
                "cacheKey": f"synthetic-{item_id}",
                "initialAnswerValue": self._fetch_latest_score_result_value(score_id, item_id),
                "finalAnswerValue": None,
                "initialCommentValue": "",
                "finalCommentValue": "",
                "editCommentValue": "",
                "isAgreement": None,
                "isInvalid": None,
                "editedAt": datetime.now(timezone.utc).isoformat(),
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "item": item_payload,
            },
            client=self.client,
        )
        return item

    def load_dataframe(self, *args, **kwargs) -> pd.DataFrame:
        scorecard_id, score_id = self._resolve_identifiers()
        score_name = self._resolve_score_name(score_id)
        example_item_ids = self._fetch_example_item_ids(scorecard_id)

        resolved_feedback_items: List[FeedbackItem] = []
        for item_id in example_item_ids:
            candidates = self._fetch_feedback_candidates_for_item(scorecard_id, score_id, item_id)
            latest_feedback = self._choose_latest_feedback_item(candidates)
            if latest_feedback is not None:
                resolved_feedback_items.append(latest_feedback)
                continue

            synthetic = self._build_synthetic_feedback_item(scorecard_id, score_id, item_id)
            if synthetic is not None:
                resolved_feedback_items.append(synthetic)

        feedback_rows_builder = FeedbackItems(
            scorecard=self.parameters.scorecard,
            score=self.parameters.score,
            days=self.parameters.days,
            limit=self.parameters.limit,
            column_mappings=self.parameters.column_mappings,
            item_config=self.parameters.item_config,
        )
        dataframe = feedback_rows_builder._create_dataset_rows(resolved_feedback_items, score_name)
        dataframe.attrs["reference_builder"] = {
            "source": "scorecard_example_items",
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "example_item_count": len(example_item_ids),
            "resolved_feedback_item_count": len(resolved_feedback_items),
        }
        logging.info(
            "Built scorecard-example reference dataframe: %s rows from %s example items.",
            len(dataframe),
            len(example_item_ids),
        )
        return dataframe
