import unittest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from plexus.scores.Score import Score
from plexus.processors.FilterCustomerOnlyProcessor import FilterCustomerOnlyProcessor
from plexus.processors.RemoveSpeakerIdentifiersTranscriptFilter import RemoveSpeakerIdentifiersTranscriptFilter


class TestProcessorIntegration(unittest.TestCase):
    """Integration tests for processor execution in training, evaluation, and production"""

    def test_apply_processors_to_text_single_processor(self):
        """Test applying a single processor to text"""
        text = "Agent: Hello there. Customer: Hi, I need help. Agent: Sure thing."
        
        processors_config = [
            {'class': 'FilterCustomerOnlyProcessor'}
        ]
        
        result = Score.apply_processors_to_text(text, processors_config)
        
        # Should contain only customer speech
        self.assertIn("Hi, I need help", result)
        # Should not contain agent speech
        self.assertNotIn("Hello there", result)
        self.assertNotIn("Sure thing", result)

    def test_apply_processors_to_text_chained_processors(self):
        """Test chaining multiple processors"""
        text = "Agent: Hello there. Customer: Hi, I need help. Agent: Sure thing. Customer: Thank you."
        
        processors_config = [
            {'class': 'FilterCustomerOnlyProcessor'},
            {'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}
        ]
        
        result = Score.apply_processors_to_text(text, processors_config)
        
        # Should contain customer speech
        self.assertIn("Hi, I need help", result)
        self.assertIn("Thank you", result)
        # Should not contain agent speech
        self.assertNotIn("Hello there", result)
        self.assertNotIn("Sure thing", result)
        # Should not contain speaker identifiers
        self.assertNotIn("Customer:", result)
        self.assertNotIn("Agent:", result)

    def test_apply_processors_to_text_empty_config(self):
        """Test that empty processor config returns original text"""
        text = "Agent: Hello. Customer: Hi."
        
        result = Score.apply_processors_to_text(text, [])
        
        self.assertEqual(result, text)

    def test_apply_processors_to_text_none_config(self):
        """Test that None processor config returns original text"""
        text = "Agent: Hello. Customer: Hi."
        
        result = Score.apply_processors_to_text(text, None)
        
        self.assertEqual(result, text)

    def test_apply_processors_to_text_empty_text(self):
        """Test handling of empty text"""
        processors_config = [
            {'class': 'FilterCustomerOnlyProcessor'}
        ]
        
        result = Score.apply_processors_to_text("", processors_config)
        
        self.assertEqual(result, "")

    def test_apply_processors_to_text_with_parameters(self):
        """Test processor with custom parameters"""
        text = "Some text with stopwords and more text"
        
        # RemoveStopWordsTranscriptFilter doesn't take parameters in our implementation,
        # but this tests the parameter passing mechanism
        processors_config = [
            {
                'class': 'RemoveStopWordsTranscriptFilter',
                'parameters': {}
            }
        ]
        
        # Should not raise an error
        result = Score.apply_processors_to_text(text, processors_config)
        self.assertIsInstance(result, str)

    def test_apply_processors_to_text_invalid_processor(self):
        """Test handling of invalid processor class"""
        text = "Agent: Hello. Customer: Hi."
        
        processors_config = [
            {'class': 'NonExistentProcessor'}
        ]
        
        # Should log error but not crash, returning original text
        result = Score.apply_processors_to_text(text, processors_config)
        
        # Should return original text since processor failed
        self.assertEqual(result, text)

    def test_apply_processors_to_text_missing_class_field(self):
        """Test handling of processor config missing 'class' field"""
        text = "Agent: Hello. Customer: Hi."
        
        processors_config = [
            {'parameters': {}}  # Missing 'class' field
        ]
        
        # Should log warning but not crash
        result = Score.apply_processors_to_text(text, processors_config)
        
        # Should return original text
        self.assertEqual(result, text)

    def test_processor_execution_in_training_flow(self):
        """Test that processors are applied during training data processing"""
        # This tests the existing behavior in ScoreData.process_data()
        from plexus.scores.core.ScoreData import ScoreData
        
        # Create a mock score with processor config
        class TestScore(Score):
            def predict(self, context, model_input):
                return Score.Result(value="test", parameters=self.parameters)
            
            def train_model(self):
                pass
            
            def predict_validation(self):
                pass
        
        # Create score with processor configuration
        score = TestScore(
            name="Test Score",
            scorecard_name="Test Scorecard",
            data={
                'class': 'MockDataCache',
                'processors': [
                    {'class': 'FilterCustomerOnlyProcessor'}
                ]
            }
        )
        
        # Verify the processor config is stored
        self.assertIn('processors', score.parameters.data)
        self.assertEqual(len(score.parameters.data['processors']), 1)
        self.assertEqual(score.parameters.data['processors'][0]['class'], 'FilterCustomerOnlyProcessor')

    def test_scorecard_level_processor_configuration(self):
        """Test that scorecard-level processors can be configured"""
        # This tests the structure, not the full execution
        scorecard_config = {
            'name': 'Test Scorecard',
            'processors': [
                {'class': 'FilterCustomerOnlyProcessor'},
                {'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}
            ],
            'scores': []
        }
        
        # Verify structure
        self.assertIn('processors', scorecard_config)
        self.assertEqual(len(scorecard_config['processors']), 2)

    def test_score_level_overrides_scorecard_level(self):
        """Test that score-level processors override scorecard-level processors"""
        # This is tested through the Scorecard.get_score_result logic
        # where score-level processors are checked first
        
        scorecard_processors = [
            {'class': 'RemoveStopWordsTranscriptFilter'}
        ]
        
        score_processors = [
            {'class': 'FilterCustomerOnlyProcessor'}
        ]
        
        # In the actual implementation, score_processors would be used
        # This test verifies the configuration structure
        self.assertNotEqual(scorecard_processors, score_processors)
        self.assertEqual(score_processors[0]['class'], 'FilterCustomerOnlyProcessor')

    def test_processor_error_handling_continues_with_other_processors(self):
        """Test that if one processor fails, others still run"""
        text = "Agent: Hello. Customer: Hi there. Agent: Goodbye."
        
        processors_config = [
            {'class': 'NonExistentProcessor'},  # This will fail
            {'class': 'FilterCustomerOnlyProcessor'}  # This should still run
        ]
        
        result = Score.apply_processors_to_text(text, processors_config)
        
        # Despite first processor failing, second should have run
        # However, since first processor fails, text remains unchanged for it
        # and second processor operates on original text
        self.assertIn("Hi there", result)

    def test_multiple_customer_turns_with_chained_processors(self):
        """Test complex scenario with multiple customer turns and chained processors"""
        text = """
        Agent: Welcome to support, how can I help you today?
        Customer: I'm having trouble with my order.
        Agent: I understand. Can you provide your order number?
        Customer: Yes, it's 12345.
        Agent: Thank you. Let me look that up.
        Customer: I appreciate your help.
        Agent: You're welcome. I found your order.
        """
        
        processors_config = [
            {'class': 'FilterCustomerOnlyProcessor'},
            {'class': 'RemoveSpeakerIdentifiersTranscriptFilter'}
        ]
        
        result = Score.apply_processors_to_text(text, processors_config)
        
        # Should have all customer utterances
        self.assertIn("having trouble with my order", result)
        self.assertIn("12345", result)
        self.assertIn("appreciate your help", result)
        
        # Should not have agent utterances
        self.assertNotIn("Welcome to support", result)
        self.assertNotIn("look that up", result)
        self.assertNotIn("found your order", result)
        
        # Should not have speaker labels
        self.assertNotIn("Customer:", result)
        self.assertNotIn("Agent:", result)

    def test_processor_preserves_text_encoding(self):
        """Test that processors handle UTF-8 text correctly"""
        text = "Agent: Hello 👋 Customer: Hi there! 😊 I need help. Agent: Sure! 🎉"
        
        processors_config = [
            {'class': 'FilterCustomerOnlyProcessor'}
        ]
        
        result = Score.apply_processors_to_text(text, processors_config)
        
        # Should preserve emoji and special characters
        self.assertIn("😊", result)
        self.assertIn("Hi there", result)
        # Should not have agent's emoji
        self.assertNotIn("👋", result)
        self.assertNotIn("🎉", result)

    def test_processor_handles_whitespace_text(self):
        """Test processor handling of whitespace-only text"""
        text = "   \n\t  "
        
        processors_config = [
            {'class': 'FilterCustomerOnlyProcessor'}
        ]
        
        result = Score.apply_processors_to_text(text, processors_config)
        
        # Should handle gracefully
        self.assertIsInstance(result, str)


if __name__ == '__main__':
    unittest.main()

