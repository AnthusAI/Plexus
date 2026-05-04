"""Plexus agent documentation knowledge base.

The :mod:`plexus.documentation` package owns the runtime view of the
agent-facing documentation tree. Markdown files under
``documentation/agent/`` carry YAML frontmatter that this package parses
into a structured index used by :mod:`MCP.tools.tactus_runtime.execute`
to back ``plexus.docs.list`` and ``plexus.docs.get``.
"""

from plexus.documentation.repository import (
    Document,
    DocumentationRepository,
    InvalidDocumentationKeyError,
    InvalidDocumentationFile,
    ListResult,
)

__all__ = [
    "Document",
    "DocumentationRepository",
    "InvalidDocumentationKeyError",
    "InvalidDocumentationFile",
    "ListResult",
]
