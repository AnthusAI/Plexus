from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from plexus.cli.procedure.tactus_adapters.trace import PlexusTraceSink


@pytest.mark.asyncio
async def test_trace_sink_records_tool_call_with_structured_payloads():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-1"

    sink = PlexusTraceSink(recorder)
    await sink.start_session({"scorecard_id": "sc-1"})

    event = SimpleNamespace(
        sequence=1,
        kind="TOOL_CALL",
        role="assistant",
        content="Calling tool: plexus_scorecard_create",
        tool_name="plexus_scorecard_create",
        tool_parameters={"name": "Test"},
        human_interaction="INTERNAL",
    )
    message_id = await sink.record(event)

    assert message_id == "msg-1"
    recorder.record_message.assert_awaited_once_with(
        role="ASSISTANT",
        content="Calling tool: plexus_scorecard_create",
        message_type="TOOL_CALL",
        tool_name="plexus_scorecard_create",
        tool_parameters={"name": "Test"},
        tool_response=None,
        human_interaction="INTERNAL",
        metadata=None,
    )


@pytest.mark.asyncio
async def test_trace_sink_records_modern_tool_call_event_shape():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-2"

    sink = PlexusTraceSink(recorder)
    await sink.start_session()

    event = {
        "event_type": "tool_call",
        "agent_name": "creator",
        "tool_name": "plexus_scorecard_create",
        "tool_args": {"name": "Test"},
    }

    message_id = await sink.record(event)

    assert message_id == "msg-2"
    recorder.record_message.assert_awaited_once_with(
        role="ASSISTANT",
        content="Tool call: plexus_scorecard_create",
        message_type="TOOL_CALL",
        tool_name="plexus_scorecard_create",
        tool_parameters={"name": "Test"},
        tool_response=None,
        human_interaction="INTERNAL",
        metadata=None,
    )


@pytest.mark.asyncio
async def test_trace_sink_ends_session_with_status():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"

    sink = PlexusTraceSink(recorder)
    await sink.start_session()
    await sink.end_session(status="FAILED")

    recorder.end_session.assert_awaited_once_with(status="FAILED")
