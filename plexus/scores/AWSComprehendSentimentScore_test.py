import unittest
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
from plexus.scores.AWSComprehendSentimentScore import AWSComprehendSentimentScore
from plexus.scores.Score import Score


class TestAWSComprehendSentimentScore(unittest.TestCase):
    """Test suite for AWSComprehendSentimentScore"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock boto3 client to avoid actual AWS calls
        self.mock_comprehend_client = Mock()
        
        with patch('boto3.client', return_value=self.mock_comprehend_client):
            self.score = AWSComprehendSentimentScore(
                name="Test Sentiment",
                scorecard_name="Test Scorecard"
            )

    @pytest.mark.asyncio
    async def test_positive_sentiment(self):
        """Test detection of positive sentiment"""
        # Mock AWS Comprehend response
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'POSITIVE',
            'SentimentScore': {
                'Positive': 0.95,
                'Negative': 0.01,
                'Neutral': 0.03,
                'Mixed': 0.01
            }
        }
        
        model_input = Score.Input(
            text="I absolutely love this product! It's amazing and works perfectly.",
            metadata={}
        )
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        self.assertEqual(result.value, 'POSITIVE')
        self.assertIn('POSITIVE', result.explanation)
        self.assertIn('95.0%', result.explanation)

    @pytest.mark.asyncio
    async def test_negative_sentiment(self):
        """Test detection of negative sentiment"""
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'NEGATIVE',
            'SentimentScore': {
                'Positive': 0.02,
                'Negative': 0.92,
                'Neutral': 0.04,
                'Mixed': 0.02
            }
        }
        
        model_input = Score.Input(
            text="This is terrible. I'm very disappointed and frustrated.",
            metadata={}
        )
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        self.assertEqual(result.value, 'NEGATIVE')
        self.assertIn('NEGATIVE', result.explanation)
        self.assertIn('92.0%', result.explanation)

    @pytest.mark.asyncio
    async def test_neutral_sentiment(self):
        """Test detection of neutral sentiment"""
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'NEUTRAL',
            'SentimentScore': {
                'Positive': 0.05,
                'Negative': 0.03,
                'Neutral': 0.90,
                'Mixed': 0.02
            }
        }
        
        model_input = Score.Input(
            text="The product arrived on Tuesday. It is blue.",
            metadata={}
        )
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        self.assertEqual(result.value, 'NEUTRAL')
        self.assertIn('NEUTRAL', result.explanation)
        self.assertIn('90.0%', result.explanation)

    @pytest.mark.asyncio
    async def test_mixed_sentiment(self):
        """Test detection of mixed sentiment"""
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'MIXED',
            'SentimentScore': {
                'Positive': 0.35,
                'Negative': 0.40,
                'Neutral': 0.10,
                'Mixed': 0.15
            }
        }
        
        model_input = Score.Input(
            text="The product quality is great, but the customer service was horrible.",
            metadata={}
        )
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        self.assertEqual(result.value, 'MIXED')
        self.assertIn('MIXED', result.explanation)

    @pytest.mark.asyncio
    async def test_text_truncation_at_byte_limit(self):
        """Test that text is truncated to 5000 byte limit"""
        # Create text that exceeds 5000 bytes
        long_text = "A" * 6000
        
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'NEUTRAL',
            'SentimentScore': {
                'Positive': 0.25,
                'Negative': 0.25,
                'Neutral': 0.25,
                'Mixed': 0.25
            }
        }
        
        model_input = Score.Input(text=long_text, metadata={})
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        # Check that detect_sentiment was called with truncated text
        call_args = self.mock_comprehend_client.detect_sentiment.call_args
        called_text = call_args[1]['Text']
        
        # Verify the text was truncated
        self.assertLessEqual(len(called_text.encode('utf-8')), 5000)
        
        # Verify explanation mentions truncation
        self.assertIn('truncated', result.explanation.lower())
        self.assertIn('6000 bytes', result.explanation)

    @pytest.mark.asyncio
    async def test_multibyte_character_truncation(self):
        """Test that truncation doesn't break multi-byte UTF-8 characters"""
        # Create text with multi-byte characters (emoji, Chinese, etc.)
        # Each emoji is typically 4 bytes
        text = "Hello " + "😀" * 1250 + " World"  # ~5000 bytes
        
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'POSITIVE',
            'SentimentScore': {
                'Positive': 0.8,
                'Negative': 0.1,
                'Neutral': 0.05,
                'Mixed': 0.05
            }
        }
        
        model_input = Score.Input(text=text, metadata={})
        
        # Should not raise UnicodeDecodeError
        result = await self.score.predict(context=None, model_input=model_input)
        
        # Verify result is valid
        self.assertEqual(result.value, 'POSITIVE')
        
        # Verify the truncated text is valid UTF-8
        call_args = self.mock_comprehend_client.detect_sentiment.call_args
        called_text = call_args[1]['Text']
        
        # Should be able to encode/decode without errors
        called_text.encode('utf-8').decode('utf-8')

    @pytest.mark.asyncio
    async def test_empty_text(self):
        """Test handling of empty text"""
        model_input = Score.Input(text="", metadata={})
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        # Should return NEUTRAL for empty text without calling API
        self.assertEqual(result.value, 'NEUTRAL')
        self.mock_comprehend_client.detect_sentiment.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_only_text(self):
        """Test handling of whitespace-only text"""
        model_input = Score.Input(text="   \n\t  ", metadata={})
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        # Should return NEUTRAL for whitespace-only text without calling API
        self.assertEqual(result.value, 'NEUTRAL')
        self.mock_comprehend_client.detect_sentiment.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test handling of AWS API errors"""
        # Mock an AWS ClientError
        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Rate exceeded'
            }
        }
        self.mock_comprehend_client.detect_sentiment.side_effect = ClientError(
            error_response, 'DetectSentiment'
        )
        
        model_input = Score.Input(text="Test text", metadata={})
        
        # Should raise an exception with meaningful error message
        with self.assertRaises(Exception) as context:
            self.score.predict(context=None, model_input=model_input)
        
        self.assertIn('Failed to detect sentiment', str(context.exception))
        self.assertIn('Rate exceeded', str(context.exception))

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self):
        """Test handling of unexpected errors"""
        # Mock an unexpected error
        self.mock_comprehend_client.detect_sentiment.side_effect = RuntimeError("Unexpected error")
        
        model_input = Score.Input(text="Test text", metadata={})
        
        # Should raise an exception
        with self.assertRaises(Exception):
            self.score.predict(context=None, model_input=model_input)

    @pytest.mark.asyncio
    async def test_confidence_scores_in_explanation(self):
        """Test that all confidence scores are included in explanation"""
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'POSITIVE',
            'SentimentScore': {
                'Positive': 0.75,
                'Negative': 0.10,
                'Neutral': 0.12,
                'Mixed': 0.03
            }
        }
        
        model_input = Score.Input(text="Great product!", metadata={})
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        # Check that all scores are in explanation
        self.assertIn('Positive: 75.0%', result.explanation)
        self.assertIn('Negative: 10.0%', result.explanation)
        self.assertIn('Neutral: 12.0%', result.explanation)
        self.assertIn('Mixed: 3.0%', result.explanation)

    @pytest.mark.asyncio
    async def test_with_customer_filtered_input(self):
        """Test sentiment detection on customer-only filtered text"""
        # Simulate text that has been filtered to customer-only
        customer_text = "I'm very happy with the service. Everything went smoothly."
        
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'POSITIVE',
            'SentimentScore': {
                'Positive': 0.88,
                'Negative': 0.03,
                'Neutral': 0.07,
                'Mixed': 0.02
            }
        }
        
        model_input = Score.Input(text=customer_text, metadata={})
        
        result = await self.score.predict(context=None, model_input=model_input)
        
        self.assertEqual(result.value, 'POSITIVE')
        self.assertIn('88.0%', result.explanation)

    @pytest.mark.asyncio
    async def test_truncate_to_byte_limit_exact_limit(self):
        """Test truncation when text is exactly at the limit"""
        text = "A" * 5000
        truncated = self.score._truncate_to_byte_limit(text, 5000)
        
        self.assertEqual(len(truncated.encode('utf-8')), 5000)
        self.assertEqual(text, truncated)

    @pytest.mark.asyncio
    async def test_truncate_to_byte_limit_under_limit(self):
        """Test truncation when text is under the limit"""
        text = "Hello world"
        truncated = self.score._truncate_to_byte_limit(text, 5000)
        
        self.assertEqual(text, truncated)

    @pytest.mark.asyncio
    async def test_truncate_to_byte_limit_over_limit(self):
        """Test truncation when text is over the limit"""
        text = "A" * 6000
        truncated = self.score._truncate_to_byte_limit(text, 5000)
        
        self.assertLessEqual(len(truncated.encode('utf-8')), 5000)
        self.assertLess(len(truncated), len(text))

    @pytest.mark.asyncio
    async def test_language_code_is_english(self):
        """Test that language code is set to 'en'"""
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'NEUTRAL',
            'SentimentScore': {
                'Positive': 0.25,
                'Negative': 0.25,
                'Neutral': 0.25,
                'Mixed': 0.25
            }
        }
        
        model_input = Score.Input(text="Test", metadata={})
        self.score.predict(context=None, model_input=model_input)
        
        # Verify language code is 'en'
        call_args = self.mock_comprehend_client.detect_sentiment.call_args
        self.assertEqual(call_args[1]['LanguageCode'], 'en')

    @pytest.mark.asyncio
    async def test_result_has_parameters(self):
        """Test that result includes score parameters"""
        self.mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'POSITIVE',
            'SentimentScore': {
                'Positive': 0.9,
                'Negative': 0.03,
                'Neutral': 0.05,
                'Mixed': 0.02
            }
        }
        
        model_input = Score.Input(text="Great!", metadata={})
        result = await self.score.predict(context=None, model_input=model_input)
        
        self.assertIsNotNone(result.parameters)
        self.assertEqual(result.parameters.name, "Test Sentiment")


if __name__ == '__main__':
    unittest.main()

