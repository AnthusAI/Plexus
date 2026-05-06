#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import requests


AG_NEWS_LABELS = ("World", "Sports", "Business", "Sci/Tech")
DEFAULT_DATASET = "fancyzhx/ag_news"
DEFAULT_SPLIT = "test"
DEFAULT_IDENTIFIER_NAME = "Hugging Face Fixture ID"
DEFAULT_PREFIX = "proxy-ag-news"


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


def resolve_label_names(dataset: Any, dataset_name: str) -> list[str] | tuple[str, ...]:
    label_feature = getattr(dataset, "features", {}).get("label")
    names = getattr(label_feature, "names", None)
    if names:
        return list(names)
    if dataset_name == DEFAULT_DATASET:
        return AG_NEWS_LABELS
    return ()


def load_rows(dataset_name: str, split: str, start: int, limit: int) -> tuple[Any, list[dict[str, Any]]]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "The Hugging Face 'datasets' package is required. "
            "Install the full Plexus dependencies or run the scoring integration Compose profile."
        ) from exc

    dataset = load_dataset(dataset_name, split=f"{split}[{start}:{start + limit}]")
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
) -> list[SeededFixture]:
    dataset, rows = load_rows(dataset_name, split, start, limit)
    label_names = resolve_label_names(dataset, dataset_name)

    seeded: list[SeededFixture] = []
    for offset, row in enumerate(rows):
        row_index = start + offset
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        item_id = stable_fixture_id(prefix, dataset_name, split, row_index)
        external_id = f"{item_id}-external"
        identifier_value = f"{item_id}-identifier"
        label = normalized_label(row.get("label"))
        label_name = label_name_for({**row, "label": label}, label_names)
        metadata = {
            "source": "private-graphql-proxy-fixture",
            "dataset": dataset_name,
            "split": split,
            "row_index": row_index,
            "label": label,
            "label_name": label_name,
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
        description="Seed Hugging Face text-classification rows as private proxy Items."
    )
    parser.add_argument("--proxy-url", default=os.getenv("PLEXUS_API_URL", "http://localhost:18080/graphql"))
    parser.add_argument("--api-key", default=os.getenv("PLEXUS_API_KEY", "local-smoke-key"))
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--score-id")
    parser.add_argument("--dataset", default=os.getenv("PLEXUS_PROXY_FIXTURE_DATASET", DEFAULT_DATASET))
    parser.add_argument("--split", default=os.getenv("PLEXUS_PROXY_FIXTURE_SPLIT", DEFAULT_SPLIT))
    parser.add_argument("--start", type=int, default=int(os.getenv("PLEXUS_PROXY_FIXTURE_START", "0")))
    parser.add_argument("--limit", type=int, default=int(os.getenv("PLEXUS_PROXY_FIXTURE_LIMIT", "5")))
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
    )
    json.dump({"items": [fixture.as_dict() for fixture in fixtures]}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
