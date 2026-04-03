from plexus.rca_analysis import (
    MISCLASSIFICATION_CATEGORIES,
    MISCLASSIFICATION_EXCLUDED_ANALYSES,
    build_misclassification_classification_contract,
)


def test_misclassification_categories_are_locked():
    assert MISCLASSIFICATION_CATEGORIES == (
        "score_configuration_problem",
        "information_gap",
        "guideline_gap_requires_sme",
        "mechanical_malfunction",
    )


def test_contract_excludes_feedback_contradictions_analysis():
    contract = build_misclassification_classification_contract()
    excluded = contract["excluded_analyses"]
    assert "feedback_label_contradictions" in excluded
    assert "label_inconsistency_audit" in excluded
    assert tuple(excluded) == MISCLASSIFICATION_EXCLUDED_ANALYSES


def test_item_classifier_output_contract_shape():
    contract = build_misclassification_classification_contract()
    output = contract["item_classifier_output"]

    assert output["required_fields"] == [
        "primary_category",
        "rationale",
        "confidence",
        "evidence_snippets",
    ]
    assert output["field_contracts"]["primary_category"]["allowed_values"] == list(
        MISCLASSIFICATION_CATEGORIES
    )
    assert output["field_contracts"]["confidence"]["allowed_values"] == [
        "high",
        "medium",
        "low",
    ]
