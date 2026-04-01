#!/usr/bin/env python3
"""
Create or update a dedicated Console chat procedure and print its ID.

Usage:
  python scripts/upsert_console_chat_procedure.py
  python scripts/upsert_console_chat_procedure.py --procedure-id <id>
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from typing import Any, Dict, Optional

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plexus.dashboard.api.client import ClientContext, PlexusDashboardClient


LIST_PROCEDURES_QUERY = """
query ListProcedureByAccount($accountId: String!, $limit: Int) {
  listProcedureByAccountIdAndUpdatedAt(
    accountId: $accountId
    sortDirection: DESC
    limit: $limit
  ) {
    items {
      id
      name
      category
      status
      isTemplate
      accountId
      updatedAt
    }
  }
}
"""


GET_PROCEDURE_QUERY = """
query GetProcedure($id: ID!) {
  getProcedure(id: $id) {
    id
    name
    category
    status
    isTemplate
    accountId
  }
}
"""


CREATE_PROCEDURE_MUTATION = """
mutation CreateProcedure($input: CreateProcedureInput!) {
  createProcedure(input: $input) {
    id
    name
    category
    status
    accountId
    updatedAt
  }
}
"""


UPDATE_PROCEDURE_MUTATION = """
mutation UpdateProcedure($input: UpdateProcedureInput!) {
  updateProcedure(input: $input) {
    id
    name
    category
    status
    accountId
    updatedAt
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account-key",
        default=os.getenv("PLEXUS_ACCOUNT_KEY"),
        help="Account key (defaults to PLEXUS_ACCOUNT_KEY).",
    )
    parser.add_argument(
        "--yaml",
        default="plexus/procedures/console_chat_agent.yaml",
        help="Path to Console procedure YAML source.",
    )
    parser.add_argument(
        "--procedure-id",
        default=None,
        help="Procedure ID to update explicitly. If omitted, upsert by category+name.",
    )
    parser.add_argument(
        "--category",
        default="builtin:console_chat",
        help="Category for the Console procedure.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Override procedure name (defaults to YAML `name`).",
    )
    parser.add_argument(
        "--status",
        default="COMPLETED",
        help="Procedure status to write on create/update.",
    )
    return parser.parse_args()


def load_yaml(yaml_path: pathlib.Path) -> tuple[str, Dict[str, Any]]:
    source = yaml_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(source)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected YAML object at top level: {yaml_path}")
    return source, parsed


def pick_existing_procedure(
    items: list[Dict[str, Any]],
    desired_name: str,
    desired_category: str,
) -> Optional[Dict[str, Any]]:
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("isTemplate") is True:
            continue
        if item.get("category") != desired_category:
            continue
        if item.get("name") != desired_name:
            continue
        return item
    return None


def main() -> int:
    args = parse_args()
    if not args.account_key:
        print("Missing account key. Set PLEXUS_ACCOUNT_KEY or pass --account-key.", file=sys.stderr)
        return 1

    yaml_path = pathlib.Path(args.yaml)
    if not yaml_path.exists():
        print(f"YAML file not found: {yaml_path}", file=sys.stderr)
        return 1

    source, parsed = load_yaml(yaml_path)
    name = args.name or parsed.get("name") or "Console Chat Agent"
    description = parsed.get("description") or "General-purpose Console chat procedure."
    version = parsed.get("version")
    category = parsed.get("category") or args.category

    client = PlexusDashboardClient(context=ClientContext(account_key=args.account_key))
    account_id = client._resolve_account_id()

    update_input: Dict[str, Any] = {
        "name": name,
        "description": description,
        "category": category,
        "code": source,
        "status": args.status,
        "isTemplate": False,
    }
    if version:
        update_input["version"] = str(version)

    target_id = args.procedure_id
    if target_id:
        result = client.execute(GET_PROCEDURE_QUERY, {"id": target_id})
        existing = result.get("getProcedure")
        if not existing:
            print(f"Procedure not found: {target_id}", file=sys.stderr)
            return 1
        if existing.get("accountId") != account_id:
            print(
                f"Procedure {target_id} belongs to a different account ({existing.get('accountId')}).",
                file=sys.stderr,
            )
            return 1
    else:
        result = client.execute(
            LIST_PROCEDURES_QUERY,
            {"accountId": account_id, "limit": 200},
        )
        items = result.get("listProcedureByAccountIdAndUpdatedAt", {}).get("items", [])
        existing = pick_existing_procedure(items, desired_name=name, desired_category=category)
        target_id = existing.get("id") if existing else None

    if target_id:
        payload = {"input": {"id": target_id, **update_input}}
        updated = client.execute(UPDATE_PROCEDURE_MUTATION, payload).get("updateProcedure")
        if not updated:
            print(f"Failed to update procedure {target_id}", file=sys.stderr)
            return 1
        procedure_id = updated["id"]
        print(f"Updated procedure: {procedure_id}")
    else:
        payload_input = {
            "accountId": account_id,
            "featured": False,
            **update_input,
        }
        created = client.execute(CREATE_PROCEDURE_MUTATION, {"input": payload_input}).get("createProcedure")
        if not created:
            print("Failed to create console procedure", file=sys.stderr)
            return 1
        procedure_id = created["id"]
        print(f"Created procedure: {procedure_id}")

    print(f"CONSOLE_PROCEDURE_ID={procedure_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
