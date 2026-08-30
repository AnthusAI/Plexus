"""Recall scoring for scanner eval pipelines.

``evaluate_recall`` takes gold annotations and scanner findings as plain
Python data and returns recall/accuracy/precision metrics plus a confusion
matrix. No HTTP, no dashboard, no persistence.
"""

from __future__ import annotations

from typing import Any

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
)


def _spans_overlap(
    start_a: int,
    end_a: int,
    start_b: int,
    end_b: int,
) -> bool:
    """Inclusive span overlap, matching SourceSpanOverlapScore._spans_overlap."""
    return start_a <= end_b and start_b <= end_a


def _annotation_matches_finding(annotation: dict, finding: dict) -> bool:
    a_file = annotation.get("file_path") or annotation.get("filePath")
    f_file = finding.get("filePath") or finding.get("file_path")
    if a_file != f_file:
        return False
    a_start = int(annotation["start_line"])
    a_end = int(annotation["end_line"])
    f_start = int(finding["startLine"])
    f_end = int(finding["endLine"])
    return _spans_overlap(a_start, a_end, f_start, f_end)


def _annotation_is_detected(annotation: dict, findings: list) -> bool:
    return any(_annotation_matches_finding(annotation, finding) for finding in findings)


def evaluate_recall(
    annotations: list,
    findings: list,
) -> dict[str, Any]:
    """Score recall of ``findings`` against gold ``annotations``.

    Each annotation is a dict with ``file_path``, ``start_line``, ``end_line``,
    and ``expected.status`` (``"positive"`` or ``"negative"``). Each finding is a
    dict with ``filePath``, ``startLine``, ``endLine``.

    Returns a dict with ``accuracy``, ``recall``, ``precision``,
    ``confusion_matrix``, and denominators. Negative annotations are scored
    as "No" references; a scanner finding overlapping them is a false positive.
    """
    references: list[str] = []
    predictions: list[str] = []

    for annotation in annotations:
        status = annotation.get("expected", {}).get("status", "positive")
        reference = "Yes" if status == "positive" else "No"
        detected = _annotation_is_detected(annotation, findings)
        prediction = "Yes" if detected else "No"
        references.append(reference)
        predictions.append(prediction)

    if not references:
        return {
            "accuracy": None,
            "recall": None,
            "precision": None,
            "confusion_matrix": None,
            "total": 0,
        }

    labels = ["No", "Yes"]
    cm = confusion_matrix(references, predictions, labels=labels)
    tn, fp, fn, tp = cm.ravel()

    return {
        "accuracy": accuracy_score(references, predictions),
        "recall": recall_score(references, predictions, pos_label="Yes"),
        "precision": precision_score(references, predictions, pos_label="Yes", zero_division=0),
        "confusion_matrix": cm.tolist(),
        "total": len(references),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
    }
