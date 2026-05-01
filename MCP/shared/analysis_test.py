#!/usr/bin/env python3
"""
BDD-style tests for shared RCA analysis utilities.
"""
import pytest
import json
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit


class TestBuildFeedbackContext:
    """BDD tests for build_feedback_context — constructing reviewer context strings."""

    def test_reviewer_corrected_value(self):
        """
        GIVEN a feedback item where the reviewer corrected the value
        WHEN build_feedback_context is called
        THEN it should include the original and corrected values
        """
        from plexus.rca_analysis import build_feedback_context

        ctx = build_feedback_context(
            feedback_comment="Agent said medications are free",
            feedback_initial="Yes",
            feedback_final="No",
            predicted_value="Yes",
        )
        assert "Original production value: Yes" in ctx
        assert "Reviewer corrected to: No" in ctx
        assert "Reviewer comment: Agent said medications are free" in ctx

    def test_reviewer_agreed_but_eval_differs(self):
        """
        GIVEN a feedback item where the reviewer agreed with production
        AND the evaluation produced a different result
        WHEN build_feedback_context is called
        THEN it should explain the agreement scenario clearly
        """
        from plexus.rca_analysis import build_feedback_context

        ctx = build_feedback_context(
            feedback_comment="Agree",
            feedback_initial="No",
            feedback_final="No",
            predicted_value="Yes",
        )
        assert "Reviewer AGREED with original production value 'No'" in ctx
        assert "evaluation produced 'Yes'" in ctx
        assert "reviewer comment may refer to the original" in ctx

    def test_empty_feedback(self):
        """
        GIVEN no feedback information
        WHEN build_feedback_context is called
        THEN it should return an empty string
        """
        from plexus.rca_analysis import build_feedback_context

        ctx = build_feedback_context()
        assert ctx == ""

    def test_comment_only(self):
        """
        GIVEN only a feedback comment (no initial/final values)
        WHEN build_feedback_context is called
        THEN it should include the comment
        """
        from plexus.rca_analysis import build_feedback_context

        ctx = build_feedback_context(feedback_comment="This is wrong")
        assert "Reviewer comment: This is wrong" in ctx

    def test_long_comment_truncated(self):
        """
        GIVEN a very long feedback comment
        WHEN build_feedback_context is called
        THEN the comment should be truncated to 300 chars
        """
        from plexus.rca_analysis import build_feedback_context

        long_comment = "x" * 500
        ctx = build_feedback_context(feedback_comment=long_comment)
        # The comment in the output should be truncated
        assert len(ctx) < 500


class TestAnalyzeScoreResult:
    """BDD tests for analyze_score_result — the core LLM inference logic."""

    def test_successful_two_turn_analysis(self):
        """
        GIVEN a transcript, predicted/correct values, and score context
        WHEN analyze_score_result is called
        AND the OpenAI helper responds successfully
        THEN it should return (detailed_cause, suggested_fix) from two turns
        """
        from plexus.rca_analysis import analyze_score_result

        call_count = [0]
        responses = [
            "The model incorrectly flagged this as a violation.",
            "Add 'free service + copay mention = compliant' rule.",
        ]

        def fake_invoke(*, system, messages, max_output_tokens, call_site="rca"):
            text = responses[min(call_count[0], len(responses) - 1)]
            call_count[0] += 1
            return text

        with patch("plexus.rca_analysis._invoke_rca_openai_text", side_effect=fake_invoke):
            cause, fix = analyze_score_result(
                primary_input="Agent: SelectRx is a free service for you.",
                predicted="No",
                correct="Yes",
                explanation="Flagged as Ambiguous Cost Language",
                topic_label="Free service false alarms",
                score_guidelines="Check for misrepresentation",
                score_yaml_code="name: Agent Misrepresentation",
            )

        assert "incorrectly flagged" in cause
        assert "copay" in fix
        assert call_count[0] == 2

    def test_openai_failure_returns_empty(self):
        """
        GIVEN a valid request
        WHEN the OpenAI call fails with an exception
        THEN it should return empty strings without raising
        """
        from plexus.rca_analysis import analyze_score_result

        with patch(
            "plexus.rca_analysis._invoke_rca_openai_text",
            side_effect=Exception("OpenAI unavailable"),
        ):
            cause, fix = analyze_score_result(
                primary_input="Some input artifact",
                predicted="No",
                correct="Yes",
                explanation="Some explanation",
            )

        assert cause == ""
        assert fix == ""

    def test_feedback_context_included_in_prompt(self):
        """
        GIVEN feedback_context text
        WHEN analyze_score_result is called
        THEN the feedback context should appear in the prompt sent to the LLM
        """
        from plexus.rca_analysis import analyze_score_result

        captured_messages: list = []

        def fake_invoke(*, system, messages, max_output_tokens, call_site="rca"):
            captured_messages.append(messages)
            return "Analysis result"

        with patch("plexus.rca_analysis._invoke_rca_openai_text", side_effect=fake_invoke):
            analyze_score_result(
                primary_input="Some input artifact",
                predicted="No",
                correct="Yes",
                explanation="Some explanation",
                feedback_context="Reviewer AGREED with original production value 'No'",
            )

        assert len(captured_messages) >= 1
        first_user_content = captured_messages[0][0]["content"]
        assert "Reviewer AGREED" in first_user_content


class TestPayloadRootCauseInclusion:
    """BDD tests for root_cause inclusion in plexus_evaluation_info payload."""

    def test_root_cause_included_when_available(self):
        """
        GIVEN evaluation_info with first-class root_cause fields
        WHEN building the MCP payload
        THEN root_cause should be included in the payload
        """
        evaluation_info = {
            'id': 'eval-123',
            'type': 'feedback',
            'status': 'COMPLETED',
            'scorecard_name': 'Test',
            'scorecard_id': 'sc-1',
            'score_name': 'Test Score',
            'score_id': 'score-1',
            'score_version_id': 'ver-1',
            'total_items': 91,
            'processed_items': 91,
            'metrics': [],
            'accuracy': 92.31,
            'confusion_matrix': None,
            'predicted_class_distribution': None,
            'dataset_class_distribution': None,
            'cost': None,
            'started_at': None,
            'created_at': None,
            'updated_at': None,
            'root_cause': {
                'topics': [
                    {
                        'label': 'Free service false alarms',
                        'member_count': 3,
                        'exemplars': [
                            {
                                'item_id': 'item-1',
                                'score_explanation': 'Flagged as Ambiguous Cost Language',
                                'detailed_cause': 'Model incorrectly flagged free service',
                                'suggested_fix': 'Add safe harbor for free service + copay',
                            }
                        ],
                        'detailed_explanation': 'Pattern of false alarms...',
                        'improvement_suggestion': 'Add a safe harbor rule...',
                    }
                ],
                'overall_explanation': 'The score over-flags free service language.',
                'overall_improvement_suggestion': 'Add copay disclaimer safe harbor.',
                'misclassification_analysis': {
                    'category_totals': {
                        'score_configuration_problem': 3,
                        'information_gap': 1,
                        'guideline_gap_requires_sme': 0,
                        'mechanical_malfunction': 0,
                    }
                }
            },
            'misclassification_analysis': {
                'category_totals': {
                    'score_configuration_problem': 3,
                    'information_gap': 1,
                    'guideline_gap_requires_sme': 0,
                    'mechanical_malfunction': 0,
                }
            },
        }

        # Simulate the payload construction from evaluations.py
        payload = {
            "id": evaluation_info['id'],
            "type": evaluation_info['type'],
            "status": evaluation_info['status'],
            "scorecard": evaluation_info['scorecard_name'],
            "score": evaluation_info['score_name'],
        }

        root_cause = evaluation_info.get('root_cause')
        if root_cause:
            payload['root_cause'] = root_cause
        misclassification_analysis = evaluation_info.get('misclassification_analysis')
        if misclassification_analysis:
            payload['misclassification_analysis'] = misclassification_analysis

        assert 'root_cause' in payload
        assert 'misclassification_analysis' in payload
        assert payload['root_cause']['overall_explanation'] == 'The score over-flags free service language.'
        assert len(payload['root_cause']['topics']) == 1
        assert payload['root_cause']['topics'][0]['exemplars'][0]['detailed_cause'] == 'Model incorrectly flagged free service'
        assert payload['root_cause']['topics'][0]['exemplars'][0]['score_explanation'] == 'Flagged as Ambiguous Cost Language'
        assert payload['misclassification_analysis']['category_totals']['information_gap'] == 1

    def test_root_cause_not_included_when_missing(self):
        """
        GIVEN evaluation_info without root_cause fields
        WHEN building the MCP payload
        THEN root_cause should NOT be in the payload
        """
        evaluation_info = {
            'parameters': {'some_other_field': True}
        }

        payload = {}
        root_cause = evaluation_info.get('root_cause')
        if root_cause:
            payload['root_cause'] = root_cause
        misclassification_analysis = evaluation_info.get('misclassification_analysis')
        if misclassification_analysis:
            payload['misclassification_analysis'] = misclassification_analysis

        assert 'root_cause' not in payload
        assert 'misclassification_analysis' not in payload

    def test_root_cause_not_included_when_root_cause_none(self):
        """
        GIVEN evaluation_info with root_cause=None
        WHEN building the MCP payload
        THEN root_cause should NOT be in the payload
        """
        evaluation_info = {
            'parameters': None,
            'root_cause': None,
            'misclassification_analysis': None,
        }

        payload = {}
        root_cause = evaluation_info.get('root_cause')
        if root_cause:
            payload['root_cause'] = root_cause
        misclassification_analysis = evaluation_info.get('misclassification_analysis')
        if misclassification_analysis:
            payload['misclassification_analysis'] = misclassification_analysis

        assert 'root_cause' not in payload
        assert 'misclassification_analysis' not in payload


class TestScoreExplanationInExemplarDicts:
    """BDD tests for score_explanation inclusion in RCA exemplar dicts."""

    def test_score_explanation_stored_in_exemplar(self):
        """
        GIVEN an exemplar with score_explanation in metadata
        WHEN the exemplar dict is constructed
        THEN score_explanation should be included
        """
        # Simulate the exemplar dict construction from Evaluation.py
        class MockExemplar:
            text = "Agent said free service"
            timestamp = "2026-03-31T10:00:00Z"
            metadata = {
                "item_id": "item-1",
                "initial_answer_value": "No",
                "final_answer_value": "Yes",
                "score_explanation": "**Ambiguous Cost Language**: Agent used 'free service' language",
            }

        ex = MockExemplar()
        above_fold = True
        item_id = ex.metadata.get("item_id")
        explanation = ""
        detailed_cause = "Model incorrectly flagged"
        suggested_fix = "Add safe harbor"

        score_explanation = ex.metadata.get("score_explanation", "")
        exemplar_dict = {
            "text": ex.text,
            "item_id": item_id,
            "initial_answer_value": ex.metadata.get("initial_answer_value"),
            "final_answer_value": ex.metadata.get("final_answer_value"),
            "timestamp": ex.timestamp,
            "above_fold": above_fold,
            **({"score_explanation": score_explanation} if score_explanation else {}),
            **({"detailed_cause": detailed_cause} if detailed_cause else {}),
            **({"suggested_fix": suggested_fix} if suggested_fix else {}),
        }

        assert exemplar_dict["score_explanation"] == "**Ambiguous Cost Language**: Agent used 'free service' language"
        assert exemplar_dict["detailed_cause"] == "Model incorrectly flagged"
        assert exemplar_dict["suggested_fix"] == "Add safe harbor"

    def test_score_explanation_omitted_when_empty(self):
        """
        GIVEN an exemplar without score_explanation
        WHEN the exemplar dict is constructed
        THEN score_explanation key should NOT be present
        """
        score_explanation = ""
        exemplar_dict = {
            "text": "test",
            **({"score_explanation": score_explanation} if score_explanation else {}),
        }

        assert "score_explanation" not in exemplar_dict
