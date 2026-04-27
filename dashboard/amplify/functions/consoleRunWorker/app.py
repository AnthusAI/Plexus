import logging
import os
from typing import Any, Dict

from boto3.dynamodb.types import TypeDeserializer

from plexus.console.chat_runtime import (
    PRODUCTION_RESPONSE_TARGET,
    build_response_owner,
    normalize_response_target,
    process_console_message,
)
from plexus.dashboard.api.client import PlexusDashboardClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

deserializer = TypeDeserializer()


def _deserialize_dynamo_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {key: deserializer.deserialize(value) for key, value in raw.items()}


def _resolve_client() -> PlexusDashboardClient:
    api_url = str(os.getenv("PLEXUS_API_URL") or "").strip()
    api_key = str(os.getenv("PLEXUS_API_KEY") or "").strip()
    if not api_url or not api_key:
        raise RuntimeError("PLEXUS_API_URL and PLEXUS_API_KEY are required")
    return PlexusDashboardClient(api_url=api_url, api_key=api_key)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records") or []
    if not records:
        logger.info("No ChatMessage stream records to process")
        return {"processed": 0, "skipped": 0, "batchItemFailures": []}

    expected_target = normalize_response_target(
        os.getenv("CONSOLE_RESPONSE_TARGET") or PRODUCTION_RESPONSE_TARGET
    )
    request_id = getattr(context, "aws_request_id", None)
    owner = build_response_owner(expected_target, request_id=request_id)
    client = _resolve_client()

    failures = []
    processed = 0
    skipped = 0

    for record in records:
        event_name = str(record.get("eventName") or "").upper()
        sequence_number = str(record.get("dynamodb", {}).get("SequenceNumber") or record.get("eventID") or "")
        if event_name != "INSERT":
            skipped += 1
            continue

        new_image = record.get("dynamodb", {}).get("NewImage")
        if not isinstance(new_image, dict):
            skipped += 1
            continue

        try:
            message = _deserialize_dynamo_item(new_image)
            if process_console_message(
                client,
                message,
                expected_target=expected_target,
                owner=owner,
            ):
                processed += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error(
                "Failed processing ChatMessage stream record %s: %s",
                sequence_number,
                exc,
                exc_info=True,
            )
            if sequence_number:
                failures.append({"itemIdentifier": sequence_number})

    return {
        "processed": processed,
        "skipped": skipped,
        "batchItemFailures": failures,
    }
