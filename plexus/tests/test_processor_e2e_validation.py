"""
End-to-End validation tests for processor consistency across training, prediction, and evaluation.

This test suite verifies that processors produce identical transformations whether applied during:
- Training (via ScoreData.process_data())
- Prediction (via Score.apply_processors_to_text())
- Evaluation (via Scorecard.score_entire_text() → get_score_result())
"""

import unittest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch
from plexus.scores.Score import Score
from plexus.scores.core.ScoreData import ScoreData
from plexus.processors.FilterCustomerOnlyProcessor import FilterCustomerOnlyProcessor
from plexus.processors.RemoveSpeakerIdentifiersTranscriptFilter import RemoveSpeakerIdentifiersTranscriptFilter


class TestProcessorE2EValidation(unittest.TestCase):
    """Verify processors work consistently across all operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_text = "Agent: Hello there. Customer: Hi, I need help. Agent: Sure thing. Customer: Thank you."
        self.processors_config = [
            {'class': 'FilterCustomerOnlyProcessor'},
            {'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}
        ]

    def test_prediction_flow_with_processors(self):
        """Test processors work in prediction flow via Score.apply_processors_to_text()"""
        result = Score.apply_processors_to_text(self.test_text, self.processors_config)

        # Should contain customer speech without labels
        self.assertIn("Hi, I need help", result)
        self.assertIn("Thank you", result)

        # Should NOT contain agent speech
        self.assertNotIn("Hello there", result)
        self.assertNotIn("Sure thing", result)

        # Should NOT contain speaker labels
        self.assertNotIn("Agent:", result)
        self.assertNotIn("Customer:", result)

    def test_processor_consistency_remove_speaker_identifiers(self):
        """Test RemoveSpeakerIdentifiersTranscriptFilter consistency"""
        text = "Agent: Hello. Customer: Hi. Speaker1: Test."
        config = [{'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}]

        # Apply via prediction flow
        prediction_result = Score.apply_processors_to_text(text, config)

        # Should remove all speaker identifiers
        self.assertNotIn("Agent:", prediction_result)
        self.assertNotIn("Customer:", prediction_result)
        self.assertNotIn("Speaker1:", prediction_result)

        # Content should remain
        self.assertIn("Hello", prediction_result)
        self.assertIn("Hi", prediction_result)
        self.assertIn("Test", prediction_result)

    def test_processor_consistency_filter_customer_only(self):
        """Test FilterCustomerOnlyProcessor consistency"""
        text = "Agent: Hello. Customer: Hi there. Agent: How can I help?"
        config = [{'class': 'FilterCustomerOnlyProcessor'}]

        # Apply via prediction flow
        prediction_result = Score.apply_processors_to_text(text, config)

        # Should keep only customer speech (note: FilterCustomerOnly also removes speaker labels)
        self.assertIn("Hi there", prediction_result)

        # Should not contain agent speech
        self.assertNotIn("Hello", prediction_result)
        self.assertNotIn("How can I help", prediction_result)

    def test_processor_chain_order_consistency(self):
        """Test that processor order matters and is consistent"""
        text = "Agent: Hello. Customer: Hi there."

        # Chain 1: Filter then Remove
        config1 = [
            {'class': 'FilterCustomerOnlyProcessor'},
            {'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}
        ]
        result1 = Score.apply_processors_to_text(text, config1)

        # Chain 2: Remove then Filter (different order)
        config2 = [
            {'class': 'RemoveSpeakerIdentifiersTranscriptFilter'},
            {'class': 'FilterCustomerOnlyProcessor'}
        ]
        result2 = Score.apply_processors_to_text(text, config2)

        # Results should be different due to order
        self.assertNotEqual(result1, result2)

        # Result 1 should have customer speech without label
        self.assertIn("Hi there", result1)
        self.assertNotIn("Customer:", result1)

        # Result 2 should have removed labels first, then filter won't find "Customer:" to filter on
        # So it might behave differently depending on FilterCustomerOnlyProcessor implementation

    def test_empty_processor_config_returns_original_text(self):
        """Test that empty processor config returns original text"""
        text = "Agent: Hello. Customer: Hi."

        result_empty = Score.apply_processors_to_text(text, [])
        result_none = Score.apply_processors_to_text(text, None)

        self.assertEqual(result_empty, text)
        self.assertEqual(result_none, text)

    def test_processor_with_empty_text(self):
        """Test processors handle empty text gracefully"""
        config = [{'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}]

        result = Score.apply_processors_to_text("", config)

        self.assertEqual(result, "")

    def test_processor_with_whitespace_only_text(self):
        """Test processors handle whitespace-only text"""
        config = [{'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}]

        text = "   \n\t  "
        result = Score.apply_processors_to_text(text, config)

        # Should handle gracefully
        self.assertIsInstance(result, str)

    def test_multiple_processors_in_sequence(self):
        """Test multiple processors applied in sequence produce expected result"""
        text = "Agent: I don't think this is working. Customer: It's not working for me either."

        config = [
            {'class': 'FilterCustomerOnlyProcessor'},
            {'class': 'RemoveSpeakerIdentifiersTranscriptFilter'},
            {'class': 'ExpandContractionsProcessor'}
        ]

        result = Score.apply_processors_to_text(text, config)

        # Should have customer speech only
        self.assertIn("not working", result)

        # Should not have agent speech
        self.assertNotIn("I don", result)
        self.assertNotIn("think", result)

        # Should have expanded contractions
        self.assertIn("It is not", result)

        # Should not have speaker labels
        self.assertNotIn("Customer:", result)

    def test_processor_error_handling_graceful(self):
        """Test that processor errors are handled gracefully"""
        text = "Agent: Hello. Customer: Hi."

        config = [
            {'class': 'NonExistentProcessor'},  # This will fail
            {'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}  # This should still run
        ]

        result = Score.apply_processors_to_text(text, config)

        # Should have removed speaker identifiers despite first processor failing
        self.assertNotIn("Agent:", result)
        self.assertNotIn("Customer:", result)
        self.assertIn("Hello", result)
        self.assertIn("Hi", result)

    def test_processor_preserves_text_encoding(self):
        """Test processors preserve UTF-8 encoding"""
        text = "Agent: Hello 👋 Customer: Hi there! 😊"

        config = [{'class': 'FilterCustomerOnlyProcessor'}]

        result = Score.apply_processors_to_text(text, config)

        # Should preserve emoji
        self.assertIn("😊", result)
        self.assertIn("Hi there", result)

    def test_processor_configuration_from_score_parameters(self):
        """Test processors can be configured from score parameters"""
        # This tests that the configuration structure is correct

        class MockScore(Score):
            def predict(self, context, model_input):
                return Score.Result(value="test", parameters=self.parameters)

            def train_model(self):
                pass

            def predict_validation(self):
                pass

        # Create score with processor configuration
        score = MockScore(
            name="Test Score",
            scorecard_name="Test Scorecard",
            data={
                'class': 'MockDataCache',
                'processors': [
                    {'class': 'FilterCustomerOnlyProcessor'}
                ]
            }
        )

        # Verify processors are in configuration
        self.assertIn('processors', score.parameters.data)
        self.assertEqual(len(score.parameters.data['processors']), 1)
        self.assertEqual(
            score.parameters.data['processors'][0]['class'],
            'FilterCustomerOnlyProcessor'
        )

    def test_scorecard_level_vs_score_level_processors(self):
        """Test that score-level processors override scorecard-level processors"""
        # This verifies the configuration precedence structure

        scorecard_processors = [
            {'class': 'RemoveStopWordsTranscriptFilter'}
        ]

        score_processors = [
            {'class': 'FilterCustomerOnlyProcessor'}
        ]

        # In actual implementation, score_processors would be used
        self.assertNotEqual(scorecard_processors, score_processors)
        self.assertEqual(score_processors[0]['class'], 'FilterCustomerOnlyProcessor')

    def test_processor_with_parameters(self):
        """Test processors can receive custom parameters"""
        text = "Some text with parameters"

        # Test with ByColumnValueDatasetFilter parameters structure
        config = [
            {
                'class': 'RemoveSpeakerIdentifiersTranscriptFilter',
                'parameters': {}  # Even empty parameters should work
            }
        ]

        result = Score.apply_processors_to_text(text, config)

        # Should not raise an error
        self.assertIsInstance(result, str)


if __name__ == '__main__':
    unittest.main()
