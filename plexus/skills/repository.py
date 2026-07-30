"""Frontmatter-aware repository for operational agent skills."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

import yaml


_FRONTMATTER_DELIM = "---"
_SKILL_FILE_NAME = "SKILL.md"
_PLEXUS_METADATA_KEYS = (
    "tags",
    "applies_to",
    "console_supported",
    "requires_subagent",
    "allowed_modes",
    "resources",
)


class InvalidSkillKeyError(ValueError):
    """Raised when a caller asks for an unsafe or unknown skill id."""


@dataclass(frozen=True)
class Skill:
    """A single resolved skill entry."""

    metadata: dict[str, Any]
    body: str
    path: str
    resources: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return str(self.metadata.get("id", ""))


@dataclass(frozen=True)
class InvalidSkillFile:
    """A skill file that could not be indexed."""

    path: str
    reason: str


@dataclass(frozen=True)
class SkillListResult:
    """Result of a :meth:`SkillRepository.list_skills` call."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    invalid: list[InvalidSkillFile] = field(default_factory=list)


class SkillRepository:
    """Index repo-local operational skills rooted at ``skills/``.

    Only ``*/SKILL.md`` files are indexed. The stable public id is derived from
    the containing folder name, so renaming frontmatter display names does not
    break console references.
    """

    def __init__(self, root_dir: str) -> None:
        self._root = os.path.realpath(root_dir)

    @property
    def root(self) -> str:
        return self._root

    def list_skills(
        self,
        *,
        query: str | None = None,
        tags: Iterable[str] | None = None,
        mode: str | None = None,
    ) -> SkillListResult:
        """Return metadata summaries for matching skills."""

        if not os.path.isdir(self._root):
            return SkillListResult()

        normalized_query = str(query or "").strip().lower()
        requested_tags = {str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()}
        normalized_mode = str(mode or "").strip().lower()

        entries: list[dict[str, Any]] = []
        invalid: list[InvalidSkillFile] = []

        for path in self._walk_skill_files():
            skill_id = _skill_id_from_path(path)
            try:
                metadata, _body = _parse_frontmatter(path)
                normalized = _normalize_metadata(metadata, skill_id)
            except _MissingFrontmatterError as exc:
                invalid.append(InvalidSkillFile(path=path, reason=str(exc)))
                continue
            except _MalformedFrontmatterError as exc:
                invalid.append(InvalidSkillFile(path=path, reason=str(exc)))
                continue

            if not _matches_query(normalized, normalized_query):
                continue
            if requested_tags:
                skill_tags = {str(tag).lower() for tag in normalized.get("tags", [])}
                if not requested_tags.issubset(skill_tags):
                    continue
            if normalized_mode:
                allowed_modes = {
                    str(allowed_mode).strip().lower()
                    for allowed_mode in normalized.get("allowed_modes", [])
                }
                if normalized_mode not in allowed_modes:
                    continue

            entries.append(_summary_entry(normalized))

        entries.sort(key=lambda entry: entry["id"])
        return SkillListResult(entries=entries, invalid=invalid)

    def get_skill(self, skill_id: str, *, mode: str | None = None) -> Skill:
        """Return the full body for one skill id."""

        _ensure_safe_key(skill_id)

        for path in self._walk_skill_files():
            candidate_id = _skill_id_from_path(path)
            if candidate_id != skill_id:
                continue
            try:
                metadata, body = _parse_frontmatter(path)
            except (_MissingFrontmatterError, _MalformedFrontmatterError) as exc:
                raise InvalidSkillKeyError(
                    f"Skill {skill_id!r} could not be loaded: {exc}"
                ) from exc
            try:
                body = _filter_skill_body(body, mode=mode)
            except _MalformedSkillBodyError as exc:
                raise InvalidSkillKeyError(
                    f"Skill {skill_id!r} has malformed mode-filter blocks: {exc}"
                ) from exc
            return Skill(
                metadata=_normalize_metadata(metadata, candidate_id),
                body=body,
                path=path,
                resources=_resource_refs_for(path, self._root),
            )

        raise InvalidSkillKeyError(f"Unknown skill id: {skill_id!r}")

    def _walk_skill_files(self) -> Iterable[str]:
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in {"__pycache__", ".pytest_cache"}
            ]
            if _SKILL_FILE_NAME not in filenames:
                continue
            full = os.path.join(dirpath, _SKILL_FILE_NAME)
            resolved = os.path.realpath(full)
            if not resolved.startswith(self._root + os.sep):
                continue
            yield full


class _MissingFrontmatterError(RuntimeError):
    pass


class _MalformedFrontmatterError(RuntimeError):
    pass


class _MalformedSkillBodyError(RuntimeError):
    pass


def _parse_frontmatter(path: str) -> tuple[dict[str, Any], str]:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()

    if not text.lstrip().startswith(_FRONTMATTER_DELIM):
        raise _MissingFrontmatterError("file does not begin with YAML frontmatter")

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


def _skill_id_from_path(path: str) -> str:
    return os.path.basename(os.path.dirname(path))


def _normalize_metadata(metadata: dict[str, Any], skill_id: str) -> dict[str, Any]:
    normalized = dict(metadata)
    standard_metadata = metadata.get("metadata")
    if isinstance(standard_metadata, dict):
        for key in _PLEXUS_METADATA_KEYS:
            if key not in normalized and key in standard_metadata:
                normalized[key] = standard_metadata[key]

    normalized["id"] = skill_id
    normalized.setdefault("name", skill_id)
    normalized.setdefault("description", "")
    normalized.setdefault("tags", [])
    normalized.setdefault("applies_to", [])
    normalized.setdefault("console_supported", False)
    normalized.setdefault("requires_subagent", False)
    normalized.setdefault("allowed_modes", [])
    normalized.setdefault("resources", [])
    normalized["tags"] = _string_list(normalized.get("tags"))
    normalized["applies_to"] = _string_list(normalized.get("applies_to"))
    normalized["allowed_modes"] = _string_list(normalized.get("allowed_modes"))
    normalized["resources"] = _string_list(normalized.get("resources"))
    normalized["requires_subagent"] = bool(normalized.get("requires_subagent"))
    return normalized


def _summary_entry(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": metadata.get("id"),
        "name": metadata.get("name"),
        "description": metadata.get("description"),
        "tags": list(metadata.get("tags") or []),
        "applies_to": list(metadata.get("applies_to") or []),
        "console_supported": metadata.get("console_supported"),
        "requires_subagent": bool(metadata.get("requires_subagent")),
        "allowed_modes": list(metadata.get("allowed_modes") or []),
    }


def _matches_query(metadata: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        [
            str(metadata.get("id", "")),
            str(metadata.get("name", "")),
            str(metadata.get("description", "")),
            " ".join(metadata.get("tags") or []),
            " ".join(metadata.get("applies_to") or []),
        ]
    ).lower()
    return query in haystack


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _resource_refs_for(skill_path: str, root_dir: str) -> list[str]:
    skill_dir = os.path.dirname(skill_path)
    refs: list[str] = []
    for dirpath, dirnames, filenames in os.walk(skill_dir):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in {"__pycache__", ".pytest_cache"}
        ]
        for filename in filenames:
            if filename == _SKILL_FILE_NAME:
                continue
            full = os.path.join(dirpath, filename)
            resolved = os.path.realpath(full)
            if not resolved.startswith(os.path.realpath(root_dir) + os.sep):
                continue
            refs.append(os.path.relpath(resolved, root_dir))
    refs.sort()
    return refs


def _ensure_safe_key(skill_id: str) -> None:
    if not isinstance(skill_id, str) or skill_id == "":
        raise InvalidSkillKeyError(f"Invalid skill id: {skill_id!r}")

    forbidden_substrings = ("..", "/", "\\")
    for token in forbidden_substrings:
        if token in skill_id:
            raise InvalidSkillKeyError(f"Invalid skill id: {skill_id!r}")


def _filter_skill_body(body: str, *, mode: str | None = None) -> str:
    normalized_mode = (mode or "").strip().lower()
    if normalized_mode != "console":
        return body

    hidden_tags = ("console-hidden", "ide-only")
    filtered = body
    for tag in hidden_tags:
        open_pattern = re.compile(rf"<{tag}\b[^>]*>", flags=re.IGNORECASE)
        close_pattern = re.compile(rf"</{tag}>", flags=re.IGNORECASE)
        open_count = len(open_pattern.findall(filtered))
        close_count = len(close_pattern.findall(filtered))
        if open_count != close_count:
            raise _MalformedSkillBodyError(
                f"unbalanced <{tag}> blocks (open={open_count}, close={close_count})"
            )
        filtered = re.sub(
            rf"<{tag}\b[^>]*>[\s\S]*?</{tag}>",
            "",
            filtered,
            flags=re.IGNORECASE,
        )
    return filtered
