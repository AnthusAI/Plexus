from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from plexus.cli.procedure.builtin_procedures import CONSOLE_CHAT_BUILTIN_ID
from plexus.cli.procedure.service import ProcedureService


@pytest.mark.asyncio
async def test_tactus_execution_options_are_passed_to_procedure_parameters():
    client = Mock()
    service = ProcedureService(client)
    service.get_procedure_info = Mock(return_value=SimpleNamespace(
        scorecard_name="Demo", score_name="Score",
        procedure=SimpleNamespace(scorecardId="scorecard-1", scoreId="score-1"),
    ))
    service.get_procedure_yaml = Mock(return_value="name: Feedback Alignment Optimizer\nclass: Tactus\n")
    captured = {}

    async def capture_execute(**kwargs):
        captured.update(kwargs)
        return {"success": True, "status": "COMPLETED"}

    with patch(
        "plexus.cli.procedure.service.ProcedureService._build_optimizer_recent_rubric_memory_briefing",
        new=AsyncMock(return_value=None),
    ), patch(
        "plexus.cli.procedure.service.ProcedureService._build_optimizer_rubric_memory_briefing",
        new=AsyncMock(return_value=None),
    ), patch(
        "plexus.cli.procedure.mcp_transport.create_procedure_mcp_server",
        new=AsyncMock(return_value=Mock()),
    ), patch(
        "plexus.cli.procedure.procedure_executor.execute_procedure",
        new=AsyncMock(side_effect=capture_execute),
    ):
        await service.run_procedure(
            "procedure-1", account_id="acct-1", dry_run=True, max_iterations=1
        )

    assert captured["context"]["dry_run"] is True
    assert captured["context"]["max_iterations"] == 1


@pytest.mark.asyncio
async def test_run_procedure_builtin_wraps_execution_with_runtime_actor_context():
    client = Mock()
    client.context = Mock(
        actor_user_id="user-123",
        actor_type="agent",
        actor_key="procedure-runner",
        actor_source="agent",
    )
    service = ProcedureService(client)
    expected_result = {
        "success": True,
        "status": "COMPLETED",
        "procedure_id": CONSOLE_CHAT_BUILTIN_ID,
    }
    resolved_actor = {
        "actor_user_id": "user-123",
        "actor_type": "agent",
        "actor_key": "procedure-runner",
        "actor_source": "agent",
    }

    with patch(
        "plexus.cli.procedure.service.resolve_actor_context",
        return_value=resolved_actor,
    ) as resolve_actor_mock, patch(
        "plexus.cli.procedure.service.set_runtime_actor_context",
        return_value=nullcontext(),
    ) as set_actor_context_mock, patch(
        "plexus.cli.procedure.mcp_transport.create_procedure_mcp_server",
        new=AsyncMock(return_value=Mock()),
    ), patch(
        "plexus.cli.procedure.procedure_executor.execute_procedure",
        new=AsyncMock(return_value=expected_result),
    ):
        result = await service.run_procedure(CONSOLE_CHAT_BUILTIN_ID, account_id="acct-1")

    assert result == expected_result
    resolve_actor_mock.assert_called_once_with(
        runtime_override=client.context,
        explicit_source="agent",
    )
    set_actor_context_mock.assert_called_once_with(resolved_actor)


@pytest.mark.asyncio
async def test_run_evaluation_for_procedure_passes_parent_client_and_account():
    client = Mock()
    service = ProcedureService(client)

    with patch(
        "plexus.cli.shared.evaluation_runner.run_accuracy_evaluation",
        new=AsyncMock(return_value={"success": True}),
    ) as run_eval_mock:
        result = await service._run_evaluation_for_procedure(
            procedure_id="proc-1",
            scorecard_name="Card",
            score_name="Score",
            score_version_id=None,
            account_id="acc-1",
            parameter_values={},
            n_samples=5,
        )

    assert '"success": true' in result
    run_eval_mock.assert_awaited_once()
    run_eval_kwargs = run_eval_mock.await_args.kwargs
    assert run_eval_kwargs["client"] is client
    assert run_eval_kwargs["account_id"] == "acc-1"
