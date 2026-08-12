"""ECS agent endpoint adapter for task scale-in protection."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen


class EcsAgentTaskScaleInProtection:
    """Protect the current ECS task through the injected agent endpoint.

    ``ECS_AGENT_URI`` is available only inside ECS.  The agent authenticates
    these calls with the task role, so no static AWS credentials or SDK are
    required in the portable worker.
    """

    def __init__(self, agent_uri: str, *, expires_in_minutes: int = 2880) -> None:
        endpoint = agent_uri.rstrip("/")
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("ECS_AGENT_URI must be an HTTP URL")
        if not 1 <= expires_in_minutes <= 2880:
            raise ValueError(
                "task protection expiry must be between 1 and 2880 minutes"
            )
        self._endpoint = f"{endpoint}/task-protection/v1/state"
        self._expires_in_minutes = expires_in_minutes

    def enable(self) -> bool:
        return self._set_state(True, self._expires_in_minutes)

    def clear(self) -> bool:
        return self._set_state(False, None)

    def _set_state(self, enabled: bool, expires_in_minutes: int | None) -> bool:
        payload: dict[str, object] = {"ProtectionEnabled": enabled}
        if expires_in_minutes is not None:
            payload["ExpiresInMinutes"] = expires_in_minutes
        request = Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            with urlopen(request, timeout=5) as response:  # nosec B310: ECS-local URI
                return 200 <= response.status < 300
        except OSError:
            return False
