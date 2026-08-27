from __future__ import annotations

from typing import Any

from .document_store import local_table_name
from .schema_contract import get_schema_contract


SCORING_JOB_CLAIMS_TABLE = "scoring_job_claims"
GRAPHQL_CACHE_TABLE = "graphql_cache"
UPSTREAM_REQUESTS_TABLE = "upstream_requests"


def build_virtuus_schema() -> dict[str, Any]:
    contract = get_schema_contract()
    tables: dict[str, Any] = {}

    for model_name in contract.models:
        table_name = local_table_name(model_name)
        pk_fields = contract.primary_key_fields(model_name)
        table_conf: dict[str, Any] = {"directory": table_name}
        if len(pk_fields) == 1:
            table_conf["primary_key"] = pk_fields[0]
        else:
            table_conf["partition_key"] = pk_fields[0]
            table_conf["sort_key"] = pk_fields[1]
        tables[table_name] = table_conf

    tables[SCORING_JOB_CLAIMS_TABLE] = {
        "directory": SCORING_JOB_CLAIMS_TABLE,
        "partition_key": "accountId",
        "sort_key": "scoringJobId",
    }
    tables[GRAPHQL_CACHE_TABLE] = {
        "directory": GRAPHQL_CACHE_TABLE,
        "primary_key": "cacheKey",
    }
    tables[UPSTREAM_REQUESTS_TABLE] = {
        "directory": UPSTREAM_REQUESTS_TABLE,
        "primary_key": "id",
    }
    return {"tables": tables}
