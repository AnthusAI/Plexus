import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from plexus.reports.blocks.feedback_analysis import FeedbackAnalysis
from plexus.dashboard.api.models.feedback_item import FeedbackItem


@pytest.fixture
def mock_api_client():
    """Creates a mock API client."""
    client = MagicMock()
    client.account_id = "test-account-id"
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
        
        # Mock the _fetch_feedback_items method to return our test data
        with patch.object(block, '_fetch_feedback_items', return_value=mock_feedback_items):
            # Call the generate method
            output, logs = await block.generate()
            
            # Verify the output
            assert output is not None
            assert "overall_ac1" in output
            assert "question_ac1s" in output
            assert "score1" in output["question_ac1s"]
            assert "score2" in output["question_ac1s"]
            assert output["total_items"] == 15
            assert output["total_mismatches"] == 4
            
            # Check that AC1 values are reasonable
            assert output["overall_ac1"] is not None
            assert isinstance(output["overall_ac1"], float)
            assert output["question_ac1s"]["score1"]["ac1"] is not None
            assert output["question_ac1s"]["score2"]["ac1"] is not None
            
            # Verify logs were generated
            assert logs is not None
            assert "Starting FeedbackAnalysis block generation" in logs
            assert "Feedback analysis completed successfully" in logs
    
    @pytest.mark.asyncio
    async def test_generate_with_no_data(self, mock_api_client):
        """Tests generating a report with no feedback data."""
        
        # Create the block with required configuration
        config = {
            "scorecard": "test-scorecard-id",
            "days": 14
        }
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Mock the _fetch_feedback_items method to return empty list
        with patch.object(block, '_fetch_feedback_items', return_value=[]):
            # Call the generate method
            output, logs = await block.generate()
            
            # Verify the output shows empty results
            assert output is not None
            assert output["overall_ac1"] is None
            assert output["question_ac1s"] == {}
            assert output["total_items"] == 0
            
            # Verify logs were generated
            assert logs is not None
            assert "No feedback items found for the specified criteria" in logs
    
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
        
        # Verify the output is None due to configuration error
        assert output is None
        
        # Verify error logs were generated
        assert logs is not None
        assert "ERROR: 'scorecard' identifier missing in block configuration" in logs
        assert "Configuration Error" in logs
    
    def test_analyze_feedback(self, mock_api_client, mock_feedback_items):
        """Tests the _analyze_feedback method directly."""
        
        # Create the block
        config = {"scorecard": "test-scorecard-id"}
        block = FeedbackAnalysis(config, {}, mock_api_client)
        
        # Call the _analyze_feedback method
        results = block._analyze_feedback(mock_feedback_items)
        
        # Verify results
        assert results is not None
        assert "overall_ac1" in results
        assert results["overall_ac1"] is not None
        assert "question_ac1s" in results
        assert "score1" in results["question_ac1s"]
        assert "score2" in results["question_ac1s"]
        assert results["total_mismatches"] == 4
        
        # Check score1 details
        score1 = results["question_ac1s"]["score1"]
        assert score1["total_comparisons"] == 10
        assert score1["mismatches"] == 3
        assert score1["mismatch_percentage"] == 30.0
        
        # Check score2 details
        score2 = results["question_ac1s"]["score2"]
        assert score2["total_comparisons"] == 5
        assert score2["mismatches"] == 1
        assert score2["mismatch_percentage"] == 20.0 