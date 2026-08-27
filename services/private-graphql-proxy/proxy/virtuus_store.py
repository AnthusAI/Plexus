from __future__ import annotations

import os
import threading
import uuid
from datetime import timedelta
from typing import Any, Optional

from virtuus import Database

from .document_store import (
    key_from_input,
    list_documents,
    local_table_name,
    missing_pk_fields,
    normalize_document,
    primary_key_fields,
)
from .schema_contract import get_schema_contract
from .store import iso_now, parse_datetime, scoring_job_claim_lease_seconds, utcnow
from .virtuus_schema import (
    GRAPHQL_CACHE_TABLE,
    SCORING_JOB_CLAIMS_TABLE,
    UPSTREAM_REQUESTS_TABLE,
    build_virtuus_schema,
)


class VirtuusStore:
    """File-backed GraphQL store using embedded Virtuus tables."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._lock = threading.RLock()
        self._db: Optional[Database] = None

    def _database(self) -> Database:
        if self._db is None:
            raise RuntimeError("VirtuusStore.initialize() has not been called")
        return self._db

    def _table(self, table_name: str):
        return self._database().tables[table_name]

    def initialize(self) -> None:
        with self._lock:
            os.makedirs(self.data_dir, exist_ok=True)
            schema = build_virtuus_schema()
            self._db = Database.from_schema_dict(schema, data_root=self.data_dir)

    def ready(self) -> bool:
        with self._lock:
            if self._db is None:
                return False
            return os.path.isdir(self.data_dir)

    def claim_scoring_job(
        self,
        *,
        account_id: str,
        scoring_job_id: str,
        item_id: str,
        scorecard_id: str,
        score_id: str,
        score_result_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            claims = self._table(SCORING_JOB_CLAIMS_TABLE)
            existing = claims.get(account_id, scoring_job_id)
            if existing is None:
                claims.put(
                    {
                        "accountId": account_id,
                        "scoringJobId": scoring_job_id,
                        "itemId": item_id,
                        "scorecardId": scorecard_id,
                        "scoreId": score_id,
                        "scoreResultId": score_result_id,
                        "claimedAt": iso_now(),
                    }
                )
                return {"state": "CLAIMED", "scoreResultId": score_result_id}

            if (existing["itemId"], existing["scorecardId"], existing["scoreId"]) != (
                item_id,
                scorecard_id,
                score_id,
            ):
                return {
                    "state": "CONFLICT",
                    "scoreResultId": existing["scoreResultId"],
                }

            if self.get_private("ScoreResult", {"id": existing["scoreResultId"]}):
                return {
                    "state": "COMPLETED",
                    "scoreResultId": existing["scoreResultId"],
                }

            claimed_at = parse_datetime(existing.get("claimedAt"))
            lease_seconds = scoring_job_claim_lease_seconds()
            if claimed_at is not None:
                stale_at = claimed_at + timedelta(seconds=lease_seconds)
                if utcnow() >= stale_at:
                    claims.put(
                        {
                            **existing,
                            "scoreResultId": score_result_id,
                            "claimedAt": iso_now(),
                        }
                    )
                    return {"state": "CLAIMED", "scoreResultId": score_result_id}

            return {
                "state": "IN_PROGRESS",
                "scoreResultId": existing["scoreResultId"],
            }

    def upsert_private(self, model: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            doc = normalize_document(model, dict(input_doc))
            self._put_document(model, doc)
            return doc

    def update_private(self, model: str, input_doc: dict[str, Any]) -> Optional[dict[str, Any]]:
        with self._lock:
            existing = self._get_document(model, key_from_input(model, input_doc))
            if not existing:
                return None
            merged = {**existing, **input_doc}
            if "updatedAt" not in input_doc:
                merged["updatedAt"] = iso_now()
            doc = normalize_document(model, merged)
            self._put_document(model, doc)
            return doc

    def get_private(self, model: str, key: dict[str, Any]) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._get_document(model, key)

    def delete_private(self, model: str, key: dict[str, Any]) -> Optional[dict[str, Any]]:
        with self._lock:
            existing = self._get_document(model, key)
            if existing is None:
                return None
            self._delete_document(model, key)
            return existing

    def list_private(
        self,
        model: str,
        filters: dict[str, Any],
        sort_direction: str = "ASC",
        sort_field: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._lock:
            table_name = local_table_name(model)
            if table_name not in self._database().tables:
                return []
            documents = self._table(table_name).scan()
            return list_documents(
                documents,
                filters,
                sort_direction=sort_direction,
                sort_field=sort_field,
                limit=limit,
                offset=offset,
            )

    def get_cache(self, cache_key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._table(GRAPHQL_CACHE_TABLE).get(cache_key)
            if row is None:
                return None
            return {
                "response": row.get("response"),
                "fetched_at": parse_datetime(row.get("fetchedAt")),
                "expires_at": parse_datetime(row.get("expiresAt")),
                "stale_until": parse_datetime(row.get("staleUntil")),
            }

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
        with self._lock:
            fetched_at = utcnow()
            expires_at = fetched_at + timedelta(seconds=ttl_seconds)
            stale_until = fetched_at + timedelta(seconds=stale_seconds)
            self._table(GRAPHQL_CACHE_TABLE).put(
                {
                    "cacheKey": cache_key,
                    "operationName": operation_name,
                    "query": query,
                    "variables": variables,
                    "response": response,
                    "fetchedAt": fetched_at.isoformat().replace("+00:00", "Z"),
                    "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
                    "staleUntil": stale_until.isoformat().replace("+00:00", "Z"),
                }
            )

    def cleanup_expired_cache(self) -> int:
        with self._lock:
            now = utcnow()
            cache_table = self._table(GRAPHQL_CACHE_TABLE)
            expired = [
                row
                for row in cache_table.scan()
                if parse_datetime(row.get("staleUntil")) is not None
                and parse_datetime(row.get("staleUntil")) < now
            ]
            for row in expired:
                cache_table.delete(row["cacheKey"])
            return len(expired)

    def record_upstream_request(
        self,
        operation_name: Optional[str],
        root_fields: list[str],
        forwarded_query: str,
        variables: dict[str, Any],
    ) -> None:
        with self._lock:
            self._table(UPSTREAM_REQUESTS_TABLE).put(
                {
                    "id": str(uuid.uuid4()),
                    "createdAt": iso_now(),
                    "operationName": operation_name,
                    "rootFields": root_fields,
                    "forwardedQuery": forwarded_query,
                    "variables": variables,
                }
            )

    def upstream_requests(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._table(UPSTREAM_REQUESTS_TABLE).scan()
            rows.sort(key=lambda row: row.get("createdAt") or "", reverse=True)
            return [
                {
                    "id": row.get("id"),
                    "created_at": parse_datetime(row.get("createdAt")),
                    "operation_name": row.get("operationName"),
                    "root_fields": row.get("rootFields") or [],
                    "forwarded_query": row.get("forwardedQuery") or "",
                    "variables": row.get("variables") or {},
                }
                for row in rows[:100]
            ]

    def _put_document(self, model: str, doc: dict[str, Any]) -> None:
        if missing_pk_fields(model, doc):
            missing = missing_pk_fields(model, doc)
            raise ValueError(f"{model} missing primary key fields: {', '.join(missing)}")
        table_name = local_table_name(model)
        if table_name not in self._database().tables:
            raise KeyError(f"model {model} is not registered in the Virtuus schema")
        self._table(table_name).put(doc)

    def _get_document(self, model: str, key: dict[str, Any]) -> Optional[dict[str, Any]]:
        if missing_pk_fields(model, key):
            return None
        table_name = local_table_name(model)
        if table_name not in self._database().tables:
            return None
        table = self._table(table_name)
        pk_fields = primary_key_fields(model)
        if len(pk_fields) == 1:
            return table.get(str(key[pk_fields[0]]))
        return table.get(str(key[pk_fields[0]]), str(key[pk_fields[1]]))

    def _delete_document(self, model: str, key: dict[str, Any]) -> None:
        table_name = local_table_name(model)
        table = self._table(table_name)
        pk_fields = primary_key_fields(model)
        if len(pk_fields) == 1:
            table.delete(str(key[pk_fields[0]]))
        else:
            table.delete(str(key[pk_fields[0]]), str(key[pk_fields[1]]))

    def model_directory(self, model: str) -> str:
        return os.path.join(self.data_dir, local_table_name(model))

    def supports_model(self, model: str) -> bool:
        return model in get_schema_contract().models
