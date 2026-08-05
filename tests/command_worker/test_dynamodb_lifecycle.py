from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from botocore.exceptions import ClientError

from plexus.command_worker import ClaimStatus, CommandEnvelope, ProgressUpdate
from plexus.command_worker.adapters import DynamoDBLifecycleStore
from plexus.command_worker.models import request_digest

NOW = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)


def _envelope(**overrides: object) -> CommandEnvelope:
    values: dict[str, object] = {
        "schema_version": 2,
        "command_id": "command-1",
        "tenant_id": "tenant-1",
        "target": "evaluate",
        "idempotency_key": "request-1",
        "created_at": NOW,
        "payload": {"item_id": "item-1"},
    }
    values.update(overrides)
    return CommandEnvelope(**values)  # type: ignore[arg-type]


class Table:
    """Executable DynamoDB-table double for lifecycle conditional semantics."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict] = {}

    def put_item(self, *, Item):
        self.items[(Item["pk"], Item["sk"])] = deepcopy(Item)

    def get_item(self, *, Key, ConsistentRead=False):
        item = self.items.get((Key["pk"], Key["sk"]))
        return {} if item is None else {"Item": deepcopy(item)}

    def update_item(
        self,
        *,
        Key,
        UpdateExpression,
        ConditionExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
        ReturnValues=None,
    ):
        item = self.items.get((Key["pk"], Key["sk"]))
        if item is None:
            self._conditional_failure()
        assert item is not None
        values = ExpressionAttributeValues
        if "#fence = #fence + :one" in UpdateExpression:
            if not (
                item["tenant_id"] == values[":tenant_id"]
                and item["target"] == values[":target"]
                and item["idempotency_key"] == values[":idempotency_key"]
                and item["created_at"] == values[":created_at"]
                and item["payload_digest"] == values[":digest"]
                and (
                    item["status"] == values[":announced"]
                    or (
                        item["status"] == values[":running"]
                        and item["lease_expires_at"] <= values[":now"]
                    )
                )
            ):
                self._conditional_failure()
            item.update(
                status=values[":running"],
                fence=item["fence"] + values[":one"],
                lease_owner=values[":owner"],
                lease_expires_at=values[":lease_expires_at"],
                updated_at=values[":updated_at"],
            )
        elif ":cancel_requested" in values and ":fence" not in values:
            if item["status"] != values[":cancel_requested"]:
                self._conditional_failure()
            item.update(status=values[":cancelled"], updated_at=values[":updated_at"])
            item.pop("lease_owner", None)
            item.pop("lease_expires_at", None)
        elif ":cancel_requested" in values and "#lease_expires_at" in UpdateExpression:
            if not (
                item["fence"] == values[":fence"]
                and item["status"] in {values[":running"], values[":cancel_requested"]}
                and item["lease_expires_at"] > values[":now"]
            ):
                self._conditional_failure()
            item.update(
                lease_expires_at=values[":lease_expires_at"],
                updated_at=values[":updated_at"],
            )
        else:
            if not (
                item["fence"] == values[":fence"]
                and item["status"] == values[":expected_status"]
                and item["lease_expires_at"] > values[":now"]
            ):
                self._conditional_failure()
            if ":cancelled" in values:
                item.update(
                    status=values[":cancelled"], updated_at=values[":updated_at"]
                )
                item.pop("lease_owner", None)
                item.pop("lease_expires_at", None)
            elif ":progress_fraction" in values:
                item.update(
                    progress_fraction=values[":progress_fraction"],
                    progress_message=values[":progress_message"],
                    progress_details=values[":progress_details"],
                    updated_at=values[":updated_at"],
                )
            elif ":succeeded" in values:
                item.update(
                    status=values[":succeeded"],
                    result=values[":result"],
                    updated_at=values[":updated_at"],
                )
                item.pop("lease_owner", None)
                item.pop("lease_expires_at", None)
            elif ":failed" in values:
                item.update(
                    status=values[":failed"],
                    error=values[":error"],
                    updated_at=values[":updated_at"],
                )
                item.pop("lease_owner", None)
                item.pop("lease_expires_at", None)
            else:  # pragma: no cover - guards the test double, not production code
                raise AssertionError(UpdateExpression)
        return {"Attributes": deepcopy(item)} if ReturnValues == "ALL_NEW" else {}

    @staticmethod
    def _conditional_failure() -> None:
        raise ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )


@pytest.fixture
def table() -> Table:
    return Table()


def _seed(table, envelope: CommandEnvelope, *, status: str = "ANNOUNCED") -> None:
    digest = request_digest(envelope.target, envelope.payload)
    table.put_item(
        Item={
            "pk": f"COMMAND#{envelope.command_id}",
            "sk": "META",
            "tenant_id": envelope.tenant_id,
            "target": envelope.target,
            "idempotency_key": envelope.idempotency_key,
            "created_at": envelope.created_at.isoformat(),
            "payload_digest": digest.value,
            "digest_algorithm": digest.algorithm,
            "digest_canonicalization_version": digest.canonicalization_version,
            "status": status,
            "fence": 0,
            "expires_at_epoch": 1_800_000_000,
        }
    )


def test_claim_reclaim_and_terminal_mutations_are_fenced(table) -> None:
    envelope = _envelope()
    _seed(table, envelope)
    store = DynamoDBLifecycleStore(table)

    first = store.claim(envelope, "worker-one", NOW, timedelta(minutes=5))
    assert first.token == "1"
    assert (
        store.claim(envelope, "worker-two", NOW, timedelta(minutes=5))
        is ClaimStatus.ACTIVE
    )

    reclaimed = store.claim(
        envelope, "worker-two", NOW + timedelta(minutes=6), timedelta(minutes=5)
    )
    assert reclaimed.token == "2"
    assert (
        store.report_progress(
            envelope.command_id,
            first.token,
            ProgressUpdate(0.5),
            NOW + timedelta(minutes=6),
        )
        is False
    )
    assert (
        store.complete(
            envelope.command_id,
            first.token,
            {"stale": True},
            NOW + timedelta(minutes=6),
        )
        is False
    )
    assert (
        store.complete(
            envelope.command_id,
            reclaimed.token,
            {"ok": True},
            NOW + timedelta(minutes=6),
        )
        is True
    )
    assert (
        store.claim(
            envelope, "worker-three", NOW + timedelta(minutes=6), timedelta(minutes=5)
        )
        is ClaimStatus.TERMINAL
    )


def test_cancellation_is_observable_and_only_the_current_lease_can_settle_it(
    table,
) -> None:
    envelope = _envelope()
    _seed(table, envelope)
    store = DynamoDBLifecycleStore(table)
    claim = store.claim(envelope, "worker-one", NOW, timedelta(minutes=5))

    table.items[("COMMAND#command-1", "META")]["status"] = "CANCEL_REQUESTED"
    renewed = store.renew(envelope.command_id, claim.token, NOW, timedelta(minutes=5))

    assert renewed is not None
    assert renewed.cancellation_requested is True
    assert (
        store.report_progress(
            envelope.command_id, claim.token, ProgressUpdate(0.5), NOW
        )
        is False
    )
    assert store.complete(envelope.command_id, claim.token, {"ok": True}, NOW) is False
    assert store.finalize_cancel(envelope.command_id, claim.token, NOW) is True
    assert store.finalize_cancel(envelope.command_id, claim.token, NOW) is False
    assert (
        store.claim(envelope, "worker-two", NOW, timedelta(minutes=5))
        is ClaimStatus.TERMINAL
    )


def test_expired_owner_cannot_renew_or_commit_before_replacement_claims(table) -> None:
    envelope = _envelope()
    _seed(table, envelope)
    store = DynamoDBLifecycleStore(table)
    claim = store.claim(envelope, "worker-one", NOW, timedelta(minutes=5))
    expired = NOW + timedelta(minutes=6)

    assert (
        store.renew(envelope.command_id, claim.token, expired, timedelta(minutes=5))
        is None
    )
    assert (
        store.complete(envelope.command_id, claim.token, {"late": True}, expired)
        is False
    )
    assert (
        store.claim(envelope, "worker-two", expired, timedelta(minutes=5)).token == "2"
    )


def test_claim_rejects_mismatched_immutable_envelope(table) -> None:
    envelope = _envelope()
    _seed(table, envelope)

    assert (
        DynamoDBLifecycleStore(table).claim(
            _envelope(payload={"item_id": "different"}),
            "worker-one",
            NOW,
            timedelta(minutes=5),
        )
        is ClaimStatus.INTEGRITY_MISMATCH
    )


def test_cancel_requested_command_is_never_reexecuted_after_owner_loss(table) -> None:
    envelope = _envelope()
    _seed(table, envelope, status="CANCEL_REQUESTED")
    store = DynamoDBLifecycleStore(table)

    assert (
        store.claim(envelope, "replacement", NOW, timedelta(minutes=5))
        is ClaimStatus.TERMINAL
    )
    item = table.get_item(Key={"pk": "COMMAND#command-1", "sk": "META"})["Item"]
    assert item["status"] == "CANCELLED"
