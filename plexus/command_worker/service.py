"""Provider-neutral service loop for a warm command worker container."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from threading import Event

from .ports import DrainSignal, Transport
from .worker import CommandWorker, ProcessOutcome


class ServiceStopReason(str, Enum):
    DRAIN_REQUESTED = "drain_requested"


@dataclass(frozen=True, slots=True)
class ServiceOutcome:
    """Normal service termination and the work settled before it stopped."""

    stop_reason: ServiceStopReason
    process_outcomes: tuple[ProcessOutcome, ...]

    @property
    def processed_count(self) -> int:
        return len(self.process_outcomes)

    def count(self, outcome: ProcessOutcome) -> int:
        return self.process_outcomes.count(outcome)

    @property
    def outcome_counts(self) -> dict[ProcessOutcome, int]:
        return dict(Counter(self.process_outcomes))


class ServiceReceiveError(RuntimeError):
    """Raised when the transport cannot complete a bounded receive."""

    def __init__(
        self, error: Exception, process_outcomes: tuple[ProcessOutcome, ...]
    ) -> None:
        super().__init__(f"transport receive raised {type(error).__name__}: {error}")
        self.process_outcomes = process_outcomes

    @property
    def processed_count(self) -> int:
        return len(self.process_outcomes)


class EventDrainSignal:
    """Thread-safe drain signal backed by a standard-library event."""

    def __init__(self) -> None:
        self._event = Event()

    def request(self) -> None:
        self._event.set()

    def is_requested(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: timedelta) -> bool:
        if timeout < timedelta(0):
            raise ValueError("timeout must not be negative")
        return self._event.wait(timeout.total_seconds())


class CommandWorkerService:
    """Receive and synchronously settle one delivery at a time until draining."""

    def __init__(
        self,
        transport: Transport,
        worker: CommandWorker,
        owner: str,
        drain: DrainSignal,
        receive_timeout: timedelta,
        idle_wait: timedelta,
    ) -> None:
        if not owner:
            raise ValueError("owner must be non-empty")
        if receive_timeout <= timedelta(0):
            raise ValueError("receive_timeout must be positive")
        if idle_wait <= timedelta(0):
            raise ValueError("idle_wait must be positive")
        self._transport = transport
        self._worker = worker
        self._owner = owner
        self._drain = drain
        self._receive_timeout = receive_timeout
        self._idle_wait = idle_wait

    def run(self) -> ServiceOutcome:
        outcomes: list[ProcessOutcome] = []

        while not self._drain.is_requested():
            try:
                delivery = self._transport.receive(self._receive_timeout)
            except Exception as exc:
                raise ServiceReceiveError(exc, tuple(outcomes)) from exc

            if self._drain.is_requested():
                if delivery is not None:
                    delivery.release()
                break

            if delivery is None:
                self._drain.wait(self._idle_wait)
                continue

            outcomes.append(self._worker.process(delivery, self._owner))

        return ServiceOutcome(
            stop_reason=ServiceStopReason.DRAIN_REQUESTED,
            process_outcomes=tuple(outcomes),
        )
