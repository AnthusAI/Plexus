from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jinja2 import Environment
from markupsafe import Markup


def _prepare_text_template_value(value: Any) -> Any:
    if isinstance(value, str):
        return Markup(value)
    if isinstance(value, Mapping):
        return {key: _prepare_text_template_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_prepare_text_template_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_prepare_text_template_value(item) for item in value)
    return value


def render_text_template(
    template_text: str,
    context: Mapping[str, Any],
    *,
    undefined: type | None = None,
    trim_blocks: bool = False,
    lstrip_blocks: bool = False,
) -> str:
    environment_kwargs: dict[str, Any] = {
        "autoescape": True,
        "trim_blocks": trim_blocks,
        "lstrip_blocks": lstrip_blocks,
    }
    if undefined is not None:
        environment_kwargs["undefined"] = undefined

    environment = Environment(**environment_kwargs)
    template = environment.from_string(template_text)
    prepared_context = {
        key: _prepare_text_template_value(value)
        for key, value in context.items()
    }
    return template.render(**prepared_context)
