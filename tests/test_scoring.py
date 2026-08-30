"""Tests for plexus.scoring.evaluate_recall."""

import pytest

from plexus.scoring import evaluate_recall


def _annotation(file_path, start, end, status="positive"):
    return {
        "file_path": file_path,
        "start_line": start,
        "end_line": end,
        "expected": {"status": status, "labels": []},
    }


def _finding(file_path, start, end):
    return {"filePath": file_path, "startLine": start, "endLine": end}


def test_perfect_recall_when_all_positives_detected():
    annotations = [
        _annotation("app.py", 10, 10),
        _annotation("app.py", 20, 20),
    ]
    findings = [
        _finding("app.py", 10, 10),
        _finding("app.py", 20, 20),
    ]
    report = evaluate_recall(annotations, findings)
    assert report["accuracy"] == 1.0
    assert report["recall"] == 1.0
    assert report["precision"] == 1.0
    assert report["true_positives"] == 2
    assert report["false_positives"] == 0
    assert report["false_negatives"] == 0


def test_missed_positive_lowers_recall():
    annotations = [
        _annotation("app.py", 10, 10),
        _annotation("app.py", 20, 20),
    ]
    findings = [_finding("app.py", 10, 10)]
    report = evaluate_recall(annotations, findings)
    assert report["recall"] == 0.5
    assert report["true_positives"] == 1
    assert report["false_negatives"] == 1


def test_negative_annotation_with_overlap_is_false_positive():
    annotations = [
        _annotation("app.py", 10, 10, status="negative"),
    ]
    findings = [_finding("app.py", 10, 10)]
    report = evaluate_recall(annotations, findings)
    assert report["false_positives"] == 1
    assert report["true_negatives"] == 0
    assert report["precision"] == 0.0


def test_clean_negative_passes():
    annotations = [
        _annotation("app.py", 10, 10, status="negative"),
    ]
    findings = []
    report = evaluate_recall(annotations, findings)
    assert report["accuracy"] == 1.0
    assert report["true_negatives"] == 1
    assert report["false_positives"] == 0


def test_empty_annotations_returns_none_metrics():
    report = evaluate_recall([], [])
    assert report["accuracy"] is None
    assert report["recall"] is None
    assert report["total"] == 0


def test_span_overlap_is_inclusive():
    annotations = [_annotation("app.py", 5, 10)]
    findings = [_finding("app.py", 10, 10)]
    report = evaluate_recall(annotations, findings)
    assert report["true_positives"] == 1


def test_different_files_do_not_match():
    annotations = [_annotation("app.py", 10, 10)]
    findings = [_finding("other.py", 10, 10)]
    report = evaluate_recall(annotations, findings)
    assert report["true_positives"] == 0
    assert report["false_negatives"] == 1
