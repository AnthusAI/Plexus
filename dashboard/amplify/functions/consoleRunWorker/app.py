import logging
import json
import os
import time
from functools import lru_cache
from typing import Any, Dict

import boto3
from boto3.dynamodb.types import TypeDeserializer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

deserializer = TypeDeserializer()

# These imports pull in the Console's full procedure runtime and dashboard
# client. Lambda gives image functions only a small initialization window, and
# importing them here can exhaust that window before the handler starts. Keep
# them behind a cached, on-demand boundary instead.
PlexusDashboardClient = None


def _prepare_console_runtime_environment() -> None:
    """Avoid a second CloudWatch shipping client inside the Lambda responder.

    Lambda captures stdout/stderr in its managed log group.  The Console
    runtime's optional watchtower handler would perform extra CloudWatch setup
    during module imports, even though the native Lambda log path is already
    present.  Keep the runtime's redacting formatter while avoiding that
    duplicate remote setup.  An explicit configuration remains authoritative.
    """
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        os.environ.setdefault("PLEXUS_DISABLE_CLOUDWATCH_LOGS", "true")


@lru_cache(maxsize=1)
def _console_runtime():
    _prepare_console_runtime_environment()
    from plexus.console.chat_runtime import (
        PRODUCTION_RESPONSE_TARGET,
        build_response_owner,
        normalize_response_target,
        process_console_message,
        warm_console_runtime,
    )

    return {
        "production_response_target": PRODUCTION_RESPONSE_TARGET,
        "build_response_owner": build_response_owner,
        "normalize_response_target": normalize_response_target,
        "process_console_message": process_console_message,
        "warm_console_runtime": warm_console_runtime,
    }


def process_console_message(*args: Any, **kwargs: Any) -> bool:
    """Lazy compatibility wrapper used by the handler and focused tests."""
    return _console_runtime()["process_console_message"](*args, **kwargs)


def _dashboard_client_class():
    if PlexusDashboardClient is not None:
        return PlexusDashboardClient

    from plexus.dashboard.api.client import PlexusDashboardClient as dashboard_client_class

    return dashboard_client_class


@lru_cache(maxsize=1)
def _load_provider_credentials() -> None:
    secret_name = str(os.getenv("PLEXUS_CONFIG_SECRET_NAME") or "").strip()
    if not secret_name:
        raise RuntimeError("PLEXUS_CONFIG_SECRET_NAME is required")

    response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError("Plexus config secret must contain SecretString")

    try:
        config = json.loads(secret_string)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Plexus config secret must be valid JSON") from exc

    openai_api_key = str(config.get("openai-api-key") or "").strip()
    if not openai_api_key:
        raise RuntimeError("Plexus config secret is missing openai-api-key")
    os.environ["OPENAI_API_KEY"] = openai_api_key

    anthropic_api_key = str(config.get("anthropic-api-key") or "").strip()
    if anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key

    account_key = str(config.get("account-key") or "").strip()
    if account_key:
        os.environ["PLEXUS_ACCOUNT_KEY"] = account_key


def _deserialize_dynamo_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {key: deserializer.deserialize(value) for key, value in raw.items()}


@lru_cache(maxsize=1)
def _resolve_client() -> PlexusDashboardClient:
    api_url = str(os.getenv("PLEXUS_API_URL") or "").strip()
    if not api_url:
        raise RuntimeError("PLEXUS_API_URL is required")
    auth_mode = str(os.getenv("PLEXUS_GRAPHQL_AUTH_MODE") or "").strip().lower()
    if auth_mode != "iam":
        raise RuntimeError("PLEXUS_GRAPHQL_AUTH_MODE must be iam")
    account_key = str(os.getenv("PLEXUS_ACCOUNT_KEY") or "").strip()
    from plexus.dashboard.api.client import ClientContext

    context = ClientContext(account_key=account_key or None)
    return _dashboard_client_class()(api_url=api_url, context=context)


def fetch_console_message(client: PlexusDashboardClient, message_id: str) -> Dict[str, Any] | None:
    """Read a persisted Console message for the direct interactive path.

    The stream worker still receives the same insert as a recovery path.  The
    response-status conditional claim in process_console_message makes the two
    delivery mechanisms race-safe.
    """
    query = """
    query GetDirectConsoleMessage($id: ID!) {
      getChatMessage(id: $id) {
        id accountId sessionId procedureId role humanInteraction messageType
        content responseTarget responseStatus metadata createdAt
        session {
          id metadata scorecardId scoreId
          scorecard { id name }
          score { id name }
        }
      }
    }
    """
    result = client.execute(query, {"id": message_id})
    if not isinstance(result, dict):
        return None
    data = result.get("data")
    message = data.get("getChatMessage") if isinstance(data, dict) else result.get("getChatMessage")
    return message if isinstance(message, dict) else None


@lru_cache(maxsize=1)
def _warm_interactive_runtime() -> None:
    """Prepare immutable Console runtime state before an interactive request."""
    _load_provider_credentials()
    client = _resolve_client()
    _console_runtime()["warm_console_runtime"](client)


if str(os.getenv("PLEXUS_EAGER_CONSOLE_RUNTIME") or "").strip().lower() == "true":
    _warm_interactive_runtime()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    direct_message_id = str(event.get("directMessageId") or "").strip()
    if not direct_message_id:
        logger.info("No direct Console message to process")
        return {"processed": 0, "skipped": 0, "batchItemFailures": []}

    runtime = _console_runtime()
    expected_target = runtime["normalize_response_target"](
        os.getenv("CONSOLE_RESPONSE_TARGET") or runtime["production_response_target"]
    )
    request_id = getattr(context, "aws_request_id", None)
    previous_request_id = os.environ.get("PLEXUS_LAMBDA_REQUEST_ID")
    if request_id:
        os.environ["PLEXUS_LAMBDA_REQUEST_ID"] = request_id
    try:
        owner = runtime["build_response_owner"](expected_target, request_id=request_id)
        _load_provider_credentials()
        client = _resolve_client()

        fetch_started = time.monotonic()
        direct_message = fetch_console_message(client, direct_message_id)
        direct_message_fetch_ms = int(max(0.0, (time.monotonic() - fetch_started) * 1000.0))
        if not direct_message:
            logger.warning("Direct Console message %s was not found", direct_message_id)
            return {"processed": 0, "skipped": 1, "batchItemFailures": []}
        processed = int(process_console_message(
            client,
            direct_message,
            expected_target=expected_target,
            owner=owner,
            poll_context={"direct_message_fetch_ms": direct_message_fetch_ms},
        ))
        return {"processed": processed, "skipped": 1 - processed, "batchItemFailures": []}
    finally:
        if previous_request_id is None:
            os.environ.pop("PLEXUS_LAMBDA_REQUEST_ID", None)
        else:
            os.environ["PLEXUS_LAMBDA_REQUEST_ID"] = previous_request_id
