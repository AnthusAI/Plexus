"""
Plexus: Orchestration for AI/ML classification at scale.

This package exposes many submodules. To keep imports lightweight and avoid
optional heavy dependencies during package import, top‑level symbols are
resolved lazily via ``__getattr__`` when accessed.
"""

import importlib
import warnings
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
