import json

import pytest

from plexus.runtime_budget import (
    RuntimeBudgetLimitExceeded,
    RuntimeBudgetMeter,
    RuntimeBudgetSpec,
    runtime_budget_spec_from_env,
)


def test_runtime_budget_spec_requires_explicit_fields():
    with pytest.raises(ValueError, match="wallclock_seconds"):
        RuntimeBudgetSpec.from_dict({"usd": 1, "depth": 1, "tool_calls": 2})


def test_runtime_budget_spec_loads_from_env(monkeypatch):
    monkeypatch.setenv(
        "PLEXUS_CHILD_BUDGET",
        json.dumps(
            {
                "usd": 0.25,
                "wallclock_seconds": 30,
                "depth": 1,
                "tool_calls": 4,
            }
        ),
    )

    spec = runtime_budget_spec_from_env()

    assert spec == RuntimeBudgetSpec(
        usd=0.25,
        wallclock_seconds=30.0,
        depth=1,
        tool_calls=4,
    )


def test_runtime_budget_meter_rejects_over_budget_cost():
    meter = RuntimeBudgetMeter(
        RuntimeBudgetSpec(usd=0.01, wallclock_seconds=30, depth=1, tool_calls=4)
    )

    meter.record_usd("procedure.llm", 0.004)

    with pytest.raises(RuntimeBudgetLimitExceeded, match="USD budget"):
        meter.record_usd("procedure.llm", 0.007)


def test_runtime_budget_meter_rejects_over_budget_tool_calls():
    meter = RuntimeBudgetMeter(
        RuntimeBudgetSpec(usd=1, wallclock_seconds=30, depth=1, tool_calls=1)
    )

    meter.record_tool_call("worker.step")

    with pytest.raises(RuntimeBudgetLimitExceeded, match="tool_calls budget"):
        meter.record_tool_call("worker.step")
