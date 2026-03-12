import pytest
import asyncio
from unittest.mock import patch, MagicMock

from plexus.reports.blocks.score_info import ScoreInfo

# Mock API Client
@pytest.fixture
def mock_api_client():
    return MagicMock()

# Use pytest fixtures for cleaner setup
@pytest.fixture
def score_info_block(mock_api_client): # Depends on the mock client fixture
    # Provide empty initial config/params, specific test will override config via block.config
    return ScoreInfo(config={}, params={}, api_client=mock_api_client)

@pytest.mark.asyncio # Mark tests as async
async def test_score_info_generate_without_variant(score_info_block):
    """Tests the generate method without including the variant."""
    # Set config for this specific test via the instance attribute
    score_info_block.config = {"score": "score-abc-123"}

    # Call the async generate method
    output_data, log_string = await score_info_block.generate()

    # Assertions on the returned tuple
    assert output_data is not None
    assert output_data["type"] == "ScoreInfo"
    assert "data" in output_data
    assert output_data["data"]["id"] == "score-abc-123"
    assert output_data["data"]["name"] == "Mock Score scor..." # Corrected expected value
    assert "variant" not in output_data["data"]
    
    assert log_string is not None
    assert "Fetching info for score: score-abc-123" in log_string
    assert "include_variant: False" in log_string
    assert "ScoreInfo block generation successful." in log_string

@pytest.mark.asyncio
async def test_score_info_generate_with_variant(score_info_block):
    """Tests the generate method including the variant."""
    score_info_block.config = {"score": "score-def-456", "include_variant": True}

    output_data, log_string = await score_info_block.generate()

    assert output_data is not None
    assert output_data["type"] == "ScoreInfo"
    assert "data" in output_data
    assert output_data["data"]["id"] == "score-def-456"
    assert output_data["data"]["name"] == "Mock Score scor..." # Corrected expected value
    assert "variant" in output_data["data"]
    assert output_data["data"]["variant"] is not None
    assert output_data["data"]["variant"]["name"] == "Default Variant" # Based on current mock logic

    assert log_string is not None
    assert "Fetching info for score: score-def-456" in log_string
    assert "include_variant: True" in log_string
    assert "ScoreInfo block generation successful." in log_string

@pytest.mark.asyncio
async def test_score_info_generate_missing_score(score_info_block):
    """Tests the generate method when 'score' is missing in config."""
    score_info_block.config = {} # Missing score

    output_data, log_string = await score_info_block.generate()

    # Assert that output data is None due to the error
    assert output_data is None
    
    assert log_string is not None
    assert "ERROR: 'score' identifier missing in block configuration." in log_string
    # Check that the success message is NOT in the log
    assert "ScoreInfo block generation successful." not in log_string 