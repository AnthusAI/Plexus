from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timezone
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import Settings
from .graphql_tools import (
    RootField,
    all_argument_values,
    argument_value,
    build_operation_plan,
    build_root_only_query,
    project_list_connection,
    project_value,
)
from .store import PostgresStore, cache_key_for, utcnow
from .upstream import UpstreamAppSyncClient


settings = Settings.from_env()
store = PostgresStore(settings.database_url)
upstream = UpstreamAppSyncClient(
    settings.upstream_api_url,
    settings.upstream_api_key,
    settings.upstream_timeout_seconds,
    settings.upstream_disabled,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.initialize()
    yield


app = FastAPI(
    title="Plexus Private GraphQL Proxy",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    if not store.ready():
        raise HTTPException(status_code=503, detail="database is not ready")
    return {"status": "ready"}


@app.get("/debug/upstream-requests")
def debug_upstream_requests() -> list[dict[str, Any]]:
    if not settings.enable_debug:
        raise HTTPException(status_code=404, detail="debug endpoints are disabled")
    return store.upstream_requests()


@app.post("/graphql")
async def graphql_endpoint(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
) -> JSONResponse:
    if settings.proxy_api_key and x_api_key != settings.proxy_api_key:
        raise HTTPException(status_code=401, detail="invalid proxy API key")

    payload = await request.json()
    query = payload.get("query")
    variables = payload.get("variables") or {}
    operation_name = payload.get("operationName")
    if not query:
        raise HTTPException(status_code=400, detail="GraphQL query is required")

    try:
        plan = build_operation_plan(query, operation_name)
    except Exception:
        return graphql_error("invalid GraphQL operation", status_code=400)

    if plan.blocked_fields:
        blocked = ", ".join(field.name for field in plan.blocked_fields)
        return graphql_error(
            f"operation contains unsupported or unsafe root fields: {blocked}",
            status_code=400,
        )

    data: dict[str, Any] = {}
    extensions: dict[str, Any] = {"proxy": {"private": [], "control": []}}

    for field in plan.private_fields:
        data[field.response_key] = handle_private_field(field, variables, plan.operation_type)
        extensions["proxy"]["private"].append(field.name)

    if plan.control_fields:
        control_query = (
            query
            if len(plan.control_fields) == len(plan.root_fields)
            else build_root_only_query(plan, plan.control_fields)
        )
        control_response, cache_status = execute_control_query(
            control_query,
            variables,
            operation_name,
            [field.name for field in plan.control_fields],
        )
        data.update(control_response.get("data") or {})
        extensions["proxy"]["control"].append(
            {"roots": [field.name for field in plan.control_fields], "cache": cache_status}
        )

    return JSONResponse({"data": data, "extensions": extensions})


def handle_private_field(
    field: RootField,
    variables: dict[str, Any],
    operation_type: str,
) -> Any:
    if not field.model:
        raise HTTPException(status_code=400, detail=f"{field.name} has no private model")

    if operation_type == "mutation":
        input_doc = argument_value(field.node, "input", variables)
        if not isinstance(input_doc, dict):
            raise HTTPException(status_code=400, detail=f"{field.name} requires an input object")
        if field.name.startswith("create"):
            return project_value(
                store.upsert_private(field.model, input_doc),
                field.node.selection_set,
            )
        if field.name.startswith("update"):
            return project_value(
                store.update_private(field.model, input_doc),
                field.node.selection_set,
            )
        if field.name.startswith("delete"):
            return project_value(
                store.delete_private(field.model, input_doc),
                field.node.selection_set,
            )
        raise HTTPException(status_code=400, detail=f"unsupported private mutation {field.name}")

    if operation_type != "query":
        raise HTTPException(status_code=400, detail="subscriptions are not supported")

    if field.name.startswith("get"):
        return project_value(
            store.get_private(field.model, key_arguments(field, variables)),
            field.node.selection_set,
        )

    if field.name.startswith("list"):
        args = all_argument_values(field.node, variables)
        filters = list_filters(args)
        filters.update(composite_begins_with_filters(args))
        sort_field = sort_field_for_root(field.name)
        sort_direction = args.get("sortDirection") or "ASC"
        items = store.list_private(
            field.model,
            filters,
            sort_direction=sort_direction,
            sort_field=sort_field,
            limit=args.get("limit"),
        )
        return project_list_connection(
            {"items": items, "nextToken": None},
            field.node.selection_set,
        )

    raise HTTPException(status_code=400, detail=f"unsupported private query {field.name}")


def execute_control_query(
    query: str,
    variables: dict[str, Any],
    operation_name: Optional[str],
    root_fields: list[str],
) -> tuple[dict[str, Any], str]:
    key = cache_key_for(query, variables, operation_name)
    cache_row = store.get_cache(key)
    now = utcnow()
    if cache_row and cache_row["expires_at"].astimezone(timezone.utc) >= now:
        return cache_row["response"], "fresh"

    try:
        response = upstream.execute(query, variables, operation_name)
        store.record_upstream_request(operation_name, root_fields, query, variables)
        store.put_cache(
            key,
            operation_name,
            query,
            variables,
            response,
            settings.cache_ttl_seconds,
            settings.cache_stale_seconds,
        )
        return response, "miss"
    except Exception as exc:
        if cache_row and cache_row["stale_until"].astimezone(timezone.utc) >= now:
            return cache_row["response"], "stale"
        raise HTTPException(status_code=502, detail="upstream control query failed") from exc


def key_arguments(field: RootField, variables: dict[str, Any]) -> dict[str, Any]:
    args = all_argument_values(field.node, variables)
    if field.model == "Identifier":
        return {"itemId": args.get("itemId"), "name": args.get("name")}
    return {"id": args.get("id")}


def list_filters(args: dict[str, Any]) -> dict[str, Any]:
    ignored = {"filter", "limit", "nextToken", "sortDirection"}
    filters = {
        name: value
        for name, value in args.items()
        if name not in ignored and value is not None and not isinstance(value, dict)
    }
    filter_arg = args.get("filter")
    if isinstance(filter_arg, dict):
        filters.update(filter_arg)
    for name, value in args.items():
        if name in ignored or value is None:
            continue
        if isinstance(value, dict) and "eq" in value:
            filters[name] = value["eq"]
    return filters


def composite_begins_with_filters(args: dict[str, Any]) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for value in args.values():
        if not isinstance(value, dict):
            continue
        begins_with = value.get("beginsWith")
        if isinstance(begins_with, dict):
            filters.update(begins_with)
    return filters


def sort_field_for_root(root_name: str) -> Optional[str]:
    suffixes = (
        ("UpdatedAt", "updatedAt"),
        ("CreatedAt", "createdAt"),
        ("EditedAt", "editedAt"),
        ("Position", "position"),
        ("Name", "name"),
    )
    for suffix, field_name in suffixes:
        if root_name.endswith(suffix):
            return field_name
    return None


def graphql_error(message: str, status_code: int = 200) -> JSONResponse:
    return JSONResponse({"errors": [{"message": message}]}, status_code=status_code)
