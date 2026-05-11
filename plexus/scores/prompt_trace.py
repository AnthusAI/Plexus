import re
from typing import Any, Dict, List


CAPTURE_RENDERED_MESSAGES_METADATA_KEY = "_plexus_capture_rendered_messages"

_UNRESOLVED_PLACEHOLDER_PATTERNS = (
    ("xcc", re.compile(r"\{xcc:\s*[^}]+\}")),
    ("jinja", re.compile(r"\{\{\s*[^{}]+?\s*\}\}")),
)


def should_capture_rendered_messages(metadata: Any) -> bool:
    return isinstance(metadata, dict) and bool(
        metadata.get(CAPTURE_RENDERED_MESSAGES_METADATA_KEY)
    )


def rendered_messages_from_langchain(messages: Any) -> List[Dict[str, str]]:
    rendered = []
    for message in messages or []:
        if isinstance(message, dict):
            role = str(message.get("type") or message.get("role") or "")
            content = str(message.get("content") or "")
        else:
            role = message.__class__.__name__.lower().replace("message", "")
            content = str(getattr(message, "content", "") or "")
        rendered.append({"role": role, "content": content})
    return rendered


def _excerpt(text: str, start: int, end: int, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(text) else ""
    return prefix + text[left:right] + suffix


def find_unresolved_placeholders(
    rendered_messages: List[Dict[str, str]],
    *,
    node_name: str,
    metadata: Any = None,
) -> List[Dict[str, Any]]:
    metadata_keys = sorted(str(key) for key in metadata.keys()) if isinstance(metadata, dict) else []
    findings: List[Dict[str, Any]] = []
    for message in rendered_messages:
        content = message.get("content") or ""
        role = message.get("role") or ""
        for placeholder_type, pattern in _UNRESOLVED_PLACEHOLDER_PATTERNS:
            for match in pattern.finditer(content):
                findings.append(
                    {
                        "type": placeholder_type,
                        "placeholder": match.group(0),
                        "node_name": node_name,
                        "role": role,
                        "excerpt": _excerpt(content, match.start(), match.end()),
                        "metadata_keys": metadata_keys,
                    }
                )
    return findings


def build_prompt_diagnostics(
    rendered_messages: List[Dict[str, str]],
    *,
    node_name: str,
    metadata: Any = None,
) -> Dict[str, Any]:
    return {
        "unresolved_placeholders": find_unresolved_placeholders(
            rendered_messages,
            node_name=node_name,
            metadata=metadata,
        )
    }


def extract_unresolved_placeholders_from_trace(trace: Any) -> List[Dict[str, Any]]:
    if not isinstance(trace, dict):
        return []
    findings: List[Dict[str, Any]] = []
    for node_result in trace.get("node_results") or []:
        if not isinstance(node_result, dict):
            continue
        sources = [node_result]
        input_state = node_result.get("input")
        if isinstance(input_state, dict):
            sources.append(input_state)
        for source in sources:
            diagnostics = source.get("prompt_diagnostics")
            if not isinstance(diagnostics, dict):
                continue
            unresolved = diagnostics.get("unresolved_placeholders")
            if isinstance(unresolved, list):
                findings.extend(item for item in unresolved if isinstance(item, dict))
    return findings
