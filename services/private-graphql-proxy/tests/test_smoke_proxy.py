import os
import sys
import types
import uuid

import pytest
import requests


pytestmark = pytest.mark.integration


def proxy_url() -> str:
    return os.getenv("PLEXUS_API_URL", "http://localhost:18080/graphql")


def proxy_headers() -> dict[str, str]:
    return {"x-api-key": os.getenv("PLEXUS_API_KEY", "local-smoke-key")}


def execute(query: str, variables: dict | None = None) -> dict:
    response = requests.post(
        proxy_url(),
        json={"query": query, "variables": variables or {}},
        headers=proxy_headers(),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    assert "errors" not in payload, payload
    return payload["data"]


def test_private_models_round_trip_through_proxy():
    suffix = str(uuid.uuid4())
    account_id = f"smoke-account-{suffix}"
    item_id = f"smoke-item-{suffix}"
    score_result_id = f"smoke-score-result-{suffix}"
    feedback_item_id = f"smoke-feedback-item-{suffix}"
    scorecard_id = f"smoke-scorecard-{suffix}"
    score_id = f"smoke-score-{suffix}"
    cache_key = f"smoke-cache-{suffix}"

    item = execute(
        """
        mutation CreateItem($input: CreateItemInput!) {
            createItem(input: $input) { id accountId text externalId createdAt updatedAt }
        }
        """,
        {
            "input": {
                "id": item_id,
                "accountId": account_id,
                "text": "local private smoke item",
                "externalId": f"external-{suffix}",
                "isEvaluation": False,
                "createdByType": "prediction",
            }
        },
    )["createItem"]
    assert item["id"] == item_id

    identifier = execute(
        """
        mutation CreateIdentifier($input: CreateIdentifierInput!) {
            createIdentifier(input: $input) { itemId name value accountId position }
        }
        """,
        {
            "input": {
                "itemId": item_id,
                "name": "Smoke ID",
                "value": f"identifier-{suffix}",
                "accountId": account_id,
                "position": 0,
            }
        },
    )["createIdentifier"]
    assert identifier["itemId"] == item_id

    score_result = execute(
        """
        mutation CreateScoreResult($input: CreateScoreResultInput!) {
            createScoreResult(input: $input) { id itemId accountId scorecardId scoreId value type status }
        }
        """,
        {
            "input": {
                "id": score_result_id,
                "itemId": item_id,
                "accountId": account_id,
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "value": "Yes",
                "type": "prediction",
                "status": "COMPLETED",
            }
        },
    )["createScoreResult"]
    assert score_result["id"] == score_result_id

    feedback_item = execute(
        """
        mutation CreateFeedbackItem($input: CreateFeedbackItemInput!) {
            createFeedbackItem(input: $input) { id itemId accountId scorecardId scoreId cacheKey }
        }
        """,
        {
            "input": {
                "id": feedback_item_id,
                "itemId": item_id,
                "accountId": account_id,
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "cacheKey": cache_key,
                "initialAnswerValue": "Yes",
                "finalAnswerValue": "No",
            }
        },
    )["createFeedbackItem"]
    assert feedback_item["id"] == feedback_item_id

    assert execute(
        "query GetItem($id: ID!) { getItem(id: $id) { id text } }",
        {"id": item_id},
    )["getItem"]["text"] == "local private smoke item"

    identifier_items = execute(
        """
        query FindIdentifier($accountId: String!, $value: String!) {
            listIdentifierByAccountIdAndValue(accountId: $accountId, value: {eq: $value}) {
                items { itemId name value }
                nextToken
            }
        }
        """,
        {"accountId": account_id, "value": f"identifier-{suffix}"},
    )["listIdentifierByAccountIdAndValue"]["items"]
    assert identifier_items[0]["itemId"] == item_id

    score_items = execute(
        """
        query FindScoreResult($itemId: String!, $type: String!, $scoreId: String!) {
            listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt(
                itemId: $itemId,
                typeScoreIdUpdatedAt: {beginsWith: {type: $type, scoreId: $scoreId}},
                sortDirection: DESC,
                limit: 1
            ) {
                items { id itemId scoreId type }
                nextToken
            }
        }
        """,
        {"itemId": item_id, "type": "prediction", "scoreId": score_id},
    )["listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt"]["items"]
    assert score_items[0]["id"] == score_result_id

    feedback_items = execute(
        """
        query FindFeedback($cacheKey: String!) {
            listFeedbackItemByCacheKey(cacheKey: $cacheKey) {
                items { id cacheKey itemId }
                nextToken
            }
        }
        """,
        {"cacheKey": cache_key},
    )["listFeedbackItemByCacheKey"]["items"]
    assert feedback_items[0]["id"] == feedback_item_id


def test_seeded_item_read_paths_through_proxy():
    suffix = str(uuid.uuid4())
    account_id = f"item-read-account-{suffix}"
    score_id = f"item-read-score-{suffix}"
    item_id = f"item-read-{suffix}"
    external_id = f"item-read-external-{suffix}"

    seeded = execute(
        """
        mutation SeedItem($input: CreateItemInput!) {
            createItem(input: $input) {
                id
                accountId
                scoreId
                externalId
                text
                metadata
                createdAt
                updatedAt
            }
        }
        """,
        {
            "input": {
                "id": item_id,
                "accountId": account_id,
                "scoreId": score_id,
                "externalId": external_id,
                "text": "seeded local item read smoke",
                "metadata": {"source": "private-graphql-proxy-smoke", "suffix": suffix},
                "isEvaluation": False,
                "createdByType": "prediction",
            }
        },
    )["createItem"]
    assert seeded["id"] == item_id

    by_id = execute(
        """
        query GetSeededItem($id: ID!) {
            getItem(id: $id) {
                id
                accountId
                scoreId
                externalId
                text
                metadata
            }
        }
        """,
        {"id": item_id},
    )["getItem"]
    assert by_id["id"] == item_id
    assert by_id["text"] == "seeded local item read smoke"
    assert by_id["metadata"]["source"] == "private-graphql-proxy-smoke"

    by_account = execute(
        """
        query ItemsByAccount($accountId: String!) {
            listItemByAccountIdAndUpdatedAt(
                accountId: $accountId,
                sortDirection: DESC,
                limit: 5
            ) {
                items { id accountId externalId text }
                nextToken
            }
        }
        """,
        {"accountId": account_id},
    )["listItemByAccountIdAndUpdatedAt"]["items"]
    assert [item["id"] for item in by_account] == [item_id]

    by_score = execute(
        """
        query ItemsByScore($scoreId: String!) {
            listItemByScoreIdAndUpdatedAt(
                scoreId: $scoreId,
                sortDirection: DESC,
                limit: 5
            ) {
                items { id scoreId externalId text }
                nextToken
            }
        }
        """,
        {"scoreId": score_id},
    )["listItemByScoreIdAndUpdatedAt"]["items"]
    assert [item["id"] for item in by_score] == [item_id]

    by_external_id = execute(
        """
        query ItemByExternalId($accountId: String!, $externalId: String!) {
            listItemByAccountIdAndExternalId(
                accountId: $accountId,
                externalId: {eq: $externalId},
                limit: 1
            ) {
                items { id accountId externalId text }
                nextToken
            }
        }
        """,
        {"accountId": account_id, "externalId": external_id},
    )["listItemByAccountIdAndExternalId"]["items"]
    assert [item["id"] for item in by_external_id] == [item_id]


def test_score_result_can_be_created_for_seeded_item():
    suffix = str(uuid.uuid4())
    account_id = f"score-result-account-{suffix}"
    item_id = f"score-result-item-{suffix}"
    score_result_id = f"score-result-{suffix}"
    scorecard_id = f"score-result-scorecard-{suffix}"
    score_id = f"score-result-score-{suffix}"
    score_version_id = f"score-result-version-{suffix}"

    execute(
        """
        mutation SeedItem($input: CreateItemInput!) {
            createItem(input: $input) { id accountId text }
        }
        """,
        {
            "input": {
                "id": item_id,
                "accountId": account_id,
                "scoreId": score_id,
                "externalId": f"score-result-external-{suffix}",
                "text": "item that will receive a score result",
                "isEvaluation": False,
                "createdByType": "prediction",
            }
        },
    )

    created = execute(
        """
        mutation CreateScoreResult($input: CreateScoreResultInput!) {
            createScoreResult(input: $input) {
                id
                itemId
                accountId
                scorecardId
                scoreId
                scoreVersionId
                value
                explanation
                confidence
                metadata
                type
                status
            }
        }
        """,
        {
            "input": {
                "id": score_result_id,
                "itemId": item_id,
                "accountId": account_id,
                "scorecardId": scorecard_id,
                "scoreId": score_id,
                "scoreVersionId": score_version_id,
                "value": "Pass",
                "explanation": "Created by private GraphQL proxy smoke test",
                "confidence": 0.98,
                "metadata": {"source": "private-graphql-proxy-smoke", "suffix": suffix},
                "type": "prediction",
                "status": "COMPLETED",
                "code": "200",
            }
        },
    )["createScoreResult"]
    assert created["id"] == score_result_id
    assert created["itemId"] == item_id
    assert created["metadata"]["source"] == "private-graphql-proxy-smoke"

    by_id = execute(
        """
        query GetScoreResult($id: ID!) {
            getScoreResult(id: $id) {
                id
                itemId
                scoreId
                value
                status
            }
        }
        """,
        {"id": score_result_id},
    )["getScoreResult"]
    assert by_id == {
        "id": score_result_id,
        "itemId": item_id,
        "scoreId": score_id,
        "value": "Pass",
        "status": "COMPLETED",
    }

    by_item = execute(
        """
        query ScoreResultsByItem($itemId: String!) {
            listScoreResultByItemId(itemId: $itemId) {
                items { id itemId scoreId value status }
                nextToken
            }
        }
        """,
        {"itemId": item_id},
    )["listScoreResultByItemId"]["items"]
    assert [result["id"] for result in by_item] == [score_result_id]

    by_item_score_type = execute(
        """
        query ScoreResultsByItemScoreType($itemId: String!, $type: String!, $scoreId: String!) {
            listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt(
                itemId: $itemId,
                typeScoreIdUpdatedAt: {beginsWith: {type: $type, scoreId: $scoreId}},
                sortDirection: DESC,
                limit: 1
            ) {
                items { id itemId scoreId type value status }
                nextToken
            }
        }
        """,
        {"itemId": item_id, "type": "prediction", "scoreId": score_id},
    )["listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt"]["items"]
    assert [result["id"] for result in by_item_score_type] == [score_result_id]


def test_control_plane_cache_smoke_read_only():
    required = {
        "PLEXUS_PROXY_SMOKE_ACCOUNT_ID": os.getenv("PLEXUS_PROXY_SMOKE_ACCOUNT_ID"),
        "PLEXUS_PROXY_SMOKE_SCORECARD_ID": os.getenv("PLEXUS_PROXY_SMOKE_SCORECARD_ID"),
        "PLEXUS_PROXY_SMOKE_SCORE_ID": os.getenv("PLEXUS_PROXY_SMOKE_SCORE_ID"),
        "PLEXUS_PROXY_SMOKE_SCORE_VERSION_ID": os.getenv("PLEXUS_PROXY_SMOKE_SCORE_VERSION_ID"),
        "PLEXUS_PROXY_SMOKE_EVALUATION_ID": os.getenv("PLEXUS_PROXY_SMOKE_EVALUATION_ID"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"missing production read-only smoke fixture env vars: {', '.join(missing)}")

    query = """
    query ControlSmoke($accountId: ID!, $scorecardId: ID!, $scoreId: ID!, $scoreVersionId: ID!, $evaluationId: ID!) {
        getAccount(id: $accountId) { id name key }
        getScorecard(id: $scorecardId) { id name key }
        getScore(id: $scoreId) { id name key }
        getScoreVersion(id: $scoreVersionId) { id }
        getEvaluation(id: $evaluationId) { id type status }
    }
    """
    variables = {
        "accountId": required["PLEXUS_PROXY_SMOKE_ACCOUNT_ID"],
        "scorecardId": required["PLEXUS_PROXY_SMOKE_SCORECARD_ID"],
        "scoreId": required["PLEXUS_PROXY_SMOKE_SCORE_ID"],
        "scoreVersionId": required["PLEXUS_PROXY_SMOKE_SCORE_VERSION_ID"],
        "evaluationId": required["PLEXUS_PROXY_SMOKE_EVALUATION_ID"],
    }

    first = execute(query, variables)
    second = execute(query, variables)

    assert first["getAccount"]["id"] == variables["accountId"]
    assert second == first


def test_existing_plexus_client_can_target_proxy():
    if "plexus.utils" not in sys.modules:
        utils_stub = types.ModuleType("plexus.utils")
        utils_stub.truncate_dict_strings_inner = lambda value, *args, **kwargs: value
        sys.modules["plexus.utils"] = utils_stub

    try:
        from plexus.dashboard.api.client import PlexusDashboardClient
        from plexus.dashboard.api.models.item import Item
    except Exception as exc:
        pytest.skip(f"existing Plexus client dependencies are not installed: {exc}")

    suffix = str(uuid.uuid4())
    client = PlexusDashboardClient(api_url=proxy_url(), api_key=os.getenv("PLEXUS_API_KEY", "local-smoke-key"))
    item = Item.create(
        client,
        evaluationId="prediction-default",
        deterministic_id=f"client-smoke-item-{suffix}",
        accountId=f"client-smoke-account-{suffix}",
        text="created through existing Plexus client",
        isEvaluation=False,
        createdByType="prediction",
    )

    fetched = Item.get_by_id(item.id, client)
    assert fetched.text == "created through existing Plexus client"
