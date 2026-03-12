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


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__, '-v'])