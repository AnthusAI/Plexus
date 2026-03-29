"""Lean DSPy clients package init for console worker runtime."""

from __future__ import annotations

import logging
import os
from importlib import import_module
from pathlib import Path

import litellm

from dspy.clients.cache import Cache

logger = logging.getLogger(__name__)
DISK_CACHE_DIR = os.environ.get("DSPY_CACHEDIR") or os.path.join(Path.home(), ".dspy_cache")
DISK_CACHE_LIMIT = int(os.environ.get("DSPY_CACHE_LIMIT", 3e10))


def configure_cache(
    enable_disk_cache: bool | None = True,
    enable_memory_cache: bool | None = True,
    disk_cache_dir: str | None = DISK_CACHE_DIR,
    disk_size_limit_bytes: int | None = DISK_CACHE_LIMIT,
    memory_max_entries: int = 1000000,
):
    dspy_cache = Cache(
        enable_disk_cache,
        enable_memory_cache,
        disk_cache_dir,
        disk_size_limit_bytes,
        memory_max_entries,
    )

    import dspy

    dspy.cache = dspy_cache


litellm.telemetry = False
litellm.cache = None


def _get_dspy_cache():
    disk_cache_dir = os.environ.get("DSPY_CACHEDIR") or os.path.join(Path.home(), ".dspy_cache")
    disk_cache_limit = int(os.environ.get("DSPY_CACHE_LIMIT", 3e10))
    try:
        return Cache(
            enable_disk_cache=True,
            enable_memory_cache=True,
            disk_cache_dir=disk_cache_dir,
            disk_size_limit_bytes=disk_cache_limit,
            memory_max_entries=1000000,
        )
    except Exception as exc:
        logger.warning("Failed to initialize disk cache; using memory-only cache: %s", exc)
        return Cache(
            enable_disk_cache=False,
            enable_memory_cache=True,
            disk_cache_dir=disk_cache_dir,
            disk_size_limit_bytes=disk_cache_limit,
            memory_max_entries=1000000,
        )


DSPY_CACHE = _get_dspy_cache()
if "LITELLM_LOCAL_MODEL_COST_MAP" not in os.environ:
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"


def configure_litellm_logging(level: str = "ERROR"):
    from litellm._logging import verbose_logger

    numeric = getattr(logging, level)
    verbose_logger.setLevel(numeric)
    for handler in verbose_logger.handlers:
        handler.setLevel(numeric)


def enable_litellm_logging():
    litellm.suppress_debug_info = False
    configure_litellm_logging("DEBUG")


def disable_litellm_logging():
    litellm.suppress_debug_info = True
    configure_litellm_logging("ERROR")


disable_litellm_logging()


def __getattr__(name: str):
    if name in {"BaseLM", "inspect_history"}:
        module = import_module("dspy.clients.base_lm")
        value = getattr(module, name)
    elif name == "LM":
        module = import_module("dspy.clients.lm")
        value = module.LM
    elif name in {"Provider", "TrainingJob"}:
        module = import_module("dspy.clients.provider")
        value = getattr(module, name)
    elif name == "Embedder":
        class _UnavailableEmbedder:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("DSPy Embedder is unavailable in console worker runtime")

        value = _UnavailableEmbedder
    else:
        raise AttributeError(f"module 'dspy.clients' has no attribute {name!r}")
    globals()[name] = value
    return value


__all__ = [  # noqa: F822
    "BaseLM",
    "LM",
    "Provider",
    "TrainingJob",
    "inspect_history",
    "Embedder",
    "enable_litellm_logging",
    "disable_litellm_logging",
    "configure_cache",
]
