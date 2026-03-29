"""Shared CLI utilities.

Avoid importing heavy dependencies at package import time.
Callers should access utilities via explicit module imports or lazy attributes.
"""

from importlib import import_module
from typing import Any

__all__ = [
    "get_score_yaml_path",
    "get_score_guidelines_path",
    "sanitize_path_name",
    "select_sample_data_driven",
    "select_sample_csv",
    "get_scoring_jobs_for_batch",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - import proxy
    if name in __all__:
        return getattr(import_module(".shared", __name__), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
