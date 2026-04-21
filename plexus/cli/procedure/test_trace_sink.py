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
            "chunk_text": " this is a longer chunk update that should exceed the persistence threshold.",
            "accumulated_text": "Hel this is a longer chunk update that should exceed the persistence threshold.",
        }
    )

    assert first_message_id == "msg-stream-1"
    assert second_message_id == "msg-stream-1"
    recorder.record_message.assert_awaited_once()
    recorder.update_message.assert_awaited_once()
    assert sink._active_stream_message_ids["assistant"] == "msg-stream-1"
    assert sink._active_stream_texts["assistant"] == "Hel this is a longer chunk update that should exceed the persistence threshold."


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


@pytest.mark.asyncio
async def test_trace_sink_drops_duplicate_post_stream_assistant_message():
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
    await sink.record(
        {
            "event_type": "agent_turn",
            "agent_name": "assistant",
            "stage": "completed",
        }
    )

    message_id = await sink.record(
        {
            "event_type": "agent_message",
            "agent_name": "assistant",
            "role": "assistant",
            "content": "Hello",
        }
    )

    assert message_id is None
    recorder.record_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_trace_sink_stream_metadata_contains_latency_markers():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-stream-1"
    recorder.update_message.return_value = True
    recorder.get_latest_console_chat_metadata = lambda: {
        "queued_at": "2026-03-28T01:00:00+00:00",
        "instrumentation": {
            "client_send_started_at": "2026-03-28T00:59:58+00:00",
        },
    }

    sink = PlexusTraceSink(recorder)
    sink.mark_runtime_execute_started("2026-03-28T01:00:01+00:00")
    await sink.start_session()

    await sink.record(
        {
            "event_type": "agent_stream_chunk",
            "agent_name": "assistant",
            "chunk_text": "Hello there.",
            "accumulated_text": "Hello there.",
            "timestamp": "2026-03-28T01:00:02+00:00",
        }
    )
    await sink.record(
        {
            "event_type": "agent_turn",
            "agent_name": "assistant",
            "stage": "completed",
            "timestamp": "2026-03-28T01:00:03+00:00",
        }
    )

    final_update_call = recorder.update_message.await_args_list[-1]
    metadata = final_update_call.kwargs.get("metadata", {})
    streaming = metadata.get("streaming", {}) if isinstance(metadata, dict) else {}
    timings = streaming.get("timings", {}) if isinstance(streaming, dict) else {}

    assert timings.get("dispatch_queued_at") == "2026-03-28T01:00:00+00:00"
    assert timings.get("backend_runtime_execute_started_at") == "2026-03-28T01:00:01+00:00"
    assert timings.get("first_chunk_received_at") == "2026-03-28T01:00:02+00:00"
    assert timings.get("chunk_count") == 1


@pytest.mark.asyncio
async def test_trace_sink_cost_events_attach_to_streamed_assistant_message():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-stream-1"
    recorder.update_message.return_value = True

    sink = PlexusTraceSink(recorder)
    await sink.start_session()
    await sink.record({"event_type": "agent_turn", "agent_name": "assistant", "stage": "started"})
    await sink.record(
        {
            "event_type": "cost",
            "agent_name": "assistant",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "total_cost": 0.0025,
        }
    )
    await sink.record(
        {
            "event_type": "agent_stream_chunk",
            "agent_name": "assistant",
            "chunk_text": "Hi",
            "accumulated_text": "Hi",
        }
    )
    await sink.record({"event_type": "agent_turn", "agent_name": "assistant", "stage": "completed"})

    final_update_call = recorder.update_message.await_args_list[-1]
    metadata = final_update_call.kwargs.get("metadata")
    assert isinstance(metadata, dict)
    cost = metadata.get("cost")
    assert isinstance(cost, dict)
    assert cost.get("kind") == "assistant_inference"
    assert cost.get("live") is False
    summary = cost.get("summary")
    assert isinstance(summary, dict)
    assert summary.get("total_usd") == pytest.approx(0.0025)
    assert isinstance(summary.get("breakdown"), list)
    assert summary["breakdown"][0]["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_trace_sink_tool_call_message_includes_tool_cost_metadata():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-tool-1"

    sink = PlexusTraceSink(recorder)
    await sink.start_session()

    event = {
        "event_type": "tool_call",
        "agent_name": "assistant",
        "tool_name": "plexus_evaluation_run",
        "tool_args": {"evaluation_type": "accuracy"},
        "tool_result": {
            "_from_cache": True,
            "cost": 0.42,
            "cost_details": {
                "schema_version": 1,
                "total_usd": 0.42,
                "llm_calls": 1,
                "prompt_tokens": 200,
                "completion_tokens": 10,
                "total_tokens": 210,
                "cached_tokens": 0,
                "breakdown": [
                    {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "spent_usd": 0.42,
                        "reused_usd": 0.0,
                        "referenced_usd": 0.42,
                        "llm_calls": 1,
                        "evaluation_runs": 1,
                        "prompt_tokens": 200,
                        "completion_tokens": 10,
                        "total_tokens": 210,
                        "cached_tokens": 0,
                    }
                ],
            },
        },
    }
    await sink.record(event)

    call_kwargs = recorder.record_message.await_args.kwargs
    metadata = call_kwargs.get("metadata")
    assert isinstance(metadata, dict)
    cost = metadata.get("cost")
    assert isinstance(cost, dict)
    assert cost.get("kind") == "tool_execution"
    assert cost.get("billing_mode") == "reused"
    assert cost.get("live") is False


@pytest.mark.asyncio
async def test_trace_sink_does_not_attach_zero_cost_placeholder_to_assistant_message():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-assistant-1"
    recorder.update_message.return_value = True

    sink = PlexusTraceSink(recorder)
    await sink.start_session()

    await sink.record({"event_type": "agent_turn", "agent_name": "code_editor", "stage": "started"})
    await sink.record(
        {
            "role": "ASSISTANT",
            "content": "Compliance-bias clarification for ambiguous cost language",
            # Deliberately omit agent_name to exercise active-turn fallback.
        }
    )

    record_kwargs = recorder.record_message.await_args.kwargs
    metadata = record_kwargs.get("metadata")
    assert not isinstance(metadata, dict) or "cost" not in metadata


@pytest.mark.asyncio
async def test_trace_sink_late_cost_event_updates_recent_assistant_message():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-assistant-1"
    recorder.update_message.return_value = True

    sink = PlexusTraceSink(recorder)
    await sink.start_session()

    await sink.record({"event_type": "agent_turn", "agent_name": "code_editor", "stage": "started"})
    await sink.record(
        {
            "role": "ASSISTANT",
            "content": "Hypothesis text",
            # Deliberately omit agent_name to exercise active-turn fallback.
        }
    )
    await sink.record({"event_type": "agent_turn", "agent_name": "code_editor", "stage": "completed"})
    await sink.record(
        {
            "event_type": "cost",
            "agent_name": "code_editor",
            "provider": "openai",
            "model": "gpt-5.4",
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "total_tokens": 125,
            "total_cost": 0.0125,
        }
    )

    update_kwargs = recorder.update_message.await_args.kwargs
    assert update_kwargs.get("message_id") == "msg-assistant-1"
    metadata = update_kwargs.get("metadata")
    assert isinstance(metadata, dict)
    cost = metadata.get("cost")
    assert isinstance(cost, dict)
    assert cost.get("kind") == "assistant_inference"
    assert cost.get("live") is False
    summary = cost.get("summary")
    assert isinstance(summary, dict)
    assert summary.get("total_usd") == pytest.approx(0.0125)
    assert summary.get("llm_calls") == 1


@pytest.mark.asyncio
async def test_trace_sink_updates_started_tool_call_from_explicit_tool_response():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.return_value = "msg-tool-1"
    recorder.update_message.return_value = True

    sink = PlexusTraceSink(recorder)
    await sink.start_session()

    started_id = await sink.record(
        {
            "event_type": "tool_call_started",
            "tool_name": "plexus_evaluation_run",
            "tool_args": {"evaluation_type": "accuracy"},
        }
    )
    completed_id = await sink.record(
        {
            "kind": "TOOL_RESPONSE",
            "tool_name": "plexus_evaluation_run",
            "tool_result": {"status": "FAILED", "errorMessage": "Initial evaluation failed"},
        }
    )

    assert started_id == "msg-tool-1"
    assert completed_id == "msg-tool-1"
    recorder.update_message.assert_awaited_once()
    update_kwargs = recorder.update_message.await_args.kwargs
    assert update_kwargs["message_id"] == "msg-tool-1"
    assert update_kwargs["tool_response"] == {"status": "FAILED", "errorMessage": "Initial evaluation failed"}


@pytest.mark.asyncio
async def test_trace_sink_records_assistant_alert_for_failed_tool_result():
    recorder = AsyncMock()
    recorder.start_session.return_value = "sess-1"
    recorder.record_message.side_effect = ["msg-tool-1", "msg-alert-1"]
    recorder.update_message.return_value = True

    sink = PlexusTraceSink(recorder)
    await sink.start_session()

    await sink.record(
        {
            "event_type": "tool_call_started",
            "tool_name": "plexus_evaluation_run",
            "tool_args": {"evaluation_type": "accuracy"},
        }
    )
    await sink.record(
        {
            "event_type": "tool_call",
            "tool_name": "plexus_evaluation_run",
            "tool_args": {"evaluation_type": "accuracy"},
            "tool_result": {
                "status": "FAILED",
                "errorMessage": "Initial evaluation failed: score returned ERROR",
            },
        }
    )

    alert_call = recorder.record_message.await_args_list[-1]
    assert alert_call.kwargs["role"] == "ASSISTANT"
    assert alert_call.kwargs["human_interaction"] == "ALERT_ERROR"
    assert "plexus_evaluation_run failed" in alert_call.kwargs["content"]
