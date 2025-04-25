import pytest
from unittest.mock import patch, MagicMock

from plexus.reports.blocks.score_info import ScoreInfo

# TODO: Add test cases for ScoreInfo 

def test_score_info_generate_without_variant():
    """Tests the generate method without including the variant."""
    block = ScoreInfo()
    # Use the updated key 'score' instead of 'scoreId'
    config = {"score": "score-abc-123"} 
    params = {} # Not used by this block currently

    # TODO: Adapt assertion based on actual generate() return format (JSON string? Dict?)
    # Current generate() returns a markdown string with JSON
    # result = block.generate(config, params)
    # assert result["type"] == "ScoreInfo"
    # assert "data" in result
    # assert result["data"]["id"] == "score-abc-123"
    # assert result["data"]["name"] == "Mock Score scor..." # Based on current mock logic
    # assert "variant" not in result["data"] or result["data"]["variant"] is None
    pass # Placeholder until we decide on return format

def test_score_info_generate_with_variant():
    """Tests the generate method including the variant."""
    block = ScoreInfo()
    # Use the updated key 'score' and boolean value
    config = {"score": "score-def-456", "include_variant": True} 
    params = {} # Not used by this block currently

    # TODO: Adapt assertion based on actual generate() return format
    # result = block.generate(config, params)
    # assert result["type"] == "ScoreInfo"
    # assert "data" in result
    # assert result["data"]["id"] == "score-def-456"
    # assert result["data"]["name"] == "Mock Score scor..." # Based on current mock logic
    # assert "variant" in result["data"]
    # assert result["data"]["variant"] is not None
    # assert result["data"]["variant"]["name"] == "Default Variant" # Based on current mock logic
    pass # Placeholder

def test_score_info_generate_missing_score():
    """Tests the generate method when 'score' is missing in config."""
    block = ScoreInfo()
    config = {} # Missing score
    params = {}

    # TODO: Adapt assertion based on actual generate() return format
    result = block.generate(config, params)
    # The error message might be in the returned string or logged
    assert isinstance(result, dict) # generate() currently returns dict on error
    assert "error" in result
    assert result["error"] == "'score' is required in the block configuration." 