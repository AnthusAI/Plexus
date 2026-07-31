"""Contract tests for the reported, human-governed portfolio procedure."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from lupa import LuaError, LuaRuntime


PROCEDURE_PATH = Path(__file__).resolve().parents[2] / "procedures" / "optimization_portfolio_run.yaml"
REPO_ROOT = PROCEDURE_PATH.parents[1]


def test_portfolio_run_procedure_uses_the_single_runtime_orchestrator_and_structured_human_review():
    parsed = yaml.safe_load(PROCEDURE_PATH.read_text())

    assert parsed["class"] == "Tactus"
    assert parsed["name"] == "Optimization Portfolio Run"
    assert "plexus.optimization.portfolio_run" in parsed["code"]
    assert "Human.review" in parsed["code"]
    assert "action_key" in parsed["code"]
    assert "resource_refs" in parsed["code"]
    assert "preconditions" in parsed["code"]
    assert "response_schema" in parsed["code"]
    assert "approval_responses" in parsed["code"]
    assert parsed["params"]["max_semantic_diagnoses"] == {
        "type": "number",
        "required": True,
        "description": "Explicit maximum number of model-backed semantic score diagnoses for this portfolio run.",
    }
    assert "max_semantic_diagnoses = params.max_semantic_diagnoses" in parsed["code"]
    assert parsed["params"]["max_semantic_cost_usd"] == {
        "type": "string",
        "required": True,
        "description": "Exact decimal-string run-wide cap for semantic diagnosis, separate from optimizer cost.",
    }
    assert "max_semantic_cost_usd = params.max_semantic_cost_usd" in parsed["code"]
    assert parsed["params"]["execution_mode"] == {
        "type": "string",
        "required": False,
        "default": "automatic",
        "description": "Launch policy: automatic for deterministic safe targets, or approval_required for Human.review.",
    }
    assert "execution_mode = params.execution_mode" in parsed["code"]
    assert parsed["params"]["toolchain_version"] == {
        "type": "string",
        "required": False,
        "description": "Optional immutable build identity added to the recorded Plexus and Tactus package versions.",
    }
    assert "toolchain_version = params.toolchain_version" in parsed["code"]
    assert "while true do" in parsed["code"]
    assert "set_champion" not in parsed["code"]
    assert "score.update" not in parsed["code"]


def test_portfolio_run_procedure_durably_waits_for_exact_optimizer_children():
    code = yaml.safe_load(PROCEDURE_PATH.read_text())["code"]

    assert 'result.status == "WAITING_FOR_CHILDREN"' in code
    assert "Procedure.await_children" in code
    assert 'mode = "any"' in code
    assert "optimizer_child_snapshots = optimizer_child_snapshots" in code
    assert "State.set(\"optimization_portfolio_child_snapshots\"" in code
    assert "child.task_id" in code
    assert "child.procedure_id" in code
    assert "launch_state.launch_spec.identity" in code
    assert "child.target.scorecard_id" in code
    assert "child.target.score_id" in code
    assert "Stage.set(\"optimization\")" in code


def test_portfolio_run_procedure_defers_retryable_publication_and_only_returns_explicit_terminals():
    code = yaml.safe_load(PROCEDURE_PATH.read_text())["code"]

    assert 'result.status == "RETRYABLE_PUBLICATION"' in code
    assert "Procedure.defer" in code
    assert "retry.key" in code
    assert "retry.resume_at" in code
    assert "retry.reason" in code
    assert "terminal_statuses[result.status]" in code

    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(
        """
params = {
  account_id = "account", run_key = "run", max_cost_usd = 1,
  max_semantic_diagnoses = 1, max_semantic_cost_usd = "1",
  max_samples = 1, max_iterations = 1, max_concurrency = 1,
  execution_mode = "automatic"
}
local calls = 0
deferred = nil
Stage = {set = function(_) end}
State = {get = function(_) return nil end, set = function(_, _) end}
Human = {review = function(_) error("human review must not run") end}
Procedure = {
  await_children = function(_) error("child wait must not run") end,
  defer = function(request) deferred = request end
}
plexus = {optimization = {portfolio_run = function(_)
  calls = calls + 1
  if calls == 1 then
    return {status = "RETRYABLE_PUBLICATION", retry = {
      key = "optimization-report-publication",
      resume_at = "2026-07-31T12:00:00Z",
      reason = "retryable_report_publication"
    }}
  end
  return {status = "COMPLETED", result = {}}
end}}
"""
    )
    execute = lua.execute("return function()\n" + code + "\nend")
    result = execute()

    assert result["status"] == "COMPLETED"
    deferred = lua.globals().deferred
    assert deferred["key"] == "optimization-report-publication"
    assert deferred["resume_at"] == "2026-07-31T12:00:00Z"
    assert deferred["reason"] == "retryable_report_publication"


@pytest.mark.asyncio
async def test_checked_in_portfolio_replays_defer_before_retrying_publication():
    """Exercise the real YAML through Tactus across wait, early replay, and due replay."""
    from tactus.adapters.memory import MemoryStorage
    from tactus.core.execution_context import BaseExecutionContext
    from tactus.core.runtime import TactusRuntime

    parsed = yaml.safe_load(PROCEDURE_PATH.read_text())
    parameters = """
params = {
  account_id = "account", run_key = "run", max_cost_usd = 1,
  max_semantic_diagnoses = 1, max_semantic_cost_usd = "1",
  max_samples = 1, max_iterations = 1, max_concurrency = 1,
  execution_mode = "automatic"
}
if plexus == nil then plexus = require("plexus") end
if Stage == nil then Stage = {set = function(_) end} end
"""
    parsed["procedure"] = parameters + parsed.pop("code")
    source = yaml.safe_dump(parsed, sort_keys=False)
    now = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
    first_resume_at = now + timedelta(minutes=5)
    second_resume_at = now + timedelta(minutes=10)
    clock = SimpleNamespace(now=now)

    storage = MemoryStorage()

    class _ClockedRuntime(TactusRuntime):
        def _create_execution_context(self, strict_determinism):
            return BaseExecutionContext(
                procedure_id=self.procedure_id,
                storage_backend=self.storage_backend,
                hitl_handler=self.hitl_handler,
                child_wait_resolver=self.child_wait_resolver,
                clock=lambda: clock.now,
                strict_determinism=strict_determinism,
                log_handler=self.log_handler,
            )

    class _Optimization:
        def __init__(self):
            self.calls = 0

        def portfolio_run(self, _request):
            self.calls += 1
            if self.calls in {1, 2}:
                return {
                    "status": "RETRYABLE_PUBLICATION",
                    "retry": {
                        "key": "optimization-report-publication",
                        "resume_at": (
                            first_resume_at if self.calls == 1 else second_resume_at
                        ).isoformat().replace("+00:00", "Z"),
                        "reason": "retryable_report_publication",
                    },
                }
            return {"status": "COMPLETED", "result": {}}

    optimization = _Optimization()

    async def execute():
        runtime = _ClockedRuntime(
            procedure_id="portfolio-retry-replay",
            storage_backend=storage,
            hitl_handler=object(),
            run_id="stable-run-identity",
        )
        runtime.register_python_module(
            "plexus", SimpleNamespace(optimization=optimization),
        )
        return await runtime.execute(source, context={}, format="yaml")

    first = await execute()
    assert first["success"] is False
    assert first["status"] == "WAITING_FOR_TIME"
    assert optimization.calls == 1

    clock.now = first_resume_at - timedelta(seconds=1)
    early = await execute()
    assert early["success"] is False
    assert early["status"] == "WAITING_FOR_TIME"
    assert optimization.calls == 1

    clock.now = first_resume_at
    second_wait = await execute()
    assert second_wait["success"] is False
    assert second_wait["status"] == "WAITING_FOR_TIME"
    assert optimization.calls == 2

    clock.now = second_resume_at - timedelta(seconds=1)
    second_early = await execute()
    assert second_early["success"] is False
    assert second_early["status"] == "WAITING_FOR_TIME"
    assert optimization.calls == 2

    clock.now = second_resume_at
    completed = await execute()
    assert completed["success"] is True
    assert completed["result"]["status"] == "COMPLETED"
    assert optimization.calls == 3

    metadata = storage.load_procedure_metadata("portfolio-retry-replay")
    continuations = [
        entry for entry in metadata.execution_log
        if entry.type == "scheduled_continuation"
    ]
    assert len(continuations) == 2
    assert all(entry.result["completed"] is True for entry in continuations)


def test_portfolio_run_procedure_cannot_complete_when_the_report_orchestrator_failed():
    """A returned failure is a failed procedure, not a successful Lua return."""
    code = yaml.safe_load(PROCEDURE_PATH.read_text())["code"]
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(
        """
params = {
  account_id = "account",
  run_key = "run",
  max_cost_usd = 1,
  max_semantic_diagnoses = 1,
  max_semantic_cost_usd = "1",
  max_samples = 1,
  max_iterations = 1,
  max_concurrency = 1,
  execution_mode = "automatic"
}
Stage = {set = function(_) end}
State = {get = function(_) return nil end, set = function(_, _) end}
Human = {review = function(_) error("human review must not run") end}
Procedure = {await_children = function(_) error("child wait must not run") end}
plexus = {optimization = {portfolio_run = function(_)
  return {status = "FAILED", error = "durable report publication failed"}
end}}
"""
    )
    execute = lua.execute("return function()\n" + code + "\nend")

    with pytest.raises(LuaError, match="durable report publication failed"):
        execute()


def test_semantic_budget_operator_docs_require_release_order_and_read_only_pilot():
    deployment = (REPO_ROOT / "optimization" / "DEPLOYMENT.md").read_text()
    checklist = (REPO_ROOT / "optimization" / "PRODUCTION_PILOT_CHECKLIST.md").read_text()
    skill = (REPO_ROOT.parents[0] / "skills" / "score-optimizer" / "SKILL.md").read_text()

    for text in (deployment, checklist, skill):
        assert "Tactus release/main" in text
        assert "Plexus pin/lock" in text
        assert "local/sandbox" in text
        assert "production read-only" in text
        assert "identity and budget" in text
    assert "max_semantic_cost_usd" in deployment
    assert "No new GraphQL resources" in checklist
    for text in (deployment, checklist):
        assert "pre-release cross-repo source tests only" in text
        assert "production/full release validation is blocked" in text
        assert "Tactus release" in text and "Plexus pin/lock" in text
