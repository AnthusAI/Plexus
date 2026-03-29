"""Lean DSPy predict package exports for console worker runtime."""

from __future__ import annotations

from importlib import import_module

_LAZY = {
    "Predict": ("dspy.predict.predict", "Predict"),
    "ChainOfThought": ("dspy.predict.chain_of_thought", "ChainOfThought"),
    "ProgramOfThought": ("dspy.predict.program_of_thought", "ProgramOfThought"),
    "ReAct": ("dspy.predict.react", "ReAct"),
    "Parallel": ("dspy.predict.parallel", "Parallel"),
}


def __getattr__(name: str):
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module 'dspy.predict' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = list(_LAZY.keys())
