"""Standard-library heartbeat scheduling for the portable worker core."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from threading import Event, Thread


class _ThreadHeartbeatHandle:
    def __init__(
        self, stop_event: Event, thread: Thread, shutdown_timeout: float
    ) -> None:
        self._stop_event = stop_event
        self._thread = thread
        self._shutdown_timeout = shutdown_timeout

    def stop(self) -> bool:
        self._stop_event.set()
        self._thread.join(self._shutdown_timeout)
        return not self._thread.is_alive()


class ThreadHeartbeatScheduler:
    """Run recurring callbacks on a daemon thread with bounded shutdown."""

    def __init__(self, shutdown_timeout: timedelta = timedelta(seconds=5)) -> None:
        if shutdown_timeout <= timedelta(0):
            raise ValueError("shutdown_timeout must be positive")
        self._shutdown_timeout = shutdown_timeout.total_seconds()

    def start(
        self, interval: timedelta, callback: Callable[[], None]
    ) -> _ThreadHeartbeatHandle:
        if interval <= timedelta(0):
            raise ValueError("interval must be positive")
        stop_event = Event()

        def run() -> None:
            while not stop_event.wait(interval.total_seconds()):
                callback()

        thread = Thread(
            target=run,
            name="command-worker-heartbeat",
            daemon=True,
        )
        thread.start()
        return _ThreadHeartbeatHandle(stop_event, thread, self._shutdown_timeout)
