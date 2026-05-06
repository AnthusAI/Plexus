#!/usr/bin/env python3
"""
Create one Evaluation, Procedure, and ScoreVersion and print attribution fields.

Usage example:
  python3 scripts/attribution_smoke.py \
    --account-id <account-id> \
    --score-id <score-id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict

# Allow running from repo root without editable install.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plexus.cli.shared.client_utils import create_client
from plexus.dashboard.api.models.evaluation import Evaluation
from plexus.dashboard.api.models.procedure import Procedure
from plexus.dashboard.api.models.score import Score


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_json(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return json.loads(text)
        except Exception:
            return value
    return value


def _read_record(client: Any, model_name: str, record_id: str) -> Dict[str, Any]:
    query = f"""
    query Read{model_name}($id: ID!) {{
      get{model_name}(id: $id) {{
        id
        createdByUserId
        metadata
        parameters
        updatedAt
        createdAt
      }}
    }}
    """
    result = client.execute(query, {"id": record_id})
    payload = result.get(f"get{model_name}") or {}
    if "metadata" in payload:
        payload["metadata"] = _parse_json(payload.get("metadata"))
    if "parameters" in payload:
        payload["parameters"] = _parse_json(payload.get("parameters"))
    return payload


def run(args: argparse.Namespace) -> Dict[str, Any]:
    client = create_client()
    now = _iso_now()
    tag = f"attribution-smoke-{now}"

    evaluation = Evaluation.create(
        client=client,
        type="accuracy",
        accountId=args.account_id,
        scoreId=args.score_id,
        status="PENDING",
        accuracy=0.0,
        inferences=0,
        parameters={
            "source": "scripts/attribution_smoke.py",
            "tag": tag,
        },
    )

    procedure = Procedure.create(
        client=client,
        accountId=args.account_id,
        name=f"Attribution Smoke {now}",
        scoreId=args.score_id,
        metadata={
            "source": "scripts/attribution_smoke.py",
            "tag": tag,
        },
    )

    score = Score.get_by_id(args.score_id, client=client)
    score_version_result = score.create_version_from_code(
        args.score_yaml,
        note=f"Attribution smoke {now}",
        guidelines=args.guidelines,
    )
    if not score_version_result.get("success"):
        raise RuntimeError(
            f"ScoreVersion create failed: {score_version_result.get('error')} - {score_version_result.get('message')}"
        )
    score_version_id = score_version_result["version_id"]

    read_score_version_query = """
    query ReadScoreVersion($id: ID!) {
      getScoreVersion(id: $id) {
        id
        scoreId
        createdByUserId
        metadata
        note
        createdAt
        updatedAt
      }
    }
    """
    score_version_payload = client.execute(read_score_version_query, {"id": score_version_id}).get("getScoreVersion") or {}
    score_version_payload["metadata"] = _parse_json(score_version_payload.get("metadata"))

    return {
        "inputs": {
            "accountId": args.account_id,
            "scoreId": args.score_id,
            "tag": tag,
        },
        "created": {
            "evaluationId": evaluation.id,
            "procedureId": procedure.id,
            "scoreVersionId": score_version_id,
        },
        "records": {
            "evaluation": _read_record(client, "Evaluation", evaluation.id),
            "procedure": _read_record(client, "Procedure", procedure.id),
            "scoreVersion": score_version_payload,
        },
        "env": {
            "PLEXUS_ACTOR_USER_ID": args.actor_user_id,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attribution smoke for Evaluation/Procedure/ScoreVersion")
    parser.add_argument("--account-id", required=True, help="Account ID for Evaluation/Procedure creation")
    parser.add_argument("--score-id", required=True, help="Score ID for Evaluation and ScoreVersion creation")
    parser.add_argument(
        "--score-yaml",
        default="name: Attribution Smoke\\nclass: NumericClassifier\\n",
        help="YAML body for new ScoreVersion configuration",
    )
    parser.add_argument(
        "--guidelines",
        default="Smoke guideline for attribution verification.",
        help="Guidelines to attach to created score version",
    )
    parser.add_argument(
        "--actor-user-id",
        default="",
        help="Optional echo field for reporting expected actor user id",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    output = run(arguments)
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
