from __future__ import annotations

from typing import Any, Optional

import requests


class UpstreamAppSyncClient:
    def __init__(
        self,
        api_url: Optional[str],
        api_key: Optional[str],
        timeout_seconds: float,
        disabled: bool = False,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.disabled = disabled

    def execute(
        self,
        query: str,
        variables: dict[str, Any],
        operation_name: Optional[str],
    ) -> dict[str, Any]:
        if self.disabled:
            raise RuntimeError("upstream AppSync access is disabled")
        if not self.api_url or not self.api_key:
            raise RuntimeError("upstream AppSync URL/key are not configured")

        response = requests.post(
            self.api_url,
            json={
                "query": query,
                "variables": variables or {},
                "operationName": operation_name,
            },
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if "errors" in payload:
            raise RuntimeError(f"upstream GraphQL errors: {payload['errors']}")
        return payload
