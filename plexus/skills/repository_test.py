"""Unit tests for the operational skill repository."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from plexus.skills.repository import InvalidSkillKeyError, SkillRepository


def _write_skill(
    root: Path,
    skill_id: str,
    *,
    name: str,
    description: str,
    tags: list[str] | None = None,
    applies_to: list[str] | None = None,
    console_supported: bool | str = True,
    requires_subagent: bool = False,
    allowed_modes: list[str] | None = None,
    body: str = "# Body\n",
) -> Path:
    path = root / skill_id / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "name": name,
        "description": description,
        "tags": tags or ["test"],
        "applies_to": applies_to or ["test workflow"],
        "console_supported": console_supported,
        "requires_subagent": requires_subagent,
        "allowed_modes": allowed_modes or ["planning", "execution"],
        "resources": [],
    }
    path.write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body,
        encoding="utf-8",
    )
    return path


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw, _ = text.split("---", 2)
    parsed = yaml.safe_load(raw) or {}
    assert isinstance(parsed, dict)
    return parsed


def test_list_returns_metadata_entries_sorted_by_stable_folder_id(tmp_path) -> None:
    _write_skill(tmp_path, "z-last", name="A Display Name", description="last")
    _write_skill(tmp_path, "a-first", name="Renamed Display", description="first")

    repo = SkillRepository(str(tmp_path))
    result = repo.list_skills()

    assert [entry["id"] for entry in result.entries] == ["a-first", "z-last"]
    assert result.entries[0]["name"] == "Renamed Display"
    for entry in result.entries:
        assert {
            "id",
            "name",
            "description",
            "tags",
            "applies_to",
            "console_supported",
            "requires_subagent",
            "allowed_modes",
        } <= set(entry)
        assert "content" not in entry and "body" not in entry


def test_list_filters_by_query_tags_and_mode(tmp_path) -> None:
    _write_skill(
        tmp_path,
        "score-code-editor",
        name="Score Code Editor",
        description="Edit score Tactus code",
        tags=["score-workflow", "code"],
        applies_to=["score code editing"],
        allowed_modes=["planning", "execution"],
    )
    _write_skill(
        tmp_path,
        "client-redaction",
        name="Client Redaction",
        description="Repository scan",
        tags=["repository-hygiene"],
        applies_to=["redaction"],
        console_supported=False,
        allowed_modes=["ide"],
    )

    repo = SkillRepository(str(tmp_path))
    result = repo.list_skills(query="tactus", tags=["score-workflow"], mode="planning")

    assert [entry["id"] for entry in result.entries] == ["score-code-editor"]


def test_standard_nested_metadata_is_available_to_plexus_filters(tmp_path) -> None:
    path = tmp_path / "software-delivery-team" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\n"
        "name: software-delivery-team\n"
        "description: Coordinate a delivery team\n"
        "metadata:\n"
        "  tags: [software-delivery, multi-agent]\n"
        "  applies_to: [delivery coordination]\n"
        "  console_supported: false\n"
        "  requires_subagent: true\n"
        "  allowed_modes: [ide]\n"
        "  resources: [artifacts.md]\n"
        "---\n"
        "# Software Delivery Team\n",
        encoding="utf-8",
    )

    repo = SkillRepository(str(tmp_path))
    result = repo.list_skills(tags=["multi-agent"], mode="ide")

    assert [entry["id"] for entry in result.entries] == ["software-delivery-team"]
    assert result.entries[0]["requires_subagent"] is True
    assert result.entries[0]["console_supported"] is False
    skill = repo.get_skill("software-delivery-team", mode="ide")
    assert skill.metadata["resources"] == ["artifacts.md"]


def test_legacy_top_level_metadata_takes_precedence_over_nested_metadata(tmp_path) -> None:
    path = tmp_path / "portable-skill" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\n"
        "name: portable-skill\n"
        "description: Portable skill\n"
        "tags: [legacy]\n"
        "requires_subagent: false\n"
        "metadata:\n"
        "  tags: [nested]\n"
        "  requires_subagent: true\n"
        "---\n"
        "# Portable Skill\n",
        encoding="utf-8",
    )

    repo = SkillRepository(str(tmp_path))
    skill = repo.get_skill("portable-skill")

    assert skill.metadata["tags"] == ["legacy"]
    assert skill.metadata["requires_subagent"] is False


def test_get_skill_returns_body_metadata_and_resource_refs(tmp_path) -> None:
    skill_path = _write_skill(
        tmp_path,
        "score-code-editor",
        name="Score Code Editor",
        description="Edit score code",
        body="# Score Code Editor\nUse score.edit.\n",
    )
    helper_path = skill_path.parent / "references" / "extra.md"
    helper_path.parent.mkdir()
    helper_path.write_text("# extra\n", encoding="utf-8")

    repo = SkillRepository(str(tmp_path))
    skill = repo.get_skill("score-code-editor")

    assert skill.id == "score-code-editor"
    assert skill.metadata["id"] == "score-code-editor"
    assert skill.body.startswith("# Score Code Editor")
    assert skill.resources == ["score-code-editor/references/extra.md"]


def test_get_skill_console_mode_filters_ide_only_and_console_hidden_blocks(tmp_path) -> None:
    _write_skill(
        tmp_path,
        "score-code-editor",
        name="Score Code Editor",
        description="Edit score code",
        body=(
            "# Score Code Editor\n"
            "<ide-only>\nIDE instructions\n</ide-only>\n"
            "<console-hidden>\nHidden in console\n</console-hidden>\n"
            "Visible in console\n"
        ),
    )

    repo = SkillRepository(str(tmp_path))
    skill = repo.get_skill("score-code-editor", mode="console")

    assert "IDE instructions" not in skill.body
    assert "Hidden in console" not in skill.body
    assert "Visible in console" in skill.body


def test_get_skill_rejects_unbalanced_mode_filter_blocks(tmp_path) -> None:
    _write_skill(
        tmp_path,
        "guidelines",
        name="Guidelines",
        description="Guidelines instructions",
        body="# Guidelines\n<ide-only>\nMissing closing tag\n",
    )

    repo = SkillRepository(str(tmp_path))

    with pytest.raises(InvalidSkillKeyError, match="malformed mode-filter blocks"):
        repo.get_skill("guidelines", mode="console")


def test_get_skill_rejects_unsafe_ids(tmp_path) -> None:
    repo = SkillRepository(str(tmp_path))

    for skill_id in ("", "../escape", "/absolute", "nested/path", "nested\\path"):
        with pytest.raises(InvalidSkillKeyError):
            repo.get_skill(skill_id)


def test_unknown_id_raises_invalid_skill_key(tmp_path) -> None:
    _write_skill(tmp_path, "score-code-editor", name="Score Code Editor", description="Edit")
    repo = SkillRepository(str(tmp_path))

    with pytest.raises(InvalidSkillKeyError):
        repo.get_skill("missing-skill")


def test_list_reports_missing_frontmatter_as_invalid(tmp_path) -> None:
    _write_skill(tmp_path, "valid-skill", name="Valid", description="Valid")
    bad_path = tmp_path / "bad-skill" / "SKILL.md"
    bad_path.parent.mkdir()
    bad_path.write_text("# Missing frontmatter\n", encoding="utf-8")

    repo = SkillRepository(str(tmp_path))
    result = repo.list_skills()

    assert [entry["id"] for entry in result.entries] == ["valid-skill"]
    assert any("bad-skill" in invalid.path for invalid in result.invalid)
    assert any("frontmatter" in invalid.reason for invalid in result.invalid)


def test_list_returns_empty_for_missing_root(tmp_path) -> None:
    repo = SkillRepository(str(tmp_path / "missing"))

    result = repo.list_skills()

    assert result.entries == []
    assert result.invalid == []


def test_real_repo_skills_have_explicit_console_support_classification() -> None:
    skills_root = Path(__file__).resolve().parents[2] / "skills"
    repo = SkillRepository(str(skills_root))
    result = repo.list_skills()

    ids = {entry["id"] for entry in result.entries}
    assert {
        "software-delivery-team",
        "product-owner",
        "coding-agent",
        "outside-consultant",
        "score-code-editor",
        "score-setup",
        "guidelines",
        "score-optimizer",
        "client-redaction",
    } <= ids
    assert result.invalid == []

    entries_by_id = {entry["id"]: entry for entry in result.entries}
    delivery_role_requirements = {
        "software-delivery-team": True,
        "product-owner": True,
        "coding-agent": False,
        "outside-consultant": False,
    }
    for skill_id, requires_subagent in delivery_role_requirements.items():
        entry = entries_by_id[skill_id]
        assert entry["console_supported"] is False
        assert entry["requires_subagent"] is requires_subagent
        assert entry["allowed_modes"] == ["ide"]

    required_fields = {
        "tags",
        "applies_to",
        "console_supported",
        "requires_subagent",
        "allowed_modes",
    }
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        frontmatter = _read_frontmatter(skill_file)
        nested_metadata = frontmatter.get("metadata")
        classification = dict(nested_metadata) if isinstance(nested_metadata, dict) else {}
        classification.update(
            {key: frontmatter[key] for key in required_fields if key in frontmatter}
        )
        missing = required_fields - set(classification)
        assert not missing, f"{skill_file} missing explicit fields: {sorted(missing)}"

    delivery_skill = repo.get_skill("software-delivery-team", mode="ide")
    assert delivery_skill.metadata["console_supported"] is False
    assert delivery_skill.metadata["requires_subagent"] is True
    assert "software-delivery-team/artifacts.md" in delivery_skill.resources
    assert (
        "software-delivery-team/references/host-adapters.md"
        in delivery_skill.resources
    )
