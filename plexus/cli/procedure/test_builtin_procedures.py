from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml

from plexus.cli.procedure.builtin_procedures import (
    CONSOLE_CHAT_BUILTIN_ID,
    get_builtin_procedure_yaml,
    is_builtin_procedure_id,
)
from plexus.cli.procedure.service import ProcedureService
from plexus.cli.procedure.tactus_adapters.storage import PlexusStorageAdapter


def test_builtin_console_procedure_yaml_contains_tactus_source():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    assert yaml_text

    parsed = yaml.safe_load(yaml_text)
    assert parsed["class"] == "Tactus"
    assert "console_session_history" in parsed.get("input", {})
    assert parsed["agents"]["assistant"]["model"] == "gpt-5.4-mini"
    assert parsed["agents"]["assistant"]["reasoning_effort"] == "medium"
    assert parsed["agents"]["assistant"]["verbosity"] == "low"
    assert parsed["agents"]["assistant"]["max_tokens"] == 1024
    assert parsed["agents"]["assistant"]["stream"] is True
    assert parsed["agents"]["assistant"]["tools"] == ["execute_tactus"]
    assert isinstance(parsed.get("code"), str)
    assert "State.set(\"stage\", \"preparing\")" in parsed["code"]
    assert "Previous user message before latest (if any):" in parsed["code"]
    assert "Use prior turns for continuity and respond concisely with concrete help." in parsed["code"]


def test_builtin_console_procedure_prompt_teaches_docs_primitives():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    # The Console assistant must know how to discover and load topics
    # from the agent documentation knowledge base.
    assert "plexus.docs.list" in system_prompt, (
        "Console assistant prompt should teach plexus.docs.list for "
        "topic discovery"
    )
    assert "plexus.docs.get" in system_prompt, (
        "Console assistant prompt should teach plexus.docs.get for "
        "loading individual topic bodies"
    )
    # Anchor on the canonical entry-point topic and at least one
    # namespace so future prompt edits cannot silently drop them.
    assert "mcp.execute-tactus-overview" in system_prompt
    assert "score-authoring" in system_prompt
    assert "plexus.scorecards.search" in system_prompt
    assert "plexus.score.search" in system_prompt


def test_builtin_console_procedure_prompt_is_cs_domain_focused():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "AUDIENCE AND LANGUAGE" in system_prompt
    assert "non-technical customer success representatives" in system_prompt
    assert "scorecards, scores, guidelines, prompts, evaluations, reports" in system_prompt
    assert "avoid exposing raw tool syntax" in system_prompt


def test_builtin_console_procedure_prompt_contains_nontechnical_intent_routing():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "INTENT ROUTING FOR NON-TECHNICAL REQUESTS" in system_prompt
    assert "clarify wording" in system_prompt
    assert "stricter/looser" in system_prompt
    assert "Do not reroute score behavior requests into guidelines edits" in system_prompt
    assert "how a score is performing" in system_prompt
    assert "grade one item/call" in system_prompt


def test_builtin_console_procedure_prompt_teaches_skill_discovery():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "OPERATIONAL SKILLS" in system_prompt
    assert "plexus.skills.list" in system_prompt
    assert "plexus.skills.get" in system_prompt
    assert "metadata only" in system_prompt
    assert "fetch exactly one relevant skill body" in system_prompt
    assert "Cite the skill id" in system_prompt
    assert "Do not preload or fetch every skill body" in system_prompt
    assert "Docs are reference material" in system_prompt
    assert "Do not merge the two namespaces" in system_prompt
    assert "score-code-editor" in system_prompt
    assert 'mode = "console"' in system_prompt


def test_builtin_console_procedure_prompt_teaches_guidelines_validation_runtime_helper():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "GUIDELINES WORKFLOWS" in system_prompt
    assert "plexus.guidelines.validate" in system_prompt
    assert "deterministically validates guidelines" in system_prompt
    assert "Invalid guidelines are rejected and not saved" in system_prompt
    assert "omit code and yaml_content" in system_prompt
    assert "no score version was saved" in system_prompt


def test_builtin_console_procedure_prompt_teaches_report_dispatch_contract():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "REPORT REQUESTS (HARD RULES)" in system_prompt
    assert "plexus.report.run" in system_prompt
    assert "reports.reports-catalog" in system_prompt
    assert 'plexus.docs.list({ namespace = "reports" })' in system_prompt
    assert "load the specific `reports.*` topic before constructing the report call" in system_prompt
    assert "report_configs{}" in system_prompt
    assert "FeedbackAlignment" in system_prompt
    assert "memory_analysis = false" in system_prompt
    assert "pass a resolved scorecard UUID" in system_prompt
    assert "use the returned `scorecard.id`" in system_prompt
    assert "task_id = h[\"dispatch_result\"]" in system_prompt
    assert "Do not use `plexus.feedback.alignment` to run a report" in system_prompt
    assert "Do not use `plexus.procedure.optimize` to run a report" in system_prompt


def test_builtin_console_procedure_prompt_teaches_prediction_contract():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "PREDICTION REQUESTS (HARD RULES)" in system_prompt
    assert "use `plexus.score.predict`" in system_prompt
    assert "Do not use report or evaluation APIs for a single-item prediction" in system_prompt
    assert "scorecard_identifier = \"My Scorecard\"" in system_prompt
    assert "score_identifier = \"My Score\"" in system_prompt
    assert "do not ask for another confirmation" in system_prompt


def test_builtin_console_procedure_prompt_enforces_score_edit_completion_contract():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "IMPORTANT for score.edit" in system_prompt
    assert "behavior-change requests" in system_prompt
    assert "not `plexus.score.update` guidelines" in system_prompt
    assert "Existing guideline validation issues do not block score.edit code workflows" in system_prompt
    assert "instruction = [[tighten the refund exception rule]]" in system_prompt
    assert "prefer Lua long-bracket strings (`[[...]]`)" in system_prompt
    assert "pass `target.scorecard_id` and `target.score_id` to score.edit" in system_prompt
    assert "Do not use `plexus.scorecards.search` as the target id source" in system_prompt
    assert "do not auto-select one" in system_prompt
    assert "score.edit is edit execution only" in system_prompt
    assert "waits internally for terminal completion" in system_prompt
    assert "status is `completed` with result `version_id`" in system_prompt
    assert "version_id" in system_prompt
    assert "without asking for another confirmation" in system_prompt
    assert "latest updated score version created in this chat" in system_prompt
    assert "Do not restart from champion" in system_prompt
    assert "worker status, updated score version_id, parent version, changed fields" in system_prompt


def test_builtin_console_procedure_prompt_blocks_direct_score_code_update():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "Do not call plexus.score.update with code, yaml_content, or full YAML" in system_prompt
    assert "use score.edit instead" in system_prompt
    assert "code = \"<full yaml>\"" not in system_prompt
    assert "yaml_content" in system_prompt
    assert "guidelines = \"<new guidelines markdown>\"" in system_prompt


def test_builtin_console_procedure_prompt_teaches_runtime_post_submit_smoke_test():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "post-submit smoke test (`plexus.score.test`)" in system_prompt
    assert "Report that automatic smoke-test outcome" in system_prompt


def test_builtin_console_procedure_guards_against_uuid_only_replies():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    code = parsed["code"]

    assert 'for _, key in ipairs({ "response", "content", "message", "text", "output" }) do' in code
    assert "result\" }) do" not in code
    assert "looks_like_uuid" in code
    assert "assistant returned only a version identifier" in code


def test_builtin_console_procedure_disambiguates_deictic_score_references():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    code = parsed["code"]

    assert "I need the exact target first" in code
    assert "more than one possible score target" in code
    assert "this score" in code
    assert "same score" in code


def test_builtin_console_procedure_consumes_score_disambiguation_followups():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    code = parsed["code"]
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "find_pending_score_disambiguation" in code
    assert "resolve_pending_score_choice" in code
    assert "Continue the pending user request" in code
    assert "Use score_identifier exactly" in code
    assert "without confidence" in code
    assert "plexus.score.resolve" in system_prompt
    assert "score_resolve" in system_prompt


def test_builtin_console_procedure_prompt_teaches_planning_mode_contract():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    system_prompt = parsed["agents"]["assistant"]["system_prompt"]

    assert "TOOL ACCESS MODE" in system_prompt
    assert "console_tool_access_mode" in parsed["input"]
    assert "tool_not_allowed_in_planning_mode" in system_prompt
    assert "full tool surface" in system_prompt
    assert "plexus.skills.list" in system_prompt
    assert "plexus.skills.get" in system_prompt
    assert "inspect existing procedure runs" in system_prompt
    assert "plexus.procedure.chat_messages" in system_prompt
    assert "Planning mode may run predictions, evaluations, reports" in system_prompt
    assert "Planning mode may use `plexus.guidelines.validate`" in system_prompt
    assert "promoting champions with `plexus.score.set_champion`" in system_prompt
    assert "`plexus.score.update` or `plexus.score.edit`" in system_prompt
    assert "plexus.procedure.run" in system_prompt
    assert "plexus.score.contradictions" in system_prompt
    assert "plexus.report.acceptance_rate" in system_prompt
    assert "plexus.report.score_champion_version_timeline" in system_prompt
    assert "Private mode is soft UI privacy" in system_prompt
    assert "hidden from other users in the workspace UI" in system_prompt


def test_builtin_console_procedure_version_is_current():
    yaml_text = get_builtin_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)
    parsed = yaml.safe_load(yaml_text)
    # Bumped when the Console assistant tool contract changes.
    assert parsed["version"] == "1.6.17"


def test_is_builtin_procedure_id():
    assert is_builtin_procedure_id(CONSOLE_CHAT_BUILTIN_ID) is True
    assert is_builtin_procedure_id("builtin:unknown/path") is False
    assert is_builtin_procedure_id("proc-123") is False


@patch("plexus.cli.procedure.service.Procedure.get_by_id")
def test_service_get_procedure_yaml_uses_builtin_without_db_lookup(mock_get_by_id):
    service = ProcedureService(Mock())

    yaml_text = service.get_procedure_yaml(CONSOLE_CHAT_BUILTIN_ID)

    assert yaml_text
    assert "class: Tactus" in yaml_text
    mock_get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_run_procedure_builtin_routes_to_tactus_executor():
    client = Mock()
    service = ProcedureService(client)
    expected_result = {
        "success": True,
        "status": "COMPLETED",
        "procedure_id": CONSOLE_CHAT_BUILTIN_ID,
    }

    with patch(
        "plexus.cli.procedure.mcp_transport.create_procedure_mcp_server",
        new=AsyncMock(return_value=Mock()),
    ) as create_mcp_mock, patch(
        "plexus.cli.procedure.procedure_executor.execute_procedure",
        new=AsyncMock(return_value=expected_result),
    ) as execute_mock:
        result = await service.run_procedure(CONSOLE_CHAT_BUILTIN_ID, account_id="acct-1")

    assert result == expected_result
    create_mcp_mock.assert_awaited_once()
    execute_mock.assert_awaited_once()
    execute_kwargs = execute_mock.await_args.kwargs
    assert execute_kwargs["procedure_id"] == CONSOLE_CHAT_BUILTIN_ID
    assert execute_kwargs["context"]["account_id"] == "acct-1"


@pytest.mark.asyncio
async def test_run_procedure_builtin_passes_console_context_overrides():
    client = Mock()
    service = ProcedureService(client)
    expected_result = {
        "success": True,
        "status": "COMPLETED",
        "procedure_id": CONSOLE_CHAT_BUILTIN_ID,
    }

    with patch(
        "plexus.cli.procedure.mcp_transport.create_procedure_mcp_server",
        new=AsyncMock(return_value=Mock()),
    ), patch(
        "plexus.cli.procedure.procedure_executor.execute_procedure",
        new=AsyncMock(return_value=expected_result),
    ) as execute_mock:
        result = await service.run_procedure(
            CONSOLE_CHAT_BUILTIN_ID,
            account_id="acct-1",
            console_user_message="Multiply that by three.",
            console_session_history=[
                {"role": "USER", "content": "Pick a random number."},
                {"role": "ASSISTANT", "content": "How about 7?"},
                {"role": "USER", "content": "Multiply that by three."},
            ],
        )

    assert result == expected_result
    execute_kwargs = execute_mock.await_args.kwargs
    assert execute_kwargs["context"]["console_user_message"] == "Multiply that by three."
    assert execute_kwargs["context"]["console_session_history"] == [
        {"role": "USER", "content": "Pick a random number."},
        {"role": "ASSISTANT", "content": "How about 7?"},
        {"role": "USER", "content": "Multiply that by three."},
    ]


@pytest.mark.asyncio
async def test_run_procedure_builtin_skips_mcp_server_when_disabled():
    client = Mock()
    service = ProcedureService(client)
    expected_result = {
        "success": True,
        "status": "COMPLETED",
        "procedure_id": CONSOLE_CHAT_BUILTIN_ID,
    }

    with patch(
        "plexus.cli.procedure.mcp_transport.create_procedure_mcp_server",
        new=AsyncMock(return_value=Mock()),
    ) as create_mcp_mock, patch(
        "plexus.cli.procedure.procedure_executor.execute_procedure",
        new=AsyncMock(return_value=expected_result),
    ) as execute_mock:
        result = await service.run_procedure(
            CONSOLE_CHAT_BUILTIN_ID,
            account_id="acct-1",
            enable_mcp=False,
        )

    assert result == expected_result
    create_mcp_mock.assert_not_called()
    execute_kwargs = execute_mock.await_args.kwargs
    assert execute_kwargs["mcp_server"] is None


def test_builtin_storage_adapter_uses_in_memory_metadata():
    client = Mock()
    storage = PlexusStorageAdapter(client, CONSOLE_CHAT_BUILTIN_ID)

    metadata = storage.load_procedure_metadata(CONSOLE_CHAT_BUILTIN_ID)
    metadata.state["k"] = "v"
    storage.save_procedure_metadata(CONSOLE_CHAT_BUILTIN_ID, metadata)
    storage.update_procedure_status(CONSOLE_CHAT_BUILTIN_ID, "WAITING_FOR_HUMAN", "msg-1")

    loaded = storage.load_procedure_metadata(CONSOLE_CHAT_BUILTIN_ID)
    assert loaded.state["k"] == "v"
    assert loaded.status == "WAITING_FOR_HUMAN"
    assert loaded.waiting_on_message_id == "msg-1"
    client.execute.assert_not_called()
