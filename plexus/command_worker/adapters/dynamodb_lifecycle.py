"""DynamoDB implementation of the portable command lifecycle port.

The adapter owns only execution lifecycle state. Command submission and broker
publication remain separate concerns because DynamoDB cannot atomically write
an SQS message. Metadata is written by the command repository at:

``pk=COMMAND#<command_id>, sk=META``

with tenant and immutable envelope fields, a request digest, lifecycle status,
numeric fencing token, lease fields, and ``expires_at_epoch`` TTL. Every
execution mutation is conditionally fenced by that numeric token.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Mapping

from botocore.exceptions import ClientError

from ..models import Claim, CommandEnvelope, JSONValue, ProgressUpdate, request_digest
from ..ports import ClaimStatus

_META_SORT_KEY = "META"
_COMMAND_PREFIX = "COMMAND#"
_ANNOUNCED = "ANNOUNCED"
_RUNNING = "RUNNING"
_CANCEL_REQUESTED = "CANCEL_REQUESTED"
_CANCELLED = "CANCELLED"
_SUCCEEDED = "SUCCEEDED"
_FAILED = "FAILED"


class DynamoDBLifecycleStore:
    """LifecycleStore backed by one canonical DynamoDB metadata item per command."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def claim(
        self,
        envelope: CommandEnvelope,
        owner: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> Claim | ClaimStatus:
        item = self._read_verified(envelope)
        if item is None:
            return ClaimStatus.INTEGRITY_MISMATCH
        if item["status"] in {_SUCCEEDED, _FAILED, _CANCELLED}:
            return ClaimStatus.TERMINAL
        if item["status"] == _CANCEL_REQUESTED:
            self._settle_expired_cancellation(envelope.command_id, now)
            return ClaimStatus.TERMINAL

        expires_at = now + lease_duration
        try:
            response = self._table.update_item(
                Key=self._key(envelope.command_id),
                UpdateExpression=(
                    "SET #status = :running, #fence = #fence + :one, "
                    "#lease_owner = :owner, #lease_expires_at = :lease_expires_at, "
                    "#updated_at = :updated_at"
                ),
                ConditionExpression=(
                    "#tenant_id = :tenant_id AND #target = :target AND "
                    "#idempotency_key = :idempotency_key AND "
                    "#created_at = :created_at AND #digest = :digest AND "
                    "(#status = :announced OR "
                    "(#status = :running AND #lease_expires_at <= :now))"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                    "#fence": "fence",
                    "#lease_owner": "lease_owner",
                    "#lease_expires_at": "lease_expires_at",
                    "#updated_at": "updated_at",
                    "#tenant_id": "tenant_id",
                    "#target": "target",
                    "#idempotency_key": "idempotency_key",
                    "#created_at": "created_at",
                    "#digest": "payload_digest",
                },
                ExpressionAttributeValues={
                    ":running": _RUNNING,
                    ":one": 1,
                    ":owner": owner,
                    ":lease_expires_at": self._timestamp(expires_at),
                    ":updated_at": self._timestamp(now),
                    ":tenant_id": envelope.tenant_id,
                    ":target": envelope.target,
                    ":idempotency_key": envelope.idempotency_key,
                    ":created_at": self._timestamp(envelope.created_at),
                    ":digest": request_digest(envelope.target, envelope.payload).value,
                    ":announced": _ANNOUNCED,
                    ":now": self._timestamp(now),
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if self._conditional_failure(error):
                return self._claim_status_after_conflict(envelope, now)
            raise
        return self._claim_from_item(response["Attributes"])

    def report_progress(
        self,
        command_id: str,
        token: str,
        progress: ProgressUpdate,
        now: datetime,
    ) -> bool:
        return self._fenced_update(
            command_id,
            token,
            update_expression=(
                "SET #progress_fraction = :progress_fraction, "
                "#progress_message = :progress_message, "
                "#progress_details = :progress_details, #updated_at = :updated_at"
            ),
            names={
                "#progress_fraction": "progress_fraction",
                "#progress_message": "progress_message",
                "#progress_details": "progress_details",
                "#updated_at": "updated_at",
            },
            values={
                ":progress_fraction": progress.fraction,
                ":progress_message": progress.message,
                ":progress_details": self._thaw(progress.details),
                ":updated_at": self._timestamp(now),
            },
            status=_RUNNING,
            now=now,
        )

    def renew(
        self,
        command_id: str,
        token: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> Claim | None:
        try:
            response = self._table.update_item(
                Key=self._key(command_id),
                UpdateExpression=(
                    "SET #lease_expires_at = :lease_expires_at, "
                    "#updated_at = :updated_at"
                ),
                ConditionExpression=(
                    "#fence = :fence AND "
                    "(#status = :running OR #status = :cancel_requested) AND "
                    "#lease_expires_at > :now"
                ),
                ExpressionAttributeNames={
                    "#fence": "fence",
                    "#status": "status",
                    "#lease_expires_at": "lease_expires_at",
                    "#updated_at": "updated_at",
                },
                ExpressionAttributeValues={
                    ":fence": self._fence(token),
                    ":running": _RUNNING,
                    ":cancel_requested": _CANCEL_REQUESTED,
                    ":lease_expires_at": self._timestamp(now + lease_duration),
                    ":updated_at": self._timestamp(now),
                    ":now": self._timestamp(now),
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as error:
            if self._conditional_failure(error):
                return None
            raise
        return self._claim_from_item(response["Attributes"])

    def complete(
        self, command_id: str, token: str, result: JSONValue, now: datetime
    ) -> bool:
        return self._fenced_update(
            command_id,
            token,
            update_expression=(
                "SET #status = :succeeded, #result = :result, #updated_at = :updated_at "
                "REMOVE #lease_owner, #lease_expires_at"
            ),
            names={
                "#status": "status",
                "#result": "result",
                "#updated_at": "updated_at",
                "#lease_owner": "lease_owner",
                "#lease_expires_at": "lease_expires_at",
            },
            values={
                ":succeeded": _SUCCEEDED,
                ":result": self._thaw(result),
                ":updated_at": self._timestamp(now),
            },
            status=_RUNNING,
            now=now,
        )

    def fail(self, command_id: str, token: str, error: str, now: datetime) -> bool:
        return self._fenced_update(
            command_id,
            token,
            update_expression=(
                "SET #status = :failed, #error = :error, #updated_at = :updated_at "
                "REMOVE #lease_owner, #lease_expires_at"
            ),
            names={
                "#status": "status",
                "#error": "error",
                "#updated_at": "updated_at",
                "#lease_owner": "lease_owner",
                "#lease_expires_at": "lease_expires_at",
            },
            values={
                ":failed": _FAILED,
                ":error": error,
                ":updated_at": self._timestamp(now),
            },
            status=_RUNNING,
            now=now,
        )

    def finalize_cancel(self, command_id: str, token: str, now: datetime) -> bool:
        return self._fenced_update(
            command_id,
            token,
            update_expression=(
                "SET #status = :cancelled, #updated_at = :updated_at "
                "REMOVE #lease_owner, #lease_expires_at"
            ),
            names={
                "#status": "status",
                "#updated_at": "updated_at",
                "#lease_owner": "lease_owner",
                "#lease_expires_at": "lease_expires_at",
            },
            values={
                ":cancelled": _CANCELLED,
                ":updated_at": self._timestamp(now),
            },
            status=_CANCEL_REQUESTED,
            now=now,
        )

    def _fenced_update(
        self,
        command_id: str,
        token: str,
        *,
        update_expression: str,
        names: dict[str, str],
        values: dict[str, Any],
        status: str,
        now: datetime,
    ) -> bool:
        names = {
            **names,
            "#fence": "fence",
            "#status": "status",
            "#lease_expires_at": "lease_expires_at",
        }
        values = {
            **values,
            ":fence": self._fence(token),
            ":expected_status": status,
            ":now": self._timestamp(now),
        }
        try:
            self._table.update_item(
                Key=self._key(command_id),
                UpdateExpression=update_expression,
                ConditionExpression=(
                    "#fence = :fence AND #status = :expected_status AND "
                    "#lease_expires_at > :now"
                ),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
            )
        except ClientError as error:
            if self._conditional_failure(error):
                return False
            raise
        return True

    def _settle_expired_cancellation(self, command_id: str, now: datetime) -> None:
        try:
            self._table.update_item(
                Key=self._key(command_id),
                UpdateExpression=(
                    "SET #status = :cancelled, #updated_at = :updated_at "
                    "REMOVE #lease_owner, #lease_expires_at"
                ),
                ConditionExpression="#status = :cancel_requested",
                ExpressionAttributeNames={
                    "#status": "status",
                    "#updated_at": "updated_at",
                    "#lease_owner": "lease_owner",
                    "#lease_expires_at": "lease_expires_at",
                },
                ExpressionAttributeValues={
                    ":cancelled": _CANCELLED,
                    ":cancel_requested": _CANCEL_REQUESTED,
                    ":updated_at": self._timestamp(now),
                },
            )
        except ClientError as error:
            if not self._conditional_failure(error):
                raise

    def _claim_status_after_conflict(
        self, envelope: CommandEnvelope, now: datetime
    ) -> ClaimStatus:
        item = self._read_verified(envelope)
        if item is None:
            return ClaimStatus.INTEGRITY_MISMATCH
        if item["status"] in {_SUCCEEDED, _FAILED, _CANCELLED}:
            return ClaimStatus.TERMINAL
        if item["status"] == _CANCEL_REQUESTED:
            self._settle_expired_cancellation(envelope.command_id, now)
            return ClaimStatus.TERMINAL
        return ClaimStatus.ACTIVE

    def _read_verified(self, envelope: CommandEnvelope) -> Mapping[str, Any] | None:
        response = self._table.get_item(
            Key=self._key(envelope.command_id), ConsistentRead=True
        )
        item = response.get("Item")
        if item is None:
            return None
        expected_digest = request_digest(envelope.target, envelope.payload)
        if (
            item.get("tenant_id") != envelope.tenant_id
            or item.get("target") != envelope.target
            or item.get("idempotency_key") != envelope.idempotency_key
            or item.get("created_at") != self._timestamp(envelope.created_at)
            or item.get("payload_digest") != expected_digest.value
            or item.get("digest_algorithm") != expected_digest.algorithm
            or item.get("digest_canonicalization_version")
            != expected_digest.canonicalization_version
        ):
            return None
        return item

    @staticmethod
    def _key(command_id: str) -> dict[str, str]:
        return {"pk": f"{_COMMAND_PREFIX}{command_id}", "sk": _META_SORT_KEY}

    @staticmethod
    def _claim_from_item(item: Mapping[str, Any]) -> Claim:
        return Claim(
            token=str(item["fence"]),
            owner=item["lease_owner"],
            expires_at=datetime.fromisoformat(item["lease_expires_at"]),
            cancellation_requested=item["status"] == _CANCEL_REQUESTED,
        )

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.isoformat()

    @staticmethod
    def _fence(token: str) -> int:
        try:
            fence = int(token)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "DynamoDB lifecycle tokens must be integer strings"
            ) from error
        if fence < 1:
            raise ValueError("DynamoDB lifecycle tokens must be positive")
        return fence

    @staticmethod
    def _thaw(value: JSONValue | Mapping[str, JSONValue] | None) -> Any:
        if value is None:
            return None
        return json.loads(json.dumps(value, default=dict))

    @staticmethod
    def _conditional_failure(error: ClientError) -> bool:
        return (
            error.response.get("Error", {}).get("Code")
            == "ConditionalCheckFailedException"
        )
