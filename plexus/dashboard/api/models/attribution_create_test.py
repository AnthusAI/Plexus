from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from plexus.dashboard.api.models.evaluation import Evaluation
from plexus.dashboard.api.models.procedure import Procedure
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.score import Score


pytestmark = pytest.mark.unit


class _Context:
    actor_user_id = "user-123"
    actor_type = "agent"
    actor_key = "execute_tactus"
    actor_source = "execute_tactus"


def test_report_create_injects_actor_attribution():
    client = Mock()
    client.context = _Context()
    client.execute.return_value = {
        "createReport": {
            "id": "report-1",
            "accountId": "acc-1",
            "name": "Report",
            "taskId": "task-1",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "parameters": "{\"attribution\":{\"actorType\":\"agent\"}}",
        }
    }
    Report.create(client=client, accountId="acc-1", taskId="task-1", name="Report")
    input_data = client.execute.call_args[0][1]["input"]
    assert input_data["createdByUserId"] == "user-123"
    params = input_data["parameters"]
    if isinstance(params, str):
        params = json.loads(params)
    assert params["attribution"]["actorKey"] == "execute_tactus"


def test_evaluation_create_injects_actor_attribution():
    client = Mock()
    client.context = _Context()
    client.execute.return_value = {
        "createEvaluation": {
            "id": "eval-1",
            "type": "accuracy",
            "accountId": "acc-1",
            "status": "PENDING",
            "accuracy": 0.0,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "parameters": "{\"attribution\":{\"actorType\":\"agent\"}}",
        }
    }

    Evaluation.create(client=client, type="accuracy", accountId="acc-1")
    input_data = client.execute.call_args[0][1]["input"]
    assert input_data["createdByUserId"] == "user-123"
    params = json.loads(input_data["parameters"])
    assert params["attribution"]["source"] == "execute_tactus"


def test_evaluation_create_preserves_explicit_created_by_user_id():
    client = Mock()
    client.context = _Context()
    client.execute.return_value = {
        "createEvaluation": {
            "id": "eval-1",
            "type": "accuracy",
            "accountId": "acc-1",
            "status": "PENDING",
            "accuracy": 0.0,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "parameters": "{\"attribution\":{\"actorType\":\"agent\"}}",
        }
    }

    Evaluation.create(
        client=client,
        type="accuracy",
        accountId="acc-1",
        createdByUserId="explicit-user",
    )
    input_data = client.execute.call_args[0][1]["input"]
    assert input_data["createdByUserId"] == "explicit-user"
    params = json.loads(input_data["parameters"])
    assert params["attribution"]["requestUserId"] == "user-123"


def test_procedure_create_injects_actor_attribution():
    client = Mock()
    client.context = _Context()
    client.execute.return_value = {
        "createProcedure": {
            "id": "proc-1",
            "name": "Procedure",
            "status": "RUNNING",
            "featured": False,
            "isTemplate": False,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "accountId": "acc-1",
            "metadata": {"attribution": {"actorType": "agent"}},
        }
    }
    Procedure.create(client=client, accountId="acc-1", name="Procedure")
    input_data = client.execute.call_args[0][1]["input"]
    assert input_data["createdByUserId"] == "user-123"
    metadata = input_data["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    assert metadata["attribution"]["source"] == "execute_tactus"


def test_procedure_create_preserves_explicit_created_by_user_id():
    client = Mock()
    client.context = _Context()
    client.execute.return_value = {
        "createProcedure": {
            "id": "proc-1",
            "name": "Procedure",
            "status": "RUNNING",
            "featured": False,
            "isTemplate": False,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "accountId": "acc-1",
            "metadata": {"attribution": {"actorType": "agent"}},
        }
    }

    Procedure.create(
        client=client,
        accountId="acc-1",
        name="Procedure",
        createdByUserId="explicit-user",
    )
    input_data = client.execute.call_args[0][1]["input"]
    assert input_data["createdByUserId"] == "explicit-user"
    metadata = input_data["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    assert metadata["attribution"]["requestUserId"] == "user-123"


def test_score_create_version_injects_actor_attribution():
    client = Mock()
    client.context = _Context()
    client.execute.side_effect = [
        {"getScore": {"championVersionId": None}},
        {
            "createScoreVersion": {
                "id": "sv-1",
                "configuration": "foo: bar",
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-01T00:00:00Z",
                "note": "new",
                "metadata": {},
                "createdByUserId": "user-123",
                "score": {"id": "score-1", "championVersionId": "sv-1"},
            }
        },
    ]

    score = Score(
        id="score-1",
        name="Score",
        key="score",
        externalId="1",
        type="classification",
        order=1,
        sectionId="sec-1",
        client=client,
    )

    result = score.create_version_from_code("foo: bar")
    assert result["success"] is True
    mutation_input = client.execute.call_args_list[1][0][1]["input"]
    assert mutation_input["createdByUserId"] == "user-123"
    assert mutation_input["metadata"]["attribution"]["actorType"] == "agent"
