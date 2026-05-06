from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    database_url: str
    upstream_api_url: Optional[str]
    upstream_api_key: Optional[str]
    proxy_api_key: Optional[str]
    cache_ttl_seconds: int
    cache_stale_seconds: int
    upstream_timeout_seconds: float
    upstream_disabled: bool
    enable_debug: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv(
                "PLEXUS_PROXY_DATABASE_URL",
                "postgresql://plexus:plexus@localhost:5432/plexus_proxy",
            ),
            upstream_api_url=os.getenv("PLEXUS_PROXY_UPSTREAM_API_URL"),
            upstream_api_key=os.getenv("PLEXUS_PROXY_UPSTREAM_API_KEY"),
            proxy_api_key=os.getenv("PLEXUS_PROXY_API_KEY"),
            cache_ttl_seconds=int(os.getenv("PLEXUS_PROXY_CACHE_TTL_SECONDS", "900")),
            cache_stale_seconds=int(os.getenv("PLEXUS_PROXY_CACHE_STALE_SECONDS", "86400")),
            upstream_timeout_seconds=float(os.getenv("PLEXUS_PROXY_UPSTREAM_TIMEOUT_SECONDS", "30")),
            upstream_disabled=os.getenv("PLEXUS_PROXY_UPSTREAM_DISABLED", "false").lower()
            in {"1", "true", "yes"},
            enable_debug=os.getenv("PLEXUS_PROXY_ENABLE_DEBUG", "false").lower()
            in {"1", "true", "yes"},
        )
