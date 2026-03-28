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


@pytest.mark.asyncio
async def test_trace_sink_drops_placeholder_assistant_completion_message():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"

    sink = PlexusTraceSink(recorder)
    await sink.start_session()

    message_id = await sink.record(
        {
            "event_type": "agent_complete",
            "role": "assistant",
            "content": "Assistant turn completed.",
        }
    )

    assert message_id is None
    recorder.record_message.assert_not_awaited()
    assert sink.assistant_message_texts == []


@pytest.mark.asyncio
async def test_trace_sink_stream_chunk_upserts_single_assistant_message():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-stream-1"
    recorder.update_message.return_value = True

    sink = PlexusTraceSink(recorder)
    await sink.start_session()

    first_message_id = await sink.record(
        {
            "event_type": "agent_stream_chunk",
            "agent_name": "assistant",
            "chunk_text": "Hel",
            "accumulated_text": "Hel",
        }
    )
    second_message_id = await sink.record(
        {
            "event_type": "agent_stream_chunk",
            "agent_name": "assistant",
            "chunk_text": "lo",
            "accumulated_text": "Hello",
        }
    )

    assert first_message_id == "msg-stream-1"
    assert second_message_id == "msg-stream-1"
    recorder.record_message.assert_awaited_once()
    recorder.update_message.assert_not_awaited()
    assert sink._active_stream_message_ids["assistant"] == "msg-stream-1"
    assert sink._active_stream_texts["assistant"] == "Hello"

    await sink.record(
        {
            "event_type": "agent_turn",
            "agent_name": "assistant",
            "stage": "completed",
        }
    )

    recorder.update_message.assert_awaited_once()
    assert recorder.update_message.await_args.kwargs["content"] == "Hello"


@pytest.mark.asyncio
async def test_trace_sink_stream_completion_finalizes_message_and_tracks_text():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-stream-1"
    recorder.update_message.return_value = True

    sink = PlexusTraceSink(recorder)
    await sink.start_session()
    await sink.record(
        {
            "event_type": "agent_stream_chunk",
            "agent_name": "assistant",
            "chunk_text": "Hello",
            "accumulated_text": "Hello",
        }
    )

    completed_id = await sink.record(
        {
            "event_type": "agent_turn",
            "agent_name": "assistant",
            "stage": "completed",
        }
    )

    assert completed_id == "msg-stream-1"
    assert sink.assistant_message_texts == ["Hello"]
    assert sink._active_stream_message_ids == {}
    assert sink._active_stream_texts == {}
    assert recorder.update_message.await_count == 1
