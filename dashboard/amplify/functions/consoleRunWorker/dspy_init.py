"""Lean DSPy package init for console worker runtime.

Avoid eager imports that pull optional heavy dependencies (numpy, teleprompt
stack) while preserving symbols used by Tactus.
"""

from __future__ import annotations

from importlib import import_module

from dspy.dsp.utils.settings import settings

configure = settings.configure
load_settings = settings.load
context = settings.context

_LAZY_IMPORTS = {
    "BaseLM": ("dspy.clients.base_lm", "BaseLM"),
    "inspect_history": ("dspy.clients.base_lm", "inspect_history"),
    "LM": ("dspy.clients.lm", "LM"),
    "Predict": ("dspy.predict.predict", "Predict"),
    "ChainOfThought": ("dspy.predict.chain_of_thought", "ChainOfThought"),
    "ProgramOfThought": ("dspy.predict.program_of_thought", "ProgramOfThought"),
    "ReAct": ("dspy.predict.react", "ReAct"),
    "History": ("dspy.adapters.types.history", "History"),
    "Module": ("dspy.primitives.module", "Module"),
    "Prediction": ("dspy.primitives.prediction", "Prediction"),
    "Signature": ("dspy.signatures.signature", "Signature"),
    "ensure_signature": ("dspy.signatures.signature", "ensure_signature"),
    "InputField": ("dspy.signatures.field", "InputField"),
    "OutputField": ("dspy.signatures.field", "OutputField"),
    "Tool": ("dspy.adapters.types.tool", "Tool"),
    "ToolCalls": ("dspy.adapters.types.tool", "ToolCalls"),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'dspy' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = [  # noqa: F822
    "BaseLM",
    "LM",
    "inspect_history",
    "settings",
    "configure",
    "load_settings",
    "context",
    "Predict",
    "ChainOfThought",
    "ProgramOfThought",
    "ReAct",
    "History",
    "Module",
    "Prediction",
    "Signature",
    "ensure_signature",
    "InputField",
    "OutputField",
    "Tool",
    "ToolCalls",
]
