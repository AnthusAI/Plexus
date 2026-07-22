#!/usr/bin/env python3
"""Mirror Plexus Amplify production data into staging inside one AWS account.

The destructive modes intentionally require CONFIRM_DESTRUCTIVE to be set to
"mirror-main-to-staging". Preflight mode performs discovery only.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
# The original staging refresh runs in one region.  Developer sandboxes are
# routinely created elsewhere, so source and target clients must be separate.
SOURCE_REGION = os.environ.get("SOURCE_REGION", REGION)
TARGET_REGION = os.environ.get("TARGET_REGION", REGION)
ACCOUNT_ID = os.environ.get("EXPECTED_ACCOUNT_ID", "656853518159")
APP_ID = os.environ.get("AMPLIFY_APP_ID", "d1vx7jva4xxlue")
SOURCE_SUFFIX = os.environ.get("SOURCE_TABLE_SUFFIX", "xp6b4qnyovcjxh5p4yz57ygwku-NONE")
TARGET_SUFFIX = os.environ.get("TARGET_TABLE_SUFFIX", "5urd722zufd3tj43kvbrlsrkjm-NONE")
SOURCE_BRANCH_TOKEN = os.environ.get("SOURCE_BRANCH_TOKEN", "-ma-")
TARGET_BRANCH_TOKEN = os.environ.get("TARGET_BRANCH_TOKEN", "-st-")
CONFIRM_VALUE = os.environ.get("CONFIRM_DESTRUCTIVE_VALUE", "mirror-main-to-staging")

TABLE_WORKERS = int(os.environ.get("TABLE_WORKERS", "4"))
SEGMENT_WORKERS = int(os.environ.get("SEGMENT_WORKERS", "16"))
S3_WORKERS = int(os.environ.get("S3_WORKERS", "32"))
COPY_SKIP_SAME_SIZE = os.environ.get("S3_SKIP_SAME_SIZE", "true").lower() in {"1", "true", "yes"}

S3_BUCKET_PAIRS = {
    "dataSources": (
        "amplify-d1vx7jva4xxlue-ma-datasourcesbucketa1d38c0-memqyep8frdb",
        "amplify-d1vx7jva4xxlue-st-datasourcesbucketa1d38c0-aq7wslsg1zlk",
    ),
    "reportBlockDetails": (
        "amplify-d1vx7jva4xxlue-ma-reportblockdetailsbucket-gpos9qryoip8",
        "amplify-d1vx7jva4xxlue-st-reportblockdetailsbucket-2zg0b5t0l0qt",
    ),
    "scoreResultAttachments": (
        "amplify-d1vx7jva4xxlue-ma-scoreresultattachmentsbu-tvxo9hgmmpjk",
        "amplify-d1vx7jva4xxlue-st-scoreresultattachmentsbu-ou07sntftvd7",
    ),
    "taskAttachments": (
        "amplify-d1vx7jva4xxlue-ma-taskattachmentsbucket5ce-lexp0hwtoiqu",
        "amplify-d1vx7jva4xxlue-st-taskattachmentsbucket5ce-wap7oaygmo04",
    ),
    "rubricMemory": (
        "amplify-d1vx7jva4xxlue-ma-rubricmemorybucket827768-zkrpyuf8ec32",
        "amplify-d1vx7jva4xxlue-st-rubricmemorybucket827768-bs8rfrbij69y",
    ),
}
if raw_bucket_pairs := os.environ.get("S3_BUCKET_PAIRS_JSON"):
    parsed_bucket_pairs = json.loads(raw_bucket_pairs)
    if not isinstance(parsed_bucket_pairs, dict):
        raise RuntimeError("S3_BUCKET_PAIRS_JSON must be a JSON object")
    S3_BUCKET_PAIRS = {
        category: (pair[0], pair[1])
        for category, pair in parsed_bucket_pairs.items()
        if isinstance(category, str) and isinstance(pair, list) and len(pair) == 2
        and all(isinstance(bucket, str) for bucket in pair)
    }
    if not S3_BUCKET_PAIRS:
        raise RuntimeError("S3_BUCKET_PAIRS_JSON did not contain any valid bucket pairs")

SEGMENTS_BY_MODEL = {
    "ScoreResult": 64,
    "Item": 32,
    "AggregatedMetrics": 32,
    "FeedbackItem": 24,
    "Identifier": 24,
    "ChatMessage": 16,
    "ScoringJob": 16,
    "Task": 8,
    "Evaluation": 8,
    "Report": 4,
    "ReportBlock": 4,
    "DataSource": 4,
    "DataSourceVersion": 4,
    "DataSet": 4,
}

READ_CONFIG = Config(retries={"max_attempts": 10, "mode": "adaptive"}, max_pool_connections=128)
WRITE_CONFIG = Config(retries={"max_attempts": 20, "mode": "adaptive"}, max_pool_connections=128)

source_session = boto3.Session(region_name=SOURCE_REGION)
target_session = boto3.Session(region_name=TARGET_REGION)
sts = source_session.client("sts", config=READ_CONFIG)
source_ddb_client = source_session.client("dynamodb", config=WRITE_CONFIG)
target_ddb_client = target_session.client("dynamodb", config=WRITE_CONFIG)
source_ddb = source_session.resource("dynamodb", config=WRITE_CONFIG)
target_ddb = target_session.resource("dynamodb", config=WRITE_CONFIG)
source_s3 = source_session.client("s3", config=WRITE_CONFIG)
target_s3 = target_session.client("s3", config=WRITE_CONFIG)
target_lambda_client = target_session.client("lambda", config=WRITE_CONFIG)
source_cognito = source_session.client("cognito-idp", config=WRITE_CONFIG)
target_cognito = target_session.client("cognito-idp", config=WRITE_CONFIG)
serializer = TypeSerializer()
deserializer = TypeDeserializer()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str, **fields: Any) -> None:
    payload = {"ts": now(), "message": message, **fields}
    print(json.dumps(payload, default=json_default), flush=True)


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    return str(value)


@dataclass(frozen=True)
class TablePair:
    model: str
    source: str
    target: str
    source_count: int
    target_count: int
    key_attributes: tuple[str, ...]


@dataclass(frozen=True)
class MappingState:
    tables: list[TablePair]
    event_source_mappings: list[dict[str, Any]]
    source_user_pool_id: str | None
    target_user_pool_id: str | None


def require_expected_account() -> None:
    identity = sts.get_caller_identity()
    log("identity", account=identity["Account"], arn=identity["Arn"])
    if identity["Account"] != ACCOUNT_ID:
        raise RuntimeError(f"Refusing to run in account {identity['Account']}; expected {ACCOUNT_ID}")


def table_model_name(table_name: str, suffix: str) -> str | None:
    marker = f"-{suffix}"
    if table_name.endswith(marker):
        return table_name[: -len(marker)]
    return None


def list_tables_by_model(client: Any, suffix: str) -> dict[str, str]:
    result: dict[str, str] = {}
    paginator = client.get_paginator("list_tables")
    for page in paginator.paginate():
        for name in page.get("TableNames", []):
            model = table_model_name(name, suffix)
            if model:
                result[model] = name
    return result


def describe_table(client: Any, name: str) -> dict[str, Any]:
    return client.describe_table(TableName=name)["Table"]


def key_attributes(table_description: dict[str, Any]) -> tuple[str, ...]:
    return tuple(element["AttributeName"] for element in table_description["KeySchema"])


def discover_table_pairs() -> list[TablePair]:
    source_tables = list_tables_by_model(source_ddb_client, SOURCE_SUFFIX)
    target_tables = list_tables_by_model(target_ddb_client, TARGET_SUFFIX)
    missing_targets = sorted(set(source_tables) - set(target_tables))
    extra_targets = sorted(set(target_tables) - set(source_tables))
    if missing_targets:
        raise RuntimeError(f"Missing staging target tables for models: {', '.join(missing_targets)}")
    if extra_targets:
        log("extra staging tables without production source", models=extra_targets)

    pairs: list[TablePair] = []
    for model in sorted(source_tables):
        source_desc = describe_table(source_ddb_client, source_tables[model])
        target_desc = describe_table(target_ddb_client, target_tables[model])
        source_keys = key_attributes(source_desc)
        target_keys = key_attributes(target_desc)
        if source_keys != target_keys:
            raise RuntimeError(
                f"Key schema mismatch for {model}: source={source_keys} target={target_keys}"
            )
        pairs.append(
            TablePair(
                model=model,
                source=source_tables[model],
                target=target_tables[model],
                source_count=int(source_desc.get("ItemCount", 0)),
                target_count=int(target_desc.get("ItemCount", 0)),
                key_attributes=target_keys,
            )
        )
    return pairs


def table_stream_arn(table_name: str) -> str | None:
    table = describe_table(target_ddb_client, table_name)
    return table.get("LatestStreamArn")


def discover_staging_event_source_mappings(table_pairs: Iterable[TablePair]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for pair in table_pairs:
        arn = table_stream_arn(pair.target)
        if not arn:
            continue
        paginator = target_lambda_client.get_paginator("list_event_source_mappings")
        for page in paginator.paginate(EventSourceArn=arn):
            for mapping in page.get("EventSourceMappings", []):
                mappings.append(
                    {
                        "uuid": mapping["UUID"],
                        "state": mapping.get("State"),
                        "function_arn": mapping.get("FunctionArn"),
                        "event_source_arn": mapping.get("EventSourceArn"),
                    }
                )
    return mappings


def update_event_source_mapping(uuid: str, enabled: bool) -> None:
    target_lambda_client.update_event_source_mapping(UUID=uuid, Enabled=enabled)


def set_stream_consumers(mappings: list[dict[str, Any]], enabled: bool) -> None:
    for mapping in mappings:
        log("update event source mapping", uuid=mapping["uuid"], enabled=enabled)
        update_event_source_mapping(mapping["uuid"], enabled)


def restore_stream_consumers(mappings: list[dict[str, Any]]) -> None:
    for mapping in mappings:
        was_enabled = mapping.get("state") == "Enabled"
        log("restore event source mapping", uuid=mapping["uuid"], enabled=was_enabled)
        update_event_source_mapping(mapping["uuid"], enabled=was_enabled)


def wait_for_event_source_state(mappings: list[dict[str, Any]], desired: str, timeout_seconds: int = 300) -> None:
    if not mappings:
        return
    deadline = time.time() + timeout_seconds
    remaining = {mapping["uuid"] for mapping in mappings}
    while remaining and time.time() < deadline:
        for uuid in list(remaining):
            current = target_lambda_client.get_event_source_mapping(UUID=uuid).get("State")
            if current == desired:
                remaining.remove(uuid)
        if remaining:
            time.sleep(5)
    if remaining:
        raise RuntimeError(f"Timed out waiting for event source mappings to reach {desired}: {sorted(remaining)}")


def scan_kwargs(total_segments: int, segment: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if total_segments > 1:
        kwargs.update({"TotalSegments": total_segments, "Segment": segment})
    return kwargs


def delete_table_segment(pair: TablePair, total_segments: int, segment: int) -> int:
    table = target_ddb.Table(pair.target)
    deleted = 0
    last_key = None
    projection = ", ".join(f"#k{i}" for i, _ in enumerate(pair.key_attributes))
    names = {f"#k{i}": key for i, key in enumerate(pair.key_attributes)}
    with table.batch_writer() as writer:
        while True:
            kwargs = scan_kwargs(total_segments, segment)
            kwargs.update({"ProjectionExpression": projection, "ExpressionAttributeNames": names})
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            response = table.scan(**kwargs)
            for item in response.get("Items", []):
                writer.delete_item(Key={key: item[key] for key in pair.key_attributes})
                deleted += 1
                if deleted % 10000 == 0:
                    log("delete progress", table=pair.target, segment=segment, deleted=deleted)
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
    log("delete segment complete", table=pair.target, segment=segment, deleted=deleted)
    return deleted


def empty_table(pair: TablePair) -> int:
    segments = max(1, min(segment_count(pair.model), SEGMENT_WORKERS))
    log("empty table start", model=pair.model, table=pair.target, segments=segments)
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=segments) as executor:
        futures = [executor.submit(delete_table_segment, pair, segments, segment) for segment in range(segments)]
        for future in concurrent.futures.as_completed(futures):
            total += future.result()
    log("empty table complete", model=pair.model, table=pair.target, deleted=total)
    return total


def copy_table_segment(pair: TablePair, total_segments: int, segment: int, limit: int | None = None) -> int:
    source = source_ddb.Table(pair.source)
    target = target_ddb.Table(pair.target)
    copied = 0
    last_key = None
    with target.batch_writer(overwrite_by_pkeys=list(pair.key_attributes)) as writer:
        while True:
            kwargs = scan_kwargs(total_segments, segment)
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            response = source.scan(**kwargs)
            for item in response.get("Items", []):
                writer.put_item(Item=item)
                copied += 1
                if copied % 10000 == 0:
                    log("copy progress", model=pair.model, segment=segment, copied=copied)
                if limit and copied >= limit:
                    log("copy segment limit reached", model=pair.model, segment=segment, copied=copied)
                    return copied
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
    log("copy segment complete", model=pair.model, segment=segment, copied=copied)
    return copied


def segment_count(model: str) -> int:
    return int(os.environ.get(f"SEGMENTS_{model.upper()}", str(SEGMENTS_BY_MODEL.get(model, 4))))


def copy_table(pair: TablePair, canary_limit: int | None = None) -> int:
    if canary_limit:
        log("copy table canary start", model=pair.model, source=pair.source, target=pair.target, limit=canary_limit)
        copied = copy_table_segment(pair, 1, 0, canary_limit)
        log("copy table canary complete", model=pair.model, copied=copied)
        return copied

    segments = max(1, min(segment_count(pair.model), SEGMENT_WORKERS))
    log("copy table start", model=pair.model, source=pair.source, target=pair.target, segments=segments)
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=segments) as executor:
        futures = [executor.submit(copy_table_segment, pair, segments, segment) for segment in range(segments)]
        for future in concurrent.futures.as_completed(futures):
            total += future.result()
    log("copy table complete", model=pair.model, copied=total)
    return total


def empty_all_tables(pairs: list[TablePair]) -> None:
    ordered = sorted(pairs, key=lambda pair: pair.target_count, reverse=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=TABLE_WORKERS) as executor:
        futures = [executor.submit(empty_table, pair) for pair in ordered]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def copy_all_tables(pairs: list[TablePair]) -> None:
    ordered = sorted(pairs, key=lambda pair: pair.source_count, reverse=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=TABLE_WORKERS) as executor:
        futures = [executor.submit(copy_table, pair) for pair in ordered]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def list_s3_keys(client: Any, bucket: str) -> Iterable[dict[str, Any]]:
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for item in page.get("Contents", []):
            yield item


def empty_bucket(bucket: str) -> int:
    log("empty bucket start", bucket=bucket)
    deleted = 0
    batch: list[dict[str, str]] = []
    for obj in list_s3_keys(target_s3, bucket):
        batch.append({"Key": obj["Key"]})
        if len(batch) == 1000:
            target_s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
            deleted += len(batch)
            log("empty bucket progress", bucket=bucket, deleted=deleted)
            batch = []
    if batch:
        target_s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
        deleted += len(batch)
    log("empty bucket complete", bucket=bucket, deleted=deleted)
    return deleted


def head_size(bucket: str, key: str) -> int | None:
    try:
        return int(target_s3.head_object(Bucket=bucket, Key=key)["ContentLength"])
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def copy_one_object(source_bucket: str, target_bucket: str, key: str, size: int) -> str:
    if COPY_SKIP_SAME_SIZE:
        target_size = head_size(target_bucket, key)
        if target_size == size:
            return "skipped"
    target_s3.copy(
        {"Bucket": source_bucket, "Key": key},
        target_bucket,
        key,
        SourceClient=source_s3,
        Config=TransferConfig(max_concurrency=4, multipart_threshold=64 * 1024 * 1024),
    )
    return "copied"


def copy_bucket_pair(category: str, source_bucket: str, target_bucket: str) -> dict[str, int]:
    log("copy bucket start", category=category, source=source_bucket, target=target_bucket)
    stats = {"listed": 0, "copied": 0, "skipped": 0, "failed": 0, "bytes": 0}
    lockless_updates: list[dict[str, int]] = []

    def worker(obj: dict[str, Any]) -> dict[str, int]:
        key = obj["Key"]
        size = int(obj.get("Size", 0))
        try:
            status = copy_one_object(source_bucket, target_bucket, key, size)
            return {"listed": 1, status: 1, "failed": 0, "bytes": size}
        except Exception as exc:  # noqa: BLE001 - log and continue object-level failures.
            log("copy object failed", category=category, key=key, error=str(exc))
            return {"listed": 1, "copied": 0, "skipped": 0, "failed": 1, "bytes": size}

    with concurrent.futures.ThreadPoolExecutor(max_workers=S3_WORKERS) as executor:
        futures = []
        for obj in list_s3_keys(source_s3, source_bucket):
            futures.append(executor.submit(worker, obj))
            if len(futures) >= S3_WORKERS * 4:
                for future in concurrent.futures.as_completed(futures):
                    lockless_updates.append(future.result())
                futures = []
                stats = merge_stats(stats, lockless_updates)
                lockless_updates = []
                log("copy bucket progress", category=category, **stats)
        for future in concurrent.futures.as_completed(futures):
            lockless_updates.append(future.result())
    stats = merge_stats(stats, lockless_updates)
    log("copy bucket complete", category=category, **stats)
    return stats


def merge_stats(base: dict[str, int], updates: list[dict[str, int]]) -> dict[str, int]:
    result = dict(base)
    for update in updates:
        for key, value in update.items():
            result[key] = result.get(key, 0) + int(value)
    return result


def empty_all_buckets() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(S3_BUCKET_PAIRS)) as executor:
        futures = [executor.submit(empty_bucket, target) for _, target in S3_BUCKET_PAIRS.values()]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def copy_all_buckets() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(S3_BUCKET_PAIRS)) as executor:
        futures = [
            executor.submit(copy_bucket_pair, category, source, target)
            for category, (source, target) in S3_BUCKET_PAIRS.items()
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def discover_user_pool(branch_token: str, explicit_env: str) -> str | None:
    explicit = os.environ.get(explicit_env)
    if explicit:
        return explicit
    desired_branch = "main" if branch_token == SOURCE_BRANCH_TOKEN else "staging"
    candidates = []
    cognito_client = source_cognito if branch_token == SOURCE_BRANCH_TOKEN else target_cognito
    paginator = cognito_client.get_paginator("list_user_pools")
    for page in paginator.paginate(MaxResults=60):
        for pool in page.get("UserPools", []):
            name = pool.get("Name", "")
            pool_id = pool["Id"]
            details = cognito_client.describe_user_pool(UserPoolId=pool_id)["UserPool"]
            tags = details.get("UserPoolTags", {})
            if tags.get("amplify:app-id") == APP_ID and tags.get("amplify:branch-name") == desired_branch:
                candidates.append(pool_id)
                continue
            lowered = name.lower()
            if APP_ID in name and branch_token.strip("-") in lowered:
                candidates.append(pool_id)
            elif APP_ID in name and ((branch_token == SOURCE_BRANCH_TOKEN and "main" in lowered) or (branch_token == TARGET_BRANCH_TOKEN and "staging" in lowered)):
                candidates.append(pool_id)
    if len(candidates) == 1:
        return candidates[0]
    log("user pool discovery ambiguous", branch_token=branch_token, candidates=candidates)
    return None


def mirror_cognito_users(source_pool_id: str | None, target_pool_id: str | None) -> None:
    if not source_pool_id or not target_pool_id:
        log("skip cognito mirror: missing source or target user pool", source_pool_id=source_pool_id, target_pool_id=target_pool_id)
        return
    temp_password = os.environ.get("STAGING_COGNITO_TEMP_PASSWORD")
    if not temp_password:
        log("skip cognito create: STAGING_COGNITO_TEMP_PASSWORD not set; existing users may still be updated")
    log("cognito mirror start", source_pool_id=source_pool_id, target_pool_id=target_pool_id)
    copied = 0
    updated = 0
    skipped_create = 0
    paginator = source_cognito.get_paginator("list_users")
    for page in paginator.paginate(UserPoolId=source_pool_id):
        for user in page.get("Users", []):
            username = user["Username"]
            attributes = [
                attr for attr in user.get("Attributes", [])
                if attr.get("Name") not in {"sub", "identities", "email_verified", "phone_number_verified"}
            ]
            try:
                target_cognito.admin_get_user(UserPoolId=target_pool_id, Username=username)
                if attributes:
                    target_cognito.admin_update_user_attributes(
                        UserPoolId=target_pool_id,
                        Username=username,
                        UserAttributes=attributes,
                    )
                updated += 1
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "UserNotFoundException":
                    raise
                if not temp_password:
                    skipped_create += 1
                    continue
                target_cognito.admin_create_user(
                    UserPoolId=target_pool_id,
                    Username=username,
                    UserAttributes=attributes,
                    TemporaryPassword=temp_password,
                    MessageAction="SUPPRESS",
                )
                copied += 1
    log("cognito mirror complete", created=copied, updated=updated, skipped_create=skipped_create)


def preflight() -> MappingState:
    require_expected_account()
    pairs = discover_table_pairs()
    mappings = discover_staging_event_source_mappings(pairs)
    source_pool_id = discover_user_pool(SOURCE_BRANCH_TOKEN, "SOURCE_USER_POOL_ID")
    target_pool_id = discover_user_pool(TARGET_BRANCH_TOKEN, "TARGET_USER_POOL_ID")
    for pair in pairs:
        log(
            "table pair",
            model=pair.model,
            source=pair.source,
            target=pair.target,
            source_count=pair.source_count,
            target_count=pair.target_count,
            key_attributes=pair.key_attributes,
        )
    for category, (source, target) in S3_BUCKET_PAIRS.items():
        source_s3.head_bucket(Bucket=source)
        target_s3.head_bucket(Bucket=target)
        log("bucket pair", category=category, source=source, target=target)
    for mapping in mappings:
        log("staging event source mapping", **mapping)
    log("cognito pools", source_user_pool_id=source_pool_id, target_user_pool_id=target_pool_id)
    return MappingState(pairs, mappings, source_pool_id, target_pool_id)


def canary(state: MappingState) -> None:
    require_confirmation("Canary mode")
    safe_models = [pair for pair in state.tables if pair.model in {"Account", "User"}]
    if not safe_models:
        raise RuntimeError("No Account/User table pair found for canary")
    set_stream_consumers(state.event_source_mappings, False)
    wait_for_event_source_state(state.event_source_mappings, "Disabled")
    try:
        for pair in safe_models:
            empty_table(pair)
            copy_table(pair)
    finally:
        restore_stream_consumers(state.event_source_mappings)


def full_mirror(state: MappingState) -> None:
    require_confirmation("Full mirror")
    if SOURCE_SUFFIX == TARGET_SUFFIX:
        raise RuntimeError("Refusing full mirror when source and target table suffixes are identical")
    set_stream_consumers(state.event_source_mappings, False)
    wait_for_event_source_state(state.event_source_mappings, "Disabled")
    try:
        empty_all_buckets()
        empty_all_tables(state.tables)
        copy_all_tables(state.tables)
        copy_all_buckets()
        mirror_cognito_users(state.source_user_pool_id, state.target_user_pool_id)
    finally:
        restore_stream_consumers(state.event_source_mappings)


def require_confirmation(operation: str) -> None:
    if os.environ.get("CONFIRM_DESTRUCTIVE") != CONFIRM_VALUE:
        raise RuntimeError(f"{operation} requires CONFIRM_DESTRUCTIVE={CONFIRM_VALUE}")


def selected_pair(state: MappingState) -> TablePair:
    model = os.environ.get("MODEL")
    if not model:
        raise RuntimeError("MODEL is required for table-scoped modes")
    matches = [pair for pair in state.tables if pair.model == model]
    if not matches:
        raise RuntimeError(f"No table mapping found for MODEL={model}")
    return matches[0]


def direct_pair_from_model() -> TablePair:
    model = os.environ.get("MODEL")
    if not model:
        raise RuntimeError("MODEL is required for table-scoped modes")
    source_name = f"{model}-{SOURCE_SUFFIX}"
    target_name = f"{model}-{TARGET_SUFFIX}"
    source_desc = describe_table(source_ddb_client, source_name)
    target_desc = describe_table(target_ddb_client, target_name)
    source_keys = key_attributes(source_desc)
    target_keys = key_attributes(target_desc)
    if source_keys != target_keys:
        raise RuntimeError(
            f"Key schema mismatch for {model}: source={source_keys} target={target_keys}"
        )
    return TablePair(
        model=model,
        source=source_name,
        target=target_name,
        source_count=int(source_desc.get("ItemCount", 0)),
        target_count=int(target_desc.get("ItemCount", 0)),
        key_attributes=target_keys,
    )


def selected_bucket_pair() -> tuple[str, str, str]:
    category = os.environ.get("S3_CATEGORY")
    if not category:
        raise RuntimeError("S3_CATEGORY is required for bucket-scoped modes")
    if category not in S3_BUCKET_PAIRS:
        raise RuntimeError(f"Unknown S3_CATEGORY={category}; valid={sorted(S3_BUCKET_PAIRS)}")
    source, target = S3_BUCKET_PAIRS[category]
    return category, source, target


def segment_options(default_total: int) -> tuple[int, int] | None:
    raw_segment = os.environ.get("SEGMENT")
    raw_total = os.environ.get("TOTAL_SEGMENTS")
    if raw_segment is None and raw_total is None:
        return None
    if raw_segment is None or raw_total is None:
        raise RuntimeError("SEGMENT and TOTAL_SEGMENTS must be supplied together")
    segment = int(raw_segment)
    total = int(raw_total)
    if total <= 0 or segment < 0 or segment >= total:
        raise RuntimeError(f"Invalid segment options: SEGMENT={segment} TOTAL_SEGMENTS={total}")
    return total, segment


def run_delete_table(state: MappingState) -> None:
    require_confirmation("Delete-table mode")
    pair = selected_pair(state)
    options = segment_options(segment_count(pair.model))
    if options:
        total, segment = options
        delete_table_segment(pair, total, segment)
    else:
        empty_table(pair)


def run_copy_table(state: MappingState) -> None:
    require_confirmation("Copy-table mode")
    pair = selected_pair(state)
    options = segment_options(segment_count(pair.model))
    if options:
        total, segment = options
        copy_table_segment(pair, total, segment)
    else:
        copy_table(pair)


def run_delete_table_direct() -> None:
    require_confirmation("Delete-table mode")
    require_expected_account()
    pair = direct_pair_from_model()
    options = segment_options(segment_count(pair.model))
    if options:
        total, segment = options
        delete_table_segment(pair, total, segment)
    else:
        empty_table(pair)


def run_copy_table_direct() -> None:
    require_confirmation("Copy-table mode")
    require_expected_account()
    pair = direct_pair_from_model()
    options = segment_options(segment_count(pair.model))
    if options:
        total, segment = options
        copy_table_segment(pair, total, segment)
    else:
        copy_table(pair)


def run_empty_bucket() -> None:
    require_confirmation("Empty-bucket mode")
    require_expected_account()
    _, _, target = selected_bucket_pair()
    empty_bucket(target)


def run_copy_bucket() -> None:
    require_confirmation("Copy-bucket mode")
    require_expected_account()
    category, source, target = selected_bucket_pair()
    prefix = os.environ.get("S3_PREFIX")
    if prefix:
        copy_bucket_prefix(category, source, target, prefix)
    else:
        copy_bucket_pair(category, source, target)


def copy_bucket_prefix(category: str, source_bucket: str, target_bucket: str, prefix: str) -> dict[str, int]:
    log("copy bucket prefix start", category=category, source=source_bucket, target=target_bucket, prefix=prefix)
    stats = {"listed": 0, "copied": 0, "skipped": 0, "failed": 0, "bytes": 0}
    updates: list[dict[str, int]] = []

    def worker(obj: dict[str, Any]) -> dict[str, int]:
        key = obj["Key"]
        size = int(obj.get("Size", 0))
        try:
            status = copy_one_object(source_bucket, target_bucket, key, size)
            return {"listed": 1, status: 1, "failed": 0, "bytes": size}
        except Exception as exc:  # noqa: BLE001 - object-level failure logging.
            log("copy object failed", category=category, key=key, error=str(exc))
            return {"listed": 1, "copied": 0, "skipped": 0, "failed": 1, "bytes": size}

    paginator = source_s3.get_paginator("list_objects_v2")
    with concurrent.futures.ThreadPoolExecutor(max_workers=S3_WORKERS) as executor:
        futures = []
        for page in paginator.paginate(Bucket=source_bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                futures.append(executor.submit(worker, obj))
                if len(futures) >= S3_WORKERS * 4:
                    for future in concurrent.futures.as_completed(futures):
                        updates.append(future.result())
                    futures = []
                    stats = merge_stats(stats, updates)
                    updates = []
                    log("copy bucket prefix progress", category=category, prefix=prefix, **stats)
        for future in concurrent.futures.as_completed(futures):
            updates.append(future.result())
    stats = merge_stats(stats, updates)
    log("copy bucket prefix complete", category=category, prefix=prefix, **stats)
    return stats


def main() -> int:
    mode = os.environ.get("MIRROR_MODE", "preflight").strip().lower()
    log("mirror start", mode=mode, source_region=SOURCE_REGION, target_region=TARGET_REGION, app_id=APP_ID)
    try:
        if mode == "delete-table":
            run_delete_table_direct()
            log("mirror complete", mode=mode)
            return 0
        if mode == "copy-table":
            run_copy_table_direct()
            log("mirror complete", mode=mode)
            return 0
        if mode == "empty-bucket":
            run_empty_bucket()
            log("mirror complete", mode=mode)
            return 0
        if mode == "copy-bucket":
            run_copy_bucket()
            log("mirror complete", mode=mode)
            return 0

        state = preflight()
        if mode == "preflight":
            log("preflight complete")
        elif mode == "canary":
            canary(state)
        elif mode == "full":
            full_mirror(state)
        elif mode == "disable-consumers":
            require_confirmation("Disable-consumers mode")
            set_stream_consumers(state.event_source_mappings, False)
            wait_for_event_source_state(state.event_source_mappings, "Disabled")
        elif mode == "enable-consumers":
            require_confirmation("Enable-consumers mode")
            set_stream_consumers(state.event_source_mappings, True)
            wait_for_event_source_state(state.event_source_mappings, "Enabled")
        elif mode == "delete-table":
            run_delete_table(state)
        elif mode == "copy-table":
            run_copy_table(state)
        elif mode == "empty-bucket":
            run_empty_bucket()
        elif mode == "copy-bucket":
            run_copy_bucket()
        elif mode == "cognito":
            require_confirmation("Cognito mode")
            mirror_cognito_users(state.source_user_pool_id, state.target_user_pool_id)
        else:
            raise RuntimeError(f"Unsupported MIRROR_MODE={mode}")
        log("mirror complete", mode=mode)
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level failure logging.
        log("mirror failed", mode=mode, error=str(exc), traceback=traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
