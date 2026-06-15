from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


API_URL = os.getenv("PLEXUS_API_URL", "http://localhost:18080/graphql")
API_KEY = os.getenv("PLEXUS_API_KEY", os.getenv("PLEXUS_PROXY_API_KEY", "local-smoke-key"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def execute(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.post(
        API_URL,
        json={"query": query, "variables": variables or {}},
        headers={"x-api-key": API_KEY},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def wait_for_proxy() -> None:
    health_url = API_URL.replace("/graphql", "/readyz")
    for _ in range(60):
        try:
            response = requests.get(health_url, timeout=2)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError(f"Local proxy did not become ready at {health_url}")


def create(model: str, input_doc: dict[str, Any]) -> dict[str, Any]:
    mutation = f"""
    mutation Seed{model}($input: Create{model}Input!) {{
      create{model}(input: $input) {{ id }}
    }}
    """
    return execute(mutation, {"input": input_doc})[f"create{model}"]


def main() -> None:
    wait_for_proxy()
    ts = now()
    feedback_fixture_count = int(os.getenv("PLEXUS_LOCAL_FEEDBACK_FIXTURE_COUNT", "200"))
    if feedback_fixture_count < 1:
        raise RuntimeError("PLEXUS_LOCAL_FEEDBACK_FIXTURE_COUNT must be >= 1")
    account_id = "local-demo-account"
    scorecard_id = "local-demo-scorecard"
    section_id = "local-demo-section"
    score_id = "local-demo-score"
    score_version_id = "local-demo-score-version"
    task_id = "local-demo-task"
    evaluation_id = "local-demo-evaluation"
    report_config_id = "local-demo-report-config"
    report_id = "local-demo-report"
    data_source_id = "local-demo-data-source"
    data_source_version_id = "local-demo-data-source-version"
    data_set_id = "local-demo-data-set"
    procedure_id = "local-demo-procedure"
    chat_session_id = "local-demo-chat-session"
    nira_scorecard_id = "nira-demo-scorecard"
    nira_section_id = "nira-demo-section"
    nira_score_id = "nira-demo-score"
    nira_score_version_id = "nira-demo-score-version"
    nira_lua_score_id = "nira-demo-lua-score"
    nira_lua_score_version_id = "nira-demo-lua-score-version"
    nira_item_id = "nira-demo-item-1"

    create("Account", {
        "id": account_id,
        "name": "Local Demo Account",
        "key": "local-demo",
        "description": "Seeded account for the local control-plane MVP.",
        "settings": {"hiddenMenuItems": []},
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("User", {
        "id": "demo-user",
        "email": "demo@plexus.local",
        "displayName": "Demo User",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("Scorecard", {
        "id": scorecard_id,
        "name": "Local Demo Scorecard",
        "key": "local-demo-scorecard",
        "description": "A scorecard served entirely by the local GraphQL facade.",
        "guidelines": "# Local Demo\n\nUse this scorecard to verify local control-plane reads and writes.",
        "accountId": account_id,
        "externalId": "local-demo-scorecard",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("ScorecardSection", {
        "id": section_id,
        "name": "Conversation Quality",
        "order": 1,
        "scorecardId": scorecard_id,
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("Score", {
        "id": score_id,
        "name": "Helpful Resolution",
        "key": "helpful-resolution",
        "description": "Determines whether the conversation reached a useful resolution.",
        "order": 1,
        "type": "LangGraphScore",
        "sectionId": section_id,
        "scorecardId": scorecard_id,
        "externalId": "local-demo-score",
        "championVersionId": score_version_id,
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("ScoreVersion", {
        "id": score_version_id,
        "scoreId": score_id,
        "configuration": "name: Helpful Resolution\nmodel: local-demo\n",
        "guidelines": "Answer Yes when the interaction resolves the customer's need.",
        "isFeatured": True,
        "note": "Seeded local champion version",
        "createdByUserId": "demo-user",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("Scorecard", {
        "id": nira_scorecard_id,
        "name": "Nira Call Center QA",
        "key": "nira-call-center-qa",
        "description": "Public-safe fixture scorecard for local prediction MVP testing.",
        "guidelines": "# Resolution Quality\n\nMark Yes when the agent provides a clear resolution or next step.",
        "accountId": account_id,
        "externalId": "nira-call-center-qa",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("ScorecardSection", {
        "id": nira_section_id,
        "name": "QA Checks",
        "order": 1,
        "scorecardId": nira_scorecard_id,
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("Score", {
        "id": nira_score_id,
        "name": "Resolution Quality",
        "key": "nira-resolution-quality",
        "description": "Checks if the call contains explicit resolution language.",
        "order": 1,
        "type": "TactusScore",
        "sectionId": nira_section_id,
        "scorecardId": nira_scorecard_id,
        "externalId": "nira-resolution-quality",
        "championVersionId": nira_score_version_id,
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("ScoreVersion", {
        "id": nira_score_version_id,
        "scoreId": nira_score_id,
        "configuration": (
            "name: Resolution Quality\n"
            "key: nira-resolution-quality\n"
            "class: TactusScore\n"
            "valid_classes:\n"
            "  - \"Yes\"\n"
            "  - \"No\"\n"
            "code: |\n"
            "  default_model \"openai/gpt-4o-mini\"\n"
            "\n"
            "  ClassifyProcedure {\n"
            "    classes = {\"Yes\", \"No\"},\n"
            "    system_message = [[\n"
            "    You are a QA analyst evaluating call center transcripts.\n"
            "    Score: Resolution Quality\n"
            "    Objective: Determine whether the agent provided a clear resolution to the customer's issue.\n"
            "    Decision criteria:\n"
            "    - Yes: The agent confirmed the issue was resolved and explained any next steps.\n"
            "    - No: The agent did not provide a clear resolution or left the issue unaddressed.\n"
            "    Return concise reasoning, then put exactly one final label on the last line: Yes or No.\n"
            "    ]],\n"
            "    user_message = [[\n"
            "    Evaluate the transcript below.\n"
            "\n"
            "    <transcript>\n"
            "    {{ text }}\n"
            "    </transcript>\n"
            "    ]]\n"
            "  }\n"
        ),
        "guidelines": "LLM-backed Tactus score for local prediction smoke testing.",
        "isFeatured": True,
        "note": "Seeded LLM champion version for local predict smoke.",
        "createdByUserId": "demo-user",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("Score", {
        "id": nira_lua_score_id,
        "name": "Resolution Quality (Lua)",
        "key": "nira-resolution-quality-lua",
        "description": "Programmatic keyword-based check for resolution language (no LLM).",
        "order": 2,
        "type": "TactusScore",
        "sectionId": nira_section_id,
        "scorecardId": nira_scorecard_id,
        "externalId": "nira-resolution-quality-lua",
        "championVersionId": nira_lua_score_version_id,
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("ScoreVersion", {
        "id": nira_lua_score_version_id,
        "scoreId": nira_lua_score_id,
        "configuration": (
            "name: Resolution Quality (Lua)\n"
            "key: nira-resolution-quality-lua\n"
            "class: TactusScore\n"
            "valid_classes:\n"
            "  - \"Yes\"\n"
            "  - \"No\"\n"
            "code: |\n"
            "  local transcript = string.lower(text or \"\")\n"
            "  local has_resolution = string.find(transcript, \"resolved\") ~= nil\n"
            "  local has_next_step = string.find(transcript, \"next step\") ~= nil or string.find(transcript, \"follow-up\") ~= nil\n"
            "\n"
            "  if has_resolution or has_next_step then\n"
            "    return {\n"
            "      value = \"Yes\",\n"
            "      explanation = \"Agent gave a clear resolution or next step.\"\n"
            "    }\n"
            "  end\n"
            "\n"
            "  return {\n"
            "    value = \"No\",\n"
            "    explanation = \"No clear resolution language was detected.\"\n"
            "  }\n"
        ),
        "guidelines": "Deterministic Lua-only fixture for local prediction smoke testing (no LLM cost).",
        "isFeatured": True,
        "note": "Seeded programmatic Lua champion version.",
        "createdByUserId": "demo-user",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("Item", {
        "id": nira_item_id,
        "accountId": account_id,
        "scoreId": nira_score_id,
        "externalId": "nira-demo-external-1",
        "description": "Nira MVP prediction fixture transcript",
        "text": (
            "Customer called about a billing issue. "
            "Agent confirmed the charge was reversed and explained the next step: "
            "a follow-up confirmation email within 24 hours."
        ),
        "metadata": {"channel": "voice", "fixture": "nira-predict"},
        "isEvaluation": False,
        "createdByType": "seed",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("Identifier", {
        "itemId": nira_item_id,
        "name": "External ID",
        "value": "nira-demo-external-1",
        "accountId": account_id,
        "position": 1,
        "createdAt": ts,
        "updatedAt": ts,
    })

    # Seed a deterministic feedback-evaluation fixture set for local MVP proofing.
    edited_anchor = datetime.now(timezone.utc) - timedelta(minutes=feedback_fixture_count)
    for index in range(1, feedback_fixture_count + 1):
        item_id = f"nira-demo-item-{index}"
        external_id = f"nira-demo-external-{index}"
        final_answer = "Yes" if index % 2 == 1 else "No"
        initial_answer = final_answer if index % 5 else ("No" if final_answer == "Yes" else "Yes")
        edited_at = (edited_anchor + timedelta(minutes=index)).isoformat().replace("+00:00", "Z")

        if index > 1:
            yes_text = (
                f"Call #{index}: customer asked for an account update. "
                "The agent confirmed the issue was resolved and provided the next step: "
                "a follow-up confirmation email."
            )
            no_text = (
                f"Call #{index}: customer asked for an account update. "
                "The agent gathered details but ended the call without a clear outcome or action."
            )
            create("Item", {
                "id": item_id,
                "accountId": account_id,
                "scoreId": nira_score_id,
                "externalId": external_id,
                "description": f"Nira feedback fixture transcript {index}",
                "text": yes_text if final_answer == "Yes" else no_text,
                "metadata": {"channel": "voice", "fixture": "nira-feedback", "ordinal": index},
                "isEvaluation": True,
                "createdByType": "seed",
                "createdAt": edited_at,
                "updatedAt": edited_at,
            })
            create("Identifier", {
                "itemId": item_id,
                "name": "External ID",
                "value": external_id,
                "accountId": account_id,
                "position": index,
                "createdAt": edited_at,
                "updatedAt": edited_at,
            })

        create("FeedbackItem", {
            "id": f"nira-demo-feedback-{index:03d}",
            "accountId": account_id,
            "scorecardId": nira_scorecard_id,
            "scoreId": nira_score_id,
            "itemId": item_id,
            "cacheKey": f"{nira_score_id}:{item_id}",
            "initialAnswerValue": initial_answer,
            "finalAnswerValue": final_answer,
            "initialCommentValue": "Initial reviewer classification.",
            "finalCommentValue": "Final reviewer classification.",
            "editCommentValue": f"Synthetic QA label for fixture {index}.",
            "editorName": "Demo Reviewer",
            "isAgreement": initial_answer == final_answer,
            "isInvalid": False,
            "editedAt": edited_at,
            "createdAt": edited_at,
            "updatedAt": edited_at,
        })

    item_ids = ["local-demo-item-1", "local-demo-item-2", "local-demo-item-3"]
    for index, item_id in enumerate(item_ids, start=1):
        create("Item", {
            "id": item_id,
            "accountId": account_id,
            "scoreId": score_id,
            "externalId": f"local-demo-external-{index}",
            "description": f"Seeded local transcript {index}",
            "text": f"Customer conversation transcript {index}: the agent verifies the issue and provides a clear next step.",
            "metadata": {"channel": "local-demo", "ordinal": index},
            "isEvaluation": index <= 2,
            "createdByType": "seed",
            "evaluationId": evaluation_id if index <= 2 else None,
            "createdAt": ts,
            "updatedAt": ts,
        })
        create("Identifier", {
            "itemId": item_id,
            "name": "External ID",
            "value": f"local-demo-external-{index}",
            "accountId": account_id,
            "position": index,
            "createdAt": ts,
            "updatedAt": ts,
        })
        create("ScoreResult", {
            "id": f"local-demo-score-result-{index}",
            "accountId": account_id,
            "itemId": item_id,
            "scorecardId": scorecard_id,
            "scoreId": score_id,
            "scoreVersionId": score_version_id,
            "evaluationId": evaluation_id if index <= 2 else None,
            "value": "Yes" if index != 2 else "No",
            "confidence": 0.91 if index != 2 else 0.66,
            "metadata": {"source": "local-demo"},
            "explanation": "Seeded local explanation for the MVP control plane.",
            "type": "prediction",
            "status": "COMPLETED",
            "createdAt": ts,
            "updatedAt": ts,
        })

    create("FeedbackItem", {
        "id": "local-demo-feedback-1",
        "accountId": account_id,
        "scorecardId": scorecard_id,
        "scoreId": score_id,
        "itemId": item_ids[1],
        "cacheKey": "local-demo-feedback-cache",
        "initialAnswerValue": "No",
        "finalAnswerValue": "Yes",
        "editCommentValue": "The local reviewer marked this as resolved.",
        "editedAt": ts,
        "createdAt": ts,
        "updatedAt": ts,
    })

    create("Task", {
        "id": task_id,
        "accountId": account_id,
        "type": "evaluation",
        "status": "COMPLETED",
        "target": "Local Demo Evaluation",
        "command": "plexus evaluate local-demo",
        "description": "Seeded task showing local control-plane task data.",
        "dispatchStatus": "DISPATCHED",
        "metadata": {"source": "local-demo"},
        "output": "Local demo task completed successfully.",
        "scorecardId": scorecard_id,
        "scoreId": score_id,
        "currentStageId": "local-demo-task-stage-2",
        "createdAt": ts,
        "startedAt": ts,
        "completedAt": ts,
        "updatedAt": ts,
    })
    for order, status in [(1, "COMPLETED"), (2, "COMPLETED")]:
        create("TaskStage", {
            "id": f"local-demo-task-stage-{order}",
            "taskId": task_id,
            "name": "Prepare" if order == 1 else "Evaluate",
            "order": order,
            "status": status,
            "statusMessage": "Seeded local stage",
            "processedItems": 2,
            "totalItems": 2,
            "startedAt": ts,
            "completedAt": ts,
            "createdAt": ts,
            "updatedAt": ts,
        })

    create("Evaluation", {
        "id": evaluation_id,
        "accountId": account_id,
        "type": "accuracy",
        "status": "COMPLETED",
        "accuracy": 0.83,
        "metrics": {"accuracy": 0.83, "precision": 0.8, "recall": 0.86},
        "metricsExplanation": "Seeded local metrics for dashboard rendering.",
        "cost": 0.42,
        "inferences": 3,
        "totalItems": 3,
        "processedItems": 3,
        "scorecardId": scorecard_id,
        "scoreId": score_id,
        "scoreVersionId": score_version_id,
        "taskId": task_id,
        "createdByUserId": "demo-user",
        "createdAt": ts,
        "startedAt": ts,
        "updatedAt": ts,
    })

    create("ReportConfiguration", {
        "id": report_config_id,
        "accountId": account_id,
        "name": "Local Demo Report Configuration",
        "description": "Seeded local report configuration.",
        "configuration": "blocks:\n  - type: ScoreResultsReport\n",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("Report", {
        "id": report_id,
        "accountId": account_id,
        "reportConfigurationId": report_config_id,
        "taskId": task_id,
        "createdByUserId": "demo-user",
        "name": "Local Demo Report",
        "parameters": {"scorecardId": scorecard_id},
        "metadata": {"source": "local-demo"},
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("ReportBlock", {
        "id": "local-demo-report-block-1",
        "reportId": report_id,
        "name": "Score Results",
        "type": "ScoreResultsReport",
        "position": 1,
        "output": "Local demo report block output.",
        "log": "Generated by seed_local_demo.py",
        "dataSetId": data_set_id,
        "createdAt": ts,
        "updatedAt": ts,
    })

    create("DataSource", {
        "id": data_source_id,
        "accountId": account_id,
        "scorecardId": scorecard_id,
        "scoreId": score_id,
        "name": "Local Demo Data Source",
        "key": "local-demo-data-source",
        "description": "Seeded data source for the local MVP.",
        "currentVersionId": data_source_version_id,
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("DataSourceVersion", {
        "id": data_source_version_id,
        "dataSourceId": data_source_id,
        "yamlConfiguration": "class: LocalDemoDataSource\n",
        "isFeatured": True,
        "note": "Seeded local data source version",
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("DataSet", {
        "id": data_set_id,
        "accountId": account_id,
        "scorecardId": scorecard_id,
        "scoreId": score_id,
        "scoreVersionId": score_version_id,
        "dataSourceVersionId": data_source_version_id,
        "name": "Local Demo Dataset",
        "description": "Seeded dataset for report and evaluation pages.",
        "provenance": {"source": "local-demo"},
        "createdAt": ts,
        "updatedAt": ts,
    })

    create("Procedure", {
        "id": procedure_id,
        "accountId": account_id,
        "name": "Local Demo Procedure",
        "description": "A seeded procedure that can be rendered without AWS.",
        "category": "demo",
        "status": "COMPLETED",
        "scorecardId": scorecard_id,
        "scoreId": score_id,
        "scoreVersionId": score_version_id,
        "createdByUserId": "demo-user",
        "metadata": {"source": "local-demo"},
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("ChatSession", {
        "id": chat_session_id,
        "accountId": account_id,
        "name": "Local Demo Chat",
        "status": "COMPLETED",
        "procedureId": procedure_id,
        "scorecardId": scorecard_id,
        "scoreId": score_id,
        "metadata": {"source": "local-demo"},
        "createdAt": ts,
        "updatedAt": ts,
    })
    create("ChatMessage", {
        "id": "local-demo-chat-message-1",
        "accountId": account_id,
        "sessionId": chat_session_id,
        "procedureId": procedure_id,
        "role": "ASSISTANT",
        "humanInteraction": "CHAT_ASSISTANT",
        "messageType": "MESSAGE",
        "content": "Local control-plane demo data is online.",
        "sequenceNumber": 1,
        "createdByUserId": "demo-user",
        "createdAt": ts,
    })

    print(f"Seeded local Plexus demo data through {API_URL}")


if __name__ == "__main__":
    main()
