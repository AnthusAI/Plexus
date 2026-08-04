"""Portable command-worker lifecycle foundation."""

from .models import Claim, CommandEnvelope, JSONValue, ProgressUpdate
from .ports import (
    ClaimStatus,
    Clock,
    Delivery,
    DrainSignal,
    ExecutionContext,
    Executor,
    HeartbeatHandle,
    HeartbeatScheduler,
    LifecycleStore,
    Transport,
)
from .scheduler import ThreadHeartbeatScheduler
from .service import (
    CommandWorkerService,
    EventDrainSignal,
    ServiceOutcome,
    ServiceReceiveError,
    ServiceStopReason,
)
from .worker import CommandWorker, LeaseLostError, ProcessOutcome

__all__ = [
    "Claim",
    "ClaimStatus",
    "Clock",
    "CommandEnvelope",
    "CommandWorker",
    "Delivery",
    "DrainSignal",
    "ExecutionContext",
    "Executor",
    "EventDrainSignal",
    "HeartbeatHandle",
    "HeartbeatScheduler",
    "JSONValue",
    "LeaseLostError",
    "LifecycleStore",
    "ProcessOutcome",
    "ProgressUpdate",
    "Transport",
    "ThreadHeartbeatScheduler",
    "CommandWorkerService",
    "ServiceOutcome",
    "ServiceReceiveError",
    "ServiceStopReason",
]
