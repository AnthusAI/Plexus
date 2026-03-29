"""Lean DSPy utils package init for console worker runtime."""

from __future__ import annotations

import os
from importlib import import_module

import requests

from dspy.utils import exceptions, magicattr
from dspy.utils.annotation import experimental
from dspy.utils.callback import BaseCallback, with_callbacks
from dspy.utils.inspect_history import pretty_print_history
from dspy.utils.syncify import syncify


def download(url):
    filename = os.path.basename(url)
    remote_size = int(requests.head(url, allow_redirects=True).headers.get("Content-Length", 0))
    local_size = os.path.getsize(filename) if os.path.exists(filename) else 0
    if not os.path.exists(filename) or local_size != remote_size:
        with requests.get(url, stream=True) as response, open(filename, "wb") as target:
            for chunk in response.iter_content(chunk_size=8192):
                target.write(chunk)


def __getattr__(name: str):
    if name in {"StatusMessage", "StatusMessageProvider"}:
        module = import_module("dspy.streaming.messages")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'dspy.utils' has no attribute {name!r}")


__all__ = [  # noqa: F822
    "download",
    "exceptions",
    "magicattr",
    "BaseCallback",
    "with_callbacks",
    "experimental",
    "StatusMessage",
    "StatusMessageProvider",
    "pretty_print_history",
    "syncify",
]
