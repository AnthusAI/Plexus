import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from plexus.reports.blocks.feedback_analysis import FeedbackAnalysis
from plexus.dashboard.api.models.feedback_item import FeedbackItem


@pytest.fixture
def mock_api_client():
    """Creates a mock API client."""
    client = MagicMock()
    client.account_id = "test-account-id"
    
    # Mock the execute method and its results for scorecard lookup
    scorecard_mock = MagicMock()
    scorecard_mock.id = "test-scorecard-id"
    scorecard_mock.name = "Test Scorecard"
    
    # Set up the return value for Scorecard.get_by_external_id
    client.execute.return_value = {
        'getScorecard': {
            'id': 'test-scorecard-id',
            'name': 'Test Scorecard',
            'sections': {
                'items': [
                    {
                        'id': 'section-1',
                        'scores': {
                            'items': [
                                {
                                    'id': 'score1',
                                    'name': 'Score 1',
                                    'externalId': 'score1'
                                },
                                {
                                    'id': 'score2',
                                    'name': 'Score 2',
                                    'externalId': 'score2'
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }
    
    return client


@pytest.fixture
def mock_feedback_items():
    """Creates mock feedback items for testing."""
    items = []
    
    # Create 10 items for score1 - 3 mismatches (70% agreement)
    for i in range(10):
        is_mismatch = i < 3  # 3 out of 10 are mismatches
        item = MagicMock(spec=FeedbackItem)
        item.id = f"item-score1-{i}"
        item.accountId = "test-account-id"
        item.scorecardId = "test-scorecard-id"
        item.scoreId = "score1"
        item.externalId = f"form-{i}"
        item.initialAnswerValue = "Yes" if is_mismatch else "No"
        item.finalAnswerValue = "No" if is_mismatch else "No"
        item.isMismatch = is_mismatch
        
        # Add updatedAt attribute with a timezone-aware timestamp within the test range
        now = datetime.now(timezone.utc)
        item.updatedAt = now - timedelta(days=5)  # Within the default 14 days
        
        items.append(item)
    
    # Create 5 items for score2 - 1 mismatch (80% agreement)
    for i in range(5):
        is_mismatch = i < 1  # 1 out of 5 is a mismatch
        item = MagicMock(spec=FeedbackItem)
        item.id = f"item-score2-{i}"
        item.accountId = "test-account-id"
        item.scorecardId = "test-scorecard-id"
        item.scoreId = "score2"
        item.externalId = f"form-{i+10}"
        item.initialAnswerValue = "Good" if is_mismatch else "Better"
        item.finalAnswerValue = "Better" if is_mismatch else "Better"
        item.isMismatch = is_mismatch
        
        # Add updatedAt attribute with a timezone-aware timestamp within the test range
        now = datetime.now(timezone.utc)
        item.updatedAt = now - timedelta(days=5)  # Within the default 14 days
        
        items.append(item)
    
    return items


class TestFeedbackAnalysis:
    """Tests for the FeedbackAnalysis class."""
    
    @pytest.mark.asyncio
    async def test_generate_with_data(self, mock_api_client, mock_feedback_items):
        """Tests generating a report with mock feedback data."""
        
        # Create the block with required configuration
        config = {
            "scorecard": "test-scorecard-id",
            "days": 14
        }
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Mock Scorecard get_by_external_id
        with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_external_id', return_value=MagicMock(id="test-scorecard-id", name="Test Scorecard")):
            # Mock _fetch_feedback_items_for_score to return test items
            with patch.object(block, '_fetch_feedback_items_for_score', return_value=mock_feedback_items):
                # Call the generate method
                output, logs = await block.generate()
                
                # Verify the output
                assert output is not None
                assert "overall_ac1" in output
                assert "scores" in output
                
                # The actual total items will be 30 because the implementation processes 
                # the same 15 mock_feedback_items for both score1 and score2
                assert output["total_items"] == 30
                assert output["total_mismatches"] == 8  # 4 mismatches for each score
                
                # Check that AC1 values are reasonable
                assert output["overall_ac1"] is not None
                assert isinstance(output["overall_ac1"], float)
                
                # Verify logs were generated
                assert logs is not None
                assert "Starting FeedbackAnalysis block generation" in logs
    
    @pytest.mark.asyncio
    async def test_generate_with_no_data(self, mock_api_client):
        """Tests generating a report with no feedback data."""
        
        # Create the block with required configuration
        config = {
            "scorecard": "test-scorecard-id",
            "days": 14
        }
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Mock Scorecard get_by_external_id
        with patch('plexus.dashboard.api.models.scorecard.Scorecard.get_by_external_id', return_value=MagicMock(id="test-scorecard-id", name="Test Scorecard")):
            # Mock _fetch_feedback_items_for_score to return empty list
            with patch.object(block, '_fetch_feedback_items_for_score', return_value=[]):
                # Call the generate method
                output, logs = await block.generate()
                
                # Verify the output shows empty results
                assert output is not None
                assert output["overall_ac1"] is None
                assert len(output["scores"]) > 0  # Expect empty score objects, not an empty list
                assert all(s["item_count"] == 0 for s in output["scores"])  # All scores should have 0 items
                assert output["total_items"] == 0
                
                # Verify logs were generated
                assert logs is not None
                # Updated to match actual log message
                assert "No date-filtered items available for overall analysis" in logs
    
    @pytest.mark.asyncio
    async def test_generate_with_missing_config(self, mock_api_client):
        """Tests generating a report with missing required configuration."""
        
        # Create the block with missing scorecard config
        config = {
            "days": 14
        }
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Call the generate method
        output, logs = await block.generate()
        
        # Verify the output contains error message
        assert output is not None
        assert "error" in output
        assert "'scorecard' is required in the block configuration." in output["error"]
        
        # Verify error logs were generated
        assert logs is not None
        assert "ERROR: 'scorecard'" in logs
    
    def test_analyze_feedback_data_gwet(self, mock_api_client, mock_feedback_items):
        """Tests the _analyze_feedback_data_gwet method directly."""
        
        # Create the block
        config = {"scorecard": "test-scorecard-id"}
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Call the _analyze_feedback_data_gwet method
        results = block._analyze_feedback_data_gwet(mock_feedback_items, "test-score")
        
        # Verify results
        assert results is not None
        assert "ac1" in results
        assert results["ac1"] is not None
        assert "item_count" in results
        assert "mismatches" in results
        assert results["mismatches"] == 4
        assert results["item_count"] == 15 