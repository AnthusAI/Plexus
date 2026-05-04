"""Frontmatter-aware documentation repository.

The repository exposes the agent-facing documentation tree as an indexed
collection of structured entries. Each markdown file in the tree is
expected to begin with a YAML frontmatter block; files without
frontmatter are surfaced as invalid (they are not silently dropped, so
authors notice).

The repository is the single source of truth that the Tactus runtime
``plexus.docs.list`` and ``plexus.docs.get`` calls delegate to. There is
one canonical lookup path: by the ``id`` declared in frontmatter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable

import yaml


_FRONTMATTER_DELIM = "---"

# Stems that are intentionally excluded from the agent-facing index.
# README.md is a human-facing folder index; _index.md is a namespace
# landing page that is reachable via its declared id but should not show
# up under the namespace listing as a regular doc.
_EXCLUDED_STEMS_LOWER = frozenset({"readme", "_index"})


class InvalidDocumentationKeyError(ValueError):
    """Raised when a caller asks for a doc id that is unsafe or unknown."""


@dataclass(frozen=True)
class Document:
    """A single resolved documentation entry."""

    metadata: dict[str, Any]
    body: str
    path: str

    @property
    def id(self) -> str:
        return str(self.metadata.get("id", ""))


@dataclass(frozen=True)
class InvalidDocumentationFile:
    """A markdown file that could not be indexed."""

    path: str
    reason: str


@dataclass(frozen=True)
class ListResult:
    """Result of a :meth:`DocumentationRepository.list_docs` call."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    invalid: list[InvalidDocumentationFile] = field(default_factory=list)


class DocumentationRepository:
    """Index a documentation tree rooted at ``root_dir``.

    The repository is intentionally stateless beyond the root path; each
    ``list_docs`` and ``get_doc`` call walks the tree fresh so updates
    on disk are immediately visible. The tree is small enough that this
    is fine in practice, and it keeps test isolation simple.
    """

    def __init__(self, root_dir: str) -> None:
        self._root = os.path.realpath(root_dir)

    @property
    def root(self) -> str:
        return self._root

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_docs(self, *, namespace: str | None = None) -> ListResult:
        """Return metadata summaries for every indexable doc.

        ``README.md`` and ``_index.md`` files are excluded from the
        listing. Files without frontmatter are reported under
        :attr:`ListResult.invalid` instead of raising, so a single bad
        file does not break the whole index.
        """

        if not os.path.isdir(self._root):
            return ListResult()

        entries: list[dict[str, Any]] = []
        invalid: list[InvalidDocumentationFile] = []

        for path in self._walk_markdown():
            stem = os.path.splitext(os.path.basename(path))[0]
            if stem.lower() in _EXCLUDED_STEMS_LOWER:
                continue
            try:
                metadata, _body = _parse_frontmatter(path)
            except _MissingFrontmatterError as exc:
                invalid.append(InvalidDocumentationFile(path=path, reason=str(exc)))
                continue
            except _MalformedFrontmatterError as exc:
                invalid.append(InvalidDocumentationFile(path=path, reason=str(exc)))
                continue

            doc_id = metadata.get("id")
            if not isinstance(doc_id, str) or not doc_id:
                invalid.append(
                    InvalidDocumentationFile(
                        path=path,
                        reason="frontmatter missing required string 'id'",
                    )
                )
                continue

            entry = _summary_entry(metadata)
            if namespace is not None and entry.get("namespace") != namespace:
                continue
            entries.append(entry)

        entries.sort(key=lambda e: e["id"])
        return ListResult(entries=entries, invalid=invalid)

    def get_doc(self, doc_id: str) -> Document:
        """Return the full document for ``doc_id``.

        Raises :class:`InvalidDocumentationKeyError` for unsafe keys or
        for ids that do not resolve to an indexed file.
        """

        _ensure_safe_key(doc_id)

        for path in self._walk_markdown():
            stem = os.path.splitext(os.path.basename(path))[0]
            if stem.lower() in _EXCLUDED_STEMS_LOWER and stem != "_index":
                continue
            try:
                metadata, body = _parse_frontmatter(path)
            except (_MissingFrontmatterError, _MalformedFrontmatterError):
                continue

            if metadata.get("id") == doc_id:
                return Document(metadata=metadata, body=body, path=path)

        raise InvalidDocumentationKeyError(f"Unknown documentation id: {doc_id!r}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _walk_markdown(self) -> Iterable[str]:
        for dirpath, _dirnames, filenames in os.walk(self._root):
            for name in filenames:
                if not name.lower().endswith(".md"):
                    continue
                full = os.path.join(dirpath, name)
                resolved = os.path.realpath(full)
                if not resolved.startswith(self._root + os.sep) and resolved != self._root:
                    # Defence in depth against symlinks pointing outside
                    # the documentation root.
                    continue
                yield full


# ----------------------------------------------------------------------
# Frontmatter parsing
# ----------------------------------------------------------------------


class _MissingFrontmatterError(RuntimeError):
    pass


class _MalformedFrontmatterError(RuntimeError):
    pass


def _parse_frontmatter(path: str) -> tuple[dict[str, Any], str]:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()

    if not text.lstrip().startswith(_FRONTMATTER_DELIM):
        raise _MissingFrontmatterError("file does not begin with YAML frontmatter")

    # Skip leading blank lines so authors can leave a blank line above
    # ``---`` without breaking parsing.
    stripped = text.lstrip("\n")
    if not stripped.startswith(_FRONTMATTER_DELIM):
        raise _MissingFrontmatterError("file does not begin with YAML frontmatter")

    after_open = stripped[len(_FRONTMATTER_DELIM):]
    if not after_open.startswith("\n"):
        raise _MalformedFrontmatterError("frontmatter opening delimiter must be followed by a newline")

    after_open = after_open[1:]
    close_index = after_open.find("\n" + _FRONTMATTER_DELIM)
    if close_index < 0:
        raise _MalformedFrontmatterError("frontmatter closing delimiter not found")

    raw_yaml = after_open[:close_index]
    body_start = close_index + len("\n" + _FRONTMATTER_DELIM)
    body = after_open[body_start:]
    if body.startswith("\n"):
        body = body[1:]

    try:
        parsed = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise _MalformedFrontmatterError(f"frontmatter YAML is invalid: {exc}") from exc

    if not isinstance(parsed, dict):
        raise _MalformedFrontmatterError("frontmatter must be a YAML mapping")

    return parsed, body


def _summary_entry(metadata: dict[str, Any]) -> dict[str, Any]:
    """Build the small metadata-only dict returned by :meth:`list_docs`."""

    return {
        "id": metadata.get("id"),
        "title": metadata.get("title"),
        "summary": metadata.get("summary"),
        "namespace": metadata.get("namespace"),
        "status": metadata.get("status"),
        "disclosure": metadata.get("disclosure"),
        "tags": list(metadata.get("tags") or []),
        "related": list(metadata.get("related") or []),
    }


def _ensure_safe_key(doc_id: str) -> None:
    if not isinstance(doc_id, str) or doc_id == "":
        raise InvalidDocumentationKeyError(f"Invalid documentation id: {doc_id!r}")

    forbidden_substrings = ("..", "/", "\\")
    for token in forbidden_substrings:
        if token in doc_id:
            raise InvalidDocumentationKeyError(
                f"Invalid documentation id: {doc_id!r} (path traversal not allowed)"
            )

    if doc_id.startswith("."):
        raise InvalidDocumentationKeyError(
            f"Invalid documentation id: {doc_id!r} (must not start with a dot)"
        )
