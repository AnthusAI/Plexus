#!/usr/bin/env python3
"""
Comprehensive tests for PredictionCommands.py - the mission-critical scoring system.

This test suite focuses on the most critical aspects of the prediction pipeline:
- Score.Input creation and text/metadata preparation
- Prediction orchestration and error handling
- Parallel processing coordination
- Integration with scorecard registry
- Cost tracking and resource cleanup

The prediction system is the core of Plexus scoring and handles:
1. Input text and metadata preparation for predictions
2. Async prediction orchestration with proper cleanup
3. Multi-score parallel processing
4. Error propagation and recovery
5. Progress tracking and feedback integration
"""

import pytest
import asyncio
import json
import pandas as pd
from unittest.mock import MagicMock, patch, AsyncMock, call
from decimal import Decimal

from plexus.cli.prediction.predictions import (
    create_score_input,
    predict_score,
    predict_score_impl,
    create_feedback_comparison,
    select_sample
)
from plexus.scores.Score import Score
from plexus.scores.LangGraphScore import BatchProcessingPause


class MockScorecard:
    """Mock scorecard for testing"""
    def __init__(self, key="test_scorecard"):
        self.properties = {'key': key}
        self.key = key


class MockScore:
    """Mock score instance for testing"""
    def __init__(self, name="test_score", costs=None):
        self.parameters = Score.Parameters(name=name, scorecard_name="test_scorecard")
        self.Input = Score.Input
        self._costs = costs or {'total_cost': 10.0}
        self.setup_called = False
        self.predict_called = False
        self.cleanup_called = False
    
    async def async_setup(self):
        self.setup_called = True
    
    async def predict(self, input_data):
        self.predict_called = True
        return Score.Result(
            parameters=self.parameters,
            value="test_result",
            explanation="Test prediction result",
            metadata={"trace": {"test": "trace_data"}}
        )
    
    def get_accumulated_costs(self):
        return self._costs
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_called = True
        return False


@pytest.fixture
def mock_scorecard():
    """Mock scorecard for testing"""
    return MockScorecard()


@pytest.fixture
def sample_pandas_row():
    """Create a sample pandas row with text and metadata"""
    data = {
        'text': 'This is a test transcript for scoring',
        'metadata': json.dumps({
            'source': 'test',
            'timestamp': '2023-01-01T00:00:00Z',
            'session_id': 'test_session_123'
        }),
        'item_id': 'test_item_123'
    }
    df = pd.DataFrame([data])
    return df


@pytest.fixture
def sample_row_with_complex_metadata():
    """Create a sample row with complex nested metadata"""
    complex_metadata = {
        'source': 'phone_call',
        'caller_info': {
            'phone': '+1234567890',
            'name': 'John Doe'
        },
        'conversation_metadata': {
            'duration': 300,
            'quality_score': 0.95,
            'topics': ['billing', 'support', 'technical_issue']
        },
        'system_info': {
            'recording_id': 'rec_456789',
            'agent_id': 'agent_001'
        }
    }
    data = {
        'text': 'Complex conversation transcript with detailed metadata',
        'metadata': json.dumps(complex_metadata),
        'item_id': 'complex_item_456'
    }
    df = pd.DataFrame([data])
    return df


class TestScoreInputCreation:
    """Test the critical Score.Input creation and validation process"""
    
    def test_basic_score_input_creation(self, mock_scorecard, sample_pandas_row):
        """Test basic Score.Input creation from sample data"""
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=sample_pandas_row,
                item_id="test_item_123",
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            assert isinstance(score_input, Score.Input)
            assert score_input.text == 'This is a test transcript for scoring'
            assert isinstance(score_input.metadata, dict)
            assert score_input.metadata['source'] == 'test'
            assert score_input.metadata['timestamp'] == '2023-01-01T00:00:00Z'
            assert score_input.metadata['item_id'] == 'test_item_123'
    
    def test_score_input_with_complex_metadata(self, mock_scorecard, sample_row_with_complex_metadata):
        """Test Score.Input creation with complex nested metadata"""
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=sample_row_with_complex_metadata,
                item_id="complex_item_456",
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            assert score_input.text == 'Complex conversation transcript with detailed metadata'
            assert score_input.metadata['source'] == 'phone_call'
            assert score_input.metadata['caller_info']['name'] == 'John Doe'
            assert score_input.metadata['conversation_metadata']['duration'] == 300
            assert len(score_input.metadata['conversation_metadata']['topics']) == 3
            assert score_input.metadata['item_id'] == 'complex_item_456'
    
    def test_score_input_with_empty_text(self, mock_scorecard):
        """Test Score.Input creation with empty text"""
        empty_data = pd.DataFrame([{'text': '', 'metadata': '{}'}])
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=empty_data,
                item_id="empty_text_item",
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            assert score_input.text == ''
            assert score_input.metadata['item_id'] == 'empty_text_item'
    
    def test_score_input_with_malformed_metadata(self, mock_scorecard):
        """Test Score.Input creation with invalid JSON metadata"""
        malformed_data = pd.DataFrame([{
            'text': 'Test text with bad metadata',
            'metadata': '{"invalid": json, syntax}'  # Invalid JSON
        }])
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            # Should raise JSONDecodeError when parsing invalid metadata
            with pytest.raises(json.JSONDecodeError):
                create_score_input(
                    sample_row=malformed_data,
                    item_id="malformed_item",
                    scorecard_class=mock_scorecard,
                    score_name="test_score"
                )
    
    def test_score_input_with_none_sample_row(self, mock_scorecard):
        """Test Score.Input creation when sample_row is None (fallback case)"""
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=None,
                item_id="none_sample_item",
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            assert score_input.text == ''
            assert score_input.metadata == {'item_id': 'none_sample_item'}
    
    def test_score_input_with_missing_input_class(self, mock_scorecard, sample_pandas_row):
        """Test fallback to Score.Input when custom Input class is not available"""
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            # Create a mock score without Input class
            mock_score = MagicMock()
            mock_score.Input = None  # No custom Input class
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=sample_pandas_row,
                item_id="test_item_123",
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            # Should fall back to Score.Input
            assert isinstance(score_input, Score.Input)
            assert score_input.text == 'This is a test transcript for scoring'
    
    def test_metadata_item_id_preservation(self, mock_scorecard):
        """Test that existing item_id in metadata is preserved"""
        data_with_existing_item_id = pd.DataFrame([{
            'text': 'Test text',
            'metadata': json.dumps({'item_id': 'existing_item_789', 'other': 'data'})
        }])
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=data_with_existing_item_id,
                item_id="new_item_123",  # This should NOT override existing
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            # The item_id from metadata should be preserved
            assert score_input.metadata['item_id'] == 'existing_item_789'
            assert score_input.metadata['other'] == 'data'


class TestPredictionOrchestration:
    """Test the core prediction orchestration and async handling"""
    
    @pytest.mark.asyncio
    async def test_successful_predict_score(self, mock_scorecard, sample_pandas_row):
        """Test successful prediction with proper async orchestration"""
        with patch('plexus.cli.prediction.predictions.predict_score_impl') as mock_predict_impl, \
             patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            
            # Mock the score class used in create_score_input
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            mock_result = Score.Result(
                parameters=Score.Parameters(name="test_score", scorecard_name="test_scorecard"),
                value="success",
                explanation="Test successful prediction",
                metadata={"cost": 5.0}
            )
            mock_predict_impl.return_value = ("test_text", mock_result, {"total_cost": 5.0})
            
            transcript, predictions, costs = await predict_score(
                score_name="test_score",
                scorecard_class=mock_scorecard,
                sample_row=sample_pandas_row,
                used_item_id="test_item_123"
            )
            
            assert transcript == "test_text"
            assert predictions.value == "success"
            assert predictions.explanation == "Test successful prediction"
            assert costs["total_cost"] == 5.0
            
            # Verify predict_score_impl was called with correct parameters
            mock_predict_impl.assert_called_once()
            call_args = mock_predict_impl.call_args
            assert call_args[1]['scorecard_class'] == mock_scorecard
            assert call_args[1]['score_name'] == "test_score"
            assert call_args[1]['item_id'] == "test_item_123"
            assert isinstance(call_args[1]['input_data'], Score.Input)
    
    @pytest.mark.asyncio
    async def test_predict_score_with_batch_processing_pause(self, mock_scorecard, sample_pandas_row):
        """Test that BatchProcessingPause exceptions are properly propagated"""
        with patch('plexus.cli.prediction.predictions.predict_score_impl') as mock_predict_impl, \
             patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            mock_predict_impl.side_effect = BatchProcessingPause("test_thread_123", {"test": "state"})
            
            with pytest.raises(BatchProcessingPause):
                await predict_score(
                    score_name="test_score",
                    scorecard_class=mock_scorecard,
                    sample_row=sample_pandas_row,
                    used_item_id="test_item_123"
                )
    
    @pytest.mark.asyncio
    async def test_predict_score_with_general_exception(self, mock_scorecard, sample_pandas_row):
        """Test error handling for general exceptions during prediction"""
        with patch('plexus.cli.prediction.predictions.predict_score_impl') as mock_predict_impl, \
             patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            mock_predict_impl.side_effect = RuntimeError("Prediction failed")
            
            with pytest.raises(RuntimeError, match="Prediction failed"):
                await predict_score(
                    score_name="test_score",
                    scorecard_class=mock_scorecard,
                    sample_row=sample_pandas_row,
                    used_item_id="test_item_123"
                )
    
    @pytest.mark.asyncio
    async def test_predict_score_with_empty_result(self, mock_scorecard, sample_pandas_row):
        """Test handling when prediction returns None or empty result"""
        with patch('plexus.cli.prediction.predictions.predict_score_impl') as mock_predict_impl, \
             patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            mock_predict_impl.return_value = (None, None, None)
            
            result = await predict_score(
                score_name="test_score",
                scorecard_class=mock_scorecard,
                sample_row=sample_pandas_row,
                used_item_id="test_item_123"
            )
            
            assert result == (None, None, None)


class TestPredictScoreImpl:
    """Test the core prediction implementation with proper resource management"""
    
    @pytest.mark.asyncio
    async def test_predict_score_impl_success(self, mock_scorecard):
        """Test successful prediction implementation with proper setup and cleanup"""
        mock_score = MockScore()
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_from_name.return_value = mock_score
            
            input_data = Score.Input(
                text="Test prediction text",
                metadata={"test": "metadata"}
            )
            
            score_instance, prediction, costs = await predict_score_impl(
                scorecard_class=mock_scorecard,
                score_name="test_score",
                item_id="test_item_123",
                input_data=input_data
            )
            
            # Verify proper lifecycle management
            assert mock_score.setup_called
            assert mock_score.predict_called
            assert mock_score.cleanup_called
            
            # Verify result
            assert score_instance == mock_score
            assert prediction.value == "test_result"
            assert prediction.explanation == "Test prediction result"
            assert costs == {'total_cost': 10.0}
    
    @pytest.mark.asyncio
    async def test_predict_score_impl_with_score_without_costs(self, mock_scorecard):
        """Test prediction when score doesn't have cost tracking"""
        class MockScoreNoCosts:
            def __init__(self):
                self.parameters = Score.Parameters(name="test_score", scorecard_name="test_scorecard")
                self.setup_called = False
                self.predict_called = False
                self.cleanup_called = False
            
            async def async_setup(self):
                self.setup_called = True
            
            async def predict(self, input_data):
                self.predict_called = True
                return Score.Result(
                    parameters=self.parameters,
                    value="no_costs_result",
                    explanation="Result without costs"
                )
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.cleanup_called = True
                return False
            
            # Note: No get_accumulated_costs method
        
        mock_score = MockScoreNoCosts()
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_from_name.return_value = mock_score
            
            input_data = Score.Input(text="Test", metadata={})
            
            transcript, prediction, costs = await predict_score_impl(
                scorecard_class=mock_scorecard,
                score_name="test_score",
                item_id="test_item_123",
                input_data=input_data
            )
            
            assert prediction.value == "no_costs_result"
            assert costs is None  # Should be None when no cost tracking available
    
    @pytest.mark.asyncio
    async def test_predict_score_impl_cost_calculation_error(self, mock_scorecard):
        """Test handling when cost calculation fails"""
        class MockScoreFailingCosts:
            def __init__(self):
                self.parameters = Score.Parameters(name="test_score", scorecard_name="test_scorecard")
            
            async def async_setup(self):
                pass
            
            async def predict(self, input_data):
                return Score.Result(
                    parameters=self.parameters,
                    value="success",
                    explanation="Success despite cost error"
                )
            
            def get_accumulated_costs(self):
                raise RuntimeError("Cost calculation failed")
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False
        
        mock_score = MockScoreFailingCosts()
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_from_name.return_value = mock_score
            
            input_data = Score.Input(text="Test", metadata={})
            
            transcript, prediction, costs = await predict_score_impl(
                scorecard_class=mock_scorecard,
                score_name="test_score",
                item_id="test_item_123",
                input_data=input_data
            )
            
            assert prediction.value == "success"
            assert costs is None  # Should be None when cost calculation fails


class TestFeedbackComparison:
    """Test feedback comparison functionality"""
    
    def test_create_feedback_comparison_basic(self):
        """Test basic feedback comparison creation"""
        row_result = {
            'item_id': 'test_item_123',
            'test_score_value': 'yes',
            'test_score_explanation': 'Found clear indication'
        }
        
        # Mock feedback item with finalAnswerValue attribute
        feedback_item = MagicMock()
        feedback_item.finalAnswerValue = 'yes'
        
        comparison = create_feedback_comparison(row_result, feedback_item, 'test_score')
        
        assert comparison['current_prediction']['value'] == 'yes'
        assert comparison['current_prediction']['explanation'] == 'Found clear indication'
        assert comparison['ground_truth'] == 'yes'
        assert comparison['isAgreement'] == True
    
    def test_create_feedback_comparison_disagreement(self):
        """Test feedback comparison when prediction disagrees with ground truth"""
        row_result = {
            'item_id': 'test_item_123',
            'test_score_value': 'no',
            'test_score_explanation': 'No clear evidence found'
        }
        
        # Mock feedback item with finalAnswerValue attribute
        feedback_item = MagicMock()
        feedback_item.finalAnswerValue = 'yes'
        
        comparison = create_feedback_comparison(row_result, feedback_item, 'test_score')
        
        assert comparison['current_prediction']['value'] == 'no'
        assert comparison['ground_truth'] == 'yes'
        assert comparison['isAgreement'] == False
    
    def test_create_feedback_comparison_case_insensitive(self):
        """Test that feedback comparison is case insensitive"""
        row_result = {
            'item_id': 'test_item_123',
            'test_score_value': 'YES',
            'test_score_explanation': 'Uppercase result'
        }
        
        # Mock feedback item with finalAnswerValue attribute
        feedback_item = MagicMock()
        feedback_item.finalAnswerValue = 'yes'
        
        comparison = create_feedback_comparison(row_result, feedback_item, 'test_score')
        
        assert comparison['isAgreement'] == True  # Should match despite case difference


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios"""
    
    def test_score_input_with_very_long_text(self, mock_scorecard):
        """Test Score.Input creation with very long text content"""
        # Create text that's 100KB long
        long_text = "This is a very long transcript. " * 3000  # ~100KB
        
        long_data = pd.DataFrame([{
            'text': long_text,
            'metadata': json.dumps({'source': 'long_call'})
        }])
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=long_data,
                item_id="long_text_item",
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            assert len(score_input.text) > 90000  # Should preserve long text
            assert score_input.metadata['source'] == 'long_call'
    
    def test_score_input_with_unicode_text(self, mock_scorecard):
        """Test Score.Input creation with Unicode and special characters"""
        unicode_text = "Test with émojis 🎉, accénts, and 中文字符"
        
        unicode_data = pd.DataFrame([{
            'text': unicode_text,
            'metadata': json.dumps({'language': 'mixed', 'encoding': 'utf-8'})
        }])
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=unicode_data,
                item_id="unicode_item",
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            assert score_input.text == unicode_text
            assert score_input.metadata['language'] == 'mixed'
    
    def test_score_input_with_numeric_item_id(self, mock_scorecard, sample_pandas_row):
        """Test Score.Input creation with numeric item_id (should be converted to string)"""
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=sample_pandas_row,
                item_id=12345,  # Numeric ID
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            assert score_input.metadata['item_id'] == '12345'  # Should be string
    
    def test_score_input_with_decimal_in_metadata(self, mock_scorecard):
        """Test Score.Input creation with Decimal objects in metadata"""
        decimal_metadata = {
            'cost': Decimal('10.50'),
            'confidence': Decimal('0.95'),
            'other_data': 'normal_string'
        }
        
        decimal_data = pd.DataFrame([{
            'text': 'Test with decimal metadata',
            'metadata': json.dumps(decimal_metadata, default=str)  # Convert Decimal to string
        }])
        
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=decimal_data,
                item_id="decimal_item",
                scorecard_class=mock_scorecard,
                score_name="test_score"
            )
            
            # Decimals should be converted to strings in JSON, then back to strings
            assert score_input.metadata['cost'] == '10.50'
            assert score_input.metadata['confidence'] == '0.95'
            assert score_input.metadata['other_data'] == 'normal_string'


class TestIntegrationWithScoreRegistry:
    """Test integration with the Score registry system"""
    
    def test_score_from_name_integration(self, mock_scorecard, sample_pandas_row):
        """Test that create_score_input properly integrates with Score.from_name"""
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_score = MockScore()
            mock_from_name.return_value = mock_score
            
            score_input = create_score_input(
                sample_row=sample_pandas_row,
                item_id="registry_test_item",
                scorecard_class=mock_scorecard,
                score_name="registry_test_score"
            )
            
            # Verify Score.from_name was called with correct parameters
            mock_from_name.assert_called_once_with("test_scorecard", "registry_test_score")
            
            # Verify the score input was created correctly
            assert isinstance(score_input, Score.Input)
            assert score_input.text == 'This is a test transcript for scoring'
    
    def test_score_from_name_error_handling(self, mock_scorecard, sample_pandas_row):
        """Test error handling when Score.from_name fails"""
        with patch('plexus.cli.prediction.predictions.Score.from_name') as mock_from_name:
            mock_from_name.side_effect = ValueError("Score 'nonexistent_score' not found")
            
            with pytest.raises(ValueError, match="Score 'nonexistent_score' not found"):
                create_score_input(
                    sample_row=sample_pandas_row,
                    item_id="error_test_item",
                    scorecard_class=mock_scorecard,
                    score_name="nonexistent_score"
                )


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])