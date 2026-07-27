from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


DEFAULT_LOCAL_MODELS = frozenset({"Item", "ScoreResult", "FeedbackItem", "Identifier"})


@dataclass(frozen=True)
class RootOperation:
    root_name: str
    operation_type: str
    model: Optional[str]
    action: str
    index: Optional[dict[str, Any]] = None
    custom_operation: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class RootClassification:
    classification: str
    model: Optional[str]
    operation: Optional[RootOperation]


class SchemaContract:
    def __init__(self, manifest: dict[str, Any], sdl: str):
        self.manifest = manifest
        self.sdl = sdl
        self._roots = self._build_roots(manifest)
        self._relationships = {
            (relationship["model"], relationship["field"]): relationship
            for relationship in manifest["relationships"]
        }

    @property
    def models(self) -> dict[str, Any]:
        return self.manifest["models"]

    @property
    def indexes(self) -> dict[str, Any]:
        return self.manifest["indexes"]

    @property
    def custom_operations(self) -> dict[str, Any]:
        return self.manifest["customOperations"]

    def root_operation(self, root_name: str) -> Optional[RootOperation]:
        return self._roots.get(root_name)

    def model_for_root(self, root_name: str) -> Optional[str]:
        operation = self.root_operation(root_name)
        return operation.model if operation else None

    def relationship(self, model: str, field_name: str) -> Optional[dict[str, Any]]:
        return self._relationships.get((model, field_name))

    def primary_key_fields(self, model: str) -> list[str]:
        return list(self.models[model].get("primaryKey") or ["id"])

    def classify_root(
        self,
        root_name: str,
        operation_type: str,
        *,
        backend_mode: Optional[str] = None,
        local_models: Optional[set[str]] = None,
    ) -> RootClassification:
        mode = backend_mode or os.getenv("PLEXUS_BACKEND_MODE", "amplify")
        active_local_models = local_models if local_models is not None else configured_local_models()

        if root_name == "claimScoringJob" and mode == "local" and operation_type == "mutation":
            return RootClassification(
                "private",
                None,
                RootOperation(root_name, operation_type, None, "custom"),
            )

        operation = self.root_operation(root_name)
        if not operation and mode == "local" and operation_type == "query":
            operation = self._synthetic_legacy_index_operation(root_name)
        if not operation:
            return RootClassification("blocked", None, None)

        if operation.model:
            if mode == "local" or operation.model in active_local_models:
                return RootClassification("private", operation.model, operation)
            if operation_type == "query":
                return RootClassification("control", operation.model, operation)
            return RootClassification("blocked", operation.model, operation)

        if operation.custom_operation and operation_type == operation.operation_type:
            return RootClassification(
                "private" if mode == "local" else "control",
                None,
                operation,
            )

        return RootClassification("blocked", operation.model, operation)

    def _build_roots(self, manifest: dict[str, Any]) -> dict[str, RootOperation]:
        roots: dict[str, RootOperation] = {}
        for model_name, model in manifest["models"].items():
            operations = model["operations"]
            for action, operation_type in (
                ("get", "query"),
                ("list", "query"),
                ("create", "mutation"),
                ("update", "mutation"),
                ("delete", "mutation"),
            ):
                root_name = operations[action]
                roots[root_name] = RootOperation(root_name, operation_type, model_name, action)

            for index in manifest["indexes"].get(model_name, []):
                root_name = index["queryField"]
                index_operation = RootOperation(
                    root_name,
                    "query",
                    model_name,
                    "index",
                    index=index,
                )
                roots[root_name] = index_operation
                for alias_root_name in self._legacy_index_aliases(model_name, index):
                    roots.setdefault(
                        alias_root_name,
                        RootOperation(
                            alias_root_name,
                            "query",
                            model_name,
                            "index",
                            index=index,
                        ),
                    )

            for action in ("onCreate", "onUpdate", "onDelete"):
                root_name = manifest["subscriptions"][model_name][action]
                roots[root_name] = RootOperation(
                    root_name,
                    "subscription",
                    model_name,
                    action,
                )

        for name, operation in manifest["customOperations"].items():
            roots[name] = RootOperation(
                name,
                operation["operationType"],
                None,
                "custom",
                custom_operation=operation,
            )
        return roots

    @staticmethod
    def _legacy_index_aliases(model_name: str, index: dict[str, Any]) -> list[str]:
        """
        Backward-compatible aliases for historical Amplify index root naming.

        Some existing dashboard/CLI queries still use:
          list<Model>By<Partition>And<Sort>[And<Sort>...]
        while current generated roots may use explicit Amplify index names.
        """
        sort_fields = index.get("sortFields") or []
        partition_field = index.get("partitionField")
        if not sort_fields or not partition_field:
            return []

        legacy_alias = (
            f"list{model_name}By"
            f"{_pascal_case(partition_field)}"
            f"And{'And'.join(_pascal_case(field) for field in sort_fields)}"
        )
        if legacy_alias == index.get("queryField"):
            return []
        return [legacy_alias]

    def _synthetic_legacy_index_operation(self, root_name: str) -> Optional[RootOperation]:
        """
        Support legacy, still-in-use dashboard roots that are not present in the
        generated Amplify manifest, such as:
          listScoreByScorecardIdAndOrder
          listScorecardSectionByScorecardIdAndOrder
        """
        match = re.match(r"^list([A-Z][A-Za-z0-9]*)By([A-Z][A-Za-z0-9]*)And([A-Z][A-Za-z0-9]*)$", root_name)
        if not match:
            return None

        model_name, partition_pascal, sort_pascal = match.groups()
        model = self.models.get(model_name)
        if not model:
            return None

        partition_field = _camel_case(partition_pascal)
        sort_field = _camel_case(sort_pascal)
        model_fields = model.get("fields", {})
        if partition_field not in model_fields or sort_field not in model_fields:
            return None

        index = {
            "name": "legacySynthetic",
            "partitionField": partition_field,
            "sortFields": [sort_field],
            "queryField": root_name,
            "arguments": [partition_field, sort_field, "filter", "sortDirection", "limit", "nextToken"],
        }
        return RootOperation(
            root_name=root_name,
            operation_type="query",
            model=model_name,
            action="index",
            index=index,
        )


def configured_local_models() -> set[str]:
    configured = os.getenv("PLEXUS_PROXY_LOCAL_MODELS")
    if not configured:
        return set(DEFAULT_LOCAL_MODELS)
    return {model.strip() for model in configured.split(",") if model.strip()}


def schema_contract_dir() -> Path:
    configured = os.getenv("PLEXUS_SCHEMA_CONTRACT_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "schema"


@lru_cache(maxsize=1)
def get_schema_contract() -> SchemaContract:
    contract_dir = schema_contract_dir()
    manifest_path = contract_dir / "amplify-manifest.json"
    sdl_path = contract_dir / "amplify.graphql"
    if not manifest_path.exists() or not sdl_path.exists():
        raise RuntimeError(
            "schema contract artifacts are missing; run dashboard npm run schema:contract"
        )

    manifest = json.loads(manifest_path.read_text())
    validate_manifest(manifest)
    return SchemaContract(manifest, sdl_path.read_text())


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = {
        "contractVersion",
        "generator",
        "sources",
        "models",
        "indexes",
        "relationships",
        "customTypes",
        "customOperations",
        "authRules",
        "subscriptions",
        "storage",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise RuntimeError(f"schema contract manifest is missing sections: {', '.join(missing)}")
    if not manifest["models"]:
        raise RuntimeError("schema contract manifest does not contain any models")


def _pascal_case(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:]


def _camel_case(value: str) -> str:
    if not value:
        return value
    return value[0].lower() + value[1:]
