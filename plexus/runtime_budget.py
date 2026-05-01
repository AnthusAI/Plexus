from __future__ import annotations

import json
import os
import signal
import threading
import time
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any, Iterator


class RuntimeBudgetLimitExceeded(RuntimeError):
    """Raised when worker execution exceeds its assigned runtime budget."""


@dataclass(frozen=True)
class RuntimeBudgetSpec:
    usd: float
    wallclock_seconds: float
    depth: int
    tool_calls: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RuntimeBudgetSpec":
        if not isinstance(value, dict):
            raise ValueError("budget must be an object")

        wallclock_value = value.get("wallclock_seconds")
        if wallclock_value is None:
            wallclock_value = value.get("wallclock")
        required = {
            "usd": value.get("usd"),
            "wallclock_seconds": wallclock_value,
            "depth": value.get("depth"),
            "tool_calls": value.get("tool_calls"),
        }
        missing = [key for key, item in required.items() if item is None]
        if missing:
            raise ValueError("budget requires explicit " + ", ".join(sorted(missing)))

        spec = cls(
            usd=float(required["usd"]),
            wallclock_seconds=float(required["wallclock_seconds"]),
            depth=int(required["depth"]),
            tool_calls=int(required["tool_calls"]),
        )
        if spec.usd < 0:
            raise ValueError("budget.usd must be non-negative")
        if spec.wallclock_seconds <= 0:
            raise ValueError("budget.wallclock_seconds must be positive")
        if spec.depth < 0:
            raise ValueError("budget.depth must be non-negative")
        if spec.tool_calls < 0:
            raise ValueError("budget.tool_calls must be non-negative")
        return spec

    def to_dict(self) -> dict[str, Any]:
        return {
            "usd": self.usd,
            "wallclock_seconds": self.wallclock_seconds,
            "depth": self.depth,
            "tool_calls": self.tool_calls,
        }


def runtime_budget_spec_from_env(env_var: str = "PLEXUS_CHILD_BUDGET") -> RuntimeBudgetSpec | None:
    raw_budget = os.environ.get(env_var)
    if raw_budget is None or raw_budget.strip() == "":
        return None
    try:
        parsed = json.loads(raw_budget)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{env_var} must be valid JSON") from exc
    return RuntimeBudgetSpec.from_dict(parsed)


class RuntimeBudgetMeter:
    """Worker-side runtime budget meter for propagated child budgets."""

    def __init__(
        self,
        spec: RuntimeBudgetSpec,
        *,
        clock: Any | None = None,
    ) -> None:
        self.spec = spec
        self._clock = clock or time.monotonic
        self._start = self._clock()
        self.spent_usd = 0.0
        self.tool_calls = 0

    @classmethod
    def from_env(cls, env_var: str = "PLEXUS_CHILD_BUDGET") -> "RuntimeBudgetMeter | None":
        spec = runtime_budget_spec_from_env(env_var)
        return cls(spec) if spec is not None else None

    def elapsed_seconds(self) -> float:
        return self._clock() - self._start

    def check_wallclock(self, operation: str) -> None:
        elapsed = self.elapsed_seconds()
        if elapsed > self.spec.wallclock_seconds:
            raise RuntimeBudgetLimitExceeded(
                f"{operation} exceeded child wallclock budget: "
                f"{elapsed:.3f}s > {self.spec.wallclock_seconds:.3f}s"
            )

    def record_tool_call(self, operation: str, count: int = 1) -> None:
        next_count = self.tool_calls + int(count)
        if next_count > self.spec.tool_calls:
            raise RuntimeBudgetLimitExceeded(
                f"{operation} exceeded child tool_calls budget: "
                f"{next_count} > {self.spec.tool_calls}"
            )
        self.tool_calls = next_count

    def record_usd(self, operation: str, usd: Any) -> None:
        try:
            amount = float(usd or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        next_total = self.spent_usd + amount
        if next_total > self.spec.usd:
            raise RuntimeBudgetLimitExceeded(
                f"{operation} exceeded child USD budget: "
                f"${next_total:.6f} > ${self.spec.usd:.6f}"
            )
        self.spent_usd = next_total

    @contextmanager
    def enforce_wallclock(self, operation: str) -> Iterator[None]:
        self.check_wallclock(operation)
        if threading.current_thread() is not threading.main_thread():
            yield
            self.check_wallclock(operation)
            return

        def _raise_timeout(_signum: int, _frame: Any) -> None:
            raise RuntimeBudgetLimitExceeded(
                f"{operation} exceeded child wallclock budget: "
                f"{self.spec.wallclock_seconds:.3f}s"
            )

        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, _raise_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.spec.wallclock_seconds)
        try:
            yield
            self.check_wallclock(operation)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
            if previous_timer[0] > 0:
                signal.setitimer(signal.ITIMER_REAL, *previous_timer)

    def maybe_enforce_wallclock(self, operation: str):
        return self.enforce_wallclock(operation) if self is not None else nullcontext()
