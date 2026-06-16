from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .schema_contract import get_schema_contract


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat().replace("+00:00", "Z")


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


@dataclass(frozen=True)
class ModelConfig:
    table: str
    pk_fields: tuple[str, ...]
    columns: dict[str, str]
    default_order: str

    def column_for(self, field_name: str) -> Optional[str]:
        return self.columns.get(field_name)


MODEL_CONFIGS: dict[str, ModelConfig] = {
    "Item": ModelConfig(
        table="private_data.items",
        pk_fields=("id",),
        default_order="updated_at",
        columns={
            "id": "id",
            "accountId": "account_id",
            "scoreId": "score_id",
            "evaluationId": "evaluation_id",
            "externalId": "external_id",
            "isEvaluation": "is_evaluation",
            "createdByType": "created_by_type",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
    ),
    "Identifier": ModelConfig(
        table="private_data.identifiers",
        pk_fields=("itemId", "name"),
        default_order="position",
        columns={
            "itemId": "item_id",
            "name": "name",
            "value": "value",
            "accountId": "account_id",
            "position": "position",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
    ),
    "ScoreResult": ModelConfig(
        table="private_data.score_results",
        pk_fields=("id",),
        default_order="updated_at",
        columns={
            "id": "id",
            "itemId": "item_id",
            "accountId": "account_id",
            "scorecardId": "scorecard_id",
            "scoreId": "score_id",
            "scoreVersionId": "score_version_id",
            "evaluationId": "evaluation_id",
            "scoringJobId": "scoring_job_id",
            "feedbackItemId": "feedback_item_id",
            "type": "type",
            "status": "status",
            "code": "code",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
    ),
    "FeedbackItem": ModelConfig(
        table="private_data.feedback_items",
        pk_fields=("id",),
        default_order="updated_at",
        columns={
            "id": "id",
            "accountId": "account_id",
            "scorecardId": "scorecard_id",
            "scoreId": "score_id",
            "itemId": "item_id",
            "cacheKey": "cache_key",
            "editedAt": "edited_at",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
    ),
}


class PostgresStore:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def initialize(self) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    create schema if not exists private_data;
                    create schema if not exists control_cache;
                    create schema if not exists proxy_debug;

                    create table if not exists private_data.items (
                        id text primary key,
                        account_id text not null,
                        score_id text,
                        evaluation_id text,
                        external_id text,
                        is_evaluation boolean,
                        created_by_type text,
                        created_at timestamptz,
                        updated_at timestamptz,
                        doc jsonb not null
                    );
                    create index if not exists items_account_updated_idx on private_data.items (account_id, updated_at);
                    create index if not exists items_account_created_idx on private_data.items (account_id, created_at);
                    create index if not exists items_score_updated_idx on private_data.items (score_id, updated_at);
                    create index if not exists items_score_created_idx on private_data.items (score_id, created_at);
                    create unique index if not exists items_account_external_idx on private_data.items (account_id, external_id) where external_id is not null;
                    create index if not exists items_doc_gin_idx on private_data.items using gin (doc);

                    create table if not exists private_data.identifiers (
                        item_id text not null,
                        name text not null,
                        value text not null,
                        account_id text not null,
                        position integer,
                        created_at timestamptz,
                        updated_at timestamptz,
                        doc jsonb not null,
                        primary key (item_id, name)
                    );
                    create index if not exists identifiers_account_value_idx on private_data.identifiers (account_id, value);
                    create index if not exists identifiers_account_name_value_idx on private_data.identifiers (account_id, name, value);
                    create index if not exists identifiers_item_position_idx on private_data.identifiers (item_id, position);
                    create index if not exists identifiers_item_name_idx on private_data.identifiers (item_id, name);
                    create index if not exists identifiers_doc_gin_idx on private_data.identifiers using gin (doc);

                    create table if not exists private_data.score_results (
                        id text primary key,
                        item_id text not null,
                        account_id text not null,
                        scorecard_id text not null,
                        score_id text,
                        score_version_id text,
                        evaluation_id text,
                        scoring_job_id text,
                        feedback_item_id text,
                        type text,
                        status text,
                        code text,
                        created_at timestamptz,
                        updated_at timestamptz,
                        doc jsonb not null
                    );
                    create index if not exists score_results_account_updated_idx on private_data.score_results (account_id, updated_at);
                    create index if not exists score_results_item_idx on private_data.score_results (item_id);
                    create index if not exists score_results_scoring_job_idx on private_data.score_results (scoring_job_id);
                    create index if not exists score_results_scorecard_updated_idx on private_data.score_results (scorecard_id, updated_at);
                    create index if not exists score_results_scorecard_item_created_idx on private_data.score_results (scorecard_id, item_id, created_at);
                    create index if not exists score_results_evaluation_idx on private_data.score_results (evaluation_id);
                    create index if not exists score_results_score_version_idx on private_data.score_results (score_version_id);
                    create index if not exists score_results_score_idx on private_data.score_results (score_id);
                    create index if not exists score_results_scorecard_score_item_idx on private_data.score_results (scorecard_id, score_id, item_id);
                    create index if not exists score_results_item_scorecard_score_idx on private_data.score_results (item_id, scorecard_id, score_id);
                    create index if not exists score_results_type_status_updated_idx on private_data.score_results (type, status, updated_at);
                    create index if not exists score_results_item_type_score_updated_idx on private_data.score_results (item_id, type, score_id, updated_at);
                    create index if not exists score_results_doc_gin_idx on private_data.score_results using gin (doc);

                    create table if not exists private_data.feedback_items (
                        id text primary key,
                        account_id text not null,
                        scorecard_id text not null,
                        score_id text not null,
                        item_id text not null,
                        cache_key text not null,
                        edited_at timestamptz,
                        created_at timestamptz,
                        updated_at timestamptz,
                        doc jsonb not null
                    );
                    create index if not exists feedback_items_account_updated_idx on private_data.feedback_items (account_id, updated_at);
                    create index if not exists feedback_items_account_edited_idx on private_data.feedback_items (account_id, edited_at);
                    create index if not exists feedback_items_account_scorecard_score_updated_idx on private_data.feedback_items (account_id, scorecard_id, score_id, updated_at);
                    create index if not exists feedback_items_account_scorecard_score_edited_idx on private_data.feedback_items (account_id, scorecard_id, score_id, edited_at);
                    create index if not exists feedback_items_cache_key_idx on private_data.feedback_items (cache_key);
                    create index if not exists feedback_items_item_idx on private_data.feedback_items (item_id);
                    create index if not exists feedback_items_doc_gin_idx on private_data.feedback_items using gin (doc);

                    create table if not exists control_cache.graphql_responses (
                        cache_key text primary key,
                        operation_name text,
                        variables_hash text not null,
                        selection_hash text not null,
                        query text not null,
                        variables jsonb not null,
                        response jsonb not null,
                        fetched_at timestamptz not null,
                        expires_at timestamptz not null,
                        stale_until timestamptz not null
                    );
                    create index if not exists graphql_responses_expires_idx on control_cache.graphql_responses (expires_at);
                    create index if not exists graphql_responses_stale_until_idx on control_cache.graphql_responses (stale_until);

                    create table if not exists proxy_debug.upstream_requests (
                        id bigserial primary key,
                        created_at timestamptz not null default now(),
                        operation_name text,
                        root_fields text[] not null,
                        forwarded_query text not null,
                        variables jsonb not null
                    );
                    """
                )
                conn.commit()
        self.initialize_local_models()

    def initialize_local_models(self) -> None:
        contract = get_schema_contract()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("create schema if not exists local_data")
                for model in contract.models:
                    table = self._local_table_name(model)
                    cur.execute(
                        sql.SQL(
                            """
                            create table if not exists local_data.{table} (
                                pk text primary key,
                                primary_key jsonb not null,
                                id text,
                                account_id text,
                                created_at timestamptz,
                                updated_at timestamptz,
                                doc jsonb not null
                            )
                            """
                        ).format(table=sql.Identifier(table))
                    )
                    cur.execute(
                        sql.SQL(
                            "create index if not exists {index} on local_data.{table} (account_id)"
                        ).format(
                            index=sql.Identifier(f"{table}_account_idx"),
                            table=sql.Identifier(table),
                        )
                    )
                    cur.execute(
                        sql.SQL(
                            "create index if not exists {index} on local_data.{table} (updated_at)"
                        ).format(
                            index=sql.Identifier(f"{table}_updated_idx"),
                            table=sql.Identifier(table),
                        )
                    )
                    cur.execute(
                        sql.SQL(
                            "create index if not exists {index} on local_data.{table} using gin (doc)"
                        ).format(
                            index=sql.Identifier(f"{table}_doc_gin_idx"),
                            table=sql.Identifier(table),
                        )
                    )
                conn.commit()

    def ready(self) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 as ready")
                return cur.fetchone()["ready"] == 1

    def upsert_private(self, model: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        if self._uses_local_model_store(model):
            return self._upsert_local(model, input_doc)

        config = MODEL_CONFIGS[model]
        doc = self._normalize_private_doc(model, dict(input_doc))
        columns = list(config.columns.values())
        values = [self._column_value(doc, field) for field in config.columns]
        pk_columns = [config.columns[field] for field in config.pk_fields]
        update_columns = [column for column in columns if column not in pk_columns]

        sql = f"""
            insert into {config.table} ({", ".join(columns)}, doc)
            values ({", ".join(["%s"] * len(columns))}, %s)
            on conflict ({", ".join(pk_columns)})
            do update set
                {", ".join(f"{column} = excluded.{column}" for column in update_columns)},
                doc = excluded.doc
            returning doc
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (*values, Jsonb(doc)))
                row = cur.fetchone()
                conn.commit()
        return row["doc"]

    def update_private(self, model: str, input_doc: dict[str, Any]) -> Optional[dict[str, Any]]:
        if self._uses_local_model_store(model):
            existing = self.get_private(model, self._key_from_input(model, input_doc))
            if not existing:
                return None
            merged = {**existing, **input_doc}
            if "updatedAt" not in input_doc:
                merged["updatedAt"] = iso_now()
            return self._upsert_local(model, merged)

        existing = self.get_private(model, self._key_from_input(model, input_doc))
        if not existing:
            return None
        merged = {**existing, **input_doc}
        if "updatedAt" not in input_doc:
            merged["updatedAt"] = iso_now()
        return self.upsert_private(model, merged)

    def get_private(self, model: str, key: dict[str, Any]) -> Optional[dict[str, Any]]:
        if self._uses_local_model_store(model):
            return self._get_local(model, key)

        config = MODEL_CONFIGS[model]
        clauses = []
        values = []
        for field_name in config.pk_fields:
            clauses.append(f"{config.columns[field_name]} = %s")
            values.append(key.get(field_name))
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select doc from {config.table} where {' and '.join(clauses)}",
                    tuple(values),
                )
                row = cur.fetchone()
        return row["doc"] if row else None

    def delete_private(self, model: str, key: dict[str, Any]) -> Optional[dict[str, Any]]:
        if self._uses_local_model_store(model):
            return self._delete_local(model, key)

        config = MODEL_CONFIGS[model]
        clauses = []
        values = []
        for field_name in config.pk_fields:
            clauses.append(f"{config.columns[field_name]} = %s")
            values.append(key.get(field_name))
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"delete from {config.table} where {' and '.join(clauses)} returning doc",
                    tuple(values),
                )
                row = cur.fetchone()
                conn.commit()
        return row["doc"] if row else None

    def list_private(
        self,
        model: str,
        filters: dict[str, Any],
        sort_direction: str = "ASC",
        sort_field: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if self._uses_local_model_store(model):
            return self._list_local(
                model,
                filters,
                sort_direction=sort_direction,
                sort_field=sort_field,
                limit=limit,
                offset=offset,
            )

        config = MODEL_CONFIGS[model]
        clauses = []
        values: list[Any] = []
        for field_name, expected in filters.items():
            column = config.column_for(field_name)
            if not column:
                continue
            if isinstance(expected, dict):
                if "eq" in expected:
                    clauses.append(f"{column} = %s")
                    values.append(expected["eq"])
                elif "beginsWith" in expected:
                    clauses.append(f"{column}::text like %s")
                    values.append(f"{expected['beginsWith']}%")
                elif "between" in expected and isinstance(expected["between"], list) and len(expected["between"]) == 2:
                    start, end = expected["between"]
                    clauses.append(f"{column} >= %s and {column} <= %s")
                    values.extend([start, end])
                else:
                    if "ge" in expected:
                        clauses.append(f"{column} >= %s")
                        values.append(expected["ge"])
                    if "le" in expected:
                        clauses.append(f"{column} <= %s")
                        values.append(expected["le"])
            else:
                clauses.append(f"{column} = %s")
                values.append(expected)

        where_sql = f"where {' and '.join(clauses)}" if clauses else ""
        order_column = config.column_for(sort_field or "") or config.default_order
        direction = "DESC" if sort_direction.upper() == "DESC" else "ASC"
        limit_sql = "limit %s" if limit else ""
        offset_sql = "offset %s" if offset else ""
        if limit:
            values.append(limit)
        if offset:
            values.append(offset)

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select doc
                    from {config.table}
                    {where_sql}
                    order by {order_column} {direction} nulls last
                    {limit_sql}
                    {offset_sql}
                    """,
                    tuple(values),
                )
                rows = cur.fetchall()
        return [row["doc"] for row in rows]

    def get_cache(self, cache_key: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select response, fetched_at, expires_at, stale_until
                    from control_cache.graphql_responses
                    where cache_key = %s
                    """,
                    (cache_key,),
                )
                return cur.fetchone()

    def put_cache(
        self,
        cache_key: str,
        operation_name: Optional[str],
        query: str,
        variables: dict[str, Any],
        response: dict[str, Any],
        ttl_seconds: int,
        stale_seconds: int,
    ) -> None:
        fetched_at = utcnow()
        expires_at = fetched_at + timedelta(seconds=ttl_seconds)
        stale_until = fetched_at + timedelta(seconds=stale_seconds)
        variables_json = stable_json(variables)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into control_cache.graphql_responses (
                        cache_key, operation_name, variables_hash, selection_hash,
                        query, variables, response, fetched_at, expires_at, stale_until
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (cache_key) do update set
                        operation_name = excluded.operation_name,
                        variables_hash = excluded.variables_hash,
                        selection_hash = excluded.selection_hash,
                        query = excluded.query,
                        variables = excluded.variables,
                        response = excluded.response,
                        fetched_at = excluded.fetched_at,
                        expires_at = excluded.expires_at,
                        stale_until = excluded.stale_until
                    """,
                    (
                        cache_key,
                        operation_name,
                        digest(variables_json),
                        digest(query),
                        query,
                        Jsonb(variables),
                        Jsonb(response),
                        fetched_at,
                        expires_at,
                        stale_until,
                    ),
                )
                conn.commit()

    def cleanup_expired_cache(self) -> int:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from control_cache.graphql_responses where stale_until < now()"
                )
                deleted = cur.rowcount
                conn.commit()
        return deleted

    def record_upstream_request(
        self,
        operation_name: Optional[str],
        root_fields: list[str],
        forwarded_query: str,
        variables: dict[str, Any],
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into proxy_debug.upstream_requests (
                        operation_name, root_fields, forwarded_query, variables
                    )
                    values (%s, %s, %s, %s)
                    """,
                    (operation_name, root_fields, forwarded_query, Jsonb(variables)),
                )
                conn.commit()

    def upstream_requests(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select id, created_at, operation_name, root_fields, forwarded_query, variables
                    from proxy_debug.upstream_requests
                    order by id desc
                    limit 100
                    """
                )
                return cur.fetchall()

    def _normalize_private_doc(self, model: str, doc: dict[str, Any]) -> dict[str, Any]:
        if self._uses_local_model_store(model):
            return self._normalize_local_doc(model, doc)

        if model != "Identifier" and not doc.get("id"):
            doc["id"] = str(uuid.uuid4())
        now = iso_now()
        doc.setdefault("createdAt", now)
        doc.setdefault("updatedAt", now)
        if model == "Identifier":
            doc.setdefault("position", 0)
        return doc

    def _key_from_input(self, model: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        if self._uses_local_model_store(model):
            return {
                field: input_doc.get(field)
                for field in get_schema_contract().primary_key_fields(model)
            }

        config = MODEL_CONFIGS[model]
        return {field: input_doc.get(field) for field in config.pk_fields}

    def _column_value(self, doc: dict[str, Any], field_name: str) -> Any:
        value = doc.get(field_name)
        if field_name in {"createdAt", "updatedAt", "editedAt"}:
            return parse_datetime(value)
        return value

    def _uses_local_model_store(self, model: str) -> bool:
        return os.getenv("PLEXUS_BACKEND_MODE", "amplify") == "local" or model not in MODEL_CONFIGS

    def _local_table_name(self, model: str) -> str:
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", model).lower()
        return re.sub(r"[^a-z0-9_]", "_", snake)

    def _normalize_local_doc(self, model: str, doc: dict[str, Any]) -> dict[str, Any]:
        primary_key = get_schema_contract().primary_key_fields(model)
        if primary_key == ["id"] and not doc.get("id"):
            doc["id"] = str(uuid.uuid4())
        now = iso_now()
        doc.setdefault("createdAt", now)
        doc.setdefault("updatedAt", now)
        return doc

    def _local_pk_values(self, model: str, doc_or_key: dict[str, Any]) -> dict[str, Any]:
        return {
            field: doc_or_key.get(field)
            for field in get_schema_contract().primary_key_fields(model)
        }

    def _local_pk(self, model: str, doc_or_key: dict[str, Any]) -> str:
        values = self._local_pk_values(model, doc_or_key)
        missing = [field for field, value in values.items() if value is None]
        if missing:
            raise ValueError(f"{model} missing primary key fields: {', '.join(missing)}")
        return digest(stable_json(values))

    def _upsert_local(self, model: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        table = self._local_table_name(model)
        doc = self._normalize_local_doc(model, dict(input_doc))
        pk_values = self._local_pk_values(model, doc)
        pk = self._local_pk(model, doc)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        insert into local_data.{table} (
                            pk, primary_key, id, account_id, created_at, updated_at, doc
                        )
                        values (%s, %s, %s, %s, %s, %s, %s)
                        on conflict (pk) do update set
                            primary_key = excluded.primary_key,
                            id = excluded.id,
                            account_id = excluded.account_id,
                            created_at = excluded.created_at,
                            updated_at = excluded.updated_at,
                            doc = excluded.doc
                        returning doc
                        """
                    ).format(table=sql.Identifier(table)),
                    (
                        pk,
                        Jsonb(pk_values),
                        doc.get("id"),
                        doc.get("accountId"),
                        parse_datetime(doc.get("createdAt")),
                        parse_datetime(doc.get("updatedAt")),
                        Jsonb(doc),
                    ),
                )
                row = cur.fetchone()
                conn.commit()
        return row["doc"]

    def _get_local(self, model: str, key: dict[str, Any]) -> Optional[dict[str, Any]]:
        table = self._local_table_name(model)
        pk = self._local_pk(model, key)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("select doc from local_data.{table} where pk = %s").format(
                        table=sql.Identifier(table)
                    ),
                    (pk,),
                )
                row = cur.fetchone()
        return row["doc"] if row else None

    def _delete_local(self, model: str, key: dict[str, Any]) -> Optional[dict[str, Any]]:
        table = self._local_table_name(model)
        pk = self._local_pk(model, key)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("delete from local_data.{table} where pk = %s returning doc").format(
                        table=sql.Identifier(table)
                    ),
                    (pk,),
                )
                row = cur.fetchone()
                conn.commit()
        return row["doc"] if row else None

    def _list_local(
        self,
        model: str,
        filters: dict[str, Any],
        sort_direction: str = "ASC",
        sort_field: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        table = self._local_table_name(model)
        clauses = []
        values: list[Any] = []
        for field_name, expected in filters.items():
            if expected is None:
                continue
            if isinstance(expected, dict):
                if "eq" in expected:
                    clauses.append("doc ->> %s = %s")
                    values.extend([field_name, str(expected["eq"])])
                elif "beginsWith" in expected:
                    clauses.append("doc ->> %s like %s")
                    values.extend([field_name, f"{expected['beginsWith']}%"])
                elif "between" in expected and isinstance(expected["between"], list) and len(expected["between"]) == 2:
                    start, end = expected["between"]
                    if _is_timestamp_field(field_name):
                        clauses.append("(doc ->> %s)::timestamptz >= %s::timestamptz")
                        values.extend([field_name, str(start)])
                        clauses.append("(doc ->> %s)::timestamptz <= %s::timestamptz")
                        values.extend([field_name, str(end)])
                    else:
                        clauses.append("doc ->> %s >= %s")
                        values.extend([field_name, str(start)])
                        clauses.append("doc ->> %s <= %s")
                        values.extend([field_name, str(end)])
                else:
                    if "ge" in expected:
                        if _is_timestamp_field(field_name):
                            clauses.append("(doc ->> %s)::timestamptz >= %s::timestamptz")
                            values.extend([field_name, str(expected["ge"])])
                        else:
                            clauses.append("doc ->> %s >= %s")
                            values.extend([field_name, str(expected["ge"])])
                    if "le" in expected:
                        if _is_timestamp_field(field_name):
                            clauses.append("(doc ->> %s)::timestamptz <= %s::timestamptz")
                            values.extend([field_name, str(expected["le"])])
                        else:
                            clauses.append("doc ->> %s <= %s")
                            values.extend([field_name, str(expected["le"])])
                continue
            clauses.append("doc ->> %s = %s")
            values.extend([field_name, str(expected)])

        where_sql = sql.SQL(" where ") + sql.SQL(" and ").join(sql.SQL(clause) for clause in clauses) if clauses else sql.SQL("")
        order_field = sort_field or "updatedAt"
        direction = sql.SQL("DESC") if sort_direction.upper() == "DESC" else sql.SQL("ASC")
        limit_sql = sql.SQL(" limit %s") if limit else sql.SQL("")
        offset_sql = sql.SQL(" offset %s") if offset else sql.SQL("")

        query = sql.SQL(
            "select doc from local_data.{table}{where} order by doc ->> %s {direction} nulls last{limit}{offset}"
        ).format(
            table=sql.Identifier(table),
            where=where_sql,
            direction=direction,
            limit=limit_sql,
            offset=offset_sql,
        )
        values.append(order_field)
        if limit:
            values.append(limit)
        if offset:
            values.append(offset)

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(values))
                rows = cur.fetchall()
        return [row["doc"] for row in rows]


def cache_key_for(query: str, variables: dict[str, Any], operation_name: Optional[str]) -> str:
    return digest(stable_json({"query": query, "variables": variables, "operationName": operation_name}))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"), default=str)


def _is_timestamp_field(field_name: str) -> bool:
    return field_name.endswith("At")
