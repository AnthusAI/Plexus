"""Lean DSPy primitives package exports for console worker runtime."""

from __future__ import annotations

from importlib import import_module

_LAZY = {
    "BaseModule": ("dspy.primitives.base_module", "BaseModule"),
    "CodeInterpreter": ("dspy.primitives.code_interpreter", "CodeInterpreter"),
    "CodeInterpreterError": ("dspy.primitives.code_interpreter", "CodeInterpreterError"),
    "FinalOutput": ("dspy.primitives.code_interpreter", "FinalOutput"),
    "Example": ("dspy.primitives.example", "Example"),
    "Module": ("dspy.primitives.module", "Module"),
    "Completions": ("dspy.primitives.prediction", "Completions"),
    "Prediction": ("dspy.primitives.prediction", "Prediction"),
    "PythonInterpreter": ("dspy.primitives.python_interpreter", "PythonInterpreter"),
}


def __getattr__(name: str):
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module 'dspy.primitives' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = list(_LAZY.keys())
