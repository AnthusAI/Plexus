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
    assert parsed["agents"]["assistant"]["reasoning_effort"] == "low"
    assert parsed["agents"]["assistant"]["verbosity"] == "low"
    assert parsed["agents"]["assistant"]["max_tokens"] == 220
    assert parsed["agents"]["assistant"]["stream"] is True
    assert parsed["agents"]["assistant"]["tools"] == ["plexus"]
    assert isinstance(parsed.get("code"), str)
    assert "State.set(\"stage\", \"preparing\")" in parsed["code"]
    assert "Previous user message before latest (if any):" in parsed["code"]
    assert "Use prior turns for continuity and respond concisely with concrete help." in parsed["code"]


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
