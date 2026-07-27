#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import requests


DEFAULT_DATASET = "apptek-com/apptek_callcenter_dialogues"
DEFAULT_SPLIT = "test"
DEFAULT_IDENTIFIER_NAME = "Hugging Face Fixture ID"
DEFAULT_PREFIX = "proxy-call-center"
HF_DATASETS_SERVER_ROWS_URL = "https://datasets-server.huggingface.co/rows"
HF_DATASETS_SERVER_MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class SeededFixture:
    id: str
    external_id: str
    identifier_name: str
    identifier_value: str
    label: int | str | None
    label_name: str | None
    row_index: int
    text_preview: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "externalId": self.external_id,
            "identifierName": self.identifier_name,
            "identifierValue": self.identifier_value,
            "label": self.label,
            "labelName": self.label_name,
            "rowIndex": self.row_index,
            "textPreview": self.text_preview,
        }


class GraphQLClient:
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.post(
            self.url,
            json={"query": query, "variables": variables or {}},
            headers={"x-api-key": self.api_key},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(json.dumps(payload["errors"], indent=2))
        return payload["data"]


def stable_fixture_id(prefix: str, dataset_name: str, split: str, row_index: int) -> str:
    digest = hashlib.sha256(f"{dataset_name}:{split}:{row_index}".encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:16]}"


def label_name_for(row: dict[str, Any], label_names: list[str] | tuple[str, ...]) -> str | None:
    label = row.get("label")
    if label is None:
        return None
    try:
        return label_names[int(label)]
    except (IndexError, TypeError, ValueError):
        return str(label)


def normalized_label(value: Any) -> int | str | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def resolve_label_names(dataset: Any) -> list[str] | tuple[str, ...]:
    label_feature = getattr(dataset, "features", {}).get("label")
    names = getattr(label_feature, "names", None)
    if names:
        return list(names)
    return ()


def load_rows_from_datasets_server(
    dataset_name: str,
    split: str,
    start: int,
    limit: int,
) -> tuple[Any, list[dict[str, Any]]]:
    """Fetch an exact bounded slice without downloading the complete Hub dataset."""
    rows: list[dict[str, Any]] = []
    for offset in range(start, start + limit, HF_DATASETS_SERVER_MAX_PAGE_SIZE):
        page_size = min(HF_DATASETS_SERVER_MAX_PAGE_SIZE, start + limit - offset)
        response = requests.get(
            HF_DATASETS_SERVER_ROWS_URL,
            params={
                "dataset": dataset_name,
                "config": "default",
                "split": split,
                "offset": offset,
                "length": page_size,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        page = payload.get("rows")
        if not isinstance(page, list):
            raise RuntimeError("Hugging Face datasets-server response is missing rows.")
        rows.extend(entry["row"] for entry in page if isinstance(entry.get("row"), dict))
        if len(page) < page_size:
            break
    if len(rows) != limit:
        raise RuntimeError(
            f"Hugging Face datasets-server returned {len(rows)} rows; expected {limit}."
        )
    return SimpleNamespace(features={}), rows


def load_rows(
    dataset_name: str,
    split: str,
    start: int,
    limit: int,
    source: str = "datasets",
) -> tuple[Any, list[dict[str, Any]]]:
    if source == "datasets-server":
        return load_rows_from_datasets_server(dataset_name, split, start, limit)
    if source != "datasets":
        raise ValueError(f"Unsupported source: {source}")
    try:
        from datasets import Features, Value, load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "The Hugging Face 'datasets' package is required. "
            "Install the full Plexus dependencies or run the scoring integration Compose profile."
        ) from exc

    load_kwargs: dict[str, Any] = {}
    if dataset_name == DEFAULT_DATASET:
        # The default call-center dataset includes audio, but this seeder only
        # needs transcript text. Explicit features avoid audio codec requirements.
        load_kwargs["features"] = Features(
            {
                "text": Value("string"),
                "domain": Value("string"),
                "gender": Value("string"),
                "accent": Value("string"),
            }
        )
    dataset = load_dataset(dataset_name, split=f"{split}[{start}:{start + limit}]", **load_kwargs)
    return dataset, [dict(row) for row in dataset]


def create_item(client: GraphQLClient, input_doc: dict[str, Any]) -> dict[str, Any]:
    return client.execute(
        """
        mutation SeedFixtureItem($input: CreateItemInput!) {
            createItem(input: $input) {
                id
                accountId
                scoreId
                externalId
                text
                metadata
                isEvaluation
                createdByType
                createdAt
                updatedAt
            }
        }
        """,
        {"input": input_doc},
    )["createItem"]


def create_identifier(client: GraphQLClient, input_doc: dict[str, Any]) -> dict[str, Any]:
    return client.execute(
        """
        mutation SeedFixtureIdentifier($input: CreateIdentifierInput!) {
            createIdentifier(input: $input) {
                itemId
                name
                value
                accountId
                position
                createdAt
                updatedAt
            }
        }
        """,
        {"input": input_doc},
    )["createIdentifier"]


def create_feedback_item(client: GraphQLClient, input_doc: dict[str, Any]) -> dict[str, Any]:
    return client.execute(
        """
        mutation SeedFixtureFeedbackItem($input: CreateFeedbackItemInput!) {
            createFeedbackItem(input: $input) {
                id
                itemId
                finalAnswerValue
            }
        }
        """,
        {"input": input_doc},
    )["createFeedbackItem"]


def verify_fixture(client: GraphQLClient, fixture: SeededFixture, account_id: str) -> None:
    item = client.execute(
        """
        query VerifyFixtureItem($id: ID!, $accountId: String!, $value: String!) {
            getItem(id: $id) {
                id
                accountId
                externalId
                text
                metadata
            }
            listIdentifierByAccountIdAndValue(
                accountId: $accountId,
                value: {eq: $value},
                limit: 1
            ) {
                items {
                    itemId
                    name
                    value
                    accountId
                }
                nextToken
            }
        }
        """,
        {"id": fixture.id, "accountId": account_id, "value": fixture.identifier_value},
    )
    if not item.get("getItem"):
        raise RuntimeError(f"Fixture item was not readable after seed: {fixture.id}")
    identifiers = item["listIdentifierByAccountIdAndValue"]["items"]
    if not identifiers or identifiers[0]["itemId"] != fixture.id:
        raise RuntimeError(f"Fixture identifier was not readable after seed: {fixture.identifier_value}")


def seed_fixtures(
    *,
    client: GraphQLClient,
    account_id: str,
    score_id: str | None,
    dataset_name: str,
    split: str,
    start: int,
    limit: int,
    prefix: str,
    identifier_name: str,
    verify: bool,
    source: str = "datasets",
    label_field: str | None = None,
    feedback_scorecard_id: str | None = None,
) -> list[SeededFixture]:
    if feedback_scorecard_id and (not score_id or not label_field):
        raise ValueError("Feedback seeding requires --score-id and --label-field.")

    dataset, rows = load_rows(dataset_name, split, start, limit, source=source)
    label_names = resolve_label_names(dataset)
    seeded_at = datetime.now(timezone.utc).isoformat()

    seeded: list[SeededFixture] = []
    for offset, row in enumerate(rows):
        row_index = start + offset
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        item_id = stable_fixture_id(prefix, dataset_name, split, row_index)
        external_id = f"{item_id}-external"
        identifier_value = f"{item_id}-identifier"
        label = normalized_label(row.get(label_field) if label_field else row.get("label"))
        label_name = label_name_for({**row, "label": label}, label_names)
        if label_field and label is not None:
            label_name = str(label)
        metadata = {
            "source": "private-graphql-proxy-fixture",
            "dataset": dataset_name,
            "split": split,
            "row_index": row_index,
        }
        item_input = {
            "id": item_id,
            "accountId": account_id,
            "externalId": external_id,
            "text": text,
            "metadata": metadata,
            "evaluationId": "prediction-default",
            "isEvaluation": False,
            "createdByType": "prediction",
        }
        if score_id:
            item_input["scoreId"] = score_id

        create_item(client, item_input)
        create_identifier(
            client,
            {
                "itemId": item_id,
                "name": identifier_name,
                "value": identifier_value,
                "accountId": account_id,
                "position": offset,
            },
        )
        if feedback_scorecard_id:
            create_feedback_item(
                client,
                {
                    "id": f"{item_id}-feedback",
                    "accountId": account_id,
                    "scorecardId": feedback_scorecard_id,
                    "scoreId": score_id,
                    "itemId": item_id,
                    "cacheKey": f"{score_id}:{item_id}",
                    "initialAnswerValue": label,
                    "finalAnswerValue": label,
                    "editedAt": seeded_at,
                    "isAgreement": True,
                    "isInvalid": False,
                },
            )

        fixture = SeededFixture(
            id=item_id,
            external_id=external_id,
            identifier_name=identifier_name,
            identifier_value=identifier_value,
            label=label,
            label_name=label_name,
            row_index=row_index,
            text_preview=text[:120],
        )
        if verify:
            verify_fixture(client, fixture, account_id)
        seeded.append(fixture)

    return seeded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed Hugging Face call-center transcript rows as private proxy Items."
    )
    parser.add_argument("--proxy-url", default=os.getenv("PLEXUS_API_URL", "http://localhost:18080/graphql"))
    parser.add_argument("--api-key", default=os.getenv("PLEXUS_API_KEY", "local-smoke-key"))
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--score-id")
    parser.add_argument("--dataset", default=os.getenv("PLEXUS_PROXY_FIXTURE_DATASET", DEFAULT_DATASET))
    parser.add_argument("--split", default=os.getenv("PLEXUS_PROXY_FIXTURE_SPLIT", DEFAULT_SPLIT))
    parser.add_argument("--start", type=int, default=int(os.getenv("PLEXUS_PROXY_FIXTURE_START", "0")))
    parser.add_argument("--limit", type=int, default=int(os.getenv("PLEXUS_PROXY_FIXTURE_LIMIT", "5")))
    parser.add_argument("--source", choices=("datasets", "datasets-server"), default="datasets")
    parser.add_argument("--label-field", help="Explicit source field to use as the evaluation label.")
    parser.add_argument("--feedback-scorecard-id", help="Create labeled FeedbackItems for this scorecard.")
    parser.add_argument("--prefix", default=os.getenv("PLEXUS_PROXY_FIXTURE_PREFIX", DEFAULT_PREFIX))
    parser.add_argument("--identifier-name", default=DEFAULT_IDENTIFIER_NAME)
    parser.add_argument("--no-verify", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = GraphQLClient(args.proxy_url, args.api_key)
    fixtures = seed_fixtures(
        client=client,
        account_id=args.account_id,
        score_id=args.score_id,
        dataset_name=args.dataset,
        split=args.split,
        start=args.start,
        limit=args.limit,
        prefix=args.prefix,
        identifier_name=args.identifier_name,
        verify=not args.no_verify,
        source=args.source,
        label_field=args.label_field,
        feedback_scorecard_id=args.feedback_scorecard_id,
    )
    json.dump({"items": [fixture.as_dict() for fixture in fixtures]}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
