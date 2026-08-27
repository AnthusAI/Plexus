from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from .schema_contract import get_schema_contract
from .store import iso_now, parse_datetime


def local_table_name(model: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", model).lower()
    return re.sub(r"[^a-z0-9_]", "_", snake)


def primary_key_fields(model: str) -> list[str]:
    return list(get_schema_contract().primary_key_fields(model))


def normalize_document(model: str, doc: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(doc)
    pk_fields = primary_key_fields(model)
    if pk_fields == ["id"] and not normalized.get("id"):
        normalized["id"] = str(uuid.uuid4())
    now = iso_now()
    normalized.setdefault("createdAt", now)
    normalized.setdefault("updatedAt", now)
    if model == "Identifier":
        normalized.setdefault("position", 0)
    return normalized


def key_from_input(model: str, input_doc: dict[str, Any]) -> dict[str, Any]:
    return {field: input_doc.get(field) for field in primary_key_fields(model)}


def pk_values(model: str, doc_or_key: dict[str, Any]) -> dict[str, Any]:
    return {field: doc_or_key.get(field) for field in primary_key_fields(model)}


def missing_pk_fields(model: str, doc_or_key: dict[str, Any]) -> list[str]:
    values = pk_values(model, doc_or_key)
    return [field for field, value in values.items() if value is None]


def is_timestamp_field(field_name: str) -> bool:
    return field_name.endswith("At")


def document_matches_filter(doc: dict[str, Any], field_name: str, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, dict):
        value = doc.get(field_name)
        if "eq" in expected:
            return value == expected["eq"]
        if "beginsWith" in expected:
            return str(value or "").startswith(str(expected["beginsWith"]))
        if "between" in expected and isinstance(expected["between"], list) and len(expected["between"]) == 2:
            start, end = expected["between"]
            comparable = str(value or "")
            if is_timestamp_field(field_name):
                comparable_dt = parse_datetime(value)
                start_dt = parse_datetime(start)
                end_dt = parse_datetime(end)
                if comparable_dt is None or start_dt is None or end_dt is None:
                    return False
                return start_dt <= comparable_dt <= end_dt
            return str(start) <= comparable <= str(end)
        if "ge" in expected:
            if is_timestamp_field(field_name):
                comparable_dt = parse_datetime(value)
                ge_dt = parse_datetime(expected["ge"])
                if comparable_dt is None or ge_dt is None:
                    return False
                if comparable_dt < ge_dt:
                    return False
            elif str(value or "") < str(expected["ge"]):
                return False
        if "le" in expected:
            if is_timestamp_field(field_name):
                comparable_dt = parse_datetime(value)
                le_dt = parse_datetime(expected["le"])
                if comparable_dt is None or le_dt is None:
                    return False
                if comparable_dt > le_dt:
                    return False
            elif str(value or "") > str(expected["le"]):
                return False
        return True
    return doc.get(field_name) == expected


def filter_documents(
    documents: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    filtered = documents
    for field_name, expected in filters.items():
        if expected is None:
            continue
        filtered = [
            doc for doc in filtered if document_matches_filter(doc, field_name, expected)
        ]
    return filtered


def sort_documents(
    documents: list[dict[str, Any]],
    sort_field: Optional[str],
    sort_direction: str,
) -> list[dict[str, Any]]:
    field = sort_field or "updatedAt"
    reverse = sort_direction.upper() == "DESC"
    return sorted(
        documents,
        key=lambda doc: doc.get(field) or "",
        reverse=reverse,
    )


def list_documents(
    documents: list[dict[str, Any]],
    filters: dict[str, Any],
    sort_direction: str = "ASC",
    sort_field: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    docs = filter_documents(documents, filters)
    docs = sort_documents(docs, sort_field, sort_direction)
    if offset:
        docs = docs[offset:]
    if limit is not None:
        docs = docs[:limit]
    return docs
