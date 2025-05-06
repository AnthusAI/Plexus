import pytest
import os
from unittest.mock import patch
from plexus.Scorecard import Scorecard
from plexus.scores.LangGraphScore import LangGraphScore
from plexus.scores.Score import Score
from plexus.Registries import scorecard_registry
from decimal import Decimal

class TestLangGraphScore(LangGraphScore):
    """A concrete implementation of LangGraphScore for testing."""
    async def predict(self, *, context, model_input):
        """Simple implementation that echoes back the input text."""
        return Score.Result(
            parameters=Score.Parameters(
                name="TestScore",
                scorecard_name="TestScorecard",
                data={"percentage": 100}
            ),
            value="Pass",
            metadata={"text": model_input.text}
        )

    @classmethod
    async def create(cls, **kwargs):
        """Simple creation method."""
        return cls()

    def get_accumulated_costs(self):
        """Return some dummy costs for testing."""
        return {
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'cached_tokens': 0,
            'llm_calls': 1,
            'total_cost': Decimal('0.15')
        }

@pytest.fixture
def test_scorecard():
    """Create a test scorecard with a LangGraphScore."""
    scorecard_properties = {
        'name': 'TestScorecard',
        'id': 'test-scorecard-1',
        'scores': [{
            'name': 'TestScore',
            'id': 'test-score-1',
            'class': 'TestLangGraphScore'
        }]
    }

    # Create and register the scorecard class
    scorecard_class = type('TestScorecard', (Scorecard,), {
        'properties': scorecard_properties,
        'name': scorecard_properties['name'],
        'scores': scorecard_properties['scores'],
        'score_registry': None
    })
    
    # Initialize the registry
    scorecard_class.initialize_registry()
    
    # Register the score
    scorecard_class.score_registry.register(
        cls=TestLangGraphScore,
        properties=scorecard_properties['scores'][0],
        name=scorecard_properties['scores'][0]['name'],
        id=scorecard_properties['scores'][0]['id']
    )

    return scorecard_class(scorecard='test-scorecard-1')

@pytest.mark.asyncio
async def test_scorecard_langgraph_interface(test_scorecard):
    """Test that Scorecard correctly interfaces with LangGraphScore."""
    # Set required environment variables
    with patch.dict(os.environ, {'PLEXUS_ACCOUNT_KEY': 'test-key', 'environment': 'test'}):
        # Test scoring
        result = await test_scorecard.get_score_result(
            scorecard='test-scorecard-1',
            score='TestScore',
            text='Test content',
            metadata={},
            modality='Test',
            results=[]
        )

        # Verify we get a list with one result
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Score.Result)
        assert result[0].value == "Pass"
        assert result[0].metadata["text"] == "Test content"

@pytest.mark.asyncio
async def test_scorecard_cost_tracking(test_scorecard):
    """Test that Scorecard correctly tracks and logs costs from LangGraphScore."""
    # Set required environment variables
    with patch.dict(os.environ, {'PLEXUS_ACCOUNT_KEY': 'test-key', 'environment': 'test'}):
        # Mock the CloudWatch logger to verify metrics
        with patch.object(test_scorecard.cloudwatch_logger, 'log_metric') as mock_log_metric:
            await test_scorecard.get_score_result(
                scorecard='test-scorecard-1',
                score='TestScore',
                text='Test content',
                metadata={},
                modality='Test',
                results=[]
            )

            # Verify that all expected metrics were logged
            expected_metrics = [
                ('Cost', Decimal('0.15')),
                ('PromptTokens', 100),
                ('CompletionTokens', 50),
                ('TotalTokens', 150),
                ('CachedTokens', 0),
                ('ExternalAIRequests', 1),
                ('CostByScorecard', Decimal('0.15')),
                ('PromptTokensByScorecard', 100),
                ('CompletionTokensByScorecard', 50),
                ('TotalTokensByScorecard', 150),
                ('CachedTokensByScorecard', 0),
                ('ExternalAIRequestsByScorecard', 1)
            ]

            # Check that each metric was logged with correct values
            actual_calls = [(call[0][0], call[0][1]) for call in mock_log_metric.call_args_list]
            for metric, value in expected_metrics:
                assert (metric, value) in actual_calls, f"Missing or incorrect metric: {metric}"

@pytest.mark.asyncio
async def test_scorecard_error_handling(test_scorecard):
    """Test that Scorecard properly handles errors from LangGraphScore."""
    class ErrorScore(TestLangGraphScore):
        async def predict(self, *, context, model_input):
            raise ValueError("Test error")

    # Register the error score
    test_scorecard.score_registry.register(
        cls=ErrorScore,
        properties={'name': 'ErrorScore', 'id': 'error-score-1'},
        name='ErrorScore',
        id='error-score-1'
    )

    # Test error handling
    with patch.dict(os.environ, {'PLEXUS_ACCOUNT_KEY': 'test-key', 'environment': 'test'}):
        with pytest.raises(ValueError, match="Test error"):
            await test_scorecard.get_score_result(
                scorecard='test-scorecard-1',
                score='ErrorScore',
                text='Test content',
                metadata={},
                modality='Test',
                results=[]
            ) 