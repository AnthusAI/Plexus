from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from behave import given, then, when
from fastapi.testclient import TestClient

from proxy import app as proxy_app
from proxy.config import Settings
from proxy.store_factory import create_store


def _configure_virtuus_env(context) -> None:
    context.tmpdir = tempfile.mkdtemp(prefix="virtuus-proxy-")
    os.environ["PLEXUS_STORE"] = "virtuus"
    os.environ["PLEXUS_DATA_DIR"] = context.tmpdir
    os.environ["PLEXUS_BACKEND_MODE"] = "local"
    os.environ["PLEXUS_PROXY_UPSTREAM_DISABLED"] = "true"
    os.environ["PLEXUS_PROXY_AUTH_MODE"] = "trusted_open"
    os.environ.pop("PLEXUS_PROXY_DATABASE_URL", None)


def _bind_app(context) -> None:
    settings = Settings.from_env()
    proxy_app.settings = settings
    proxy_app.store = create_store(settings)
    proxy_app.store.initialize()
    context.client = TestClient(proxy_app.app)
    context.store = proxy_app.store
    context.data_dir = context.tmpdir


@given("a local GraphQL process configured for Virtuus file storage")
def local_graphql_virtuus(context):
    _configure_virtuus_env(context)
    _bind_app(context)


@given("no database server is running")
def no_database_server(context):
    assert os.getenv("PLEXUS_PROXY_DATABASE_URL") is None
    response = context.client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@given("Items stored as Virtuus files")
def items_stored_as_virtuus_files(context):
    _configure_virtuus_env(context)
    _bind_app(context)
    context.item_id = "restart-item-1"
    context.account_id = "restart-account-1"
    context.item_text = "survives restart"
    response = context.client.post(
        "/graphql",
        json={
            "query": """
            mutation CreateItem($input: CreateItemInput!) {
                createItem(input: $input) { id accountId text }
            }
            """,
            "variables": {
                "input": {
                    "id": context.item_id,
                    "accountId": context.account_id,
                    "text": context.item_text,
                }
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload, payload
    assert payload["data"]["createItem"]["id"] == context.item_id


@when("I create an Item through GraphQL")
def create_item_through_graphql(context):
    context.item_id = "virtuus-item-1"
    context.account_id = "virtuus-account-1"
    context.item_text = "virtuus file backed"
    response = context.client.post(
        "/graphql",
        json={
            "query": """
            mutation CreateItem($input: CreateItemInput!) {
                createItem(input: $input) { id accountId text }
            }
            """,
            "variables": {
                "input": {
                    "id": context.item_id,
                    "accountId": context.account_id,
                    "text": context.item_text,
                }
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload, payload
    context.create_response = payload["data"]["createItem"]


@when("I create an Identifier through GraphQL")
def create_identifier_through_graphql(context):
    context.item_id = "virtuus-item-for-identifier"
    context.identifier_name = "Test Identifier"
    context.identifier_value = "identifier-composite-value"
    context.account_id = "virtuus-account-identifier"
    response = context.client.post(
        "/graphql",
        json={
            "query": """
            mutation CreateIdentifier($input: CreateIdentifierInput!) {
                createIdentifier(input: $input) { itemId name value accountId position }
            }
            """,
            "variables": {
                "input": {
                    "itemId": context.item_id,
                    "name": context.identifier_name,
                    "value": context.identifier_value,
                    "accountId": context.account_id,
                    "position": 0,
                }
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload, payload
    identifier = payload["data"]["createIdentifier"]
    assert identifier["itemId"] == context.item_id
    assert identifier["name"] == context.identifier_name
    assert identifier["value"] == context.identifier_value


@when("the FastAPI process restarts")
def fastapi_restarts(context):
    _bind_app(context)


@then("I can read that Item through GraphQL")
def read_item_through_graphql(context):
    response = context.client.post(
        "/graphql",
        json={
            "query": """
            query GetItem($id: ID!) {
                getItem(id: $id) { id accountId text }
            }
            """,
            "variables": {"id": context.item_id},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload, payload
    item = payload["data"]["getItem"]
    assert item["id"] == context.item_id
    assert item["accountId"] == context.account_id
    assert item["text"] == context.item_text


@then("I can read that Identifier through GraphQL")
def read_identifier_through_graphql(context):
    response = context.client.post(
        "/graphql",
        json={
            "query": """
            query GetIdentifier($itemId: ID!, $name: ID!) {
                getIdentifier(itemId: $itemId, name: $name) { itemId name value accountId }
            }
            """,
            "variables": {
                "itemId": context.item_id,
                "name": context.identifier_name,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload, payload
    identifier = payload["data"]["getIdentifier"]
    assert identifier["itemId"] == context.item_id
    assert identifier["name"] == context.identifier_name
    assert identifier["value"] == context.identifier_value
    assert identifier["accountId"] == context.account_id


@then("a JSON file on disk contains the Item document")
def json_file_contains_item(context):
    item_dir = Path(context.data_dir) / "item"
    assert item_dir.is_dir()
    json_files = list(item_dir.glob("*.json"))
    assert json_files, "expected at least one Item JSON file"
    matching = [
        path
        for path in json_files
        if json.loads(path.read_text(encoding="utf-8")).get("id") == context.item_id
    ]
    assert matching, f"no JSON file contained item id {context.item_id}"
    document = json.loads(matching[0].read_text(encoding="utf-8"))
    assert document["text"] == context.item_text


@then("a JSON file on disk contains the Identifier document")
def json_file_contains_identifier(context):
    identifier_dir = Path(context.data_dir) / "identifier"
    assert identifier_dir.is_dir()
    json_files = list(identifier_dir.glob("*.json"))
    assert json_files, "expected at least one Identifier JSON file"
    matching = [
        path
        for path in json_files
        if json.loads(path.read_text(encoding="utf-8")).get("itemId") == context.item_id
        and json.loads(path.read_text(encoding="utf-8")).get("name") == context.identifier_name
    ]
    assert matching, (
        f"no JSON file contained identifier itemId={context.item_id} "
        f"name={context.identifier_name}"
    )
    document = json.loads(matching[0].read_text(encoding="utf-8"))
    assert document["itemId"] == context.item_id
    assert document["name"] == context.identifier_name
    assert document["value"] == context.identifier_value


@then("those records are still available through GraphQL")
def records_still_available(context):
    response = context.client.post(
        "/graphql",
        json={
            "query": """
            query GetItem($id: ID!) {
                getItem(id: $id) { id accountId text }
            }
            """,
            "variables": {"id": context.item_id},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload, payload
    item = payload["data"]["getItem"]
    assert item["id"] == context.item_id
    assert item["text"] == context.item_text
