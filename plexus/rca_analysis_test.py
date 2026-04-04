from plexus.rca_analysis import (
    MECHANICAL_SUBTYPES,
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
    assert output["field_contracts"]["mechanical_subtype"]["allowed_values"] == list(
        MECHANICAL_SUBTYPES
    )


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
        resolved_final_classes=["Yes", "No"],
        class_resolution_source="graph[-1].LogicalClassifier.code",
    )

    assert context["identifiers"]["feedback_item_id"] == "fb-1"
    assert context["prediction"]["predicted_value"] == "No"
    assert context["label_provenance"]["source"] == "feedback_final_answer_value"
    assert context["label_provenance"]["feedback_context_present"] is True
    assert context["source_availability"]["has_transcript_text"] is True
    assert context["source_availability"]["has_metadata_snapshot"] is True
    assert context["score_context"]["resolved_final_classes"] == ["Yes", "No"]
    assert context["score_context"]["class_resolution_source"] == "graph[-1].LogicalClassifier.code"


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
        resolved_final_classes=["Yes", "No"],
        class_resolution_source="graph[-1].LogicalClassifier.code",
    )


def test_classifier_detects_score_configuration_problem_default():
    context = _base_item_context()
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "score_configuration_problem"
    assert result["mechanical_subtype"] is None


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


def test_classifier_detects_mechanical_runtime_error_with_subtype():
    context = _base_item_context()
    context["prediction"]["score_explanation_excerpt"] = "Runtime error: timeout while running classifier."
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "runtime_error"
    assert "timeout" in (result["mechanical_details"] or "")


def test_classifier_does_not_treat_failed_requirements_text_as_mechanical():
    context = _base_item_context()
    context["prediction"]["score_explanation_excerpt"] = "The customer failed requirements for eligibility."
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "score_configuration_problem"


def test_classifier_detects_mechanical_parse_or_schema_error():
    context = _base_item_context()
    context["prediction"]["score_explanation_excerpt"] = "Parser error: schema validation failed to parse model output."
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "parse_or_schema_error"


def test_classifier_detects_missing_labels_as_mechanical():
    context = _base_item_context()
    context["prediction"]["predicted_value"] = ""
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "missing_labels"


def test_classifier_detects_invalid_output_class_as_mechanical():
    context = _base_item_context()
    context["prediction"]["predicted_value"] = "Maybe"
    result = classify_misclassification_item(context)
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "invalid_output_class"


def test_misclassification_analysis_summary_contains_v2_contract_fields():
    info_ctx = _base_item_context()
    info_ctx["feedback_context"]["edit_comment_excerpt"] = "Critical phrase not in transcript."
    info_class = classify_misclassification_item(info_ctx)

    mech_ctx = _base_item_context()
    mech_ctx["prediction"]["score_explanation_excerpt"] = "Runtime error: timeout during scoring."
    mech_ctx["prediction"]["predicted_value"] = "No"
    mech_class = classify_misclassification_item(mech_ctx)

    score_ctx = _base_item_context()
    score_ctx["prediction"]["predicted_value"] = "No"
    score_class = classify_misclassification_item(score_ctx)

    topics = [{
        "topic_id": 1,
        "label": "Test Topic",
        "member_count": 3,
        "exemplars": [
            {
                "timestamp": "2026-04-04T10:00:00Z",
                "misclassification_item_context": info_ctx,
                "misclassification_classification": info_class,
            },
            {
                "timestamp": "2026-04-04T11:00:00Z",
                "misclassification_item_context": mech_ctx,
                "misclassification_classification": mech_class,
            },
            {
                "timestamp": "2026-04-04T12:00:00Z",
                "misclassification_item_context": score_ctx,
                "misclassification_classification": score_class,
            },
        ],
    }]

    summary = build_misclassification_analysis_summary(topics, max_category_summary_items=2)
    assert summary["overall_assessment"]["total_items"] == 3
    assert "topic_category_breakdown" in summary
    assert "category_summaries" in summary
    assert "mechanical_subtype_totals" in summary
    assert "primary_next_action" in summary
    assert "optimization_applicability" in summary
    assert summary["max_category_summary_items_used"] == 2
    assert set(summary["category_summaries"].keys()) == set(MISCLASSIFICATION_CATEGORIES)
    assert summary["topic_category_breakdown"][0]["topic_primary_category"] in MISCLASSIFICATION_CATEGORIES
    assert 0 <= summary["topic_category_breakdown"][0]["topic_category_purity"] <= 1

