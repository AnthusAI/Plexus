from plexus.rca_analysis import (
    CONFIG_FIXABILITY_OPTIONS,
    MECHANICAL_SUBTYPES,
    MISCLASSIFICATION_CATEGORIES,
    MISCLASSIFICATION_EXCLUDED_ANALYSES,
    MISCLASSIFICATION_LABEL_PROVENANCE_SOURCES,
    build_misclassification_analysis_summary,
    build_misclassification_classification_contract,
    build_misclassification_item_context,
    classify_misclassification_item,
    normalize_best_evidence_source,
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
        "evidence_flags",
        "rationale_paragraph",
        "evidence_quote",
        "config_fixability",
    ]
    assert output["field_contracts"]["primary_category"]["allowed_values"] == list(
        MISCLASSIFICATION_CATEGORIES
    )
    assert output["field_contracts"]["mechanical_subtype"]["allowed_values"] == list(
        MECHANICAL_SUBTYPES
    )
    assert output["field_contracts"]["config_fixability"]["allowed_values"] == list(
        CONFIG_FIXABILITY_OPTIONS
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
        primary_input_text="Transcript text",
        primary_input_modality="text",
        metadata_snapshot='{"call_type":"inbound"}',
        label_provenance_source="feedback_final_answer_value",
        resolved_final_classes=["Yes", "No"],
        class_resolution_source="graph[-1].LogicalClassifier.code",
    )

    assert context["identifiers"]["feedback_item_id"] == "fb-1"
    assert context["prediction"]["predicted_value"] == "No"
    assert context["label_provenance"]["source"] == "feedback_final_answer_value"
    assert context["label_provenance"]["feedback_context_present"] is True
    assert context["source_availability"]["has_primary_input"] is True
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
            primary_input_text="",
            primary_input_modality="unknown",
            metadata_snapshot="",
            label_provenance_source="not_allowed",
        )
        assert False, "Expected ValueError for unsupported label provenance source"
    except ValueError as exc:
        assert "Unsupported label_provenance_source" in str(exc)


def test_normalize_best_evidence_source_supports_feedback_context_aliases():
    assert normalize_best_evidence_source("feedback_context") == "edit_comment"
    assert normalize_best_evidence_source("feedback_comment") == "edit_comment"
    assert normalize_best_evidence_source("feedback_comments") == "edit_comment"
    assert normalize_best_evidence_source("feedback_comment_detail") == "edit_comment"
    assert normalize_best_evidence_source("reviewer_comment") == "edit_comment"
    assert normalize_best_evidence_source("reviewer_comment_detail") == "edit_comment"
    assert normalize_best_evidence_source("edit_comment_excerpt") == "edit_comment"
    assert normalize_best_evidence_source("final_comment_excerpt") == "edit_comment"
    assert normalize_best_evidence_source("initial_comment_excerpt") == "edit_comment"


def test_normalize_best_evidence_source_supports_metadata_and_primary_input_aliases():
    assert normalize_best_evidence_source("metadata_snapshot_excerpt") == "metadata"
    assert normalize_best_evidence_source("primary_input_excerpt") == "primary_input"


def test_normalize_best_evidence_source_supports_guideline_and_score_context_aliases():
    assert normalize_best_evidence_source("score_guidelines") == "guidelines"
    assert normalize_best_evidence_source("score_context") == "score_yaml"


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
        primary_input_text="Transcript available",
        primary_input_modality="text",
        metadata_snapshot='{"call_type":"inbound"}',
        label_provenance_source="feedback_final_answer_value",
        resolved_final_classes=["Yes", "No"],
        class_resolution_source="graph[-1].LogicalClassifier.code",
    )


def _base_evidence_flags(**overrides):
    flags = {
        "external_information_missing_or_degraded": False,
        "guideline_or_policy_ambiguity": False,
        "missing_required_context_due_system": False,
        "runtime_or_parsing_failure": False,
        "invalid_output_class_signal": False,
        "best_evidence_source": "none",
        "best_evidence_quote": "",
    }
    flags.update(overrides)
    return flags


def test_classifier_detects_score_configuration_problem_default():
    context = _base_item_context()
    result = classify_misclassification_item(context, _base_evidence_flags())
    assert result["primary_category"] == "score_configuration_problem"
    assert result["mechanical_subtype"] is None


def test_classifier_detects_information_gap_from_feedback_signal():
    context = _base_item_context()
    context["feedback_context"]["edit_comment_excerpt"] = "Critical phrase not in transcript."
    context["label_provenance"]["feedback_context_present"] = True
    result = classify_misclassification_item(
        context,
        _base_evidence_flags(external_information_missing_or_degraded=True),
    )
    assert result["primary_category"] == "information_gap"
    assert result["information_gap_subtype"] in {"missing_primary_input", "degraded_primary_input"}


def test_classifier_detects_guideline_gap_from_ambiguity_signal():
    context = _base_item_context()
    context["feedback_context"]["edit_comment_excerpt"] = "Guideline is ambiguous here and needs SME clarification."
    context["label_provenance"]["feedback_context_present"] = True
    result = classify_misclassification_item(
        context,
        _base_evidence_flags(guideline_or_policy_ambiguity=True),
    )
    assert result["primary_category"] == "guideline_gap_requires_sme"


def test_classifier_detects_mechanical_runtime_error_with_subtype():
    context = _base_item_context()
    context["prediction"]["score_explanation_excerpt"] = "Runtime error: timeout while running classifier."
    result = classify_misclassification_item(context, _base_evidence_flags())
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "runtime_error"
    assert "timeout" in (result["mechanical_details"] or "")


def test_classifier_does_not_treat_failed_requirements_text_as_mechanical():
    context = _base_item_context()
    context["prediction"]["score_explanation_excerpt"] = "The customer failed requirements for eligibility."
    result = classify_misclassification_item(context, _base_evidence_flags())
    assert result["primary_category"] == "score_configuration_problem"


def test_classifier_detects_mechanical_parse_or_schema_error():
    context = _base_item_context()
    context["prediction"]["score_explanation_excerpt"] = "Parser error: schema validation failed to parse model output."
    result = classify_misclassification_item(context, _base_evidence_flags())
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "parse_or_schema_error"


def test_classifier_detects_missing_labels_as_mechanical():
    context = _base_item_context()
    context["prediction"]["predicted_value"] = ""
    result = classify_misclassification_item(context, _base_evidence_flags())
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "missing_labels"


def test_classifier_detects_missing_required_context_as_mechanical():
    context = _base_item_context()
    context["source_availability"]["missing_required_context_keys"] = ["customer_state"]
    result = classify_misclassification_item(context, _base_evidence_flags())
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "missing_required_context"


def test_classifier_detects_invalid_output_class_as_mechanical():
    context = _base_item_context()
    context["prediction"]["predicted_value"] = "Maybe"
    result = classify_misclassification_item(context, _base_evidence_flags())
    assert result["primary_category"] == "mechanical_malfunction"
    assert result["mechanical_subtype"] == "invalid_output_class"


def test_classifier_uses_llm_signal_for_information_gap():
    context = _base_item_context()
    result = classify_misclassification_item(
        context,
        _base_evidence_flags(
            external_information_missing_or_degraded=True,
            best_evidence_source="edit_comment",
            best_evidence_quote="Reviewer says key words were audible in audio but missing in transcript.",
        ),
    )
    assert result["primary_category"] == "information_gap"


def test_classifier_uses_llm_signal_for_guideline_gap():
    context = _base_item_context()
    result = classify_misclassification_item(
        context,
        _base_evidence_flags(
            guideline_or_policy_ambiguity=True,
            best_evidence_source="edit_comment",
            best_evidence_quote="Policy unclear for this edge case.",
        ),
    )
    assert result["primary_category"] == "guideline_gap_requires_sme"


def test_classifier_does_not_use_feedback_keywords_without_llm_flags():
    info_context = _base_item_context()
    info_context["feedback_context"]["edit_comment_excerpt"] = "Critical phrase not in transcript."
    info_result = classify_misclassification_item(info_context, _base_evidence_flags())
    assert info_result["primary_category"] == "score_configuration_problem"

    guideline_context = _base_item_context()
    guideline_context["feedback_context"]["edit_comment_excerpt"] = "Guideline is ambiguous and needs SME clarification."
    guideline_result = classify_misclassification_item(guideline_context, _base_evidence_flags())
    assert guideline_result["primary_category"] == "score_configuration_problem"


def test_misclassification_analysis_summary_contains_v2_contract_fields():
    info_ctx = _base_item_context()
    info_ctx["feedback_context"]["edit_comment_excerpt"] = "Critical phrase not in transcript."
    info_class = classify_misclassification_item(
        info_ctx,
        _base_evidence_flags(external_information_missing_or_degraded=True),
    )

    mech_ctx = _base_item_context()
    mech_ctx["prediction"]["score_explanation_excerpt"] = "Runtime error: timeout during scoring."
    mech_ctx["prediction"]["predicted_value"] = "No"
    mech_class = classify_misclassification_item(mech_ctx, _base_evidence_flags())

    score_ctx = _base_item_context()
    score_ctx["prediction"]["predicted_value"] = "No"
    score_class = classify_misclassification_item(score_ctx, _base_evidence_flags())

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

    item_classifications_all = [
        {
            "feedback_item_id": "fb-1",
            "item_id": "item-1",
            "timestamp": "2026-04-04T10:00:00Z",
            "topic_id": 1,
            "topic_label": "Test Topic",
            "predicted_value": "No",
            "correct_value": "Yes",
            "primary_category": info_class["primary_category"],
            "confidence": info_class["confidence"],
            "rationale_short": "Critical phrase missing in transcript.",
            "rationale_full": info_class["rationale"],
            "evidence_snippets": info_class["evidence_snippets"],
            "mechanical_subtype": info_class["mechanical_subtype"],
            "mechanical_details": info_class["mechanical_details"],
            "information_gap_subtype": info_class.get("information_gap_subtype"),
            "rationale_paragraph": "Input evidence was insufficient for a reliable label decision.",
            "evidence_quote": "Critical phrase not in transcript.",
            "config_fixability": "blocked_by_input",
            "misclassification_item_context": info_ctx,
            "misclassification_classification": info_class,
        },
        {
            "feedback_item_id": "fb-2",
            "item_id": "item-2",
            "timestamp": "2026-04-04T11:00:00Z",
            "topic_id": 1,
            "topic_label": "Test Topic",
            "predicted_value": "No",
            "correct_value": "Yes",
            "primary_category": mech_class["primary_category"],
            "confidence": mech_class["confidence"],
            "rationale_short": "Runtime error prevented valid prediction.",
            "rationale_full": mech_class["rationale"],
            "evidence_snippets": mech_class["evidence_snippets"],
            "mechanical_subtype": mech_class["mechanical_subtype"],
            "mechanical_details": mech_class["mechanical_details"],
            "information_gap_subtype": mech_class.get("information_gap_subtype"),
            "rationale_paragraph": "Runtime timeout prevented a valid prediction.",
            "evidence_quote": "Runtime error: timeout during scoring.",
            "config_fixability": "blocked_by_mechanical",
            "misclassification_item_context": mech_ctx,
            "misclassification_classification": mech_class,
        },
        {
            "feedback_item_id": "fb-3",
            "item_id": "item-3",
            "timestamp": "2026-04-04T12:00:00Z",
            "topic_id": 1,
            "topic_label": "Test Topic",
            "predicted_value": "No",
            "correct_value": "Yes",
            "primary_category": score_class["primary_category"],
            "confidence": score_class["confidence"],
            "rationale_short": "Prompt/logic likely misaligned with rubric.",
            "rationale_full": score_class["rationale"],
            "evidence_snippets": score_class["evidence_snippets"],
            "mechanical_subtype": score_class["mechanical_subtype"],
            "mechanical_details": score_class["mechanical_details"],
            "information_gap_subtype": score_class.get("information_gap_subtype"),
            "rationale_paragraph": "Score logic can be tuned to align with the rubric.",
            "evidence_quote": "Model reasoning here",
            "config_fixability": "likely_fixable",
            "misclassification_item_context": score_ctx,
            "misclassification_classification": score_class,
        },
    ]

    summary = build_misclassification_analysis_summary(
        topics,
        item_classifications_all=item_classifications_all,
        analysis_scope={
            "candidate_items_total": 3,
            "classified_items_total": 3,
            "texts_analyzed_total": 3,
            "topics_found": 1,
            "topic_assignment_scope": "exemplar_only",
            "topic_assignment_unavailable_count": 0,
        },
        max_category_summary_items=2,
    )
    assert summary["overall_assessment"]["total_items"] == 3
    assert "topic_category_breakdown" in summary
    assert "category_hierarchy" in summary
    assert "category_summaries" in summary
    assert "category_diagnostics" in summary
    assert "analysis_scope" in summary
    assert "item_classifications_all" in summary
    assert "mechanical_subtype_totals" in summary
    assert "primary_next_action" in summary
    assert "optimization_applicability" in summary
    assert summary["max_category_summary_items_used"] == 2
    assert set(summary["category_summaries"].keys()) == set(MISCLASSIFICATION_CATEGORIES)
    assert summary["topic_category_breakdown"][0]["topic_primary_category"] in MISCLASSIFICATION_CATEGORIES
    assert 0 <= summary["topic_category_breakdown"][0]["topic_category_purity"] <= 1
    hierarchy_categories = [node["category_key"] for node in summary["category_hierarchy"]]
    assert hierarchy_categories == list(MISCLASSIFICATION_CATEGORIES)
    info_node = next(node for node in summary["category_hierarchy"] if node["category_key"] == "information_gap")
    assert info_node["item_count"] == 1
    assert 0 <= info_node["share"] <= 1
    assert "information_gap" in summary["category_diagnostics"]
    info_diag = summary["category_diagnostics"]["information_gap"]
    assert "missing_or_degraded_primary_input_count" in info_diag
    assert "missing_or_degraded_primary_input_share" in info_diag
    assert "missing_required_context_count" in info_diag
    assert "missing_required_context_share" in info_diag
    assert isinstance(info_node["topics"], list)
    if info_node["topics"]:
        topic = info_node["topics"][0]
        assert 0 <= topic["topic_category_purity"] <= 1
        assert isinstance(topic["example_item_ids"], list)
    mech_node = next(node for node in summary["category_hierarchy"] if node["category_key"] == "mechanical_malfunction")
    assert "mechanical_subtype_totals" in mech_node
