import pytest
from unittest.mock import patch, MagicMock

from plexus.reports.blocks.score_info import ScoreInfoBlock

# TODO: Add test cases for ScoreInfoBlock 

def test_score_info_block_generate_without_variant():
    """Tests the generate method without including the variant."""
    block = ScoreInfoBlock()
    config = {"scoreId": "score-abc-123"}
    params = {} # Not used by this block currently

    result = block.generate(config, params)

    assert result["type"] == "ScoreInfo"
    assert "data" in result
    assert result["data"]["id"] == "score-abc-123"
    assert result["data"]["name"] == "Mock Score scor..." # Based on current mock logic
    assert "variant" not in result["data"] or result["data"]["variant"] is None

def test_score_info_block_generate_with_variant():
    """Tests the generate method including the variant."""
    block = ScoreInfoBlock()
    config = {"scoreId": "score-def-456", "include_variant": True}
    params = {} # Not used by this block currently

    result = block.generate(config, params)

    assert result["type"] == "ScoreInfo"
    assert "data" in result
    assert result["data"]["id"] == "score-def-456"
    assert result["data"]["name"] == "Mock Score scor..." # Based on current mock logic
    assert "variant" in result["data"]
    assert result["data"]["variant"] is not None
    assert result["data"]["variant"]["name"] == "Default Variant" # Based on current mock logic

def test_score_info_block_generate_missing_score_id():
    """Tests the generate method when scoreId is missing in config."""
    block = ScoreInfoBlock()
    config = {} # Missing scoreId
    params = {}

    result = block.generate(config, params)

    assert "error" in result
    assert result["error"] == "scoreId is required in the block configuration." 