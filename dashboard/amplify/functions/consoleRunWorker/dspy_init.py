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
    "Adapter": ("dspy.adapters.base", "Adapter"),
    "ChatAdapter": ("dspy.adapters.chat_adapter", "ChatAdapter"),
    "JSONAdapter": ("dspy.adapters.json_adapter", "JSONAdapter"),
    "XMLAdapter": ("dspy.adapters.xml_adapter", "XMLAdapter"),
    "TwoStepAdapter": ("dspy.adapters.two_step_adapter", "TwoStepAdapter"),
    "Audio": ("dspy.adapters.types", "Audio"),
    "Code": ("dspy.adapters.types", "Code"),
    "File": ("dspy.adapters.types", "File"),
    "Reasoning": ("dspy.adapters.types", "Reasoning"),
    "Type": ("dspy.adapters.types", "Type"),
    "History": ("dspy.adapters.types.history", "History"),
    "Module": ("dspy.primitives.module", "Module"),
    "Prediction": ("dspy.primitives.prediction", "Prediction"),
    "Signature": ("dspy.signatures.signature", "Signature"),
    "ensure_signature": ("dspy.signatures.signature", "ensure_signature"),
    "InputField": ("dspy.signatures.field", "InputField"),
    "OutputField": ("dspy.signatures.field", "OutputField"),
    "Tool": ("dspy.adapters.types.tool", "Tool"),
    "ToolCalls": ("dspy.adapters.types.tool", "ToolCalls"),
    "Image": ("dspy.adapters.types", "Image"),
    "streamify": ("dspy.streaming.streamify", "streamify"),
    "asyncify": ("dspy.utils.asyncify", "asyncify"),
    "syncify": ("dspy.utils.syncify", "syncify"),
    "load": ("dspy.utils.saving", "load"),
    "track_usage": ("dspy.utils.usage_tracker", "track_usage"),
    "Evaluate": ("dspy.evaluate.evaluate", "Evaluate"),
    "configure_dspy_loggers": ("dspy.utils.logging_utils", "configure_dspy_loggers"),
    "disable_logging": ("dspy.utils.logging_utils", "disable_logging"),
    "enable_logging": ("dspy.utils.logging_utils", "enable_logging"),
    "DSPY_CACHE": ("dspy.clients", "DSPY_CACHE"),
    "ColBERTv2": ("dspy.dsp.colbertv2", "ColBERTv2"),
    "__name__": ("dspy.__metadata__", "__name__"),
    "__version__": ("dspy.__metadata__", "__version__"),
    "__description__": ("dspy.__metadata__", "__description__"),
    "__url__": ("dspy.__metadata__", "__url__"),
    "__author__": ("dspy.__metadata__", "__author__"),
    "__author_email__": ("dspy.__metadata__", "__author_email__"),
}

_FALLBACK_MODULES = (
    "dspy.adapters",
    "dspy.clients",
    "dspy.predict",
    "dspy.primitives",
    "dspy.signatures",
    "dspy.utils",
)


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is not None:
        module_name, attr_name = target
        module = import_module(module_name)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value

    for module_name in _FALLBACK_MODULES:
        try:
            module = import_module(module_name)
        except Exception:
            continue
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value

    raise AttributeError(f"module 'dspy' has no attribute {name!r}")


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
    "Adapter",
    "ChatAdapter",
    "JSONAdapter",
    "XMLAdapter",
    "TwoStepAdapter",
    "Audio",
    "Code",
    "File",
    "Reasoning",
    "Type",
    "History",
    "Module",
    "Prediction",
    "Signature",
    "ensure_signature",
    "InputField",
    "OutputField",
    "Tool",
    "ToolCalls",
    "Image",
    "streamify",
    "asyncify",
    "syncify",
    "load",
    "track_usage",
    "Evaluate",
    "configure_dspy_loggers",
    "disable_logging",
    "enable_logging",
    "DSPY_CACHE",
    "ColBERTv2",
]
