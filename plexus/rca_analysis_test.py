from plexus.rca_analysis import (
    MISCLASSIFICATION_CATEGORIES,
    MISCLASSIFICATION_EXCLUDED_ANALYSES,
    MISCLASSIFICATION_LABEL_PROVENANCE_SOURCES,
    build_misclassification_analysis_summary,
    build_misclassification_classification_contract,
    build_misclassification_item_context,
    classify_misclassification_item,
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


def test_item_context_contract_and_provenance_sources():
    contract = build_misclassification_classification_contract()
    context_contract = contract["item_context_contract"]

    assert "required_sections" in context_contract
    assert "label_provenance_sources" in context_contract
    assert tuple(context_contract["label_provenance_sources"]) == MISCLASSIFICATION_LABEL_PROVENANCE_SOURCES
    assert "persisted_audit_metadata_required" in context_contract
    assert "identifiers.feedback_item_id" in context_contract["persisted_audit_metadata_required"]


def test_build_misclassification_item_context_includes_availability_flags():
    context = build_misclassification_item_context(
        feedback_item_id="fb-1",
        item_id="item-1",
        score_id="score-1",
        scorecard_id="scorecard-1",
        score_version_id="version-1",
        predicted_value="No",
        correct_value="Yes",
        score_explanation="Prediction explanation",
        edit_comment="Reviewer heard a missing phrase in audio.",
        initial_comment="Initial comment",
        final_comment="Final comment",
        score_guidelines_text="Guidelines text",
        score_yaml_configuration="name: Score",
        scorecard_guidance_text="Scorecard guidance",
        transcript_text="Transcript text",
        metadata_snapshot='{"call_type":"inbound"}',
        label_provenance_source="feedback_final_answer_value",
    )

    assert context["identifiers"]["feedback_item_id"] == "fb-1"
    assert context["prediction"]["predicted_value"] == "No"
    assert context["label_provenance"]["source"] == "feedback_final_answer_value"
    assert context["label_provenance"]["feedback_context_present"] is True
    assert context["source_availability"]["has_transcript_text"] is True
    assert context["source_availability"]["has_metadata_snapshot"] is True


def test_build_misclassification_item_context_rejects_unknown_provenance_source():
    try:
        build_misclassification_item_context(
            feedback_item_id="fb-1",
            item_id="item-1",
            score_id="score-1",
            scorecard_id="scorecard-1",
            score_version_id="version-1",
            predicted_value="No",
            correct_value="Yes",
            score_explanation="",
            edit_comment="",
            initial_comment="",
            final_comment="",
            score_guidelines_text="",
            score_yaml_configuration="",
            scorecard_guidance_text="",
            transcript_text="",
            metadata_snapshot="",
            label_provenance_source="not_allowed",
        )
        assert False, "Expected ValueError for unsupported label provenance source"
    except ValueError as exc:
        assert "Unsupported label_provenance_source" in str(exc)


def _base_item_context():
    return build_misclassification_item_context(
        feedback_item_id="fb-1",
        item_id="item-1",
        score_id="score-1",
        scorecard_id="scorecard-1",
        score_version_id="version-1",
        predicted_value="No",
        correct_value="Yes",
        score_explanation="Model reasoning here",
        edit_comment="",
        initial_comment="",
        final_comment="",
        score_guidelines_text="Guidelines text",
        score_yaml_configuration="name: Score",
        scorecard_guidance_text="Scorecard guidance",
        transcript_text="Transcript available",
        metadata_snapshot='{"call_type":"inbound"}',
        label_provenance_source="feedback_final_answer_value",
    )


def test_classifier_detects_score_configuration_problem_default():
    context = _base_item_context()
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "score_configuration_problem"
    assert "evidence_snippets" in result


def test_classifier_detects_information_gap_from_feedback_signal():
    context = _base_item_context()
    context["feedback_context"]["edit_comment_excerpt"] = "Critical phrase not in transcript."
    context["label_provenance"]["feedback_context_present"] = True
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "information_gap"


def test_classifier_detects_guideline_gap_from_ambiguity_signal():
    context = _base_item_context()
    context["feedback_context"]["edit_comment_excerpt"] = "Guideline is ambiguous here and needs SME clarification."
    context["label_provenance"]["feedback_context_present"] = True
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "guideline_gap_requires_sme"


def test_classifier_detects_mechanical_malfunction_from_execution_error():
    context = _base_item_context()
    context["prediction"]["score_explanation_excerpt"] = "Execution error: timeout while running classifier."
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "mechanical_malfunction"


def test_misclassification_analysis_summary_contains_totals_and_red_flags():
    context_1 = _base_item_context()
    context_1["prediction"]["predicted_value"] = "No"
    context_1["source_availability"]["has_transcript_text"] = False
    class_1 = classify_misclassification_item(context_1)

    context_2 = _base_item_context()
    context_2["prediction"]["predicted_value"] = "No"
    context_2["prediction"]["score_explanation_excerpt"] = "Execution error: timeout."
    class_2 = classify_misclassification_item(context_2)

    context_3 = _base_item_context()
    context_3["prediction"]["predicted_value"] = "No"
    class_3 = classify_misclassification_item(context_3)

    topics = [{
        "topic_id": 1,
        "exemplars": [
            {
                "misclassification_item_context": context_1,
                "misclassification_classification": class_1,
            },
            {
                "misclassification_item_context": context_2,
                "misclassification_classification": class_2,
            },
            {
                "misclassification_item_context": context_3,
                "misclassification_classification": class_3,
            },
        ],
    }]

    summary = build_misclassification_analysis_summary(topics)
    assert summary["overall_assessment"]["total_items"] == 3
    assert "category_totals" in summary
    assert "evaluation_red_flags" in summary
    assert any(flag["flag"] == "prediction_mode_collapse" for flag in summary["evaluation_red_flags"])
