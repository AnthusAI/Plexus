from __future__ import annotations

import os
from typing import Union

from .config import Settings
from .store import PostgresStore
from .virtuus_store import VirtuusStore

Store = Union[PostgresStore, VirtuusStore]


def resolve_store_type(settings: Settings) -> str:
    configured = settings.store_type or os.getenv("PLEXUS_STORE", "postgres")
    return configured.strip().lower()


def resolve_data_dir(settings: Settings) -> str | None:
    return settings.virtuus_data_dir or os.getenv("PLEXUS_DATA_DIR")


def create_store(settings: Settings) -> Store:
    store_type = resolve_store_type(settings)
    if store_type == "virtuus":
        data_dir = resolve_data_dir(settings)
        if not data_dir:
            raise RuntimeError(
                "PLEXUS_STORE=virtuus requires PLEXUS_VIRTUUS_DATA_DIR or PLEXUS_DATA_DIR"
            )
        return VirtuusStore(data_dir)
    return PostgresStore(settings.database_url)
