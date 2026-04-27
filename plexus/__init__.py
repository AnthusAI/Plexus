"""
Plexus: Orchestration for AI/ML classification at scale.

This package exposes many submodules. To keep imports lightweight and avoid
optional heavy dependencies during package import, top‑level symbols are
resolved lazily via ``__getattr__`` when accessed.
"""

import importlib
import os
import warnings

# Disable DSPy's on-disk cache when requested, using DSPy's official API.
# This avoids SQLite lock contention when running parallel evaluations.
# We also close the FanoutCache that DSPy created at import time so its
# file descriptors are released.
if os.environ.get("DSPY_DISABLE_DISK_CACHE", "").lower() in ("1", "true", "yes"):
    import dspy
    # Close the FanoutCache that was auto-created at import time
    _old_disk = getattr(getattr(dspy, "cache", None), "disk_cache", None)
    if hasattr(_old_disk, "close"):
        _old_disk.close()
    # Replace with memory-only cache via DSPy's public configure_cache()
    from dspy.clients import configure_cache
    configure_cache(enable_disk_cache=False)
    del _old_disk
from typing import Any

warnings.filterwarnings(
    "ignore",
    message=r"Field \"model_.*\" .* has conflict with protected namespace \"model_\".*",
)

from ._version import __version__

# Public symbols available via lazy import
__all__ = [
    "Evaluation",
    "PromptTemplateLoader",
    "Scorecard",
    "ScorecardResults",
    "ScorecardResultsAnalysis",
    "__version__",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - trivial lazy loader
    if name == "Evaluation":
        return importlib.import_module(".Evaluation", __name__).__dict__[name]
    if name == "PromptTemplateLoader":
        return importlib.import_module(".PromptTemplateLoader", __name__).__dict__[
            name
        ]
    if name == "Scorecard":
        return importlib.import_module(".Scorecard", __name__).__dict__[name]
    if name == "ScorecardResults":
        return importlib.import_module(".ScorecardResults", __name__).__dict__[
            name
        ]
    if name == "ScorecardResultsAnalysis":
        return importlib.import_module(".ScorecardResultsAnalysis", __name__).__dict__[
            name
        ]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
