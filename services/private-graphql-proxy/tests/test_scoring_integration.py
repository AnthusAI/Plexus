from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
import requests


pytestmark = pytest.mark.integration


PRIVATE_ROOT_PREFIXES = (
    "getItem",
    "listItem",
    "createItem",
    "updateItem",
    "deleteItem",
    "getIdentifier",
    "listIdentifier",
    "createIdentifier",
    "updateIdentifier",
    "deleteIdentifier",
    "getScoreResult",
    "listScoreResult",
    "createScoreResult",
    "updateScoreResult",
    "deleteScoreResult",
    "getFeedbackItem",
    "listFeedbackItem",
    "createFeedbackItem",
    "updateFeedbackItem",
    "deleteFeedbackItem",
)


def proxy_url() -> str:
    return os.getenv("PLEXUS_API_URL", "http://localhost:18080/graphql")


def proxy_api_key() -> str:
    return os.getenv("PLEXUS_API_KEY", "local-smoke-key")


def proxy_base_url() -> str:
    parsed = urlparse(proxy_url())
    return f"{parsed.scheme}://{parsed.netloc}"


def proxy_headers() -> dict[str, str]:
    return {"x-api-key": proxy_api_key()}


def execute(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.post(
        proxy_url(),
        json={"query": query, "variables": variables or {}},
        headers=proxy_headers(),
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    assert "errors" not in payload, payload
    return payload


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"missing {name}")
    return value


def resolve_account_id(account_key: str) -> str:
    payload = execute(
        """
        query ResolveAccount($key: String!) {
            listAccountByKey(key: $key) {
                items {
                    id
                    key
                    name
                }
                nextToken
            }
        }
        """,
        {"key": account_key},
    )
    items = payload["data"]["listAccountByKey"]["items"]
    assert items, f"no account found for PLEXUS_ACCOUNT_KEY={account_key}"
    return items[0]["id"]


def run_json_command(command: list[str], env: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        env=env,
        cwd=Path(__file__).resolve().parents[3],
        text=True,
        capture_output=True,
        timeout=int(os.getenv("PLEXUS_PROXY_SCORING_TIMEOUT_SECONDS", "300")),
    )
    assert result.returncode == 0, (
        "command failed\n"
        f"command: {' '.join(command)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def parse_prediction_json(stdout: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(stdout):
        if char != "[":
            continue
        try:
            parsed, end = decoder.raw_decode(stdout[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list) and not stdout[index + end :].strip():
            return parsed
    raise AssertionError(f"could not find JSON prediction array in stdout:\n{stdout}")


def test_real_prediction_reads_seeded_postgres_items_through_proxy():
    account_key = required_env("PLEXUS_ACCOUNT_KEY")
    scorecard = required_env("PLEXUS_PROXY_SCORING_SCORECARD")
    score = required_env("PLEXUS_PROXY_SCORING_SCORE")
    fixture_limit = int(os.getenv("PLEXUS_PROXY_SCORING_FIXTURE_LIMIT", "3"))
    fixture_dataset = os.getenv("PLEXUS_PROXY_SCORING_DATASET", "fancyzhx/ag_news")
    fixture_split = os.getenv("PLEXUS_PROXY_SCORING_SPLIT", "test")
    fixture_start = int(os.getenv("PLEXUS_PROXY_SCORING_START", "0"))

    account_id = os.getenv("PLEXUS_PROXY_SCORING_ACCOUNT_ID") or resolve_account_id(account_key)
    score_id = os.getenv("PLEXUS_PROXY_SCORING_SCORE_ID")
    repo_root = Path(__file__).resolve().parents[3]

    common_env = os.environ.copy()
    common_env["PYTHONPATH"] = f"{repo_root}:{repo_root / 'services/private-graphql-proxy'}"
    common_env["PLEXUS_API_URL"] = proxy_url()
    common_env["PLEXUS_API_KEY"] = proxy_api_key()
    common_env["PLEXUS_ACCOUNT_KEY"] = account_key
    common_env.pop("NEXT_PUBLIC_PLEXUS_API_URL", None)
    common_env.pop("NEXT_PUBLIC_PLEXUS_API_KEY", None)

    seed_output = run_json_command(
        [
            sys.executable,
            str(repo_root / "services/private-graphql-proxy/scripts/seed_huggingface_items.py"),
            "--proxy-url",
            proxy_url(),
            "--api-key",
            proxy_api_key(),
            "--account-id",
            account_id,
            "--dataset",
            fixture_dataset,
            "--split",
            fixture_split,
            "--start",
            str(fixture_start),
            "--limit",
            str(fixture_limit),
            "--prefix",
            os.getenv("PLEXUS_PROXY_SCORING_FIXTURE_PREFIX", "proxy-scoring-ag-news"),
            *(["--score-id", score_id] if score_id else []),
        ],
        common_env,
    )
    seeded_items = seed_output["items"]
    assert len(seeded_items) == fixture_limit

    first_identifier = seeded_items[0]["identifierValue"]
    verification = execute(
        """
        query VerifySeededPrivateRows($itemId: ID!, $accountId: String!, $identifierValue: String!) {
            getItem(id: $itemId) {
                id
                accountId
                text
                metadata
            }
            listIdentifierByAccountIdAndValue(
                accountId: $accountId,
                value: {eq: $identifierValue},
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
            listItemByAccountIdAndUpdatedAt(
                accountId: $accountId,
                sortDirection: DESC,
                limit: 10
            ) {
                items {
                    id
                    accountId
                    externalId
                }
                nextToken
            }
        }
        """,
        {
            "itemId": seeded_items[0]["id"],
            "accountId": account_id,
            "identifierValue": first_identifier,
        },
    )
    assert verification["data"]["getItem"]["id"] == seeded_items[0]["id"]
    assert verification["data"]["listIdentifierByAccountIdAndValue"]["items"][0]["itemId"] == seeded_items[0]["id"]
    assert "getItem" in verification["extensions"]["proxy"]["private"]
    assert "listIdentifierByAccountIdAndValue" in verification["extensions"]["proxy"]["private"]
    assert "listItemByAccountIdAndUpdatedAt" in verification["extensions"]["proxy"]["private"]

    with tempfile.TemporaryDirectory(prefix="plexus-proxy-scorecards-") as cache_dir:
        predict_env = common_env.copy()
        predict_env["SCORECARD_CACHE_DIR"] = cache_dir
        predict_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "plexus",
                "predict",
                "--scorecard",
                scorecard,
                "--score",
                score,
                "--items",
                ",".join(item["identifierValue"] for item in seeded_items),
                "--format",
                "json",
            ],
            cwd=repo_root,
            env=predict_env,
            text=True,
            capture_output=True,
            timeout=int(os.getenv("PLEXUS_PROXY_SCORING_TIMEOUT_SECONDS", "300")),
        )
    assert predict_result.returncode == 0, (
        "plexus predict failed\n"
        f"stdout:\n{predict_result.stdout}\n"
        f"stderr:\n{predict_result.stderr}"
    )
    predictions = parse_prediction_json(predict_result.stdout)
    assert len(predictions) == len(seeded_items)
    assert {result["item_id"] for result in predictions} == {item["id"] for item in seeded_items}
    for result in predictions:
        assert result["scores"], result
        assert result["scores"][0]["name"] == score

    debug_response = requests.get(
        f"{proxy_base_url()}/debug/upstream-requests",
        timeout=30,
    )
    debug_response.raise_for_status()
    upstream_requests = debug_response.json()
    assert upstream_requests, "expected at least one forwarded control-plane read"
    for request in upstream_requests:
        forwarded_roots = request["root_fields"]
        assert forwarded_roots
        for root in forwarded_roots:
            assert not root.startswith(PRIVATE_ROOT_PREFIXES), request
