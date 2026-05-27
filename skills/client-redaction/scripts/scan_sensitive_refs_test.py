import re
from pathlib import Path

from scan_sensitive_refs import (
    DEFAULT_EXCLUDES,
    compile_literal_terms,
    is_excluded,
    load_terms,
    scan_text,
)


def test_load_terms_deduplicates_case_insensitively(tmp_path: Path) -> None:
    terms_file = tmp_path / "terms.txt"
    terms_file.write_text("NonSponsorCo\n# comment\nnonsponsorco\nPrivateProject\n", encoding="utf-8")

    assert load_terms(["NONSPONSORCO", "PrivateTerm"], terms_file) == [
        "NONSPONSORCO",
        "PrivateTerm",
        "PrivateProject",
    ]


def test_compile_literal_terms_skips_approved_sponsors() -> None:
    patterns = compile_literal_terms(["Call Criteria", "Capacity", "NonSponsorCo"], ["Call Criteria", "Capacity"])

    assert [term for term, _ in patterns] == ["NonSponsorCo"]


def test_scan_text_finds_literal_terms_and_client_work_cues() -> None:
    term_patterns = compile_literal_terms(["NonSponsorCo"], [])
    findings = scan_text(
        "notes.md",
        "NonSponsorCo scorecard\ncustomer-specific workflow\n",
        term_patterns,
        [],
    )
    cue_findings = scan_text(
        "notes.md",
        "customer-specific workflow\n",
        [],
        [(r"\bcustomer[- ]specific\b", re.compile(r"\bcustomer[- ]specific\b"))],
    )

    assert findings[0].kind == "literal-term"
    assert findings[0].line == 1
    assert cue_findings[0].kind == "client-work-cue"


def test_is_excluded_uses_path_prefixes() -> None:
    assert is_excluded(Path("skills/client-redaction/SKILL.md"), ["skills/client-redaction/"])
    assert is_excluded(Path("project/issues/plx-example.json"), ["project/"])
    assert not is_excluded(Path("skills/score-optimizer/SKILL.md"), ["skills/client-redaction/"])


def test_default_excludes_skip_kanbus_storage() -> None:
    assert "project/" in DEFAULT_EXCLUDES
