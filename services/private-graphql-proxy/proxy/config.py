from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    store_type: str
    virtuus_data_dir: Optional[str]
    database_url: str
    backend_mode: str
    upstream_api_url: Optional[str]
    upstream_api_key: Optional[str]
    proxy_api_key: Optional[str]
    auth_mode: str
    auth_mode_explicit: bool
    cache_ttl_seconds: int
    cache_stale_seconds: int
    upstream_timeout_seconds: float
    upstream_disabled: bool
    enable_debug: bool
    cors_allow_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        proxy_api_key = os.getenv("PLEXUS_PROXY_API_KEY")
        auth_mode_env = os.getenv("PLEXUS_PROXY_AUTH_MODE")
        auth_mode = (
            auth_mode_env.strip().lower()
            if auth_mode_env and auth_mode_env.strip()
            else ("api_key" if proxy_api_key else "trusted_open")
        )
        return cls(
            store_type=os.getenv("PLEXUS_STORE", "postgres").strip().lower(),
            virtuus_data_dir=os.getenv("PLEXUS_VIRTUUS_DATA_DIR") or os.getenv("PLEXUS_DATA_DIR"),
            database_url=os.getenv(
                "PLEXUS_PROXY_DATABASE_URL",
                "postgresql://plexus:plexus@localhost:5432/plexus_proxy",
            ),
            backend_mode=os.getenv("PLEXUS_BACKEND_MODE", "amplify").strip().lower(),
            upstream_api_url=os.getenv("PLEXUS_PROXY_UPSTREAM_API_URL"),
            upstream_api_key=os.getenv("PLEXUS_PROXY_UPSTREAM_API_KEY"),
            proxy_api_key=proxy_api_key,
            auth_mode=auth_mode,
            auth_mode_explicit=bool(auth_mode_env and auth_mode_env.strip()),
            cache_ttl_seconds=int(os.getenv("PLEXUS_PROXY_CACHE_TTL_SECONDS", "900")),
            cache_stale_seconds=int(os.getenv("PLEXUS_PROXY_CACHE_STALE_SECONDS", "86400")),
            upstream_timeout_seconds=float(os.getenv("PLEXUS_PROXY_UPSTREAM_TIMEOUT_SECONDS", "30")),
            upstream_disabled=os.getenv("PLEXUS_PROXY_UPSTREAM_DISABLED", "false").lower()
            in {"1", "true", "yes"},
            enable_debug=os.getenv("PLEXUS_PROXY_ENABLE_DEBUG", "false").lower()
            in {"1", "true", "yes"},
            cors_allow_origins=tuple(
                origin.strip()
                for origin in os.getenv(
                    "PLEXUS_PROXY_CORS_ALLOW_ORIGINS",
                    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
                ).split(",")
                if origin.strip()
            ),
        )
