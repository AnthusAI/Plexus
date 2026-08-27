import importlib

import pytest

from plexus.scores import resolve_score_class
from plexus.scores.Score import Score
from plexus.scores.SourceSpanOverlapScore import SourceSpanOverlapScore, _spans_overlap


def _item(
    *,
    text: str = "snippet",
    file_path: str,
    start_line: int,
    end_line: int,
    source_root: str = "/repo",
) -> Score.Input:
    return Score.Input(
        text=text,
        metadata={
            "filePath": file_path,
            "startLine": start_line,
            "endLine": end_line,
            "sourceRoot": source_root,
        },
    )


def _score(**kwargs) -> SourceSpanOverlapScore:
    defaults = {
        "name": "overlap-score",
        "scorecard_name": "test-scorecard",
        "score_name": "overlap-score",
    }
    defaults.update(kwargs)
    return SourceSpanOverlapScore(**defaults)


def test_spans_overlap_inclusive():
    assert _spans_overlap(10, 12, 12, 14)
    assert _spans_overlap(12, 14, 10, 12)
    assert not _spans_overlap(10, 12, 13, 15)


def test_yaml_class_resolves():
    """Scenario: YAML class resolves"""
    score_class = resolve_score_class("SourceSpanOverlapScore")
    assert score_class is SourceSpanOverlapScore

    score = Score._create_score_from_config(
        {"class": "SourceSpanOverlapScore", "name": "overlap detector"}
    )
    assert isinstance(score, SourceSpanOverlapScore)

    module = importlib.import_module("plexus.scores.SourceSpanOverlapScore")
    module_source = importlib.import_module("inspect").getsource(module)
    assert "TactusScore" not in module_source
    assert "tactus" not in module_source.lower()


@pytest.mark.asyncio
async def test_overlapping_finding_is_yes():
    """Scenario: Overlapping finding is Yes"""
    score = _score(
        findings=[{"filePath": "src/a.ts", "startLine": 11, "endLine": 13}],
        files_scanned=["src/a.ts"],
    )
    result = await score.predict(_item(file_path="src/a.ts", start_line=10, end_line=12))
    assert result.value == "Yes"


@pytest.mark.asyncio
async def test_no_overlapping_finding_is_no():
    """Scenario: No overlapping finding is No"""
    score = _score(
        findings=[{"filePath": "src/a.ts", "startLine": 20, "endLine": 22}],
        files_scanned=["src/a.ts"],
    )
    result = await score.predict(_item(file_path="src/a.ts", start_line=10, end_line=12))
    assert result.value == "No"


@pytest.mark.asyncio
async def test_wrong_file_is_not_a_hit():
    """Scenario: Wrong file is not a hit"""
    score = _score(
        findings=[{"filePath": "src/b.ts", "startLine": 10, "endLine": 12}],
        files_scanned=["src/a.ts", "src/b.ts"],
    )
    result = await score.predict(_item(file_path="src/a.ts", start_line=10, end_line=12))
    assert result.value == "No"


@pytest.mark.asyncio
async def test_snippet_text_is_not_the_scan_input():
    """Scenario: Snippet text is not the scan input"""
    score = _score(
        findings=[{"filePath": "src/a.ts", "startLine": 50, "endLine": 52}],
        files_scanned=["src/a.ts"],
    )
    result = await score.predict(
        _item(
            text="superSecretKeyword appears here but span metadata drives scoring",
            file_path="src/a.ts",
            start_line=10,
            end_line=12,
        )
    )
    assert result.value == "No"


@pytest.mark.asyncio
async def test_unread_file_is_skipped_not_no():
    """Unread files absent from inventory must not be scored as No."""
    score = _score(
        findings=[{"filePath": "src/read.ts", "startLine": 1, "endLine": 1}],
        files_scanned=["src/read.ts"],
    )
    with pytest.raises(Score.SkippedScoreException, match="not in the scanned file inventory"):
        await score.predict(_item(file_path="src/unread.ts", start_line=1, end_line=1))


@pytest.mark.asyncio
async def test_findings_only_inventory_skips_unread_file():
    score = _score(
        findings=[{"filePath": "src/read.ts", "startLine": 1, "endLine": 1}],
    )
    with pytest.raises(Score.SkippedScoreException, match="not in the scanned file inventory"):
        await score.predict(_item(file_path="src/unread.ts", start_line=1, end_line=1))


@pytest.mark.asyncio
async def test_findings_only_inventory_no_overlap_on_same_file_is_no():
    score = _score(
        findings=[{"filePath": "src/a.ts", "startLine": 20, "endLine": 22}],
    )
    result = await score.predict(_item(file_path="src/a.ts", start_line=10, end_line=12))
    assert result.value == "No"


@pytest.mark.asyncio
async def test_findings_cache_reused_for_same_source_root():
    score = _score(
        findings=[{"filePath": "src/a.ts", "startLine": 10, "endLine": 12}],
        files_scanned=["src/a.ts"],
    )
    await score.predict(_item(file_path="src/a.ts", start_line=10, end_line=12))
    assert "/repo" in score._cache

    score._injected_findings = []
    result = await score.predict(_item(file_path="src/a.ts", start_line=10, end_line=12))
    assert result.value == "Yes"


@pytest.mark.asyncio
async def test_findings_command_parses_json(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    script = tmp_path / "emit_findings.py"
    script.write_text(
        "import json, sys\n"
        "print(json.dumps({"
        "'findings': [{'filePath': 'src/a.ts', 'startLine': 10, 'endLine': 12}],"
        "'filesScanned': ['src/a.ts']"
        "}))\n"
    )

    command = f"python3 {script} {{root}}"
    score = _score(findings_command=command, source_root=str(root))
    result = await score.predict(
        _item(file_path="src/a.ts", start_line=10, end_line=12, source_root=str(root)),
    )
    assert result.value == "Yes"
