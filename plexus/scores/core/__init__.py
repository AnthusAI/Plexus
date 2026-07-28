"""
Core score helpers.

Keep this package initializer lightweight. Dataset loading and visualization
helpers import pandas, sklearn, matplotlib, and seaborn, so expose them lazily.
"""

from importlib import import_module


_HELPER_MODULES = {
    "ScoreData": "plexus.scores.core.ScoreData",
    "ScoreVisualization": "plexus.scores.core.ScoreVisualization",
}


def __getattr__(name: str):
    module_name = _HELPER_MODULES.get(name)
    if not module_name:
        raise AttributeError(f"module 'plexus.scores.core' has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = list(_HELPER_MODULES)
