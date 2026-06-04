from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timezone
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from graphql.language.ast import FieldNode, SelectionSetNode

from .config import Settings
from .graphql_tools import (
    RootField,
    all_argument_values,
    argument_value,
    build_operation_plan,
    build_root_only_query,
    project_list_connection,
)
from .schema_contract import get_schema_contract
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
    get_schema_contract()
    store.initialize()
    yield


app = FastAPI(
    title="Plexus Private GraphQL Proxy",
    version="0.1.0",
    lifespan=lifespan,
)

if settings.cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
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
        return JSONResponse(
            {"errors": [{"message": "invalid GraphQL operation"}]},
            status_code=400,
        )

    if plan.blocked_fields:
        blocked = ", ".join(field.name for field in plan.blocked_fields)
        return JSONResponse(
            {
                "errors": [
                    {
                        "message": (
                            "operation contains unsupported or unsafe root fields: "
                            f"{blocked}"
                        )
                    }
                ]
            },
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
        return handle_local_custom_field(field, variables)

    if operation_type == "mutation":
        input_doc = argument_value(field.node, "input", variables)
        if not isinstance(input_doc, dict):
            raise HTTPException(status_code=400, detail=f"{field.name} requires an input object")
        if field.name.startswith("create"):
            return project_model_value(
                field.model,
                store.upsert_private(field.model, input_doc),
                field.node.selection_set,
            )
        if field.name.startswith("update"):
            return project_model_value(
                field.model,
                store.update_private(field.model, input_doc),
                field.node.selection_set,
            )
        if field.name.startswith("delete"):
            return project_model_value(
                field.model,
                store.delete_private(field.model, input_doc),
                field.node.selection_set,
            )
        raise HTTPException(status_code=400, detail=f"unsupported private mutation {field.name}")

    if operation_type != "query":
        raise HTTPException(status_code=400, detail="subscriptions are not supported")

    if field.name.startswith("get"):
        return project_model_value(
            field.model,
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
        return project_model_connection(
            field.model,
            {"items": items, "nextToken": None},
            field.node.selection_set,
        )

    raise HTTPException(status_code=400, detail=f"unsupported private query {field.name}")


def handle_local_custom_field(field: RootField, variables: dict[str, Any]) -> Any:
    if field.name != "getResourceByShareToken":
        raise HTTPException(status_code=400, detail=f"{field.name} has no private model")

    token = argument_value(field.node, "token", variables)
    if not token:
        return None
    matches = store.list_private("ShareLink", {"token": token}, limit=1)
    share_link = matches[0] if matches else None
    if not share_link or share_link.get("isRevoked"):
        return None
    resource_type = share_link.get("resourceType")
    resource_id = share_link.get("resourceId")
    data = None
    if resource_type and resource_id and resource_type in get_schema_contract().models:
        data = store.get_private(resource_type, {"id": resource_id})
    return project_plain_value(
        {"shareLink": share_link, "data": data},
        field.node.selection_set,
    )


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
    if not field.model:
        return {}
    return {
        key: args.get(key)
        for key in get_schema_contract().primary_key_fields(field.model)
    }


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
    operation = get_schema_contract().root_operation(root_name)
    if operation and operation.index and operation.index.get("sortFields"):
        return operation.index["sortFields"][-1]

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


def project_model_connection(
    model: str,
    connection: dict[str, Any],
    selection_set: Optional[SelectionSetNode],
) -> dict[str, Any]:
    if selection_set is None:
        return connection

    projected: dict[str, Any] = {}
    for selection in selection_set.selections:
        if not isinstance(selection, FieldNode):
            continue
        field_name = selection.name.value
        response_key = selection.alias.value if selection.alias else field_name
        if field_name == "items":
            projected[response_key] = [
                project_model_value(model, item, selection.selection_set)
                for item in connection.get("items", [])
            ]
        else:
            projected[response_key] = connection.get(field_name)
    return projected


def project_model_value(
    model: str,
    value: Any,
    selection_set: Optional[SelectionSetNode],
) -> Any:
    if value is None or selection_set is None:
        return value
    if isinstance(value, list):
        return [project_model_value(model, item, selection_set) for item in value]
    if not isinstance(value, dict):
        return value

    projected: dict[str, Any] = {}
    for selection in selection_set.selections:
        if not isinstance(selection, FieldNode):
            continue
        field_name = selection.name.value
        response_key = selection.alias.value if selection.alias else field_name
        relationship = get_schema_contract().relationship(model, field_name)
        if relationship:
            projected[response_key] = project_relationship(value, relationship, selection.selection_set)
            continue

        child = value.get(field_name)
        if isinstance(child, dict):
            projected[response_key] = project_plain_value(child, selection.selection_set)
        elif isinstance(child, list):
            projected[response_key] = [
                project_plain_value(item, selection.selection_set)
                for item in child
            ]
        else:
            projected[response_key] = child
    return projected


def project_relationship(
    source: dict[str, Any],
    relationship: dict[str, Any],
    selection_set: Optional[SelectionSetNode],
) -> Any:
    target_model = relationship["targetModel"]
    target_field = relationship["targetField"]
    kind = relationship["kind"]

    if kind == "belongsTo":
        target_id = source.get(target_field)
        target = store.get_private(target_model, {"id": target_id}) if target_id else None
        return project_model_value(target_model, target, selection_set)

    source_id = source.get("id")
    if not source_id:
        return {"items": [], "nextToken": None} if kind == "hasMany" else None

    matches = store.list_private(target_model, {target_field: source_id}, limit=100)
    if kind == "hasOne":
        return project_model_value(target_model, matches[0] if matches else None, selection_set)

    return project_model_connection(
        target_model,
        {"items": matches, "nextToken": None},
        selection_set,
    )


def project_plain_value(value: Any, selection_set: Optional[SelectionSetNode]) -> Any:
    if value is None or selection_set is None:
        return value
    if isinstance(value, list):
        return [project_plain_value(item, selection_set) for item in value]
    if not isinstance(value, dict):
        return value

    projected: dict[str, Any] = {}
    for selection in selection_set.selections:
        if not isinstance(selection, FieldNode):
            continue
        field_name = selection.name.value
        response_key = selection.alias.value if selection.alias else field_name
        child = value.get(field_name)
        if isinstance(child, (dict, list)):
            projected[response_key] = project_plain_value(child, selection.selection_set)
        else:
            projected[response_key] = child
    return projected
