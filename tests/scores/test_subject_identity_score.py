import importlib

import pytest

from plexus.scores import resolve_score_class
from plexus.scores.Score import Score
from plexus.scores.SubjectIdentityScore import SubjectIdentityScore
from plexus.scores.SubjectSpanOverlapScore import SubjectSpanOverlapScore


def _item(
    *,
    text: str = "snippet",
    subject_key: str,
    file_path: str,
    source_root: str = "/repo",
    expected_labels=None,
) -> Score.Input:
    metadata = {
        "subjectKey": subject_key,
        "filePath": file_path,
        "sourceRoot": source_root,
    }
    if expected_labels is not None:
        metadata["expectedLabels"] = expected_labels
    return Score.Input(text=text, metadata=metadata)


def _score(**kwargs) -> SubjectIdentityScore:
    defaults = {
        "name": "subject-identity-score",
        "scorecard_name": "test-scorecard",
        "score_name": "subject-identity-score",
    }
    defaults.update(kwargs)
    return SubjectIdentityScore(**defaults)


def test_yaml_class_resolves():
    """Scenario: YAML class resolves"""
    score_class = resolve_score_class("SubjectIdentityScore")
    assert score_class is SubjectIdentityScore

    score = Score._create_score_from_config(
        {"class": "SubjectIdentityScore", "name": "subject identity detector"}
    )
    assert isinstance(score, SubjectIdentityScore)

    module = importlib.import_module("plexus.scores.SubjectIdentityScore")
    module_source = importlib.import_module("inspect").getsource(module)
    assert "TactusScore" not in module_source
    assert "tactus" not in module_source.lower()


@pytest.mark.asyncio
async def test_matching_subject_key_is_yes():
    """Scenario: Matching subjectKey is Yes"""
    score = _score(
        findings=[{"subjectKey": "user:42", "filePath": "src/a.ts"}],
        files_scanned=["src/a.ts"],
    )
    result = await score.predict(
        _item(subject_key="user:42", file_path="src/a.ts"),
    )
    assert result.value == "Yes"


@pytest.mark.asyncio
async def test_matching_subject_key_ignores_span():
    """Scenario: Match is independent of span overlap"""
    score = _score(
        findings=[
            {
                "subjectKey": "user:42",
                "filePath": "src/other.ts",
                "startLine": 99,
                "endLine": 100,
            }
        ],
        files_scanned=["src/a.ts", "src/other.ts"],
    )
    result = await score.predict(
        _item(subject_key="user:42", file_path="src/a.ts"),
    )
    assert result.value == "Yes"


@pytest.mark.asyncio
async def test_non_matching_subject_key_is_no():
    """Scenario: Non-matching subjectKey is No"""
    score = _score(
        findings=[{"subjectKey": "user:99", "filePath": "src/a.ts"}],
        files_scanned=["src/a.ts"],
    )
    result = await score.predict(
        _item(subject_key="user:42", file_path="src/a.ts"),
    )
    assert result.value == "No"


@pytest.mark.asyncio
async def test_unread_file_is_skipped_not_no():
    """Unread files absent from inventory must not be scored as No."""
    score = _score(
        findings=[{"subjectKey": "user:42", "filePath": "src/read.ts"}],
        files_scanned=["src/read.ts"],
    )
    with pytest.raises(Score.SkippedScoreException, match="not in the scanned file inventory"):
        await score.predict(_item(subject_key="user:42", file_path="src/unread.ts"))


@pytest.mark.asyncio
async def test_missing_subject_key_is_skipped():
    score = _score(
        findings=[{"subjectKey": "user:42", "filePath": "src/a.ts"}],
        files_scanned=["src/a.ts"],
    )
    with pytest.raises(Score.SkippedScoreException, match="missing subjectKey"):
        await score.predict(
            Score.Input(text="snippet", metadata={"filePath": "src/a.ts"}),
        )


@pytest.mark.asyncio
async def test_expected_labels_subset_match():
    score = _score(
        findings=[
            {
                "subjectKey": "user:42",
                "filePath": "src/a.ts",
                "labels": ["pii", "email"],
            }
        ],
        files_scanned=["src/a.ts"],
    )
    result = await score.predict(
        _item(
            subject_key="user:42",
            file_path="src/a.ts",
            expected_labels=["pii"],
        ),
    )
    assert result.value == "Yes"


@pytest.mark.asyncio
async def test_expected_labels_mismatch_is_no():
    score = _score(
        findings=[
            {
                "subjectKey": "user:42",
                "filePath": "src/a.ts",
                "labels": ["pii"],
            }
        ],
        files_scanned=["src/a.ts"],
    )
    result = await score.predict(
        _item(
            subject_key="user:42",
            file_path="src/a.ts",
            expected_labels=["email"],
        ),
    )
    assert result.value == "No"


def test_subject_span_overlap_class_resolves():
    score_class = resolve_score_class("SubjectSpanOverlapScore")
    assert score_class is SubjectSpanOverlapScore


@pytest.mark.asyncio
async def test_subject_span_overlap_requires_both():
    score = SubjectSpanOverlapScore(
        name="subject-span-overlap",
        scorecard_name="test-scorecard",
        score_name="subject-span-overlap",
        findings=[
            {
                "subjectKey": "user:42",
                "filePath": "src/a.ts",
                "startLine": 20,
                "endLine": 22,
            }
        ],
        files_scanned=["src/a.ts"],
    )
    item = Score.Input(
        text="snippet",
        metadata={
            "subjectKey": "user:42",
            "filePath": "src/a.ts",
            "startLine": 10,
            "endLine": 12,
            "sourceRoot": "/repo",
        },
    )
    result = await score.predict(item)
    assert result.value == "No"

    score_yes = SubjectSpanOverlapScore(
        name="subject-span-overlap",
        scorecard_name="test-scorecard",
        score_name="subject-span-overlap",
        findings=[
            {
                "subjectKey": "user:42",
                "filePath": "src/a.ts",
                "startLine": 11,
                "endLine": 13,
            }
        ],
        files_scanned=["src/a.ts"],
    )
    result_yes = await score_yes.predict(item)
    assert result_yes.value == "Yes"
