from pathlib import Path
from types import SimpleNamespace

import pytest

from plexus.cli.procedure.mcp_transport import create_procedure_mcp_server
from plexus.cli.procedure.procedure_executor import _execute_tactus


class _FakeRuntime:
    last_context = None

    def __init__(self, **_kwargs):
        self.toolset_registry = {}
        self.tool_primitive = None
        self.log_handler = None

    async def execute(self, _source, _context, format="yaml"):
        assert format == "yaml"
        _FakeRuntime.last_context = _context
        return {"success": True, "status": "planned"}


@pytest.mark.asyncio
async def test_execute_tactus_initializes_embedded_mcp_transport(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    # Patch runtime and adapters to keep this test focused on MCP bridge setup.
    monkeypatch.setattr("tactus.core.TactusRuntime", _FakeRuntime)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )

    mcp_server = await create_procedure_mcp_server(experiment_context={"procedure_id": "p-1"})
    assert mcp_server.transport.connected is False

    result = await _execute_tactus(
        procedure_id="p-1",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  return run(input)\n"
        ),
        client=SimpleNamespace(),
        mcp_server=mcp_server,
        context={},
    )

    assert result["success"] is True
    assert mcp_server.transport.connected is True


@pytest.mark.asyncio
async def test_execute_tactus_hydrates_context_from_params_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    monkeypatch.setattr("tactus.core.TactusRuntime", _FakeRuntime)
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusStorageAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusHITLAdapter",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.tactus_adapters.PlexusTraceSink",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "plexus.cli.procedure.chat_recorder.ProcedureChatRecorder",
        lambda *_a, **_k: SimpleNamespace(),
    )

    result = await _execute_tactus(
        procedure_id="p-ctx",
        procedure_source=(
            "name: Test\n"
            "class: Tactus\n"
            "params:\n"
            "  brief:\n"
            "    type: string\n"
            "    value: hello\n"
            "  dry_run:\n"
            "    type: boolean\n"
            "    default: true\n"
            "code: |\n"
            "  local function run(input)\n"
            "    return { success = true }\n"
            "  end\n"
            "  Procedure {\n"
            "    input = { brief = field.string{required=true} },\n"
            "    output = { success = field.boolean{required=true} },\n"
            "    function(input) return run(input) end\n"
            "  }\n"
        ),
        client=SimpleNamespace(),
        mcp_server=None,
        context=None,
    )

    assert result["success"] is True
    assert _FakeRuntime.last_context == {"brief": "hello", "dry_run": True}


def test_scorecard_create_dry_run_skips_approval():
    yaml_path = Path("plexus/procedures/scorecard_create.yaml")
    content = yaml_path.read_text()

    dry_run_index = content.find("if dry_run then")
    approve_index = content.find("local approved = Human.approve")

    assert dry_run_index != -1, "dry-run branch must exist"
    assert approve_index != -1, "approval branch must exist for non-dry-run execution"
    assert dry_run_index < approve_index, "dry-run should return before approval"
